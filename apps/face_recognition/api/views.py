"""
Face Recognition REST API Views (Sprint 2.5)

REST API endpoints for biometric face recognition:
- POST /api/v1/biometrics/face/enroll/ - Face enrollment
- POST /api/v1/biometrics/face/verify/ - Face verification
- GET  /api/v1/biometrics/face/quality/ - Quality assessment
- POST /api/v1/biometrics/face/liveness/ - Liveness detection

All endpoints require authentication and return OpenAPI-compliant responses.

Author: Development Team
Date: October 2025
"""

import logging
import uuid
import numpy as np
from rest_framework import status
from rest_framework.views import APIView
from apps.ontology.decorators import ontology
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from apps.core.exceptions.patterns import (
    FILE_EXCEPTIONS,
    BUSINESS_LOGIC_EXCEPTIONS
)

from apps.face_recognition.models import FaceEmbedding, BiometricConsentLog
from apps.face_recognition.services import (
    ImageQualityAssessmentService,
    LivenessDetectionService,
    EnsembleVerificationService
)
from apps.peoples.models import People
from .serializers import (
    FaceEnrollmentSerializer,
    FaceEnrollmentResponseSerializer,
    FaceVerificationSerializer,
    FaceVerificationResponseSerializer,
    FaceQualityAssessmentSerializer,
    FaceQualityAssessmentResponseSerializer,
    LivenessDetectionSerializer,
    LivenessDetectionResponseSerializer
)

logger = logging.getLogger(__name__)


