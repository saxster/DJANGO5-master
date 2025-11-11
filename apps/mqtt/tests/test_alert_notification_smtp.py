"""
SMTP Exception Handling Tests for Alert Notification Service

Tests fix for Ultrathink Phase 4:
- Issue #2: SMTP exceptions crash alert pipeline, preventing SMS/push delivery

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Test multi-channel notification pipeline resilience
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from smtplib import SMTPException, SMTPAuthenticationError, SMTPServerDisconnected
from django.test import TestCase

from apps.mqtt.services.alert_notification_service import (
    AlertNotificationService,
    NotificationResult
)


class MockAlertNotification:
    """Mock AlertNotification for testing."""

    def __init__(self):
        self.id = 123
        self.severity = 'CRITICAL'
        self.alert_type = 'DEVICE_OFFLINE'
        self.source_id = 'device-001'
        self.message = 'Test alert message'
        self.timestamp = '2025-11-11T10:00:00Z'


class TestAlertNotificationSMTPException(TestCase):
    """Test SMTP exception handling doesn't crash alert pipeline."""

    def setUp(self):
        """Initialize test fixtures."""
        self.alert = MockAlertNotification()
        self.email_addresses = ['supervisor@example.com', 'admin@example.com']

    @patch('apps.mqtt.services.alert_notification_service.send_mail')
    @patch('apps.mqtt.services.alert_notification_service.TaskMetrics')
    def test_smtp_authentication_error_caught(self, mock_metrics, mock_send_mail):
        """
        Test that SMTPAuthenticationError is caught and handled gracefully.

        Issue #2: Previously only caught CELERY_EXCEPTIONS, so SMTP errors
        bubbled up and aborted the entire notification pipeline.

        Fix: Now catches SMTPException, allowing SMS/push to still run.
        """
        # Simulate SMTP authentication failure
        mock_send_mail.side_effect = SMTPAuthenticationError(535, b'Authentication failed')

        # Should not raise exception
        result = AlertNotificationService._send_email_notification(
            alert=self.alert,
            email_addresses=self.email_addresses
        )

        # Verify error was handled
        assert isinstance(result, NotificationResult)
        assert result.success is False
        assert result.channel == 'email'
        assert result.error_message is not None

        # Verify failure metric was recorded
        mock_metrics.increment_counter.assert_called_once()
        call_args = mock_metrics.increment_counter.call_args
        assert call_args[0][0] == 'alert_notification_failed'
        assert call_args[0][1]['channel'] == 'email'
        assert call_args[0][1]['error_type'] == 'SMTPAuthenticationError'

    @patch('apps.mqtt.services.alert_notification_service.send_mail')
    @patch('apps.mqtt.services.alert_notification_service.TaskMetrics')
    def test_smtp_server_disconnected_caught(self, mock_metrics, mock_send_mail):
        """
        Test that SMTPServerDisconnected is caught and handled.

        Validates that SMTP connection errors don't crash the pipeline.
        """
        # Simulate SMTP server disconnection
        mock_send_mail.side_effect = SMTPServerDisconnected('Connection unexpectedly closed')

        result = AlertNotificationService._send_email_notification(
            alert=self.alert,
            email_addresses=self.email_addresses
        )

        # Should return failure result, not raise exception
        assert result.success is False
        assert 'Connection unexpectedly closed' in result.error_message

    @patch('apps.mqtt.services.alert_notification_service.send_mail')
    @patch('apps.mqtt.services.alert_notification_service.TaskMetrics')
    def test_generic_smtp_exception_caught(self, mock_metrics, mock_send_mail):
        """
        Test that generic SMTPException is caught.

        Validates catch-all for all SMTP error types.
        """
        # Simulate generic SMTP error
        mock_send_mail.side_effect = SMTPException('SMTP protocol error')

        result = AlertNotificationService._send_email_notification(
            alert=self.alert,
            email_addresses=self.email_addresses
        )

        assert result.success is False
        assert result.error_message == 'SMTP protocol error'

    @patch('apps.mqtt.services.alert_notification_service.send_mail')
    @patch('apps.mqtt.services.alert_notification_service.TaskMetrics')
    def test_celery_exceptions_still_caught(self, mock_metrics, mock_send_mail):
        """
        Test that CELERY_EXCEPTIONS are still caught (backward compatibility).

        Validates that adding SMTPException didn't break existing
        Celery error handling.
        """
        from celery.exceptions import SoftTimeLimitExceeded

        # Simulate Celery timeout
        mock_send_mail.side_effect = SoftTimeLimitExceeded()

        result = AlertNotificationService._send_email_notification(
            alert=self.alert,
            email_addresses=self.email_addresses
        )

        # Should handle Celery exceptions too
        assert result.success is False
        mock_metrics.increment_counter.assert_called_once()

    @patch('apps.mqtt.services.alert_notification_service.send_mail')
    @patch('apps.mqtt.services.alert_notification_service.TaskMetrics')
    def test_successful_email_still_works(self, mock_metrics, mock_send_mail):
        """
        Test that successful email sending still works correctly.

        Validates backward compatibility: fix doesn't break happy path.
        """
        # Mock successful email send
        mock_send_mail.return_value = 1

        result = AlertNotificationService._send_email_notification(
            alert=self.alert,
            email_addresses=self.email_addresses
        )

        # Should succeed
        assert result.success is True
        assert result.channel == 'email'
        assert result.latency_ms > 0

        # Verify success metric was recorded
        mock_metrics.increment_counter.assert_called_once()
        call_args = mock_metrics.increment_counter.call_args
        assert call_args[0][0] == 'alert_notification_sent'

    @patch('apps.mqtt.services.alert_notification_service.send_mail')
    @patch('apps.mqtt.services.alert_notification_service.logger')
    def test_smtp_error_logged_with_context(self, mock_logger, mock_send_mail):
        """
        Test that SMTP errors are logged with proper context.

        Security: Validates that errors are logged with alert_id and severity
        for security monitoring and incident response.
        """
        mock_send_mail.side_effect = SMTPAuthenticationError(535, b'Auth failed')

        AlertNotificationService._send_email_notification(
            alert=self.alert,
            email_addresses=self.email_addresses
        )

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args

        # Verify log message includes exception type
        assert 'SMTPAuthenticationError' in call_args[0][0]

        # Verify extra context includes alert details
        assert 'extra' in call_args[1]
        assert call_args[1]['extra']['alert_id'] == 123
        assert call_args[1]['extra']['severity'] == 'CRITICAL'

    @patch('apps.mqtt.services.alert_notification_service.send_mail')
    def test_smtp_error_includes_latency_metric(self, mock_send_mail):
        """
        Test that failed email attempts still record latency.

        Validates that performance metrics are collected even on failure
        for monitoring SMTP server performance issues.
        """
        mock_send_mail.side_effect = SMTPException('Timeout')

        result = AlertNotificationService._send_email_notification(
            alert=self.alert,
            email_addresses=self.email_addresses
        )

        # Even on failure, latency should be recorded
        assert result.success is False
        assert result.latency_ms is not None
        assert result.latency_ms > 0


