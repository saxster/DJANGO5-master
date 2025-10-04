"""
Search Dashboard Exporter

Exports search metrics for Grafana/Prometheus dashboard consumption.

Features:
- Aggregated metrics per tenant
- Time-series data export
- Top queries analytics
- Performance trend analysis

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Class < 150 lines
- Rule #11: Specific exception handling
- Rule #12: Database query optimization
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from django.core.cache import cache
from django.db import DatabaseError, connection
from django.db.models import Count, Avg, Q
from django.utils import timezone

from apps.search.models import SearchAnalytics
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_MINUTE

logger = logging.getLogger(__name__)


class SearchDashboardExporter:
    """
    Exports search analytics for dashboard visualization.

    Provides aggregated metrics and time-series data for monitoring.
    """

    CACHE_TTL = 5 * SECONDS_IN_MINUTE  # 5 minutes cache for dashboard data

    def __init__(self, tenant_id: Optional[int] = None):
        """
        Initialize dashboard exporter.

        Args:
            tenant_id: Optional tenant ID for scoped exports
        """
        self.tenant_id = tenant_id

    def get_tenant_metrics(
        self,
        tenant_id: int,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics for a specific tenant.

        Args:
            tenant_id: Tenant ID
            hours: Number of hours to look back

        Returns:
            Dict with aggregated metrics
        """
        cache_key = f"search_dashboard:tenant:{tenant_id}:hours:{hours}"

        # Try cache first
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            since = timezone.now() - timedelta(hours=hours)

            analytics = SearchAnalytics.objects.filter(
                tenant_id=tenant_id,
                timestamp__gte=since
            ).select_related('tenant', 'user')

            metrics = {
                'tenant_id': tenant_id,
                'period_hours': hours,
                'total_queries': analytics.count(),
                'unique_users': analytics.values('user').distinct().count(),
                'avg_response_time_ms': analytics.aggregate(
                    Avg('response_time_ms')
                )['response_time_ms__avg'] or 0,
                'zero_result_queries': analytics.filter(result_count=0).count(),
                'top_queries': self._get_top_queries(analytics, limit=10),
                'queries_by_hour': self._get_queries_by_hour(analytics, hours),
                'queries_by_entity': self._get_queries_by_entity(analytics),
                'timestamp': timezone.now().isoformat(),
            }

            # Cache for 5 minutes
            cache.set(cache_key, metrics, timeout=self.CACHE_TTL)

            return metrics

        except (DatabaseError, AttributeError) as e:
            logger.error(
                f"Failed to get tenant metrics for tenant {tenant_id}: {e}",
                exc_info=True
            )
            return self._empty_metrics(tenant_id, hours)

    def get_all_tenants_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary metrics for all active tenants.

        Returns:
            List of tenant summaries
        """
        cache_key = "search_dashboard:all_tenants_summary"

        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            since = timezone.now() - timedelta(hours=1)

            # Get active tenants from last hour
            active_tenants = SearchAnalytics.objects.filter(
                timestamp__gte=since
            ).values('tenant_id').annotate(
                query_count=Count('id')
            ).order_by('-query_count')

            summaries = []
            for tenant_data in active_tenants[:50]:  # Top 50 active tenants
                tenant_id = tenant_data['tenant_id']
                summaries.append({
                    'tenant_id': tenant_id,
                    'queries_last_hour': tenant_data['query_count'],
                })

            cache.set(cache_key, summaries, timeout=self.CACHE_TTL)

            return summaries

        except DatabaseError as e:
            logger.error(f"Failed to get all tenants summary: {e}", exc_info=True)
            return []

    def get_performance_trends(
        self,
        tenant_id: int,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get performance trend data for visualization.

        Args:
            tenant_id: Tenant ID
            hours: Number of hours to analyze

        Returns:
            Dict with time-series performance data
        """
        try:
            since = timezone.now() - timedelta(hours=hours)

            analytics = SearchAnalytics.objects.filter(
                tenant_id=tenant_id,
                timestamp__gte=since
            ).order_by('timestamp')

            # Group by hour for trend analysis
            trends = defaultdict(lambda: {'count': 0, 'total_time': 0})

            for record in analytics:
                hour_key = record.timestamp.strftime('%Y-%m-%d %H:00')
                trends[hour_key]['count'] += 1
                trends[hour_key]['total_time'] += record.response_time_ms

            # Calculate averages
            trend_data = []
            for hour, data in sorted(trends.items()):
                avg_time = data['total_time'] / data['count'] if data['count'] > 0 else 0
                trend_data.append({
                    'timestamp': hour,
                    'query_count': data['count'],
                    'avg_response_time_ms': round(avg_time, 2),
                })

            return {
                'tenant_id': tenant_id,
                'period_hours': hours,
                'data_points': len(trend_data),
                'trends': trend_data,
            }

        except DatabaseError as e:
            logger.error(f"Failed to get performance trends: {e}", exc_info=True)
            return {'tenant_id': tenant_id, 'trends': []}

    def _get_top_queries(
        self,
        queryset,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get most frequent queries"""
        try:
            top = queryset.values('query').annotate(
                count=Count('id')
            ).order_by('-count')[:limit]

            return [
                {
                    'query': item['query'][:100],  # Truncate long queries
                    'count': item['count']
                }
                for item in top
            ]
        except (DatabaseError, AttributeError):
            return []

    def _get_queries_by_hour(
        self,
        queryset,
        hours: int
    ) -> List[int]:
        """Get query count per hour"""
        try:
            # Simple hourly grouping
            hourly_counts = []
            now = timezone.now()

            for h in range(hours):
                hour_start = now - timedelta(hours=h+1)
                hour_end = now - timedelta(hours=h)
                count = queryset.filter(
                    timestamp__gte=hour_start,
                    timestamp__lt=hour_end
                ).count()
                hourly_counts.insert(0, count)

            return hourly_counts
        except (DatabaseError, AttributeError):
            return [0] * hours

    def _get_queries_by_entity(self, queryset) -> Dict[str, int]:
        """Get query count by entity type"""
        try:
            # Entities are stored as JSON array in analytics
            entity_counts = defaultdict(int)

            for record in queryset:
                if record.entities:
                    for entity in record.entities:
                        entity_counts[entity] += 1

            return dict(entity_counts)
        except (DatabaseError, AttributeError, TypeError):
            return {}

    def _empty_metrics(self, tenant_id: int, hours: int) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            'tenant_id': tenant_id,
            'period_hours': hours,
            'total_queries': 0,
            'unique_users': 0,
            'avg_response_time_ms': 0,
            'zero_result_queries': 0,
            'top_queries': [],
            'queries_by_hour': [0] * hours,
            'queries_by_entity': {},
            'timestamp': timezone.now().isoformat(),
        }
