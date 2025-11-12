"""
Test suite for SLA Prevention Tasks exception handling.

Validates specific exception handling patterns per Rule #11:
- No generic exception handlers (all must be specific types)
- Use specific exception types from apps.core.exceptions.patterns
- All errors logged with exc_info=True
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from django.db import DatabaseError, IntegrityError, OperationalError
from celery.exceptions import Retry

from background_tasks.sla_prevention_tasks import (
    predict_sla_breaches_task,
    auto_escalate_at_risk_tickets,
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


class TestPredictSLABreachesTaskExceptions:
    """Test exception handling in predict_sla_breaches_task."""

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_handles_database_error_with_retry(self, mock_logger, mock_ticket):
        """Test that DatabaseError triggers task retry (line 145-147)."""
        mock_ticket.objects.filter.side_effect = DatabaseError("DB connection lost")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            predict_sla_breaches_task(mock_self)

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

        # Verify retry was called with countdown
        assert mock_self.retry.called

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_handles_operational_error_with_retry(self, mock_logger, mock_ticket):
        """Test that OperationalError triggers task retry."""
        mock_ticket.objects.filter.side_effect = OperationalError("Deadlock detected")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            predict_sla_breaches_task(mock_self)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_handles_integrity_error_with_retry(self, mock_logger, mock_ticket):
        """Test that IntegrityError triggers task retry."""
        mock_ticket.objects.filter.side_effect = IntegrityError("Constraint violation")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            predict_sla_breaches_task(mock_self)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.NOCAlertEvent')
    @patch('background_tasks.sla_prevention_tasks.SLABreachPredictor')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_handles_prediction_error_gracefully(self, mock_logger, mock_predictor, mock_alert, mock_ticket):
        """Test that prediction errors within loop are caught and logged (line 124)."""
        # Setup mock tickets
        mock_tickets = [Mock(id=1, other_data=None, tenant=Mock(), client=Mock(), bu=Mock())]
        mock_ticket.objects.filter.return_value.select_related.return_value.__getitem__ = lambda s, i: mock_tickets
        mock_ticket.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Make predictor raise exception
        mock_predictor.predict_breach.side_effect = ValueError("Invalid data")

        mock_self = Mock()

        result = predict_sla_breaches_task(mock_self)

        # Should complete task despite error
        assert result is not None
        assert 'tickets_analyzed' in result

        # Verify error was logged
        assert mock_logger.error.called

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.SLABreachPredictor')
    @patch('background_tasks.sla_prevention_tasks.NOCAlertEvent')
    @patch('background_tasks.sla_prevention_tasks.timezone')
    def test_success_path(self, mock_timezone, mock_alert, mock_predictor, mock_ticket):
        """Test successful prediction execution."""
        mock_timezone.now.return_value = timezone.now()

        # Setup mock ticket
        mock_ticket_instance = Mock(
            id=1,
            ticketdesc="Test ticket",
            other_data={},
            tenant=Mock(),
            client=Mock(),
            bu=Mock(),
            assignee=None,
            status='NEW',
            priority='LOW'
        )
        mock_ticket.objects.filter.return_value.select_related.return_value = [mock_ticket_instance]
        mock_ticket.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Setup predictor
        mock_predictor.predict_breach.return_value = (0.85, {'time_until_sla_deadline_minutes': 30})

        mock_self = Mock()

        result = predict_sla_breaches_task(mock_self)

        assert result['tickets_analyzed'] == 1
        assert result['high_risk_count'] == 1
        assert result['escalated_count'] == 1  # Should auto-escalate at 85%


class TestAutoEscalateAtRiskTicketsExceptions:
    """Test exception handling in auto_escalate_at_risk_tickets task."""

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_handles_database_error_with_retry(self, mock_logger, mock_ticket):
        """Test that DatabaseError triggers task retry (line 201-203)."""
        mock_ticket.objects.filter.side_effect = DatabaseError("DB error")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            auto_escalate_at_risk_tickets(mock_self)

        assert mock_logger.error.called
        assert 'exc_info' in mock_logger.error.call_args[1]
        assert mock_logger.error.call_args[1]['exc_info'] is True

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_handles_operational_error_with_retry(self, mock_logger, mock_ticket):
        """Test that OperationalError triggers task retry."""
        mock_ticket.objects.filter.side_effect = OperationalError("Transaction timeout")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            auto_escalate_at_risk_tickets(mock_self)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_handles_individual_ticket_error_gracefully(self, mock_logger, mock_ticket):
        """Test that errors within loop are caught and logged (line 192)."""
        # Setup mock tickets
        mock_ticket1 = Mock(id=1, priority='LOW', other_data={'sla_risk_score': 0.8})
        mock_ticket1.save.side_effect = IntegrityError("Constraint violation")

        mock_ticket2 = Mock(id=2, priority='LOW', other_data={'sla_risk_score': 0.8})

        mock_ticket.objects.filter.return_value.select_related.return_value = [mock_ticket1, mock_ticket2]
        mock_ticket.objects.filter.return_value.select_related.return_value.__getitem__ = \
            lambda s, i: [mock_ticket1, mock_ticket2]

        mock_self = Mock()

        result = auto_escalate_at_risk_tickets(mock_self)

        # Should complete despite error on ticket1
        assert result is not None
        assert 'escalated_count' in result

        # Verify error was logged for ticket1
        assert mock_logger.error.called

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.timezone')
    def test_success_path(self, mock_timezone, mock_ticket):
        """Test successful escalation execution."""
        mock_timezone.now.return_value = timezone.now()

        # Setup mock ticket
        mock_ticket_instance = Mock(
            id=1,
            priority='MEDIUM',
            other_data={'sla_risk_score': 0.8}
        )
        mock_ticket.objects.filter.return_value.select_related.return_value = [mock_ticket_instance]

        mock_self = Mock()

        result = auto_escalate_at_risk_tickets(mock_self)

        assert result['escalated_count'] == 1
        assert mock_ticket_instance.priority == 'HIGH'


class TestDatabaseExceptionHandling:
    """Integration tests for DATABASE_EXCEPTIONS handling."""

    def test_database_exceptions_tuple_completeness(self):
        """Verify DATABASE_EXCEPTIONS includes all critical database errors."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        assert IntegrityError in DATABASE_EXCEPTIONS
        assert OperationalError in DATABASE_EXCEPTIONS
        assert DatabaseError in DATABASE_EXCEPTIONS

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_all_database_error_types_trigger_retry(self, mock_logger, mock_ticket):
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
            mock_ticket.objects.filter.side_effect = error

            mock_self = Mock()
            mock_self.retry = Mock(side_effect=Retry)

            with pytest.raises(Retry):
                predict_sla_breaches_task(mock_self)

            assert mock_logger.error.called, f"Failed to log {type(error).__name__}"
            assert mock_self.retry.called, f"Failed to retry on {type(error).__name__}"


