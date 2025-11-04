"""
Voice Input Views

Handles voice input processing for conversational onboarding.

Migrated from: apps/onboarding_api/views.py (lines 2191-2400)
Date: 2025-09-30
"""
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core_onboarding.models import ConversationSession
from ..services.llm import get_llm_service
from ..utils.security import require_tenant_scope
import logging

logger = logging.getLogger(__name__)


class ConversationVoiceInputView(APIView):
    """Accept voice input for conversational onboarding"""
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('update_conversation')
    def post(self, request, conversation_id):
        """Handle voice input submission"""
        if not self._check_feature_enabled():
            return Response(
                {"error": "Conversational onboarding is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        if not self._check_voice_enabled():
            return Response(
                {"error": "Voice input is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        session = get_object_or_404(
            ConversationSession,
            session_id=conversation_id,
            user=request.user
        )

        audio_file = request.FILES.get('audio')
        if not audio_file:
            return Response(
                {"error": "Missing audio file"},
                status=status.HTTP_400_BAD_REQUEST
            )

        language = request.data.get(
            'language',
            session.preferred_voice_language or 'en-US'
        )

        return self._process_voice_input(
            session, audio_file, language, request
        )

    def _check_feature_enabled(self):
        """Check if feature is enabled"""
        return settings.ENABLE_CONVERSATIONAL_ONBOARDING

    def _check_voice_enabled(self):
        """Check if voice input is enabled"""
        return getattr(settings, 'ENABLE_ONBOARDING_VOICE_INPUT', True)

    def _process_voice_input(self, session, audio_file, language, request):
        """Process voice input"""
        from apps.core_onboarding.services.speech_service import OnboardingSpeechService
        speech_service = OnboardingSpeechService()

        if not speech_service.is_language_supported(language):
            return Response({
                "error": f"Language '{language}' is not supported",
                "supported_languages": speech_service.get_supported_languages()
            }, status=status.HTTP_400_BAD_REQUEST)

        logger.info(
            f"Processing voice input for session {session.session_id}",
            extra={'session_id': str(session.session_id), 'language': language}
        )

        transcription_result = speech_service.transcribe_voice_input(
            audio_file=audio_file,
            language_code=language,
            session_id=str(session.session_id)
        )

        if not transcription_result['success']:
            logger.error(
                f"Voice transcription failed: {transcription_result['error']}",
                extra={'session_id': str(session.session_id)}
            )
            return Response({
                "error": "Voice transcription failed",
                "details": transcription_result['error'],
                "fallback": "Please use text input instead"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Update session metadata
        self._update_session_metadata(session, language, transcription_result)

        # Process through LLM
        try:
            llm_service = get_llm_service()
            response = llm_service.process_voice_input(
                transcript=transcription_result['transcript'],
                session=session,
                context=session.context_data
            )

            return Response({
                "conversation_id": str(session.session_id),
                "transcription": {
                    "text": transcription_result['transcript'],
                    "confidence": transcription_result['confidence'],
                    "language": language,
                    "duration_seconds": transcription_result['duration_seconds'],
                    "processing_time_ms": transcription_result['processing_time_ms']
                },
                "response": response.get('response_text', ''),
                "next_questions": response.get('questions', []),
                "state": session.current_state,
                "voice_interaction_count": session.voice_interaction_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error processing voice input through LLM: {str(e)}",
                exc_info=True,
                extra={'session_id': str(session.session_id)}
            )
            return Response(
                {"error": "Failed to process voice input"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _update_session_metadata(self, session, language, transcription_result):
        """Update session with voice interaction metadata"""
        session.voice_enabled = True
        session.preferred_voice_language = language
        session.voice_interaction_count += 1
        session.total_audio_duration_seconds += int(transcription_result['duration_seconds'])

        session.audio_transcripts.append({
            'timestamp': timezone.now().isoformat(),
            'transcript': transcription_result['transcript'],
            'confidence': transcription_result['confidence'],
            'duration_seconds': transcription_result['duration_seconds'],
            'language': language,
            'processing_time_ms': transcription_result['processing_time_ms']
        })
        session.save()


class VoiceCapabilityView(APIView):
    """Check voice input capability and configuration"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return voice capability information"""
        from apps.core_onboarding.services.speech_service import OnboardingSpeechService

        speech_service = OnboardingSpeechService()

        return Response({
            "voice_enabled": getattr(settings, 'ENABLE_ONBOARDING_VOICE_INPUT', True),
            "service_available": speech_service.is_service_available(),
            "supported_languages": speech_service.get_supported_languages(),
            "configuration": {
                "max_audio_duration_seconds": getattr(
                    settings, 'ONBOARDING_VOICE_MAX_DURATION_SECONDS', 60
                ),
                "max_file_size_mb": getattr(
                    settings, 'ONBOARDING_VOICE_MAX_FILE_SIZE_MB', 10
                ),
                "default_language": getattr(
                    settings, 'ONBOARDING_VOICE_DEFAULT_LANGUAGE', 'en-US'
                ),
                "min_confidence_threshold": getattr(
                    settings, 'ONBOARDING_VOICE_MIN_CONFIDENCE', 0.6
                )
            },
            "supported_formats": [
                "audio/webm", "audio/wav", "audio/mp3",
                "audio/ogg", "audio/m4a", "audio/aac", "audio/flac"
            ],
            "features": {
                "real_time_transcription": False,
                "speaker_identification": False,
                "noise_cancellation": True,
                "multi_language_detection": False,
                "auto_language_detection": False
            }
        }, status=status.HTTP_200_OK)
