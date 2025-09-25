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

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_process_audio_transcript_exception_with_retry(self, mock_service_class, mock_get):
        """Test task exception handling with retry"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = self.jobneed_detail_id
        mock_get.return_value = mock_jobneed_detail

        # Mock SpeechToTextService raising exception
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.side_effect = Exception("Transcription API error")
        mock_service_class.return_value = mock_service

        # Create a mock task with retry capability
        class MockTask:
            def __init__(self):
                self.request = Mock()
                self.request.retries = 0
                self.max_retries = 3

            def retry(self, exc):
                raise exc

        mock_task = MockTask()

        # Execute the task with exception
        with self.assertRaises(Exception):
            process_audio_transcript.bind(mock_task)(self.jobneed_detail_id)

        # Verify error was logged
        self.assertEqual(mock_jobneed_detail.transcript_status, 'FAILED')

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_process_audio_transcript_max_retries_exceeded(self, mock_service_class, mock_get):
        """Test task when max retries are exceeded"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = self.jobneed_detail_id
        mock_get.return_value = mock_jobneed_detail

        # Mock SpeechToTextService raising exception
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.side_effect = Exception("Persistent API error")
        mock_service_class.return_value = mock_service

        # Create a mock task that has exceeded max retries
        class MockTask:
            def __init__(self):
                self.request = Mock()
                self.request.retries = 3
                self.max_retries = 3

            def retry(self, exc):
                # Don't actually retry since max retries exceeded
                pass

        mock_task = MockTask()

        result = process_audio_transcript.bind(mock_task)(self.jobneed_detail_id)

        self.assertIn('traceback', result)
        self.assertEqual(result['status'], 'FAILED_PERMANENTLY')

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_process_audio_transcript_status_updates(self, mock_service_class, mock_get):
        """Test that task correctly updates transcript status throughout process"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = self.jobneed_detail_id
        mock_jobneed_detail.transcript_language = None  # Not set initially
        mock_get.return_value = mock_jobneed_detail

        # Mock SpeechToTextService
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.return_value = "Transcribed content"
        mock_service.DEFAULT_LANGUAGE = 'en-US'
        mock_service_class.return_value = mock_service

        # Execute the task
        with patch('django.utils.timezone.now', return_value=timezone.now()):
            result = process_audio_transcript(self.jobneed_detail_id)

        # Verify status progression
        save_calls = mock_jobneed_detail.save.call_args_list
        self.assertTrue(len(save_calls) >= 2)  # At least PROCESSING and COMPLETED

        # Verify final state
        self.assertEqual(mock_jobneed_detail.transcript_status, 'COMPLETED')
        self.assertEqual(mock_jobneed_detail.transcript_language, 'en-US')

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_process_audio_transcript_preserves_existing_language(self, mock_service_class, mock_get):
        """Test that task preserves existing transcript language setting"""
        # Mock JobneedDetails with existing language
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = self.jobneed_detail_id
        mock_jobneed_detail.transcript_language = 'hi-IN'  # Already set
        mock_get.return_value = mock_jobneed_detail

        # Mock SpeechToTextService
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.return_value = "Transcribed content"
        mock_service.DEFAULT_LANGUAGE = 'en-US'
        mock_service_class.return_value = mock_service

        # Execute the task
        with patch('django.utils.timezone.now', return_value=timezone.now()):
            process_audio_transcript(self.jobneed_detail_id)

        # Verify language was preserved
        self.assertEqual(mock_jobneed_detail.transcript_language, 'hi-IN')

    def test_process_audio_transcript_task_metadata(self):
        """Test task configuration and metadata"""
        task = process_audio_transcript

        # Verify task configuration
        self.assertEqual(task.max_retries, 3)
        self.assertEqual(task.default_retry_delay, 60)
        self.assertEqual(task.name, 'process_audio_transcript')
        self.assertTrue(task.bind)


class TestTaskIntegration(TestCase):
    """Integration tests for speech-to-text task workflow"""

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_full_workflow_success(self, mock_service_class, mock_get):
        """Test complete workflow from audio upload to transcript completion"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = 123
        mock_jobneed_detail.transcript_language = None
        mock_get.return_value = mock_jobneed_detail

        # Mock successful transcription service
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.return_value = "Complete transcribed text from audio file."
        mock_service.DEFAULT_LANGUAGE = 'en-US'
        mock_service_class.return_value = mock_service

        # Simulate the full workflow
        with patch('django.utils.timezone.now', return_value=timezone.now()):
            result = process_audio_transcript(123)

        # Verify complete workflow
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(mock_jobneed_detail.transcript, "Complete transcribed text from audio file.")
        self.assertEqual(mock_jobneed_detail.transcript_status, 'COMPLETED')
        self.assertEqual(mock_jobneed_detail.transcript_language, 'en-US')
        self.assertIsNotNone(mock_jobneed_detail.transcript_processed_at)

        # Verify task reported success
        self.assertIn('SUCCESS', result['story'])
        self.assertEqual(result['transcript_length'], len("Complete transcribed text from audio file."))

    @patch('background_tasks.tasks.JobneedDetails.objects.get')
    @patch('background_tasks.tasks.SpeechToTextService')
    def test_workflow_with_service_error(self, mock_service_class, mock_get):
        """Test workflow when service encounters an error"""
        # Mock JobneedDetails
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = 123
        mock_get.return_value = mock_jobneed_detail

        # Mock service with error
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.transcribe_audio.side_effect = Exception("Service error")
        mock_service_class.return_value = mock_service

        # Create mock task for retry testing
        class MockTask:
            def __init__(self):
                self.request = Mock()
                self.request.retries = 0
                self.max_retries = 3

            def retry(self, exc):
                raise exc

        mock_task = MockTask()

        # Execute with error
        with self.assertRaises(Exception):
            process_audio_transcript.bind(mock_task)(123)

        # Verify error state
        self.assertEqual(mock_jobneed_detail.transcript_status, 'FAILED')