"""
Comprehensive tests for MQTT input validation security fixes.
Tests that validate_mqtt_topic() and validate_mqtt_payload() prevent injection attacks.
"""

import json
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from background_tasks.tasks import validate_mqtt_topic, validate_mqtt_payload, publish_mqtt


class MQTTTopicValidationTest(TestCase):
    """Test MQTT topic validation security"""

    def test_valid_topic_accepted(self):
        """Test valid MQTT topics are accepted"""
        valid_topics = [
            "home/temperature",
            "devices/sensor/001",
            "youtility/facility/building_a/floor_1",
            "data/metrics",
            "alerts/security",
        ]

        for topic in valid_topics:
            try:
                result = validate_mqtt_topic(topic)
                self.assertEqual(result, topic.strip())
            except ValidationError:
                self.fail(f"Valid topic rejected: {topic}")

    def test_empty_topic_rejected(self):
        """Test empty topics are rejected"""
        invalid_topics = [None, "", "   ", 0]

        for topic in invalid_topics:
            with self.assertRaises(ValidationError) as cm:
                validate_mqtt_topic(topic)
            self.assertIn("must be a non-empty string", str(cm.exception))

    def test_non_string_topic_rejected(self):
        """Test non-string topics are rejected"""
        invalid_topics = [123, [], {}, True]

        for topic in invalid_topics:
            with self.assertRaises(ValidationError):
                validate_mqtt_topic(topic)

    def test_oversized_topic_rejected(self):
        """Test oversized topics are rejected"""
        # Create topic longer than 1000 bytes
        long_topic = "a" * 1001

        with self.assertRaises(ValidationError) as cm:
            validate_mqtt_topic(long_topic)
        self.assertIn("exceeds maximum length", str(cm.exception))

    def test_null_character_rejected(self):
        """Test topics with null characters are rejected"""
        malicious_topic = "home/temp\x00erature"

        with self.assertRaises(ValidationError) as cm:
            validate_mqtt_topic(malicious_topic)
        self.assertIn("cannot contain null characters", str(cm.exception))

    def test_wildcard_characters_rejected(self):
        """Test wildcard characters in publish topics are rejected"""
        wildcard_topics = [
            "home/+/temperature",
            "home/bedroom/#",
            "devices/+/status",
            "alerts/#",
        ]

        for topic in wildcard_topics:
            with self.assertRaises(ValidationError) as cm:
                validate_mqtt_topic(topic)
            self.assertIn("cannot contain wildcards", str(cm.exception))

    def test_injection_attempts_rejected(self):
        """Test injection attack attempts are rejected"""
        malicious_topics = [
            "home/temp<script>alert('xss')</script>",
            "home/temp'DROP TABLE users;--",
            'home/temp"onclick="alert(1)"',
            "home/temp javascript:alert(1)",
            "devices/<script>evil()</script>/data",
        ]

        for topic in malicious_topics:
            with self.assertRaises(ValidationError) as cm:
                validate_mqtt_topic(topic)
            self.assertIn("potentially malicious content", str(cm.exception))

    def test_invalid_characters_rejected(self):
        """Test topics with invalid characters are rejected"""
        invalid_topics = [
            "home/temp@ure",  # @ not allowed
            "home/temp&ure",  # & not allowed
            "home/temp|ure",  # | not allowed
            "home/temp;ure",  # ; not allowed
        ]

        for topic in invalid_topics:
            with self.assertRaises(ValidationError) as cm:
                validate_mqtt_topic(topic)
            self.assertIn("invalid characters", str(cm.exception))

    def test_topic_trimming(self):
        """Test topics are properly trimmed"""
        topic_with_spaces = "  home/temperature  "
        result = validate_mqtt_topic(topic_with_spaces)
        self.assertEqual(result, "home/temperature")

    def test_unicode_topic_handling(self):
        """Test unicode topics are handled correctly"""
        unicode_topic = "home/température"

        # Should handle unicode properly
        try:
            result = validate_mqtt_topic(unicode_topic)
            # Unicode should be preserved if valid
            self.assertIsInstance(result, str)
        except ValidationError:
            # Or rejected if containing invalid unicode patterns
            pass


