"""
Comprehensive Tests for Logging Security Framework.

Tests all logging security components:
- Log rotation monitoring
- Log access auditing
- Real-time security scanning
- PII detection in user content
- Compliance reporting
- Integration with sanitization middleware

CRITICAL: Validates Rule #15 - Logging Data Sanitization compliance.
"""

import os
import logging
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.services.log_rotation_monitoring_service import (
    LogRotationMonitoringService,
    LogFileStatus,
    LogRotationAlert
)
from apps.core.services.log_access_auditing_service import (
    LogAccessAuditingService,
    LogAccessOperation,
    LogAccessAuditEntry
)
from apps.core.services.realtime_log_scanner_service import (
    RealtimeLogScannerService,
    SecurityViolationType
)
from apps.core.services.pii_detection_service import (
    PIIDetectionService,
    PIIType
)
from apps.core.services.logging_compliance_service import (
    LoggingComplianceService,
    ComplianceFramework
)

User = get_user_model()


@pytest.mark.security
class LogRotationMonitoringServiceTest(TestCase):
    """Tests for log rotation monitoring."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = LogRotationMonitoringService()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_log_file_size_detection(self):
        """Test detection of oversized log files."""
        test_log = os.path.join(self.temp_dir, 'test.log')

        with open(test_log, 'w') as f:
            f.write('x' * (150 * 1024 * 1024))

        status = self.service._get_file_status(test_log)

        self.assertIsNotNone(status)
        self.assertTrue(status.exceeds_threshold)
        self.assertGreater(status.size_mb, 100)

    def test_old_file_detection(self):
        """Test detection of files exceeding retention policy."""
        test_log = os.path.join(self.temp_dir, 'old.log')

        with open(test_log, 'w') as f:
            f.write('test data')

        old_time = (datetime.now() - timedelta(days=95)).timestamp()
        os.utime(test_log, (old_time, old_time))

        status = self.service._get_file_status(test_log)

        self.assertIsNotNone(status)
        self.assertTrue(status.should_rotate)
        self.assertGreater(status.age_days, 90)

    @patch('apps.core.services.log_rotation_monitoring_service.send_mail')
    def test_alert_generation(self, mock_send_mail):
        """Test alert generation for threshold violations."""
        test_log = os.path.join(self.temp_dir, 'large.log')

        with open(test_log, 'w') as f:
            f.write('x' * (200 * 1024 * 1024))

        with patch.object(self.service, 'log_dirs', [self.temp_dir]):
            result = self.service.check_log_rotation_status()

        self.assertEqual(result['status'], 'warning')
        self.assertGreater(result['alerts_generated'], 0)
        self.assertTrue(mock_send_mail.called)

    def test_cleanup_dry_run(self):
        """Test dry run mode doesn't delete files."""
        test_log = os.path.join(self.temp_dir, 'old.log')

        with open(test_log, 'w') as f:
            f.write('test data')

        old_time = (datetime.now() - timedelta(days=95)).timestamp()
        os.utime(test_log, (old_time, old_time))

        with patch.object(self.service, 'log_dirs', [self.temp_dir]):
            result = self.service.cleanup_old_logs(dry_run=True)

        self.assertTrue(os.path.exists(test_log))
        self.assertEqual(result['files_deleted'], 0)
        self.assertGreater(result['files_identified'], 0)

    def test_cleanup_actual_deletion(self):
        """Test actual file deletion in cleanup."""
        test_log = os.path.join(self.temp_dir, 'old.log')

        with open(test_log, 'w') as f:
            f.write('test data')

        old_time = (datetime.now() - timedelta(days=95)).timestamp()
        os.utime(test_log, (old_time, old_time))

        with patch.object(self.service, 'log_dirs', [self.temp_dir]):
            result = self.service.cleanup_old_logs(dry_run=False)

        self.assertFalse(os.path.exists(test_log))
        self.assertGreater(result['files_deleted'], 0)


