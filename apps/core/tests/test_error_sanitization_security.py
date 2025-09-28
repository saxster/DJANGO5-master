"""
Error Sanitization Security Tests (Penetration Testing)

Addresses Issue #19: Inconsistent Error Message Sanitization
Comprehensive security tests to validate error response sanitization.

Test Coverage:
- Correlation ID presence validation
- Stack trace exposure prevention
- DEBUG mode information leakage
- Internal path disclosure
- Exception detail sanitization
- Factory pattern compliance

Complies with: .claude/rules.md Rule #5 (No Debug Information in Production)
"""

import pytest
import json
from django.test import TestCase, RequestFactory, override_settings
from django.http import JsonResponse
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, IntegrityError
from unittest.mock import patch, MagicMock

from apps.core.services.error_response_factory import ErrorResponseFactory
from apps.core.middleware.error_response_validation import ErrorResponseValidationMiddleware
from apps.core.error_handling import GlobalExceptionMiddleware, CorrelationIDMiddleware


@pytest.mark.security
class ErrorResponseFactoryTestCase(TestCase):
    """Test ErrorResponseFactory for secure error responses."""

    def test_api_error_includes_correlation_id(self):
        """Verify all API errors include correlation ID."""
        response = ErrorResponseFactory.create_api_error_response(
            error_code='VALIDATION_ERROR',
            message='Test error',
        )

        self.assertIsInstance(response, JsonResponse)
        content = json.loads(response.content)

        self.assertIn('error', content)
        self.assertIn('correlation_id', content['error'])
        self.assertIsNotNone(content['error']['correlation_id'])

    def test_api_error_never_exposes_exception_details(self):
        """Verify exception details are never exposed."""
        test_exceptions = [
            ValidationError("Detailed validation error with sensitive info"),
            DatabaseError("Connection to database 'prod_db' failed at line 123"),
            PermissionDenied("User 'admin' lacks permission 'secret_view'"),
        ]

        for exception in test_exceptions:
            with self.subTest(exception=type(exception).__name__):
                response = ErrorResponseFactory.from_exception(
                    exception=exception,
                    request_type='api',
                )

                content = json.loads(response.content)
                message = content['error']['message']

                self.assertNotIn('prod_db', message)
                self.assertNotIn('line 123', message)
                self.assertNotIn('admin', message)
                self.assertNotIn('secret_view', message)
                self.assertNotIn('sensitive info', message.lower())

    @override_settings(DEBUG=True)
    def test_no_debug_info_even_when_debug_true(self):
        """CRITICAL: Verify no debug info exposed even with DEBUG=True."""
        exception = ValidationError("Internal error details here")

        response = ErrorResponseFactory.from_exception(
            exception=exception,
            request_type='api',
        )

        content = json.loads(response.content)

        self.assertNotIn('debug', content)
        self.assertNotIn('exception_type', str(content))
        self.assertNotIn('exception_message', str(content))
        self.assertNotIn('traceback', str(content))
        self.assertNotIn('stack_trace', str(content))

    def test_validation_error_response_format(self):
        """Test validation error with field errors."""
        field_errors = {
            'email': ['Invalid email format'],
            'phone': ['Phone number required'],
        }

        response = ErrorResponseFactory.create_validation_error_response(
            field_errors=field_errors,
            request_type='api',
        )

        content = json.loads(response.content)

        self.assertEqual(content['success'], False)
        self.assertIn('field_errors', content['error'])
        self.assertEqual(len(content['error']['field_errors']), 2)
        self.assertIn('correlation_id', content['error'])

    def test_success_response_includes_correlation_id(self):
        """Verify success responses also include correlation IDs."""
        response = ErrorResponseFactory.create_success_response(
            data={'result': 'success'},
            message='Operation completed',
        )

        content = json.loads(response.content)

        self.assertEqual(content['success'], True)
        self.assertIn('correlation_id', content)
        self.assertIsNotNone(content['correlation_id'])


