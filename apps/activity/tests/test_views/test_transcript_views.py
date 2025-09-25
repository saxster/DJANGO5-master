"""
Tests for Transcript Views

Test coverage for speech-to-text API endpoints including:
- Transcript status checking
- Transcript management operations
- Service status queries
- Error handling
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from apps.activity.models.job_model import JobneedDetails
from apps.core.services.speech_to_text_service import SpeechToTextService

User = get_user_model()


class TestTranscriptStatusView(TestCase):
    """Test cases for TranscriptStatusView"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)

        # Create test JobneedDetails
        self.jobneed_detail = JobneedDetails(
            id=1,
            seqno=1,
            transcript_status='COMPLETED',
            transcript='This is a test transcript.',
            transcript_language='en-US',
            transcript_processed_at=timezone.now()
        )

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_get_transcript_status_by_id(self, mock_get):
        """Test getting transcript status by JobneedDetails ID"""
        mock_get.return_value = self.jobneed_detail

        response = self.client.get(
            reverse('activity:transcript_status'),
            {'jobneed_detail_id': '1'}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['jobneed_detail_id'], 1)
        self.assertEqual(data['transcript_status'], 'COMPLETED')
        self.assertEqual(data['transcript'], 'This is a test transcript.')
        self.assertEqual(data['transcript_language'], 'en-US')
        self.assertTrue(data['has_transcript'])
        self.assertIsNotNone(data['transcript_processed_at'])

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_get_transcript_status_by_uuid(self, mock_get):
        """Test getting transcript status by JobneedDetails UUID"""
        self.jobneed_detail.uuid = 'test-uuid-123'
        mock_get.return_value = self.jobneed_detail

        response = self.client.get(
            reverse('activity:transcript_status'),
            {'uuid': 'test-uuid-123'}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['uuid'], 'test-uuid-123')

    def test_get_transcript_status_missing_params(self):
        """Test getting transcript status without required parameters"""
        response = self.client.get(reverse('activity:transcript_status'))

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_get_transcript_status_not_found(self, mock_get):
        """Test getting transcript status for non-existent JobneedDetails"""
        from apps.activity.models.job_model import JobneedDetails
        mock_get.side_effect = JobneedDetails.DoesNotExist()

        response = self.client.get(
            reverse('activity:transcript_status'),
            {'jobneed_detail_id': '999'}
        )

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data['error'], 'JobneedDetails not found')

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_get_transcript_status_pending(self, mock_get):
        """Test getting transcript status for pending transcription"""
        self.jobneed_detail.transcript_status = 'PENDING'
        self.jobneed_detail.transcript = None
        mock_get.return_value = self.jobneed_detail

        response = self.client.get(
            reverse('activity:transcript_status'),
            {'jobneed_detail_id': '1'}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['transcript_status'], 'PENDING')
        self.assertFalse(data['has_transcript'])
        self.assertNotIn('transcript', data)

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_get_transcript_status_failed(self, mock_get):
        """Test getting transcript status for failed transcription"""
        self.jobneed_detail.transcript_status = 'FAILED'
        self.jobneed_detail.transcript = None
        mock_get.return_value = self.jobneed_detail

        response = self.client.get(
            reverse('activity:transcript_status'),
            {'jobneed_detail_id': '1'}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['transcript_status'], 'FAILED')
        self.assertFalse(data['has_transcript'])
        self.assertIn('error_message', data)

    def test_get_transcript_status_unauthenticated(self):
        """Test getting transcript status without authentication"""
        self.client.logout()

        response = self.client.get(
            reverse('activity:transcript_status'),
            {'jobneed_detail_id': '1'}
        )

        self.assertEqual(response.status_code, 302)  # Redirect to login


