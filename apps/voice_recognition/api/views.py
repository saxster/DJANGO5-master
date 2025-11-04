"""
Voice Recognition REST API Views (Sprint 2.5)

REST API endpoints for biometric voice recognition:
- POST /api/v1/biometrics/voice/enroll/ - Voice enrollment
- POST /api/v1/biometrics/voice/verify/ - Voice verification
- POST /api/v1/biometrics/voice/challenge/ - Generate challenge
- POST /api/v1/biometrics/voice/quality/ - Quality assessment

All endpoints require authentication and return OpenAPI-compliant responses.

Author: Development Team
Date: October 2025
"""

import logging
import uuid
import numpy as np
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import DatabaseError, IntegrityError
from django.utils import timezone
from datetime import timedelta
from apps.core.exceptions.patterns import FILE_EXCEPTIONS

from apps.voice_recognition.models import VoiceEmbedding
from apps.face_recognition.models import BiometricConsentLog  # Shared consent model
from apps.voice_recognition.services import ResemblyzerVoiceService
from apps.peoples.models import People
from .serializers import (
    VoiceEnrollmentSerializer,
    VoiceEnrollmentResponseSerializer,
    VoiceVerificationSerializer,
    VoiceVerificationResponseSerializer,
    VoiceChallengeRequestSerializer,
    VoiceChallengeResponseSerializer,
    AudioQualityAssessmentSerializer,
    AudioQualityAssessmentResponseSerializer
)

logger = logging.getLogger(__name__)


