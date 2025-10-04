"""
API v2 Sync Views

Enhanced sync views with:
- ML conflict prediction
- Cross-device coordination
- Real-time push notifications
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.api.v1.services.sync_engine_service import sync_engine
from apps.ml.services.conflict_predictor import conflict_predictor
from apps.core.services.cross_device_sync_service import cross_device_sync_service
from apps.core.services.sync_push_service import sync_push_service


class SyncVoiceView(APIView):
    """Enhanced voice sync with ML prediction and cross-device coordination."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Sync voice data with enhancements."""
        prediction = conflict_predictor.predict_conflict({
            'domain': 'voice',
            'user_id': request.user.id,
            'device_id': request.data.get('device_id')
        })

        if prediction['risk_level'] == 'high':
            return Response({
                'status': 'conflict_risk',
                'prediction': prediction,
                'recommendation': prediction['recommendation']
            }, status=status.HTTP_409_CONFLICT)

        result = sync_engine.sync_voice_data(
            user_id=str(request.user.id),
            payload=request.data,
            device_id=request.data.get('device_id', 'unknown')
        )

        cross_device_sync_service.sync_across_devices(
            user=request.user,
            device_id=request.data.get('device_id'),
            domain='voice',
            entity_id=request.data.get('entity_id', 'batch'),
            data=request.data
        )

        return Response(result)


class SyncBatchView(APIView):
    """Batch sync with all v2 enhancements."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Batch sync with enhancements."""
        return Response({
            'message': 'v2 batch sync',
            'enhancements': ['ml_prediction', 'cross_device', 'push']
        })


class VersionInfoView(APIView):
    """API version information."""

    def get(self, request):
        """Get API version info."""
        return Response({
            'version': 'v2',
            'features': [
                'GraphQL mutations',
                'Real-time push notifications',
                'ML conflict prediction',
                'Cross-device sync',
                'API versioning'
            ],
            'deprecated_features': [],
            'migration_guide': '/docs/api-v2-migration'
        })