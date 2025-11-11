"""
Caching utilities and decorators for Django application.

Provides:
- Generic cache decorator with key generation
- Dashboard metrics caching
- User permissions caching
- Cache invalidation helpers
- Cache monitoring utilities

Usage:
    from apps.core.utils_new.cache_utils import cache_result, invalidate_cache

    @cache_result(timeout=300, key_prefix='dashboard_metrics')
    def get_dashboard_metrics(site_id, date_range):
        # Expensive operation
        return metrics

Created: 2025-11-07
"""

import hashlib
import logging
from functools import wraps
from typing import Any, Callable, Optional, Union
from django.core.cache import cache
from django.conf import settings
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

logger = logging.getLogger(__name__)


def generate_cache_key(*args, prefix: str = '', **kwargs) -> str:
    """
    Generate a consistent cache key from function arguments.
    
    Args:
        *args: Positional arguments
        prefix: Key prefix for namespacing
        **kwargs: Keyword arguments
        
    Returns:
        MD5 hash-based cache key
        
    Example:
        >>> generate_cache_key(1, 2, prefix='metrics', site='HQ')
        'metrics_7c9e4f8a1b2c3d4e5f6a7b8c9d0e1f2a'
    """
    key_parts = [str(prefix)] if prefix else []
    key_parts.extend([str(arg) for arg in args])
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    
    key_string = '_'.join(key_parts)
    key_hash = hashlib.md5(key_string.encode()).hexdigest()
    
    return f"{prefix}_{key_hash}" if prefix else key_hash


def cache_result(
    timeout: int = 300,
    key_prefix: str = '',
    key_func: Optional[Callable] = None,
    unless: Optional[Callable] = None
) -> Callable:
    """
    Decorator to cache function results.
    
    Args:
        timeout: Cache timeout in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key namespacing
        key_func: Custom function to generate cache key
        unless: Condition function - if returns True, skip caching
        
    Returns:
        Decorated function with caching
        
    Example:
        @cache_result(timeout=600, key_prefix='site_stats')
        def get_site_statistics(site_id):
            return expensive_aggregation(site_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if caching should be skipped
            if unless and unless(*args, **kwargs):
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = generate_cache_key(
                    func.__name__,
                    *args,
                    prefix=key_prefix,
                    **kwargs
                )
            
            # Try to get from cache
            result = cache.get(cache_key)
            
            if result is None:
                # Cache miss - compute result
                logger.debug(f"Cache miss for key: {cache_key}")
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout)
                
                # Track cache miss
                _increment_cache_stat('misses')
            else:
                # Cache hit
                logger.debug(f"Cache hit for key: {cache_key}")
                _increment_cache_stat('hits')
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate = lambda *args, **kwargs: invalidate_cache(
            func.__name__, *args, prefix=key_prefix, **kwargs
        )
        
        return wrapper
    return decorator


def invalidate_cache(func_name: str, *args, prefix: str = '', **kwargs) -> bool:
    """
    Invalidate specific cache entry.
    
    Args:
        func_name: Name of cached function
        *args: Function arguments
        prefix: Cache key prefix
        **kwargs: Function keyword arguments
        
    Returns:
        True if cache was invalidated
        
    Example:
        invalidate_cache('get_site_statistics', site_id=123, prefix='site_stats')
    """
    cache_key = generate_cache_key(func_name, *args, prefix=prefix, **kwargs)
    deleted = cache.delete(cache_key)
    
    if deleted:
        logger.info(f"Cache invalidated for key: {cache_key}")
    else:
        logger.debug(f"No cache found for key: {cache_key}")
    
    return deleted


def invalidate_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    Note: Requires Redis backend with delete_pattern support.

    Args:
        pattern: Redis pattern (e.g., 'dashboard_*')

    Returns:
        Number of keys deleted

    Example:
        invalidate_pattern('user_perms_*')
    """
    try:
        if hasattr(cache, 'delete_pattern'):
            deleted = cache.delete_pattern(pattern)
            logger.info(f"Invalidated {deleted} cache keys matching: {pattern}")
            return deleted
        else:
            logger.warning("delete_pattern not supported by cache backend")
            return 0
    except CACHE_EXCEPTIONS as e:
        logger.error(f"Redis error invalidating cache pattern {pattern}: {e}")
        return 0
    except AttributeError as e:
        logger.warning(f"Cache backend doesn't support delete_pattern: {e}")
        return 0


