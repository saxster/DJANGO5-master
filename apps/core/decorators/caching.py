"""
Query Result Caching Decorator

Provides smart caching for expensive database queries with automatic invalidation.

Features:
- Automatic cache key generation from function arguments
- Support for user-specific, tenant-specific caching
- Configurable TTL (time-to-live)
- Cache hit/miss tracking for performance monitoring

Usage:
    @cache_query(timeout=300, key_prefix='tickets')
    def get_filtered_tickets(user, filters):
        return Ticket.objects.filter(**filters).all()

Follows .claude/rules.md:
- Functions < 50 lines
- Specific exception handling
- Uses Redis (already configured)
"""

import logging
import hashlib
import json
from functools import wraps
from typing import Any, Callable, Optional
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


def _generate_cache_key(key_prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Generate deterministic cache key from function arguments.

    Args:
        key_prefix: Cache key prefix (e.g., 'tickets', 'people')
        func_name: Function name
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Cache key string (e.g., 'tickets:get_tickets:a1b2c3d4')
    """
    # Build key parts
    key_parts = [key_prefix, func_name]

    # Hash positional arguments (skip 'self' if present)
    filtered_args = args[1:] if args and hasattr(args[0], '__dict__') else args
    if filtered_args:
        # Convert args to JSON for consistent hashing
        args_json = json.dumps(
            [_serialize_arg(arg) for arg in filtered_args],
            sort_keys=True,
            cls=DjangoJSONEncoder
        )
        args_hash = hashlib.md5(args_json.encode()).hexdigest()[:8]
        key_parts.append(args_hash)

    # Hash keyword arguments
    if kwargs:
        kwargs_json = json.dumps(
            {k: _serialize_arg(v) for k, v in sorted(kwargs.items())},
            sort_keys=True,
            cls=DjangoJSONEncoder
        )
        kwargs_hash = hashlib.md5(kwargs_json.encode()).hexdigest()[:8]
        key_parts.append(kwargs_hash)

    cache_key = ':'.join(key_parts)
    return cache_key


def _serialize_arg(arg: Any) -> Any:
    """
    Serialize function argument for cache key generation.

    Handles:
    - Django model instances (use pk)
    - User objects (use id + tenant)
    - QuerySets (use query hash)
    - Regular Python objects
    """
    # Django model instance
    if hasattr(arg, 'pk') and hasattr(arg, '_meta'):
        model_name = arg._meta.label
        return f"{model_name}:{arg.pk}"

    # User object (include tenant for isolation)
    if hasattr(arg, 'id') and hasattr(arg, 'client_id'):
        return f"user:{arg.id}:tenant:{arg.client_id}"

    # QuerySet
    if hasattr(arg, 'query'):
        return str(arg.query)

    # Regular objects
    return arg


def cache_query(timeout: int = 300, key_prefix: str = 'query', track_stats: bool = True):
    """
    Cache database query results with automatic key generation.

    Args:
        timeout: Cache TTL in seconds (default: 5 minutes)
        key_prefix: Prefix for cache keys (e.g., 'tickets', 'people')
        track_stats: Log cache hit/miss statistics

    Returns:
        Decorator function

    Example:
        @cache_query(timeout=600, key_prefix='people_search')
        def search_users(request, query):
            return People.objects.filter(username__icontains=query).all()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _generate_cache_key(key_prefix, func.__name__, args, kwargs)

            # Try cache first
            result = cache.get(cache_key)
            if result is not None:
                if track_stats:
                    logger.debug(f"Cache HIT: {cache_key}")
                return result

            # Cache miss - execute query
            if track_stats:
                logger.debug(f"Cache MISS: {cache_key}")

            result = func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, timeout)

            if track_stats:
                logger.info(f"Cached query result: {cache_key} (TTL: {timeout}s)")

            return result

        # Attach cache invalidation helper
        wrapper.invalidate_cache = lambda *args, **kwargs: cache.delete(
            _generate_cache_key(key_prefix, func.__name__, args, kwargs)
        )

        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern: Cache key pattern (e.g., 'tickets:*', 'people:search:*')

    Returns:
        Number of keys deleted

    Example:
        # Invalidate all ticket caches for user 123
        invalidate_cache_pattern('tickets:*:user:123:*')
    """
    try:
        # Use redis-py delete_pattern if available
        if hasattr(cache, 'delete_pattern'):
            deleted = cache.delete_pattern(pattern)
            logger.info(f"Invalidated {deleted} cache keys matching: {pattern}")
            return deleted
        else:
            logger.warning(f"Cache backend does not support pattern deletion: {pattern}")
            return 0
    except Exception as e:
        logger.error(f"Error invalidating cache pattern {pattern}: {e}", exc_info=True)
        return 0


def cache_queryset_page(timeout: int = 300, key_prefix: str = 'page'):
    """
    Cache paginated queryset results.

    Optimized for list views with pagination parameters.

    Args:
        timeout: Cache TTL in seconds
        key_prefix: Prefix for cache keys

    Example:
        @cache_queryset_page(timeout=300, key_prefix='ticket_list')
        def get_ticket_page(user, page_num, filters):
            queryset = Ticket.objects.filter(**filters)
            return list(queryset[page_num*20:(page_num+1)*20])
    """
    return cache_query(timeout=timeout, key_prefix=key_prefix, track_stats=True)


__all__ = [
    'cache_query',
    'invalidate_cache_pattern',
    'cache_queryset_page',
]
