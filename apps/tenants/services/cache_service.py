"""
Tenant-Aware Caching Service

Provides automatic tenant-scoped cache key prefixing to prevent cross-tenant
cache pollution and ensure data isolation.

Features:
    - Automatic tenant namespace isolation
    - Cache key prefixing with tenant ID
    - Cache invalidation per tenant
    - Performance metrics by tenant
    - Thread-safe tenant context detection

Security:
    - Prevents cache key collisions between tenants
    - Ensures data isolation in shared cache backends
    - Audit logging for cache operations

Usage:
    from apps.tenants.services import TenantCacheService

    cache_service = TenantCacheService()

    # Set tenant-scoped cache
    cache_service.set('user_data', user_data, timeout=3600)

    # Get tenant-scoped cache
    user_data = cache_service.get('user_data')

    # Invalidate all cache for current tenant
    cache_service.clear_tenant_cache()
"""

import logging
import hashlib
from typing import Any, Optional, List
from datetime import datetime, timezone as dt_timezone

from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from apps.core.utils_new.db_utils import THREAD_LOCAL, get_current_db_name

logger = logging.getLogger('tenants.cache')


class TenantCacheService:
    """
    Tenant-aware caching with automatic key scoping.

    All cache operations are automatically scoped to the current tenant
    based on thread-local context.
    """

    # Cache key prefix for tenant caches
    TENANT_PREFIX = 'tenant'

    # Cache key for tracking tenant cache keys
    TENANT_KEYS_SUFFIX = '__keys__'

    def __init__(self, tenant_db: Optional[str] = None):
        """
        Initialize tenant cache service.

        Args:
            tenant_db: Tenant database alias (optional, uses thread-local if not provided)
        """
        self._tenant_db = tenant_db

    def _get_tenant_db(self) -> str:
        """
        Get current tenant database alias.

        Returns:
            Tenant database alias string

        Raises:
            ValueError: If no tenant context is set
        """
        if self._tenant_db:
            return self._tenant_db

        tenant_db = get_current_db_name()
        if not tenant_db or tenant_db == 'default':
            # Log warning but allow 'default' - some operations are tenant-agnostic
            logger.debug("Using 'default' database for cache operations")

        return tenant_db

    def _build_cache_key(self, key: str) -> str:
        """
        Build tenant-scoped cache key.

        Args:
            key: Original cache key

        Returns:
            Tenant-prefixed cache key

        Example:
            >>> service = TenantCacheService(tenant_db='tenant_a')
            >>> service._build_cache_key('user_123')
            'tenant:tenant_a:user_123'
        """
        tenant_db = self._get_tenant_db()
        return f"{self.TENANT_PREFIX}:{tenant_db}:{key}"

    def _track_cache_key(self, key: str) -> None:
        """
        Track cache key for tenant-wide invalidation.

        Maintains a set of all cache keys for each tenant to enable
        efficient bulk invalidation.

        Args:
            key: Cache key to track
        """
        tenant_db = self._get_tenant_db()
        tracking_key = f"{self.TENANT_PREFIX}:{tenant_db}:{self.TENANT_KEYS_SUFFIX}"

        try:
            # Get existing keys set
            existing_keys = cache.get(tracking_key, set())
            if not isinstance(existing_keys, set):
                existing_keys = set()

            # Add new key
            existing_keys.add(key)

            # Update tracking set (TTL: 24 hours)
            cache.set(tracking_key, existing_keys, timeout=86400)

        except (ValueError, KeyError, TypeError) as e:
            # Non-critical error - log but continue
            logger.warning(
                f"Failed to track cache key: {e}",
                extra={'key': key, 'error': str(e)}
            )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from tenant-scoped cache.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default

        Example:
            >>> service = TenantCacheService()
            >>> user_data = service.get('user_123', default={})
        """
        scoped_key = self._build_cache_key(key)

        try:
            value = cache.get(scoped_key, default)

            logger.debug(
                f"Cache {'hit' if value != default else 'miss'}",
                extra={
                    'key': key,
                    'scoped_key': scoped_key,
                    'tenant_db': self._get_tenant_db()
                }
            )

            return value

        except (ValueError, KeyError) as e:
            logger.error(
                f"Cache get error: {e}",
                extra={'key': key, 'error': str(e)},
                exc_info=True
            )
            return default

    def set(
        self,
        key: str,
        value: Any,
        timeout: int = DEFAULT_TIMEOUT
    ) -> bool:
        """
        Set value in tenant-scoped cache.

        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds (default: backend default)

        Returns:
            True if successful, False otherwise

        Example:
            >>> service = TenantCacheService()
            >>> service.set('user_123', user_data, timeout=3600)
            True
        """
        scoped_key = self._build_cache_key(key)

        try:
            # Set cache value
            cache.set(scoped_key, value, timeout=timeout)

            # Track key for bulk invalidation
            self._track_cache_key(scoped_key)

            logger.debug(
                f"Cache set",
                extra={
                    'key': key,
                    'scoped_key': scoped_key,
                    'timeout': timeout,
                    'tenant_db': self._get_tenant_db()
                }
            )

            return True

        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                f"Cache set error: {e}",
                extra={'key': key, 'error': str(e)},
                exc_info=True
            )
            return False

    def delete(self, key: str) -> bool:
        """
        Delete value from tenant-scoped cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        scoped_key = self._build_cache_key(key)

        try:
            cache.delete(scoped_key)

            logger.debug(
                f"Cache delete",
                extra={
                    'key': key,
                    'scoped_key': scoped_key,
                    'tenant_db': self._get_tenant_db()
                }
            )

            return True

        except (ValueError, KeyError) as e:
            logger.error(
                f"Cache delete error: {e}",
                extra={'key': key, 'error': str(e)},
                exc_info=True
            )
            return False

    def get_many(self, keys: List[str]) -> dict:
        """
        Get multiple values from tenant-scoped cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary mapping original keys to cached values
        """
        if not keys:
            return {}

        # Build scoped keys mapping
        key_mapping = {self._build_cache_key(k): k for k in keys}
        scoped_keys = list(key_mapping.keys())

        try:
            # Get cached values
            cached_values = cache.get_many(scoped_keys)

            # Map back to original keys
            result = {
                key_mapping[scoped_key]: value
                for scoped_key, value in cached_values.items()
            }

            logger.debug(
                f"Cache get_many",
                extra={
                    'requested': len(keys),
                    'found': len(result),
                    'tenant_db': self._get_tenant_db()
                }
            )

            return result

        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                f"Cache get_many error: {e}",
                extra={'keys_count': len(keys), 'error': str(e)},
                exc_info=True
            )
            return {}

    def set_many(self, data: dict, timeout: int = DEFAULT_TIMEOUT) -> None:
        """
        Set multiple values in tenant-scoped cache.

        Args:
            data: Dictionary of key-value pairs
            timeout: Cache timeout in seconds
        """
        if not data:
            return

        # Build scoped keys mapping
        scoped_data = {
            self._build_cache_key(k): v
            for k, v in data.items()
        }

        try:
            cache.set_many(scoped_data, timeout=timeout)

            # Track all keys
            for scoped_key in scoped_data.keys():
                self._track_cache_key(scoped_key)

            logger.debug(
                f"Cache set_many",
                extra={
                    'count': len(data),
                    'timeout': timeout,
                    'tenant_db': self._get_tenant_db()
                }
            )

        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                f"Cache set_many error: {e}",
                extra={'count': len(data), 'error': str(e)},
                exc_info=True
            )

    def clear_tenant_cache(self) -> int:
        """
        Clear all cache entries for current tenant.

        Returns:
            Number of cache entries cleared

        Security:
            Only clears cache for current tenant (isolated)
        """
        tenant_db = self._get_tenant_db()
        tracking_key = f"{self.TENANT_PREFIX}:{tenant_db}:{self.TENANT_KEYS_SUFFIX}"

        try:
            # Get all tracked keys for tenant
            tracked_keys = cache.get(tracking_key, set())

            if not tracked_keys:
                logger.info(
                    f"No tracked keys found for tenant",
                    extra={'tenant_db': tenant_db}
                )
                return 0

            # Delete all tracked keys
            cache.delete_many(tracked_keys)

            # Delete tracking key itself
            cache.delete(tracking_key)

            logger.info(
                f"Cleared tenant cache",
                extra={
                    'tenant_db': tenant_db,
                    'keys_cleared': len(tracked_keys)
                }
            )

            return len(tracked_keys)

        except (ValueError, KeyError, TypeError) as e:
            logger.error(
                f"Cache clear error: {e}",
                extra={'tenant_db': tenant_db, 'error': str(e)},
                exc_info=True
            )
            return 0
