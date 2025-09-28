"""
Comprehensive tests for secure error handling utilities.
Tests that ErrorHandler prevents information disclosure and provides secure responses.
"""

import json
from django.test import TestCase
from django.http import JsonResponse
from apps.core.error_handling import ErrorHandler


class SecureErrorHandlerTest(TestCase):
    """Test secure error handling functionality"""

    def test_create_secure_task_response_success(self):
        """Test secure task response creation for successful operations"""
        response = ErrorHandler.create_secure_task_response(
            success=True,
            message="Operation completed successfully",
            data={"result": "test_data"}
        )

        # Verify response structure
        self.assertIsInstance(response, dict)
        self.assertTrue(response["success"])
        self.assertEqual(response["message"], "Operation completed successfully")
        self.assertEqual(response["data"]["result"], "test_data")
        self.assertIn("correlation_id", response)
        self.assertIn("timestamp", response)

        # Verify no sensitive information
        self.assertNotIn("traceback", response)
        self.assertNotIn("exception", response)

    def test_create_secure_task_response_failure(self):
        """Test secure task response creation for failed operations"""
        response = ErrorHandler.create_secure_task_response(
            success=False,
            message="Operation failed",
            error_code="VALIDATION_ERROR"
        )

        # Verify response structure
        self.assertFalse(response["success"])
        self.assertEqual(response["message"], "Operation failed")
        self.assertEqual(response["error_code"], "VALIDATION_ERROR")

        # Verify no sensitive information is exposed
        self.assertNotIn("traceback", response)
        self.assertNotIn("exception", response)
        self.assertNotIn("stack_trace", response)

    def test_correlation_id_generation(self):
        """Test correlation ID is properly generated"""
        response1 = ErrorHandler.create_secure_task_response()
        response2 = ErrorHandler.create_secure_task_response()

        # Both should have correlation IDs
        self.assertIn("correlation_id", response1)
        self.assertIn("correlation_id", response2)

        # Correlation IDs should be unique
        self.assertNotEqual(response1["correlation_id"], response2["correlation_id"])

        # Should be valid UUID format
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        )
        self.assertTrue(uuid_pattern.match(response1["correlation_id"]))

    def test_custom_correlation_id(self):
        """Test custom correlation ID is used when provided"""
        custom_id = "custom-correlation-123"
        response = ErrorHandler.create_secure_task_response(
            correlation_id=custom_id
        )

        self.assertEqual(response["correlation_id"], custom_id)

    @patch('apps.core.error_handling.logger')
    def test_handle_exception_logging(self, mock_logger):
        """Test exception handling with proper logging"""
        test_exception = ValueError("Test exception for logging")
        context = {"user_id": 123, "action": "test_action"}

        correlation_id = ErrorHandler.handle_exception(
            test_exception,
            context=context
        )

        # Verify logging occurred
        mock_logger.error.assert_called_once()

        # Verify correlation ID is returned
        self.assertIsInstance(correlation_id, str)

    @patch('apps.core.error_handling.logger')
    def test_handle_exception_no_stack_trace_in_return(self, mock_logger):
        """Test exception handling doesn't return stack traces"""
        test_exception = RuntimeError("Sensitive error message")

        correlation_id = ErrorHandler.handle_exception(test_exception)

        # Only correlation ID should be returned, no sensitive info
        self.assertIsInstance(correlation_id, str)

        # Logger should be called with full details for debugging
        mock_logger.error.assert_called_once()

    def test_handle_task_exception_secure_response(self):
        """Test task exception handling produces secure responses"""
        test_exception = Exception("Database connection failed")
        task_params = {"user_id": 123, "api_key": "secret123"}

        with patch('apps.core.error_handling.logger') as mock_logger:
            response = ErrorHandler.handle_task_exception(
                test_exception,
                task_name="test_task",
                task_params=task_params
            )

        # Verify secure response format
        self.assertIsInstance(response, dict)
        self.assertFalse(response["success"])
        self.assertEqual(response["message"], "Task execution failed")
        self.assertEqual(response["error_code"], "TASK_EXECUTION_ERROR")
        self.assertIn("correlation_id", response)

        # Verify no sensitive information in response
        self.assertNotIn("traceback", response)
        self.assertNotIn("exception", response)
        self.assertNotIn("api_key", str(response))
        self.assertNotIn("Database connection failed", str(response))

        # Verify logging occurred with full details
        mock_logger.error.assert_called_once()

    def test_sanitize_task_params_sensitive_data(self):
        """Test task parameters are sanitized to remove sensitive data"""
        sensitive_params = {
            "user_id": 123,
            "password": "secret123",
            "api_key": "sk-1234567890",
            "access_token": "token123",
            "normal_field": "normal_value"
        }

        sanitized = ErrorHandler._sanitize_task_params(sensitive_params)

        # Sensitive fields should be redacted
        self.assertEqual(sanitized["password"], "[REDACTED]")
        self.assertEqual(sanitized["api_key"], "[REDACTED]")
        self.assertEqual(sanitized["access_token"], "[REDACTED]")

        # Normal fields should be preserved
        self.assertEqual(sanitized["user_id"], 123)
        self.assertEqual(sanitized["normal_field"], "normal_value")

    def test_sanitize_task_params_nested_data(self):
        """Test task parameter sanitization handles nested data"""
        nested_params = {
            "config": {
                "secret": "hidden_value",
                "normal": "visible_value"
            },
            "list_data": [1, 2, 3]
        }

        sanitized = ErrorHandler._sanitize_task_params(nested_params)

        # Nested secret should be redacted
        self.assertEqual(sanitized["secret"], "[REDACTED]")

        # Complex types should be summarized
        self.assertEqual(sanitized["config"], "<dict>")
        self.assertEqual(sanitized["list_data"], "<list>")

    def test_sanitize_task_params_non_dict(self):
        """Test task parameter sanitization handles non-dict inputs"""
        non_dict_inputs = [
            "string_param",
            123,
            ["list", "param"],
            None
        ]

        for input_data in non_dict_inputs:
            result = ErrorHandler._sanitize_task_params(input_data)
            self.assertIsInstance(result, dict)
            self.assertIn("params", result)

    def test_safe_execute_with_success(self):
        """Test safe execution wrapper with successful function"""
        def successful_function():
            return "success_result"

        result = ErrorHandler.safe_execute(successful_function)
        self.assertEqual(result, "success_result")

    @patch('apps.core.error_handling.ErrorHandler.handle_exception')
    def test_safe_execute_with_exception(self, mock_handle_exception):
        """Test safe execution wrapper with failing function"""
        def failing_function():
            raise ValueError("Function failed")

        default_return = "default_value"
        result = ErrorHandler.safe_execute(
            failing_function,
            default_return=default_return
        )

        # Should return default value
        self.assertEqual(result, default_return)

        # Should handle exception
        mock_handle_exception.assert_called_once()

    def test_safe_execute_specific_exceptions(self):
        """Test safe execution only catches specified exception types"""
        def failing_function():
            raise KeyError("Key not found")

        # Should catch KeyError
        result = ErrorHandler.safe_execute(
            failing_function,
            exception_types=(KeyError,),
            default_return="caught"
        )
        self.assertEqual(result, "caught")

        # Should not catch other exceptions
        def other_failing_function():
            raise ValueError("Different error")

        with self.assertRaises(ValueError):
            ErrorHandler.safe_execute(
                other_failing_function,
                exception_types=(KeyError,)
            )

    def test_create_error_response_format(self):
        """Test error response creation has correct format"""
        response = ErrorHandler.create_error_response(
            message="Test error message",
            error_code="TEST_ERROR",
            status_code=400
        )

        # Should return JsonResponse
        self.assertIsInstance(response, JsonResponse)

        # Verify response content structure
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"]["message"], "Test error message")
        self.assertEqual(response_data["error"]["code"], "TEST_ERROR")
        self.assertIn("correlation_id", response_data["error"])
        self.assertIn("timestamp", response_data["error"])

    def test_create_error_response_no_details_exposure(self):
        """Test error response doesn't expose internal details"""
        response = ErrorHandler.create_error_response(
            message="Database error",
            details={"internal": "sensitive_info"}
        )

        response_data = json.loads(response.content)

        # Should include details in response
        self.assertIn("details", response_data["error"])

        # But should not expose stack traces or internal exceptions
        self.assertNotIn("traceback", response_data["error"])
        self.assertNotIn("exception", response_data["error"])