class VoiceEnrollmentView(APIView):
    """
    Voice Enrollment API Endpoint.

    POST /api/v1/biometrics/voice/enroll/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Enroll a new voiceprint for a user.

        Request Body (multipart/form-data):
            - audio: Audio file (WAV, MP3, M4A)
            - user_id: User ID
            - consent_given: Boolean (required)
            - is_primary: Boolean (optional, default: True)

        Returns:
            201: Enrollment successful
            400: Invalid request data
            403: Consent not given
            404: User not found
            500: Internal error
        """
        serializer = VoiceEnrollmentSerializer(data=request.data)

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
                biometric_type='VOICE',
                consent_given=data['consent_given'],
                consent_method='API_ENROLLMENT'
            )

            # Save uploaded audio temporarily
            audio_file = data['audio']
            file_name = f'temp/voice_enrollment_{uuid.uuid4()}.wav'
            audio_path = default_storage.save(file_name, ContentFile(audio_file.read()))
            full_audio_path = default_storage.path(audio_path)

            # Assess audio quality
            voice_service = ResemblyzerVoiceService()
            quality_result = voice_service.assess_audio_quality(full_audio_path)

            if not quality_result.get('acceptable', False):
                # Clean up temp file
                default_storage.delete(audio_path)

                return Response({
                    'success': False,
                    'message': 'Audio quality too low for enrollment',
                    'audio_quality': quality_result,
                    'quality_issues': quality_result.get('quality_issues', []),
                    'recommendations': quality_result.get('recommendations', [])
                }, status=status.HTTP_400_BAD_REQUEST)

            # Extract voice embedding
            voice_embedding = voice_service.extract_voice_embedding(full_audio_path)

            if voice_embedding is None:
                # Clean up temp file
                default_storage.delete(audio_path)

                return Response({
                    'success': False,
                    'message': 'Failed to extract voice embedding',
                    'audio_quality': quality_result
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create voice embedding record
            voiceprint = VoiceEmbedding.objects.create(
                user=user,
                embedding_vector=voice_embedding.tolist(),
                model_name='Resemblyzer',
                quality_score=quality_result.get('overall_quality', 0),
                confidence_score=0.90,  # Enrollment confidence
                is_primary=data.get('is_primary', True),
                metadata={
                    'enrollment_source': 'API',
                    'audio_quality': quality_result,
                    'snr_db': quality_result.get('snr_db'),
                    'duration_seconds': quality_result.get('duration_seconds')
                }
            )

            # Clean up temp file
            default_storage.delete(audio_path)

            response_data = {
                'success': True,
                'voiceprint_id': str(voiceprint.id),
                'quality_score': quality_result.get('overall_quality'),
                'confidence_score': 0.90,
                'message': 'Voice enrolled successfully',
                'audio_quality': quality_result
            }

            response_serializer = VoiceEnrollmentResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error during voice enrollment: {e}")
            return Response(
                {'success': False, 'message': 'Database error during enrollment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except Exception as e:
            logger.error(f"Unexpected error during voice enrollment: {e}")
            # Clean up temp file
            try:
                if 'audio_path' in locals():
                    default_storage.delete(audio_path)
            except FILE_EXCEPTIONS:
                pass

            return Response(
                {'success': False, 'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VoiceVerificationView(APIView):
    """
    Voice Verification API Endpoint.

    POST /api/v1/biometrics/voice/verify/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Verify a voice sample against enrolled voiceprints.

        Request Body (multipart/form-data):
            - audio: Audio file to verify
            - user_id: User ID (optional)
            - voiceprint_id: Voiceprint ID (optional)
            - enable_anti_spoofing: Boolean (optional, default: True)

        Returns:
            200: Verification result
            400: Invalid request data
            404: User or voiceprint not found
            500: Internal error
        """
        serializer = VoiceVerificationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'verified': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Get reference voiceprints
            if data.get('voiceprint_id'):
                try:
                    voiceprints = [VoiceEmbedding.objects.get(id=data['voiceprint_id'])]
                except VoiceEmbedding.DoesNotExist:
                    return Response(
                        {'verified': False, 'message': 'Voiceprint not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            elif data.get('user_id'):
                voiceprints = VoiceEmbedding.objects.filter(
                    user_id=data['user_id'],
                    is_active=True
                )
                if not voiceprints.exists():
                    return Response(
                        {'verified': False, 'message': 'No enrolled voice found for user'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                return Response(
                    {'verified': False, 'message': 'user_id or voiceprint_id required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Save uploaded audio temporarily
            audio_file = data['audio']
            file_name = f'temp/voice_verify_{uuid.uuid4()}.wav'
            audio_path = default_storage.save(file_name, ContentFile(audio_file.read()))
            full_audio_path = default_storage.path(audio_path)

            # Initialize voice service
            voice_service = ResemblyzerVoiceService()

            # Extract reference embeddings
            reference_embeddings = [
                np.array(vp.embedding_vector) for vp in voiceprints
            ]

            # Verify voice
            verification_result = voice_service.verify_voice(
                test_audio_path=full_audio_path,
                reference_embeddings=reference_embeddings
            )

            # Assess audio quality
            quality_result = voice_service.assess_audio_quality(full_audio_path)

            # Calculate fraud risk (simplified)
            fraud_risk_score = 0.0
            if not quality_result.get('acceptable', True):
                fraud_risk_score += 0.3
            if verification_result.get('confidence', 0) < 0.6:
                fraud_risk_score += 0.3

            # Clean up temp file
            default_storage.delete(audio_path)

            response_data = {
                'verified': verification_result.get('verified', False),
                'confidence': verification_result.get('confidence', 0.0),
                'similarity': verification_result.get('similarity', 0.0),
                'match_score': verification_result.get('similarity', 0.0),
                'threshold_met': verification_result.get('threshold_met', False),
                'fraud_risk_score': fraud_risk_score,
                'quality_metrics': quality_result,
                'message': 'Voice verification complete'
            }

            response_serializer = VoiceVerificationResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error during voice verification: {e}")
            # Clean up temp file
            try:
                if 'audio_path' in locals():
                    default_storage.delete(audio_path)
            except FILE_EXCEPTIONS:
                pass

            return Response(
                {'verified': False, 'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VoiceQualityView(APIView):
    """
    Voice/Audio Quality Assessment API Endpoint.

    POST /api/v1/biometrics/voice/quality/
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Assess audio quality for voice verification.

        Request Body (multipart/form-data):
            - audio: Audio file

        Returns:
            200: Quality assessment result
            400: Invalid request data
        """
        serializer = AudioQualityAssessmentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Save audio temporarily
            audio_file = data['audio']
            file_name = f'temp/voice_quality_{uuid.uuid4()}.wav'
            audio_path = default_storage.save(file_name, ContentFile(audio_file.read()))
            full_audio_path = default_storage.path(audio_path)

            # Assess quality
            voice_service = ResemblyzerVoiceService()
            quality_result = voice_service.assess_audio_quality(full_audio_path)

            # Clean up temp file
            default_storage.delete(audio_path)

            response_serializer = AudioQualityAssessmentResponseSerializer(quality_result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error assessing audio quality: {e}")
            # Clean up temp file
            try:
                if 'audio_path' in locals():
                    default_storage.delete(audio_path)
            except FILE_EXCEPTIONS:
                pass

            return Response(
                {'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VoiceChallengeView(APIView):
    """
    Voice Challenge Generation API Endpoint.

    POST /api/v1/biometrics/voice/challenge/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Generate a voice challenge for liveness detection.

        Request Body (JSON):
            - user_id: User ID
            - challenge_type: 'phrase', 'digits', or 'words' (optional)

        Returns:
            200: Challenge generated
            400: Invalid request data
            404: User not found
        """
        serializer = VoiceChallengeRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            # Verify user exists
            try:
                user = People.objects.get(id=data['user_id'])
            except People.DoesNotExist:
                return Response(
                    {'message': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Generate challenge
            import random
            challenge_type = data.get('challenge_type', 'phrase')

            if challenge_type == 'phrase':
                phrases = [
                    "The quick brown fox jumps over the lazy dog",
                    "Security is our top priority",
                    "Please speak this phrase clearly",
                    "Voice verification in progress"
                ]
                challenge_text = random.choice(phrases)
            elif challenge_type == 'digits':
                digits = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                challenge_text = ' '.join(digits)
            else:  # words
                words = random.sample([
                    'alpha', 'bravo', 'charlie', 'delta', 'echo',
                    'foxtrot', 'golf', 'hotel', 'india', 'juliet'
                ], k=4)
                challenge_text = ' '.join(words)

            challenge_id = uuid.uuid4()
            expires_at = timezone.now() + timedelta(minutes=5)

            response_data = {
                'challenge_id': challenge_id,
                'challenge_text': challenge_text,
                'challenge_type': challenge_type,
                'expires_at': expires_at,
                'timeout_seconds': 300  # 5 minutes
            }

            response_serializer = VoiceChallengeResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error generating voice challenge: {e}")
            return Response(
                {'message': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