@pytest.mark.security
class ErrorValidationMiddlewareTestCase(TestCase):
    """Test error response validation middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = ErrorResponseValidationMiddleware()

    def test_middleware_detects_missing_correlation_id(self):
        """Test detection of missing correlation IDs."""
        error_response = JsonResponse(
            {'error': {'message': 'Test error'}},
            status=400
        )

        request = self.factory.get('/test/')
        request.correlation_id = 'test-correlation-123'

        validated_response = self.middleware.process_response(request, error_response)

        content = json.loads(validated_response.content)
        self.assertIn('correlation_id', content.get('error', content))

    def test_middleware_strips_stack_traces(self):
        """Test that stack traces are stripped from responses."""
        error_with_trace = JsonResponse({
            'error': {
                'message': 'Error',
                'traceback': 'File "/app/views.py", line 123, in view_func\n  raise Exception',
            }
        }, status=500)

        request = self.factory.get('/test/')
        request.correlation_id = 'test-123'

        validated_response = self.middleware.process_response(request, error_with_trace)

        content = json.loads(validated_response.content)
        error_str = json.dumps(content)

        self.assertNotIn('traceback', error_str.lower())
        self.assertNotIn('File "', error_str)
        self.assertNotIn('.py:', error_str)

    def test_middleware_logs_violations(self):
        """Test that validation violations are logged."""
        bad_response = JsonResponse({
            'error': {
                'message': 'Error',
                'debug': {'stack_trace': 'some trace'},
            }
        }, status=500)

        request = self.factory.get('/test/')
        request.correlation_id = 'test-123'

        with self.assertLogs('error_validation', level='WARNING') as cm:
            self.middleware.process_response(request, bad_response)

            log_output = ''.join(cm.output)
            self.assertIn('violations', log_output.lower())


@pytest.mark.security
class CorrelationIDComplianceTestCase(TestCase):
    """Test correlation ID compliance across error scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_all_error_codes_include_correlation_id(self):
        """Test all error code types include correlation IDs."""
        error_codes = [
            'VALIDATION_ERROR',
            'PERMISSION_DENIED',
            'DATABASE_ERROR',
            'RESOURCE_NOT_FOUND',
            'RATE_LIMIT_EXCEEDED',
            'FILE_UPLOAD_ERROR',
            'INTERNAL_ERROR',
        ]

        for error_code in error_codes:
            with self.subTest(error_code=error_code):
                response = ErrorResponseFactory.create_api_error_response(
                    error_code=error_code,
                )

                content = json.loads(response.content)
                self.assertIn('error', content)
                self.assertIn('correlation_id', content['error'])
                self.assertEqual(len(content['error']['correlation_id']), 36)

    def test_correlation_id_propagates_through_exception_chain(self):
        """Test correlation ID preserved through exception handling."""
        request = self.factory.get('/test/')
        correlation_middleware = CorrelationIDMiddleware()
        correlation_middleware.process_request(request)

        exception = ValidationError("Test error")

        response = ErrorResponseFactory.from_exception(
            exception=exception,
            request_type='api',
            correlation_id=request.correlation_id,
        )

        content = json.loads(response.content)
        self.assertEqual(
            content['error']['correlation_id'],
            request.correlation_id
        )


@pytest.mark.security
@override_settings(DEBUG=False)
class ProductionModeSecurityTestCase(TestCase):
    """Test error handling in production mode (DEBUG=False)."""

    def test_no_information_disclosure_in_production(self):
        """Verify no internal information in production errors."""
        exception = DatabaseError(
            "FATAL:  password authentication failed for user 'postgres'\n"
            "DETAIL:  Connection from 10.0.0.1 rejected"
        )

        response = ErrorResponseFactory.from_exception(
            exception=exception,
            request_type='api',
        )

        content = json.loads(response.content)
        error_message = content['error']['message']

        self.assertNotIn('postgres', error_message)
        self.assertNotIn('10.0.0.1', error_message)
        self.assertNotIn('FATAL', error_message)
        self.assertNotIn('password', error_message)

    def test_generic_message_for_unexpected_errors(self):
        """Verify generic messages for unexpected errors."""
        exception = RuntimeError("Internal server configuration error at module X")

        response = ErrorResponseFactory.from_exception(
            exception=exception,
            request_type='api',
        )

        content = json.loads(response.content)

        self.assertEqual(content['error']['code'], 'INTERNAL_ERROR')
        self.assertEqual(
            content['error']['message'],
            'An unexpected error occurred'
        )
        self.assertNotIn('module X', str(content))


@pytest.mark.security
class LogSanitizationIntegrationTestCase(TestCase):
    """Test integration of error responses with log sanitization."""

    def test_sensitive_data_sanitized_in_error_logs(self):
        """Verify sensitive data sanitized before logging."""
        exception = ValidationError(
            "Invalid email: user@company.com or phone: +1-555-1234"
        )

        with self.assertLogs('apps.core.services.error_response_factory', level='ERROR') as cm:
            ErrorResponseFactory.from_exception(
                exception=exception,
                request_type='api',
            )

            log_output = ''.join(cm.output)

            self.assertNotIn('user@company.com', log_output)
            self.assertNotIn('+1-555-1234', log_output)
            self.assertIn('[SANITIZED]', log_output)


__all__ = [
    'ErrorResponseFactoryTestCase',
    'ErrorValidationMiddlewareTestCase',
    'CorrelationIDComplianceTestCase',
    'ProductionModeSecurityTestCase',
    'LogSanitizationIntegrationTestCase',
]