class ErrorHandlerSecurityTest(TestCase):
    """Security-focused tests for error handling"""

    def test_no_stack_trace_leakage_in_responses(self):
        """Test stack traces are never included in responses"""
        try:
            # Generate an exception with stack trace
            raise RuntimeError("Intentional test exception")
        except Exception as e:
            response = ErrorHandler.handle_task_exception(
                e,
                task_name="security_test",
                task_params={"test": "data"}
            )

        # Response should not contain stack trace
        response_str = json.dumps(response)
        self.assertNotIn("Traceback", response_str)
        self.assertNotIn("File \"/", response_str)
        self.assertNotIn(".py\", line", response_str)

    def test_sensitive_parameter_redaction(self):
        """Test sensitive parameters are properly redacted"""
        sensitive_keys = [
            'password', 'passwd', 'pwd', 'secret', 'key', 'token',
            'auth', 'credential', 'cert', 'api_key', 'access_token'
        ]

        for sensitive_key in sensitive_keys:
            params = {sensitive_key: "sensitive_value", "normal": "normal_value"}

            sanitized = ErrorHandler._sanitize_task_params(params)

            self.assertEqual(sanitized[sensitive_key], "[REDACTED]")
            self.assertEqual(sanitized["normal"], "normal_value")

    def test_case_insensitive_sensitive_detection(self):
        """Test sensitive data detection is case insensitive"""
        case_variations = {
            "PASSWORD": "secret123",
            "Password": "secret123",
            "API_KEY": "key123",
            "Access_Token": "token123"
        }

        sanitized = ErrorHandler._sanitize_task_params(case_variations)

        # All should be redacted regardless of case
        for key in case_variations:
            self.assertEqual(sanitized[key], "[REDACTED]")

    def test_error_correlation_tracking(self):
        """Test error correlation IDs enable proper tracking"""
        custom_correlation = "security-test-123"

        response = ErrorHandler.create_secure_task_response(
            success=False,
            correlation_id=custom_correlation
        )

        self.assertEqual(response["correlation_id"], custom_correlation)

        # Multiple responses with same correlation ID should be linkable
        response2 = ErrorHandler.create_secure_task_response(
            success=True,
            correlation_id=custom_correlation
        )

        self.assertEqual(response2["correlation_id"], custom_correlation)

    @patch('apps.core.error_handling.logger')
    def test_detailed_logging_vs_safe_response(self, mock_logger):
        """Test detailed logging occurs while response stays safe"""
        sensitive_exception = Exception("Database password: secret123")
        sensitive_params = {"db_password": "secret123", "user": "admin"}

        response = ErrorHandler.handle_task_exception(
            sensitive_exception,
            task_name="database_task",
            task_params=sensitive_params
        )

        # Response should be safe
        response_str = json.dumps(response)
        self.assertNotIn("secret123", response_str)
        self.assertNotIn("password", response_str.lower())

        # But logging should have occurred with details
        mock_logger.error.assert_called_once()

    def test_xss_prevention_in_error_messages(self):
        """Test XSS prevention in error messages"""
        xss_message = "<script>alert('xss')</script>"

        response = ErrorHandler.create_error_response(message=xss_message)
        response_data = json.loads(response.content)

        # XSS should be prevented (message should be escaped or sanitized)
        error_message = response_data["error"]["message"]
        self.assertNotIn("<script>", error_message)

    def test_json_injection_prevention(self):
        """Test JSON injection prevention in responses"""
        injection_attempt = '"; alert("xss"); "'

        response = ErrorHandler.create_secure_task_response(
            success=False,
            message=injection_attempt
        )

        # Should produce valid JSON
        json_str = json.dumps(response)
        parsed = json.loads(json_str)

        # Should not break JSON structure
        self.assertIsInstance(parsed, dict)
        self.assertIn("message", parsed)


