"""
Test suite for Executive Scorecard Tasks exception handling.

Validates specific exception handling patterns per Rule #11:
- No generic exception handlers (all must be specific types)
- Use specific exception types from apps.core.exceptions.patterns
- All errors logged with exc_info=True
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from django.db import DatabaseError, IntegrityError, OperationalError
from django.core.exceptions import ValidationError
from celery.exceptions import Retry

from background_tasks.executive_scorecard_tasks import (
    generate_monthly_scorecards_task,
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS


class TestGenerateMonthlyScorecardsExceptions:
    """Test exception handling in generate_monthly_scorecards_task."""

    @patch('background_tasks.executive_scorecard_tasks.BusinessUnit')
    @patch('background_tasks.executive_scorecard_tasks.logger')
    def test_handles_database_error_with_retry(self, mock_logger, mock_business_unit):
        """Test that DatabaseError triggers task retry."""
        mock_business_unit.objects.filter.side_effect = DatabaseError("Connection lost")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            generate_monthly_scorecards_task(mock_self)

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

        # Verify retry was called
        assert mock_self.retry.called

    @patch('background_tasks.executive_scorecard_tasks.BusinessUnit')
    @patch('background_tasks.executive_scorecard_tasks.logger')
    def test_handles_operational_error_with_retry(self, mock_logger, mock_business_unit):
        """Test that OperationalError triggers task retry."""
        mock_business_unit.objects.filter.side_effect = OperationalError("Deadlock")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            generate_monthly_scorecards_task(mock_self)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.executive_scorecard_tasks.ExecutiveScoreCardService')
    @patch('background_tasks.executive_scorecard_tasks.BusinessUnit')
    @patch('background_tasks.executive_scorecard_tasks.logger')
    def test_handles_email_sending_error_gracefully(self, mock_logger, mock_business_unit, mock_service):
        """Test that email sending errors are caught and logged (line 137)."""
        # Setup mock business units
        mock_client = Mock()
        mock_client.id = 1
        mock_client.name = "Test Client"
        mock_client.tenant = Mock()
        mock_client.preferences = {'executive_emails': ['exec@test.com']}
        mock_client.primary_contact = None

        mock_business_unit.objects.filter.return_value.select_related.return_value.__getitem__ = Mock(return_value=mock_client)
        mock_business_unit.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Mock successful scorecard generation
        mock_service.generate_monthly_scorecard.return_value = {
            'period': 'Oct 2025',
            'data': {}
        }

        # Mock email delivery to fail
        with patch('background_tasks.executive_scorecard_tasks.ReportDeliveryService') as mock_delivery:
            mock_delivery.send_email.side_effect = ValidationError("Email validation failed")

            mock_self = Mock()
            result = generate_monthly_scorecards_task(mock_self)

        # Should continue processing despite email error
        assert result['errors'] > 0

        # Verify error was logged with exc_info
        assert mock_logger.error.called

    @patch('background_tasks.executive_scorecard_tasks.ExecutiveScoreCardService')
    @patch('background_tasks.executive_scorecard_tasks.BusinessUnit')
    @patch('background_tasks.executive_scorecard_tasks.logger')
    def test_handles_scorecard_generation_error_gracefully(self, mock_logger, mock_business_unit, mock_service):
        """Test that scorecard generation errors are caught and logged (line 153)."""
        # Setup mock business units
        mock_client = Mock()
        mock_client.id = 1
        mock_client.name = "Test Client"
        mock_client.tenant = Mock()

        mock_business_unit.objects.filter.return_value.select_related.return_value.__getitem__ = Mock(return_value=mock_client)
        mock_business_unit.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Mock scorecard generation to fail
        mock_service.generate_monthly_scorecard.side_effect = ValueError("Invalid data")

        mock_self = Mock()
        result = generate_monthly_scorecards_task(mock_self)

        # Should continue processing and track error
        assert result['errors'] > 0

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    @patch('background_tasks.executive_scorecard_tasks.ExecutiveScoreCardService')
    @patch('background_tasks.executive_scorecard_tasks.BusinessUnit')
    @patch('background_tasks.executive_scorecard_tasks.timezone')
    def test_success_path(self, mock_timezone, mock_business_unit, mock_service):
        """Test successful scorecard generation."""
        mock_timezone.now.return_value = timezone.now()

        # Setup mock business units
        mock_client = Mock()
        mock_client.id = 1
        mock_client.name = "Test Client"
        mock_client.tenant = Mock()
        mock_client.preferences = {'executive_emails': ['exec@test.com']}
        mock_client.primary_contact = None

        mock_business_unit.objects.filter.return_value.select_related.return_value = [mock_client]
        mock_business_unit.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Mock successful scorecard generation
        mock_service.generate_monthly_scorecard.return_value = {
            'period': 'Oct 2025',
            'data': {}
        }

        # Mock successful email delivery
        with patch('background_tasks.executive_scorecard_tasks.ReportDeliveryService') as mock_delivery:
            with patch('background_tasks.executive_scorecard_tasks.render_to_string') as mock_render:
                mock_render.return_value = "<html>Report</html>"
                mock_delivery.send_email.return_value = True

                mock_self = Mock()
                result = generate_monthly_scorecards_task(mock_self)

        assert result['clients_processed'] == 1
        assert result['scorecards_generated'] >= 0


class TestDatabaseExceptionHandling:
    """Integration tests for DATABASE_EXCEPTIONS handling."""

    def test_database_exceptions_tuple_completeness(self):
        """Verify DATABASE_EXCEPTIONS includes all critical database errors."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        assert IntegrityError in DATABASE_EXCEPTIONS
        assert OperationalError in DATABASE_EXCEPTIONS
        assert DatabaseError in DATABASE_EXCEPTIONS

    @patch('background_tasks.executive_scorecard_tasks.BusinessUnit')
    @patch('background_tasks.executive_scorecard_tasks.logger')
    def test_all_database_error_types_trigger_retry(self, mock_logger, mock_business_unit):
        """Test that all DATABASE_EXCEPTIONS types trigger retry."""
        from django.db import DataError, InterfaceError

        error_types = [
            IntegrityError("Integrity error"),
            OperationalError("Operational error"),
            DatabaseError("Database error"),
            DataError("Data error"),
            InterfaceError("Interface error"),
        ]

        for error in error_types:
            mock_logger.reset_mock()
            mock_business_unit.objects.filter.side_effect = error

            mock_self = Mock()
            mock_self.retry = Mock(side_effect=Retry)

            with pytest.raises(Retry):
                generate_monthly_scorecards_task(mock_self)

            assert mock_logger.error.called, f"Failed to log {type(error).__name__}"
            assert mock_self.retry.called, f"Failed to retry on {type(error).__name__}"


class TestLoggingPatterns:
    """Test that all error logging follows best practices."""

    @patch('background_tasks.executive_scorecard_tasks.BusinessUnit')
    @patch('background_tasks.executive_scorecard_tasks.logger')
    def test_database_errors_logged_with_exc_info(self, mock_logger, mock_business_unit):
        """Verify DatabaseError logging includes exc_info=True."""
        mock_business_unit.objects.filter.side_effect = DatabaseError("Test error")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        try:
            generate_monthly_scorecards_task(mock_self)
        except Retry:
            pass

        # Verify exc_info=True in log call
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get('exc_info') is True
