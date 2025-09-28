"""
Tests for SpeechToTextService

Test coverage for the speech-to-text service including:
- Service initialization
- Audio file handling
- Transcription methods
- Error handling
- Edge cases
"""

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

    @patch('os.path.exists', return_value=False)
    def test_initialization_with_missing_credentials_file(self, mock_exists):
        """Test service initialization with missing credentials file"""
        with patch.object(settings, 'GOOGLE_APPLICATION_CREDENTIALS', '/nonexistent/credentials.json'):
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

    def test_get_supported_languages(self):
        """Test supported languages retrieval"""
        languages = self.service.get_supported_languages()

        self.assertIsInstance(languages, dict)
        self.assertIn('en', languages)
        self.assertIn('hi', languages)
        self.assertEqual(languages['en'], 'en-US')
        self.assertEqual(languages['hi'], 'hi-IN')

    @patch('subprocess.run')
    def test_get_audio_duration(self, mock_subprocess):
        """Test audio duration retrieval"""
        # Mock successful ffprobe response
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "45.678\n"

        duration = self.service._get_audio_duration('/path/to/audio.wav')

        self.assertEqual(duration, 45.678)
        mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    def test_get_audio_duration_failure(self, mock_subprocess):
        """Test audio duration retrieval failure"""
        # Mock ffprobe failure
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Error message"

        duration = self.service._get_audio_duration('/path/to/audio.wav')

        self.assertEqual(duration, 0.0)

    @patch('tempfile.NamedTemporaryFile')
    @patch('subprocess.run')
    def test_convert_to_wav_success(self, mock_subprocess, mock_tempfile):
        """Test successful audio conversion to WAV"""
        # Mock temporary file
        mock_temp = Mock()
        mock_temp.name = '/tmp/converted.wav'
        mock_tempfile.return_value.__enter__.return_value = mock_temp

        # Mock successful ffmpeg conversion
        mock_subprocess.return_value.returncode = 0

        result = self.service._convert_to_wav('/path/to/audio.mp3')

        self.assertEqual(result, '/tmp/converted.wav')
        mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    def test_convert_to_wav_failure(self, mock_subprocess):
        """Test failed audio conversion to WAV"""
        # Mock ffmpeg failure
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Conversion error"

        result = self.service._convert_to_wav('/path/to/audio.mp3')

        self.assertIsNone(result)

    def test_convert_to_wav_already_wav(self):
        """Test conversion when file is already WAV"""
        wav_path = '/path/to/audio.wav'
        result = self.service._convert_to_wav(wav_path)

        # Should return the same path for WAV files
        self.assertEqual(result, wav_path)

    @patch('subprocess.run')
    def test_split_audio_into_chunks(self, mock_subprocess):
        """Test audio splitting into chunks"""
        # Mock successful ffmpeg splitting
        mock_subprocess.return_value.returncode = 0

        with patch('os.listdir', return_value=['chunk_001.wav', 'chunk_002.wav', 'chunk_003.wav']):
            chunks = self.service._split_audio_into_chunks('/path/to/long_audio.wav', '/tmp')

            self.assertEqual(len(chunks), 3)
            self.assertIn('/tmp/chunk_001.wav', chunks)
            self.assertIn('/tmp/chunk_002.wav', chunks)
            self.assertIn('/tmp/chunk_003.wav', chunks)

    @patch('subprocess.run')
    def test_split_audio_failure(self, mock_subprocess):
        """Test audio splitting failure"""
        # Mock ffmpeg failure
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Splitting error"

        chunks = self.service._split_audio_into_chunks('/path/to/audio.wav', '/tmp')

        self.assertEqual(chunks, [])

    def test_detect_language_default(self):
        """Test language detection returns default"""
        mock_jobneed_detail = Mock()

        language = self.service._detect_language(mock_jobneed_detail)

        self.assertEqual(language, self.service.DEFAULT_LANGUAGE)

    @patch('builtins.open', create=True)
    def test_transcribe_short_audio_success(self, mock_open):
        """Test successful short audio transcription"""
        # Mock file reading
        mock_open.return_value.__enter__.return_value.read.return_value = b'fake_audio_data'

        # Mock Google Speech API client
        mock_client = Mock()
        mock_response = Mock()
        mock_result = Mock()
        mock_alternative = Mock()
        mock_alternative.transcript = "Hello, this is a test transcription."
        mock_alternative.confidence = 0.95
        mock_result.alternatives = [mock_alternative]
        mock_response.results = [mock_result]
        mock_client.recognize.return_value = mock_response

        self.service.client = mock_client

        transcript = self.service._transcribe_short_audio('/path/to/audio.wav', 'en-US')

        self.assertEqual(transcript, "Hello, this is a test transcription.")
        mock_client.recognize.assert_called_once()

    def test_transcribe_short_audio_no_results(self):
        """Test short audio transcription with no results"""
        # Mock Google Speech API client with empty results
        mock_client = Mock()
        mock_response = Mock()
        mock_response.results = []
        mock_client.recognize.return_value = mock_response

        self.service.client = mock_client

        with patch('builtins.open', create=True):
            transcript = self.service._transcribe_short_audio('/path/to/audio.wav', 'en-US')

            self.assertIsNone(transcript)

    def test_transcribe_short_audio_exception(self):
        """Test short audio transcription with exception"""
        # Mock Google Speech API client to raise exception
        mock_client = Mock()
        mock_client.recognize.side_effect = Exception("API Error")

        self.service.client = mock_client

        with patch('builtins.open', create=True):
            transcript = self.service._transcribe_short_audio('/path/to/audio.wav', 'en-US')

            self.assertIsNone(transcript)

    @patch('tempfile.TemporaryDirectory')
    def test_transcribe_long_audio_success(self, mock_temp_dir):
        """Test successful long audio transcription"""
        # Mock temporary directory
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/test_dir'

        # Mock audio splitting
        with patch.object(self.service, '_split_audio_into_chunks') as mock_split:
            mock_split.return_value = ['/tmp/test_dir/chunk_001.wav', '/tmp/test_dir/chunk_002.wav']

            # Mock short audio transcription for each chunk
            with patch.object(self.service, '_transcribe_short_audio') as mock_transcribe:
                mock_transcribe.side_effect = ["First chunk transcript.", "Second chunk transcript."]

                transcript = self.service._transcribe_long_audio('/path/to/long_audio.wav', 'en-US')

                self.assertEqual(transcript, "First chunk transcript. Second chunk transcript.")
                self.assertEqual(mock_transcribe.call_count, 2)

    @patch('tempfile.TemporaryDirectory')
    def test_transcribe_long_audio_no_chunks(self, mock_temp_dir):
        """Test long audio transcription with no chunks"""
        # Mock temporary directory
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/test_dir'

        # Mock audio splitting failure
        with patch.object(self.service, '_split_audio_into_chunks') as mock_split:
            mock_split.return_value = []

            transcript = self.service._transcribe_long_audio('/path/to/long_audio.wav', 'en-US')

            self.assertIsNone(transcript)

    def test_transcribe_audio_no_client(self):
        """Test transcription when client is not available"""
        self.service.client = None

        mock_jobneed_detail = Mock()
        transcript = self.service.transcribe_audio(mock_jobneed_detail)

        self.assertIsNone(transcript)

    @patch.object(SpeechToTextService, '_get_audio_attachment')
    def test_transcribe_audio_no_attachment(self, mock_get_attachment):
        """Test transcription when no audio attachment is found"""
        self.service.client = Mock()
        mock_get_attachment.return_value = None

        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = 123

        transcript = self.service.transcribe_audio(mock_jobneed_detail)

        self.assertIsNone(transcript)

    @patch('os.path.getsize', return_value=20*1024*1024)  # 20MB file
    @patch.object(SpeechToTextService, '_get_audio_attachment')
    @patch.object(SpeechToTextService, '_get_audio_file_path')
    @patch('os.path.exists', return_value=True)
    def test_transcribe_audio_file_too_large(self, mock_exists, mock_get_path, mock_get_attachment):
        """Test transcription when file is too large"""
        self.service.client = Mock()

        mock_attachment = Mock()
        mock_get_attachment.return_value = mock_attachment
        mock_get_path.return_value = '/path/to/large_audio.mp3'

        mock_jobneed_detail = Mock()
        transcript = self.service.transcribe_audio(mock_jobneed_detail)

        self.assertIsNone(transcript)