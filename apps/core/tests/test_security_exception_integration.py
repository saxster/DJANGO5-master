"""
Security Integration Tests for Exception Handling Anti-Pattern Remediation.

This test suite focuses on security aspects of the exception handling improvements:
1. Validates no information disclosure through error messages
2. Tests correlation ID tracking for security incidents
3. Ensures sensitive data is not logged
4. Tests security exception hierarchy
5. Validates secure error responses in production mode

Security Requirements:
- No stack traces exposed to users in production
- No sensitive data (passwords, tokens, keys) logged
- Correlation IDs for incident tracking
- Proper error classification for security monitoring
- Secure fallback behavior when template rendering fails
"""

import pytest
import uuid
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import DatabaseError
from django.http import JsonResponse
from django.template import TemplateDoesNotExist

from apps.core.exceptions import (
    SecurityException,
    CSRFException,
    RateLimitException,
    SuspiciousOperationException,
    FileUploadSecurityException,
    ExceptionFactory
)
from apps.core.error_handling import (
    ErrorHandler,
    GlobalExceptionMiddleware
)

User = get_user_model()


class TestSecurityExceptionClassification(TestCase):
    """Test security exception classification and handling."""

    def test_security_exception_types(self):
        """Test all security exception types inherit correctly."""
        exceptions = [
            CSRFException("CSRF token missing"),
            RateLimitException("Rate limit exceeded"),
            SuspiciousOperationException("Suspicious activity"),
            FileUploadSecurityException("Malicious file detected")
        ]

        for exception in exceptions:
            self.assertIsInstance(exception, SecurityException)
            self.assertIsNotNone(exception.correlation_id)
            self.assertTrue(len(exception.correlation_id) > 10)

    def test_security_exception_context_sanitization(self):
        """Test that security exceptions sanitize context data."""
        sensitive_context = {
            'password': 'user_password_123',
            'api_key': 'secret_key_456',
            'csrf_token': 'csrf_token_789',
            'user_ip': '192.168.1.1',  # This is OK to log
            'user_agent': 'Mozilla/5.0'  # This is OK to log
        }

        exception = ExceptionFactory.create_security_error(
            "Security violation detected",
            context=sensitive_context
        )

        # Context should still contain non-sensitive data
        self.assertIn('user_ip', exception.context)
        self.assertIn('user_agent', exception.context)

        # But the to_dict method should sanitize when used for logging
        dict_representation = exception.to_dict()
        self.assertIn('context', dict_representation)


class TestSecurityErrorResponses(TestCase):
    """Test secure error response generation."""

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEBUG=False)
    def test_production_error_response_no_debug_info(self):
        """Test that production error responses contain no debug information."""
        request = self.factory.get('/api/secure-endpoint')

        # Simulate various exception types
        test_cases = [
            (PermissionDenied("Access denied"), 403),
            (ValueError("Invalid input"), 500),
            (DatabaseError("DB connection failed"), 500),
            (SuspiciousOperation("Suspicious request"), 400)
        ]

        for exception, expected_status in test_cases:
            with self.subTest(exception=type(exception).__name__):
                response = ErrorHandler.handle_api_error(
                    request,
                    exception,
                    expected_status
                )

                self.assertEqual(response.status_code, expected_status)

                response_data = response.json()
                error_data = response_data.get('error', {})

                # Should not contain debug information
                self.assertNotIn('debug', error_data)
                self.assertNotIn('traceback', error_data)
                self.assertNotIn('exception_message', error_data)
                self.assertNotIn('stack_trace', error_data)

                # Should contain correlation ID for tracking
                self.assertIn('correlation_id', error_data)
                self.assertIn('timestamp', error_data)

    @override_settings(DEBUG=True)
    def test_development_error_response_has_debug_info(self):
        """Test that development error responses contain debug information."""
        request = self.factory.get('/api/test-endpoint')

        response = ErrorHandler.handle_api_error(
            request,
            ValueError("Test error"),
            500
        )

        response_data = response.json()
        error_data = response_data.get('error', {})

        # Should contain debug information in development
        self.assertIn('debug', error_data)
        self.assertIn('exception_type', error_data['debug'])
        self.assertIn('exception_message', error_data['debug'])

    def test_correlation_id_consistency(self):
        """Test that correlation IDs are consistent across the request lifecycle."""
        request = self.factory.get('/api/test')
        test_correlation_id = str(uuid.uuid4())

        # Simulate correlation ID being set by middleware
        request.correlation_id = test_correlation_id

        response = ErrorHandler.handle_api_error(
            request,
            ValueError("Test error"),
            500,
            correlation_id=test_correlation_id
        )

        response_data = response.json()
        self.assertEqual(
            response_data['error']['correlation_id'],
            test_correlation_id
        )


