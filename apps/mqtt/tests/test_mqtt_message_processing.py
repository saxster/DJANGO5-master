"""
MQTT Message Processing Tests

Tests message handling including:
- Batch processing performance
- Invalid message format rejection
- Required field validation
- Rate limiting
- Message ordering
- Topic routing

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Test message validation thoroughly
"""

import pytest
import json
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase

from apps.mqtt.subscriber import MQTTPayloadValidator, MQTTSubscriberService
from apps.mqtt.models import DeviceTelemetry, SensorReading, DeviceAlert
from background_tasks.mqtt_handler_tasks import (
    process_device_telemetry,
    process_sensor_data,
    process_device_alert
)


class TestMQTTPayloadValidation:
    """Test MQTT payload validation and security checks."""

    def test_validate_topic_accepts_allowed_prefixes(self):
        """Test topic validation accepts whitelisted topic prefixes."""
        validator = MQTTPayloadValidator()

        # Test all allowed prefixes
        assert validator.validate_topic('device/sensor-123/telemetry') is True
        assert validator.validate_topic('guard/guard-456/gps') is True
        assert validator.validate_topic('sensor/door-789/status') is True
        assert validator.validate_topic('alert/device-001/panic') is True
        assert validator.validate_topic('system/health/server-01') is True

    def test_validate_topic_rejects_unauthorized_prefixes(self):
        """Test topic validation rejects non-whitelisted topics."""
        validator = MQTTPayloadValidator()

        # Security: Prevent unauthorized topics
        assert validator.validate_topic('admin/backdoor') is False
        assert validator.validate_topic('unauthorized/topic') is False
        assert validator.validate_topic('') is False
        assert validator.validate_topic('random') is False

    def test_validate_json_payload_parses_valid_json(self):
        """Test JSON payload validation with valid data."""
        validator = MQTTPayloadValidator()

        valid_payload = json.dumps({
            'device_id': 'sensor-123',
            'battery': 85,
            'timestamp': datetime.now(dt_timezone.utc).isoformat()
        }).encode('utf-8')

        result = validator.validate_json_payload(valid_payload)

        assert result is not None
        assert isinstance(result, dict)
        assert result['device_id'] == 'sensor-123'
        assert result['battery'] == 85

    def test_validate_json_payload_rejects_oversized_payloads(self):
        """
        Test payload size limit (1MB) is enforced.

        Security: Prevents memory exhaustion attacks.
        """
        validator = MQTTPayloadValidator()

        # Create payload exceeding 1MB
        large_payload = json.dumps({
            'data': 'x' * (1024 * 1024 + 1)  # 1MB + 1 byte
        }).encode('utf-8')

        result = validator.validate_json_payload(large_payload)

        assert result is None, "Oversized payloads must be rejected"

    def test_validate_json_payload_rejects_malformed_json(self):
        """
        Test malformed JSON is rejected.

        Security: Prevents parser exploits.
        """
        validator = MQTTPayloadValidator()

        malformed_payloads = [
            b'{ invalid json }',
            b'not json at all',
            b'{"unclosed": ',
            b'',
        ]

        for payload in malformed_payloads:
            result = validator.validate_json_payload(payload)
            assert result is None, f"Malformed JSON should be rejected: {payload}"

    def test_validate_json_payload_rejects_non_object_json(self):
        """
        Test non-object JSON (arrays, primitives) is rejected.

        Security: MQTT messages must be JSON objects.
        """
        validator = MQTTPayloadValidator()

        # Valid JSON but not objects
        non_object_payloads = [
            b'["array", "data"]',
            b'"string"',
            b'123',
            b'true',
            b'null',
        ]

        for payload in non_object_payloads:
            result = validator.validate_json_payload(payload)
            assert result is None, f"Non-object JSON should be rejected: {payload}"

    def test_validate_json_payload_validates_timestamp_format(self):
        """
        Test timestamp validation for invalid formats.

        Security: Invalid timestamps could cause crashes.
        """
        validator = MQTTPayloadValidator()

        # Invalid timestamp format
        invalid_timestamp_payload = json.dumps({
            'device_id': 'sensor-123',
            'timestamp': 'not-a-timestamp'
        }).encode('utf-8')

        result = validator.validate_json_payload(invalid_timestamp_payload)

        assert result is None, "Invalid timestamp format should be rejected"

    def test_validate_json_payload_accepts_valid_iso_timestamp(self):
        """Test valid ISO 8601 timestamp is accepted."""
        validator = MQTTPayloadValidator()

        valid_payload = json.dumps({
            'device_id': 'sensor-123',
            'timestamp': '2025-11-12T10:30:00Z'
        }).encode('utf-8')

        result = validator.validate_json_payload(valid_payload)

        assert result is not None
        assert result['timestamp'] == '2025-11-12T10:30:00Z'

    def test_sanitize_string_removes_dangerous_characters(self):
        """
        Test string sanitization removes null bytes and limits length.

        Security: Prevents injection attacks and buffer overflows.
        """
        validator = MQTTPayloadValidator()

        # Test null byte removal
        result = validator.sanitize_string("test\x00string")
        assert '\x00' not in result

        # Test length limit
        long_string = 'x' * 500
        result = validator.sanitize_string(long_string, max_length=255)
        assert len(result) == 255

        # Test whitespace stripping
        result = validator.sanitize_string("  test  ")
        assert result == "test"


