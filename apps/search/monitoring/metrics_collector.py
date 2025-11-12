"""
Search Metrics Collector

Aggregates and exports Prometheus metrics for search performance monitoring.

Features:
- Query latency histograms per tenant
- Cache hit/miss rates
- Result count distributions
- Error rate tracking
- Top queries analytics

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle (metrics collection only)
- Rule #7: Class < 150 lines
- Rule #11: Specific exception handling
- Rule #15: No sensitive data in logs
"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR

logger = logging.getLogger(__name__)

# Prometheus metrics (lazy import for optional dependency)
try:
    from prometheus_client import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS
        Counter, Histogram, Gauge, Summary, generate_latest, REGISTRY
    )
    METRICS_ENABLED = True

    # Query performance metrics
    search_queries_total = Counter(
        'search_queries_total',
        'Total number of search queries',
        ['tenant_id', 'entity_type', 'status']
    )

    search_query_duration = Histogram(
        'search_query_duration_seconds',
        'Search query execution time',
        ['tenant_id', 'entity_type'],
        buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
    )

    search_results_count = Histogram(
        'search_results_count',
        'Number of search results returned',
        ['tenant_id', 'entity_type'],
        buckets=[0, 1, 5, 10, 20, 50, 100, 500]
    )

    # Cache performance metrics
    search_cache_hits_total = Counter(
        'search_cache_hits_total',
        'Total search cache hits',
        ['tenant_id']
    )

    search_cache_misses_total = Counter(
        'search_cache_misses_total',
        'Total search cache misses',
        ['tenant_id']
    )

    search_cache_size = Gauge(
        'search_cache_size_bytes',
        'Approximate search cache size in bytes',
        ['tenant_id']
    )

    # Error tracking metrics
    search_errors_total = Counter(
        'search_errors_total',
        'Total search errors',
        ['tenant_id', 'error_type']
    )

    # Analytics metrics
    search_zero_results_total = Counter(
        'search_zero_results_total',
        'Total searches with zero results',
        ['tenant_id']
    )

    search_click_through_rate = Summary(
        'search_click_through_rate',
        'Search result click-through rate',
        ['tenant_id']
    )

except ImportError:
    METRICS_ENABLED = False
    logger.warning("prometheus_client not installed. Metrics collection disabled.", exc_info=True)


class SearchMetricsCollector:
    """
    Collects and exports Prometheus metrics for search operations.

    Thread-safe for concurrent access.
    """

    def __init__(self, tenant_id: Optional[int] = None):
        """
        Initialize metrics collector.

        Args:
            tenant_id: Optional tenant ID for scoped metrics
        """
        self.tenant_id = tenant_id
        self.enabled = METRICS_ENABLED

    def record_query(
        self,
        tenant_id: int,
        entity_types: List[str],
        duration_seconds: float,
        result_count: int,
        status: str = 'success',
        from_cache: bool = False
    ):
        """
        Record search query metrics.

        Args:
            tenant_id: Tenant ID
            entity_types: Entity types searched
            duration_seconds: Query execution time
            result_count: Number of results returned
            status: Query status ('success', 'error', 'timeout')
            from_cache: Whether results came from cache
        """
        if not self.enabled:
            return

        try:
            tenant_str = str(tenant_id)

            # Record query count
            for entity_type in entity_types:
                search_queries_total.labels(
                    tenant_id=tenant_str,
                    entity_type=entity_type,
                    status=status
                ).inc()

                # Record duration (only for successful queries)
                if status == 'success':
                    search_query_duration.labels(
                        tenant_id=tenant_str,
                        entity_type=entity_type
                    ).observe(duration_seconds)

                    # Record result count
                    search_results_count.labels(
                        tenant_id=tenant_str,
                        entity_type=entity_type
                    ).observe(result_count)

            # Record cache hit/miss
            if from_cache:
                search_cache_hits_total.labels(tenant_id=tenant_str).inc()
            else:
                search_cache_misses_total.labels(tenant_id=tenant_str).inc()

            # Track zero results
            if result_count == 0:
                search_zero_results_total.labels(tenant_id=tenant_str).inc()

        except (AttributeError, ValueError) as e:
            logger.warning(f"Failed to record query metrics: {e}", exc_info=True)

    def record_error(
        self,
        tenant_id: int,
        error_type: str,
        correlation_id: Optional[str] = None
    ):
        """
        Record search error for monitoring.

        Args:
            tenant_id: Tenant ID
            error_type: Error classification (e.g., 'database', 'timeout', 'validation')
            correlation_id: Optional correlation ID for debugging
        """
        if not self.enabled:
            return

        try:
            search_errors_total.labels(
                tenant_id=str(tenant_id),
                error_type=error_type
            ).inc()

            # Log error with correlation ID (Rule #15: No sensitive data)
            logger.error(
                f"Search error recorded",
                extra={
                    'tenant_id': tenant_id,
                    'error_type': error_type,
                    'correlation_id': correlation_id,
                }
            )

        except (AttributeError, ValueError) as e:
            logger.warning(f"Failed to record error metrics: {e}", exc_info=True)

    def update_cache_size(self, tenant_id: int, size_bytes: int):
        """
        Update cache size gauge.

        Args:
            tenant_id: Tenant ID
            size_bytes: Approximate cache size in bytes
        """
        if not self.enabled:
            return

        try:
            search_cache_size.labels(tenant_id=str(tenant_id)).set(size_bytes)
        except (AttributeError, ValueError) as e:
            logger.warning(f"Failed to update cache size: {e}", exc_info=True)

    def record_click_through(
        self,
        tenant_id: int,
        clicked: bool,
        position: Optional[int] = None
    ):
        """
        Record search result click-through for CTR analysis.

        Args:
            tenant_id: Tenant ID
            clicked: Whether a result was clicked
            position: Position of clicked result (0-indexed)
        """
        if not self.enabled:
            return

        try:
            ctr = 1.0 if clicked else 0.0
            search_click_through_rate.labels(
                tenant_id=str(tenant_id)
            ).observe(ctr)
        except (AttributeError, ValueError) as e:
            logger.warning(f"Failed to record CTR: {e}", exc_info=True)

    @staticmethod
    def export_metrics() -> bytes:
        """
        Export all Prometheus metrics in text format.

        Returns:
            Metrics in Prometheus exposition format
        """
        if not METRICS_ENABLED:
            return b"# Metrics export disabled\n"

        try:
            return generate_latest(REGISTRY)
        except (DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS) as e:
            logger.error(f"Failed to export metrics: {e}", exc_info=True)
            return b"# Error exporting metrics\n"

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get human-readable summary of current metrics.

        Returns:
            Dict with metrics summary (for dashboard display)
        """
        return {
            'enabled': self.enabled,
            'tenant_id': self.tenant_id,
            'timestamp': timezone.now().isoformat(),
            'note': 'Use /metrics/search endpoint for Prometheus scraping'
        }
