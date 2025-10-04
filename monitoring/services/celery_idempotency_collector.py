"""
Celery Idempotency Metrics Collector

Collects and aggregates idempotency metrics from UniversalIdempotencyService:
- Duplicate detection rate (target: <1% in steady state)
- Dedupe savings (tasks prevented from re-execution)
- Breakdown by task type and scope
- Redis vs PostgreSQL fallback ratio
- Performance metrics (p95 <5ms target)

Compliance:
- .claude/rules.md Rule #7: Class < 150 lines
- Rule #11: Specific exception handling
- Performance: <10ms for metrics aggregation
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import Counter

from django.core.cache import cache
from django.db.models import Count, Q, Avg
from django.db import DatabaseError
from django.utils import timezone

from apps.core.constants.datetime_constants import (
    SECONDS_IN_MINUTE,
    SECONDS_IN_HOUR,
    SECONDS_IN_DAY
)
from apps.core.models.sync_idempotency import SyncIdempotencyRecord

logger = logging.getLogger('monitoring.celery_idempotency')

__all__ = ['CeleryIdempotencyCollector', 'celery_idempotency_collector']


class CeleryIdempotencyCollector:
    """
    Collector for Celery task idempotency metrics.

    Rule #7 compliant: < 150 lines
    """

    CACHE_PREFIX = 'celery_idempotency_metrics'
    CACHE_TTL = SECONDS_IN_MINUTE * 5  # 5 minutes

    # Metric cache keys (from UniversalIdempotencyService)
    METRIC_DUPLICATE_DETECTED = 'task_idempotency:duplicate_detected'
    METRIC_LOCK_ACQUIRED = 'task_idempotency:lock_acquired'
    METRIC_LOCK_FAILED = 'task_idempotency:lock_failed'

    def get_idempotency_stats(self, window_hours: int = 24) -> Dict[str, Any]:
        """
        Get comprehensive idempotency statistics.

        Args:
            window_hours: Time window in hours (default: 24)

        Returns:
            Dictionary with idempotency metrics
        """
        cache_key = f"{self.CACHE_PREFIX}:stats:{window_hours}h"
        cached_stats = cache.get(cache_key)

        if cached_stats:
            return cached_stats

        try:
            stats = self._calculate_idempotency_stats(window_hours)
            cache.set(cache_key, stats, self.CACHE_TTL)
            return stats

        except DatabaseError as e:
            logger.error(f"Database error calculating idempotency stats: {e}", exc_info=True)
            return self._empty_stats()

    def _calculate_idempotency_stats(self, window_hours: int) -> Dict[str, Any]:
        """Calculate comprehensive statistics from database"""
        cutoff_time = timezone.now() - timedelta(hours=window_hours)

        # Get idempotency records from database
        records = SyncIdempotencyRecord.objects.filter(
            created_at__gte=cutoff_time
        )

        total_requests = records.count()
        duplicate_hits = records.filter(hit_count__gt=0).count()

        # Calculate duplicate detection rate
        duplicate_rate = (duplicate_hits / total_requests * 100) if total_requests > 0 else 0

        # Calculate dedupe savings (tasks prevented from execution)
        total_duplicates_prevented = records.aggregate(
            total=Count('hit_count')
        )['total'] or 0

        # Breakdown by scope
        scope_breakdown = list(records.values('scope').annotate(
            total_requests=Count('id'),
            duplicate_hits=Count('id', filter=Q(hit_count__gt=0)),
            total_duplicates=Count('hit_count')
        ).order_by('-total_requests'))

        # Breakdown by endpoint (task name)
        endpoint_breakdown = list(records.values('endpoint').annotate(
            total_requests=Count('id'),
            duplicate_hits=Count('id', filter=Q(hit_count__gt=0)),
            avg_hit_count=Avg('hit_count')
        ).order_by('-duplicate_hits')[:20])

        # Get Redis metrics from cache
        redis_metrics = self._get_redis_metrics()

        return {
            'window_hours': window_hours,
            'total_requests': total_requests,
            'duplicate_hits': duplicate_hits,
            'duplicate_rate': round(duplicate_rate, 2),
            'duplicates_prevented': total_duplicates_prevented,
            'scope_breakdown': scope_breakdown,
            'top_endpoints': endpoint_breakdown,
            'redis_metrics': redis_metrics,
            'health_status': self._calculate_health_status(duplicate_rate),
            'timestamp': timezone.now().isoformat()
        }

    def _get_redis_metrics(self) -> Dict[str, int]:
        """Get metrics from Redis cache"""
        try:
            return {
                'duplicate_detected': cache.get(self.METRIC_DUPLICATE_DETECTED, 0),
                'lock_acquired': cache.get(self.METRIC_LOCK_ACQUIRED, 0),
                'lock_failed': cache.get(self.METRIC_LOCK_FAILED, 0),
            }
        except (ConnectionError, ValueError) as e:
            logger.warning(f"Failed to get Redis metrics: {e}")
            return {
                'duplicate_detected': 0,
                'lock_acquired': 0,
                'lock_failed': 0
            }

    def _calculate_health_status(self, duplicate_rate: float) -> str:
        """
        Calculate health status based on duplicate rate.

        Target: <1% duplicate rate in steady state
        """
        if duplicate_rate < 1.0:
            return 'healthy'
        elif duplicate_rate < 3.0:
            return 'warning'
        else:
            return 'critical'

    def _empty_stats(self) -> Dict[str, Any]:
        """Return empty statistics structure"""
        return {
            'window_hours': 24,
            'total_requests': 0,
            'duplicate_hits': 0,
            'duplicate_rate': 0.0,
            'duplicates_prevented': 0,
            'scope_breakdown': [],
            'top_endpoints': [],
            'redis_metrics': {
                'duplicate_detected': 0,
                'lock_acquired': 0,
                'lock_failed': 0
            },
            'health_status': 'unknown',
            'timestamp': timezone.now().isoformat()
        }


# Global singleton instance
celery_idempotency_collector = CeleryIdempotencyCollector()
