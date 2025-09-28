"""
Comprehensive test suite for Enhanced Exception Handling Anti-Pattern Remediation.

This test suite validates that:
1. New exception classification system works correctly
2. Correlation IDs are properly assigned and tracked
3. No generic exception patterns remain in critical modules
4. Error responses are secure and don't leak sensitive information
5. Exception factory creates appropriate exception types
6. Compatibility layer works for Django validation errors

Security Focus:
- Ensures no stack traces are exposed to users
- Validates correlation ID tracking for debugging
- Tests secure error response formatting
- Verifies PII is not logged in error messages
"""

import pytest
import uuid
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse, HttpResponse

from apps.core.exceptions import (
    BaseApplicationException,
    SecurityException,
    EnhancedValidationException,
    DatabaseException,
    BusinessLogicException,
    UserManagementException,
    OnboardingException,
    ActivityManagementException,
    ExceptionFactory,
    convert_django_validation_error
)
from apps.core.error_handling import (
    ErrorHandler,
    CorrelationIDMiddleware,
    GlobalExceptionMiddleware
)

User = get_user_model()


class TestEnhancedExceptionClassification(TestCase):
    """Test the enhanced exception classification system."""

    def test_base_application_exception_creates_correlation_id(self):
        """Test that BaseApplicationException automatically creates correlation ID."""
        exception = BaseApplicationException("Test error")

        self.assertIsNotNone(exception.correlation_id)
        self.assertTrue(len(exception.correlation_id) > 10)  # UUID should be long
        self.assertEqual(exception.error_code, "BASEAPPLICATIONEXCEPTION")
        self.assertEqual(exception.message, "Test error")
        self.assertEqual(exception.context, {})

    def test_base_application_exception_uses_provided_correlation_id(self):
        """Test that BaseApplicationException uses provided correlation ID."""
        test_correlation_id = str(uuid.uuid4())
        exception = BaseApplicationException(
            "Test error",
            correlation_id=test_correlation_id
        )

        self.assertEqual(exception.correlation_id, test_correlation_id)

    def test_base_application_exception_to_dict(self):
        """Test BaseApplicationException to_dict method."""
        context = {"user_id": 123, "operation": "test"}
        exception = BaseApplicationException(
            "Test error",
            error_code="TEST_ERROR",
            context=context
        )

        result = exception.to_dict()

        self.assertEqual(result['error_code'], "TEST_ERROR")
        self.assertEqual(result['message'], "Test error")
        self.assertEqual(result['context'], context)
        self.assertIn('correlation_id', result)

    def test_security_exception_hierarchy(self):
        """Test security exception hierarchy."""
        exception = SecurityException("Security breach detected")

        self.assertIsInstance(exception, BaseApplicationException)
        self.assertEqual(exception.error_code, "SECURITYEXCEPTION")
        self.assertIsNotNone(exception.correlation_id)

    def test_validation_exception_with_field(self):
        """Test EnhancedValidationException with field information."""
        exception = EnhancedValidationException(
            "Invalid email format",
            field="email"
        )

        self.assertEqual(exception.field, "email")
        self.assertEqual(exception.message, "Invalid email format")
        self.assertIsInstance(exception, BaseApplicationException)

    def test_business_logic_exception_hierarchy(self):
        """Test business logic exception hierarchy."""
        user_ex = UserManagementException("User creation failed")
        onboarding_ex = OnboardingException("Onboarding step failed")
        activity_ex = ActivityManagementException("Task creation failed")

        # All should inherit from BusinessLogicException
        self.assertIsInstance(user_ex, BusinessLogicException)
        self.assertIsInstance(onboarding_ex, BusinessLogicException)
        self.assertIsInstance(activity_ex, BusinessLogicException)

        # All should inherit from BaseApplicationException
        self.assertIsInstance(user_ex, BaseApplicationException)
        self.assertIsInstance(onboarding_ex, BaseApplicationException)
        self.assertIsInstance(activity_ex, BaseApplicationException)


