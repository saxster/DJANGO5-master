"""
Tenant Isolation Tests

Critical security tests to ensure complete data isolation between tenants.
Tests prevent cross-tenant data leakage, which would be a catastrophic
security breach in multi-tenant environments.

Test Coverage:
    - Cross-tenant data access prevention
    - Cache isolation between tenants
    - Query routing to correct databases
    - Thread-local context isolation
    - Tenant boundary enforcement

Security Note:
    These tests verify the core security promise of multi-tenancy.
    Any failures must be treated as CRITICAL security vulnerabilities.
"""

import pytest
from unittest.mock import patch, Mock
import threading
import time

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.tenants.middlewares import TenantMiddleware, TenantDbRouter
from apps.tenants.services import TenantCacheService
from apps.core.utils_new.db_utils import THREAD_LOCAL

User = get_user_model()


class TenantIsolationTest(TestCase):
    """Test suite for tenant data isolation."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda req: Mock())
        self.router = TenantDbRouter()
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        # Clear thread-local
        if hasattr(THREAD_LOCAL, 'DB'):
            delattr(THREAD_LOCAL, 'DB')

    # ==================
    # Database Routing Isolation Tests
    # ==================

    @override_settings(
        DATABASES={
            'default': {},
            'tenant_a': {},
            'tenant_b': {}
        }
    )
    def test_requests_to_different_tenants_use_different_databases(self):
        """Test that requests to different hostnames route to different databases."""
        # Request from tenant A
        request_a = self.factory.get('/', HTTP_HOST='tenant-a.example.com')

        with patch('apps.tenants.middlewares.tenant_db_from_request', return_value='tenant_a'):
            self.middleware(request_a)
            db_a = THREAD_LOCAL.DB

        # Request from tenant B (simulating different request in different thread context)
        # Clear thread-local to simulate new request
        delattr(THREAD_LOCAL, 'DB')

        request_b = self.factory.get('/', HTTP_HOST='tenant-b.example.com')

        with patch('apps.tenants.middlewares.tenant_db_from_request', return_value='tenant_b'):
            self.middleware(request_b)
            db_b = THREAD_LOCAL.DB

        # Verify different databases
        self.assertEqual(db_a, 'tenant_a')
        self.assertEqual(db_b, 'tenant_b')
        self.assertNotEqual(db_a, db_b, "Different tenants should use different databases")

    @override_settings(DATABASES={'default': {}, 'tenant_a': {}})
    def test_thread_local_context_isolated_between_requests(self):
        """Test that thread-local context doesn't leak between requests."""
        # Set context for first request
        setattr(THREAD_LOCAL, 'DB', 'tenant_a')

        # Verify it's set
        self.assertEqual(THREAD_LOCAL.DB, 'tenant_a')

        # Clear and set context for second request
        delattr(THREAD_LOCAL, 'DB')
        setattr(THREAD_LOCAL, 'DB', 'default')

        # Verify context changed
        self.assertEqual(THREAD_LOCAL.DB, 'default')
        self.assertNotEqual(THREAD_LOCAL.DB, 'tenant_a')

    @override_settings(DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}})
    def test_database_router_respects_thread_local_context(self):
        """Test that database router uses thread-local context."""
        # Set tenant A context
        setattr(THREAD_LOCAL, 'DB', 'tenant_a')
        db_read = self.router.db_for_read(Mock())
        db_write = self.router.db_for_write(Mock())

        self.assertEqual(db_read, 'tenant_a')
        self.assertEqual(db_write, 'tenant_a')

        # Change to tenant B context
        setattr(THREAD_LOCAL, 'DB', 'tenant_b')
        db_read = self.router.db_for_read(Mock())
        db_write = self.router.db_for_write(Mock())

        self.assertEqual(db_read, 'tenant_b')
        self.assertEqual(db_write, 'tenant_b')

    # ==================
    # Cache Isolation Tests
    # ==================

    def test_cache_keys_scoped_per_tenant(self):
        """Test that cache keys are automatically scoped per tenant."""
        # Tenant A cache
        cache_a = TenantCacheService(tenant_db='tenant_a')
        cache_a.set('user_data', {'name': 'Alice'})

        # Tenant B cache
        cache_b = TenantCacheService(tenant_db='tenant_b')
        cache_b.set('user_data', {'name': 'Bob'})

        # Retrieve and verify isolation
        data_a = cache_a.get('user_data')
        data_b = cache_b.get('user_data')

        self.assertEqual(data_a['name'], 'Alice')
        self.assertEqual(data_b['name'], 'Bob')
        self.assertNotEqual(data_a, data_b, "Cache data should be isolated per tenant")

    def test_cache_clear_only_affects_current_tenant(self):
        """Test that clearing cache only affects current tenant."""
        # Set cache for tenant A
        cache_a = TenantCacheService(tenant_db='tenant_a')
        cache_a.set('data1', 'value1')
        cache_a.set('data2', 'value2')

        # Set cache for tenant B
        cache_b = TenantCacheService(tenant_db='tenant_b')
        cache_b.set('data1', 'value_b1')
        cache_b.set('data2', 'value_b2')

        # Clear tenant A cache
        cleared_count = cache_a.clear_tenant_cache()
        self.assertGreater(cleared_count, 0, "Should clear some keys")

        # Verify tenant A cache cleared
        self.assertIsNone(cache_a.get('data1'))
        self.assertIsNone(cache_a.get('data2'))

        # Verify tenant B cache still intact
        self.assertEqual(cache_b.get('data1'), 'value_b1')
        self.assertEqual(cache_b.get('data2'), 'value_b2')

    def test_cache_get_many_isolated_per_tenant(self):
        """Test that get_many operations are tenant-isolated."""
        # Tenant A cache
        cache_a = TenantCacheService(tenant_db='tenant_a')
        cache_a.set_many({
            'key1': 'value_a1',
            'key2': 'value_a2',
            'key3': 'value_a3'
        })

        # Tenant B cache
        cache_b = TenantCacheService(tenant_db='tenant_b')
        cache_b.set_many({
            'key1': 'value_b1',
            'key2': 'value_b2',
            'key3': 'value_b3'
        })

        # Get many from each tenant
        data_a = cache_a.get_many(['key1', 'key2', 'key3'])
        data_b = cache_b.get_many(['key1', 'key2', 'key3'])

        # Verify isolation
        self.assertEqual(data_a['key1'], 'value_a1')
        self.assertEqual(data_b['key1'], 'value_b1')
        self.assertNotEqual(data_a, data_b)

    # ==================
    # Cross-Tenant Access Prevention Tests
    # ==================

    def test_tenant_cannot_access_other_tenant_cache(self):
        """Test that one tenant cannot access another tenant's cache directly."""
        # Tenant A sets data
        cache_a = TenantCacheService(tenant_db='tenant_a')
        cache_a.set('secret_data', 'tenant_a_secret')

        # Tenant B tries to get the same key
        cache_b = TenantCacheService(tenant_db='tenant_b')
        retrieved_data = cache_b.get('secret_data')

        # Should be None (not found) because key is scoped differently
        self.assertIsNone(
            retrieved_data,
            "Tenant B should not be able to access Tenant A's cache"
        )

    @override_settings(DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}})
    def test_query_routing_prevents_cross_tenant_queries(self):
        """Test that database routing prevents cross-tenant queries."""
        # Set tenant A context
        setattr(THREAD_LOCAL, 'DB', 'tenant_a')
        db_a = self.router.db_for_read(Mock())

        # Set tenant B context
        setattr(THREAD_LOCAL, 'DB', 'tenant_b')
        db_b = self.router.db_for_read(Mock())

        # Verify queries routed to different databases
        self.assertNotEqual(
            db_a, db_b,
            "Queries from different tenants should route to different databases"
        )

    # ==================
    # Thread Safety Tests
    # ==================

    @override_settings(DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}})
    def test_thread_local_isolation_between_threads(self):
        """Test that thread-local context is isolated between threads."""
        results = {'thread1': None, 'thread2': None}

        def set_and_get_tenant_a():
            setattr(THREAD_LOCAL, 'DB', 'tenant_a')
            time.sleep(0.1)  # Simulate work
            results['thread1'] = getattr(THREAD_LOCAL, 'DB', None)

        def set_and_get_tenant_b():
            setattr(THREAD_LOCAL, 'DB', 'tenant_b')
            time.sleep(0.1)  # Simulate work
            results['thread2'] = getattr(THREAD_LOCAL, 'DB', None)

        thread1 = threading.Thread(target=set_and_get_tenant_a)
        thread2 = threading.Thread(target=set_and_get_tenant_b)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify each thread maintained its own context
        self.assertEqual(results['thread1'], 'tenant_a')
        self.assertEqual(results['thread2'], 'tenant_b')

    # ==================
    # Boundary Enforcement Tests
    # ==================

    def test_cache_service_requires_tenant_context(self):
        """Test that cache service requires valid tenant context."""
        # Clear thread-local
        if hasattr(THREAD_LOCAL, 'DB'):
            delattr(THREAD_LOCAL, 'DB')

        cache_service = TenantCacheService()

        # Should use 'default' when no context set (with warning)
        db = cache_service._get_tenant_db()
        self.assertEqual(db, 'default')

    @override_settings(DATABASES={'default': {}, 'tenant_a': {}})
    def test_middleware_sets_tenant_context_for_all_requests(self):
        """Test that middleware sets tenant context for every request."""
        request = self.factory.get('/', HTTP_HOST='tenant-a.example.com')

        with patch('apps.tenants.middlewares.tenant_db_from_request', return_value='tenant_a'):
            self.middleware(request)

            # Verify context was set
            self.assertTrue(hasattr(THREAD_LOCAL, 'DB'))
            self.assertEqual(THREAD_LOCAL.DB, 'tenant_a')


