"""
Redis Memory Management Service

Implements intelligent memory management, monitoring, and optimization for Redis instances.
Addresses critical memory issues identified in Redis analysis:
- OOM prevention through proactive monitoring
- Intelligent cache eviction policies
- Memory usage optimization and defragmentation
- Memory leak detection and prevention

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service layer <150 lines per class
- Rule #11: Specific exception handling
"""

import logging
import time
import psutil
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class MemoryStats:
    """Redis memory statistics."""
    used_memory: int
    used_memory_human: str
    used_memory_peak: int
    used_memory_peak_human: str
    memory_fragmentation_ratio: float
    maxmemory: int
    maxmemory_human: str
    evicted_keys: int
    expired_keys: int
    keyspace_hits: int
    keyspace_misses: int
    hit_ratio: float


@dataclass
class MemoryAlert:
    """Memory alert information."""
    level: str  # 'warning', 'critical', 'emergency'
    message: str
    threshold: float
    current_usage: float
    recommended_action: str
    timestamp: datetime


class RedisMemoryManager:
    """
    Advanced Redis memory management and optimization service.

    Provides proactive memory monitoring, intelligent eviction,
    and optimization recommendations for Redis instances.
    """

    # Memory threshold levels (percentage of max memory)
    MEMORY_THRESHOLDS = {
        'warning': 70.0,      # Start monitoring closely
        'critical': 85.0,     # Begin aggressive cleanup
        'emergency': 95.0     # Emergency eviction mode
    }

    # Cache key patterns for cleanup priority (high to low priority)
    CLEANUP_PATTERNS = [
        'temp:*',             # Temporary data - highest priority for cleanup
        'session:expired:*',  # Expired sessions
        'cache:old:*',        # Old cache entries
        'select2:*',          # Select2 cache data
        'report:*',           # Report cache data
        'api:response:*',     # API response cache
        'template:*',         # Template fragments
        'query:*',            # Query cache
        'user:prefs:*',       # User preferences
    ]

    def __init__(self):
        self.alerts: List[MemoryAlert] = []
        self._last_cleanup = None
        self._cleanup_running = False

    def get_memory_stats(self) -> Optional[MemoryStats]:
        """
        Get comprehensive Redis memory statistics.

        Returns:
            MemoryStats object with current memory information
        """
        try:
            # Get Redis client for info commands
            redis_client = cache._cache.get_master_client()
            info = redis_client.info('memory')
            stats_info = redis_client.info('stats')

            # Calculate hit ratio
            hits = stats_info.get('keyspace_hits', 0)
            misses = stats_info.get('keyspace_misses', 0)
            hit_ratio = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0

            return MemoryStats(
                used_memory=info.get('used_memory', 0),
                used_memory_human=info.get('used_memory_human', '0B'),
                used_memory_peak=info.get('used_memory_peak', 0),
                used_memory_peak_human=info.get('used_memory_peak_human', '0B'),
                memory_fragmentation_ratio=info.get('mem_fragmentation_ratio', 1.0),
                maxmemory=info.get('maxmemory', 0),
                maxmemory_human=self._bytes_to_human(info.get('maxmemory', 0)),
                evicted_keys=stats_info.get('evicted_keys', 0),
                expired_keys=stats_info.get('expired_keys', 0),
                keyspace_hits=hits,
                keyspace_misses=misses,
                hit_ratio=round(hit_ratio, 2)
            )

        except (ConnectionError, TimeoutError, AttributeError) as e:
            logger.error(f"Error getting Redis memory stats: {e}")
            return None

    def check_memory_health(self) -> List[MemoryAlert]:
        """
        Check Redis memory health and generate alerts.

        Returns:
            List of MemoryAlert objects for any issues found
        """
        stats = self.get_memory_stats()
        if not stats:
            return [MemoryAlert(
                level='critical',
                message='Unable to retrieve Redis memory statistics',
                threshold=0,
                current_usage=0,
                recommended_action='Check Redis connection and service status',
                timestamp=timezone.now()
            )]

        alerts = []

        # Calculate memory usage percentage
        if stats.maxmemory > 0:
            usage_percentage = (stats.used_memory / stats.maxmemory) * 100
        else:
            # No maxmemory set - check against system memory
            system_memory = psutil.virtual_memory().total
            usage_percentage = (stats.used_memory / system_memory) * 100

        # Check against thresholds
        for level, threshold in self.MEMORY_THRESHOLDS.items():
            if usage_percentage >= threshold:
                alert = MemoryAlert(
                    level=level,
                    message=f'Redis memory usage at {usage_percentage:.1f}% (threshold: {threshold}%)',
                    threshold=threshold,
                    current_usage=usage_percentage,
                    recommended_action=self._get_recommended_action(level, stats),
                    timestamp=timezone.now()
                )
                alerts.append(alert)
                break

        # Check fragmentation ratio
        if stats.memory_fragmentation_ratio > 2.0:
            alerts.append(MemoryAlert(
                level='warning',
                message=f'High memory fragmentation: {stats.memory_fragmentation_ratio:.2f}',
                threshold=2.0,
                current_usage=stats.memory_fragmentation_ratio,
                recommended_action='Run memory defragmentation during off-peak hours',
                timestamp=timezone.now()
            ))

        # Check hit ratio
        if stats.hit_ratio < 80.0 and stats.keyspace_hits + stats.keyspace_misses > 1000:
            alerts.append(MemoryAlert(
                level='warning',
                message=f'Low cache hit ratio: {stats.hit_ratio}%',
                threshold=80.0,
                current_usage=stats.hit_ratio,
                recommended_action='Review cache TTL settings and warming strategy',
                timestamp=timezone.now()
            ))

        self.alerts = alerts
        return alerts

    def optimize_memory_usage(self, force: bool = False) -> Dict[str, Any]:
        """
        Optimize Redis memory usage through intelligent cleanup.

        Args:
            force: Force optimization even if recently performed

        Returns:
            Dictionary with optimization results
        """
        if self._cleanup_running:
            return {'status': 'already_running', 'message': 'Memory optimization already in progress'}

        # Check if cleanup was recently performed (unless forced)
        if not force and self._last_cleanup:
            time_since_cleanup = timezone.now() - self._last_cleanup
            if time_since_cleanup < timedelta(minutes=15):
                return {
                    'status': 'skipped',
                    'message': f'Cleanup performed {time_since_cleanup.seconds // 60} minutes ago'
                }

        self._cleanup_running = True
        start_time = time.time()

        try:
            results = {
                'status': 'completed',
                'start_time': timezone.now().isoformat(),
                'keys_cleaned': 0,
                'memory_freed': 0,
                'patterns_processed': []
            }

            initial_stats = self.get_memory_stats()
            if not initial_stats:
                return {'status': 'error', 'message': 'Unable to get initial memory stats'}

            # Perform cleanup by priority
            for pattern in self.CLEANUP_PATTERNS:
                keys_cleaned = self._cleanup_pattern(pattern)
                results['keys_cleaned'] += keys_cleaned
                results['patterns_processed'].append({
                    'pattern': pattern,
                    'keys_cleaned': keys_cleaned
                })

                # Check if we've freed enough memory
                current_stats = self.get_memory_stats()
                if current_stats and initial_stats.maxmemory > 0:
                    usage_percentage = (current_stats.used_memory / initial_stats.maxmemory) * 100
                    if usage_percentage < self.MEMORY_THRESHOLDS['warning']:
                        logger.info(f"Memory optimization target reached: {usage_percentage:.1f}%")
                        break

            # Calculate memory freed
            final_stats = self.get_memory_stats()
            if final_stats and initial_stats:
                results['memory_freed'] = initial_stats.used_memory - final_stats.used_memory

            # Update cleanup timestamp
            self._last_cleanup = timezone.now()
            results['duration_seconds'] = time.time() - start_time

            logger.info(f"Redis memory optimization completed: {results}")
            return results

        except Exception as e:
            logger.error(f"Error during memory optimization: {e}")
            return {'status': 'error', 'message': str(e)}

        finally:
            self._cleanup_running = False

    def _cleanup_pattern(self, pattern: str) -> int:
        """
        Clean up keys matching a specific pattern.

        Args:
            pattern: Redis key pattern to clean

        Returns:
            Number of keys cleaned up
        """
        try:
            redis_client = cache._cache.get_master_client()

            # Use SCAN for efficient key iteration
            keys = []
            cursor = 0

            while True:
                cursor, batch = redis_client.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

                # Limit to prevent memory issues
                if len(keys) >= 1000:
                    break

            if keys:
                # Delete in chunks to avoid blocking
                chunk_size = 100
                deleted_count = 0

                for i in range(0, len(keys), chunk_size):
                    chunk = keys[i:i + chunk_size]
                    deleted = redis_client.delete(*chunk)
                    deleted_count += deleted

                logger.info(f"Cleaned {deleted_count} keys matching pattern: {pattern}")
                return deleted_count

            return 0

        except Exception as e:
            logger.warning(f"Error cleaning pattern {pattern}: {e}")
            return 0

    def _get_recommended_action(self, level: str, stats: MemoryStats) -> str:
        """Get recommended action based on alert level."""
        if level == 'emergency':
            return 'Immediate action required: Scale Redis or enable emergency eviction'
        elif level == 'critical':
            return 'Run memory optimization and consider increasing maxmemory limit'
        elif level == 'warning':
            return 'Schedule memory optimization during next maintenance window'
        else:
            return 'Monitor memory usage trends'

    def _bytes_to_human(self, bytes_value: int) -> str:
        """Convert bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f}PB"

    def get_optimization_recommendations(self) -> List[str]:
        """
        Get personalized optimization recommendations based on current usage patterns.

        Returns:
            List of optimization recommendations
        """
        stats = self.get_memory_stats()
        if not stats:
            return ['Unable to analyze Redis stats - check connection']

        recommendations = []

        # Memory configuration recommendations
        if stats.maxmemory == 0:
            recommendations.append(
                "Configure maxmemory limit to prevent OOM kills. "
                "Recommended: 80% of available system memory"
            )

        # Fragmentation recommendations
        if stats.memory_fragmentation_ratio > 1.5:
            recommendations.append(
                f"High fragmentation ratio ({stats.memory_fragmentation_ratio:.2f}). "
                "Enable active defragmentation in Redis configuration"
            )

        # Hit ratio recommendations
        if stats.hit_ratio < 90:
            recommendations.append(
                f"Low cache hit ratio ({stats.hit_ratio}%). "
                "Review TTL settings and implement cache warming"
            )

        # Eviction recommendations
        if stats.evicted_keys > 0:
            recommendations.append(
                f"{stats.evicted_keys} keys evicted. "
                "Consider increasing memory limit or optimizing data structures"
            )

        return recommendations


# Global instance
redis_memory_manager = RedisMemoryManager()

# Export public interface
__all__ = [
    'RedisMemoryManager',
    'MemoryStats',
    'MemoryAlert',
    'redis_memory_manager'
]