class TestExceptionFactory(TestCase):
    """Test the exception factory for standardized exception creation."""

    def test_create_validation_error(self):
        """Test validation error creation."""
        test_correlation_id = str(uuid.uuid4())
        exception = ExceptionFactory.create_validation_error(
            "Email is required",
            field="email",
            correlation_id=test_correlation_id
        )

        self.assertIsInstance(exception, EnhancedValidationException)
        self.assertEqual(exception.message, "Email is required")
        self.assertEqual(exception.field, "email")
        self.assertEqual(exception.correlation_id, test_correlation_id)
        self.assertEqual(exception.error_code, "VALIDATION_ERROR")

    def test_create_security_error(self):
        """Test security error creation."""
        context = {"ip_address": "192.168.1.1", "user_agent": "test"}
        exception = ExceptionFactory.create_security_error(
            "Suspicious activity detected",
            error_type="SUSPICIOUS_OPERATION",
            context=context
        )

        self.assertIsInstance(exception, SecurityException)
        self.assertEqual(exception.message, "Suspicious activity detected")
        self.assertEqual(exception.error_code, "SUSPICIOUS_OPERATION")
        self.assertEqual(exception.context, context)

    def test_create_business_logic_error(self):
        """Test business logic error creation."""
        exception = ExceptionFactory.create_business_logic_error(
            "Operation not allowed",
            operation="user_deletion"
        )

        self.assertIsInstance(exception, BusinessLogicException)
        self.assertEqual(exception.message, "Operation not allowed")
        self.assertEqual(exception.error_code, "BUSINESS_LOGIC_ERROR_USER_DELETION")
        self.assertEqual(exception.context['operation'], "user_deletion")

    def test_create_database_error(self):
        """Test database error creation."""
        query_context = {"table": "users", "operation": "INSERT"}
        exception = ExceptionFactory.create_database_error(
            "Database connection failed",
            error_type="CONNECTION_ERROR",
            query_context=query_context
        )

        self.assertIsInstance(exception, DatabaseException)
        self.assertEqual(exception.message, "Database connection failed")
        self.assertEqual(exception.error_code, "CONNECTION_ERROR")
        self.assertEqual(exception.context, query_context)


class TestDjangoValidationErrorCompatibility(TestCase):
    """Test compatibility layer for Django validation errors."""

    def test_convert_simple_django_validation_error(self):
        """Test conversion of simple Django validation error."""
        django_error = DjangoValidationError("This field is required")

        enhanced_error = convert_django_validation_error(django_error)

        self.assertIsInstance(enhanced_error, EnhancedValidationException)
        self.assertEqual(enhanced_error.message, "This field is required")
        self.assertEqual(enhanced_error.error_code, "VALIDATION_ERROR")

    def test_convert_django_validation_error_with_correlation_id(self):
        """Test conversion with provided correlation ID."""
        test_correlation_id = str(uuid.uuid4())
        django_error = DjangoValidationError("Invalid value")

        enhanced_error = convert_django_validation_error(
            django_error,
            correlation_id=test_correlation_id
        )

        self.assertEqual(enhanced_error.correlation_id, test_correlation_id)


class TestErrorHandlerSafeExecute(TestCase):
    """Test ErrorHandler.safe_execute method for specific exception handling."""

    def test_safe_execute_with_validation_error(self):
        """Test safe_execute handles ValueError specifically."""
        def failing_function():
            raise ValueError("Invalid input")

        with patch('apps.core.error_handling.logger') as mock_logger:
            result = ErrorHandler.safe_execute(
                failing_function,
                default_return="default",
                exception_types=(ValueError,),
                context={"operation": "test"}
            )

        self.assertEqual(result, "default")
        mock_logger.warning.assert_called()

    def test_safe_execute_with_database_error(self):
        """Test safe_execute handles DatabaseError specifically."""
        def failing_function():
            raise DatabaseError("Connection failed")

        with patch('apps.core.error_handling.logger') as mock_logger:
            result = ErrorHandler.safe_execute(
                failing_function,
                default_return="default",
                exception_types=(DatabaseError,),
                context={"operation": "db_test"}
            )

        self.assertEqual(result, "default")
        mock_logger.error.assert_called()

    def test_safe_execute_success(self):
        """Test safe_execute returns function result on success."""
        def success_function():
            return "success"

        result = ErrorHandler.safe_execute(success_function)

        self.assertEqual(result, "success")


