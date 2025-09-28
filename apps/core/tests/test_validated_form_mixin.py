"""
Unit tests for ValidatedFormProcessingMixin

Tests the form processing mixin that eliminates 150+ lines
of duplicated form save patterns.

Following .claude/rules.md:
- Validates transaction management
- Tests error handling
- Verifies delegation to services
"""

import pytest
from django.test import TestCase, RequestFactory
from django.http import JsonResponse, QueryDict
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from apps.core.mixins import ValidatedFormProcessingMixin, StandardFormProcessingMixin

User = get_user_model()


class TestView(ValidatedFormProcessingMixin):
    """Test view for mixin testing."""

    crud_config = {
        "form": Mock,
        "model": Mock,
    }

    def process_valid_form(self, form, request, is_create):
        return {"pk": 1}

    def get_crud_config(self):
        return self.crud_config


@pytest.mark.unit
class ValidatedFormProcessingMixinTestCase(TestCase):
    """Test suite for ValidatedFormProcessingMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )
        self.view = TestView()

    def test_extract_form_data_from_direct_post(self):
        """Test extracting data from direct POST."""
        request = self.factory.post('/', {
            'field1': 'value1',
            'field2': 'value2'
        })
        request.user = self.user

        data = self.view.extract_form_data(request)

        self.assertIsInstance(data, QueryDict)

    def test_extract_form_data_from_formdata_parameter(self):
        """Test extracting data from formData parameter."""
        request = self.factory.post('/', {
            'formData': 'field1=value1&field2=value2'
        })
        request.user = self.user

        data = self.view.extract_form_data(request)

        self.assertIsInstance(data, QueryDict)
        self.assertIn('field1', data)

    def test_get_form_instance_create(self):
        """Test getting form instance for creation."""
        request = self.factory.post('/')
        request.user = self.user
        data = QueryDict('field1=value1')

        mock_form_class = Mock(return_value=Mock())
        self.view.crud_config = {"form": mock_form_class}

        form = self.view.get_form_instance(data, request)

        mock_form_class.assert_called_once_with(data, request=request)

    def test_get_form_instance_update(self):
        """Test getting form instance for update."""
        request = self.factory.post('/')
        request.user = self.user
        data = QueryDict('field1=value1')
        instance = Mock()

        mock_form_class = Mock(return_value=Mock())
        self.view.crud_config = {"form": mock_form_class}

        form = self.view.get_form_instance(data, request, instance=instance)

        mock_form_class.assert_called_once_with(data, request=request, instance=instance)

    def test_handle_valid_form_response_with_dict(self):
        """Test valid form response with dict result."""
        request = self.factory.post('/')
        request.user = self.user
        form = Mock()

        response = self.view.handle_valid_form_response(form, request, is_create=True)

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 200)

    def test_handle_valid_form_response_with_jsonresponse(self):
        """Test valid form response when process_valid_form returns JsonResponse."""
        request = self.factory.post('/')
        request.user = self.user
        form = Mock()

        expected_response = JsonResponse({"custom": "response"})

        class TestView2(ValidatedFormProcessingMixin):
            crud_config = {"form": Mock}

            def process_valid_form(self, form, request, is_create):
                return expected_response

            def get_crud_config(self):
                return self.crud_config

        view = TestView2()
        response = view.handle_valid_form_response(form, request, is_create=True)

        self.assertEqual(response, expected_response)

    @patch('apps.core.mixins.validated_form_mixin.utils.handle_invalid_form')
    def test_handle_invalid_form_response(self, mock_handle_invalid):
        """Test invalid form response handling."""
        request = self.factory.post('/')
        request.user = self.user
        form = Mock()
        form.errors = {"field1": ["Error message"]}
        config = {"model": Mock}

        mock_handle_invalid.return_value = JsonResponse({"errors": form.errors}, status=400)

        response = self.view.handle_invalid_form_response(form, request, config)

        mock_handle_invalid.assert_called_once()

    def test_process_valid_form_not_implemented(self):
        """Test that process_valid_form must be implemented."""

        class IncompleteView(ValidatedFormProcessingMixin):
            crud_config = {"form": Mock}

            def get_crud_config(self):
                return self.crud_config

        view = IncompleteView()
        form = Mock()
        request = Mock()

        with self.assertRaises(NotImplementedError):
            view.process_valid_form(form, request, is_create=True)


@pytest.mark.unit
class StandardFormProcessingMixinTestCase(TestCase):
    """Test suite for StandardFormProcessingMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )

    @patch('apps.core.mixins.validated_form_mixin.putils.save_userinfo')
    @patch('apps.core.mixins.validated_form_mixin.transaction.atomic')
    def test_process_valid_form_create(self, mock_atomic, mock_save_userinfo):
        """Test standard form processing for creation."""

        class TestView(StandardFormProcessingMixin):
            crud_config = {"form": Mock, "model": Mock}

            def get_crud_config(self):
                return self.crud_config

            def save_model(self, form, request, is_create):
                instance = Mock()
                instance.id = 1
                return instance

        view = TestView()
        request = self.factory.post('/')
        request.user = self.user
        request.session = {}

        form = Mock()
        mock_instance = Mock()
        mock_instance.id = 1
        mock_save_userinfo.return_value = mock_instance

        mock_atomic.return_value.__enter__ = Mock()
        mock_atomic.return_value.__exit__ = Mock(return_value=False)

        response = view.process_valid_form(form, request, is_create=True)

        self.assertIsInstance(response, JsonResponse)

    def test_save_model_default_implementation(self):
        """Test default save_model calls form.save()."""

        class TestView(StandardFormProcessingMixin):
            crud_config = {"form": Mock, "model": Mock}

            def get_crud_config(self):
                return self.crud_config

        view = TestView()
        form = Mock()
        mock_instance = Mock()
        form.save.return_value = mock_instance

        result = view.save_model(form, Mock(), is_create=True)

        form.save.assert_called_once()
        self.assertEqual(result, mock_instance)

    def test_get_success_response_data_default(self):
        """Test default success response data."""

        class TestView(StandardFormProcessingMixin):
            crud_config = {"form": Mock, "model": Mock}

            def get_crud_config(self):
                return self.crud_config

        view = TestView()
        instance = Mock()
        instance.id = 42

        data = view.get_success_response_data(instance, Mock())

        self.assertEqual(data, {"pk": 42})