@pytest.mark.security
class LogAccessAuditingServiceTest(TestCase):
    """Tests for log access auditing."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = LogAccessAuditingService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

    def test_superuser_has_access_to_all_logs(self):
        """Test superuser can access all log types."""
        for log_type in ['security_logs', 'application_logs', 'error_logs', 'audit_logs']:
            has_access = self.service.validate_log_access(
                self.superuser,
                log_type,
                LogAccessOperation.READ
            )
            self.assertTrue(has_access)

    def test_regular_user_denied_security_logs(self):
        """Test regular user cannot access security logs."""
        with self.assertRaises(Exception):
            self.service.validate_log_access(
                self.user,
                'security_logs',
                LogAccessOperation.READ
            )

    def test_audit_trail_recording(self):
        """Test audit trail is properly recorded."""
        try:
            self.service.validate_log_access(
                self.superuser,
                'application_logs',
                LogAccessOperation.READ
            )
        except:
            pass

        audit_trail = self.service.get_access_audit_trail(
            user_id=self.superuser.id,
            start_date=timezone.now() - timedelta(hours=1)
        )

        self.assertGreater(len(audit_trail), 0)
        self.assertEqual(audit_trail[0]['user_id'], self.superuser.id)

    def test_unauthorized_access_alerting(self):
        """Test unauthorized access attempts trigger alerts."""
        with self.assertLogs('apps.core.services.log_access_auditing_service', level='WARNING'):
            with self.assertRaises(Exception):
                self.service.validate_log_access(
                    self.user,
                    'security_logs',
                    LogAccessOperation.DELETE
                )


@pytest.mark.security
class RealtimeLogScannerServiceTest(TestCase):
    """Tests for real-time log security scanning."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = RealtimeLogScannerService()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_password_detection_in_logs(self):
        """Test detection of passwords in log files."""
        test_log = os.path.join(self.temp_dir, 'test.log')

        with open(test_log, 'w') as f:
            f.write('INFO: User login\n')
            f.write('ERROR: Authentication failed for user with password: secret123\n')
            f.write('INFO: Normal log entry\n')

        result = self.service.scan_log_file(test_log, max_lines=10)

        self.assertGreater(result['violations_found'], 0)
        self.assertIn('password', result['violation_types'])

    def test_email_detection_in_logs(self):
        """Test detection of email addresses in log files."""
        test_log = os.path.join(self.temp_dir, 'test.log')

        with open(test_log, 'w') as f:
            f.write('INFO: Sending email to user@example.com\n')
            f.write('INFO: Email sent to admin@test.org\n')

        result = self.service.scan_log_file(test_log, max_lines=10)

        self.assertGreater(result['violations_found'], 0)
        self.assertIn('email', result['violation_types'])

    def test_credit_card_detection_in_logs(self):
        """Test detection of credit card numbers in log files."""
        test_log = os.path.join(self.temp_dir, 'test.log')

        with open(test_log, 'w') as f:
            f.write('INFO: Processing payment\n')
            f.write('DEBUG: Card number: 4111111111111111\n')

        result = self.service.scan_log_file(test_log, max_lines=10)

        self.assertGreater(result['violations_found'], 0)
        self.assertIn('credit_card', result['violation_types'])

    @patch('apps.core.services.realtime_log_scanner_service.send_mail')
    def test_critical_violation_alerts(self, mock_send_mail):
        """Test critical violations trigger immediate alerts."""
        test_log = os.path.join(self.temp_dir, 'test.log')

        with open(test_log, 'w') as f:
            f.write('ERROR: Authentication with token: sk_live_1234567890abcdef\n')

        result = self.service.scan_log_file(test_log, max_lines=10)

        self.assertGreater(result['violations_found'], 0)
        self.assertTrue(mock_send_mail.called)

    def test_violation_summary_generation(self):
        """Test violation summary aggregation."""
        test_log = os.path.join(self.temp_dir, 'test.log')

        with open(test_log, 'w') as f:
            f.write('ERROR: password: secret123\n')
            f.write('ERROR: token: abc123xyz\n')
            f.write('INFO: email: user@test.com\n')

        self.service.scan_log_file(test_log, max_lines=10)

        summary = self.service.get_violation_summary(hours=1)

        self.assertGreater(summary['total_violations'], 0)
        self.assertIn('violations_by_type', summary)
        self.assertIn('violations_by_severity', summary)


