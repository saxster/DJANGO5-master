"""
Tenant-Aware Cache Service

Provides cache operations with automatic tenant isolation via key prefixing.

Security:
    - Prevents cross-tenant cache pollution
    - Automatic key prefixing based on current tenant context
    - Audit logging for cache operations

Compliance:
    - Rule #11: Specific exception handling (no generic Exception)
    - Performance: <5ms overhead for key prefixing
"""

import logging
import hashlib
from typing import Any, Optional, Union, List
from django.core.cache import cache as default_cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class TenantAwareCache:
    """
    Tenant-isolated cache wrapper.

    Automatically prefixes all cache keys with current tenant context
    to prevent cross-tenant data leakage.

    Example:
        >>> from apps.core.cache.tenant_aware import tenant_cache
        >>> tenant_cache.set('user:123', user_data, timeout=3600)
        # Actual key: 'tenant:intelliwiz_django:user:123'
    """

    def __init__(self, cache_backend=None):
        """
        Initialize tenant-aware cache.

        Args:
            cache_backend: Django cache backend (defaults to 'default')
        """
        self.cache = cache_backend or default_cache
        self.prefix_template = "tenant:{tenant}:{key}"

    def _get_tenant_prefix(self) -> str:
        """
        Get current tenant identifier for cache key prefixing.

        Returns:
            str: Tenant database name (e.g., 'intelliwiz_django')

        Security:
            - Uses thread-local tenant context
            - Safe fallback to 'default' tenant
        """
        try:
            tenant_db = get_current_db_name()
            return tenant_db
        except (AttributeError, ImportError) as e:
            logger.warning(f"Failed to get tenant context: {e}")
            return 'default'

    def _make_tenant_key(self, key: str) -> str:
        """
        Create tenant-prefixed cache key.

        Args:
            key: Original cache key

        Returns:
            str: Tenant-prefixed key

        Example:
            >>> cache._make_tenant_key('user:123')
            'tenant:intelliwiz_django:user:123'
        """
        tenant = self._get_tenant_prefix()
        prefixed_key = self.prefix_template.format(tenant=tenant, key=key)

        # Log for audit if key contains sensitive patterns
        if any(pattern in key.lower() for pattern in ['password', 'secret', 'token']):
            logger.warning(
                "Potentially sensitive data cached",
                extra={
                    'tenant': tenant,
                    'key_pattern': key.split(':')[0] if ':' in key else 'unknown',
                    'security_event': 'sensitive_cache_key'
                }
            )

        return prefixed_key

    def get(self, key: str, default=None) -> Any:
        """
        Get value from tenant-isolated cache.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default

        Raises:
            ValueError: If key is empty or invalid
        """
        if not key or not isinstance(key, str):
            raise ValueError("Cache key must be a non-empty string")

        tenant_key = self._make_tenant_key(key)

        try:
            value = self.cache.get(tenant_key, default)
            return value
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Cache get failed for key '{key}': {e}",
                extra={'tenant': self._get_tenant_prefix(), 'operation': 'get'}
            )
            return default

    def set(
        self,
        key: str,
        value: Any,
        timeout: Optional[int] = DEFAULT_TIMEOUT
    ) -> bool:
        """
        Set value in tenant-isolated cache.

        Args:
            key: Cache key
            value: Value to cache
            timeout: Expiration timeout in seconds

        Returns:
            bool: True if successful

        Raises:
            ValueError: If key is empty or invalid
        """
        if not key or not isinstance(key, str):
            raise ValueError("Cache key must be a non-empty string")

        tenant_key = self._make_tenant_key(key)

        try:
            success = self.cache.set(tenant_key, value, timeout)
            return success
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Cache set failed for key '{key}': {e}",
                extra={'tenant': self._get_tenant_prefix(), 'operation': 'set'}
            )
            return False

    def delete(self, key: str) -> bool:
        """
        Delete value from tenant-isolated cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key was deleted

        Raises:
            ValueError: If key is empty or invalid
        """
        if not key or not isinstance(key, str):
            raise ValueError("Cache key must be a non-empty string")

        tenant_key = self._make_tenant_key(key)

        try:
            success = self.cache.delete(tenant_key)
            return success
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Cache delete failed for key '{key}': {e}",
                extra={'tenant': self._get_tenant_prefix(), 'operation': 'delete'}
            )
            return False

    def get_many(self, keys: List[str]) -> dict:
        """
        Get multiple values from tenant-isolated cache.

        Args:
            keys: List of cache keys

        Returns:
            dict: Mapping of keys to values (without tenant prefix)
        """
        if not keys:
            return {}

        tenant_keys = {k: self._make_tenant_key(k) for k in keys}

        try:
            cached_values = self.cache.get_many(tenant_keys.values())

            # Reverse the tenant prefix mapping
            result = {}
            for original_key, tenant_key in tenant_keys.items():
                if tenant_key in cached_values:
                    result[original_key] = cached_values[tenant_key]

            return result
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Cache get_many failed: {e}",
                extra={'tenant': self._get_tenant_prefix(), 'operation': 'get_many'}
            )
            return {}

    def set_many(self, data: dict, timeout: Optional[int] = DEFAULT_TIMEOUT) -> bool:
        """
        Set multiple values in tenant-isolated cache.

        Args:
            data: Dictionary of key-value pairs
            timeout: Expiration timeout in seconds

        Returns:
            bool: True if all keys were set successfully
        """
        if not data:
            return True

        tenant_data = {
            self._make_tenant_key(k): v
            for k, v in data.items()
        }

        try:
            failed_keys = self.cache.set_many(tenant_data, timeout)
            return len(failed_keys) == 0
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Cache set_many failed: {e}",
                extra={'tenant': self._get_tenant_prefix(), 'operation': 'set_many'}
            )
            return False

    def incr(self, key: str, delta: int = 1) -> int:
        """
        Increment integer value in cache.

        Args:
            key: Cache key
            delta: Increment amount

        Returns:
            int: New value after increment

        Raises:
            ValueError: If key doesn't exist or value is not an integer
        """
        tenant_key = self._make_tenant_key(key)

        try:
            return self.cache.incr(tenant_key, delta)
        except ValueError as e:
            # Key doesn't exist or not an integer
            raise ValueError(f"Cannot increment key '{key}': {e}") from e
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Cache incr failed for key '{key}': {e}",
                extra={'tenant': self._get_tenant_prefix(), 'operation': 'incr'}
            )
            raise

    def decr(self, key: str, delta: int = 1) -> int:
        """
        Decrement integer value in cache.

        Args:
            key: Cache key
            delta: Decrement amount

        Returns:
            int: New value after decrement

        Raises:
            ValueError: If key doesn't exist or value is not an integer
        """
        tenant_key = self._make_tenant_key(key)

        try:
            return self.cache.decr(tenant_key, delta)
        except ValueError as e:
            raise ValueError(f"Cannot decrement key '{key}': {e}") from e
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"Cache decr failed for key '{key}': {e}",
                extra={'tenant': self._get_tenant_prefix(), 'operation': 'decr'}
            )
            raise

    def clear_tenant_cache(self) -> bool:
        """
        Clear all cache entries for current tenant.

        WARNING: This is a destructive operation.

        Returns:
            bool: True if successful

        Security:
            - Only clears current tenant's cache
            - Logs operation for audit
        """
        tenant = self._get_tenant_prefix()

        logger.warning(
            f"Clearing entire cache for tenant: {tenant}",
            extra={'tenant': tenant, 'security_event': 'cache_clear'}
        )

        try:
            # Django cache doesn't have tenant-aware clear
            # We need to track keys or use pattern-based deletion
            # This is a placeholder - actual implementation depends on cache backend
            logger.error(
                "Tenant-wide cache clear not implemented - requires Redis SCAN",
                extra={'tenant': tenant}
            )
            return False
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Cache clear failed: {e}", extra={'tenant': tenant})
            return False


# Global tenant-aware cache instance
tenant_cache = TenantAwareCache()
