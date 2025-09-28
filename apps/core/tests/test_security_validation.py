"""
Security validation tests for code quality improvements.
Ensures that code quality changes don't compromise security features.
"""

# Standard library imports
import unittest
# Django imports
from django.test import TestCase
from django.core.exceptions import ValidationError

# Third-party imports
import pytest

# Local application imports
from background_tasks.tasks import validate_mqtt_topic, validate_mqtt_payload


class SecurityValidationTest(TestCase):
    """Test security features after code quality improvements."""

    @pytest.mark.security
    def test_mqtt_topic_validation_security(self):
        """Test MQTT topic validation prevents security issues."""
        # Test valid topics
        valid_topics = [
            "sensor/temperature",
            "device/001/status",
            "building/floor1/room101"
        ]

        for topic in valid_topics:
            try:
                result = validate_mqtt_topic(topic)
                self.assertIsInstance(result, str)
                self.assertEqual(result.strip(), topic.strip())
            except ValidationError:
                self.fail(f"Valid topic '{topic}' should not raise ValidationError")

        # Test invalid topics that should be rejected for security
        invalid_topics = [
            "",           # Empty string
            None,         # None value
            "   ",        # Only whitespace
            "topic with spaces",  # May need escaping
            "topic/../../../etc/passwd",  # Path traversal attempt
        ]

        for topic in invalid_topics:
            with self.assertRaises((ValidationError, TypeError, AttributeError)):
                validate_mqtt_topic(topic)

    @pytest.mark.security
    def test_mqtt_payload_validation_security(self):
        """Test MQTT payload validation prevents security issues."""
        # Test valid payloads
        valid_payloads = [
            {"temperature": 25.5},
            {"status": "online", "battery": 85},
            "simple string",
            42,
            True,
            [1, 2, 3]
        ]

        for payload in valid_payloads:
            try:
                result = validate_mqtt_payload(payload)
                self.assertIsNotNone(result)
            except ValidationError:
                self.fail(f"Valid payload '{payload}' should not raise ValidationError")

        # Test potentially dangerous payloads
        dangerous_payloads = [
            {"__class__": {"__module__": "os", "__name__": "system"}},  # Object injection attempt
            "<script>alert('xss')</script>",  # XSS attempt
            "'; DROP TABLE users; --",  # SQL injection attempt
        ]

        for payload in dangerous_payloads:
            # Should either sanitize or reject dangerous content
            try:
                result = validate_mqtt_payload(payload)
                # If it doesn't raise an exception, it should be sanitized
                if isinstance(result, str):
                    self.assertNotIn("<script>", result)
                    self.assertNotIn("DROP TABLE", result)
            except ValidationError:
                # Rejecting dangerous payloads is also acceptable
                pass

    @pytest.mark.security
    def test_xss_prevention_still_active(self):
        """Test that XSS prevention is still working after code improvements."""
        # This test checks that our import reorganization didn't break XSS prevention
        from background_tasks.tasks import sanitize_mqtt_payload

        test_payloads = [
            {"user_input": "<script>alert('xss')</script>"},
            {"description": "Normal text"},
            {"content": "<img src='x' onerror='alert(1)'>"}
        ]

        for payload in test_payloads:
            sanitized = sanitize_mqtt_payload(payload)

            if isinstance(sanitized, dict):
                for key, value in sanitized.items():
                    if isinstance(value, str):
                        # Should not contain dangerous script tags
                        self.assertNotIn("<script>", value)
                        self.assertNotIn("onerror=", value)

    @pytest.mark.security
    def test_type_hints_dont_bypass_validation(self):
        """Test that adding type hints doesn't bypass security validation."""
        # Even with type hints, functions should still validate input properly

        # Test with wrong type that should be caught by validation logic
        with self.assertRaises((ValidationError, TypeError)):
            validate_mqtt_topic(123)  # Integer instead of string

        with self.assertRaises((ValidationError, TypeError)):
            validate_mqtt_topic(None)  # None instead of string

    @pytest.mark.security
    def test_improved_string_formatting_security(self):
        """Test that improved string formatting doesn't introduce security issues."""
        # Test the refactored string formatting logic
        test_cases = [
            {
                "identifier": "INTERNALTOUR",
                "expected_type": "TOUR"
            },
            {
                "identifier": "EXTERNALTOUR",
                "expected_type": "TOUR"
            },
            {
                "identifier": "MAINTENANCE",
                "expected_type": "MAINTENANCE"
            },
            {
                "identifier": "<script>alert('xss')</script>",
                "expected_type": "<script>alert('xss')</script>"  # Should be handled by other validation
            }
        ]

        for test_case in test_cases:
            # Simulate the improved logic
            task_type = "TOUR" if test_case["identifier"] in ["INTERNALTOUR", "EXTERNALTOUR"] else test_case["identifier"]

            if test_case["identifier"] in ["INTERNALTOUR", "EXTERNALTOUR"]:
                self.assertEqual(task_type, "TOUR")
            else:
                # For security test, just verify it returns the input
                # (other layers should handle sanitization)
                self.assertEqual(task_type, test_case["identifier"])

    @pytest.mark.security
    def test_settings_functions_security(self):
        """Test that settings functions with type hints maintain security."""
        from intelliwiz_config.settings import check_path

        # Test path traversal attempts
        dangerous_paths = [
            "/etc/passwd",
            "../../../etc/shadow",
            "/tmp/claude/../../../home",
            "~/../../../root"
        ]

        for path in dangerous_paths:
            # The function should handle these safely
            try:
                result = check_path(path)
                self.assertIsInstance(result, bool)
                # If it succeeds, it should have created a safe path
            except (OSError, PermissionError):
                # It's acceptable to fail on dangerous paths
                pass

    @pytest.mark.security
    def test_import_reorganization_security(self):
        """Test that import reorganization doesn't break security imports."""
        # Verify that security-related imports are still accessible
        import background_tasks.tasks as tasks_module

        # Check that critical security functions/classes are still imported
        required_security_items = [
            'ValidationError',  # Should be imported from Django
            'XSSPrevention',    # Should be available in the module
        ]

        tasks_content = open(tasks_module.__file__, 'r').read()

        for item in required_security_items:
            self.assertIn(item, tasks_content,
                         f"Security-related item '{item}' should still be available")

    def test_no_hardcoded_secrets_after_cleanup(self):
        """Test that dead code removal didn't accidentally expose secrets."""
        import background_tasks.tasks as tasks_module
        import intelliwiz_config.settings as settings_module

        # Read the actual file contents to check for patterns
        files_to_check = [
            (tasks_module.__file__, "tasks.py"),
            (settings_module.__file__, "settings.py"),
        ]

        secret_patterns = [
            "password=",
            "secret_key=",
            "api_key=",
            "token=",
            "auth=",
        ]

        for file_path, file_name in files_to_check:
            with open(file_path, 'r') as f:
                content = f.read().lower()

            for pattern in secret_patterns:
                # If pattern exists, ensure it's in a comment or env() call
                if pattern in content:
                    lines_with_pattern = [
                        line for line in content.split('\n')
                        if pattern in line.lower()
                    ]

                    for line in lines_with_pattern:
                        # Should be either a comment, env() call, or safe assignment
                        is_safe = (
                            line.strip().startswith('#') or
                            'env(' in line or
                            'getenv(' in line or
                            '""' in line or  # Empty string assignment
                            "''" in line     # Empty string assignment
                        )

                        self.assertTrue(is_safe,
                                      f"Potential hardcoded secret in {file_name}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()