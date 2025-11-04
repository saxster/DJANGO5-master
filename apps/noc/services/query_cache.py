"""
NOC Query Cache with Redis Backend.

Caches natural language query results to reduce LLM API calls and database queries.
Follows .claude/rules.md Rule #7 (<150 lines) and Rule #11 (specific exceptions).
"""

import logging
import hashlib
import json
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.conf import settings

__all__ = ['QueryCache']

logger = logging.getLogger('noc.nl_query')


class QueryCache:
    """
    Redis-backed cache for NL query results.

    Cache Strategy:
    - Key: MD5 hash of (query_text + user_id + tenant_id)
    - TTL: 5 minutes (configurable)
    - Namespace: noc:nl_query
    """

    CACHE_PREFIX = 'noc:nl_query'
    DEFAULT_TTL = 300  # 5 minutes in seconds

    @staticmethod
    def get_cache_key(query_text: str, user_id: int, tenant_id: int) -> str:
        """
        Generate cache key from query parameters.

        Args:
            query_text: Natural language query string
            user_id: User ID (for permission context)
            tenant_id: Tenant ID (for isolation)

        Returns:
            Cache key string
        """
        # Normalize query text (lowercase, strip whitespace)
        normalized = query_text.lower().strip()

        # Create hash of query + context
        key_data = f"{normalized}:{user_id}:{tenant_id}"
        key_hash = hashlib.md5(key_data.encode('utf-8')).hexdigest()

        return f"{QueryCache.CACHE_PREFIX}:{key_hash}"

    @staticmethod
    def get(query_text: str, user_id: int, tenant_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached query result.

        Args:
            query_text: Natural language query string
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            Cached result dict or None if not found/expired
        """
        cache_key = QueryCache.get_cache_key(query_text, user_id, tenant_id)

        try:
            cached_value = cache.get(cache_key)

            if cached_value is not None:
                logger.info(
                    f"Cache hit for query",
                    extra={
                        'cache_key': cache_key,
                        'user_id': user_id,
                        'tenant_id': tenant_id,
                    }
                )
                # Track cache hit for metrics
                QueryCache._increment_hit_counter()
                return cached_value

            # Cache miss
            logger.debug(f"Cache miss for query", extra={'cache_key': cache_key})
            QueryCache._increment_miss_counter()
            return None

        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
            # Fail gracefully - return None on cache errors
            return None

    @staticmethod
    def set(query_text: str, user_id: int, tenant_id: int, result: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Store query result in cache.

        Args:
            query_text: Natural language query string
            user_id: User ID
            tenant_id: Tenant ID
            result: Query result to cache
            ttl: Time-to-live in seconds (default: 5 minutes)

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = QueryCache.get_cache_key(query_text, user_id, tenant_id)
        ttl = ttl or QueryCache.DEFAULT_TTL

        try:
            # Validate result is serializable
            if not QueryCache._is_cacheable(result):
                logger.warning(f"Result not cacheable", extra={'cache_key': cache_key})
                return False

            # Store in cache
            cache.set(cache_key, result, timeout=ttl)

            logger.debug(
                f"Cached query result",
                extra={
                    'cache_key': cache_key,
                    'ttl': ttl,
                    'user_id': user_id,
                }
            )

            return True

        except Exception as e:
            logger.error(f"Cache storage error: {e}", exc_info=True)
            return False

    @staticmethod
    def invalidate(query_text: str, user_id: int, tenant_id: int) -> bool:
        """
        Invalidate specific cached query.

        Args:
            query_text: Natural language query string
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        cache_key = QueryCache.get_cache_key(query_text, user_id, tenant_id)

        try:
            cache.delete(cache_key)
            logger.info(f"Invalidated cache", extra={'cache_key': cache_key})
            return True

        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return False

    @staticmethod
    def invalidate_tenant(tenant_id: int) -> bool:
        """
        Invalidate all cached queries for a tenant.

        Note: This is expensive and should be used sparingly.
        Redis pattern matching used for bulk invalidation.

        Args:
            tenant_id: Tenant ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            # Get Redis client directly for pattern matching
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")

            # Pattern: noc:nl_query:*
            # This is approximate - we can't easily filter by tenant in key
            # Better approach: use Redis SCAN with pattern
            pattern = f"{QueryCache.CACHE_PREFIX}:*"
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = redis_conn.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted_count += redis_conn.delete(*keys)

                if cursor == 0:
                    break

            logger.info(
                f"Invalidated tenant cache",
                extra={'tenant_id': tenant_id, 'deleted_count': deleted_count}
            )
            return True

        except Exception as e:
            logger.error(f"Tenant cache invalidation error: {e}", exc_info=True)
            return False

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dict with hits, misses, hit_rate
        """
        hits = QueryCache._get_counter_value('hits')
        misses = QueryCache._get_counter_value('misses')
        total = hits + misses

        hit_rate = (hits / total * 100) if total > 0 else 0.0

        return {
            'hits': hits,
            'misses': misses,
            'total_queries': total,
            'hit_rate_percent': round(hit_rate, 2),
        }

    @staticmethod
    def _is_cacheable(result: Any) -> bool:
        """
        Check if result can be safely cached.

        Args:
            result: Result to validate

        Returns:
            True if cacheable, False otherwise
        """
        try:
            # Test JSON serialization
            json.dumps(result, default=str)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _increment_hit_counter():
        """Increment cache hit counter."""
        try:
            cache.incr(f"{QueryCache.CACHE_PREFIX}:stats:hits", delta=1, default=0)
        except Exception:
            pass  # Fail silently for metrics

    @staticmethod
    def _increment_miss_counter():
        """Increment cache miss counter."""
        try:
            cache.incr(f"{QueryCache.CACHE_PREFIX}:stats:misses", delta=1, default=0)
        except Exception:
            pass  # Fail silently for metrics

    @staticmethod
    def _get_counter_value(counter_name: str) -> int:
        """Get counter value."""
        try:
            value = cache.get(f"{QueryCache.CACHE_PREFIX}:stats:{counter_name}")
            return value if value is not None else 0
        except Exception:
            return 0

    @staticmethod
    def reset_stats():
        """Reset cache statistics."""
        try:
            cache.delete(f"{QueryCache.CACHE_PREFIX}:stats:hits")
            cache.delete(f"{QueryCache.CACHE_PREFIX}:stats:misses")
            logger.info("Cache statistics reset")
        except Exception as e:
            logger.error(f"Failed to reset cache stats: {e}")