class TestTranscriptManagementView(TestCase):
    """Test cases for TranscriptManagementView"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)

        self.jobneed_detail = JobneedDetails(
            id=1,
            seqno=1,
            transcript_status='FAILED',
            transcript=None
        )

    def test_post_missing_action(self):
        """Test POST request without action parameter"""
        response = self.client.post(
            reverse('activity:transcript_management'),
            {'jobneed_detail_id': '1'}
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'Missing action parameter')

    def test_post_missing_jobneed_detail_id(self):
        """Test POST request without jobneed_detail_id parameter"""
        response = self.client.post(
            reverse('activity:transcript_management'),
            {'action': 'retry_transcription'}
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'Missing jobneed_detail_id')

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_post_jobneed_detail_not_found(self, mock_get):
        """Test POST request for non-existent JobneedDetails"""
        from apps.activity.models.job_model import JobneedDetails
        mock_get.side_effect = JobneedDetails.DoesNotExist()

        response = self.client.post(
            reverse('activity:transcript_management'),
            {
                'action': 'retry_transcription',
                'jobneed_detail_id': '999'
            }
        )

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data['error'], 'JobneedDetails not found')

    @patch('background_tasks.tasks.process_audio_transcript.delay')
    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_retry_transcription_success(self, mock_get, mock_task):
        """Test successful transcription retry"""
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = 1
        mock_get.return_value = mock_jobneed_detail

        response = self.client.post(
            reverse('activity:transcript_management'),
            {
                'action': 'retry_transcription',
                'jobneed_detail_id': '1'
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['transcript_status'], 'PENDING')
        mock_task.assert_called_once_with(1)

        # Verify that transcript fields were reset
        self.assertIsNone(mock_jobneed_detail.transcript)
        self.assertEqual(mock_jobneed_detail.transcript_status, 'PENDING')
        self.assertIsNone(mock_jobneed_detail.transcript_processed_at)

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_clear_transcript_success(self, mock_get):
        """Test successful transcript clearing"""
        mock_jobneed_detail = Mock()
        mock_jobneed_detail.id = 1
        mock_get.return_value = mock_jobneed_detail

        response = self.client.post(
            reverse('activity:transcript_management'),
            {
                'action': 'clear_transcript',
                'jobneed_detail_id': '1'
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'success')
        self.assertIsNone(data['transcript_status'])

        # Verify that all transcript fields were cleared
        self.assertIsNone(mock_jobneed_detail.transcript)
        self.assertIsNone(mock_jobneed_detail.transcript_status)
        self.assertIsNone(mock_jobneed_detail.transcript_language)
        self.assertIsNone(mock_jobneed_detail.transcript_processed_at)

    @patch('apps.activity.models.job_model.JobneedDetails.objects.get')
    def test_unknown_action(self, mock_get):
        """Test POST request with unknown action"""
        mock_get.return_value = Mock()

        response = self.client.post(
            reverse('activity:transcript_management'),
            {
                'action': 'unknown_action',
                'jobneed_detail_id': '1'
            }
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'Unknown action: unknown_action')


class TestSpeechServiceStatusView(TestCase):
    """Test cases for SpeechServiceStatusView"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)

    @patch('apps.core.services.speech_to_text_service.SpeechToTextService')
    def test_get_service_status_available(self, mock_service_class):
        """Test getting service status when service is available"""
        mock_service = Mock()
        mock_service.is_service_available.return_value = True
        mock_service.get_supported_languages.return_value = {
            'en': 'en-US',
            'hi': 'hi-IN'
        }
        mock_service.DEFAULT_LANGUAGE = 'en-US'
        mock_service.MAX_FILE_SIZE = 10 * 1024 * 1024
        mock_service.CHUNK_DURATION = 30
        mock_service_class.return_value = mock_service

        with patch('django.conf.settings.GOOGLE_APPLICATION_CREDENTIALS', '/path/to/creds.json'):
            with patch('os.path.exists', return_value=True):
                response = self.client.get(reverse('activity:speech_service_status'))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data['service_available'])
        self.assertTrue(data['credentials_configured'])
        self.assertEqual(data['supported_languages']['en'], 'en-US')
        self.assertEqual(data['default_language'], 'en-US')
        self.assertEqual(data['max_file_size_mb'], 10)
        self.assertEqual(data['chunk_duration_seconds'], 30)

    @patch('apps.core.services.speech_to_text_service.SpeechToTextService')
    def test_get_service_status_unavailable(self, mock_service_class):
        """Test getting service status when service is unavailable"""
        mock_service = Mock()
        mock_service.is_service_available.return_value = False
        mock_service.get_supported_languages.return_value = {}
        mock_service.DEFAULT_LANGUAGE = 'en-US'
        mock_service.MAX_FILE_SIZE = 10 * 1024 * 1024
        mock_service.CHUNK_DURATION = 30
        mock_service_class.return_value = mock_service

        # Test with no credentials configured
        with patch('django.conf.settings', spec=[]):  # No GOOGLE_APPLICATION_CREDENTIALS
            response = self.client.get(reverse('activity:speech_service_status'))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertFalse(data['service_available'])
        self.assertFalse(data['credentials_configured'])

    @patch('apps.core.services.speech_to_text_service.SpeechToTextService')
    def test_get_service_status_credentials_missing(self, mock_service_class):
        """Test getting service status with missing credentials file"""
        mock_service = Mock()
        mock_service.is_service_available.return_value = False
        mock_service.get_supported_languages.return_value = {}
        mock_service.DEFAULT_LANGUAGE = 'en-US'
        mock_service.MAX_FILE_SIZE = 10 * 1024 * 1024
        mock_service.CHUNK_DURATION = 30
        mock_service_class.return_value = mock_service

        with patch('django.conf.settings.GOOGLE_APPLICATION_CREDENTIALS', '/missing/creds.json'):
            with patch('os.path.exists', return_value=False):
                response = self.client.get(reverse('activity:speech_service_status'))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertFalse(data['service_available'])
        self.assertFalse(data['credentials_configured'])


