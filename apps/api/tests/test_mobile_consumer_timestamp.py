"""
Tests for MobileSyncConsumer timestamp parsing.

Ensures ISO8601 timestamps with timezone offsets are parsed correctly
for server-to-device synchronization queries.
"""

from asgiref.sync import async_to_sync
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.api.mobile_consumers import MobileSyncConsumer
from apps.voice_recognition.models import VoiceVerificationLog

User = get_user_model()


class MobileConsumerTimestampParsingTests(TestCase):
    """Verify server voice data retrieval handles ISO8601 timestamps safely."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='voiceuser',
            peoplecode='VUSER001',
            peoplename='Voice User',
            email='voice@example.com',
            password='strong-pass-123'
        )

        older_timestamp = timezone.now() - timedelta(hours=2)
        recent_timestamp = timezone.now() - timedelta(minutes=5)

        VoiceVerificationLog.objects.create(
            verification_id='voice-old',
            user=self.user,
            device_id='device-123',
            verified=True,
            result=VoiceVerificationLog.VerificationResult.SUCCESS,
            confidence_score=0.9,
            created_at=older_timestamp
        )

        VoiceVerificationLog.objects.create(
            verification_id='voice-recent',
            user=self.user,
            device_id='device-123',
            verified=True,
            result=VoiceVerificationLog.VerificationResult.SUCCESS,
            confidence_score=0.96,
            created_at=recent_timestamp
        )

    def test_parses_zulu_timestamp(self):
        consumer = MobileSyncConsumer()
        consumer.user = self.user

        cutoff = (timezone.now() - timedelta(minutes=30)).astimezone(timezone.utc)
        zulu_timestamp = cutoff.isoformat().replace('+00:00', 'Z')
        data = async_to_sync(consumer._get_server_voice_data)(zulu_timestamp)

        self.assertTrue(any(item['id'] == 'voice-recent' for item in data))
        self.assertFalse(any(item['id'] == 'voice-old' for item in data))