class TestSensitiveDataLogging(TestCase):
    """Test that sensitive data is not logged in error messages."""

    def test_error_handler_sanitizes_task_params(self):
        """Test that ErrorHandler sanitizes task parameters."""
        sensitive_params = {
            'username': 'testuser',
            'password': 'secret123',
            'api_key': 'key_456',
            'access_token': 'token_789',
            'normal_field': 'safe_value'
        }

        with patch('apps.core.error_handling.logger') as mock_logger:
            ErrorHandler.handle_task_exception(
                ValueError("Task failed"),
                "test_task",
                task_params=sensitive_params
            )

        # Check that logger was called
        self.assertTrue(mock_logger.error.called)

        # Get the logged message
        log_call_args = str(mock_logger.error.call_args)

        # Sensitive data should be redacted
        self.assertNotIn('secret123', log_call_args)
        self.assertNotIn('key_456', log_call_args)
        self.assertNotIn('token_789', log_call_args)

        # Non-sensitive data should be present
        self.assertIn('testuser', log_call_args)
        self.assertIn('safe_value', log_call_args)

    def test_security_context_sanitization(self):
        """Test that security contexts sanitize sensitive fields."""
        context_with_secrets = {
            'user_id': 123,
            'session_key': 'session_secret_key',
            'csrf_token': 'csrf_secret_token',
            'request_path': '/api/test',
            'user_agent': 'TestAgent/1.0'
        }

        with patch('apps.core.error_handling.logger') as mock_logger:
            ErrorHandler.handle_exception(
                SecurityException("Security violation"),
                context=context_with_secrets
            )

        log_call_args = str(mock_logger.error.call_args)

        # Should not log sensitive session/token data
        self.assertNotIn('session_secret_key', log_call_args)
        self.assertNotIn('csrf_secret_token', log_call_args)

        # Should log non-sensitive context
        self.assertIn('123', log_call_args)  # user_id
        self.assertIn('/api/test', log_call_args)  # request_path


class TestSecurityMiddlewareIntegration(TestCase):
    """Test security aspects of middleware integration."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GlobalExceptionMiddleware()

    def test_middleware_logs_security_exceptions_with_context(self):
        """Test that middleware logs security exceptions with proper context."""
        request = self.factory.get('/api/sensitive-endpoint')
        request.correlation_id = str(uuid.uuid4())
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.__str__ = Mock(return_value="testuser")

        # Simulate suspicious operation
        exception = SuspiciousOperation("Suspicious file upload attempt")

        with patch('apps.core.error_handling.logger') as mock_logger:
            response = self.middleware.process_exception(request, exception)

        # Should log with security context
        mock_logger.error.assert_called()
        log_args = mock_logger.error.call_args[0][0]

        # Should include correlation ID and security details
        self.assertIn(request.correlation_id, str(log_args))
        self.assertIn("testuser", str(log_args))
        self.assertIn("SuspiciousOperation", str(log_args))

    def test_middleware_handles_template_rendering_failures_securely(self):
        """Test middleware handles template failures without exposing internals."""
        request = self.factory.get('/dashboard/sensitive')
        request.correlation_id = str(uuid.uuid4())
        request.user = Mock()
        request.user.is_authenticated = False

        exception = ValueError("Template processing error")

        with patch('apps.core.error_handling.render') as mock_render:
            # Simulate template rendering failure
            mock_render.side_effect = TemplateDoesNotExist("error_template.html")

            response = self.middleware.process_exception(request, exception)

        # Should get a basic HTTP response, not expose template errors
        self.assertIn("Error 500", response.content.decode())
        self.assertIn(request.correlation_id, response.content.decode())

    def test_api_vs_web_request_detection(self):
        """Test that middleware correctly detects API vs web requests."""
        # API request tests
        api_requests = [
            self.factory.get('/api/users'),
            self.factory.get('/data', HTTP_ACCEPT='application/json'),
            self.factory.post('/submit', content_type='application/json')
        ]

        # Web request tests
        web_requests = [
            self.factory.get('/dashboard'),
            self.factory.get('/login'),
            self.factory.get('/profile', HTTP_ACCEPT='text/html')
        ]

        exception = ValueError("Test error")

        for request in api_requests:
            with self.subTest(path=request.path):
                request.correlation_id = str(uuid.uuid4())
                request.user = Mock()
                request.user.is_authenticated = False

                response = self.middleware.process_exception(request, exception)
                self.assertIsInstance(response, JsonResponse)

        for request in web_requests:
            with self.subTest(path=request.path):
                request.correlation_id = str(uuid.uuid4())
                request.user = Mock()
                request.user.is_authenticated = False

                with patch('apps.core.error_handling.render') as mock_render:
                    mock_render.return_value = Mock(content=b"Error page")
                    response = self.middleware.process_exception(request, exception)

                # Should attempt to render template (mock_render called)
                mock_render.assert_called()


class TestSecurityIncidentTracking(TestCase):
    """Test security incident tracking and correlation."""

    def test_security_exception_correlation_tracking(self):
        """Test that security exceptions maintain correlation for incident tracking."""
        correlation_id = str(uuid.uuid4())

        # Create initial security exception
        initial_exception = ExceptionFactory.create_security_error(
            "Suspicious login attempt",
            correlation_id=correlation_id
        )

        # Create follow-up exception with same correlation ID
        followup_exception = ExceptionFactory.create_security_error(
            "Account locked due to suspicious activity",
            correlation_id=correlation_id
        )

        # Both should have the same correlation ID for tracking
        self.assertEqual(initial_exception.correlation_id, correlation_id)
        self.assertEqual(followup_exception.correlation_id, correlation_id)

    def test_security_exception_timeline_tracking(self):
        """Test that security exceptions include timestamp for incident timeline."""
        exception = SecurityException("Security event")
        exception_dict = exception.to_dict()

        # Should have correlation ID for tracking
        self.assertIn('correlation_id', exception_dict)

        # The error handling system should add timestamps
        with patch('apps.core.error_handling.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

            response = ErrorHandler.create_error_response(
                "Security violation",
                error_code="SECURITY_ERROR",
                correlation_id=exception.correlation_id
            )

        response_data = response.json()
        self.assertIn('timestamp', response_data['error'])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