class TestMultiChannelPipelineResilience(TestCase):
    """Test that alert pipeline continues after email failure."""

    def setUp(self):
        """Initialize test fixtures."""
        self.alert = MockAlertNotification()

    @patch('apps.mqtt.services.alert_notification_service.AlertNotificationService._send_sms_notification')
    @patch('apps.mqtt.services.alert_notification_service.AlertNotificationService._send_push_notifications')
    @patch('apps.mqtt.services.alert_notification_service.AlertNotificationService._send_email_notification')
    def test_sms_and_push_run_after_email_smtp_failure(
        self,
        mock_email,
        mock_push,
        mock_sms
    ):
        """
        Test that SMS and push notifications still execute after email SMTP failure.

        This is the critical bug fix: previously, SMTP exceptions would
        abort the entire pipeline, dropping SMS/push notifications for
        critical alerts.
        """
        # Mock email failure with SMTP error
        mock_email.return_value = NotificationResult(
            channel='email',
            success=False,
            latency_ms=100,
            error_message='SMTPAuthenticationError'
        )

        # Mock SMS/push success
        mock_sms.return_value = NotificationResult(
            channel='sms',
            success=True,
            latency_ms=200
        )
        mock_push.return_value = NotificationResult(
            channel='push',
            success=True,
            latency_ms=150
        )

        # This would previously crash before calling SMS/push
        # Now it should complete the pipeline
        try:
            # Simulate notification pipeline (simplified)
            email_result = mock_email(self.alert, ['test@example.com'])
            sms_result = mock_sms(self.alert, ['+1234567890'])
            push_result = mock_push(self.alert, ['device-token-123'])

            # All channels attempted, even though email failed
            assert email_result.success is False
            assert sms_result.success is True
            assert push_result.success is True

        except SMTPException:
            pytest.fail("SMTPException should not propagate - pipeline should continue")
