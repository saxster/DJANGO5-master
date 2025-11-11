"""
Cache Invalidation Pattern Tests

Tests fix for Ultrathink Phase 4:
- Issue #3: NOC cache invalidation pattern mismatch

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Test cache key pattern matching
"""

import pytest
from unittest.mock import patch, Mock, call
from django.test import TestCase
from django.core.cache import cache

from apps.noc.services.cache_service import NOCCacheService


class TestNOCCacheInvalidation(TestCase):
    """Test cache invalidation patterns match actual cache keys."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    @patch('apps.noc.services.cache_service.NOCCacheService._tenant_scope')
    @patch('apps.noc.services.cache_service.cache')
    def test_tenant_cache_invalidation_pattern_matches_keys(
        self,
        mock_cache,
        mock_tenant_scope
    ):
        """
        Test that invalidate_tenant_cache() uses correct pattern to match real keys.

        Issue #3: Previously used pattern "tenant_{scope}:*:tenant_{id}:*"
        but actual keys have format "tenant_{scope}:{type}:user_{id}:{hash}".
        Pattern never matched, so invalidation deleted nothing.

        Fix: Pattern now "tenant_{tenant_id}:*" to match actual key structure.
        """
        tenant_id = 123
        mock_tenant_scope.return_value = tenant_id

        # Call invalidation
        NOCCacheService.invalidate_tenant_cache(tenant_id)

        # Verify correct pattern was used
        mock_cache.delete_pattern.assert_called_once()
        call_args = mock_cache.delete_pattern.call_args[0][0]

        # Pattern should be: "noc_cache:tenant_{tenant_id}:*"
        expected_pattern = f"noc_cache:tenant_{tenant_id}:*"
        assert call_args == expected_pattern, (
            f"Expected pattern '{expected_pattern}', got '{call_args}'"
        )

        # Pattern should NOT have double tenant reference (the bug)
        assert call_args.count('tenant_') == 1, (
            "Pattern should have exactly ONE tenant_ reference, not two"
        )

    def test_tenant_invalidation_deletes_dashboard_cache(self):
        """
        Test that tenant invalidation actually deletes dashboard cache keys.

        Validates that the fixed pattern matches real dashboard cache keys
        created by _build_cache_key().
        """
        tenant_id = 456
        user_id = 789
        filters = {'status': 'active'}

        # Set up cache key matching actual structure
        with patch('apps.noc.services.cache_service.NOCCacheService._tenant_scope', return_value=tenant_id):
            # Create a cache key using the service's own method
            cache_key = NOCCacheService._build_cache_key(
                data_type='dashboard',
                user_id=user_id,
                filters=filters
            )

            # Cache some data
            cache.set(cache_key, {'test': 'data'}, 300)

            # Verify data is cached
            assert cache.get(cache_key) is not None

            # Invalidate tenant cache
            NOCCacheService.invalidate_tenant_cache(tenant_id)

            # Verify data was deleted
            assert cache.get(cache_key) is None, (
                "Cache key should be deleted by tenant invalidation"
            )

    def test_tenant_invalidation_deletes_metrics_cache(self):
        """
        Test that tenant invalidation deletes metrics cache keys.

        Validates that the fixed pattern matches real metrics cache keys
        created by set_metrics_cache().
        """
        tenant_id = 101
        client_id = 202

        with patch('apps.noc.services.cache_service.NOCCacheService._tenant_scope', return_value=tenant_id):
            # Set metrics cache
            metrics_data = {'count': 50, 'avg_response': 120}
            NOCCacheService.set_metrics_cache(client_id, metrics_data)

            # Verify metrics are cached
            cached_metrics = NOCCacheService.get_metrics_cached(client_id)
            assert cached_metrics is not None
            assert cached_metrics['count'] == 50

            # Invalidate tenant cache
            NOCCacheService.invalidate_tenant_cache(tenant_id)

            # Verify metrics were deleted
            cached_metrics_after = NOCCacheService.get_metrics_cached(client_id)
            assert cached_metrics_after is None, (
                "Metrics cache should be deleted by tenant invalidation"
            )

    @patch('apps.noc.services.cache_service.NOCCacheService._tenant_scope')
    def test_multiple_users_same_tenant_invalidated_together(self, mock_tenant_scope):
        """
        Test that invalidating a tenant clears cache for all users in that tenant.

        Validates that pattern wildcard (*) matches all user-specific keys
        within a tenant.
        """
        tenant_id = 999
        mock_tenant_scope.return_value = tenant_id

        # Create cache keys for multiple users
        for user_id in [1, 2, 3]:
            cache_key = NOCCacheService._build_cache_key(
                data_type='dashboard',
                user_id=user_id,
                filters={}
            )
            cache.set(cache_key, {'user': user_id}, 300)

        # Verify all keys are cached
        for user_id in [1, 2, 3]:
            cache_key = NOCCacheService._build_cache_key(
                data_type='dashboard',
                user_id=user_id,
                filters={}
            )
            assert cache.get(cache_key) is not None

        # Invalidate tenant cache
        NOCCacheService.invalidate_tenant_cache(tenant_id)

        # Verify all user keys were deleted
        for user_id in [1, 2, 3]:
            cache_key = NOCCacheService._build_cache_key(
                data_type='dashboard',
                user_id=user_id,
                filters={}
            )
            assert cache.get(cache_key) is None, (
                f"User {user_id} cache should be deleted with tenant invalidation"
            )

    @patch('apps.noc.services.cache_service.NOCCacheService._tenant_scope')
    def test_tenant_invalidation_does_not_affect_other_tenants(self, mock_tenant_scope):
        """
        Test that tenant invalidation doesn't delete cache from other tenants.

        Security: Validates tenant isolation is maintained in cache invalidation.
        """
        tenant_1 = 100
        tenant_2 = 200

        # Set cache for tenant 1
        mock_tenant_scope.return_value = tenant_1
        cache_key_1 = NOCCacheService._build_cache_key(
            data_type='dashboard',
            user_id=1,
            filters={}
        )
        cache.set(cache_key_1, {'tenant': tenant_1}, 300)

        # Set cache for tenant 2
        mock_tenant_scope.return_value = tenant_2
        cache_key_2 = NOCCacheService._build_cache_key(
            data_type='dashboard',
            user_id=1,
            filters={}
        )
        cache.set(cache_key_2, {'tenant': tenant_2}, 300)

        # Verify both are cached
        assert cache.get(cache_key_1) is not None
        assert cache.get(cache_key_2) is not None

        # Invalidate only tenant 1
        NOCCacheService.invalidate_tenant_cache(tenant_1)

        # Tenant 1 cache deleted, tenant 2 cache intact
        assert cache.get(cache_key_1) is None, "Tenant 1 cache should be deleted"
        assert cache.get(cache_key_2) is not None, (
            "Tenant 2 cache should NOT be deleted"
        )

    def test_old_pattern_would_not_match(self):
        """
        Test that the OLD buggy pattern would not have matched actual keys.

        This test documents the bug: validates that the old pattern
        "tenant_{scope}:*:tenant_{id}:*" would not match keys like
        "tenant_{scope}:{type}:user_{id}:{hash}".
        """
        tenant_id = 456

        # Simulate old buggy pattern
        old_pattern = f"noc_cache:tenant_{tenant_id}:*:tenant_{tenant_id}:*"

        # Actual cache key structure
        actual_key = f"noc_cache:tenant_{tenant_id}:dashboard:user_789:abc123de"

        # The old pattern expects "tenant_" to appear TWICE
        # But actual key only has it ONCE at the start
        # This would never match with Redis KEYS or Django cache patterns

        # Count occurrences
        tenant_refs_in_pattern = old_pattern.count('tenant_')
        tenant_refs_in_key = actual_key.count('tenant_')

        assert tenant_refs_in_pattern == 2, "Old pattern had 2 tenant_ references"
        assert tenant_refs_in_key == 1, "Actual key has 1 tenant_ reference"

        # This mismatch is why invalidation never worked
        assert tenant_refs_in_pattern != tenant_refs_in_key, (
            "Pattern mismatch explains why cache invalidation didn't work"
        )
