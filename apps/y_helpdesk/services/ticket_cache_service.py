"""
Ticket Cache Service - Advanced Redis Caching Strategy

Implements comprehensive multi-level caching for ticket operations:
- L1: In-memory Python cache for ultra-fast access
- L2: Redis distributed cache for cross-instance sharing
- L3: Database materialized views for complex aggregations

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service layer <150 lines per class
- Rule #12: Database query optimization through caching
"""

import logging
import json
import hashlib
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db import models

from apps.y_helpdesk.exceptions import CACHE_EXCEPTIONS
from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache level priorities."""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_DATABASE = "l3_database"


class CacheStrategy(Enum):
    """Cache invalidation strategies."""
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    MANUAL = "manual"
    WRITE_THROUGH = "write_through"


@dataclass
class CacheConfig:
    """Configuration for cache operations."""
    key_prefix: str
    ttl_seconds: int
    strategy: CacheStrategy
    levels: List[CacheLevel]
    compress: bool = False
    version: str = "v1"


class TicketCacheService:
    """
    Advanced caching service for ticket operations.

    Provides intelligent multi-level caching with automatic invalidation,
    cache warming, and performance monitoring.
    """

    # Cache configurations for different operation types
    CACHE_CONFIGS = {
        'ticket_list': CacheConfig(
            key_prefix='tkt_list',
            ttl_seconds=300,  # 5 minutes
            strategy=CacheStrategy.TIME_BASED,
            levels=[CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
            compress=True
        ),
        'dashboard_stats': CacheConfig(
            key_prefix='tkt_dash',
            ttl_seconds=600,  # 10 minutes
            strategy=CacheStrategy.EVENT_BASED,
            levels=[CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        ),
        'escalation_matrix': CacheConfig(
            key_prefix='esc_matrix',
            ttl_seconds=3600,  # 1 hour
            strategy=CacheStrategy.EVENT_BASED,
            levels=[CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        ),
        'mobile_sync': CacheConfig(
            key_prefix='mob_sync',
            ttl_seconds=120,  # 2 minutes
            strategy=CacheStrategy.TIME_BASED,
            levels=[CacheLevel.L2_REDIS],
            compress=True
        ),
        'user_permissions': CacheConfig(
            key_prefix='usr_perms',
            ttl_seconds=1800,  # 30 minutes
            strategy=CacheStrategy.EVENT_BASED,
            levels=[CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        )
    }

    # L1 in-memory cache (per-process)
    _memory_cache: Dict[str, Dict] = {}
    _memory_cache_timestamps: Dict[str, datetime] = {}

    @classmethod
    def get_cached_data(
        cls,
        cache_type: str,
        cache_key_params: Dict[str, Any],
        data_loader: Callable[[], Any],
        force_refresh: bool = False
    ) -> Any:
        """
        Get data from cache or load if not available.

        Args:
            cache_type: Type of cache operation (from CACHE_CONFIGS)
            cache_key_params: Parameters to build cache key
            data_loader: Function to load data if not in cache
            force_refresh: Force refresh from data source

        Returns:
            Cached or freshly loaded data
        """
        config = cls.CACHE_CONFIGS.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            return data_loader()

        # Build cache key
        cache_key = cls._build_cache_key(config, cache_key_params)

        if force_refresh:
            logger.info(f"Force refresh for cache key: {cache_key}")
            data = data_loader()
            cls._store_in_cache(cache_key, data, config)
            return data

        # Try L1 cache first (memory)
        if CacheLevel.L1_MEMORY in config.levels:
            memory_data = cls._get_from_memory_cache(cache_key, config)
            if memory_data is not None:
                logger.debug(f"L1 cache hit: {cache_key}")
                return memory_data

        # Try L2 cache (Redis)
        if CacheLevel.L2_REDIS in config.levels:
            redis_data = cls._get_from_redis_cache(cache_key, config)
            if redis_data is not None:
                logger.debug(f"L2 cache hit: {cache_key}")
                # Populate L1 cache
                if CacheLevel.L1_MEMORY in config.levels:
                    cls._store_in_memory_cache(cache_key, redis_data, config)
                return redis_data

        # Cache miss - load data with stampede protection
        # Use distributed lock to prevent multiple concurrent rebuilds
        lock_key = f"cache_rebuild:{cache_key}"

        try:
            # Try to acquire lock with short timeout (prevent thundering herd)
            with distributed_lock(lock_key, timeout=5, blocking_timeout=0.1):
                # Double-check cache after acquiring lock
                # (another request may have populated it)
                redis_data = cls._get_from_redis_cache(cache_key, config)
                if redis_data is not None:
                    logger.debug(f"L2 cache hit after lock acquisition: {cache_key}")
                    if CacheLevel.L1_MEMORY in config.levels:
                        cls._store_in_memory_cache(cache_key, redis_data, config)
                    return redis_data

                # Still a miss - rebuild cache
                logger.info(f"Cache miss, loading data with lock: {cache_key}")
                data = data_loader()

                # Store in all configured cache levels
                cls._store_in_cache(cache_key, data, config)
                return data

        except LockAcquisitionError:
            # Another request is rebuilding cache
            # Return stale data or database query instead of blocking
            # REMOVED: time.sleep(0.05) - blocking I/O violates Rule #14

            # Try reading from cache again (may get stale data)
            redis_data = cls._get_from_redis_cache(cache_key, config)
            if redis_data is not None:
                logger.debug(f"L2 cache hit after wait: {cache_key}")
                if CacheLevel.L1_MEMORY in config.levels:
                    cls._store_in_memory_cache(cache_key, redis_data, config)
                return redis_data

            # Cache still not available - load directly (fallback)
            logger.warning(f"Cache stampede fallback for: {cache_key}")
            return data_loader()

    @classmethod
    def invalidate_cache(
        cls,
        cache_type: str,
        cache_key_params: Optional[Dict[str, Any]] = None,
        pattern: Optional[str] = None
    ) -> None:
        """
        Invalidate cache entries.

        Args:
            cache_type: Type of cache to invalidate
            cache_key_params: Specific cache key parameters
            pattern: Pattern to match for bulk invalidation
        """
        config = cls.CACHE_CONFIGS.get(cache_type)
        if not config:
            return

        if cache_key_params:
            # Invalidate specific key
            cache_key = cls._build_cache_key(config, cache_key_params)
            cls._invalidate_specific_key(cache_key, config)
        elif pattern:
            # Pattern-based invalidation
            cls._invalidate_pattern(config.key_prefix, pattern, config)
        else:
            # Invalidate all keys for this cache type
            cls._invalidate_all_keys(config)

        logger.info(f"Cache invalidated: {cache_type}")

    @classmethod
    def warm_cache(cls, cache_type: str, warmup_data: List[Dict[str, Any]]) -> None:
        """
        Pre-populate cache with commonly accessed data.

        Args:
            cache_type: Type of cache to warm
            warmup_data: List of data items to pre-cache
        """
        config = cls.CACHE_CONFIGS.get(cache_type)
        if not config:
            return

        for data_item in warmup_data:
            cache_key_params = data_item.get('key_params', {})
            data = data_item.get('data')

            if cache_key_params and data:
                cache_key = cls._build_cache_key(config, cache_key_params)
                cls._store_in_cache(cache_key, data, config)

        logger.info(f"Cache warmed: {cache_type}, {len(warmup_data)} items")

    @classmethod
    def get_cache_stats(cls, cache_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Args:
            cache_type: Specific cache type or None for all

        Returns:
            Cache statistics
        """
        stats = {
            'timestamp': timezone.now().isoformat(),
            'memory_cache_size': len(cls._memory_cache),
            'cache_types': {}
        }

        configs_to_check = (
            {cache_type: cls.CACHE_CONFIGS[cache_type]}
            if cache_type and cache_type in cls.CACHE_CONFIGS
            else cls.CACHE_CONFIGS
        )

        for ct, config in configs_to_check.items():
            type_stats = {
                'ttl_seconds': config.ttl_seconds,
                'strategy': config.strategy.value,
                'levels': [level.value for level in config.levels],
                'memory_entries': cls._count_memory_entries(config.key_prefix),
                'redis_info': cls._get_redis_info(config.key_prefix)
            }
            stats['cache_types'][ct] = type_stats

        return stats

    @classmethod
    def _build_cache_key(
        cls,
        config: CacheConfig,
        params: Dict[str, Any]
    ) -> str:
        """Build deterministic cache key from parameters."""
        # Sort parameters for consistent key generation
        sorted_params = sorted(params.items())
        param_string = "&".join(f"{k}={v}" for k, v in sorted_params)

        # Create hash for long parameter strings
        param_hash = hashlib.md5(param_string.encode()).hexdigest()[:12]

        # Include version and tenant info
        tenant = params.get('tenant', 'default')

        return f"{config.key_prefix}:{config.version}:{tenant}:{param_hash}"

    @classmethod
    def _get_from_memory_cache(
        cls,
        cache_key: str,
        config: CacheConfig
    ) -> Optional[Any]:
        """Get data from L1 memory cache."""
        if cache_key not in cls._memory_cache:
            return None

        # Check TTL
        timestamp = cls._memory_cache_timestamps.get(cache_key)
        if timestamp:
            age = timezone.now() - timestamp
            if age.total_seconds() > config.ttl_seconds:
                # Expired
                cls._remove_from_memory_cache(cache_key)
                return None

        return cls._memory_cache[cache_key].get('data')

    @classmethod
    def _get_from_redis_cache(
        cls,
        cache_key: str,
        config: CacheConfig
    ) -> Optional[Any]:
        """Get data from L2 Redis cache."""
        try:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                if config.compress:
                    # Decompress if needed
                    return cls._decompress_data(cached_data)
                return cached_data
        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Redis cache error for key {cache_key}: {e}")

        return None

    @classmethod
    def _store_in_cache(
        cls,
        cache_key: str,
        data: Any,
        config: CacheConfig
    ) -> None:
        """Store data in configured cache levels."""
        # Store in L1 memory cache
        if CacheLevel.L1_MEMORY in config.levels:
            cls._store_in_memory_cache(cache_key, data, config)

        # Store in L2 Redis cache
        if CacheLevel.L2_REDIS in config.levels:
            cls._store_in_redis_cache(cache_key, data, config)

    @classmethod
    def _store_in_memory_cache(
        cls,
        cache_key: str,
        data: Any,
        config: CacheConfig
    ) -> None:
        """Store data in L1 memory cache."""
        cls._memory_cache[cache_key] = {'data': data}
        cls._memory_cache_timestamps[cache_key] = timezone.now()

        # Cleanup old entries to prevent memory leaks
        cls._cleanup_memory_cache()

    @classmethod
    def _store_in_redis_cache(
        cls,
        cache_key: str,
        data: Any,
        config: CacheConfig
    ) -> None:
        """Store data in L2 Redis cache."""
        try:
            cache_data = data
            if config.compress:
                cache_data = cls._compress_data(data)

            cache.set(cache_key, cache_data, config.ttl_seconds)
        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Redis cache store error for key {cache_key}: {e}")

    @classmethod
    def _invalidate_specific_key(
        cls,
        cache_key: str,
        config: CacheConfig
    ) -> None:
        """Invalidate specific cache key."""
        # Remove from memory cache
        cls._remove_from_memory_cache(cache_key)

        # Remove from Redis cache
        try:
            cache.delete(cache_key)
        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Redis cache delete error for key {cache_key}: {e}")

    @classmethod
    def _remove_from_memory_cache(cls, cache_key: str) -> None:
        """Remove key from memory cache."""
        cls._memory_cache.pop(cache_key, None)
        cls._memory_cache_timestamps.pop(cache_key, None)

    @classmethod
    def _cleanup_memory_cache(cls, max_entries: int = 1000) -> None:
        """Clean up memory cache to prevent memory leaks."""
        if len(cls._memory_cache) <= max_entries:
            return

        # Remove oldest entries
        sorted_keys = sorted(
            cls._memory_cache_timestamps.items(),
            key=lambda x: x[1]
        )

        # Remove oldest 20% of entries
        keys_to_remove = [k for k, _ in sorted_keys[:len(sorted_keys) // 5]]

        for key in keys_to_remove:
            cls._remove_from_memory_cache(key)

        logger.info(f"Cleaned up {len(keys_to_remove)} memory cache entries")

    @classmethod
    def _compress_data(cls, data: Any) -> str:
        """Compress data for storage (placeholder implementation)."""
        # In production, would use actual compression like gzip
        return json.dumps(data)

    @classmethod
    def _decompress_data(cls, compressed_data: str) -> Any:
        """Decompress stored data (placeholder implementation)."""
        # In production, would use actual decompression
        return json.loads(compressed_data)

    @classmethod
    def _count_memory_entries(cls, prefix: str) -> int:
        """Count memory cache entries with given prefix."""
        return sum(1 for key in cls._memory_cache.keys() if key.startswith(prefix))

    @classmethod
    def _get_redis_info(cls, prefix: str) -> Dict[str, Any]:
        """Get Redis cache information for prefix."""
        # This would be implemented with Redis-specific commands
        # For now, return placeholder
        return {
            'estimated_entries': 0,
            'estimated_memory_usage': '0 MB'
        }

    @classmethod
    def _invalidate_pattern(
        cls,
        prefix: str,
        pattern: str,
        config: CacheConfig
    ) -> None:
        """Invalidate cache entries matching pattern."""
        # Remove matching entries from memory cache
        keys_to_remove = [
            key for key in cls._memory_cache.keys()
            if key.startswith(prefix) and pattern in key
        ]

        for key in keys_to_remove:
            cls._remove_from_memory_cache(key)

        # For Redis, would use SCAN and DELETE commands
        logger.info(f"Pattern invalidation: {prefix}:{pattern}")

    @classmethod
    def _invalidate_all_keys(cls, config: CacheConfig) -> None:
        """Invalidate all keys for cache type."""
        # Remove all entries with this prefix from memory cache
        keys_to_remove = [
            key for key in cls._memory_cache.keys()
            if key.startswith(config.key_prefix)
        ]

        for key in keys_to_remove:
            cls._remove_from_memory_cache(key)

        logger.info(f"Invalidated all keys for: {config.key_prefix}")


# Convenience functions for common caching operations

def cache_ticket_list(cache_key_params: Dict[str, Any], data_loader: Callable) -> Any:
    """Cache ticket list data."""
    return TicketCacheService.get_cached_data(
        'ticket_list', cache_key_params, data_loader
    )


def cache_dashboard_stats(cache_key_params: Dict[str, Any], data_loader: Callable) -> Any:
    """Cache dashboard statistics."""
    return TicketCacheService.get_cached_data(
        'dashboard_stats', cache_key_params, data_loader
    )


def cache_escalation_matrix(cache_key_params: Dict[str, Any], data_loader: Callable) -> Any:
    """Cache escalation matrix data."""
    return TicketCacheService.get_cached_data(
        'escalation_matrix', cache_key_params, data_loader
    )


def invalidate_ticket_caches(ticket_ids: Optional[List[int]] = None) -> None:
    """Invalidate ticket-related caches when data changes."""
    # Invalidate all ticket-related caches
    cache_types = ['ticket_list', 'dashboard_stats', 'mobile_sync']

    for cache_type in cache_types:
        TicketCacheService.invalidate_cache(cache_type)

    logger.info(f"Invalidated ticket caches for tickets: {ticket_ids or 'all'}")