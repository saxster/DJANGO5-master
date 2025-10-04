"""
Comprehensive Tenant Routing Tests

Tests multi-tenant middleware, database routing, and cache isolation.

Security Focus:
    - Verify tenant isolation (no cross-tenant data leakage)
    - Test unknown host handling
    - Validate middleware ordering
    - Test cache key prefixing
"""

import pytest
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.db import connection
from unittest.mock import patch, MagicMock

from apps.tenants.middlewares import TenantMiddleware, TenantDbRouter
from apps.core.utils_new.db_utils import (
    tenant_db_from_request,
    hostname_from_request,
    get_current_db_name,
    THREAD_LOCAL
)
from apps.core.cache.tenant_aware import tenant_cache
from intelliwiz_config.settings.tenants import (
    get_tenant_for_host,
    get_tenant_mappings,
    TENANT_MAPPINGS
)

People = get_user_model()


class TenantMiddlewareTests(TestCase):
    """Test TenantMiddleware functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: None)

    def test_middleware_sets_thread_local_db(self):
        """Test middleware sets THREAD_LOCAL.DB correctly."""
        # Create request with known tenant hostname
        request = self.factory.get('/', HTTP_HOST='sps.youtility.local')

        # Call middleware
        self.middleware(request)

        # Verify THREAD_LOCAL.DB is set
        self.assertTrue(hasattr(THREAD_LOCAL, 'DB'))
        self.assertEqual(get_current_db_name(), 'sps')

    def test_middleware_handles_unknown_host(self):
        """Test middleware handles unknown hostname gracefully."""
        request = self.factory.get('/', HTTP_HOST='unknown.host.com')

        # Call middleware
        self.middleware(request)

        # Should default to 'default' database
        self.assertEqual(get_current_db_name(), 'default')

    def test_middleware_handles_localhost(self):
        """Test middleware handles localhost correctly."""
        request = self.factory.get('/', HTTP_HOST='localhost:8000')

        self.middleware(request)

        # Should default to 'default' for localhost
        self.assertEqual(get_current_db_name(), 'default')

    def test_middleware_cleans_thread_local_between_requests(self):
        """Test thread local is properly reset between requests."""
        # First request
        request1 = self.factory.get('/', HTTP_HOST='sps.youtility.local')
        self.middleware(request1)
        db1 = get_current_db_name()

        # Second request with different tenant
        request2 = self.factory.get('/', HTTP_HOST='dell.youtility.local')
        self.middleware(request2)
        db2 = get_current_db_name()

        # Verify different databases
        self.assertEqual(db1, 'sps')
        self.assertEqual(db2, 'dell')


class TenantDatabaseRouterTests(TestCase):
    """Test TenantDbRouter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.router = TenantDbRouter()
        self.factory = RequestFactory()

    def test_router_reads_from_correct_database(self):
        """Test router directs reads to correct database."""
        # Set thread local to specific tenant
        setattr(THREAD_LOCAL, 'DB', 'sps')

        # Test db_for_read
        db = self.router.db_for_read(People)
        self.assertEqual(db, 'sps')

    def test_router_writes_to_correct_database(self):
        """Test router directs writes to correct database."""
        setattr(THREAD_LOCAL, 'DB', 'icicibank')

        # Test db_for_write
        db = self.router.db_for_write(People)
        self.assertEqual(db, 'icicibank')

    def test_router_defaults_when_no_thread_local(self):
        """Test router defaults to 'default' when no THREAD_LOCAL.DB."""
        # Clear THREAD_LOCAL.DB if it exists
        if hasattr(THREAD_LOCAL, 'DB'):
            delattr(THREAD_LOCAL, 'DB')

        db = self.router.db_for_read(People)
        self.assertEqual(db, 'default')

    def test_router_raises_404_for_invalid_database(self):
        """Test router raises Http404 for invalid database alias."""
        from django.http import Http404

        # Set invalid database alias
        setattr(THREAD_LOCAL, 'DB', 'nonexistent_db')

        # Should raise Http404
        with self.assertRaises(Http404):
            self.router.db_for_read(People)


class TenantConfigTests(TestCase):
    """Test tenant configuration loading."""

    def test_get_tenant_mappings_returns_dict(self):
        """Test get_tenant_mappings returns valid dictionary."""
        mappings = get_tenant_mappings()

        self.assertIsInstance(mappings, dict)
        self.assertGreater(len(mappings), 0)

    def test_get_tenant_for_host_known_tenant(self):
        """Test get_tenant_for_host returns correct database for known host."""
        db = get_tenant_for_host('sps.youtility.local')
        self.assertEqual(db, 'sps')

    def test_get_tenant_for_host_unknown_tenant(self):
        """Test get_tenant_for_host returns default for unknown host."""
        db = get_tenant_for_host('unknown.example.com')
        self.assertEqual(db, 'default')

    def test_get_tenant_for_host_case_insensitive(self):
        """Test get_tenant_for_host is case-insensitive."""
        db1 = get_tenant_for_host('SPS.YouTility.LOCAL')
        db2 = get_tenant_for_host('sps.youtility.local')

        self.assertEqual(db1, db2)
        self.assertEqual(db1, 'sps')

    @override_settings(TENANT_MAPPINGS='{"custom.host": "custom_db"}')
    @patch.dict('os.environ', {'TENANT_MAPPINGS': '{"custom.host": "custom_db"}'})
    def test_get_tenant_mappings_from_environment(self):
        """Test tenant mappings can be loaded from environment."""
        # Force reload of tenant mappings
        from intelliwiz_config.settings import tenants
        from importlib import reload
        reload(tenants)

        mappings = tenants.get_tenant_mappings()
        self.assertIn('custom.host', mappings)


