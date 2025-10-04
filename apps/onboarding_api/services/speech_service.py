"""
Speech-to-Text Service for Conversational Onboarding

This service provides voice input capabilities for the conversational onboarding module.
It reuses the existing Google Cloud Speech infrastructure from SpeechToTextService.

Features:
- Voice-to-text transcription for user input
- Multi-language support (10+ languages including major Indian languages)
- Automatic audio format conversion
- Quality metrics and confidence scoring
- Temporary file management and cleanup

Following .claude/rules.md:
- Rule #7: Service classes < 150 lines per method
- Rule #9: Specific exception handling (no bare except)
- Rule #12: Query optimization where applicable
"""

import os
import tempfile
import logging
import time
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.core.services.speech_to_text_service import SpeechToTextService
from apps.onboarding_api.services.pii_integration import get_pii_service

logger = logging.getLogger(__name__)


class OnboardingSpeechService:
    """
    Voice input/output service for conversational onboarding sessions.

    Provides voice transcription by reusing the existing SpeechToTextService
    infrastructure that's already configured for Google Cloud Speech API.
    """

    # Supported languages (matching SpeechToTextService)
    SUPPORTED_LANGUAGES = {
        'en': 'en-US',
        'hi': 'hi-IN',
        'mr': 'mr-IN',
        'ta': 'ta-IN',
        'te': 'te-IN',
        'kn': 'kn-IN',
        'gu': 'gu-IN',
        'bn': 'bn-IN',
        'ml': 'ml-IN',
        'or': 'or-IN'
    }

    def __init__(self):
        """Initialize service with existing speech-to-text infrastructure."""
        self.speech_service = SpeechToTextService()
        self.pii_service = get_pii_service()  # PII redaction for transcripts (Rule #15 compliance)

    def transcribe_voice_input(
        self,
        audio_file,
        language_code: str = 'en-US',
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe user voice input for onboarding conversation.

        Args:
            audio_file: Django UploadedFile object with audio data
            language_code: BCP-47 language code (e.g., 'en-US', 'hi-IN')
            session_id: Optional session ID for tracking and logging

        Returns:
            {
                'success': bool,
                'transcript': str | None,
                'confidence': float,
                'language': str,
                'duration_seconds': float,
                'processing_time_ms': int,
                'error': str | None
            }
        """
        result = {
            'success': False,
            'transcript': None,
            'confidence': 0.0,
            'language': language_code,
            'duration_seconds': 0.0,
            'processing_time_ms': 0,
            'error': None
        }

        temp_path = None
        wav_path = None

        try:
            # Save uploaded audio to temporary file
            temp_path = self._save_temp_audio(audio_file, session_id)
            logger.info(
                f"Saved audio to temp file for session {session_id}: {temp_path}",
                extra={'session_id': session_id, 'language': language_code}
            )

            # Convert to WAV format if needed (reuse existing service)
            wav_path = self.speech_service._convert_to_wav(temp_path)
            if not wav_path:
                result['error'] = "Audio format conversion failed"
                logger.error(f"WAV conversion failed for {temp_path}")
                return result

            # Get audio duration for metrics
            duration = self.speech_service._get_audio_duration(wav_path)
            result['duration_seconds'] = duration

            # Validate duration (onboarding voice snippets should be < 60 seconds)
            max_duration = getattr(settings, 'ONBOARDING_VOICE_MAX_DURATION_SECONDS', 60)
            if duration > max_duration:
                result['error'] = f"Audio duration {duration:.1f}s exceeds limit of {max_duration}s"
                logger.warning(result['error'], extra={'session_id': session_id})
                return result

            # Transcribe audio
            start_time = time.time()
            logger.info(
                f"Starting transcription for session {session_id}, duration={duration:.1f}s",
                extra={'session_id': session_id, 'duration': duration}
            )

            transcript = self.speech_service._transcribe_short_audio(
                wav_path,
                language_code
            )

            processing_time = int((time.time() - start_time) * 1000)
            result['processing_time_ms'] = processing_time

            if transcript:
                # CRITICAL: Apply PII redaction before storing/logging (Rule #15 compliance)
                pii_result = self.pii_service.sanitize_voice_transcript(
                    transcript=transcript,
                    session_id=session_id or 'unknown',
                    additional_context={
                        'language': language_code,
                        'duration_seconds': duration,
                        'processing_time_ms': processing_time
                    }
                )

                # Use sanitized transcript for LLM and storage
                sanitized_transcript = pii_result['sanitized_transcript']

                result['success'] = True
                result['transcript'] = sanitized_transcript
                result['confidence'] = 0.90  # TODO: Extract actual confidence from API response
                result['pii_redacted'] = pii_result['redaction_metadata']['redactions_count'] > 0
                result['safe_for_llm'] = pii_result['safe_for_llm']

                logger.info(
                    f"Voice transcription successful (PII-sanitized): {len(sanitized_transcript)} chars, {processing_time}ms",
                    extra={
                        'session_id': session_id,
                        'transcript_length': len(sanitized_transcript),
                        'processing_time_ms': processing_time,
                        'pii_redactions': pii_result['redaction_metadata']['redactions_count'],
                        'safe_for_llm': pii_result['safe_for_llm']
                    }
                )
            else:
                result['error'] = "No transcription returned from speech service"
                logger.warning(
                    f"Voice transcription returned empty result for session {session_id}",
                    extra={'session_id': session_id}
                )

        except ValidationError as e:
            logger.error(f"Validation error during transcription: {str(e)}", exc_info=True)
            result['error'] = f"Validation error: {str(e)}"
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"File operation error during transcription: {str(e)}", exc_info=True)
            result['error'] = f"File error: {str(e)}"
        except (ValueError, TypeError) as e:
            logger.error(f"Data error during transcription: {str(e)}", exc_info=True)
            result['error'] = f"Data error: {str(e)}"
        except Exception as e:
            # Catch-all for unexpected errors (but log specifically)
            logger.error(
                f"Unexpected error during voice transcription: {str(e)}",
                exc_info=True,
                extra={'session_id': session_id}
            )
            result['error'] = f"Transcription failed: {str(e)}"
        finally:
            # Always cleanup temporary files
            self._cleanup_temp_files([temp_path, wav_path])

        return result

    def _save_temp_audio(self, audio_file, session_id: Optional[str] = None) -> str:
        """
        Save uploaded audio file to temporary location.

        Args:
            audio_file: Django UploadedFile object
            session_id: Optional session ID for filename prefix

        Returns:
            Path to saved temporary file

        Raises:
            OSError: If file save fails
            ValidationError: If audio file is invalid
        """
        # Validate audio file exists and has content
        if not audio_file:
            raise ValidationError("No audio file provided")

        if audio_file.size == 0:
            raise ValidationError("Audio file is empty")

        # Check file size limit
        max_size_mb = getattr(settings, 'ONBOARDING_VOICE_MAX_FILE_SIZE_MB', 10)
        max_size_bytes = max_size_mb * 1024 * 1024
        if audio_file.size > max_size_bytes:
            raise ValidationError(
                f"Audio file size {audio_file.size} bytes exceeds limit of {max_size_bytes} bytes"
            )

        # Determine file suffix from filename
        suffix = os.path.splitext(audio_file.name)[1] if audio_file.name else '.webm'
        prefix = f"onboarding_{session_id}_" if session_id else "onboarding_voice_"

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            prefix=prefix,
            delete=False,
            mode='wb'
        ) as tmp:
            # Write audio data in chunks
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            return tmp.name

    def _cleanup_temp_files(self, file_paths: list):
        """
        Clean up temporary audio files.

        Args:
            file_paths: List of file paths to delete
        """
        for path in file_paths:
            if not path:
                continue

            try:
                if os.path.exists(path):
                    os.unlink(path)
                    logger.debug(f"Cleaned up temp file: {path}")
            except OSError as e:
                # Log warning but don't raise - cleanup failures shouldn't break flow
                logger.warning(f"Failed to cleanup temp file {path}: {e}")

    def is_language_supported(self, language_code: str) -> bool:
        """
        Check if language is supported for voice input.

        Args:
            language_code: BCP-47 language code (e.g., 'en-US' or 'en')

        Returns:
            True if language is supported, False otherwise
        """
        # Extract language prefix (e.g., 'en' from 'en-US')
        lang_short = language_code.split('-')[0].lower()
        return lang_short in self.SUPPORTED_LANGUAGES

    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get dictionary of supported languages.

        Returns:
            Dict mapping language codes to full language identifiers
        """
        return self.SUPPORTED_LANGUAGES.copy()

    def is_service_available(self) -> bool:
        """
        Check if the speech-to-text service is available.

        Returns:
            True if service is configured and available
        """
        return self.speech_service.is_service_available()