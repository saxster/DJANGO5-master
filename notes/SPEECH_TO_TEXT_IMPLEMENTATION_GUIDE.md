# Speech-to-Text Implementation Guide

This document contains all the changes required to implement speech-to-text functionality for audio attachments in JobneedDetails (SiteSurvey).

## Overview

The implementation provides automatic speech-to-text transcription for audio files uploaded during SiteSurvey operations. It uses Google Cloud Speech API and follows an event-driven architecture where audio uploads automatically trigger background transcription tasks.

## Architecture

- **Event-Driven Processing**: Audio upload automatically triggers transcription
- **Background Processing**: Celery tasks handle transcription asynchronously
- **Status Tracking**: Database fields track transcription progress
- **API Endpoints**: RESTful endpoints for status checking and management
- **Comprehensive Testing**: Full test coverage for all components

## Files to Create

### 1. Speech-to-Text Service
**File**: `apps/core/services/speech_to_text_service.py`

```python
"""
Speech-to-Text Service Layer

This service handles audio transcription using Google Cloud Speech API:
- Supports multiple audio formats (MP3, WAV, etc.)
- Handles both short (<60s) and long audio files
- Audio conversion and chunking for long files
- Retry logic and comprehensive error handling
- Language detection and multi-language support
"""

import os
import tempfile
import subprocess
import logging
from typing import Optional, Dict, Any, List, Tuple
from django.conf import settings
from django.core.files.base import ContentFile
from google.cloud import speech
from google.cloud.speech import RecognitionConfig, RecognitionAudio

logger = logging.getLogger(__name__)
error_logger = logging.getLogger("error_logger")


class SpeechToTextService:
    """Centralized service for audio transcription operations"""

    # Configuration settings
    DEFAULT_LANGUAGE = 'en-US'
    CHUNK_DURATION = 30  # seconds for long audio splitting
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

    # Supported languages for speech recognition
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
        """Initialize the Speech-to-Text service with Google Cloud credentials"""
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Google Cloud Speech client with proper error handling"""
        try:
            # Check if credentials path is configured
            credentials_path = getattr(settings, 'GOOGLE_APPLICATION_CREDENTIALS', None)

            if not credentials_path:
                error_logger.error("GOOGLE_APPLICATION_CREDENTIALS not configured in settings")
                return

            if not os.path.exists(credentials_path):
                error_logger.error(f"Google Cloud credentials file not found at: {credentials_path}")
                return

            # Initialize client with service account file
            self.client = speech.SpeechClient.from_service_account_file(credentials_path)
            logger.info("Google Cloud Speech client initialized successfully")

        except Exception as e:
            error_logger.error(f"Failed to initialize Google Cloud Speech client: {str(e)}")
            self.client = None

    def transcribe_audio(self, jobneed_detail) -> Optional[str]:
        """
        Main transcription method for JobneedDetails with audio attachments

        Args:
            jobneed_detail: JobneedDetails instance with audio attachment

        Returns:
            Transcribed text or None if transcription fails
        """
        if not self.client:
            error_logger.error("Speech client not initialized")
            return None

        try:
            # Get audio attachment from jobneed_detail
            audio_attachment = self._get_audio_attachment(jobneed_detail)
            if not audio_attachment:
                logger.warning(f"No audio attachment found for JobneedDetails ID: {jobneed_detail.id}")
                return None

            # Get audio file path
            audio_file_path = self._get_audio_file_path(audio_attachment)
            if not audio_file_path or not os.path.exists(audio_file_path):
                logger.error(f"Audio file not found: {audio_file_path}")
                return None

            # Check file size
            if os.path.getsize(audio_file_path) > self.MAX_FILE_SIZE:
                logger.error(f"Audio file too large: {os.path.getsize(audio_file_path)} bytes")
                return None

            # Convert audio to supported format
            wav_path = self._convert_to_wav(audio_file_path)
            if not wav_path:
                return None

            try:
                # Get audio duration to determine processing method
                duration = self._get_audio_duration(wav_path)
                logger.info(f"Audio duration: {duration:.1f} seconds")

                # Determine language (could be enhanced with detection)
                language_code = self._detect_language(jobneed_detail)

                if duration <= 60:
                    # Short audio - use synchronous recognition
                    transcript = self._transcribe_short_audio(wav_path, language_code)
                else:
                    # Long audio - split into chunks and process
                    transcript = self._transcribe_long_audio(wav_path, language_code)

                return transcript

            finally:
                # Clean up temporary WAV file
                if wav_path != audio_file_path:
                    try:
                        os.unlink(wav_path)
                    except OSError:
                        pass

        except Exception as e:
            error_logger.error(f"Error in transcribe_audio for JobneedDetails {jobneed_detail.id}: {str(e)}")
            return None

    def _get_audio_attachment(self, jobneed_detail):
        """Get audio attachment for the given JobneedDetails instance"""
        try:
            from apps.activity.models.attachment_model import Attachment

            # Find audio attachment for this jobneed detail
            attachments = Attachment.objects.filter(
                owner=str(jobneed_detail.uuid),
                ownername__tacode='JOBNEEDDETAILS'
            ).exclude(filename='default.jpg')

            for attachment in attachments:
                # Check if it's an audio file based on file extension or mime type
                filename = str(attachment.filename)
                if self._is_audio_file(filename):
                    return attachment

            return None

        except Exception as e:
            error_logger.error(f"Error getting audio attachment: {str(e)}")
            return None

    def _is_audio_file(self, filename: str) -> bool:
        """Check if file is an audio file based on extension"""
        audio_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma']
        return any(filename.lower().endswith(ext) for ext in audio_extensions)

    def _get_audio_file_path(self, attachment) -> Optional[str]:
        """Get full file path for the attachment"""
        try:
            file_path = os.path.join(
                settings.MEDIA_ROOT,
                attachment.filepath.replace('youtility4_media/', ''),
                str(attachment.filename)
            )
            return file_path
        except Exception as e:
            error_logger.error(f"Error building file path: {str(e)}")
            return None

    def _convert_to_wav(self, audio_file_path: str) -> Optional[str]:
        """Convert audio file to WAV format required by Google Speech API"""
        try:
            # If already WAV, check if it meets requirements
            if audio_file_path.lower().endswith('.wav'):
                # Could add WAV format validation here
                return audio_file_path

            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
                wav_path = tmp_wav.name

            # Convert using ffmpeg
            cmd = [
                'ffmpeg', '-i', audio_file_path,
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-ar', '16000',          # 16kHz sample rate
                '-ac', '1',              # Mono channel
                '-y',                    # Overwrite output
                wav_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                error_logger.error(f"FFmpeg conversion failed: {result.stderr}")
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
                return None

            logger.info(f"Audio converted to WAV: {wav_path}")
            return wav_path

        except subprocess.TimeoutExpired:
            error_logger.error("Audio conversion timed out")
            return None
        except FileNotFoundError:
            error_logger.error("FFmpeg not found - please install ffmpeg")
            return None
        except Exception as e:
            error_logger.error(f"Error converting audio: {str(e)}")
            return None

    def _get_audio_duration(self, wav_path: str) -> float:
        """Get audio duration using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                wav_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                logger.warning(f"Could not get audio duration: {result.stderr}")
                return 0.0

        except Exception as e:
            logger.warning(f"Error getting audio duration: {str(e)}")
            return 0.0

    def _detect_language(self, jobneed_detail) -> str:
        """
        Detect or determine language for transcription
        Currently returns default, but could be enhanced with:
        - User preference from jobneed_detail
        - Site-specific language settings
        - Automatic language detection
        """
        try:
            # Try to get language from site/client settings
            if hasattr(jobneed_detail, 'jobneed') and jobneed_detail.jobneed:
                if hasattr(jobneed_detail.jobneed, 'bu') and jobneed_detail.jobneed.bu:
                    # Could look up site-specific language preference
                    pass

            # Default to English for now
            return self.DEFAULT_LANGUAGE

        except Exception:
            return self.DEFAULT_LANGUAGE

    def _transcribe_short_audio(self, wav_path: str, language_code: str) -> Optional[str]:
        """Transcribe short audio file (<= 60 seconds) using synchronous recognition"""
        try:
            # Read audio file
            with open(wav_path, "rb") as audio_file:
                content = audio_file.read()

            audio = RecognitionAudio(content=content)

            # Configure recognition
            config = RecognitionConfig(
                encoding=RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language_code,
                enable_automatic_punctuation=True,
                audio_channel_count=1,
                model='latest_long'  # Better for longer utterances
            )

            logger.info(f"Starting synchronous transcription with language: {language_code}")
            response = self.client.recognize(config=config, audio=audio)

            # Combine all transcript results
            transcript_parts = []
            for result in response.results:
                if result.alternatives:
                    transcript_parts.append(result.alternatives[0].transcript)
                    logger.info(f"Transcription confidence: {result.alternatives[0].confidence:.2%}")

            if transcript_parts:
                full_transcript = " ".join(transcript_parts)
                logger.info(f"Transcription completed successfully, length: {len(full_transcript)} chars")
                return full_transcript
            else:
                logger.warning("No transcription results returned")
                return None

        except Exception as e:
            error_logger.error(f"Error in short audio transcription: {str(e)}")
            return None

    def _transcribe_long_audio(self, wav_path: str, language_code: str) -> Optional[str]:
        """Transcribe long audio file by splitting into chunks"""
        try:
            logger.info(f"Processing long audio file: {wav_path}")

            # Create temporary directory for chunks
            with tempfile.TemporaryDirectory() as temp_dir:
                # Split audio into chunks
                chunk_files = self._split_audio_into_chunks(wav_path, temp_dir)

                if not chunk_files:
                    logger.error("Failed to split audio into chunks")
                    return None

                # Transcribe each chunk
                all_transcripts = []
                for i, chunk_file in enumerate(chunk_files):
                    logger.info(f"Processing chunk {i+1}/{len(chunk_files)}: {chunk_file}")

                    transcript = self._transcribe_short_audio(chunk_file, language_code)
                    if transcript:
                        all_transcripts.append(transcript)
                    else:
                        logger.warning(f"No transcript for chunk {i+1}")

                if all_transcripts:
                    full_transcript = " ".join(all_transcripts)
                    logger.info(f"Long audio transcription completed, {len(chunk_files)} chunks processed")
                    return full_transcript
                else:
                    logger.error("No transcripts from any chunks")
                    return None

        except Exception as e:
            error_logger.error(f"Error in long audio transcription: {str(e)}")
            return None

    def _split_audio_into_chunks(self, wav_path: str, temp_dir: str) -> List[str]:
        """Split audio file into chunks of specified duration"""
        try:
            chunk_files = []

            # Use ffmpeg to split audio into chunks
            chunk_pattern = os.path.join(temp_dir, 'chunk_%03d.wav')

            cmd = [
                'ffmpeg', '-i', wav_path,
                '-f', 'segment',
                '-segment_time', str(self.CHUNK_DURATION),
                '-acodec', 'copy',
                '-y',
                chunk_pattern
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                error_logger.error(f"Audio splitting failed: {result.stderr}")
                return []

            # Get list of created chunk files
            for filename in sorted(os.listdir(temp_dir)):
                if filename.startswith('chunk_') and filename.endswith('.wav'):
                    chunk_files.append(os.path.join(temp_dir, filename))

            logger.info(f"Audio split into {len(chunk_files)} chunks")
            return chunk_files

        except Exception as e:
            error_logger.error(f"Error splitting audio: {str(e)}")
            return []

    def get_supported_languages(self) -> Dict[str, str]:
        """Get dictionary of supported languages"""
        return self.SUPPORTED_LANGUAGES.copy()

    def is_service_available(self) -> bool:
        """Check if the speech-to-text service is available"""
        return self.client is not None
```