def get_cache_stats() -> dict:
    """
    Get cache statistics (hits, misses, hit rate).
    
    Returns:
        Dictionary with cache statistics
        
    Example:
        >>> get_cache_stats()
        {'hits': 1500, 'misses': 500, 'hit_rate': 75.0}
    """
    hits = cache.get('_cache_stats_hits', 0)
    misses = cache.get('_cache_stats_misses', 0)
    total = hits + misses
    hit_rate = (hits / total * 100) if total > 0 else 0.0
    
    return {
        'hits': hits,
        'misses': misses,
        'total_requests': total,
        'hit_rate': round(hit_rate, 2)
    }


def reset_cache_stats() -> None:
    """Reset cache statistics counters."""
    cache.delete('_cache_stats_hits')
    cache.delete('_cache_stats_misses')
    logger.info("Cache statistics reset")


def _increment_cache_stat(stat_type: str) -> None:
    """
    Increment cache statistic counter.
    
    Args:
        stat_type: 'hits' or 'misses'
    """
    key = f'_cache_stats_{stat_type}'
    try:
        cache.incr(key)
    except ValueError:
        # Key doesn't exist, set to 1
        cache.set(key, 1, timeout=None)


def warm_cache(func: Callable, args_list: list) -> int:
    """
    Warm cache by pre-computing results for given arguments.

    Args:
        func: Cached function to warm
        args_list: List of argument tuples to pre-compute

    Returns:
        Number of cache entries warmed

    Example:
        warm_cache(get_site_statistics, [(1,), (2,), (3,)])
    """
    warmed = 0
    for args in args_list:
        try:
            if isinstance(args, tuple):
                func(*args)
            else:
                func(args)
            warmed += 1
        except ValueError as e:
            logger.error(f"Invalid value warming cache for {func.__name__}{args}: {e}")
        except TypeError as e:
            logger.error(f"Type error warming cache for {func.__name__}{args}: {e}")
        except KeyError as e:
            logger.error(f"Key error warming cache for {func.__name__}{args}: {e}")
        except CACHE_EXCEPTIONS as e:
            logger.error(f"Cache error warming cache for {func.__name__}{args}: {e}")

    logger.info(f"Warmed {warmed} cache entries for {func.__name__}")
    return warmed


# Specific caching helpers

def cache_user_permissions(user_id: int, permissions: dict, timeout: int = 900) -> None:
    """
    Cache user permissions (default 15 minutes).
    
    Args:
        user_id: User ID
        permissions: Permissions dictionary
        timeout: Cache timeout in seconds
    """
    cache_key = f"user_perms_{user_id}"
    cache.set(cache_key, permissions, timeout)
    logger.debug(f"Cached permissions for user {user_id}")


def get_cached_user_permissions(user_id: int) -> Optional[dict]:
    """
    Retrieve cached user permissions.
    
    Args:
        user_id: User ID
        
    Returns:
        Cached permissions or None if not found
    """
    cache_key = f"user_perms_{user_id}"
    return cache.get(cache_key)


def invalidate_user_permissions(user_id: int) -> bool:
    """
    Invalidate cached user permissions.
    
    Args:
        user_id: User ID
        
    Returns:
        True if cache was invalidated
    """
    cache_key = f"user_perms_{user_id}"
    deleted = cache.delete(cache_key)
    if deleted:
        logger.info(f"Invalidated permissions cache for user {user_id}")
    return deleted


__all__ = [
    'generate_cache_key',
    'cache_result',
    'invalidate_cache',
    'invalidate_pattern',
    'get_cache_stats',
    'reset_cache_stats',
    'warm_cache',
    'cache_user_permissions',
    'get_cached_user_permissions',
    'invalidate_user_permissions',
]
