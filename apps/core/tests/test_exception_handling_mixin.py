"""
Unit tests for ExceptionHandlingMixin

Tests the POST exception handling mixin that eliminates 800+ lines
of duplicated exception handling code.

Following .claude/rules.md:
- Validates specific exception handling (Rule 11)
- No debug info exposure (Rule 5)
- Correlation ID tracking
"""

import pytest
from django.test import TestCase, RequestFactory
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.db import IntegrityError, DatabaseError
from unittest.mock import Mock, patch

from apps.core.mixins import ExceptionHandlingMixin, with_exception_handling
from apps.core.exceptions import (
    ActivityManagementException,
    SystemException,
    BusinessLogicException,
)

User = get_user_model()


class TestView(ExceptionHandlingMixin):
    """Test view for mixin testing."""
    pass


@pytest.mark.unit
class ExceptionHandlingMixinTestCase(TestCase):
    """Test suite for ExceptionHandlingMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )
        self.view = TestView()

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_validation_error_returns_400(self, mock_error_handler):
        """Test ValidationError handling returns 400 status."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise ValidationError("Invalid data")

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertEqual(response.json()["error"], "Invalid form data")

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_activity_management_exception_returns_422(self, mock_error_handler):
        """Test ActivityManagementException returns 422 status."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise ActivityManagementException("Activity error")

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertEqual(response.status_code, 422)
        self.assertIn("correlation_id", response.json())

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_permission_denied_returns_403(self, mock_error_handler):
        """Test PermissionDenied returns 403 status."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise PermissionDenied()

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Access denied")

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_object_not_found_returns_404(self, mock_error_handler):
        """Test ObjectDoesNotExist returns 404 status."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise ObjectDoesNotExist()

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertEqual(response.status_code, 404)

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_value_error_returns_400(self, mock_error_handler):
        """Test ValueError returns 400 status."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise ValueError("Invalid value")

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid data format")

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_integrity_error_returns_422(self, mock_error_handler):
        """Test IntegrityError returns 422 status."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise IntegrityError("Duplicate key")

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "Database operation failed")

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_system_exception_returns_500(self, mock_error_handler):
        """Test SystemException returns 500 status."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise SystemException("System failure")

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"], "System error occurred")

    def test_no_debug_info_in_responses(self):
        """Test that stack traces are never exposed in responses (Rule 5)."""
        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise ValueError("Internal error with sensitive data: password=secret123")

        with patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception') as mock:
            mock.return_value = {"correlation_id": "test-123"}

            response = self.view.handle_exceptions(request, handler_with_error)

            response_data = response.json()
            self.assertNotIn("password=secret123", str(response_data))
            self.assertNotIn("stack_trace", response_data)
            self.assertNotIn("traceback", response_data)

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_correlation_id_always_present(self, mock_error_handler):
        """Test correlation ID is always included in error responses."""
        mock_error_handler.return_value = {"correlation_id": "test-correlation-123"}

        request = self.factory.post('/')
        request.user = self.user

        def handler_with_error(req):
            raise ValidationError("Test error")

        response = self.view.handle_exceptions(request, handler_with_error)

        self.assertIn("correlation_id", response.json())
        self.assertEqual(response.json()["correlation_id"], "test-correlation-123")


@pytest.mark.unit
class WithExceptionHandlingDecoratorTestCase(TestCase):
    """Test suite for with_exception_handling decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )

    def test_decorator_requires_mixin(self):
        """Test decorator raises TypeError if mixin not used."""
        class InvalidView:
            @with_exception_handling
            def post(self, request):
                return JsonResponse({"status": "ok"})

        view = InvalidView()
        request = self.factory.post('/')
        request.user = self.user

        with self.assertRaises(TypeError):
            view.post(request)

    @patch('apps.core.mixins.exception_handling_mixin.ErrorHandler.handle_exception')
    def test_decorator_handles_exceptions(self, mock_error_handler):
        """Test decorator properly handles exceptions."""
        mock_error_handler.return_value = {"correlation_id": "test-123"}

        class TestView(ExceptionHandlingMixin):
            @with_exception_handling
            def post(self, request):
                raise ValidationError("Test error")

        view = TestView()
        request = self.factory.post('/')
        request.user = self.user

        response = view.post(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("correlation_id", response.json())