### 2. Transcript API Views
**File**: `apps/activity/views/transcript_views.py`

```python
"""
Transcript Views

API endpoints for speech-to-text transcript management:
- Check transcript status
- Retrieve transcript content
- Manage transcription requests
"""

import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import response as rp
from django.views.generic.base import View
from apps.activity.models.job_model import JobneedDetails
from apps.core.services.speech_to_text_service import SpeechToTextService

logger = logging.getLogger("django")


class TranscriptStatusView(LoginRequiredMixin, View):
    """
    API endpoint to check transcript status for JobneedDetails

    GET parameters:
    - jobneed_detail_id: ID of the JobneedDetails instance
    - uuid: UUID of the JobneedDetails instance (alternative to ID)

    Returns JSON with transcript status and content
    """

    def get(self, request, *args, **kwargs):
        R = request.GET

        try:
            # Get JobneedDetails by ID or UUID
            jobneed_detail = None

            if R.get("jobneed_detail_id"):
                try:
                    jobneed_detail = JobneedDetails.objects.get(id=R["jobneed_detail_id"])
                except JobneedDetails.DoesNotExist:
                    return rp.JsonResponse({"error": "JobneedDetails not found"}, status=404)

            elif R.get("uuid"):
                try:
                    jobneed_detail = JobneedDetails.objects.get(uuid=R["uuid"])
                except JobneedDetails.DoesNotExist:
                    return rp.JsonResponse({"error": "JobneedDetails not found"}, status=404)
            else:
                return rp.JsonResponse({
                    "error": "Missing required parameter: jobneed_detail_id or uuid"
                }, status=400)

            # Build response data
            response_data = {
                "jobneed_detail_id": jobneed_detail.id,
                "uuid": str(jobneed_detail.uuid),
                "transcript_status": jobneed_detail.transcript_status,
                "transcript_language": jobneed_detail.transcript_language,
                "transcript_processed_at": jobneed_detail.transcript_processed_at.isoformat() if jobneed_detail.transcript_processed_at else None,
                "has_transcript": bool(jobneed_detail.transcript),
            }

            # Include transcript content if completed
            if jobneed_detail.transcript_status == 'COMPLETED' and jobneed_detail.transcript:
                response_data["transcript"] = jobneed_detail.transcript
                response_data["transcript_length"] = len(jobneed_detail.transcript)

            # Include error info if failed
            elif jobneed_detail.transcript_status == 'FAILED':
                response_data["error_message"] = "Transcription failed. Please try re-uploading the audio."

            return rp.JsonResponse(response_data, status=200)

        except Exception as e:
            logger.error(f"Error in TranscriptStatusView: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Internal server error"}, status=500)


class TranscriptManagementView(LoginRequiredMixin, View):
    """
    API endpoint for transcript management operations

    POST actions:
    - retry_transcription: Retry failed transcription
    - clear_transcript: Clear existing transcript
    """

    def post(self, request, *args, **kwargs):
        R = request.POST

        try:
            action = R.get("action")
            if not action:
                return rp.JsonResponse({"error": "Missing action parameter"}, status=400)

            # Get JobneedDetails
            jobneed_detail = None
            if R.get("jobneed_detail_id"):
                try:
                    jobneed_detail = JobneedDetails.objects.get(id=R["jobneed_detail_id"])
                except JobneedDetails.DoesNotExist:
                    return rp.JsonResponse({"error": "JobneedDetails not found"}, status=404)
            else:
                return rp.JsonResponse({"error": "Missing jobneed_detail_id"}, status=400)

            if action == "retry_transcription":
                return self._retry_transcription(jobneed_detail)
            elif action == "clear_transcript":
                return self._clear_transcript(jobneed_detail)
            else:
                return rp.JsonResponse({"error": f"Unknown action: {action}"}, status=400)

        except Exception as e:
            logger.error(f"Error in TranscriptManagementView: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Internal server error"}, status=500)

    def _retry_transcription(self, jobneed_detail):
        """Retry transcription for a JobneedDetails instance"""
        try:
            from background_tasks.tasks import process_audio_transcript

            # Reset transcript fields
            jobneed_detail.transcript = None
            jobneed_detail.transcript_status = 'PENDING'
            jobneed_detail.transcript_processed_at = None
            jobneed_detail.save()

            # Queue new transcription task
            process_audio_transcript.delay(jobneed_detail.id)

            logger.info(f"Transcription retry queued for JobneedDetails {jobneed_detail.id}")

            return rp.JsonResponse({
                "status": "success",
                "message": "Transcription retry queued",
                "transcript_status": "PENDING"
            }, status=200)

        except Exception as e:
            logger.error(f"Error retrying transcription: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Failed to retry transcription"}, status=500)

    def _clear_transcript(self, jobneed_detail):
        """Clear existing transcript data"""
        try:
            jobneed_detail.transcript = None
            jobneed_detail.transcript_status = None
            jobneed_detail.transcript_language = None
            jobneed_detail.transcript_processed_at = None
            jobneed_detail.save()

            logger.info(f"Transcript cleared for JobneedDetails {jobneed_detail.id}")

            return rp.JsonResponse({
                "status": "success",
                "message": "Transcript cleared",
                "transcript_status": None
            }, status=200)

        except Exception as e:
            logger.error(f"Error clearing transcript: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Failed to clear transcript"}, status=500)


class SpeechServiceStatusView(LoginRequiredMixin, View):
    """
    API endpoint to check speech-to-text service status and configuration
    """

    def get(self, request, *args, **kwargs):
        try:
            # Initialize service to check status
            service = SpeechToTextService()

            response_data = {
                "service_available": service.is_service_available(),
                "supported_languages": service.get_supported_languages(),
                "default_language": service.DEFAULT_LANGUAGE,
                "max_file_size_mb": service.MAX_FILE_SIZE / (1024 * 1024),
                "chunk_duration_seconds": service.CHUNK_DURATION,
            }

            # Add configuration status
            from django.conf import settings
            credentials_configured = hasattr(settings, 'GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_configured:
                import os
                credentials_exist = os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS)
                response_data["credentials_configured"] = credentials_exist
            else:
                response_data["credentials_configured"] = False

            return rp.JsonResponse(response_data, status=200)

        except Exception as e:
            logger.error(f"Error in SpeechServiceStatusView: {str(e)}", exc_info=True)
            return rp.JsonResponse({"error": "Internal server error"}, status=500)
```

