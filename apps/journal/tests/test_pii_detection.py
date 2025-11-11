"""
Tests for PII Detection Service

Tests for:
- PII pattern detection
- Log sanitization (GDPR compliance)
- Crisis detection safety
"""
import pytest
import logging
from apps.journal.services.pii_detection_service import PIIDetectionScanner


@pytest.mark.django_db
@pytest.mark.security
class TestPIILoggingSanitization:

    def test_pii_detection_logs_do_not_contain_context(self, caplog, test_journal_entry):
        """Test PII detection logging excludes context snippets."""
        # Entry with SSN
        test_journal_entry.content = "My SSN is 123-45-6789 and I'm worried"
        test_journal_entry.save()

        scanner = PIIDetectionScanner()

        with caplog.at_level(logging.WARNING):
            result = scanner.scan_journal_entry(test_journal_entry)

        # Verify PII was detected
        assert result['has_pii'] is True
        assert result['pii_count'] > 0

        # Verify logs don't contain PII context
        log_output = caplog.text
        assert '123-45-6789' not in log_output, "PII should not be in logs"
        assert '[REDACTED]' not in log_output, "Context snippets should not be logged"

        # Verify safe metadata IS logged (check the actual log record extra field)
        assert len(caplog.records) > 0, "At least one log record should be created"
        warning_record = caplog.records[-1]  # Get the warning record from PII detection
        assert hasattr(warning_record, 'pii_count'), "pii_count should be in extra fields"
        assert warning_record.pii_count > 0
        assert hasattr(warning_record, 'pii_types_summary'), "pii_types_summary should be in extra"

    def test_pii_types_summary_safe_to_log(self, test_journal_entry):
        """Test PII type summary doesn't include context."""
        test_journal_entry.content = "Call me at 555-123-4567"
        test_journal_entry.save()

        scanner = PIIDetectionScanner()
        result = scanner.scan_journal_entry(test_journal_entry)

        # Get safe summary for logging
        safe_summary = scanner._get_safe_pii_summary(result['pii_found'])

        # Safe summary should only include type and severity
        for item in safe_summary:
            assert 'type' in item
            assert 'severity' in item
            assert 'context' not in item, "Context should be excluded from safe summary"
            assert 'match' not in item, "Match text should be excluded"