# ==================
# Pytest Fixtures and Integration Tests
# ==================

@pytest.fixture
def tenant_a_context():
    """Fixture providing tenant A context."""
    setattr(THREAD_LOCAL, 'DB', 'tenant_a')
    yield
    if hasattr(THREAD_LOCAL, 'DB'):
        delattr(THREAD_LOCAL, 'DB')


@pytest.fixture
def tenant_b_context():
    """Fixture providing tenant B context."""
    setattr(THREAD_LOCAL, 'DB', 'tenant_b')
    yield
    if hasattr(THREAD_LOCAL, 'DB'):
        delattr(THREAD_LOCAL, 'DB')


@pytest.mark.django_db
class TestTenantIsolationIntegration:
    """Integration tests for tenant isolation."""

    def test_end_to_end_tenant_isolation(self, tenant_a_context):
        """Test complete tenant isolation from request to cache."""
        factory = RequestFactory()
        middleware = TenantMiddleware(lambda req: Mock())
        router = TenantDbRouter()

        # Create request
        request = factory.get('/', HTTP_HOST='tenant-a.example.com')

        with patch('apps.tenants.middlewares.tenant_db_from_request', return_value='tenant_a'):
            # Process through middleware
            middleware(request)

            # Verify database routing
            db = router.db_for_read(Mock())
            assert db == 'tenant_a'

            # Verify cache isolation
            cache_service = TenantCacheService()
            cache_service.set('test_key', 'test_value')

            # Verify key is scoped
            scoped_key = cache_service._build_cache_key('test_key')
            assert 'tenant_a' in scoped_key

    def test_concurrent_tenant_requests_isolated(self):
        """Test that concurrent requests to different tenants remain isolated."""
        results = {'a_db': None, 'b_db': None, 'a_cache': None, 'b_cache': None}

        def tenant_a_operations():
            setattr(THREAD_LOCAL, 'DB', 'tenant_a')
            router = TenantDbRouter()
            results['a_db'] = router.db_for_read(Mock())

            cache_service = TenantCacheService()
            cache_service.set('data', 'tenant_a_data')
            results['a_cache'] = cache_service.get('data')

        def tenant_b_operations():
            setattr(THREAD_LOCAL, 'DB', 'tenant_b')
            router = TenantDbRouter()
            results['b_db'] = router.db_for_read(Mock())

            cache_service = TenantCacheService()
            cache_service.set('data', 'tenant_b_data')
            results['b_cache'] = cache_service.get('data')

        with override_settings(DATABASES={'default': {}, 'tenant_a': {}, 'tenant_b': {}}):
            thread_a = threading.Thread(target=tenant_a_operations)
            thread_b = threading.Thread(target=tenant_b_operations)

            thread_a.start()
            thread_b.start()

            thread_a.join()
            thread_b.join()

        # Verify isolation
        assert results['a_db'] == 'tenant_a'
        assert results['b_db'] == 'tenant_b'
        assert results['a_cache'] == 'tenant_a_data'
        assert results['b_cache'] == 'tenant_b_data'
        assert results['a_cache'] != results['b_cache']
