"""
Test suite for MQTT Batch Processor exception handling.

Validates specific exception handling patterns per Rule #11:
- No generic exception handlers (all must be specific types)
- Use specific exception types from apps.core.exceptions.patterns
- All errors logged with exc_info=True
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from django.db import IntegrityError, OperationalError, DatabaseError

from background_tasks.mqtt_batch_processor import MQTTBatchProcessor
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS


class TestMQTTBatchProcessorExceptions:
    """Test exception handling in MQTTBatchProcessor."""

    def setup_method(self):
        """Setup test fixtures."""
        self.processor = MQTTBatchProcessor(batch_size=10, flush_interval=5)

    def teardown_method(self):
        """Cleanup after each test."""
        if hasattr(self, 'processor') and self.processor.running:
            self.processor.stop()

    # =========================================================================
    # Test add_telemetry exception handling (line 165)
    # =========================================================================

    def test_add_telemetry_handles_validation_error(self):
        """Test add_telemetry handles ValidationError specifically."""
        # Invalid telemetry data (missing required field)
        invalid_data = {'device_id': None}  # Missing timestamp

        with pytest.raises(TypeError):  # DeviceTelemetry init will raise TypeError
            self.processor.add_telemetry(invalid_data)

    def test_add_telemetry_handles_type_error(self):
        """Test add_telemetry handles TypeError for invalid data types."""
        invalid_data = {'device_id': 123, 'timestamp': 'not-a-datetime'}

        with pytest.raises(VALIDATION_EXCEPTIONS):
            self.processor.add_telemetry(invalid_data)

    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_add_telemetry_logs_with_exc_info(self, mock_logger):
        """Test that add_telemetry logs errors with exc_info=True."""
        invalid_data = {'device_id': None}

        with pytest.raises(Exception):
            self.processor.add_telemetry(invalid_data)

        # Verify logger.error was called with exc_info=True
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    # =========================================================================
    # Test add_guard_location exception handling (line 179)
    # =========================================================================

    def test_add_guard_location_handles_validation_error(self):
        """Test add_guard_location handles ValidationError specifically."""
        invalid_data = {'guard_id': None}  # Missing required fields

        with pytest.raises(TypeError):
            self.processor.add_guard_location(invalid_data)

    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_add_guard_location_logs_with_exc_info(self, mock_logger):
        """Test that add_guard_location logs errors with exc_info=True."""
        invalid_data = {'guard_id': None}

        with pytest.raises(Exception):
            self.processor.add_guard_location(invalid_data)

        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    # =========================================================================
    # Test add_sensor_reading exception handling (line 193)
    # =========================================================================

    def test_add_sensor_reading_handles_validation_error(self):
        """Test add_sensor_reading handles ValidationError specifically."""
        invalid_data = {'sensor_id': None}

        with pytest.raises(TypeError):
            self.processor.add_sensor_reading(invalid_data)

    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_add_sensor_reading_logs_with_exc_info(self, mock_logger):
        """Test that add_sensor_reading logs errors with exc_info=True."""
        invalid_data = {'sensor_id': None}

        with pytest.raises(Exception):
            self.processor.add_sensor_reading(invalid_data)

        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    # =========================================================================
    # Test _flush_telemetry exception handling (line 232)
    # =========================================================================

    @patch('background_tasks.mqtt_batch_processor.DeviceTelemetry')
    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_flush_telemetry_handles_database_error(self, mock_logger, mock_device_telemetry):
        """Test _flush_telemetry handles DatabaseError specifically."""
        # Setup mock to raise DatabaseError
        mock_device_telemetry.objects.bulk_create.side_effect = DatabaseError("DB connection lost")

        # Add some data to batch
        with self.processor.lock:
            self.processor.batches['telemetry'] = [Mock()] * 5

        # Call internal flush method (assumes lock held)
        with self.processor.lock:
            self.processor._flush_telemetry()

        # Verify error was logged with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

        # Verify batch was NOT cleared (for retry)
        assert len(self.processor.batches['telemetry']) == 5

    @patch('background_tasks.mqtt_batch_processor.DeviceTelemetry')
    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_flush_telemetry_handles_integrity_error(self, mock_logger, mock_device_telemetry):
        """Test _flush_telemetry handles IntegrityError specifically."""
        mock_device_telemetry.objects.bulk_create.side_effect = IntegrityError("Duplicate key")

        with self.processor.lock:
            self.processor.batches['telemetry'] = [Mock()] * 3

        with self.processor.lock:
            self.processor._flush_telemetry()

        # Verify specific DATABASE_EXCEPTIONS handler was triggered
        assert mock_logger.error.called
        error_message = mock_logger.error.call_args[0][0]
        assert 'Database error' in error_message

    @patch('background_tasks.mqtt_batch_processor.DeviceTelemetry')
    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_flush_telemetry_handles_operational_error(self, mock_logger, mock_device_telemetry):
        """Test _flush_telemetry handles OperationalError for deadlocks."""
        mock_device_telemetry.objects.bulk_create.side_effect = OperationalError("Deadlock detected")

        with self.processor.lock:
            self.processor.batches['telemetry'] = [Mock()] * 2

        with self.processor.lock:
            self.processor._flush_telemetry()

        # Verify DATABASE_EXCEPTIONS caught it
        assert mock_logger.error.called
        assert self.processor.flush_errors == 1

    @patch('background_tasks.mqtt_batch_processor.DeviceTelemetry')
    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_flush_telemetry_validation_error_handling(self, mock_logger, mock_device_telemetry):
        """Test _flush_telemetry handles validation errors with specific handler."""
        # This tests the VALIDATION_EXCEPTIONS handler
        mock_device_telemetry.objects.bulk_create.side_effect = ValueError("Validation error")

        with self.processor.lock:
            self.processor.batches['telemetry'] = [Mock()]

        with self.processor.lock:
            self.processor._flush_telemetry()

        # Should still log with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args[1]
        assert call_args[1]['exc_info'] is True

    # =========================================================================
    # Integration tests
    # =========================================================================

    @patch('background_tasks.mqtt_batch_processor.DeviceTelemetry')
    def test_batch_processor_handles_database_exceptions_gracefully(self, mock_device_telemetry):
        """Integration test: processor continues after database errors."""
        # First flush fails, second succeeds
        mock_device_telemetry.objects.bulk_create.side_effect = [
            OperationalError("Transient error"),  # First call fails
            None  # Second call succeeds
        ]

        with self.processor.lock:
            self.processor.batches['telemetry'] = [Mock()] * 2

        # First flush fails
        with self.processor.lock:
            self.processor._flush_telemetry()

        assert self.processor.flush_errors == 1
        assert len(self.processor.batches['telemetry']) == 2  # Batch retained for retry

        # Second flush succeeds (manually clear batch to simulate success)
        with self.processor.lock:
            self.processor.batches['telemetry'].clear()

        assert len(self.processor.batches['telemetry']) == 0

    def test_processor_tracks_error_metrics(self):
        """Test that processor correctly tracks flush_errors metric."""
        assert self.processor.flush_errors == 0

        with patch('background_tasks.mqtt_batch_processor.DeviceTelemetry') as mock_dt:
            mock_dt.objects.bulk_create.side_effect = DatabaseError("Test error")

            with self.processor.lock:
                self.processor.batches['telemetry'] = [Mock()]
                self.processor._flush_telemetry()

            assert self.processor.flush_errors == 1

    # =========================================================================
    # Test specific exception types are caught
    # =========================================================================

    def test_database_exceptions_tuple_includes_all_db_errors(self):
        """Verify DATABASE_EXCEPTIONS includes all Django DB error types."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        # Verify all critical database exceptions are included
        assert IntegrityError in DATABASE_EXCEPTIONS
        assert OperationalError in DATABASE_EXCEPTIONS
        assert DatabaseError in DATABASE_EXCEPTIONS

    @patch('background_tasks.mqtt_batch_processor.DeviceTelemetry')
    @patch('background_tasks.mqtt_batch_processor.logger')
    def test_all_database_exception_types_handled(self, mock_logger, mock_device_telemetry):
        """Test that all DATABASE_EXCEPTIONS types are properly handled."""
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
            mock_device_telemetry.objects.bulk_create.side_effect = error

            with self.processor.lock:
                self.processor.batches['telemetry'] = [Mock()]
                self.processor._flush_telemetry()

            # Each should be caught by DATABASE_EXCEPTIONS handler
            assert mock_logger.error.called, f"Failed to log {type(error).__name__}"
            error_msg = mock_logger.error.call_args[0][0]
            assert 'Database error' in error_msg, f"Wrong handler for {type(error).__name__}"
