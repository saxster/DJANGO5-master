"""
Comprehensive tests for Sync Engine DB Persistence

Tests that WebSocket sync batches actually write to database.
Critical gap identified: tests were only validating event capture, not DB writes.

Following .claude/rules.md testing patterns.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.api.v1.services.sync_engine_service import SyncEngineService
from apps.voice_recognition.models import VoiceVerificationLog

User = get_user_model()


@pytest.mark.django_db
class SyncEnginePersistenceTests(TestCase):
    """Test that sync engine actually persists data to database"""

    def setUp(self):
        """Set up test user and sync engine"""
        self.user = User.objects.create_user(
            loginid='synctest',
            peoplecode='SYNC001',
            peoplename='Sync Test User',
            email='synctest@example.com',
            dateofbirth='1990-01-01'
        )
        self.sync_engine = SyncEngineService()
        self.device_id = 'test-device-123'

    def test_sync_voice_data_persists_to_database(self):
        """Test that voice data from WebSocket batch writes to VoiceVerificationLog"""
        # Arrange
        voice_payload = {
            'voice_data': [
                {
                    'verification_id': 'voice-001',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True,
                    'confidence_score': 0.95,
                    'quality_score': 0.88,
                    'processing_time_ms': 250
                },
                {
                    'verification_id': 'voice-002',
                    'timestamp': timezone.now().isoformat(),
                    'verified': False,
                    'confidence_score': 0.42,
                    'quality_score': 0.65,
                    'processing_time_ms': 180
                }
            ]
        }

        # Act
        result = self.sync_engine.sync_voice_data(
            str(self.user.id),
            voice_payload,
            self.device_id
        )

        # Assert - Check sync result
        self.assertEqual(result['synced_items'], 2)
        self.assertEqual(result['failed_items'], 0)
        self.assertEqual(len(result['errors']), 0)

        # Assert - Verify DB persistence
        voice_logs = VoiceVerificationLog.objects.filter(user_id=str(self.user.id))
        self.assertEqual(voice_logs.count(), 2)

        # Verify first log
        log1 = voice_logs.get(verification_id='voice-001')
        self.assertEqual(log1.device_id, self.device_id)
        self.assertTrue(log1.verified)
        self.assertEqual(log1.confidence_score, 0.95)
        self.assertEqual(log1.quality_score, 0.88)
        self.assertEqual(log1.processing_time_ms, 250)

        # Verify second log
        log2 = voice_logs.get(verification_id='voice-002')
        self.assertFalse(log2.verified)
        self.assertEqual(log2.confidence_score, 0.42)

    def test_duplicate_voice_verification_skipped(self):
        """Test that duplicate verification_id doesn't create duplicate DB records"""
        # Arrange - Create existing log
        VoiceVerificationLog.objects.create(
            verification_id='voice-duplicate',
            user_id=str(self.user.id),
            device_id=self.device_id,
            verified=True,
            confidence_score=0.90,
            created_at=timezone.now()
        )

        voice_payload = {
            'voice_data': [
                {
                    'verification_id': 'voice-duplicate',
                    'timestamp': timezone.now().isoformat(),
                    'verified': False,  # Different value - should be skipped
                    'confidence_score': 0.60
                }
            ]
        }

        # Act
        result = self.sync_engine.sync_voice_data(
            str(self.user.id),
            voice_payload,
            self.device_id
        )

        # Assert - Original record unchanged
        logs = VoiceVerificationLog.objects.filter(verification_id='voice-duplicate')
        self.assertEqual(logs.count(), 1)
        original_log = logs.first()
        self.assertTrue(original_log.verified)  # Original value preserved
        self.assertEqual(original_log.confidence_score, 0.90)

    def test_sync_voice_data_handles_validation_errors(self):
        """Test that validation errors are captured without crashing"""
        # Arrange - Missing required field
        voice_payload = {
            'voice_data': [
                {
                    # Missing 'verification_id' - should fail validation
                    'timestamp': timezone.now().isoformat(),
                    'verified': True
                },
                {
                    'verification_id': 'voice-valid',
                    'timestamp': timezone.now().isoformat(),
                    'verified': True
                }
            ]
        }

        # Act
        result = self.sync_engine.sync_voice_data(
            str(self.user.id),
            voice_payload,
            self.device_id
        )

        # Assert - One succeeded, one failed
        self.assertEqual(result['synced_items'], 1)
        self.assertEqual(result['failed_items'], 1)
        self.assertEqual(len(result['errors']), 1)

        # Verify valid item was persisted
        valid_log = VoiceVerificationLog.objects.filter(verification_id='voice-valid')
        self.assertTrue(valid_log.exists())

    def test_sync_voice_data_empty_batch(self):
        """Test handling of empty voice data batch"""
        # Arrange
        voice_payload = {'voice_data': []}

        # Act
        result = self.sync_engine.sync_voice_data(
            str(self.user.id),
            voice_payload,
            self.device_id
        )

        # Assert
        self.assertEqual(result['synced_items'], 0)
        self.assertEqual(result['failed_items'], 0)
        self.assertEqual(len(result['errors']), 0)

    def test_sync_behavioral_data_placeholder(self):
        """Test behavioral data sync placeholder (implementation pending)"""
        # Arrange
        behavioral_payload = {
            'behavioral_data': [
                {'event_type': 'screen_view', 'timestamp': timezone.now().isoformat()},
                {'event_type': 'button_click', 'timestamp': timezone.now().isoformat()}
            ]
        }

        # Act
        result = self.sync_engine.sync_behavioral_data(
            str(self.user.id),
            behavioral_payload,
            self.device_id
        )

        # Assert - Placeholder returns success without errors
        self.assertEqual(result['synced_items'], 0)  # Not implemented yet
        self.assertEqual(result['failed_items'], 0)
        self.assertEqual(len(result['errors']), 0)

    def test_sync_session_data_placeholder(self):
        """Test session data sync placeholder"""
        # Arrange
        session_payload = {
            'sessions': [
                {'session_id': 'sess-001', 'duration_ms': 120000},
                {'session_id': 'sess-002', 'duration_ms': 85000}
            ]
        }

        # Act
        result = self.sync_engine.sync_session_data(
            str(self.user.id),
            session_payload,
            self.device_id
        )

        # Assert
        self.assertEqual(result['synced_items'], 0)
        self.assertEqual(result['failed_items'], 0)

    def test_sync_metrics_data_placeholder(self):
        """Test metrics data sync placeholder"""
        # Arrange
        metrics_payload = {
            'metrics': [
                {'metric_name': 'app_start_time_ms', 'value': 450},
                {'metric_name': 'api_latency_ms', 'value': 85}
            ]
        }

        # Act
        result = self.sync_engine.sync_metrics_data(
            str(self.user.id),
            metrics_payload,
            self.device_id
        )

        # Assert
        self.assertEqual(result['synced_items'], 0)
        self.assertEqual(result['failed_items'], 0)

    def test_sync_voice_data_large_batch_performance(self):
        """Test syncing large batch of voice data (performance check)"""
        # Arrange - Create 100 voice verification items
        voice_payload = {
            'voice_data': [
                {
                    'verification_id': f'voice-batch-{i}',
                    'timestamp': timezone.now().isoformat(),
                    'verified': i % 2 == 0,
                    'confidence_score': 0.50 + (i / 200)
                }
                for i in range(100)
            ]
        }

        # Act
        result = self.sync_engine.sync_voice_data(
            str(self.user.id),
            voice_payload,
            self.device_id
        )

        # Assert
        self.assertEqual(result['synced_items'], 100)
        self.assertEqual(result['failed_items'], 0)

        # Verify all persisted
        logs = VoiceVerificationLog.objects.filter(user_id=str(self.user.id))
        self.assertEqual(logs.count(), 100)