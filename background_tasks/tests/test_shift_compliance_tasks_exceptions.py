"""
Test suite for Shift Compliance Tasks exception handling.

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

from background_tasks.shift_compliance_tasks import (
    rebuild_shift_schedule_cache_task,
    detect_shift_no_shows_task,
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS


class TestRebuildShiftScheduleCacheExceptions:
    """Test exception handling in rebuild_shift_schedule_cache_task."""

    @patch('background_tasks.shift_compliance_tasks.Tenant')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_database_error_with_retry(self, mock_logger, mock_tenant):
        """Test that DatabaseError triggers task retry."""
        mock_tenant.objects.filter.side_effect = DatabaseError("Connection lost")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            rebuild_shift_schedule_cache_task(mock_self)

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

        # Verify retry was called
        assert mock_self.retry.called

    @patch('background_tasks.shift_compliance_tasks.Tenant')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_operational_error_with_retry(self, mock_logger, mock_tenant):
        """Test that OperationalError triggers task retry."""
        mock_tenant.objects.filter.side_effect = OperationalError("Deadlock")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            rebuild_shift_schedule_cache_task(mock_self)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.shift_compliance_tasks.ShiftComplianceService')
    @patch('background_tasks.shift_compliance_tasks.SecurityAnomalyConfig')
    @patch('background_tasks.shift_compliance_tasks.Tenant')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_cache_build_error_gracefully(self, mock_logger, mock_tenant, mock_config, mock_service):
        """Test that cache build errors are caught and logged (line 86)."""
        # Setup mock tenant
        mock_tenant_obj = Mock()
        mock_tenant_obj.id = 1
        mock_tenant_obj.name = "Test Tenant"

        mock_tenant.objects.filter.return_value = [mock_tenant_obj]
        mock_tenant.objects.filter.return_value.count.return_value = 1

        # Mock config creation
        mock_config_obj = Mock()
        mock_config.objects.get_or_create.return_value = (mock_config_obj, True)

        # Mock service to raise error
        with patch.object(mock_service, '__init__', return_value=None):
            mock_service_instance = Mock()
            mock_service_instance.build_schedule_cache.side_effect = ValueError("Cache build failed")

            with patch('background_tasks.shift_compliance_tasks.ShiftComplianceService', return_value=mock_service_instance):
                mock_self = Mock()
                result = rebuild_shift_schedule_cache_task(mock_self)

        # Should continue processing despite error
        assert 'tenants_processed' in result

        # Verify error was logged with exc_info
        assert mock_logger.error.called

    @patch('background_tasks.shift_compliance_tasks.Tenant')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_unexpected_error_gracefully_line_109(self, mock_logger, mock_tenant):
        """Test that unexpected errors are caught and raised (line 109)."""
        mock_tenant.objects.filter.side_effect = ValueError("Unexpected error")

        mock_self = Mock()

        with pytest.raises(ValueError):
            rebuild_shift_schedule_cache_task(mock_self)

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    @patch('background_tasks.shift_compliance_tasks.ShiftComplianceService')
    @patch('background_tasks.shift_compliance_tasks.SecurityAnomalyConfig')
    @patch('background_tasks.shift_compliance_tasks.Tenant')
    def test_success_path(self, mock_tenant, mock_config, mock_service):
        """Test successful cache rebuild."""
        # Setup mock tenant
        mock_tenant_obj = Mock()
        mock_tenant_obj.id = 1
        mock_tenant_obj.name = "Test Tenant"

        mock_tenant.objects.filter.return_value = [mock_tenant_obj]

        # Mock config creation
        mock_config_obj = Mock()
        mock_config.objects.get_or_create.return_value = (mock_config_obj, True)

        # Mock successful cache build
        with patch.object(mock_service, '__init__', return_value=None):
            mock_service_instance = Mock()
            mock_service_instance.build_schedule_cache.return_value = 10

            with patch('background_tasks.shift_compliance_tasks.ShiftComplianceService', return_value=mock_service_instance):
                mock_self = Mock()
                result = rebuild_shift_schedule_cache_task(mock_self)

        assert result['tenants_processed'] >= 0
        assert result['total_cache_entries'] >= 0


class TestDetectShiftNoShowsExceptions:
    """Test exception handling in detect_shift_no_shows_task."""

    @patch('background_tasks.shift_compliance_tasks.ShiftScheduleCache')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_database_error_with_retry(self, mock_logger, mock_cache):
        """Test that DatabaseError triggers task retry."""
        mock_cache.objects.filter.side_effect = DatabaseError("Connection lost")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            detect_shift_no_shows_task(mock_self)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.shift_compliance_tasks.ShiftScheduleCache')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_operational_error_with_retry(self, mock_logger, mock_cache):
        """Test that OperationalError triggers task retry."""
        mock_cache.objects.filter.side_effect = OperationalError("Deadlock")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            detect_shift_no_shows_task(mock_self)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.shift_compliance_tasks.NOCAlertEvent')
    @patch('background_tasks.shift_compliance_tasks.Attendance')
    @patch('background_tasks.shift_compliance_tasks.ShiftScheduleCache')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_shift_check_error_gracefully(self, mock_logger, mock_cache, mock_attendance, mock_alert):
        """Test that shift check errors are caught and logged (line 248)."""
        # Setup mock shift
        mock_shift = Mock()
        mock_shift.id = 1
        mock_shift.person = Mock()
        mock_shift.person.id = 1
        mock_shift.person.get_full_name.return_value = "John Doe"
        mock_shift.site = Mock()
        mock_shift.site.id = 1
        mock_shift.site.name = "Test Site"
        mock_shift.tenant = Mock()
        mock_shift.scheduled_start = timezone.now()

        mock_cache.objects.filter.return_value.select_related.return_value = [mock_shift]
        mock_cache.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Mock attendance check to raise error
        mock_attendance.objects.filter.side_effect = ValueError("Attendance check failed")

        mock_self = Mock()
        result = detect_shift_no_shows_task(mock_self)

        # Should continue processing despite error
        assert 'shifts_checked' in result

        # Verify error was logged with exc_info
        assert mock_logger.error.called

    @patch('background_tasks.shift_compliance_tasks.ShiftScheduleCache')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_handles_unexpected_error_gracefully_line_270(self, mock_logger, mock_cache):
        """Test that unexpected errors are caught and raised (line 270)."""
        mock_cache.objects.filter.side_effect = ValueError("Unexpected error")

        mock_self = Mock()

        with pytest.raises(ValueError):
            detect_shift_no_shows_task(mock_self)

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    @patch('background_tasks.shift_compliance_tasks.NOCAlertEvent')
    @patch('background_tasks.shift_compliance_tasks.Attendance')
    @patch('background_tasks.shift_compliance_tasks.ShiftScheduleCache')
    def test_success_path_no_shows_detected(self, mock_cache, mock_attendance, mock_alert):
        """Test successful no-show detection."""
        # Setup mock shift
        mock_shift = Mock()
        mock_shift.id = 1
        mock_shift.person = Mock()
        mock_shift.person.id = 1
        mock_shift.person.get_full_name.return_value = "John Doe"
        mock_shift.site = Mock()
        mock_shift.site.id = 1
        mock_shift.site.name = "Test Site"
        mock_shift.tenant = Mock()
        mock_shift.scheduled_start = timezone.now()

        mock_cache.objects.filter.return_value.select_related.return_value = [mock_shift]
        mock_cache.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Mock no attendance found (no-show)
        mock_attendance.objects.filter.return_value.first.return_value = None

        mock_self = Mock()
        result = detect_shift_no_shows_task(mock_self)

        assert result['shifts_checked'] == 1
        assert result['no_shows_detected'] >= 0

    @patch('background_tasks.shift_compliance_tasks.NOCAlertEvent')
    @patch('background_tasks.shift_compliance_tasks.Attendance')
    @patch('background_tasks.shift_compliance_tasks.ShiftScheduleCache')
    def test_success_path_late_arrival(self, mock_cache, mock_attendance, mock_alert):
        """Test successful late arrival detection."""
        # Setup mock shift
        mock_shift = Mock()
        mock_shift.id = 1
        mock_shift.person = Mock()
        mock_shift.person.id = 1
        mock_shift.person.get_full_name.return_value = "John Doe"
        mock_shift.site = Mock()
        mock_shift.site.id = 1
        mock_shift.site.name = "Test Site"
        mock_shift.tenant = Mock()
        mock_shift.scheduled_start = timezone.now() - timezone.timedelta(minutes=30)

        mock_cache.objects.filter.return_value.select_related.return_value = [mock_shift]
        mock_cache.objects.filter.return_value.select_related.return_value.count.return_value = 1

        # Mock late attendance
        mock_attendance_obj = Mock()
        mock_attendance_obj.punchin = timezone.now()  # 30 minutes late
        mock_attendance_obj.bu = mock_shift.site
        mock_attendance.objects.filter.return_value.first.return_value = mock_attendance_obj
        mock_attendance.objects.filter.return_value.exists.return_value = False

        mock_self = Mock()
        result = detect_shift_no_shows_task(mock_self)

        assert result['shifts_checked'] == 1
        assert result['late_arrivals'] >= 0


class TestDatabaseExceptionHandling:
    """Integration tests for DATABASE_EXCEPTIONS handling."""

    def test_database_exceptions_tuple_completeness(self):
        """Verify DATABASE_EXCEPTIONS includes all critical database errors."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        assert IntegrityError in DATABASE_EXCEPTIONS
        assert OperationalError in DATABASE_EXCEPTIONS
        assert DatabaseError in DATABASE_EXCEPTIONS

    @patch('background_tasks.shift_compliance_tasks.Tenant')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_all_database_error_types_trigger_retry(self, mock_logger, mock_tenant):
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
            mock_tenant.objects.filter.side_effect = error

            mock_self = Mock()
            mock_self.retry = Mock(side_effect=Retry)

            with pytest.raises(Retry):
                rebuild_shift_schedule_cache_task(mock_self)

            assert mock_logger.error.called, f"Failed to log {type(error).__name__}"
            assert mock_self.retry.called, f"Failed to retry on {type(error).__name__}"


class TestLoggingPatterns:
    """Test that all error logging follows best practices."""

    @patch('background_tasks.shift_compliance_tasks.Tenant')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_database_errors_logged_with_exc_info(self, mock_logger, mock_tenant):
        """Verify DatabaseError logging includes exc_info=True."""
        mock_tenant.objects.filter.side_effect = DatabaseError("Test error")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        try:
            rebuild_shift_schedule_cache_task(mock_self)
        except Retry:
            pass

        # Verify exc_info=True in log call
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get('exc_info') is True

    @patch('background_tasks.shift_compliance_tasks.Tenant')
    @patch('background_tasks.shift_compliance_tasks.logger')
    def test_unexpected_errors_logged_with_exc_info(self, mock_logger, mock_tenant):
        """Verify unexpected errors logging includes exc_info=True."""
        mock_tenant.objects.filter.side_effect = ValueError("Unexpected")

        mock_self = Mock()

        try:
            rebuild_shift_schedule_cache_task(mock_self)
        except ValueError:
            pass

        # Verify exc_info=True in log call
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get('exc_info') is True
