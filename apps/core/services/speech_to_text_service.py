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

        except (ValueError, TypeError) as e:
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

        except (ValueError, TypeError) as e:
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

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
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
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
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
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
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

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
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

        except (DatabaseError, IntegrityError, ObjectDoesNotExist):
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

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
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

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
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

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            error_logger.error(f"Error splitting audio: {str(e)}")
            return []

    def get_supported_languages(self) -> Dict[str, str]:
        """Get dictionary of supported languages"""
        return self.SUPPORTED_LANGUAGES.copy()

    def is_service_available(self) -> bool:
        """Check if the speech-to-text service is available"""
        return self.client is not None