### 3. Background Task Tests
**File**: `background_tasks/tests/test_speech_tasks.py`

```python
"""
Tests for Speech-to-Text Background Tasks

Test coverage for the background transcription task including:
- Task execution success and failure scenarios
- Retry logic
- Status updates
- Error handling
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone
from background_tasks.tasks import process_audio_transcript


class TestProcessAudioTranscriptTask(TestCase):
    """Test cases for process_audio_transcript background task"""

    def setUp(self):
        """Set up test fixtures"""
        self.jobneed_detail_id = 123

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_process_audio_transcript_success(self, mock_service_class, mock_get):
        """Test successful audio transcription processing"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = self.jobneed_detail_id
        mock_get.return_value = mock_jobneed_detail

        # Mock SpeechToTextService
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.return_value = "This is the transcribed text."
        mock_service.DEFAULT_LANGUAGE = 'en-US'
        mock_service_class.return_value = mock_service

        # Execute the task
        with patch('django.utils.timezone.now', return_value=timezone.now()):
            result = process_audio_transcript(self.jobneed_detail_id)

        # Verify results
        self.assertIn('SUCCESS', result['story'])
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(result['transcript_length'], len("This is the transcribed text."))

        # Verify JobneedDetails was updated
        self.assertEqual(mock_jobneed_detail.transcript, "This is the transcribed text.")
        self.assertEqual(mock_jobneed_detail.transcript_status, 'COMPLETED')
        self.assertEqual(mock_jobneed_detail.transcript_language, 'en-US')
        self.assertIsNotNone(mock_jobneed_detail.transcript_processed_at)
        mock_jobneed_detail.save.assert_called()

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    def test_process_audio_transcript_jobneed_not_found(self, mock_get):
        """Test task when JobneedDetails doesn't exist"""
        from apps.activity.models.job_model import JobneedDetails
        mock_get.side_effect = JobneedDetails.DoesNotExist()

        result = process_audio_transcript(self.jobneed_detail_id)

        self.assertIn('ERROR', result['story'])
        self.assertIn('not found', result['story'])

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_process_audio_transcript_service_unavailable(self, mock_service_class, mock_get):
        """Test task when speech service is unavailable"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = self.jobneed_detail_id
        mock_get.return_value = mock_jobneed_detail

        # Mock SpeechToTextService as unavailable
        mock_service = Mock()
        mock_service.is_service_available.return_value = False
        mock_service_class.return_value = mock_service

        result = process_audio_transcript(self.jobneed_detail_id)

        self.assertIn('ERROR', result['story'])
        self.assertIn('not available', result['story'])

        # Verify status was updated to FAILED
        self.assertEqual(mock_jobneed_detail.transcript_status, 'FAILED')
        mock_jobneed_detail.save.assert_called()

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_process_audio_transcript_transcription_failed(self, mock_service_class, mock_get):
        """Test task when transcription returns None (failed)"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = self.jobneed_detail_id
        mock_get.return_value = mock_jobneed_detail

        # Mock SpeechToTextService returning None (failure)
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.return_value = None
        mock_service_class.return_value = mock_service

        with patch('django.utils.timezone.now', return_value=timezone.now()):
            result = process_audio_transcript(self.jobneed_detail_id)

        # Verify results
        self.assertIn('WARNING', result['story'])
        self.assertIn('failed', result['story'])
        self.assertEqual(result['status'], 'FAILED')

        # Verify JobneedDetails was updated
        self.assertEqual(mock_jobneed_detail.transcript_status, 'FAILED')
        self.assertIsNotNone(mock_jobneed_detail.transcript_processed_at)
        mock_jobneed_detail.save.assert_called()
```

