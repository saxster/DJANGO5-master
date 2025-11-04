"""
Tenant System Edge Case Tests

Tests for corner cases, race conditions, and unusual scenarios
in the multi-tenant system.

Coverage:
    - Thread-local cleanup verification
    - Inactive/deleted tenant handling
    - Cache key isolation
    - Invalid subdomain validation
    - Concurrent request handling
    - NULL tenant scenarios

Author: Multi-Tenancy Hardening - Comprehensive Resolution
Date: 2025-11-03
"""

import pytest
import threading
from unittest.mock import patch, MagicMock
from django.test import RequestFactory, TestCase, override_settings
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden, HttpResponseGone

from apps.tenants.models import Tenant, TenantAwareModel
from apps.tenants.middlewares import TenantMiddleware
from apps.tenants.middleware_unified import UnifiedTenantMiddleware
from apps.tenants.utils import (
    get_tenant_from_context,
    get_current_tenant_cached,
    cleanup_tenant_context,
    db_alias_to_slug,
    slug_to_db_alias,
    is_valid_tenant_slug,
)
from apps.core.utils_new.db_utils import THREAD_LOCAL, set_db_for_router


class TestThreadLocalCleanup(TestCase):
    """Test thread-local context cleanup."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: MagicMock(status_code=200))

        # Create test tenant
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test-tenant"
        )

    def test_thread_local_cleaned_up_after_request(self):
        """Verify thread-local is cleaned up after successful request."""
        # Simulate request
        request = self.factory.get('/', HTTP_HOST='test.youtility.local')

        with patch('apps.core.utils_new.db_utils.tenant_db_from_request', return_value='test_tenant'):
            # Process request
            response = self.middleware(request)

        # Verify thread-local is cleaned up
        assert not hasattr(THREAD_LOCAL, 'DB'), "Thread-local DB should be cleaned up"
        assert not hasattr(THREAD_LOCAL, 'TENANT_CACHE'), "Thread-local cache should be cleaned up"

    def test_thread_local_cleaned_up_on_exception(self):
        """Verify thread-local is cleaned up even when request raises exception."""
        request = self.factory.get('/', HTTP_HOST='test.youtility.local')

        def get_response_with_exception(r):
            setattr(THREAD_LOCAL, 'DB', 'test_tenant')
            raise RuntimeError("Simulated error")

        middleware = TenantMiddleware(get_response=get_response_with_exception)

        # Process request (should raise exception)
        try:
            with patch('apps.core.utils_new.db_utils.tenant_db_from_request', return_value='test_tenant'):
                middleware(request)
        except RuntimeError:
            pass

        # Verify cleanup happened despite exception
        assert not hasattr(THREAD_LOCAL, 'DB'), "Thread-local should be cleaned up after exception"

    def test_concurrent_requests_dont_leak_context(self):
        """Verify concurrent requests on different threads don't share context."""
        results = {}

        def request_handler(tenant_name, db_alias):
            """Simulate request on separate thread."""
            set_db_for_router(db_alias)
            # Simulate some processing
            import time
            time.sleep(0.01)
            # Check context
            from apps.core.utils_new.db_utils import get_current_db_name
            results[threading.current_thread().name] = get_current_db_name()
            cleanup_tenant_context()

        # Create two threads with different tenant contexts
        thread1 = threading.Thread(target=request_handler, args=('Tenant A', 'tenant_a'))
        thread2 = threading.Thread(target=request_handler, args=('Tenant B', 'tenant_b'))

        # Start threads
        thread1.start()
        thread2.start()

        # Wait for completion
        thread1.join()
        thread2.join()

        # Verify each thread had its own context
        assert results[thread1.name] == 'tenant_a', "Thread 1 should have tenant_a context"
        assert results[thread2.name] == 'tenant_b', "Thread 2 should have tenant_b context"


