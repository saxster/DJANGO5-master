"""
Base Test Case for Code Duplication Elimination

This module provides reusable test base classes and utilities to eliminate
test setup patterns duplicated across the codebase.

Following .claude/rules.md:
- Rule #7: Classes <150 lines (single responsibility)
- Rule #11: Specific exception handling
"""

import logging
from typing import Dict, Any, Optional, List
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.test.client import Client
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token

from apps.tenants.models import Tenant
from apps.onboarding.models import BusinessUnit

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseTestCase(TestCase):
    """
    Base test case consolidating common test setup patterns.

    Provides standardized user creation, authentication, and data setup
    to eliminate duplication across test files.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up class-level test data."""
        super().setUpTestData()
        cls._setup_test_users()
        cls._setup_test_tenants()

    def setUp(self):
        """Set up test instance."""
        super().setUp()
        self.client = Client()

    @classmethod
    def _setup_test_users(cls):
        """Create standard test users."""
        cls.admin_user = cls.create_test_user(
            loginid='admin@test.com',
            peoplename='Admin User',
            is_staff=True,
            is_superuser=True
        )

        cls.regular_user = cls.create_test_user(
            loginid='user@test.com',
            peoplename='Regular User'
        )

        cls.inactive_user = cls.create_test_user(
            loginid='inactive@test.com',
            peoplename='Inactive User',
            is_active=False
        )

    @classmethod
    def _setup_test_tenants(cls):
        """Create standard test tenants."""
        cls.test_tenant = Tenant.objects.create(
            name='Test Tenant',
            domain='test.example.com'
        )

        cls.test_bu = BusinessUnit.objects.create(
            name='Test Business Unit',
            code='TEST_BU',
            tenant=cls.test_tenant
        )

        # Associate regular user with business unit
        cls.regular_user.bu = cls.test_bu
        cls.regular_user.save()

    @classmethod
    def create_test_user(
        cls,
        loginid: str,
        peoplename: str,
        password: str = 'testpass123',
        **kwargs
    ):
        """
        Create a test user with standard defaults.

        Args:
            loginid: User login ID (email)
            peoplename: User display name
            password: User password
            **kwargs: Additional user fields

        Returns:
            User instance
        """
        defaults = {
            'email': loginid,
            'mobno': f'+1234567{len(loginid)}',
            'isverified': True,
            'enable': True,
            'is_active': True
        }
        defaults.update(kwargs)

        user = User.objects.create_user(
            loginid=loginid,
            peoplename=peoplename,
            password=password,
            **defaults
        )
        return user

    def authenticate_user(self, user=None):
        """
        Authenticate a user for testing.

        Args:
            user: User to authenticate (defaults to regular_user)
        """
        user = user or self.regular_user
        self.client.force_login(user)
        return user

    def create_test_data(self, model_class, count: int = 1, **kwargs) -> List:
        """
        Create test instances of a model.

        Args:
            model_class: Model class to create instances of
            count: Number of instances to create
            **kwargs: Field values for the model

        Returns:
            List of created instances
        """
        instances = []
        for i in range(count):
            # Add index to make each instance unique
            indexed_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, str) and '{i}' in value:
                    indexed_kwargs[key] = value.format(i=i)
                else:
                    indexed_kwargs[key] = value

            instance = model_class.objects.create(**indexed_kwargs)
            instances.append(instance)

        return instances

    def assert_field_errors(self, response, field_name: str, expected_error: str = None):
        """
        Assert that a field has validation errors.

        Args:
            response: HTTP response
            field_name: Field name to check
            expected_error: Expected error message (optional)
        """
        self.assertIn('errors', response.data)
        self.assertIn(field_name, response.data['errors'])

        if expected_error:
            field_errors = response.data['errors'][field_name]
            if isinstance(field_errors, list):
                self.assertIn(expected_error, field_errors)
            else:
                self.assertIn(expected_error, str(field_errors))

    def assert_permission_denied(self, response):
        """Assert that response indicates permission denied."""
        self.assertIn(response.status_code, [403, 401])

    def assert_success_response(self, response, status_code: int = 200):
        """Assert that response indicates success."""
        self.assertEqual(response.status_code, status_code)
        if hasattr(response, 'data') and isinstance(response.data, dict):
            self.assertTrue(response.data.get('success', True))


