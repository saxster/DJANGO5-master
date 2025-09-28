"""
Unit tests for CRUDActionMixin

Tests the GET action routing mixin that eliminates 500+ lines
of duplicated code.

Following .claude/rules.md:
- Comprehensive test coverage
- Specific exception handling validation
- Edge case coverage
"""

import pytest
from django.test import TestCase, RequestFactory
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from apps.core.mixins import CRUDActionMixin
from apps.activity.models.asset_model import Asset
from apps.activity.forms.asset_form import AssetForm

User = get_user_model()


class TestView(CRUDActionMixin):
    """Test view class for mixin testing."""

    crud_config = {
        "template_list": "test/list.html",
        "template_form": "test/form.html",
        "model": Asset,
        "form": AssetForm,
        "form_name": "testform",
        "related": ["parent", "location"],
        "fields": ["assetcode", "assetname"],
        "list_method": "get_assetlistview",
    }


@pytest.mark.unit
class CRUDActionMixinTestCase(TestCase):
    """Test suite for CRUDActionMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )
        self.view = TestView()

    def test_get_crud_config_uses_P_attribute(self):
        """Test that get_crud_config prefers P over crud_config."""
        view = TestView()
        view.P = {"model": Mock()}
        config = view.get_crud_config()
        self.assertEqual(config, view.P)

    def test_get_crud_config_fallback_to_params(self):
        """Test fallback to params attribute."""
        view = TestView()
        view.params = {"model": Mock()}
        config = view.get_crud_config()
        self.assertEqual(config, view.params)

    def test_get_crud_config_uses_crud_config(self):
        """Test default to crud_config."""
        view = TestView()
        config = view.get_crud_config()
        self.assertEqual(config, view.crud_config)

    @patch('apps.core.mixins.crud_action_mixin.render')
    def test_handle_template_request(self, mock_render):
        """Test template rendering."""
        request = self.factory.get('/?template=true')
        request.user = self.user

        mock_render.return_value = JsonResponse({"status": "ok"})

        response = self.view.handle_template_request(request, self.view.crud_config)

        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        self.assertEqual(args[1], "test/list.html")

    def test_handle_list_request_with_manager_method(self):
        """Test list request when model has custom manager method."""
        request = self.factory.get('/?action=list')
        request.user = self.user

        with patch.object(Asset.objects, 'get_assetlistview') as mock_method:
            mock_method.return_value = [
                {"id": 1, "assetcode": "ASSET001"},
                {"id": 2, "assetcode": "ASSET002"},
            ]

            response = self.view.handle_list_request(request, self.view.crud_config)

            self.assertIsInstance(response, JsonResponse)
            mock_method.assert_called_once()

    def test_handle_form_request_creates_empty_form(self):
        """Test form request returns empty form for creation."""
        request = self.factory.get('/?action=form')
        request.user = self.user
        request.session = {'client_id': 1, 'bu_id': 1}

        with patch('apps.core.mixins.crud_action_mixin.render') as mock_render:
            mock_render.return_value = JsonResponse({"status": "ok"})

            response = self.view.handle_form_request(request, self.view.crud_config)

            mock_render.assert_called_once()

    @patch('apps.core.mixins.crud_action_mixin.utils.render_form_for_delete')
    def test_handle_delete_request(self, mock_delete):
        """Test delete confirmation rendering."""
        request = self.factory.get('/?action=delete&id=1')
        request.user = self.user

        mock_delete.return_value = JsonResponse({"status": "ok"})

        response = self.view.handle_delete_request(request, self.view.crud_config)

        mock_delete.assert_called_once_with(request, self.view.crud_config, True)

    @patch('apps.core.mixins.crud_action_mixin.utils.get_model_obj')
    @patch('apps.core.mixins.crud_action_mixin.render')
    def test_handle_update_request(self, mock_render, mock_get_obj):
        """Test update form rendering."""
        request = self.factory.get('/?id=1')
        request.user = self.user
        request.session = {'client_id': 1, 'bu_id': 1}

        mock_asset = Mock(spec=Asset)
        mock_asset.id = 1
        mock_get_obj.return_value = mock_asset
        mock_render.return_value = JsonResponse({"status": "ok"})

        response = self.view.handle_update_request(request, self.view.crud_config)

        mock_get_obj.assert_called_once()
        mock_render.assert_called_once()

    def test_handle_custom_action_returns_none_by_default(self):
        """Test that custom action handler returns None for unhandled actions."""
        request = self.factory.get('/?action=custom_action')
        request.user = self.user

        result = self.view.handle_custom_action(
            request, "custom_action", self.view.crud_config
        )

        self.assertIsNone(result)

    def test_get_template_context_empty_by_default(self):
        """Test default template context is empty."""
        request = self.factory.get('/')
        request.user = self.user

        context = self.view.get_template_context(request)

        self.assertEqual(context, {})

    def test_get_form_context_default(self):
        """Test default form context generation."""
        request = self.factory.get('/')
        request.user = self.user
        form = Mock()

        context = self.view.get_form_context(request, form, is_update=False)

        self.assertIn("form", context)
        self.assertEqual(context["msg"], "Create")

    def test_get_form_context_for_update(self):
        """Test form context for update."""
        request = self.factory.get('/')
        request.user = self.user
        form = Mock()
        instance = Mock()

        context = self.view.get_form_context(
            request, form, is_update=True, instance=instance
        )

        self.assertEqual(context["msg"], "Update")


@pytest.mark.unit
class CRUDActionMixinExceptionHandlingTestCase(TestCase):
    """Test exception handling in CRUDActionMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )
        self.view = TestView()

    @patch('apps.core.mixins.crud_action_mixin.ErrorHandler.handle_exception')
    def test_validation_error_handling(self, mock_error_handler):
        """Test ValidationError is caught and returns 400."""
        request = self.factory.get('/?action=list')
        request.user = self.user

        with patch.object(self.view, 'handle_list_request') as mock_handler:
            from django.core.exceptions import ValidationError
            mock_handler.side_effect = ValidationError("Invalid data")

            response = self.view.get(request)

            self.assertEqual(response.status_code, 400)
            mock_error_handler.assert_called_once()

    @patch('apps.core.mixins.crud_action_mixin.ErrorHandler.handle_exception')
    def test_permission_denied_handling(self, mock_error_handler):
        """Test PermissionDenied is caught and returns 403."""
        request = self.factory.get('/?action=list')
        request.user = self.user

        with patch.object(self.view, 'handle_list_request') as mock_handler:
            from django.core.exceptions import PermissionDenied
            mock_handler.side_effect = PermissionDenied()

            response = self.view.get(request)

            self.assertEqual(response.status_code, 403)

    @patch('apps.core.mixins.crud_action_mixin.ErrorHandler.handle_exception')
    def test_object_not_found_handling(self, mock_error_handler):
        """Test ObjectDoesNotExist is caught and returns 404."""
        request = self.factory.get('/?id=999')
        request.user = self.user
        request.session = {'client_id': 1, 'bu_id': 1}

        with patch.object(self.view, 'handle_update_request') as mock_handler:
            from django.core.exceptions import ObjectDoesNotExist
            mock_handler.side_effect = ObjectDoesNotExist()

            response = self.view.get(request)

            self.assertEqual(response.status_code, 404)


@pytest.mark.integration
class CRUDActionMixinIntegrationTestCase(TestCase):
    """Integration tests for CRUDActionMixin with real models."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )

    @pytest.mark.skip("Requires database setup")
    def test_full_crud_flow(self):
        """Test complete CRUD flow with mixin."""
        pass