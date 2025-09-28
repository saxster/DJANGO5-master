"""
Comprehensive tests for AuthenticationService.

Tests authentication business logic, session management,
role-based routing, and security validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError

from apps.peoples.services.authentication_service import (
    AuthenticationService,
    AuthenticationResult,
    UserContext,
    UserAccessType,
    SiteCode
)
from apps.peoples.models import People
from apps.core.exceptions import (
    AuthenticationError,
    UserManagementException,
    BusinessLogicException
)


class TestAuthenticationService(TestCase):
    """Test AuthenticationService functionality."""

    def setUp(self):
        self.auth_service = AuthenticationService()
        self.mock_user = Mock(spec=People)
        self.mock_user.id = 1
        self.mock_user.peoplename = "Test User"
        self.mock_user.loginid = "testuser"
        self.mock_user.peoplecode = "TEST001"
        self.mock_user.is_authenticated = True
        self.mock_user.is_staff = False
        self.mock_user.is_superuser = False
        self.mock_user.is_active = True

        # Mock business unit
        self.mock_bu = Mock()
        self.mock_bu.id = 2
        self.mock_bu.bucode = "SPSESIC"
        self.mock_bu.buname = "Test Business Unit"
        self.mock_user.bu = self.mock_bu

        # Mock client
        self.mock_client = Mock()
        self.mock_client.id = 1
        self.mock_client.buname = "Test Client"
        self.mock_user.client = self.mock_client

        # Mock people extras
        self.mock_extras = Mock()
        self.mock_extras.userfor = "Web"
        self.mock_user.people_extras = self.mock_extras

    @patch('apps.peoples.services.authentication_service.People.objects')
    def test_validate_user_access_success(self, mock_people_objects):
        """Test successful user access validation."""
        # Mock query result
        mock_query = Mock()
        mock_query.exists.return_value = True
        mock_query.__getitem__.return_value = {"people_extras__userfor": "Web"}
        mock_people_objects.filter.return_value.values.return_value = mock_query

        result = self.auth_service._validate_user_access("testuser", "Web")

        self.assertTrue(result.success)
        mock_people_objects.filter.assert_called_once_with(loginid="testuser")

    @patch('apps.peoples.services.authentication_service.People.objects')
    def test_validate_user_access_user_not_found(self, mock_people_objects):
        """Test user access validation when user not found."""
        # Mock empty query result
        mock_query = Mock()
        mock_query.exists.return_value = False
        mock_people_objects.filter.return_value.values.return_value = mock_query

        result = self.auth_service._validate_user_access("nonexistent", "Web")

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "User not found")

    @patch('apps.peoples.services.authentication_service.People.objects')
    def test_validate_user_access_unauthorized_access_type(self, mock_people_objects):
        """Test user access validation with unauthorized access type."""
        # Mock query result with mobile-only user
        mock_query = Mock()
        mock_query.exists.return_value = True
        mock_query.__getitem__.return_value = {"people_extras__userfor": "Mobile"}
        mock_people_objects.filter.return_value.values.return_value = mock_query

        result = self.auth_service._validate_user_access("mobileuser", "Web")

        self.assertFalse(result.success)
        self.assertIn("unauthorized", result.error_message.lower())

    @patch('apps.peoples.services.authentication_service.authenticate')
    def test_authenticate_credentials_success(self, mock_authenticate):
        """Test successful credential authentication."""
        mock_authenticate.return_value = self.mock_user

        result = self.auth_service._authenticate_credentials("testuser", "password")

        self.assertEqual(result, self.mock_user)
        mock_authenticate.assert_called_once_with(username="testuser", password="password")

    @patch('apps.peoples.services.authentication_service.authenticate')
    def test_authenticate_credentials_failure(self, mock_authenticate):
        """Test failed credential authentication."""
        mock_authenticate.return_value = None

        result = self.auth_service._authenticate_credentials("testuser", "wrongpassword")

        self.assertIsNone(result)

    def test_build_user_context(self):
        """Test building user context."""
        context = self.auth_service._build_user_context(self.mock_user)

        self.assertIsInstance(context, UserContext)
        self.assertEqual(context.user, self.mock_user)
        self.assertEqual(context.bu_id, 2)
        self.assertEqual(context.sitecode, "SPSESIC")
        self.assertEqual(context.client_name, "Test Client")

    def test_validate_site_access_success(self):
        """Test successful site access validation."""
        context = UserContext(user=self.mock_user, bu_id=2, sitecode="SPSESIC")

        result = self.auth_service._validate_site_access(context)

        self.assertTrue(result.success)

    def test_validate_site_access_no_site(self):
        """Test site access validation with no site."""
        context = UserContext(user=self.mock_user, bu_id=1, sitecode=None)

        result = self.auth_service._validate_site_access(context)

        self.assertFalse(result.success)
        self.assertEqual(result.redirect_url, 'peoples:no_site')

    def test_determine_redirect_url_valid_site(self):
        """Test redirect URL determination for valid sites."""
        test_cases = [
            ("SPSOPS", "reports:generateattendance"),
            ("SPSHR", "employee_creation:employee_creation"),
            ("SPSOPERATION", "reports:generate_declaration_form"),
            ("SPSESIC", "reports:generatepdf"),
        ]

        for sitecode, expected_url in test_cases:
            context = UserContext(user=self.mock_user, sitecode=sitecode)
            result = self.auth_service._determine_redirect_url(context)
            self.assertEqual(result, expected_url)

    def test_determine_redirect_url_invalid_site(self):
        """Test redirect URL determination for invalid sites."""
        context = UserContext(user=self.mock_user, sitecode="INVALID")

        result = self.auth_service._determine_redirect_url(context)

        self.assertEqual(result, "onboarding:rp_dashboard")

    def test_determine_redirect_url_with_wizard_data(self):
        """Test redirect URL determination with wizard data."""
        context = UserContext(
            user=self.mock_user,
            sitecode="INVALID",
            has_wizard_data=True
        )

        result = self.auth_service._determine_redirect_url(context)

        self.assertEqual(result, "onboarding:wizard_delete")

    def test_prepare_session_data(self):
        """Test session data preparation."""
        context = UserContext(
            user=self.mock_user,
            bu_id=2,
            sitecode="SPSESIC",
            client_name="Test Client",
            access_type="Web"
        )

        session_data = self.auth_service._prepare_session_data(context)

        expected_keys = [
            'user_id', 'peoplecode', 'bu_id', 'sitecode',
            'client_name', 'access_type'
        ]
        for key in expected_keys:
            self.assertIn(key, session_data)

        self.assertEqual(session_data['user_id'], 1)
        self.assertEqual(session_data['peoplecode'], "TEST001")

    @patch('apps.peoples.services.authentication_service.People.objects')
    @patch('apps.peoples.services.authentication_service.authenticate')
    def test_authenticate_user_success(self, mock_authenticate, mock_people_objects):
        """Test complete user authentication success flow."""
        # Mock user validation
        mock_query = Mock()
        mock_query.exists.return_value = True
        mock_query.__getitem__.return_value = {"people_extras__userfor": "Web"}
        mock_people_objects.filter.return_value.values.return_value = mock_query

        # Mock authentication
        mock_authenticate.return_value = self.mock_user

        result = self.auth_service.authenticate_user("testuser", "password", "Web")

        self.assertTrue(result.success)
        self.assertEqual(result.user, self.mock_user)
        self.assertIsNotNone(result.redirect_url)
        self.assertIsNotNone(result.session_data)

    @patch('apps.peoples.services.authentication_service.People.objects')
    @patch('apps.peoples.services.authentication_service.authenticate')
    def test_authenticate_user_invalid_credentials(self, mock_authenticate, mock_people_objects):
        """Test user authentication with invalid credentials."""
        # Mock user validation success
        mock_query = Mock()
        mock_query.exists.return_value = True
        mock_query.__getitem__.return_value = {"people_extras__userfor": "Web"}
        mock_people_objects.filter.return_value.values.return_value = mock_query

        # Mock authentication failure
        mock_authenticate.return_value = None

        result = self.auth_service.authenticate_user("testuser", "wrongpassword", "Web")

        self.assertFalse(result.success)
        self.assertIn("Invalid login details", result.error_message)

    @patch('apps.peoples.services.authentication_service.People.objects')
    def test_authenticate_user_validation_failure(self, mock_people_objects):
        """Test user authentication with validation failure."""
        # Mock user not found
        mock_query = Mock()
        mock_query.exists.return_value = False
        mock_people_objects.filter.return_value.values.return_value = mock_query

        result = self.auth_service.authenticate_user("nonexistent", "password", "Web")

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "User not found")

    @patch('apps.peoples.services.authentication_service.People.objects')
    def test_authenticate_user_no_site_access(self, mock_people_objects):
        """Test user authentication with no site access."""
        # Mock user validation success
        mock_query = Mock()
        mock_query.exists.return_value = True
        mock_query.__getitem__.return_value = {"people_extras__userfor": "Web"}
        mock_people_objects.filter.return_value.values.return_value = mock_query

        # Mock authentication success but no site access
        mock_user_no_site = Mock(spec=People)
        mock_user_no_site.bu = None
        mock_user_no_site.client = None

        with patch('apps.peoples.services.authentication_service.authenticate') as mock_auth:
            mock_auth.return_value = mock_user_no_site

            result = self.auth_service.authenticate_user("testuser", "password", "Web")

            self.assertFalse(result.success)
            self.assertEqual(result.redirect_url, 'peoples:no_site')

    def test_logout_user_success(self):
        """Test successful user logout."""
        mock_request = Mock()
        mock_request.user = self.mock_user

        with patch('apps.peoples.services.authentication_service.logout') as mock_logout:
            result = self.auth_service.logout_user(mock_request)

            self.assertTrue(result.success)
            self.assertEqual(result.redirect_url, 'peoples:login')
            mock_logout.assert_called_once_with(mock_request)

    def test_logout_user_unauthenticated(self):
        """Test logout for unauthenticated user."""
        mock_request = Mock()
        mock_request.user.is_authenticated = False

        with patch('apps.peoples.services.authentication_service.logout') as mock_logout:
            result = self.auth_service.logout_user(mock_request)

            self.assertTrue(result.success)
            mock_logout.assert_called_once_with(mock_request)

    def test_logout_user_exception(self):
        """Test logout with exception handling."""
        mock_request = Mock()
        mock_request.user = self.mock_user

        with patch('apps.peoples.services.authentication_service.logout') as mock_logout:
            mock_logout.side_effect = Exception("Logout error")

            result = self.auth_service.logout_user(mock_request)

            self.assertFalse(result.success)
            self.assertEqual(result.error_message, "Logout failed")
            self.assertIsNotNone(result.correlation_id)

    def test_validate_session_authenticated(self):
        """Test session validation for authenticated user."""
        mock_request = Mock()
        mock_request.user.is_authenticated = True

        result = self.auth_service.validate_session(mock_request)

        self.assertTrue(result)

    def test_validate_session_unauthenticated(self):
        """Test session validation for unauthenticated user."""
        mock_request = Mock()
        mock_request.user.is_authenticated = False

        result = self.auth_service.validate_session(mock_request)

        self.assertFalse(result)

    def test_validate_session_exception(self):
        """Test session validation with exception."""
        mock_request = Mock()
        mock_request.user.is_authenticated = Mock(side_effect=Exception("Session error"))

        result = self.auth_service.validate_session(mock_request)

        self.assertFalse(result)

    def test_get_user_permissions(self):
        """Test getting user permissions."""
        # Mock groups and permissions
        mock_groups = Mock()
        mock_groups.values_list.return_value = ['admin', 'user']
        self.mock_user.groups = mock_groups

        mock_permissions = Mock()
        mock_permissions.values_list.return_value = ['add_user', 'change_user']
        self.mock_user.user_permissions = mock_permissions

        permissions = self.auth_service.get_user_permissions(self.mock_user)

        expected_keys = [
            'is_staff', 'is_superuser', 'is_active', 'bu_id',
            'client_id', 'access_type', 'groups', 'user_permissions'
        ]
        for key in expected_keys:
            self.assertIn(key, permissions)

        self.assertEqual(permissions['groups'], ['admin', 'user'])
        self.assertEqual(permissions['user_permissions'], ['add_user', 'change_user'])

    def test_get_user_permissions_exception(self):
        """Test getting user permissions with exception."""
        mock_user = Mock()
        mock_user.groups.values_list.side_effect = Exception("Permission error")

        permissions = self.auth_service.get_user_permissions(mock_user)

        self.assertEqual(permissions, {})

    @patch('apps.peoples.services.authentication_service.ErrorHandler.handle_exception')
    def test_authenticate_user_exception_handling(self, mock_error_handler):
        """Test exception handling in authenticate_user."""
        mock_error_handler.return_value = "correlation-123"

        with patch('apps.peoples.services.authentication_service.People.objects') as mock_objects:
            mock_objects.filter.side_effect = Exception("Database error")

            result = self.auth_service.authenticate_user("testuser", "password", "Web")

            self.assertFalse(result.success)
            self.assertEqual(result.error_message, "Authentication service error")
            self.assertEqual(result.correlation_id, "correlation-123")
            mock_error_handler.assert_called_once()

    def test_service_name(self):
        """Test service name."""
        self.assertEqual(self.auth_service.get_service_name(), "AuthenticationService")


class TestUserAccessType(TestCase):
    """Test UserAccessType enumeration."""

    def test_access_type_values(self):
        """Test access type enumeration values."""
        self.assertEqual(UserAccessType.WEB.value, "Web")
        self.assertEqual(UserAccessType.MOBILE.value, "Mobile")
        self.assertEqual(UserAccessType.BOTH.value, "Both")


class TestSiteCode(TestCase):
    """Test SiteCode enumeration."""

    def test_site_code_values(self):
        """Test site code enumeration values."""
        expected_sites = [
            "SPSESIC", "SPSPAYROLL", "SPSOPS", "SPSOPERATION", "SPSHR"
        ]
        actual_sites = [site.value for site in SiteCode]

        for site in expected_sites:
            self.assertIn(site, actual_sites)


class TestAuthenticationResult(TestCase):
    """Test AuthenticationResult data structure."""

    def test_authentication_result_creation(self):
        """Test creating authentication result."""
        result = AuthenticationResult(
            success=True,
            user=self.mock_user,
            redirect_url="dashboard",
            session_data={"key": "value"}
        )

        self.assertTrue(result.success)
        self.assertEqual(result.redirect_url, "dashboard")
        self.assertIsNotNone(result.session_data)

    def test_authentication_result_failure(self):
        """Test creating failed authentication result."""
        result = AuthenticationResult(
            success=False,
            error_message="Authentication failed",
            correlation_id="corr-123"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Authentication failed")
        self.assertEqual(result.correlation_id, "corr-123")

    def setUp(self):
        self.mock_user = Mock(spec=People)


class TestUserContext(TestCase):
    """Test UserContext data structure."""

    def test_user_context_creation(self):
        """Test creating user context."""
        mock_user = Mock(spec=People)
        context = UserContext(
            user=mock_user,
            bu_id=1,
            sitecode="SPSESIC",
            client_name="Test Client",
            has_wizard_data=True,
            access_type="Web"
        )

        self.assertEqual(context.user, mock_user)
        self.assertEqual(context.bu_id, 1)
        self.assertEqual(context.sitecode, "SPSESIC")
        self.assertEqual(context.client_name, "Test Client")
        self.assertTrue(context.has_wizard_data)
        self.assertEqual(context.access_type, "Web")


@pytest.mark.integration
class TestAuthenticationServiceIntegration(TransactionTestCase):
    """Integration tests for AuthenticationService."""

    def setUp(self):
        self.auth_service = AuthenticationService()

    def test_service_metrics_tracking(self):
        """Test that service metrics are properly tracked."""
        initial_metrics = self.auth_service.get_service_metrics()
        initial_call_count = initial_metrics['call_count']

        # Attempt authentication (will fail but should be tracked)
        with patch('apps.peoples.services.authentication_service.People.objects') as mock_objects:
            mock_query = Mock()
            mock_query.exists.return_value = False
            mock_objects.filter.return_value.values.return_value = mock_query

            self.auth_service.authenticate_user("testuser", "password", "Web")

        updated_metrics = self.auth_service.get_service_metrics()
        self.assertEqual(updated_metrics['call_count'], initial_call_count + 1)

    def test_caching_behavior(self):
        """Test service caching behavior."""
        # Test cache operations
        cache_key = "test_auth_cache"
        test_data = {"user_id": 1, "permissions": ["read", "write"]}

        # Set cache
        success = self.auth_service.set_cached_data(cache_key, test_data)
        self.assertTrue(success)

        # Get from cache
        cached_data = self.auth_service.get_cached_data(cache_key)
        self.assertEqual(cached_data, test_data)

        # Invalidate cache
        success = self.auth_service.invalidate_cache(cache_key)
        self.assertTrue(success)

        # Verify cache is cleared
        cached_data = self.auth_service.get_cached_data(cache_key)
        self.assertIsNone(cached_data)