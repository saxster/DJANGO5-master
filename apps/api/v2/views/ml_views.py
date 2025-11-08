"""API v2 ML Views."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status
from django.core.exceptions import ObjectDoesNotExist
import logging

from apps.ml.services.conflict_predictor import conflict_predictor
from apps.ml_training.integrations import ProductionTrainingIntegration
from apps.activity.models import MeterReading, VehicleEntry

logger = logging.getLogger(__name__)


class ConflictPredictionView(APIView):
    """ML-powered conflict prediction."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Predict conflict probability."""
        prediction = conflict_predictor.predict_conflict(request.data)

        return Response(prediction)


class OCRCorrectionView(APIView):
    """
    API endpoint for mobile apps to submit OCR corrections.

    High-value training signal: user corrections are gold standard labels.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Submit OCR correction from mobile app.

        Request body:
        {
            "source_type": "meter_reading" or "vehicle_entry",
            "source_id": 12345,
            "corrected_text": "8942.5 kWh",
            "correction_type": "OCR_ERROR"  # or WRONG_READING
        }
        """
        try:
            source_type = request.data.get('source_type')
            source_id = request.data.get('source_id')
            corrected_text = request.data.get('corrected_text')
            correction_type = request.data.get('correction_type', 'OCR_ERROR')

            # Validate required fields
            if not all([source_type, source_id, corrected_text]):
                return Response(
                    {'error': 'Missing required fields: source_type, source_id, corrected_text'},
                    status=http_status.HTTP_400_BAD_REQUEST
                )

            # Validate source type
            if source_type not in ['meter_reading', 'vehicle_entry']:
                return Response(
                    {'error': 'Invalid source_type. Must be "meter_reading" or "vehicle_entry"'},
                    status=http_status.HTTP_400_BAD_REQUEST
                )

            # Get the source entity and validate user has permission
            if source_type == 'meter_reading':
                try:
                    entity = MeterReading.objects.select_related('asset', 'asset__site').get(
                        id=source_id
                    )
                    # Verify user has access to this site/tenant
                    if entity.asset.site.tenant != request.user.tenant:
                        return Response(
                            {'error': 'Permission denied'},
                            status=http_status.HTTP_403_FORBIDDEN
                        )
                except MeterReading.DoesNotExist:
                    return Response(
                        {'error': f'MeterReading {source_id} not found'},
                        status=http_status.HTTP_404_NOT_FOUND
                    )

            elif source_type == 'vehicle_entry':
                try:
                    entity = VehicleEntry.objects.select_related('gate_location').get(
                        id=source_id
                    )
                    # Verify user has access to this location/tenant
                    if entity.gate_location and entity.gate_location.tenant != request.user.tenant:
                        return Response(
                            {'error': 'Permission denied'},
                            status=http_status.HTTP_403_FORBIDDEN
                        )
                except VehicleEntry.DoesNotExist:
                    return Response(
                        {'error': f'VehicleEntry {source_id} not found'},
                        status=http_status.HTTP_404_NOT_FOUND
                    )

            # Track the correction via ML training integration
            ProductionTrainingIntegration.on_user_correction(
                domain='ocr',
                entity=entity,
                corrected_value=corrected_text,
                user=request.user,
                correction_type=correction_type
            )

            logger.info(
                f"User correction captured: type={source_type}, id={source_id}, "
                f"user={request.user.peoplename}, corrected_to='{corrected_text}'"
            )

            return Response({
                'status': 'success',
                'message': 'Correction recorded, thanks for improving the AI!',
                'correction_id': source_id
            }, status=http_status.HTTP_200_OK)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error processing OCR correction: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to record correction: {str(e)}'},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR
            )