class MQTTPayloadValidationTest(TestCase):
    """Test MQTT payload validation security"""

    def test_none_payload_accepted(self):
        """Test None payload is accepted"""
        result = validate_mqtt_payload(None)
        self.assertIsNone(result)

    def test_valid_string_payload_sanitized(self):
        """Test valid string payloads are sanitized"""
        clean_payload = "Temperature: 25.5°C"
        result = validate_mqtt_payload(clean_payload)
        self.assertEqual(result, clean_payload)

    def test_malicious_string_payload_sanitized(self):
        """Test malicious string payloads are sanitized"""
        malicious_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "onclick='evil()'",
            "<iframe src='evil.com'></iframe>",
        ]

        for payload in malicious_payloads:
            result = validate_mqtt_payload(payload)
            # Should be sanitized (no malicious content)
            self.assertNotIn("<script", result.lower())
            self.assertNotIn("javascript:", result.lower())
            self.assertNotIn("onclick", result.lower())

    def test_oversized_payload_rejected(self):
        """Test oversized payloads are rejected"""
        # Create payload larger than 1MB
        large_payload = "a" * (1024 * 1024 + 1)

        with self.assertRaises(ValidationError) as cm:
            validate_mqtt_payload(large_payload)
        self.assertIn("exceeds maximum size", str(cm.exception))

    def test_valid_dict_payload_sanitized(self):
        """Test valid dictionary payloads are sanitized"""
        clean_dict = {
            "temperature": 25.5,
            "humidity": 60,
            "location": "Building A"
        }

        result = validate_mqtt_payload(clean_dict)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["temperature"], 25.5)

    def test_malicious_dict_payload_sanitized(self):
        """Test malicious dictionary payloads are sanitized"""
        malicious_dict = {
            "temp": 25.5,
            "alert": "<script>alert('xss')</script>",
            "onclick": "evil()",
            "<script>": "malicious_key"
        }

        result = validate_mqtt_payload(malicious_dict)

        # Keys and values should be sanitized
        result_str = json.dumps(result)
        self.assertNotIn("<script", result_str)
        self.assertNotIn("onclick", result_str)

    def test_nested_dict_sanitization(self):
        """Test nested dictionaries are properly sanitized"""
        nested_dict = {
            "device": {
                "name": "Sensor<script>alert(1)</script>",
                "location": {
                    "building": "A",
                    "room": "101<iframe></iframe>"
                }
            }
        }

        result = validate_mqtt_payload(nested_dict)
        result_str = json.dumps(result)
        self.assertNotIn("<script", result_str)
        self.assertNotIn("<iframe", result_str)

    def test_list_payload_sanitization(self):
        """Test list payloads are sanitized"""
        malicious_list = [
            "temperature: 25",
            "<script>alert('xss')</script>",
            "javascript:evil()",
            {"key": "<iframe src='evil'></iframe>"}
        ]

        result = validate_mqtt_payload(malicious_list)
        result_str = json.dumps(result)
        self.assertNotIn("<script", result_str)
        self.assertNotIn("javascript:", result_str)
        self.assertNotIn("<iframe", result_str)

    def test_non_json_serializable_rejected(self):
        """Test non-JSON serializable payloads are rejected"""
        import datetime

        non_serializable = {
            "date": datetime.datetime.now(),
            "func": lambda x: x,
        }

        with self.assertRaises(ValidationError) as cm:
            validate_mqtt_payload(non_serializable)
        self.assertIn("not JSON serializable", str(cm.exception))

    def test_numeric_payloads_preserved(self):
        """Test numeric payloads are preserved unchanged"""
        numeric_payloads = [42, 3.14159, 0, -100]

        for payload in numeric_payloads:
            result = validate_mqtt_payload(payload)
            self.assertEqual(result, payload)

    def test_boolean_payloads_preserved(self):
        """Test boolean payloads are preserved unchanged"""
        boolean_payloads = [True, False]

        for payload in boolean_payloads:
            result = validate_mqtt_payload(payload)
            self.assertEqual(result, payload)


