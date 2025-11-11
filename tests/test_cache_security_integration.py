"""
Integration tests for CacheSecurityMiddleware registration and functionality.

Validates middleware is properly registered and enforces cache security policies.
"""

import pytest
from django.test import override_settings


@pytest.mark.security
@pytest.mark.integration
class TestCacheSecurityMiddleware:
    """Test CacheSecurityMiddleware is registered and active."""

    def test_middleware_registered_in_settings(self):
        """Verify CacheSecurityMiddleware is in MIDDLEWARE list."""
        from django.conf import settings

        middleware_list = settings.MIDDLEWARE
        assert any(
            'CacheSecurityMiddleware' in m for m in middleware_list
        ), "CacheSecurityMiddleware not registered in settings.MIDDLEWARE"

    def test_cache_key_validation_prevents_wildcards(self):
        """Test cache key with wildcards is blocked."""
        from apps.core.caching.security import validate_cache_key, CacheSecurityError

        # Malicious cache keys with wildcards
        malicious_keys = [
            'user_*:permissions',
            '*:admin_perms',
            'tenant_**:data',
            'cache:*'
        ]

        for key in malicious_keys:
            with pytest.raises(CacheSecurityError):
                validate_cache_key(key)

    def test_cache_key_length_validation(self):
        """Test excessively long cache keys are blocked."""
        from apps.core.caching.security import validate_cache_key, CacheSecurityError

        # Excessively long key (>250 chars)
        long_key = 'a' * 300

        with pytest.raises(CacheSecurityError):
            validate_cache_key(long_key)