class BaseAPITestCase(APITestCase, BaseTestCase):
    """
    Base API test case for DRF API testing.

    Extends BaseTestCase with DRF-specific functionality.
    """

    def setUp(self):
        """Set up API test instance."""
        super().setUp()
        self.api_client = APIClient()

    def authenticate_api_user(self, user=None):
        """
        Authenticate a user for API testing.

        Args:
            user: User to authenticate (defaults to regular_user)

        Returns:
            User and token
        """
        user = user or self.regular_user
        token, created = Token.objects.get_or_create(user=user)
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return user, token

    def make_api_request(
        self,
        method: str,
        url: str,
        data: Dict = None,
        user=None,
        **kwargs
    ):
        """
        Make authenticated API request.

        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            user: User to authenticate as
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        if user:
            self.authenticate_api_user(user)

        method_func = getattr(self.api_client, method.lower())
        return method_func(url, data, **kwargs)

    def assert_api_success(self, response, status_code: int = 200):
        """Assert API response indicates success."""
        self.assertEqual(response.status_code, status_code)
        if isinstance(response.data, dict):
            self.assertTrue(response.data.get('success', True))

    def assert_api_error(self, response, status_code: int = 400, error_message: str = None):
        """Assert API response indicates error."""
        self.assertEqual(response.status_code, status_code)
        if isinstance(response.data, dict):
            self.assertFalse(response.data.get('success', True))
            if error_message:
                self.assertIn(error_message, response.data.get('message', ''))


class SyncTestMixin:
    """
    Mixin providing sync-specific test utilities.

    Consolidates sync testing patterns used across mobile sync tests.
    """

    def create_sync_data(
        self,
        mobile_id: str = None,
        version: int = 1,
        sync_status: str = 'pending',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create standard sync data for testing.

        Args:
            mobile_id: Mobile ID (auto-generated if not provided)
            version: Version number
            sync_status: Sync status
            **kwargs: Additional data fields

        Returns:
            Dictionary with sync data
        """
        import uuid

        sync_data = {
            'mobile_id': mobile_id or str(uuid.uuid4()),
            'version': version,
            'sync_status': sync_status,
            'last_sync_timestamp': timezone.now().isoformat()
        }
        sync_data.update(kwargs)
        return sync_data

    def create_sync_batch(self, count: int = 3, **kwargs) -> Dict[str, Any]:
        """
        Create sync batch data for testing.

        Args:
            count: Number of entries in batch
            **kwargs: Additional data for each entry

        Returns:
            Dictionary with batch sync data
        """
        entries = []
        for i in range(count):
            entry_data = self.create_sync_data(**kwargs)
            entry_data.update({f'field_{i}': f'value_{i}'})
            entries.append(entry_data)

        return {
            'entries': entries,
            'last_sync_timestamp': timezone.now().isoformat(),
            'client_id': 'test_client'
        }

    def assert_sync_response(self, response, expected_synced: int = None, expected_conflicts: int = None):
        """
        Assert sync response format and counts.

        Args:
            response: Sync response
            expected_synced: Expected number of synced items
            expected_conflicts: Expected number of conflicts
        """
        self.assertIn('synced_items', response.data)
        self.assertIn('conflicts', response.data)
        self.assertIn('errors', response.data)

        if expected_synced is not None:
            self.assertEqual(len(response.data['synced_items']), expected_synced)

        if expected_conflicts is not None:
            self.assertEqual(len(response.data['conflicts']), expected_conflicts)


class TenantTestMixin:
    """
    Mixin providing tenant-aware test utilities.

    Consolidates tenant testing patterns used across tenant-aware tests.
    """

    def create_tenant_data(self, tenant=None, **kwargs) -> Dict[str, Any]:
        """
        Create data with tenant association.

        Args:
            tenant: Tenant to associate with (defaults to test_tenant)
            **kwargs: Additional data fields

        Returns:
            Dictionary with tenant-aware data
        """
        tenant = tenant or self.test_tenant
        data = {'tenant': tenant.id if hasattr(tenant, 'id') else tenant}
        data.update(kwargs)
        return data

    def assert_tenant_filtering(self, response, expected_tenant):
        """
        Assert that response data is filtered by tenant.

        Args:
            response: HTTP response
            expected_tenant: Expected tenant
        """
        if hasattr(response, 'data') and isinstance(response.data, dict):
            results = response.data.get('results', response.data.get('data', []))
            if isinstance(results, list):
                for item in results:
                    if isinstance(item, dict) and 'tenant' in item:
                        tenant_id = expected_tenant.id if hasattr(expected_tenant, 'id') else expected_tenant
                        self.assertEqual(item['tenant'], tenant_id)


class PerformanceTestMixin:
    """
    Mixin providing performance testing utilities.

    Consolidates performance testing patterns.
    """

    def assert_query_count(self, expected_count: int):
        """
        Context manager to assert database query count.

        Args:
            expected_count: Expected number of queries

        Returns:
            Context manager
        """
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import isolate_apps

        class QueryCountContext:
            def __enter__(self):
                self.initial_queries = len(connection.queries)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                query_count = len(connection.queries) - self.initial_queries
                if query_count != expected_count:
                    queries = connection.queries[self.initial_queries:]
                    query_details = '\n'.join([f"{i+1}: {q['sql']}" for i, q in enumerate(queries)])
                    raise AssertionError(
                        f"Expected {expected_count} queries, but {query_count} were executed:\n{query_details}"
                    )

        return QueryCountContext()

    def time_operation(self, operation_func, *args, **kwargs):
        """
        Time an operation and return duration.

        Args:
            operation_func: Function to time
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            tuple: (result, duration_in_seconds)
        """
        import time
        start_time = time.time()
        result = operation_func(*args, **kwargs)
        duration = time.time() - start_time
        return result, duration


class EnhancedTestCase(
    SyncTestMixin,
    TenantTestMixin,
    PerformanceTestMixin,
    BaseTestCase
):
    """
    Enhanced test case combining all testing utilities.

    Provides comprehensive testing capabilities consolidated from
    across the codebase.
    """
    pass


class EnhancedAPITestCase(
    SyncTestMixin,
    TenantTestMixin,
    PerformanceTestMixin,
    BaseAPITestCase
):
    """
    Enhanced API test case combining all testing utilities.

    Provides comprehensive API testing capabilities.
    """
    pass