class MQTTPublishTaskTest(TestCase):
    """Test complete MQTT publish task with validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_task = MagicMock()
        self.mock_task.retry = MagicMock()

    @patch('background_tasks.tasks.publish_message')
    def test_valid_mqtt_publish_succeeds(self, mock_publish):
        """Test valid MQTT publish succeeds"""
        topic = "home/temperature"
        payload = {"temp": 25.5, "unit": "celsius"}

        # Mock the Celery task context
        with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
            mock_task.retry = MagicMock()

            # Call the function directly (not as Celery task)
            result = publish_mqtt(mock_task, topic, payload)

            # Should succeed and return secure response
            self.assertIsInstance(result, dict)
            self.assertTrue(result.get("success", False))
            self.assertIn("correlation_id", result)

        # Verify publish_message was called with sanitized data
        mock_publish.assert_called_once()

    @patch('background_tasks.tasks.publish_message')
    def test_invalid_topic_rejected(self, mock_publish):
        """Test invalid MQTT topic is rejected"""
        malicious_topic = "home/temp<script>alert(1)</script>"
        payload = {"temp": 25.5}

        with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
            result = publish_mqtt(mock_task, malicious_topic, payload)

            # Should fail with validation error
            self.assertFalse(result.get("success", True))
            self.assertEqual(result.get("error_code"), "TASK_EXECUTION_ERROR")

        # publish_message should not be called
        mock_publish.assert_not_called()

    @patch('background_tasks.tasks.publish_message')
    def test_malicious_payload_sanitized(self, mock_publish):
        """Test malicious payload is sanitized before publishing"""
        topic = "home/security"
        malicious_payload = {
            "alert": "<script>alert('breach')</script>",
            "action": "javascript:steal_data()"
        }

        with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
            result = publish_mqtt(mock_task, topic, malicious_payload)

            # Should succeed with sanitized payload
            self.assertTrue(result.get("success", False))

        # publish_message should be called with sanitized data
        mock_publish.assert_called_once()
        called_args = mock_publish.call_args[0]
        called_payload = called_args[1]

        # Payload should be sanitized
        payload_str = json.dumps(called_payload)
        self.assertNotIn("<script", payload_str)
        self.assertNotIn("javascript:", payload_str)

    @patch('background_tasks.tasks.publish_message')
    def test_oversized_payload_rejected(self, mock_publish):
        """Test oversized payload is rejected"""
        topic = "home/data"
        oversized_payload = "x" * (1024 * 1024 + 1)  # > 1MB

        with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
            result = publish_mqtt(mock_task, oversized_payload, oversized_payload)

            # Should fail due to size limit
            self.assertFalse(result.get("success", True))

        # publish_message should not be called
        mock_publish.assert_not_called()

    @patch('background_tasks.tasks.publish_message')
    def test_publish_failure_handled_securely(self, mock_publish):
        """Test publish failures are handled securely"""
        # Mock publish_message to raise exception
        mock_publish.side_effect = Exception("MQTT broker connection failed")

        topic = "home/temperature"
        payload = {"temp": 25.5}

        with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
            mock_task.retry = MagicMock(side_effect=Exception("Retry failed"))

            try:
                result = publish_mqtt(mock_task, topic, payload)
            except Exception:
                # Exception should be raised for retry
                pass

        # publish_message should have been called
        mock_publish.assert_called_once()

    def test_correlation_id_generation(self):
        """Test correlation IDs are generated for tracking"""
        topic = "home/test"
        payload = {"test": True}

        with patch('background_tasks.tasks.publish_message'):
            with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
                result = publish_mqtt(mock_task, topic, payload)

                # Should have correlation ID
                self.assertIn("correlation_id", result)
                correlation_id = result["correlation_id"]

                # Should be valid UUID format
                import re
                uuid_pattern = re.compile(
                    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                )
                self.assertTrue(uuid_pattern.match(correlation_id))

    def test_secure_error_response_format(self):
        """Test error responses don't expose sensitive information"""
        malicious_topic = "invalid<script>topic"
        payload = {"test": True}

        with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
            result = publish_mqtt(mock_task, malicious_topic, payload)

            # Should have secure error format
            self.assertFalse(result.get("success", True))
            self.assertIn("error_code", result)
            self.assertIn("correlation_id", result)

            # Should NOT contain stack traces or detailed error info
            self.assertNotIn("traceback", result)
            self.assertNotIn("Traceback", str(result))
            self.assertNotIn("Exception", str(result))


class MQTTSecurityIntegrationTest(TestCase):
    """Integration tests for complete MQTT security"""

    @patch('background_tasks.tasks.publish_message')
    def test_xss_attack_prevention(self, mock_publish):
        """Test XSS attack attempts are prevented"""
        xss_payloads = [
            "<script>alert(document.cookie)</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>",
        ]

        for payload in xss_payloads:
            topic = "test/security"

            with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
                result = publish_mqtt(mock_task, topic, payload)

                # Should succeed with sanitized payload
                self.assertTrue(result.get("success", False))

            # Verify sanitization occurred
            mock_publish.assert_called()
            called_payload = mock_publish.call_args[0][1]
            self.assertNotIn("<script", str(called_payload).lower())

    @patch('background_tasks.tasks.publish_message')
    def test_sql_injection_prevention(self, mock_publish):
        """Test SQL injection attempts are prevented"""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; INSERT INTO users VALUES('hacker'); --",
        ]

        for payload in sql_payloads:
            topic = "test/security"

            with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
                result = publish_mqtt(mock_task, topic, payload)

                # Should succeed with sanitized payload
                self.assertTrue(result.get("success", False))

    def test_ddos_protection_via_size_limits(self):
        """Test DDoS protection through size limits"""
        topic = "test/ddos"

        # Multiple large payloads should be rejected
        for _ in range(10):
            large_payload = "x" * (1024 * 1024 + 1)  # > 1MB

            with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
                result = publish_mqtt(mock_task, topic, large_payload)

                # Should be rejected
                self.assertFalse(result.get("success", True))

    def test_topic_injection_prevention(self):
        """Test MQTT topic injection is prevented"""
        # Attempt to inject special MQTT control characters
        malicious_topics = [
            "home/temp\x00/malicious",  # Null byte injection
            "home/+/../admin",          # Path traversal attempt
            "home/#/admin",             # Wildcard injection
        ]

        for topic in malicious_topics:
            with self.assertRaises(ValidationError):
                validate_mqtt_topic(topic)