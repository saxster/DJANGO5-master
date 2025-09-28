"""
Core caching utilities for tenant-aware and intelligent cache key generation
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Union
from django.core.cache import cache
from django.conf import settings
from django.http import HttpRequest
import logging

logger = logging.getLogger(__name__)


def get_tenant_cache_key(
    base_key: str,
    request: Optional[HttpRequest] = None,
    tenant_id: Optional[int] = None,
    client_id: Optional[int] = None,
    bu_id: Optional[int] = None,
    include_version: bool = True
) -> str:
    """
    Generate tenant-aware cache key for multi-tenant isolation

    Args:
        base_key: Base cache key name
        request: HTTP request object (extracts tenant info from session)
        tenant_id: Manual tenant ID override
        client_id: Manual client ID override
        bu_id: Manual business unit ID override
        include_version: Whether to include cache version in key

    Returns:
        Formatted cache key with tenant isolation and version
    """
    # Extract tenant information
    if request and hasattr(request, 'session'):
        tenant_id = tenant_id or request.session.get('tenant_id', 1)
        client_id = client_id or request.session.get('client_id', 1)
        bu_id = bu_id or request.session.get('bu_id', 1)
    else:
        tenant_id = tenant_id or getattr(settings, 'DEFAULT_TENANT_ID', 1)
        client_id = client_id or 1
        bu_id = bu_id or 1

    # Add version to base key if requested
    if include_version:
        from apps.core.caching.versioning import cache_version_manager
        version = cache_version_manager.get_version()
        versioned_base_key = f"{base_key}:v{version}"
    else:
        versioned_base_key = base_key

    # Create hierarchical key for efficient pattern matching
    cache_key = f"tenant:{tenant_id}:client:{client_id}:bu:{bu_id}:{versioned_base_key}"

    # Ensure key length is within Redis limits (250 chars)
    if len(cache_key) > 240:
        # Hash long keys while preserving tenant prefix for pattern matching
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        cache_key = f"tenant:{tenant_id}:client:{client_id}:bu:{bu_id}:hash:{key_hash}"

    return cache_key


def get_user_cache_key(
    base_key: str,
    user_id: int,
    request: Optional[HttpRequest] = None,
    include_tenant: bool = True
) -> str:
    """
    Generate user-specific cache key with optional tenant isolation

    Args:
        base_key: Base cache key name
        user_id: User ID for personalization
        request: HTTP request for tenant context
        include_tenant: Whether to include tenant information

    Returns:
        User-specific cache key
    """
    if include_tenant and request:
        tenant_key = get_tenant_cache_key(f"user:{user_id}:{base_key}", request)
        return tenant_key
    else:
        return f"user:{user_id}:{base_key}"


def cache_key_generator(
    prefix: str,
    *args,
    request: Optional[HttpRequest] = None,
    params: Optional[Dict[str, Any]] = None,
    version: Optional[str] = None
) -> str:
    """
    Advanced cache key generator with parameter hashing

    Args:
        prefix: Cache key prefix
        *args: Additional key components
        request: HTTP request for tenant context
        params: Parameters to include in key (will be hashed)
        version: Cache version for invalidation

    Returns:
        Generated cache key
    """
    key_parts = [prefix]

    # Add positional arguments
    key_parts.extend(str(arg) for arg in args)

    # Add hashed parameters if provided
    if params:
        # Sort parameters for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(sorted_params.encode()).hexdigest()[:12]
        key_parts.append(f"params:{param_hash}")

    # Add version if provided
    if version:
        key_parts.append(f"v:{version}")

    base_key = ":".join(key_parts)

    # Apply tenant awareness if request provided
    if request:
        return get_tenant_cache_key(base_key, request)

    return base_key


def get_cache_stats() -> Dict[str, Any]:
    """
    Get comprehensive cache statistics

    Returns:
        Dictionary with cache performance metrics
    """
    try:
        # Get Redis cache info
        redis_cache = cache._cache.get_master_client()
        info = redis_cache.info()

        stats = {
            'redis_memory_used': info.get('used_memory_human', 'N/A'),
            'redis_memory_peak': info.get('used_memory_peak_human', 'N/A'),
            'redis_connected_clients': info.get('connected_clients', 0),
            'redis_total_commands': info.get('total_commands_processed', 0),
            'redis_keyspace_hits': info.get('keyspace_hits', 0),
            'redis_keyspace_misses': info.get('keyspace_misses', 0),
            'cache_backend': str(type(cache._cache)),
        }

        # Calculate hit ratio
        hits = stats['redis_keyspace_hits']
        misses = stats['redis_keyspace_misses']
        if hits + misses > 0:
            stats['hit_ratio'] = round(hits / (hits + misses) * 100, 2)
        else:
            stats['hit_ratio'] = 0

        return stats

    except (ConnectionError, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error getting cache stats: {e}")
        return {'error': str(e)}


def warm_cache_pattern(
    pattern: str,
    data_generator: callable,
    timeout: int = 3600,
    chunk_size: int = 100
) -> Dict[str, Any]:
    """
    Warm cache with precomputed data for a given pattern

    Args:
        pattern: Cache key pattern to warm
        data_generator: Function that generates data for cache
        timeout: Cache timeout in seconds
        chunk_size: Number of keys to process at once

    Returns:
        Warming operation results
    """
    try:
        generated_keys = []
        errors = []

        # Generate data and cache it
        for key, data in data_generator():
            try:
                cache.set(key, data, timeout)
                generated_keys.append(key)

                # Process in chunks to avoid memory issues
                if len(generated_keys) >= chunk_size:
                    logger.info(f"Warmed {len(generated_keys)} cache keys for pattern: {pattern}")

            except (ConnectionError, ValueError) as e:
                errors.append(f"Error warming key {key}: {str(e)}")
                logger.error(f"Cache warming error for key {key}: {e}")

        return {
            'pattern': pattern,
            'keys_warmed': len(generated_keys),
            'errors': errors,
            'success': len(errors) == 0
        }

    except (ConnectionError, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Cache warming failed for pattern {pattern}: {e}")
        return {
            'pattern': pattern,
            'keys_warmed': 0,
            'errors': [str(e)],
            'success': False
        }


def clear_cache_pattern(pattern: str) -> Dict[str, Any]:
    """
    Clear all cache keys matching a pattern

    Args:
        pattern: Pattern to match (supports wildcards)

    Returns:
        Clearing operation results
    """
    try:
        redis_cache = cache._cache.get_master_client()

        # Find all keys matching pattern
        keys = redis_cache.keys(pattern)

        if keys:
            # Delete in chunks to avoid blocking
            deleted_count = 0
            chunk_size = 1000

            for i in range(0, len(keys), chunk_size):
                chunk = keys[i:i + chunk_size]
                deleted = redis_cache.delete(*chunk)
                deleted_count += deleted

            logger.info(f"Cleared {deleted_count} cache keys matching pattern: {pattern}")

            return {
                'pattern': pattern,
                'keys_cleared': deleted_count,
                'success': True
            }
        else:
            return {
                'pattern': pattern,
                'keys_cleared': 0,
                'success': True,
                'message': 'No keys found matching pattern'
            }

    except (ConnectionError, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error clearing cache pattern {pattern}: {e}")
        return {
            'pattern': pattern,
            'keys_cleared': 0,
            'success': False,
            'error': str(e)
        }


# Cache key patterns for different data types
CACHE_PATTERNS = {
    'DASHBOARD_METRICS': 'dashboard:metrics',
    'DROPDOWN_DATA': 'dropdown',
    'USER_PREFERENCES': 'user:prefs',
    'FORM_CHOICES': 'form:choices',
    'REPORT_DATA': 'report:data',
    'ASSET_STATUS': 'asset:status',
    'ATTENDANCE_SUMMARY': 'attendance:summary',
    'MONTHLY_TRENDS': 'trends:monthly'
}


# Cache timeout configurations (in seconds)
CACHE_TIMEOUTS = {
    'DASHBOARD_METRICS': 15 * 60,     # 15 minutes
    'DROPDOWN_DATA': 30 * 60,         # 30 minutes
    'USER_PREFERENCES': 60 * 60,      # 1 hour
    'FORM_CHOICES': 2 * 60 * 60,      # 2 hours
    'REPORT_DATA': 10 * 60,           # 10 minutes
    'ASSET_STATUS': 5 * 60,           # 5 minutes
    'ATTENDANCE_SUMMARY': 60 * 60,    # 1 hour
    'MONTHLY_TRENDS': 2 * 60 * 60,    # 2 hours
    'DEFAULT': 30 * 60                # 30 minutes default
}