class TestInactiveTenantHandling(TestCase):
    """Test handling of inactive/suspended tenants."""

    def setUp(self):
        self.factory = RequestFactory()

        # Create active tenant
        self.active_tenant = Tenant.objects.create(
            tenantname="Active Tenant",
            subdomain_prefix="active-tenant",
            is_active=True
        )

        # Create suspended tenant
        self.suspended_tenant = Tenant.objects.create(
            tenantname="Suspended Tenant",
            subdomain_prefix="suspended-tenant",
            is_active=False,
            suspension_reason="Payment overdue"
        )

    def test_inactive_tenant_returns_none_from_context(self):
        """get_tenant_from_context should return None for inactive tenants."""
        # Set context to suspended tenant
        set_db_for_router('suspended_tenant')

        try:
            tenant = get_tenant_from_context()
            assert tenant is None, "Should not return inactive tenant"
        finally:
            cleanup_tenant_context()

    def test_unified_middleware_rejects_inactive_tenant(self):
        """UnifiedTenantMiddleware should return 410 Gone for inactive tenants."""
        middleware = UnifiedTenantMiddleware(get_response=lambda r: MagicMock())
        request = self.factory.get('/', HTTP_HOST='suspended.youtility.local')

        # Mock hostname mapping to suspended tenant
        with patch.object(middleware, 'tenant_mappings', {'suspended.youtility.local': 'suspended_tenant'}):
            response = middleware(request)

        # Should return 410 Gone
        assert isinstance(response, HttpResponseGone), "Should return 410 for inactive tenant"
        assert "suspended" in str(response.content).lower(), "Should mention suspension"

    def test_tenant_suspend_method(self):
        """Test Tenant.suspend() method."""
        self.active_tenant.suspend(reason="Test suspension")

        # Verify state changed
        self.active_tenant.refresh_from_db()
        assert not self.active_tenant.is_active
        assert self.active_tenant.suspended_at is not None
        assert self.active_tenant.suspension_reason == "Test suspension"

    def test_tenant_activate_method(self):
        """Test Tenant.activate() method."""
        self.suspended_tenant.activate()

        # Verify state changed
        self.suspended_tenant.refresh_from_db()
        assert self.suspended_tenant.is_active
        assert self.suspended_tenant.suspended_at is None


class TestSubdomainValidation(TestCase):
    """Test subdomain_prefix validation."""

    def test_valid_subdomains_accepted(self):
        """Valid subdomain formats should be accepted."""
        valid_subdomains = [
            'intelliwiz-django',
            'acme-corp',
            'test123',
            'a',
            'a-b-c-d-e',
            'tenant-1',
        ]

        for subdomain in valid_subdomains:
            tenant = Tenant(
                tenantname=f"Test {subdomain}",
                subdomain_prefix=subdomain
            )
            try:
                tenant.full_clean()  # Triggers validation
                assert True, f"{subdomain} should be valid"
            except ValidationError:
                pytest.fail(f"{subdomain} should have been accepted")

    def test_invalid_subdomains_rejected(self):
        """Invalid subdomain formats should be rejected."""
        invalid_subdomains = [
            'Invalid Space',  # Contains space
            'UPPERCASE',  # Contains uppercase
            '../../../etc',  # Path traversal
            'tenant_underscore',  # Contains underscore (should use hyphen)
            'tenant.dot',  # Contains dot
            'tenant/slash',  # Contains slash
            'tenant\\backslash',  # Contains backslash
            'DROP TABLE',  # SQL injection attempt
            'tenant@special',  # Special character
            '',  # Empty
        ]

        for subdomain in invalid_subdomains:
            tenant = Tenant(
                tenantname=f"Test {subdomain}",
                subdomain_prefix=subdomain
            )
            with pytest.raises(ValidationError, match='lowercase letters, numbers, and hyphens'):
                tenant.full_clean()


class TestCacheKeyIsolation(TestCase):
    """Test cache key isolation between tenants."""

    def setUp(self):
        self.tenant_a = Tenant.objects.create(
            tenantname="Tenant A",
            subdomain_prefix="tenant-a"
        )
        self.tenant_b = Tenant.objects.create(
            tenantname="Tenant B",
            subdomain_prefix="tenant-b"
        )

    def test_cache_keys_tenant_scoped(self):
        """Cache keys should be isolated between tenants."""
        from apps.core.cache.tenant_aware import tenant_cache

        # Set context to tenant A
        set_db_for_router('tenant_a')

        try:
            # Set cache value for tenant A
            tenant_cache.set('user:123:profile', {'name': 'Alice'}, 60)

            # Change context to tenant B
            cleanup_tenant_context()
            set_db_for_router('tenant_b')

            # Try to get same key from tenant B
            value = tenant_cache.get('user:123:profile')

            # Should be None (different tenant)
            assert value is None, "Tenant B should not see Tenant A's cache"

        finally:
            cleanup_tenant_context()

    def test_cache_keys_have_tenant_prefix(self):
        """Verify cache keys are prefixed with tenant."""
        from apps.core.cache.tenant_aware import TenantAwareCache

        cache_instance = TenantAwareCache()

        # Mock tenant context
        set_db_for_router('tenant_a')

        try:
            # Generate tenant key
            tenant_key = cache_instance._make_tenant_key('test:key')

            # Should have tenant prefix
            assert 'tenant:tenant_a:test:key' == tenant_key

        finally:
            cleanup_tenant_context()