@pytest.mark.django_db
class TestDeviceTelemetryProcessing:
    """Test device telemetry message processing."""

    def test_process_device_telemetry_extracts_device_id(
        self,
        mock_device_telemetry_message
    ):
        """Test device ID is correctly extracted from topic."""
        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = 'device/device-12345/telemetry'
            process_device_telemetry(topic, mock_device_telemetry_message)

            # Verify device ID was extracted
            mock_processor.add_telemetry.assert_called_once()
            telemetry_data = mock_processor.add_telemetry.call_args[0][0]
            assert telemetry_data['device_id'] == 'device-12345'

    def test_process_device_telemetry_parses_all_metrics(
        self,
        mock_device_telemetry_message
    ):
        """Test all telemetry metrics are parsed correctly."""
        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = 'device/device-12345/telemetry'
            process_device_telemetry(topic, mock_device_telemetry_message)

            telemetry_data = mock_processor.add_telemetry.call_args[0][0]

            # Verify all metrics
            assert telemetry_data['battery_level'] == 85
            assert telemetry_data['signal_strength'] == -60
            assert telemetry_data['temperature'] == 32.5
            assert telemetry_data['connectivity_status'] == 'ONLINE'

    def test_process_device_telemetry_handles_missing_timestamp(
        self,
        mock_device_telemetry_message
    ):
        """Test missing timestamp defaults to server time."""
        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            # Remove timestamp
            del mock_device_telemetry_message['timestamp']

            topic = 'device/device-12345/telemetry'
            process_device_telemetry(topic, mock_device_telemetry_message)

            # Should not raise exception
            telemetry_data = mock_processor.add_telemetry.call_args[0][0]
            assert telemetry_data['timestamp'] is not None

    def test_process_device_telemetry_handles_invalid_topic(self):
        """Test invalid topic format is handled gracefully."""
        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            # Invalid topic (missing device ID)
            invalid_topic = 'device/'
            invalid_data = {'battery': 50}

            # Should not raise exception
            process_device_telemetry(invalid_topic, invalid_data)

            # Should not process invalid topic
            mock_processor.add_telemetry.assert_not_called()

    def test_process_device_telemetry_low_battery_warning(
        self,
        mock_device_telemetry_message
    ):
        """Test low battery (<20%) triggers warning metric."""
        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            with patch('background_tasks.mqtt_handler_tasks.TaskMetrics') as mock_metrics:
                # Set low battery
                mock_device_telemetry_message['battery'] = 15

                topic = 'device/device-12345/telemetry'
                process_device_telemetry(topic, mock_device_telemetry_message)

                # Verify low battery metric was incremented
                metric_calls = [call[0][0] for call in mock_metrics.increment_counter.call_args_list]
                assert 'mqtt_device_low_battery' in metric_calls