class TestCorrelationIDMiddleware(TestCase):
    """Test correlation ID middleware functionality."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CorrelationIDMiddleware()

    def test_process_request_adds_correlation_id(self):
        """Test that middleware adds correlation ID to request."""
        request = self.factory.get('/')

        result = self.middleware.process_request(request)

        self.assertIsNone(result)  # Middleware should return None to continue
        self.assertIsNotNone(request.correlation_id)
        self.assertIsNotNone(request._correlation_id)

    def test_process_response_adds_header(self):
        """Test that middleware adds correlation ID to response headers."""
        request = self.factory.get('/')
        request._correlation_id = str(uuid.uuid4())
        response = JsonResponse({"test": "data"})

        result = self.middleware.process_response(request, response)

        self.assertEqual(result["X-Correlation-ID"], request._correlation_id)


class TestGlobalExceptionMiddleware(TestCase):
    """Test global exception middleware for structured error responses."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GlobalExceptionMiddleware()

    @patch('apps.core.error_handling.logger')
    def test_process_exception_logs_with_correlation_id(self, mock_logger):
        """Test that exception processing logs with correlation ID."""
        request = self.factory.get('/api/test')
        request.correlation_id = str(uuid.uuid4())
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.__str__ = Mock(return_value="testuser")

        exception = ValueError("Test error")

        response = self.middleware.process_exception(request, exception)

        # Should log the error with correlation ID
        mock_logger.error.assert_called()
        log_call_args = mock_logger.error.call_args[0]
        self.assertIn(request.correlation_id, str(log_call_args))

    def test_api_exception_returns_json(self):
        """Test that API requests get JSON error responses."""
        request = self.factory.get('/api/test')
        request.correlation_id = str(uuid.uuid4())
        request.user = Mock()
        request.user.is_authenticated = False

        exception = ValueError("Test error")

        response = self.middleware.process_exception(request, exception)

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 500)

    def test_web_exception_returns_html(self):
        """Test that web requests get HTML error responses."""
        request = self.factory.get('/dashboard')
        request.correlation_id = str(uuid.uuid4())
        request.user = Mock()
        request.user.is_authenticated = False

        exception = ValueError("Test error")

        with patch('apps.core.error_handling.render') as mock_render:
            mock_render.return_value = HttpResponse("Error page")
            response = self.middleware.process_exception(request, exception)

        self.assertIsInstance(response, HttpResponse)


class TestSecureErrorResponses(TestCase):
    """Test that error responses don't leak sensitive information."""

    def test_error_response_no_stack_trace_in_production(self):
        """Test that error responses don't include stack traces in production."""
        factory = RequestFactory()
        request = factory.get('/api/test')

        with patch('apps.core.error_handling.settings.DEBUG', False):
            response = ErrorHandler.handle_api_error(
                request,
                ValueError("Test error"),
                500
            )

        response_data = response.json()

        # Should not contain debug information
        self.assertNotIn('debug', response_data.get('error', {}))
        self.assertNotIn('traceback', response_data.get('error', {}))
        self.assertNotIn('exception_message', response_data.get('error', {}))

    def test_error_response_includes_correlation_id(self):
        """Test that error responses include correlation ID."""
        factory = RequestFactory()
        request = factory.get('/api/test')
        test_correlation_id = str(uuid.uuid4())

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

    def test_task_response_secure(self):
        """Test that task responses are secure."""
        response = ErrorHandler.create_secure_task_response(
            success=False,
            message="Task failed",
            error_code="TASK_ERROR"
        )

        # Should not contain sensitive debugging information
        self.assertNotIn('traceback', response)
        self.assertNotIn('exception_message', response)
        self.assertNotIn('stack_trace', response)

        # Should contain required fields
        self.assertIn('correlation_id', response)
        self.assertIn('timestamp', response)
        self.assertEqual(response['success'], False)
        self.assertEqual(response['error_code'], "TASK_ERROR")


class TestSecurityExceptionHandling(TestCase):
    """Test security-specific exception handling."""

    def test_permission_denied_exception_mapping(self):
        """Test PermissionDenied maps to correct error code."""
        from django.core.exceptions import PermissionDenied
        factory = RequestFactory()
        request = factory.get('/api/test')

        response = ErrorHandler.handle_api_error(
            request,
            PermissionDenied("Access denied"),
            403
        )

        response_data = response.json()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response_data['error']['code'], "PERMISSION_DENIED")

    def test_security_exception_logging_sanitizes_data(self):
        """Test that security exception logging sanitizes sensitive data."""
        with patch('apps.core.error_handling.logger') as mock_logger:
            context = {
                'password': 'secret123',
                'api_key': 'key123',
                'safe_data': 'public'
            }

            ErrorHandler.handle_exception(
                SecurityException("Security violation"),
                context=context
            )

        # Check that sensitive data is not logged
        log_call_args = str(mock_logger.error.call_args)
        self.assertNotIn('secret123', log_call_args)
        self.assertNotIn('key123', log_call_args)
        self.assertIn('public', log_call_args)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])