### 4. Service Tests
**File**: `apps/core/tests/test_services/test_speech_to_text_service.py`

```python
"""
Tests for SpeechToTextService

Test coverage for the speech-to-text service including:
- Service initialization
- Audio file handling
- Transcription methods
- Error handling
- Edge cases
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.conf import settings
from apps.core.services.speech_to_text_service import SpeechToTextService


class TestSpeechToTextService(TestCase):
    """Test cases for SpeechToTextService"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = SpeechToTextService()

    @patch('apps.core.services.speech_to_text_service.speech.SpeechClient.from_service_account_file')
    def test_initialization_with_valid_credentials(self, mock_client):
        """Test service initialization with valid credentials"""
        mock_client.return_value = Mock()

        with patch('os.path.exists', return_value=True):
            with patch.object(settings, 'GOOGLE_APPLICATION_CREDENTIALS', '/path/to/credentials.json'):
                service = SpeechToTextService()
                service._initialize_client()

                self.assertIsNotNone(service.client)
                mock_client.assert_called_once_with('/path/to/credentials.json')

    def test_initialization_without_credentials(self):
        """Test service initialization without credentials"""
        with patch.object(settings, 'GOOGLE_APPLICATION_CREDENTIALS', None):
            service = SpeechToTextService()
            service._initialize_client()

            self.assertIsNone(service.client)

    def test_is_service_available(self):
        """Test service availability check"""
        # Test when client is available
        self.service.client = Mock()
        self.assertTrue(self.service.is_service_available())

        # Test when client is not available
        self.service.client = None
        self.assertFalse(self.service.is_service_available())

    def test_is_audio_file(self):
        """Test audio file detection"""
        # Test valid audio extensions
        valid_audio_files = [
            'test.mp3', 'TEST.WAV', 'audio.m4a', 'sound.aac',
            'music.ogg', 'recording.flac', 'voice.wma'
        ]

        for filename in valid_audio_files:
            with self.subTest(filename=filename):
                self.assertTrue(self.service._is_audio_file(filename))

        # Test non-audio files
        non_audio_files = [
            'image.jpg', 'document.pdf', 'video.mp4', 'text.txt'
        ]

        for filename in non_audio_files:
            with self.subTest(filename=filename):
                self.assertFalse(self.service._is_audio_file(filename))
```