@ontology(
    domain="biometrics",
    purpose="REST API for face biometric operations: enrollment, verification, quality assessment, and liveness detection with ensemble AI models",
    api_endpoint=True,
    http_methods=["POST"],
    authentication_required=True,
    permissions=["IsAuthenticated"],
    rate_limit="30/minute",
    request_schema="FaceEnrollmentSerializer|FaceVerificationSerializer|FaceQualityAssessmentSerializer|LivenessDetectionSerializer",
    response_schema="FaceEnrollmentResponseSerializer|FaceVerificationResponseSerializer|FaceQualityAssessmentResponseSerializer|LivenessDetectionResponseSerializer",
    error_codes=[400, 401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "biometrics", "face-recognition", "ai", "ml", "security", "mobile"],
    security_notes="Consent logging required. Embeddings hashed. Multi-model ensemble (FaceNet512 primary). Liveness detection for anti-spoofing. Quality thresholds enforced",
    endpoints={
        "enroll": "POST /api/v1/biometrics/face/enroll/ - Enroll face with consent (multipart)",
        "verify": "POST /api/v1/biometrics/face/verify/ - Verify face against enrolled embeddings (multipart)",
        "quality": "POST /api/v1/biometrics/face/quality/ - Assess image quality (multipart)",
        "liveness": "POST /api/v1/biometrics/face/liveness/ - Detect liveness/anti-spoofing (multipart)"
    },
    examples=[
        "curl -X POST https://api.example.com/api/v1/biometrics/face/enroll/ -H 'Authorization: Bearer <token>' -F 'image=@face.jpg' -F 'user_id=123' -F 'consent_given=true'",
        "curl -X POST https://api.example.com/api/v1/biometrics/face/verify/ -H 'Authorization: Bearer <token>' -F 'image=@face.jpg' -F 'user_id=123' -F 'enable_liveness=true'"
    ]
)
@method_decorator(permission_required('face_recognition.add_faceembedding', raise_exception=True), name='dispatch')
class FaceEnrollmentView(APIView):
    """
    Face Enrollment API Endpoint.

    POST /api/v1/biometrics/face/enroll/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Enroll a new face for a user.

        Request Body (multipart/form-data):
            - image: Face image file
            - user_id: User ID
            - consent_given: Boolean (required)
            - is_primary: Boolean (optional, default: True)

        Returns:
            201: Enrollment successful
            400: Invalid request data
            403: Consent not given
            500: Internal error
        """
        serializer = FaceEnrollmentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Verify user exists
            try:
                user = People.objects.get(id=data['user_id'])
            except People.DoesNotExist:
                return Response(
                    {'success': False, 'message': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Log consent
            BiometricConsentLog.objects.create(
                user=user,
                biometric_type='FACE',
                consent_given=data['consent_given'],
                consent_method='API_ENROLLMENT'
            )

            # Save uploaded image temporarily
            image_file = data['image']
            file_name = f'temp/face_enrollment_{uuid.uuid4()}.jpg'
            image_path = default_storage.save(file_name, ContentFile(image_file.read()))
            full_image_path = default_storage.path(image_path)

            # Assess image quality
            quality_service = ImageQualityAssessmentService()
            quality_result = quality_service.assess_image_quality(full_image_path)

            if quality_result.get('overall_quality', 0) < 0.6:
                # Clean up temp file
                default_storage.delete(image_path)

                return Response({
                    'success': False,
                    'message': 'Image quality too low for enrollment',
                    'quality_score': quality_result.get('overall_quality'),
                    'quality_issues': quality_result.get('quality_issues', []),
                    'recommendations': quality_result.get('improvement_suggestions', [])
                }, status=status.HTTP_400_BAD_REQUEST)

            # Extract face embeddings
            ensemble_service = EnsembleVerificationService()
            embeddings_extracted = {}

            for model_name, model in ensemble_service.models.items():
                embedding = model.extract_features(full_image_path)
                if embedding is not None:
                    embeddings_extracted[model_name] = embedding

            if not embeddings_extracted:
                # Clean up temp file
                default_storage.delete(image_path)

                return Response({
                    'success': False,
                    'message': 'Failed to extract face embeddings - no face detected',
                    'quality_metrics': quality_result
                }, status=status.HTTP_400_BAD_REQUEST)

            # Use primary model (FaceNet512) for storage
            primary_embedding = embeddings_extracted.get('FaceNet512')
            if primary_embedding is None:
                primary_embedding = list(embeddings_extracted.values())[0]
                model_name = list(embeddings_extracted.keys())[0]
            else:
                model_name = 'FaceNet512'

            # Create face embedding record
            face_embedding = FaceEmbedding.objects.create(
                user=user,
                embedding_vector=primary_embedding.tolist(),
                model_name=model_name,
                quality_score=quality_result.get('overall_quality', 0),
                confidence_score=0.90,  # Enrollment confidence
                image_hash=quality_result.get('image_hash', ''),
                is_primary=data.get('is_primary', True),
                metadata={
                    'enrollment_source': 'API',
                    'quality_metrics': quality_result,
                    'models_used': list(embeddings_extracted.keys())
                }
            )

            # Clean up temp file
            default_storage.delete(image_path)

            response_data = {
                'success': True,
                'embedding_id': str(face_embedding.id),
                'quality_score': quality_result.get('overall_quality'),
                'confidence_score': 0.90,
                'message': 'Face enrolled successfully'
            }

            response_serializer = FaceEnrollmentResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error during face enrollment: {e}")
            return Response(
                {'success': False, 'message': 'Database error during enrollment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Unexpected error during face enrollment: {e}", exc_info=True)
            # Clean up temp file if it exists
            try:
                if 'image_path' in locals():
                    default_storage.delete(image_path)
            except FILE_EXCEPTIONS:
                pass

            return Response(
                {'success': False, 'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(permission_required('face_recognition.view_faceembedding', raise_exception=True), name='dispatch')
class FaceVerificationView(APIView):
    """
    Face Verification API Endpoint.

    POST /api/v1/biometrics/face/verify/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Verify a face image against enrolled embeddings.

        Request Body (multipart/form-data):
            - image: Face image file
            - user_id: User ID (optional)
            - embedding_id: Embedding ID (optional)
            - enable_liveness: Boolean (optional, default: True)

        Returns:
            200: Verification result
            400: Invalid request data
            404: User or embedding not found
            500: Internal error
        """
        serializer = FaceVerificationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'verified': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Get reference embeddings
            if data.get('embedding_id'):
                try:
                    embeddings = [FaceEmbedding.objects.get(id=data['embedding_id'])]
                except FaceEmbedding.DoesNotExist:
                    return Response(
                        {'verified': False, 'message': 'Embedding not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            elif data.get('user_id'):
                embeddings = FaceEmbedding.objects.filter(
                    user_id=data['user_id'],
                    is_active=True
                )
                if not embeddings.exists():
                    return Response(
                        {'verified': False, 'message': 'No enrolled face found for user'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                return Response(
                    {'verified': False, 'message': 'user_id or embedding_id required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Save uploaded image temporarily
            image_file = data['image']
            file_name = f'temp/face_verify_{uuid.uuid4()}.jpg'
            image_path = default_storage.save(file_name, ContentFile(image_file.read()))
            full_image_path = default_storage.path(image_path)

            # Assess image quality
            quality_service = ImageQualityAssessmentService()
            quality_result = quality_service.assess_image_quality(full_image_path)

            # Extract test embedding
            ensemble_service = EnsembleVerificationService()
            test_embedding = None

            for model_name, model in ensemble_service.models.items():
                embedding = model.extract_features(full_image_path)
                if embedding is not None:
                    test_embedding = embedding
                    break

            if test_embedding is None:
                default_storage.delete(image_path)
                return Response({
                    'verified': False,
                    'message': 'Failed to extract face features - no face detected',
                    'quality_metrics': quality_result
                }, status=status.HTTP_400_BAD_REQUEST)

            # Calculate similarities with all reference embeddings
            max_similarity = 0.0
            for embedding_obj in embeddings:
                ref_embedding = np.array(embedding_obj.embedding_vector)
                similarity = ensemble_service.calculate_cosine_similarity(test_embedding, ref_embedding)
                max_similarity = max(max_similarity, similarity)

            # Anti-spoofing check if enabled
            anti_spoofing_result = {}
            if data.get('enable_liveness', True):
                import asyncio
                liveness_service = LivenessDetectionService()
                liveness_result = asyncio.run(
                    liveness_service.detect_3d_liveness(full_image_path)
                )
                anti_spoofing_result = liveness_result

            # Calculate fraud risk
            fraud_risk_score = 0.0
            if not anti_spoofing_result.get('3d_liveness_detected', True):
                fraud_risk_score += 0.5
            if quality_result.get('overall_quality', 1.0) < 0.5:
                fraud_risk_score += 0.2

            # Make decision
            threshold_met = max_similarity >= 0.70
            confidence = (max_similarity + quality_result.get('overall_quality', 0)) / 2.0
            verified = threshold_met and confidence >= 0.75 and fraud_risk_score < 0.6

            # Clean up temp file
            default_storage.delete(image_path)

            response_data = {
                'verified': verified,
                'confidence': float(confidence),
                'similarity': float(max_similarity),
                'match_score': float(max_similarity),
                'threshold_met': threshold_met,
                'fraud_risk_score': float(fraud_risk_score),
                'quality_metrics': quality_result,
                'anti_spoofing_result': anti_spoofing_result if anti_spoofing_result else None,
                'message': 'Verification complete'
            }

            response_serializer = FaceVerificationResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Unexpected error during face verification: {e}", exc_info=True)
            # Clean up temp file
            try:
                if 'image_path' in locals():
                    default_storage.delete(image_path)
            except FILE_EXCEPTIONS:
                pass

            return Response(
                {'verified': False, 'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(permission_required('face_recognition.view_faceembedding', raise_exception=True), name='dispatch')
class FaceQualityView(APIView):
    """
    Face Image Quality Assessment API Endpoint.

    POST /api/v1/biometrics/face/quality/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Assess face image quality.

        Request Body (multipart/form-data):
            - image: Face image file

        Returns:
            200: Quality assessment result
            400: Invalid request data
        """
        serializer = FaceQualityAssessmentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Save image temporarily
            image_file = data['image']
            file_name = f'temp/face_quality_{uuid.uuid4()}.jpg'
            image_path = default_storage.save(file_name, ContentFile(image_file.read()))
            full_image_path = default_storage.path(image_path)

            # Assess quality
            quality_service = ImageQualityAssessmentService()
            quality_result = quality_service.assess_image_quality(full_image_path)

            # Add acceptability check
            quality_result['acceptable'] = quality_result.get('overall_quality', 0) >= 0.6
            quality_result['improvement_suggestions'] = quality_service.generate_improvement_suggestions(
                quality_result.get('quality_issues', [])
            )

            # Clean up temp file
            default_storage.delete(image_path)

            response_serializer = FaceQualityAssessmentResponseSerializer(quality_result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error assessing face image quality: {e}", exc_info=True)
            # Clean up temp file
            try:
                if 'image_path' in locals():
                    default_storage.delete(image_path)
            except FILE_EXCEPTIONS:
                pass

            return Response(
                {'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(permission_required('face_recognition.view_faceembedding', raise_exception=True), name='dispatch')
class FaceLivenessView(APIView):
    """
    Face Liveness Detection API Endpoint.

    POST /api/v1/biometrics/face/liveness/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Detect liveness in face image.

        Request Body (multipart/form-data):
            - image: Face image file
            - detection_type: 'passive', '3d_depth', or 'challenge_response'

        Returns:
            200: Liveness detection result
            400: Invalid request data
        """
        serializer = LivenessDetectionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Save image temporarily
            image_file = data['image']
            file_name = f'temp/face_liveness_{uuid.uuid4()}.jpg'
            image_path = default_storage.save(file_name, ContentFile(image_file.read()))
            full_image_path = default_storage.path(image_path)

            # Perform liveness detection
            liveness_service = LivenessDetectionService()
            detection_type = data.get('detection_type', 'passive')

            if detection_type == '3d_depth':
                import asyncio
                liveness_result = asyncio.run(
                    liveness_service.detect_3d_liveness(full_image_path)
                )
            else:
                # Passive liveness (default)
                import asyncio
                liveness_result = asyncio.run(
                    liveness_service.advanced_liveness_analysis(full_image_path)
                )

            # Add detection type to result
            liveness_result['detection_type'] = detection_type
            liveness_result['message'] = 'Liveness detection complete'

            # Clean up temp file
            default_storage.delete(image_path)

            response_serializer = LivenessDetectionResponseSerializer(liveness_result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error in liveness detection: {e}", exc_info=True)
            # Clean up temp file
            try:
                if 'image_path' in locals():
                    default_storage.delete(image_path)
            except FILE_EXCEPTIONS:
                pass

            return Response(
                {'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