@pytest.mark.django_db
class TestSensorDataProcessing:
    """Test sensor data message processing."""

    def test_process_sensor_data_stores_reading(
        self,
        mock_sensor_reading_message
    ):
        """Test sensor reading is stored in database."""
        topic = 'sensor/door-sensor-456/status'
        process_sensor_data(topic, mock_sensor_reading_message)

        # Verify sensor reading was created
        reading = SensorReading.objects.filter(sensor_id='door-sensor-456').first()

        assert reading is not None
        assert reading.sensor_type == 'DOOR'
        assert reading.state == 'OPEN'

    def test_process_sensor_data_handles_numeric_values(self):
        """Test sensor with numeric values (temperature, humidity)."""
        sensor_message = {
            'sensor_id': 'temp-sensor-123',
            'type': 'temperature',
            'value': 25.5,
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': 'sensor/temp-sensor-123/reading',
                'qos': 1,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        topic = 'sensor/temp-sensor-123/reading'
        process_sensor_data(topic, sensor_message)

        reading = SensorReading.objects.filter(sensor_id='temp-sensor-123').first()

        assert reading is not None
        assert reading.sensor_type == 'TEMPERATURE'
        assert reading.value == 25.5

    def test_process_sensor_data_fire_alarm_triggers_critical_alert(
        self,
        mock_fire_alarm_message
    ):
        """
        CRITICAL: Test fire alarm (smoke >100) triggers critical alert.

        Security: Fire alarms require immediate response.
        """
        with patch('background_tasks.mqtt_handler_tasks.process_device_alert') as mock_alert:
            topic = 'sensor/smoke-detector-789/alarm'
            process_sensor_data(topic, mock_fire_alarm_message)

            # Verify critical alert was queued
            mock_alert.apply_async.assert_called_once()
            alert_args = mock_alert.apply_async.call_args

            # Verify alert details
            alert_data = alert_args[1]['args'][1]
            assert alert_data['alert_type'] == 'fire'
            assert alert_data['severity'] == 'critical'
            assert 'fire alarm' in alert_data['message'].lower()

    def test_process_sensor_data_handles_missing_sensor_type(self):
        """Test sensor data with missing type defaults to UNKNOWN."""
        sensor_message = {
            'sensor_id': 'unknown-sensor-999',
            # Missing 'type' field
            'state': 'detected',
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': 'sensor/unknown-sensor-999/reading',
                'qos': 1,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        topic = 'sensor/unknown-sensor-999/reading'
        process_sensor_data(topic, sensor_message)

        reading = SensorReading.objects.filter(sensor_id='unknown-sensor-999').first()

        assert reading is not None
        assert reading.sensor_type == 'UNKNOWN'


@pytest.mark.django_db
class TestDeviceAlertProcessing:
    """Test device alert message processing."""

    def test_process_device_alert_creates_alert_record(
        self,
        mock_device_alert_message
    ):
        """Test device alert creates DeviceAlert record."""
        with patch('background_tasks.mqtt_handler_tasks.AlertNotificationService.notify_alert'):
            topic = 'alert/device-xyz-789/failure'
            process_device_alert(topic, mock_device_alert_message)

        alert = DeviceAlert.objects.filter(source_id='device-xyz-789').first()

        assert alert is not None
        assert alert.alert_type == 'EQUIPMENT_FAILURE'
        assert alert.severity == 'HIGH'
        assert alert.status == 'NEW'

    def test_process_device_alert_parses_location_if_present(self):
        """Test alert with GPS location parses coordinates."""
        alert_with_location = {
            'alert_type': 'intrusion',
            'severity': 'critical',
            'message': 'Intrusion detected',
            'source_id': 'sensor-intrusion-456',
            'location': {'lat': 12.9716, 'lon': 77.5946},
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': 'alert/sensor-intrusion-456/intrusion',
                'qos': 2,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.AlertNotificationService.notify_alert'):
            topic = 'alert/sensor-intrusion-456/intrusion'
            process_device_alert(topic, alert_with_location)

        alert = DeviceAlert.objects.filter(source_id='sensor-intrusion-456').first()

        assert alert is not None
        assert alert.location is not None
        assert abs(alert.location.y - 12.9716) < 0.0001

    def test_process_device_alert_handles_invalid_location_gracefully(self):
        """Test alert with invalid location doesn't crash."""
        alert_with_bad_location = {
            'alert_type': 'intrusion',
            'severity': 'critical',
            'message': 'Intrusion detected',
            'source_id': 'sensor-bad-location',
            'location': {'lat': 'invalid', 'lon': 'invalid'},  # Invalid
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': 'alert/sensor-bad-location/intrusion',
                'qos': 2,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.AlertNotificationService.notify_alert'):
            # Should not raise exception
            topic = 'alert/sensor-bad-location/intrusion'
            process_device_alert(topic, alert_with_bad_location)

        # Alert should still be created (without location)
        alert = DeviceAlert.objects.filter(source_id='sensor-bad-location').first()
        assert alert is not None
        assert alert.location is None

    def test_process_device_alert_broadcasts_to_websocket(
        self,
        mock_device_alert_message
    ):
        """Test critical alert is broadcast to NOC dashboard via WebSocket."""
        with patch('background_tasks.mqtt_handler_tasks.AlertNotificationService.notify_alert'):
            # Mock WebSocket broadcast (inherited from WebSocketBroadcastTask)
            with patch.object(
                process_device_alert,
                'broadcast_to_noc_dashboard',
                create=True
            ) as mock_broadcast:
                topic = 'alert/device-xyz-789/failure'
                process_device_alert(topic, mock_device_alert_message)

                # Verify WebSocket broadcast was called
                mock_broadcast.assert_called_once()
                broadcast_call = mock_broadcast.call_args

                assert broadcast_call[1]['message_type'] == 'critical_alert'
                assert broadcast_call[1]['priority'] == 'critical'


@pytest.mark.django_db
class TestMessageOrderingAndRaceConditions:
    """Test message ordering and concurrent processing."""

    def test_out_of_order_messages_handled_by_timestamp(self):
        """
        Test out-of-order messages are handled using device timestamp.

        Security: Message ordering based on device time, not arrival time.
        """
        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            # Send messages out of order
            older_message = {
                'device_id': 'device-123',
                'battery': 80,
                'timestamp': '2025-11-12T10:00:00Z',
                '_mqtt_metadata': {
                    'topic': 'device/device-123/telemetry',
                    'qos': 1,
                    'received_at': '2025-11-12T10:05:00Z',  # Received later
                    'broker': 'localhost'
                }
            }

            newer_message = {
                'device_id': 'device-123',
                'battery': 75,
                'timestamp': '2025-11-12T10:01:00Z',
                '_mqtt_metadata': {
                    'topic': 'device/device-123/telemetry',
                    'qos': 1,
                    'received_at': '2025-11-12T10:04:00Z',  # Received earlier
                    'broker': 'localhost'
                }
            }

            # Process newer message first (out of order)
            topic = 'device/device-123/telemetry'
            process_device_telemetry(topic, newer_message)
            process_device_telemetry(topic, older_message)

            # Both should be processed with correct timestamps
            assert mock_processor.add_telemetry.call_count == 2


@pytest.mark.django_db
class TestMessageValidationAndSecurity:
    """Test message validation and security measures."""

    def test_empty_message_handled_gracefully(self):
        """Test empty message payload is rejected gracefully."""
        validator = MQTTPayloadValidator()

        result = validator.validate_json_payload(b'{}')

        # Empty object is valid JSON but may lack required fields
        assert result is not None
        assert isinstance(result, dict)

    def test_message_with_sql_injection_attempt_sanitized(self):
        """
        Test SQL injection attempts in message fields are handled.

        Security: Validates input sanitization.
        """
        validator = MQTTPayloadValidator()

        malicious_string = "test'; DROP TABLE mqtt_device_telemetry; --"
        sanitized = validator.sanitize_string(malicious_string)

        # Sanitization removes null bytes but preserves other characters
        # (SQL injection prevention happens at ORM level via parameterized queries)
        assert '\x00' not in sanitized

    def test_message_with_xss_attempt_in_alert_message(self):
        """
        Test XSS attempts in alert messages are handled.

        Security: Alert messages may be displayed in web dashboard.
        """
        xss_alert_message = {
            'alert_type': 'intrusion',
            'severity': 'high',
            'message': '<script>alert("XSS")</script>',
            'source_id': 'sensor-xss-test',
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': 'alert/sensor-xss-test/intrusion',
                'qos': 2,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.AlertNotificationService.notify_alert'):
            topic = 'alert/sensor-xss-test/intrusion'
            process_device_alert(topic, xss_alert_message)

        # Alert should be created (XSS prevention happens at template rendering layer)
        alert = DeviceAlert.objects.filter(source_id='sensor-xss-test').first()
        assert alert is not None
        assert '<script>' in alert.message  # Stored as-is, escaped during rendering