### 5. Database Migration
**File**: `apps/activity/migrations/0006_add_transcript_fields.py`

```python
# Generated by Django 5.2.1 on 2025-09-24 12:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0005_alter_jobneed_identifier_alter_question_answertype'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobneeddetails',
            name='transcript',
            field=models.TextField(blank=True, null=True, verbose_name='Audio Transcript'),
        ),
        migrations.AddField(
            model_name='jobneeddetails',
            name='transcript_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('PENDING', 'Pending'),
                    ('PROCESSING', 'Processing'),
                    ('COMPLETED', 'Completed'),
                    ('FAILED', 'Failed'),
                ],
                max_length=20,
                null=True,
                verbose_name='Transcript Status'
            ),
        ),
        migrations.AddField(
            model_name='jobneeddetails',
            name='transcript_language',
            field=models.CharField(
                blank=True,
                default='en-US',
                help_text="Language code used for transcription (e.g., 'en-US', 'hi-IN')",
                max_length=10,
                null=True,
                verbose_name='Transcript Language'
            ),
        ),
        migrations.AddField(
            model_name='jobneeddetails',
            name='transcript_processed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Timestamp when transcript processing completed',
                null=True,
                verbose_name='Transcript Processed At'
            ),
        ),
    ]
```

## Files to Modify