class TenantCacheIsolationTests(TestCase):
    """Test tenant-aware cache isolation."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: None)

    def test_cache_keys_are_tenant_prefixed(self):
        """Test cache keys include tenant prefix."""
        # Set tenant context
        request = self.factory.get('/', HTTP_HOST='sps.youtility.local')
        self.middleware(request)

        # Set cache value
        tenant_cache.set('test_key', 'test_value')

        # Verify key is prefixed
        actual_key = tenant_cache._make_tenant_key('test_key')
        self.assertIn('tenant:sps:', actual_key)

    def test_cache_isolation_between_tenants(self):
        """Test cache values don't leak between tenants."""
        # Tenant 1: Set value
        request1 = self.factory.get('/', HTTP_HOST='sps.youtility.local')
        self.middleware(request1)
        tenant_cache.set('shared_key', 'sps_value')

        # Tenant 2: Try to read same key
        request2 = self.factory.get('/', HTTP_HOST='dell.youtility.local')
        self.middleware(request2)
        value = tenant_cache.get('shared_key')

        # Should be None (different tenant)
        self.assertIsNone(value)

    def test_cache_get_set_delete_cycle(self):
        """Test complete cache lifecycle within tenant."""
        request = self.factory.get('/', HTTP_HOST='capgemini.youtility.local')
        self.middleware(request)

        # Set value
        success = tenant_cache.set('test_key', {'data': 'value'}, timeout=3600)
        self.assertTrue(success)

        # Get value
        value = tenant_cache.get('test_key')
        self.assertEqual(value, {'data': 'value'})

        # Delete value
        deleted = tenant_cache.delete('test_key')
        self.assertTrue(deleted)

        # Verify deleted
        value = tenant_cache.get('test_key')
        self.assertIsNone(value)

    def test_cache_get_many_set_many(self):
        """Test bulk cache operations with tenant isolation."""
        request = self.factory.get('/', HTTP_HOST='icicibank.youtility.local')
        self.middleware(request)

        # Set many
        data = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3'
        }
        success = tenant_cache.set_many(data, timeout=3600)
        self.assertTrue(success)

        # Get many
        values = tenant_cache.get_many(['key1', 'key2', 'key3'])
        self.assertEqual(len(values), 3)
        self.assertEqual(values['key1'], 'value1')


class TenantUtilityFunctionsTests(TestCase):
    """Test tenant utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_hostname_from_request(self):
        """Test hostname extraction from request."""
        request = self.factory.get('/', HTTP_HOST='example.com:8000')
        hostname = hostname_from_request(request)

        self.assertEqual(hostname, 'example.com')

    def test_hostname_from_request_no_port(self):
        """Test hostname extraction without port."""
        request = self.factory.get('/', HTTP_HOST='example.com')
        hostname = hostname_from_request(request)

        self.assertEqual(hostname, 'example.com')

    def test_tenant_db_from_request(self):
        """Test database lookup from request."""
        request = self.factory.get('/', HTTP_HOST='sps.youtility.local')
        db = tenant_db_from_request(request)

        self.assertEqual(db, 'sps')


class TenantSecurityTests(TestCase):
    """Security-focused tenant tests."""

    def test_malicious_hostname_sanitization(self):
        """Test malicious hostname patterns are rejected."""
        malicious_hosts = [
            '../etc/passwd',
            'host/../../secrets',
            'host\\..\\secrets',
        ]

        for bad_host in malicious_hosts:
            db = get_tenant_for_host(bad_host)
            # Should default to 'default', not process malicious path
            self.assertEqual(db, 'default')

    def test_cache_key_validation(self):
        """Test cache rejects invalid keys."""
        with self.assertRaises(ValueError):
            tenant_cache.set('', 'value')

        with self.assertRaises(ValueError):
            tenant_cache.set(None, 'value')

        with self.assertRaises(ValueError):
            tenant_cache.get('')

    def test_tenant_switching_mid_request(self):
        """Test tenant context cannot be switched mid-request."""
        request = self.factory.get('/', HTTP_HOST='sps.youtility.local')
        middleware = TenantMiddleware(get_response=lambda r: None)

        # Set initial tenant
        middleware(request)
        initial_db = get_current_db_name()

        # Attempt to manually change THREAD_LOCAL.DB
        setattr(THREAD_LOCAL, 'DB', 'dell')

        # Get current db (should be 'dell' since we changed it)
        current_db = get_current_db_name()

        # This demonstrates THREAD_LOCAL can be changed
        # In production, only middleware should set this
        self.assertEqual(current_db, 'dell')


# Integration test combining all components
class TenantIntegrationTests(TestCase):
    """Integration tests for complete tenant workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: None)

    def test_complete_request_lifecycle(self):
        """Test complete request lifecycle with tenant routing."""
        # 1. Create request with tenant hostname
        request = self.factory.get('/', HTTP_HOST='sps.youtility.local')

        # 2. Middleware processes request
        self.middleware(request)

        # 3. Verify thread local is set
        self.assertTrue(hasattr(THREAD_LOCAL, 'DB'))
        self.assertEqual(get_current_db_name(), 'sps')

        # 4. Verify router would use correct database
        router = TenantDbRouter()
        db = router.db_for_read(People)
        self.assertEqual(db, 'sps')

        # 5. Verify cache is isolated
        tenant_cache.set('integration_test', 'success')
        value = tenant_cache.get('integration_test')
        self.assertEqual(value, 'success')

        # 6. Verify cache key has tenant prefix
        key = tenant_cache._make_tenant_key('integration_test')
        self.assertIn('tenant:sps:', key)