class TestAttachmentViewIntegration(TestCase):
    """Integration tests for attachment upload with transcription"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)

    @patch('apps.activity.views.attachment_views.Attachments._trigger_audio_transcription')
    @patch('apps.activity.views.attachment_views.utils.upload')
    @patch('apps.activity.models.attachment_model.Attachment.objects.create_att_record')
    def test_audio_upload_triggers_transcription(self, mock_create_record, mock_upload, mock_trigger):
        """Test that uploading audio file triggers transcription"""
        # Mock successful upload
        mock_upload.return_value = (True, 'test_audio.mp3', '/path/to/upload')

        # Mock attachment record creation
        mock_create_record.return_value = {
            'id': 1,
            'filename': 'test_audio.mp3',
            'ownername': 'JOBNEEDDETAILS',
            'attcount': 1
        }

        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_audio:
            response = self.client.post(
                reverse('activity:attachments'),
                {
                    'img': temp_audio,
                    'ownername': 'JOBNEEDDETAILS',
                    'ownerid': 'test-uuid-123',
                    'attachmenttype': 'AUDIO',
                    'ctzoffset': '0'
                }
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify transcription was triggered
        mock_trigger.assert_called_once_with('test-uuid-123', 'test_audio.mp3')
        self.assertEqual(data['transcript_status'], 'PENDING')

    @patch('apps.activity.views.attachment_views.utils.upload')
    @patch('apps.activity.models.attachment_model.Attachment.objects.create_att_record')
    def test_non_audio_upload_no_transcription(self, mock_create_record, mock_upload):
        """Test that uploading non-audio file doesn't trigger transcription"""
        # Mock successful upload of image
        mock_upload.return_value = (True, 'test_image.jpg', '/path/to/upload')

        # Mock attachment record creation
        mock_create_record.return_value = {
            'id': 1,
            'filename': 'test_image.jpg',
            'ownername': 'JOBNEEDDETAILS',
            'attcount': 1
        }

        with tempfile.NamedTemporaryFile(suffix='.jpg') as temp_image:
            response = self.client.post(
                reverse('activity:attachments'),
                {
                    'img': temp_image,
                    'ownername': 'JOBNEEDDETAILS',
                    'ownerid': 'test-uuid-123',
                    'attachmenttype': 'IMAGE',
                    'ctzoffset': '0'
                }
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify no transcription status was added
        self.assertNotIn('transcript_status', data)