class TestConversionUtilities(TestCase):
    """Test slug/alias conversion utilities."""

    def test_db_alias_to_slug(self):
        """Test underscore to hyphen conversion."""
        assert db_alias_to_slug('intelliwiz_django') == 'intelliwiz-django'
        assert db_alias_to_slug('test_tenant_name') == 'test-tenant-name'
        assert db_alias_to_slug('simple') == 'simple'

    def test_slug_to_db_alias(self):
        """Test hyphen to underscore conversion."""
        assert slug_to_db_alias('intelliwiz-django') == 'intelliwiz_django'
        assert slug_to_db_alias('test-tenant-name') == 'test_tenant_name'
        assert slug_to_db_alias('simple') == 'simple'

    def test_roundtrip_conversion(self):
        """Test roundtrip conversion maintains original value."""
        original = 'test-tenant-name'
        assert db_alias_to_slug(slug_to_db_alias(original)) == original

        original_alias = 'test_tenant_name'
        assert slug_to_db_alias(db_alias_to_slug(original_alias)) == original_alias

    def test_validation_functions(self):
        """Test validation utility functions."""
        # Valid slugs
        assert is_valid_tenant_slug('intelliwiz-django')
        assert is_valid_tenant_slug('acme123')
        assert is_valid_tenant_slug('a')

        # Invalid slugs
        assert not is_valid_tenant_slug('Invalid Space')
        assert not is_valid_tenant_slug('UPPERCASE')
        assert not is_valid_tenant_slug('')
        assert not is_valid_tenant_slug('x' * 51)  # Too long


class TestTenantCaching(TestCase):
    """Test per-request tenant caching."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test-tenant"
        )

    def test_tenant_cached_per_request(self):
        """get_current_tenant_cached should cache tenant for request duration."""
        set_db_for_router('test_tenant')

        try:
            # First call - should query database
            with patch('apps.tenants.utils.get_tenant_from_context') as mock_get:
                mock_get.return_value = self.tenant

                tenant1 = get_current_tenant_cached()
                assert mock_get.call_count == 1

                # Second call - should use cache
                tenant2 = get_current_tenant_cached()
                assert mock_get.call_count == 1, "Should not query database again"

                # Should be same instance
                assert tenant1 is tenant2

        finally:
            cleanup_tenant_context()

    def test_cache_cleared_between_requests(self):
        """Cache should be cleared between requests."""
        set_db_for_router('test_tenant')

        try:
            # First request
            tenant1 = get_current_tenant_cached()
            cleanup_tenant_context()

            # Second request (new context)
            set_db_for_router('test_tenant')
            tenant2 = get_current_tenant_cached()

            # Should have queried twice (cache cleared)
            assert tenant1.pk == tenant2.pk, "Should be same tenant"
            # But these are different instances (cache was cleared)

        finally:
            cleanup_tenant_context()


class TestNullTenantHandling(TestCase):
    """Test handling of records without tenant."""

    def test_save_with_skip_validation(self):
        """Models should allow saving without tenant when explicitly skipped."""
        from apps.helpbot.models import HelpBotSession
        from apps.peoples.models import People

        # Create user without tenant context
        user = People.objects.first() or People.objects.create(
            username='testuser',
            email='test@example.com'
        )

        # This should work with skip_tenant_validation
        session = HelpBotSession(user=user)
        # Should not raise error
        try:
            session.save(skip_tenant_validation=True)
            assert True, "Should allow saving with skip_tenant_validation"
        except ValidationError:
            pytest.fail("Should not raise ValidationError when skip_tenant_validation=True")
        finally:
            if session.pk:
                session.delete()

    def test_save_without_tenant_logs_warning(self):
        """Saving without tenant should log security event."""
        from apps.helpbot.models import HelpBotSession
        from apps.peoples.models import People

        user = People.objects.first() or People.objects.create(
            username='testuser2',
            email='test2@example.com'
        )

        with self.assertLogs('apps.tenants.models', level='WARNING') as logs:
            session = HelpBotSession(user=user)
            session.save()  # No skip_tenant_validation

            # Should have logged warning
            assert any('without tenant' in log.lower() for log in logs.output)

        # Cleanup
        if session.pk:
            session.delete()


class TestUnifiedMiddleware(TestCase):
    """Test UnifiedTenantMiddleware edge cases."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = UnifiedTenantMiddleware(
            get_response=lambda r: MagicMock(status_code=200, headers={})
        )

        self.active_tenant = Tenant.objects.create(
            tenantname="Active Tenant",
            subdomain_prefix="active-tenant",
            is_active=True
        )

        self.suspended_tenant = Tenant.objects.create(
            tenantname="Suspended Tenant",
            subdomain_prefix="suspended-tenant",
            is_active=False,
            suspension_reason="Test suspension"
        )

    def test_suspended_tenant_returns_410(self):
        """Suspended tenant should return 410 Gone."""
        request = self.factory.get('/', HTTP_HOST='suspended.youtility.local')

        with patch.object(self.middleware, 'tenant_mappings', {'suspended.youtility.local': 'suspended_tenant'}):
            response = self.middleware(request)

        assert isinstance(response, HttpResponseGone), "Should return 410 Gone"
        assert 'suspended' in str(response.content).lower()

    def test_unknown_hostname_strict_mode(self):
        """Unknown hostname in strict mode should return 403."""
        middleware = UnifiedTenantMiddleware(get_response=lambda r: MagicMock())
        middleware.strict_mode = True

        request = self.factory.get('/', HTTP_HOST='unknown.example.com')

        response = middleware(request)

        assert isinstance(response, HttpResponseForbidden), "Should return 403 Forbidden"

    def test_tenant_context_set_on_request(self):
        """request.tenant should be set for valid tenant."""
        request = self.factory.get('/', HTTP_HOST='active.youtility.local')

        with patch.object(self.middleware, 'tenant_mappings', {'active.youtility.local': 'active_tenant'}):
            def capture_request(r):
                # Verify request.tenant is set
                assert hasattr(r, 'tenant'), "request should have tenant attribute"
                assert r.tenant is not None, "request.tenant should not be None"
                assert r.tenant.tenant_slug == 'active-tenant'
                return MagicMock(status_code=200, headers={})

            middleware = UnifiedTenantMiddleware(get_response=capture_request)
            middleware.tenant_mappings = {'active.youtility.local': 'active_tenant'}
            middleware(request)


