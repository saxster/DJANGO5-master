"""
Test suite for Meter Intelligence Tasks exception handling.

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

from background_tasks.meter_intelligence_tasks import (
    forecast_all_tanks_task,
    detect_theft_leaks_task,
    generate_cost_dashboards_task,
    monitor_all_meter_intelligence_task,
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS


class TestForecastAllTanksExceptions:
    """Test exception handling in forecast_all_tanks_task."""

    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_handles_database_error_with_retry(self, mock_logger, mock_asset):
        """Test that DatabaseError triggers task retry."""
        mock_asset.objects.filter.side_effect = DatabaseError("Connection lost")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            forecast_all_tanks_task(mock_self, tenant_id=1)

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

        # Verify retry was called
        assert mock_self.retry.called

    @patch('background_tasks.meter_intelligence_tasks.TankForecastingService')
    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_handles_tank_forecasting_error_gracefully(self, mock_logger, mock_asset, mock_service):
        """Test that tank forecasting errors are caught and logged (line 92)."""
        # Setup mock tanks
        mock_tank = Mock()
        mock_tank.id = 1
        mock_tank.name = "Tank 1"
        mock_tank.meter_readings.order_by.return_value.first.return_value = Mock(reading_value=100)
        mock_tank.other_data = {}

        mock_asset.objects.filter.return_value.select_related.return_value = [mock_tank]

        # Mock forecasting service to raise error
        mock_service.predict_empty_date.side_effect = ValueError("Invalid reading data")

        mock_self = Mock()
        result = forecast_all_tanks_task(mock_self, tenant_id=1)

        # Should continue processing and track warning
        assert result['status'] == 'success'
        assert len(result['warnings']) > 0

        # Verify error was logged with exc_info
        assert mock_logger.error.called

    @patch('background_tasks.meter_intelligence_tasks.TankForecastingService')
    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_handles_unexpected_error_gracefully_line_124(self, mock_logger, mock_asset, mock_service):
        """Test that unexpected errors are caught and returned (line 124)."""
        mock_asset.objects.filter.side_effect = ValueError("Unexpected error")

        mock_self = Mock()
        result = forecast_all_tanks_task(mock_self, tenant_id=1)

        # Should return error result
        assert result['status'] == 'error'
        assert 'error' in result

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    @patch('background_tasks.meter_intelligence_tasks.TankForecastingService')
    @patch('background_tasks.meter_intelligence_tasks.Asset')
    def test_success_path(self, mock_asset, mock_service):
        """Test successful tank forecasting."""
        # Setup mock tanks
        mock_tank = Mock()
        mock_tank.id = 1
        mock_tank.name = "Tank 1"
        mock_tank.other_data = {}
        mock_tank.save = Mock()

        mock_reading = Mock()
        mock_reading.reading_value = 100
        mock_tank.meter_readings.order_by.return_value.first.return_value = mock_reading

        mock_asset.objects.filter.return_value.select_related.return_value = [mock_tank]

        # Mock successful forecast
        mock_service.predict_empty_date.return_value = {
            'days_remaining': 5,
            'empty_date': '2025-11-17'
        }
        mock_service.create_refill_alert.return_value = None

        mock_self = Mock()
        result = forecast_all_tanks_task(mock_self, tenant_id=1)

        assert result['status'] == 'success'
        assert result['tanks_processed'] == 1


class TestDetectTheftLeaksExceptions:
    """Test exception handling in detect_theft_leaks_task."""

    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_handles_database_error_with_retry(self, mock_logger, mock_asset):
        """Test that DatabaseError triggers task retry."""
        mock_asset.objects.filter.side_effect = DatabaseError("Connection lost")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        with pytest.raises(Retry):
            detect_theft_leaks_task(mock_self, tenant_id=1)

        assert mock_logger.error.called
        assert mock_self.retry.called

    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_handles_unexpected_error_gracefully_line_240(self, mock_logger, mock_asset):
        """Test that unexpected errors are caught and returned (line 240)."""
        mock_asset.objects.filter.side_effect = ValueError("Unexpected error")

        mock_self = Mock()
        result = detect_theft_leaks_task(mock_self, tenant_id=1)

        # Should return error result
        assert result['status'] == 'error'
        assert 'error' in result

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    @patch('background_tasks.meter_intelligence_tasks.TheftLeakDetectionService')
    @patch('background_tasks.meter_intelligence_tasks.Asset')
    def test_success_path(self, mock_asset, mock_service):
        """Test successful theft/leak detection."""
        # Setup mock assets
        mock_asset_obj = Mock()
        mock_asset_obj.id = 1

        mock_current = Mock()
        mock_current.reading_value = 80
        mock_current.timestamp = timezone.now()

        mock_previous = Mock()
        mock_previous.reading_value = 100

        mock_asset_obj.meter_readings.order_by.return_value.__getitem__ = Mock(
            side_effect=lambda idx: [mock_current, mock_previous][idx]
        )
        mock_asset_obj.meter_readings.order_by.return_value.__len__ = Mock(return_value=2)

        mock_asset.objects.filter.return_value = [mock_asset_obj]

        # Mock no theft/leak detected
        mock_service.detect_sudden_drop.return_value = {'is_theft': False}
        mock_service.detect_gradual_leak.return_value = {'is_leak': False}

        mock_self = Mock()
        result = detect_theft_leaks_task(mock_self, tenant_id=1)

        assert result['status'] == 'success'
        assert result['assets_analyzed'] == 1


class TestGenerateCostDashboardsExceptions:
    """Test exception handling in generate_cost_dashboards_task."""

    @patch('background_tasks.meter_intelligence_tasks.Bt')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_handles_unexpected_error_gracefully_line_311(self, mock_logger, mock_bt):
        """Test that unexpected errors are caught and returned (line 311)."""
        mock_bt.objects.filter.side_effect = ValueError("Unexpected error")

        mock_self = Mock()
        result = generate_cost_dashboards_task(mock_self, tenant_id=1)

        # Should return error result
        assert result['status'] == 'error'
        assert 'error' in result

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    @patch('background_tasks.meter_intelligence_tasks.CostOptimizationService')
    @patch('background_tasks.meter_intelligence_tasks.Bt')
    def test_success_path(self, mock_bt, mock_service):
        """Test successful dashboard generation."""
        # Setup mock sites
        mock_site = Mock()
        mock_site.id = 1
        mock_site.other_data = {}
        mock_site.save = Mock()

        mock_bt.objects.filter.return_value = [mock_site]

        # Mock successful dashboard generation
        mock_service.generate_cost_dashboard.return_value = {
            'total_cost': 1000,
            'savings_opportunities': []
        }

        mock_self = Mock()
        result = generate_cost_dashboards_task(mock_self, tenant_id=1)

        assert result['status'] == 'success'
        assert result['dashboards_created'] == 1


class TestMonitorAllMeterIntelligenceExceptions:
    """Test exception handling in monitor_all_meter_intelligence_task."""

    @patch('background_tasks.meter_intelligence_tasks.Tenant')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_handles_tenant_processing_error_gracefully_line_370(self, mock_logger, mock_tenant):
        """Test that tenant processing errors are caught and logged (line 370)."""
        # Setup mock tenant
        mock_tenant_obj = Mock()
        mock_tenant_obj.id = 1

        mock_tenant.objects.filter.return_value = [mock_tenant_obj]

        # Mock forecast task to raise error
        with patch('background_tasks.meter_intelligence_tasks.forecast_all_tanks_task') as mock_forecast:
            mock_forecast.side_effect = ValueError("Task failed")

            result = monitor_all_meter_intelligence_task()

        # Should continue processing and track error
        assert len(result['errors']) > 0
        assert result['errors'][0]['tenant_id'] == 1

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    @patch('background_tasks.meter_intelligence_tasks.detect_theft_leaks_task')
    @patch('background_tasks.meter_intelligence_tasks.forecast_all_tanks_task')
    @patch('background_tasks.meter_intelligence_tasks.Tenant')
    def test_success_path(self, mock_tenant, mock_forecast, mock_detect):
        """Test successful monitoring across all tenants."""
        # Setup mock tenant
        mock_tenant_obj = Mock()
        mock_tenant_obj.id = 1

        mock_tenant.objects.filter.return_value = [mock_tenant_obj]

        # Mock successful tasks
        mock_forecast.return_value = {
            'status': 'success',
            'forecasts_created': 5
        }
        mock_detect.return_value = {
            'status': 'success',
            'theft_detected': 1,
            'leaks_detected': 2
        }

        result = monitor_all_meter_intelligence_task()

        assert result['tenants_processed'] == 1
        assert result['total_forecasts'] == 5
        assert result['total_theft_detected'] == 1
        assert result['total_leaks_detected'] == 2


class TestDatabaseExceptionHandling:
    """Integration tests for DATABASE_EXCEPTIONS handling."""

    def test_database_exceptions_tuple_completeness(self):
        """Verify DATABASE_EXCEPTIONS includes all critical database errors."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        assert IntegrityError in DATABASE_EXCEPTIONS
        assert OperationalError in DATABASE_EXCEPTIONS
        assert DatabaseError in DATABASE_EXCEPTIONS

    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_all_database_error_types_trigger_retry(self, mock_logger, mock_asset):
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
            mock_asset.objects.filter.side_effect = error

            mock_self = Mock()
            mock_self.retry = Mock(side_effect=Retry)

            with pytest.raises(Retry):
                forecast_all_tanks_task(mock_self, tenant_id=1)

            assert mock_logger.error.called, f"Failed to log {type(error).__name__}"
            assert mock_self.retry.called, f"Failed to retry on {type(error).__name__}"


class TestLoggingPatterns:
    """Test that all error logging follows best practices."""

    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_database_errors_logged_with_exc_info(self, mock_logger, mock_asset):
        """Verify DatabaseError logging includes exc_info=True."""
        mock_asset.objects.filter.side_effect = DatabaseError("Test error")

        mock_self = Mock()
        mock_self.retry = Mock(side_effect=Retry)

        try:
            forecast_all_tanks_task(mock_self, tenant_id=1)
        except Retry:
            pass

        # Verify exc_info=True in log call
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get('exc_info') is True

    @patch('background_tasks.meter_intelligence_tasks.Asset')
    @patch('background_tasks.meter_intelligence_tasks.logger')
    def test_unexpected_errors_logged_with_exc_info(self, mock_logger, mock_asset):
        """Verify unexpected errors logging includes exc_info=True."""
        mock_asset.objects.filter.side_effect = ValueError("Unexpected")

        mock_self = Mock()

        result = forecast_all_tanks_task(mock_self, tenant_id=1)

        # Verify exc_info=True in log call
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get('exc_info') is True