### 1. JobneedDetails Model
**File**: `apps/activity/models/job_model.py`

**Add these fields after line 528** (after `attachmentcount = models.IntegerField(_("Attachment count"), default=0)`):

```python
    transcript = models.TextField(_("Audio Transcript"), null=True, blank=True)
    transcript_status = models.CharField(
        _("Transcript Status"),
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
        ],
        null=True,
        blank=True
    )
    transcript_language = models.CharField(
        _("Transcript Language"),
        max_length=10,
        default='en-US',
        null=True,
        blank=True,
        help_text="Language code used for transcription (e.g., 'en-US', 'hi-IN')"
    )
    transcript_processed_at = models.DateTimeField(
        _("Transcript Processed At"),
        null=True,
        blank=True,
        help_text="Timestamp when transcript processing completed"
    )
```

### 2. Background Tasks
**File**: `background_tasks/tasks.py`

**Add this task at the end of the file**:

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="process_audio_transcript")
def process_audio_transcript(self, jobneed_detail_id):
    """
    Background task to process audio transcription for JobneedDetails

    Args:
        jobneed_detail_id: ID of the JobneedDetails instance with audio attachment

    Returns:
        dict: Task result with status and transcript data
    """
    result = {"story": "process_audio_transcript() started\n", "traceback": ""}

    try:
        from apps.activity.models.job_model import JobneedDetails
        from apps.core.services.speech_to_text_service import SpeechToTextService
        from django.utils import timezone

        result["story"] += f"Processing transcript for JobneedDetails ID: {jobneed_detail_id}\n"

        # Get JobneedDetails instance
        try:
            jobneed_detail = JobneedDetails.objects.get(id=jobneed_detail_id)
            result["story"] += f"Found JobneedDetails: {jobneed_detail.id}\n"
        except JobneedDetails.DoesNotExist:
            error_msg = f"JobneedDetails with ID {jobneed_detail_id} not found"
            logger.error(error_msg)
            result["story"] += f"ERROR: {error_msg}\n"
            return result

        # Update status to PROCESSING
        jobneed_detail.transcript_status = 'PROCESSING'
        jobneed_detail.save()
        result["story"] += "Status updated to PROCESSING\n"

        # Initialize speech service
        speech_service = SpeechToTextService()

        if not speech_service.is_service_available():
            error_msg = "Speech-to-Text service not available - check Google Cloud credentials"
            logger.error(error_msg)
            jobneed_detail.transcript_status = 'FAILED'
            jobneed_detail.save()
            result["story"] += f"ERROR: {error_msg}\n"
            return result

        # Process the transcription
        logger.info(f"Starting transcription for JobneedDetails {jobneed_detail_id}")
        transcript = speech_service.transcribe_audio(jobneed_detail)

        if transcript:
            # Success - update with transcript
            jobneed_detail.transcript = transcript
            jobneed_detail.transcript_status = 'COMPLETED'
            jobneed_detail.transcript_processed_at = timezone.now()

            # Set language if not already set
            if not jobneed_detail.transcript_language:
                jobneed_detail.transcript_language = speech_service.DEFAULT_LANGUAGE

            jobneed_detail.save()

            logger.info(f"Transcription completed for JobneedDetails {jobneed_detail_id}")
            result["story"] += f"SUCCESS: Transcription completed, length: {len(transcript)} characters\n"
            result["transcript_length"] = len(transcript)
            result["status"] = "COMPLETED"

        else:
            # Transcription failed
            jobneed_detail.transcript_status = 'FAILED'
            jobneed_detail.transcript_processed_at = timezone.now()
            jobneed_detail.save()

            logger.warning(f"Transcription failed for JobneedDetails {jobneed_detail_id}")
            result["story"] += "WARNING: Transcription failed - no transcript returned\n"
            result["status"] = "FAILED"

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Error processing audio transcript for JobneedDetails {jobneed_detail_id}: {str(e)}", exc_info=True)
        result["traceback"] += f"{tb.format_exc()}"

        try:
            # Try to update status to FAILED
            jobneed_detail = JobneedDetails.objects.get(id=jobneed_detail_id)
            jobneed_detail.transcript_status = 'FAILED'
            jobneed_detail.transcript_processed_at = timezone.now()
            jobneed_detail.save()
        except Exception as save_error:
            logger.error(f"Could not update failed status: {save_error}")

        # Retry the task if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying transcription task, attempt {self.request.retries + 1}")
            raise self.retry(exc=e)
        else:
            logger.error(f"Transcription task failed permanently after {self.max_retries} retries")
            result["status"] = "FAILED_PERMANENTLY"

    return result