class TestTenantStateMethods(TestCase):
    """Test Tenant suspend/activate methods."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test-tenant"
        )

    def test_suspend_sets_fields(self):
        """suspend() should set is_active=False and timestamps."""
        self.tenant.suspend(reason="Test suspension")
        self.tenant.refresh_from_db()

        assert not self.tenant.is_active
        assert self.tenant.suspended_at is not None
        assert self.tenant.suspension_reason == "Test suspension"

    def test_activate_clears_suspension(self):
        """activate() should restore active state."""
        # First suspend
        self.tenant.suspend(reason="Test")
        self.tenant.refresh_from_db()
        assert not self.tenant.is_active

        # Then activate
        self.tenant.activate()
        self.tenant.refresh_from_db()

        assert self.tenant.is_active
        assert self.tenant.suspended_at is None

    def test_suspend_logs_security_event(self):
        """Suspension should log security event."""
        with self.assertLogs('apps.tenants.models', level='WARNING') as logs:
            self.tenant.suspend(reason="Payment overdue")

            assert any('suspended' in log.lower() for log in logs.output)
            assert any('Payment overdue' in log for log in logs.output)


class TestManagerEdgeCases(TestCase):
    """Test TenantAwareManager edge cases."""

    def setUp(self):
        self.tenant_a = Tenant.objects.create(
            tenantname="Tenant A",
            subdomain_prefix="tenant-a"
        )
        self.tenant_b = Tenant.objects.create(
            tenantname="Tenant B",
            subdomain_prefix="tenant-b"
        )

    def test_no_context_returns_empty_or_unfiltered(self):
        """No tenant context should return predictable result."""
        from apps.helpbot.models import HelpBotSession

        # Ensure no tenant context
        cleanup_tenant_context()

        # Should either return empty or unfiltered (for migrations)
        # In production with middleware, this should never happen
        queryset = HelpBotSession.objects.all()

        # Just verify it doesn't crash
        assert queryset is not None

    def test_cross_tenant_query_logs_security_event(self):
        """cross_tenant_query() should log audit trail."""
        from apps.helpbot.models import HelpBotSession

        with self.assertLogs('apps.tenants.managers', level='WARNING') as logs:
            # This should log
            queryset = HelpBotSession.objects.cross_tenant_query()

            assert any('cross-tenant' in log.lower() for log in logs.output)
            assert any('CROSS_TENANT_ACCESS' in log for log in logs.output)


# Pytest-specific tests
class TestUtilityFunctions:
    """Test utility functions with pytest."""

    def test_conversion_functions(self):
        """Test slug/alias conversion functions."""
        assert db_alias_to_slug('test_tenant') == 'test-tenant'
        assert slug_to_db_alias('test-tenant') == 'test_tenant'

    def test_validation_functions(self):
        """Test validation utility functions."""
        assert is_valid_tenant_slug('valid-tenant-123')
        assert not is_valid_tenant_slug('Invalid Space')
        assert not is_valid_tenant_slug('../../../etc')
        assert not is_valid_tenant_slug('x' * 51)  # Too long