class ErrorHandlerPerformanceTest(TestCase):
    """Performance tests for error handling"""

    def test_error_handling_performance(self):
        """Test error handling has minimal performance impact"""
        import time

        # Measure time for multiple error handlings
        start_time = time.time()

        for _ in range(1000):
            try:
                raise ValueError("Test exception")
            except Exception as e:
                ErrorHandler.handle_exception(e)

        end_time = time.time()

        avg_time = (end_time - start_time) / 1000

        # Should handle errors quickly (less than 1ms per error)
        self.assertLess(avg_time, 0.001)

    def test_secure_response_generation_performance(self):
        """Test secure response generation is fast"""
        import time

        start_time = time.time()

        for _ in range(1000):
            ErrorHandler.create_secure_task_response(
                success=False,
                message="Test message",
                error_code="TEST_ERROR"
            )

        end_time = time.time()

        avg_time = (end_time - start_time) / 1000

        # Should generate responses quickly (less than 0.1ms per response)
        self.assertLess(avg_time, 0.0001)


class ErrorHandlerIntegrationTest(TestCase):
    """Integration tests for error handling in full application context"""

    def test_task_error_handling_integration(self):
        """Test error handling integrates properly with background tasks"""
        # This would test integration with actual Celery tasks
        # For now, we test the interface compatibility

        mock_task = Mock()
        mock_task.retry = Mock()

        # Test that our error handling works with task context
        try:
            raise Exception("Integration test exception")
        except Exception as e:
            response = ErrorHandler.handle_task_exception(
                e,
                task_name="integration_test",
                task_params={"test": True}
            )

        # Should produce properly formatted response
        self.assertIsInstance(response, dict)
        self.assertIn("success", response)
        self.assertIn("correlation_id", response)

    def test_middleware_error_handling_compatibility(self):
        """Test error handling works with Django middleware"""
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = "POST"
        request.path = "/test/"

        # Test creating error response for middleware
        response = ErrorHandler.create_error_response(
            message="Middleware error",
            status_code=500
        )

        # Should be valid Django response
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 500)

    @patch('apps.core.error_handling.logger')
    def test_logging_integration(self, mock_logger):
        """Test error handling integrates with Django logging"""
        test_exception = RuntimeError("Logging integration test")

        ErrorHandler.handle_exception(
            test_exception,
            context={"request_id": "test-123"},
            level="critical"
        )

        # Should use the correct logging level
        mock_logger.critical.assert_called_once()

    def test_concurrent_error_handling(self):
        """Test error handling works correctly under concurrent load"""
        import threading
        import queue

        results = queue.Queue()

        def generate_error():
            try:
                raise ValueError("Concurrent test error")
            except Exception as e:
                response = ErrorHandler.handle_task_exception(
                    e,
                    task_name="concurrent_test"
                )
                results.put(response)

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=generate_error)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify all errors were handled correctly
        self.assertEqual(results.qsize(), 10)

        correlation_ids = set()
        while not results.empty():
            response = results.get()
            self.assertIn("correlation_id", response)
            correlation_ids.add(response["correlation_id"])

        # All correlation IDs should be unique
        self.assertEqual(len(correlation_ids), 10)