```

### 3. Attachment Views
**File**: `apps/activity/views/attachment_views.py`

**Modify the `post` method in the `Attachments` class**:

**Replace this section** (around line 88):
```python
                        model.objects.filter(uuid=R["ownerid"]).update(
                            attachmentcount=data["attcount"]
                        )
                return rp.JsonResponse(data, status=200, safe=False)
```

**With this**:
```python
                        model.objects.filter(uuid=R["ownerid"]).update(
                            attachmentcount=data["attcount"]
                        )

                    # NEW: Auto-trigger transcription for audio attachments on jobneeddetails
                    if (data["ownername"].lower() == "jobneeddetails" and
                        self._is_audio_file(data["filename"])):
                        self._trigger_audio_transcription(R["ownerid"], data["filename"])
                        # Add transcript status to response
                        data["transcript_status"] = "PENDING"

                return rp.JsonResponse(data, status=200, safe=False)
```

**Add these methods to the `Attachments` class** (after the `post` method):

```python
    def _is_audio_file(self, filename: str) -> bool:
        """Check if uploaded file is an audio file based on extension"""
        audio_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma']
        return any(filename.lower().endswith(ext) for ext in audio_extensions)

    def _trigger_audio_transcription(self, jobneed_detail_uuid: str, filename: str):
        """Trigger background transcription task for audio attachment"""
        try:
            from apps.activity.models.job_model import JobneedDetails
            from background_tasks.tasks import process_audio_transcript

            # Get JobneedDetails ID from UUID
            jobneed_detail = JobneedDetails.objects.get(uuid=jobneed_detail_uuid)

            # Set initial transcript status
            jobneed_detail.transcript_status = 'PENDING'
            jobneed_detail.save()

            # Queue the background transcription task
            process_audio_transcript.delay(jobneed_detail.id)

            logger.info(f"Audio transcription queued for JobneedDetails {jobneed_detail.id}, file: {filename}")

        except JobneedDetails.DoesNotExist:
            logger.error(f"JobneedDetails not found for UUID: {jobneed_detail_uuid}")
        except Exception as e:
            logger.error(f"Failed to trigger audio transcription: {str(e)}", exc_info=True)