@pytest.mark.security
class PIIDetectionServiceTest(TestCase):
    """Tests for PII detection in user content."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = PIIDetectionService()

    def test_email_detection_in_content(self):
        """Test email detection in user-generated content."""
        content = "Please contact me at user@example.com for more details"

        result = self.service.detect_pii(content)

        self.assertTrue(result.contains_pii)
        self.assertIn('email', result.pii_types_found)
        self.assertGreater(result.pii_count, 0)

    def test_phone_detection_in_content(self):
        """Test phone number detection."""
        content = "Call me at (555) 123-4567 tomorrow"

        result = self.service.detect_pii(content)

        self.assertTrue(result.contains_pii)
        self.assertIn('phone', result.pii_types_found)

    def test_ssn_detection_in_content(self):
        """Test SSN detection."""
        content = "My SSN is 123-45-6789"

        result = self.service.detect_pii(content)

        self.assertTrue(result.contains_pii)
        self.assertIn('ssn', result.pii_types_found)

    def test_credit_card_detection_in_content(self):
        """Test credit card detection."""
        content = "Card number 4111111111111111 for payment"

        result = self.service.detect_pii(content)

        self.assertTrue(result.contains_pii)
        self.assertIn('credit_card', result.pii_types_found)

    def test_pii_sanitization(self):
        """Test PII sanitization in content."""
        content = "Email user@example.com and call (555) 123-4567"

        result = self.service.detect_pii(content, sanitize=True)

        self.assertTrue(result.contains_pii)
        self.assertIsNotNone(result.sanitized_content)
        self.assertNotIn('user@example.com', result.sanitized_content)
        self.assertNotIn('(555) 123-4567', result.sanitized_content)
        self.assertIn('[SANITIZED]', result.sanitized_content)

    def test_safe_log_user_content(self):
        """Test safe logging of user content."""
        content = "My email is admin@example.com and phone is 555-1234"

        safe_content = self.service.safe_log_user_content(content)

        self.assertNotIn('admin@example.com', safe_content)
        self.assertNotIn('555-1234', safe_content)

    def test_content_truncation(self):
        """Test long content is truncated."""
        content = "x" * 500

        safe_content = self.service.safe_log_user_content(content, max_length=200)

        self.assertLessEqual(len(safe_content), 203)
        self.assertIn("...", safe_content)

    def test_analyze_dict_for_logging(self):
        """Test dictionary sanitization for logging."""
        content_dict = {
            'description': 'Email me at user@test.com',
            'notes': 'Call (555) 123-4567',
            'safe_field': 'This is safe content'
        }

        safe_dict = self.service.analyze_content_for_logging(content_dict)

        self.assertIn('[CONTAINS_PII', safe_dict['description'])
        self.assertIn('[CONTAINS_PII', safe_dict['notes'])
        self.assertEqual(safe_dict['safe_field'], 'This is safe content')


@pytest.mark.security
class LoggingComplianceServiceTest(TestCase):
    """Tests for compliance reporting."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = LoggingComplianceService()

    @patch('apps.core.services.realtime_log_scanner_service.RealtimeLogScannerService.get_violation_summary')
    def test_gdpr_report_generation(self, mock_scanner):
        """Test GDPR compliance report generation."""
        mock_scanner.return_value = {
            'total_violations': 0,
            'violations_by_type': {},
            'violations_by_severity': {}
        }

        report = self.service.generate_gdpr_report()

        self.assertEqual(report.framework, 'gdpr')
        self.assertGreaterEqual(report.compliance_score, 0)
        self.assertLessEqual(report.compliance_score, 100)
        self.assertIsInstance(report.violations, list)
        self.assertIsInstance(report.recommendations, list)

    @patch('apps.core.services.log_access_auditing_service.LogAccessAuditingService.get_access_audit_trail')
    def test_hipaa_report_generation(self, mock_audit):
        """Test HIPAA compliance report generation."""
        mock_audit.return_value = []

        report = self.service.generate_hipaa_report()

        self.assertEqual(report.framework, 'hipaa')
        self.assertGreaterEqual(report.compliance_score, 0)
        self.assertLessEqual(report.compliance_score, 100)

    def test_comprehensive_report_includes_all_frameworks(self):
        """Test comprehensive report covers all enabled frameworks."""
        with patch('apps.core.services.realtime_log_scanner_service.RealtimeLogScannerService.get_violation_summary') as mock_scanner, \
             patch('apps.core.services.log_access_auditing_service.LogAccessAuditingService.get_access_audit_trail') as mock_audit:

            mock_scanner.return_value = {'total_violations': 0, 'violations_by_type': {}, 'violations_by_severity': {}}
            mock_audit.return_value = []

            report = self.service.generate_comprehensive_report()

            self.assertIn('overall_compliance_score', report)
            self.assertIn('frameworks_checked', report)
            self.assertIn('reports', report)


