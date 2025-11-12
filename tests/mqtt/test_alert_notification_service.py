"""
Comprehensive tests for MQTT Alert Notification Service.

Tests SMS, email, and push notification delivery with rate limiting,
error handling, and multi-channel routing based on severity.

Coverage target: 80%+
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone as dt_timezone
from django.core import mail
from django.core.cache import cache
from django.test import override_settings

from apps.mqtt.services.alert_notification_service import (
    AlertNotificationService,
    AlertNotification,
    NotificationResult
)


@pytest.fixture
def sample_alert():
    """Create sample alert for testing."""
    return AlertNotification(
        alert_id=123,
        alert_type="DEVICE_OFFLINE",
        severity="CRITICAL",
        message="Guard device GPS-001 has been offline for 15 minutes",
        source_id="GPS-001",
        timestamp=datetime.now(dt_timezone.utc),
        location={'lat': 12.9716, 'lon': 77.5946},
        metadata={'battery': 15, 'signal': 20}
    )


@pytest.fixture
def recipients():
    """Sample recipients for testing."""
    return {
        'sms': ['+919876543210', '+918765432109'],
        'email': ['supervisor@example.com', 'manager@example.com'],
        'push': ['fcm_token_123', 'fcm_token_456']
    }


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


class TestAlertNotificationService:
    """Test multi-channel alert notifications."""

    def test_notify_critical_alert_all_channels(self, sample_alert, recipients):
        """Test that critical alerts trigger all notification channels."""
        with patch.object(AlertNotificationService, '_send_sms_notifications') as mock_sms, \
             patch.object(AlertNotificationService, '_send_email_notification') as mock_email, \
             patch.object(AlertNotificationService, '_send_push_notifications') as mock_push:
            
            mock_sms.return_value = [NotificationResult('sms', True, 250)]
            mock_email.return_value = NotificationResult('email', True, 150)
            mock_push.return_value = [NotificationResult('push', True, 100)]
            
            results = AlertNotificationService.notify_alert(sample_alert, recipients)
            
            assert len(results) == 4  # 2 SMS + 1 email + 2 push
            mock_sms.assert_called_once()
            mock_email.assert_called_once()
            mock_push.assert_called_once()

    def test_notify_high_severity_includes_sms(self, recipients):
        """Test that high severity alerts trigger SMS."""
        alert = AlertNotification(
            alert_id=124,
            alert_type="INTRUSION",
            severity="HIGH",
            message="Perimeter breach detected",
            source_id="CAM-005",
            timestamp=datetime.now(dt_timezone.utc)
        )
        
        with patch.object(AlertNotificationService, '_send_sms_notifications') as mock_sms, \
             patch.object(AlertNotificationService, '_send_email_notification') as mock_email, \
             patch.object(AlertNotificationService, '_send_push_notifications') as mock_push:
            
            mock_sms.return_value = []
            mock_email.return_value = NotificationResult('email', True, 150)
            mock_push.return_value = []
            
            AlertNotificationService.notify_alert(alert, recipients)
            
            mock_sms.assert_called_once()

    def test_notify_medium_severity_skips_sms(self, recipients):
        """Test that medium severity alerts skip SMS."""
        alert = AlertNotification(
            alert_id=125,
            alert_type="TEMPERATURE_WARNING",
            severity="MEDIUM",
            message="Temperature above threshold",
            source_id="TEMP-001",
            timestamp=datetime.now(dt_timezone.utc)
        )
        
        with patch.object(AlertNotificationService, '_send_sms_notifications') as mock_sms, \
             patch.object(AlertNotificationService, '_send_email_notification') as mock_email, \
             patch.object(AlertNotificationService, '_send_push_notifications') as mock_push:
            
            mock_email.return_value = NotificationResult('email', True, 150)
            mock_push.return_value = []
            
            AlertNotificationService.notify_alert(alert, recipients)
            
            mock_sms.assert_not_called()


class TestSMSNotifications:
    """Test SMS notification delivery via Twilio."""

    @patch('apps.mqtt.services.alert_notification_service.Client')
    @override_settings(
        TWILIO_ACCOUNT_SID='test_sid',
        TWILIO_AUTH_TOKEN='test_token',
        TWILIO_PHONE_NUMBER='+15555555555'
    )
    def test_send_sms_success(self, mock_twilio_client, sample_alert):
        """Test successful SMS delivery."""
        mock_message = Mock()
        mock_message.sid = 'SM123456'
        mock_twilio_client.return_value.messages.create.return_value = mock_message
        
        results = AlertNotificationService._send_sms_notifications(
            sample_alert,
            ['+919876543210']
        )
        
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].channel == 'sms'
        assert results[0].external_id == 'SM123456'
        assert results[0].latency_ms > 0

    @override_settings(TWILIO_ACCOUNT_SID=None)
    def test_send_sms_not_configured(self, sample_alert):
        """Test SMS when Twilio not configured."""
        results = AlertNotificationService._send_sms_notifications(
            sample_alert,
            ['+919876543210']
        )
        
        assert len(results) == 1
        assert results[0].success is False
        assert 'not configured' in results[0].error_message

    @patch('apps.mqtt.services.alert_notification_service.Client')
    @override_settings(
        TWILIO_ACCOUNT_SID='test_sid',
        TWILIO_AUTH_TOKEN='test_token',
        TWILIO_PHONE_NUMBER='+15555555555'
    )
    def test_sms_rate_limiting(self, mock_twilio_client, sample_alert):
        """Test SMS rate limiting prevents spam."""
        phone = '+919876543210'
        
        # First 10 messages should succeed
        for i in range(10):
            result = AlertNotificationService._check_sms_rate_limit(phone)
            assert result is True, f"Message {i+1} should be allowed"
        
        # 11th message should be rate limited
        result = AlertNotificationService._check_sms_rate_limit(phone)
        assert result is False, "11th message should be rate limited"

    @patch('apps.mqtt.services.alert_notification_service.Client')
    @override_settings(
        TWILIO_ACCOUNT_SID='test_sid',
        TWILIO_AUTH_TOKEN='test_token',
        TWILIO_PHONE_NUMBER='+15555555555'
    )
    def test_sms_network_failure_handling(self, mock_twilio_client, sample_alert):
        """Test SMS delivery failure handling."""
        from requests.exceptions import RequestException
        
        mock_twilio_client.return_value.messages.create.side_effect = RequestException(
            "Network timeout"
        )
        
        results = AlertNotificationService._send_sms_notifications(
            sample_alert,
            ['+919876543210']
        )
        
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error_message is not None

    def test_format_sms_message_within_limit(self, sample_alert):
        """Test SMS message formatting stays within 160 character limit."""
        message = AlertNotificationService._format_sms_message(sample_alert)
        
        assert len(message) <= 160
        assert sample_alert.severity in message
        assert sample_alert.alert_type in message
        assert sample_alert.source_id in message


class TestEmailNotifications:
    """Test email notification delivery."""

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='alerts@intelliwiz.com'
    )
    def test_send_email_success(self, sample_alert):
        """Test successful email delivery."""
        mail.outbox = []
        
        result = AlertNotificationService._send_email_notification(
            sample_alert,
            ['supervisor@example.com', 'manager@example.com']
        )
        
        assert result.success is True
        assert result.channel == 'email'
        assert result.latency_ms > 0
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject.startswith('[CRITICAL]')
        assert len(mail.outbox[0].to) == 2

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='alerts@intelliwiz.com'
    )
    def test_email_content_includes_location(self, sample_alert):
        """Test email includes location information."""
        mail.outbox = []
        
        AlertNotificationService._send_email_notification(
            sample_alert,
            ['test@example.com']
        )
        
        email_body = mail.outbox[0].body
        assert 'Latitude' in email_body
        assert 'Longitude' in email_body
        assert 'openstreetmap.org' in email_body

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_failure_handling(self, sample_alert):
        """Test email delivery failure handling."""
        with patch('apps.mqtt.services.alert_notification_service.send_mail') as mock_send:
            from smtplib import SMTPException
            mock_send.side_effect = SMTPException("SMTP server unavailable")
            
            result = AlertNotificationService._send_email_notification(
                sample_alert,
                ['test@example.com']
            )
            
            assert result.success is False
            assert result.error_message is not None

    def test_format_email_message(self, sample_alert):
        """Test email message formatting."""
        message = AlertNotificationService._format_email_message(sample_alert)
        
        assert sample_alert.alert_type in message
        assert sample_alert.severity in message
        assert sample_alert.source_id in message
        assert sample_alert.message in message
        assert 'Action Required' in message


class TestPushNotifications:
    """Test push notification delivery via FCM."""

    @override_settings(FCM_SERVER_KEY='test_server_key')
    @patch('apps.mqtt.services.alert_notification_service.requests.post')
    def test_send_push_success(self, mock_post, sample_alert):
        """Test successful push notification delivery."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message_id': 'msg_123'}
        mock_post.return_value = mock_response
        
        results = AlertNotificationService._send_push_notifications(
            sample_alert,
            ['fcm_token_123']
        )
        
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].channel == 'push'
        assert results[0].external_id == 'msg_123'

    @override_settings(FCM_SERVER_KEY=None)
    def test_push_not_configured(self, sample_alert):
        """Test push when FCM not configured."""
        results = AlertNotificationService._send_push_notifications(
            sample_alert,
            ['fcm_token_123']
        )
        
        assert len(results) == 1
        assert results[0].success is False
        assert 'not configured' in results[0].error_message

    @override_settings(FCM_SERVER_KEY='test_server_key')
    @patch('apps.mqtt.services.alert_notification_service.requests.post')
    def test_push_network_failure(self, mock_post, sample_alert):
        """Test push notification network failure."""
        from requests.exceptions import Timeout
        mock_post.side_effect = Timeout("Request timed out")
        
        results = AlertNotificationService._send_push_notifications(
            sample_alert,
            ['fcm_token_123']
        )
        
        assert len(results) == 1
        assert results[0].success is False

    @override_settings(FCM_SERVER_KEY='test_server_key')
    @patch('apps.mqtt.services.alert_notification_service.requests.post')
    def test_push_critical_priority(self, mock_post, sample_alert):
        """Test critical alerts send with high priority."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message_id': 'msg_123'}
        mock_post.return_value = mock_response
        
        AlertNotificationService._send_push_notifications(
            sample_alert,
            ['fcm_token_123']
        )
        
        # Verify FCM request had high priority
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['priority'] == 'high'


class TestRateLimiting:
    """Test rate limiting mechanisms."""

    def test_rate_limit_per_phone_number(self):
        """Test rate limiting is per phone number."""
        phone1 = '+919876543210'
        phone2 = '+918765432109'
        
        # Exhaust limit for phone1
        for _ in range(10):
            AlertNotificationService._check_sms_rate_limit(phone1)
        
        # phone1 should be limited
        assert AlertNotificationService._check_sms_rate_limit(phone1) is False
        
        # phone2 should still work
        assert AlertNotificationService._check_sms_rate_limit(phone2) is True

    def test_rate_limit_resets_after_timeout(self):
        """Test rate limit resets after cache timeout."""
        phone = '+919876543210'
        
        # Use short timeout for testing
        with patch.object(cache, 'set') as mock_set:
            AlertNotificationService._check_sms_rate_limit(phone)
            
            # Verify cache timeout is set correctly
            mock_set.assert_called()
            call_args = mock_set.call_args
            assert call_args[1]['timeout'] == 60  # SECONDS_IN_MINUTE


class TestIntegration:
    """Integration tests for full notification flow."""

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='alerts@intelliwiz.com',
        TWILIO_ACCOUNT_SID=None,
        FCM_SERVER_KEY=None
    )
    def test_full_notification_flow_email_only(self, sample_alert, recipients):
        """Test complete notification flow when only email configured."""
        mail.outbox = []
        
        results = AlertNotificationService.notify_alert(sample_alert, recipients)
        
        # Should have 1 email result (SMS and push skipped due to config)
        email_results = [r for r in results if r.channel == 'email']
        assert len(email_results) == 1
        assert email_results[0].success is True
        assert len(mail.outbox) == 1

    def test_notification_result_dataclass(self):
        """Test NotificationResult data structure."""
        result = NotificationResult(
            channel='sms',
            success=True,
            latency_ms=250.5,
            error_message=None,
            external_id='SM123'
        )
        
        assert result.channel == 'sms'
        assert result.success is True
        assert result.latency_ms == 250.5
        assert result.external_id == 'SM123'

    def test_alert_notification_dataclass(self):
        """Test AlertNotification data structure."""
        alert = AlertNotification(
            alert_id=999,
            alert_type="TEST_ALERT",
            severity="LOW",
            message="Test message",
            source_id="TEST-001",
            timestamp=datetime.now(dt_timezone.utc)
        )
        
        assert alert.alert_id == 999
        assert alert.severity == "LOW"
        assert alert.location is None
        assert alert.metadata is None