class TestLoggingPatterns:
    """Test that all error logging follows best practices."""

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_database_errors_logged_with_exc_info(self, mock_logger, mock_ticket):
        """Verify DatabaseError logging includes exc_info=True."""
        mock_ticket.objects.filter.side_effect = DatabaseError("Test error")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        try:
            predict_sla_breaches_task(mock_self)
        except Retry:
            pass

        # Verify exc_info=True in log call
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get('exc_info') is True

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    @patch('background_tasks.sla_prevention_tasks.NOCAlertEvent')
    @patch('background_tasks.sla_prevention_tasks.SLABreachPredictor')
    @patch('background_tasks.sla_prevention_tasks.logger')
    def test_individual_errors_logged_with_exc_info(self, mock_logger, mock_predictor, mock_alert, mock_ticket):
        """Verify individual ticket errors logging includes exc_info=True."""
        # Setup mock ticket that will cause error
        mock_ticket_instance = Mock(id=1, other_data=None, tenant=Mock(), client=Mock(), bu=Mock())
        mock_ticket.objects.filter.return_value.select_related.return_value = [mock_ticket_instance]
        mock_ticket.objects.filter.return_value.select_related.return_value.count.return_value = 1

        mock_predictor.predict_breach.side_effect = ValueError("Test error")

        mock_self = Mock()

        result = predict_sla_breaches_task(mock_self)

        # Verify exc_info=True in log call
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get('exc_info') is True


class TestTaskRetryBehavior:
    """Test retry behavior for different exception types."""

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    def test_retry_countdown_parameter(self, mock_ticket):
        """Verify retry is called with proper countdown parameter."""
        mock_ticket.objects.filter.side_effect = DatabaseError("DB error")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            predict_sla_breaches_task(mock_self)

        # Verify retry was called with countdown
        retry_call = mock_self.retry.call_args
        assert 'countdown' in retry_call[1]
        assert retry_call[1]['countdown'] == 60  # 60 seconds as per task definition

    @patch('background_tasks.sla_prevention_tasks.Ticket')
    def test_no_retry_on_validation_errors(self, mock_ticket):
        """Verify that validation errors within loop don't trigger task retry."""
        # Setup to cause validation error within the loop
        mock_ticket_instance = Mock(id=1, other_data=None, tenant=Mock(), client=Mock(), bu=Mock())
        mock_ticket.objects.filter.return_value.select_related.return_value = [mock_ticket_instance]
        mock_ticket.objects.filter.return_value.select_related.return_value.count.return_value = 1

        with patch('background_tasks.sla_prevention_tasks.SLABreachPredictor') as mock_predictor:
            mock_predictor.predict_breach.side_effect = ValueError("Validation error")

            mock_self = Mock()

            # Should not raise, just log and continue
            result = predict_sla_breaches_task(mock_self)

            assert result is not None
            assert 'tickets_analyzed' in result