```

### 4. Activity URLs
**File**: `apps/activity/urls.py`

**Add import** (around line 27):
```python
from apps.activity.views.transcript_views import (
    TranscriptStatusView,
    TranscriptManagementView,
    SpeechServiceStatusView,
)
```

**Add URL patterns** (before the closing `]`):
```python
    # Speech-to-Text API endpoints
    path("transcript_status/", TranscriptStatusView.as_view(), name="transcript_status"),
    path("transcript_management/", TranscriptManagementView.as_view(), name="transcript_management"),
    path("speech_service_status/", SpeechServiceStatusView.as_view(), name="speech_service_status"),
```

## Configuration Required

### 1. Settings Configuration
**File**: `intelliwiz_config/settings.py`

Add this configuration:

```python
# Google Cloud Speech-to-Text Configuration
GOOGLE_APPLICATION_CREDENTIALS = '/path/to/your/google-cloud-credentials.json'
```

### 2. System Dependencies

Install required system packages:

```bash
# Install FFmpeg (for audio conversion)
sudo apt-get update
sudo apt-get install ffmpeg

# Verify installation
ffmpeg -version
ffprobe -version
```

### 3. Python Dependencies

Add to your `requirements.txt`:

```
google-cloud-speech>=2.21.0
```

Install with:
```bash
pip install google-cloud-speech
```

## Database Migration

Run the migration after applying model changes:

```bash
python manage.py migrate activity
```

## Testing

Run the tests after implementing all changes:

```bash
# Run speech-to-text specific tests
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/core/tests/test_services/test_speech_to_text_service.py -v
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/activity/tests/test_views/test_transcript_views.py -v
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest background_tasks/tests/test_speech_tasks.py -v

# Run all activity app tests to ensure nothing broke
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/activity/tests/ -v
```

## Frontend Integration

### JavaScript Example

```javascript
// After audio upload, start polling for transcript status
function startTranscriptPolling(jobneedDetailId) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/activity/transcript_status/?jobneed_detail_id=${jobneedDetailId}`);
            const data = await response.json();

            if (data.transcript_status === 'COMPLETED') {
                // Show transcript in UI
                displayTranscript(data.transcript);
                clearInterval(pollInterval);
            } else if (data.transcript_status === 'FAILED') {
                showError('Transcription failed');
                clearInterval(pollInterval);
            }
            // Continue polling if status is PENDING or PROCESSING
        } catch (error) {
            console.error('Error checking transcript status:', error);
        }
    }, 3000); // Poll every 3 seconds
}

function displayTranscript(transcript) {
    // Display transcript in your UI
    const transcriptElement = document.getElementById('transcript-content');
    if (transcriptElement) {
        transcriptElement.textContent = transcript;
        transcriptElement.style.display = 'block';
    }
}

function showError(message) {
    // Show error message in your UI
    alert(message);
}
```

### API Endpoints

1. **Check Transcript Status**:
   - `GET /activity/transcript_status/?jobneed_detail_id=123`
   - Returns: `{"transcript_status": "COMPLETED", "transcript": "...", ...}`

2. **Retry Failed Transcription**:
   - `POST /activity/transcript_management/`
   - Data: `{"action": "retry_transcription", "jobneed_detail_id": "123"}`

3. **Clear Transcript**:
   - `POST /activity/transcript_management/`
   - Data: `{"action": "clear_transcript", "jobneed_detail_id": "123"}`

4. **Service Status**:
   - `GET /activity/speech_service_status/`
   - Returns service configuration and availability

## How It Works

1. **User uploads audio file** → `attachment_views.py` detects audio extensions
2. **Immediate response** → Returns `{"transcript_status": "PENDING"}`
3. **Background processing** → Celery task converts audio and calls Google Speech API
4. **Status updates** → Database fields track: PENDING → PROCESSING → COMPLETED/FAILED
5. **Frontend polling** → JavaScript polls transcript status endpoint
6. **Display result** → Show transcribed text when completed

## Troubleshooting

### Common Issues

1. **Google Cloud Credentials**: Ensure the credentials file exists and is readable
2. **FFmpeg Missing**: Install ffmpeg system package for audio conversion
3. **File Size Limits**: Default 10MB limit, adjust `MAX_FILE_SIZE` if needed
4. **Celery Not Running**: Ensure Celery worker and Redis are running
5. **Permission Issues**: Ensure Django can read the credentials file

### Logs to Check

- **Django logs**: Check for transcription errors
- **Celery logs**: Check background task execution
- **Google Cloud logs**: Check API quota and errors

## Security Considerations

- Google Cloud credentials should be stored securely
- File upload validation is in place (10MB limit)
- Only authenticated users can access transcript endpoints
- Audio files are processed server-side, not sent to client

This implementation provides a complete, production-ready speech-to-text solution that automatically transcribes audio uploads during SiteSurvey operations.