@pytest.mark.security
class LoggingSecurityIntegrationTest(TestCase):
    """Integration tests for complete logging security framework."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_end_to_end_sanitization_flow(self):
        """Test complete sanitization flow from request to log."""
        request = self.factory.post('/api/test/', data={
            'email': 'user@example.com',
            'password': 'secret123'
        })
        request.user = self.user

        from apps.core.middleware.logging_sanitization import LogSanitizationMiddleware
        from apps.core.error_handling import CorrelationIDMiddleware

        correlation_middleware = CorrelationIDMiddleware()
        correlation_middleware.process_request(request)

        sanitization_middleware = LogSanitizationMiddleware()
        sanitization_middleware.process_request(request)

        self.assertTrue(hasattr(request, 'correlation_id'))
        self.assertTrue(hasattr(request, 'safe_user_ref'))
        self.assertNotIn('test@example.com', request.safe_user_ref)

    def test_pii_service_integration_with_logging(self):
        """Test PII service integrates with logging framework."""
        pii_service = PIIDetectionService()

        user_content = "My email is admin@test.com and SSN is 123-45-6789"

        safe_content = pii_service.safe_log_user_content(user_content)

        with self.assertLogs('apps.core.services.pii_detection_service', level='INFO'):
            logger_test = logging.getLogger('apps.core.services.pii_detection_service')
            logger_test.info(f"User content: {safe_content}")

    @patch('apps.core.services.log_rotation_monitoring_service.send_mail')
    def test_compliance_monitoring_integration(self, mock_send_mail):
        """Test compliance monitoring integrates with all services."""
        compliance_service = LoggingComplianceService()

        with patch('apps.core.services.realtime_log_scanner_service.RealtimeLogScannerService.get_violation_summary') as mock_scanner, \
             patch('apps.core.services.log_access_auditing_service.LogAccessAuditingService.get_access_audit_trail') as mock_audit:

            mock_scanner.return_value = {'total_violations': 0, 'violations_by_type': {}, 'violations_by_severity': {}}
            mock_audit.return_value = []

            report = compliance_service.generate_comprehensive_report()

            self.assertIn('overall_compliance_score', report)
            self.assertGreater(len(report['frameworks_checked']), 0)


@pytest.mark.security
class SanitizingFilterIntegrationTest(TestCase):
    """Tests for Django logging filter integration."""

    def test_filter_in_logging_configuration(self):
        """Test SanitizingFilter can be configured in Django logging."""
        from apps.core.middleware.logging_sanitization import SanitizingFilter

        test_filter = SanitizingFilter()
        self.assertIsNotNone(test_filter)

    def test_filter_sanitizes_log_records(self):
        """Test filter properly sanitizes LogRecord objects."""
        from apps.core.middleware.logging_sanitization import SanitizingFilter

        test_filter = SanitizingFilter()

        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg="User: user@example.com, Password: secret123",
            args=(),
            exc_info=None
        )

        result = test_filter.filter(record)

        self.assertTrue(result)
        self.assertIn('[SANITIZED]', record.msg)
        self.assertNotIn('user@example.com', record.msg)
        self.assertNotIn('secret123', record.msg)

    def test_filter_handles_errors_gracefully(self):
        """Test filter doesn't break logging on errors."""
        from apps.core.middleware.logging_sanitization import SanitizingFilter

        test_filter = SanitizingFilter()

        record = Mock(spec=logging.LogRecord)
        record.msg = Mock(side_effect=Exception("Test error"))

        result = test_filter.filter(record)

        self.assertTrue(result)