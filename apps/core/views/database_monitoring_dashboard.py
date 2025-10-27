"""
Database Performance Monitoring Dashboard

Provides visibility into:
- Connection pool statistics
- Query performance metrics
- Slow query analysis
- Index usage statistics
- Database health checks

Author: Claude Code
Date: 2025-10-27
"""

import logging
from datetime import timedelta
from typing import Dict, Any, List

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.http import JsonResponse
from django.db import connection, DatabaseError
from django.conf import settings

logger = logging.getLogger(__name__)


class DatabasePerformanceDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Database performance monitoring dashboard.

    Accessible at: /admin/monitoring/database/

    Permissions: Staff users only
    """

    template_name = 'core/monitoring/database_performance.html'

    def test_func(self):
        """Only staff users can access monitoring dashboards"""
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        """Build dashboard context with database metrics"""
        context = super().get_context_data(**kwargs)

        context.update({
            'page_title': 'Database Performance Monitoring',
            'last_updated': timezone.now(),
            'connection_stats': self._get_connection_stats(),
            'query_performance': self._get_query_performance(),
            'slow_queries': self._get_slow_queries(limit=20),
            'index_usage': self._get_index_usage(),
            'database_size': self._get_database_size(),
        })

        return context

    def _get_connection_stats(self) -> Dict[str, Any]:
        """
        Get PostgreSQL connection pool statistics.

        Returns:
            dict: Connection pool metrics
        """
        stats = {
            'pool_configured': False,
            'min_size': 0,
            'max_size': 0,
            'current_connections': 0,
            'idle_connections': 0,
            'active_connections': 0,
        }

        try:
            # Get pool configuration from settings
            db_config = settings.DATABASES.get('default', {})
            pool_config = db_config.get('OPTIONS', {}).get('pool', {})

            if pool_config:
                stats['pool_configured'] = True
                stats['min_size'] = pool_config.get('min_size', 0)
                stats['max_size'] = pool_config.get('max_size', 0)

            # Query PostgreSQL for connection statistics
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE state = 'idle') as idle,
                        COUNT(*) FILTER (WHERE state = 'active') as active
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
                row = cursor.fetchone()
                if row:
                    stats['current_connections'] = row[0]
                    stats['idle_connections'] = row[1]
                    stats['active_connections'] = row[2]

        except (DatabaseError, OSError, AttributeError, KeyError, TypeError) as e:
            logger.error(f"Error fetching connection stats: {e}")

        return stats

    def _get_query_performance(self) -> Dict[str, Any]:
        """
        Get query performance statistics.

        Returns:
            dict: Query performance metrics
        """
        performance = {
            'total_queries': 0,
            'avg_execution_time_ms': 0.0,
            'slowest_query_ms': 0.0,
        }

        try:
            # Try to get from QueryPerformance model if available
            try:
                from apps.core.models.query_performance import QueryPerformance

                # Get statistics from last 24 hours
                time_threshold = timezone.now() - timedelta(hours=24)

                queries = QueryPerformance.objects.filter(
                    executed_at__gte=time_threshold
                )

                if queries.exists():
                    from django.db.models import Avg, Max, Count

                    stats = queries.aggregate(
                        total=Count('id'),
                        avg_time=Avg('execution_time'),
                        max_time=Max('execution_time')
                    )

                    performance['total_queries'] = stats['total'] or 0
                    performance['avg_execution_time_ms'] = (stats['avg_time'] or 0) * 1000
                    performance['slowest_query_ms'] = (stats['max_time'] or 0) * 1000

            except ImportError:
                logger.warning("QueryPerformance model not available")

        except (DatabaseError, ImportError, AttributeError, KeyError, TypeError) as e:
            logger.error(f"Error fetching query performance: {e}")

        return performance

    def _get_slow_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get slow query log.

        Args:
            limit: Maximum number of queries to return

        Returns:
            list: Slow queries with execution times
        """
        slow_queries = []

        try:
            try:
                from apps.core.models.query_performance import QueryPerformance

                # Get slowest queries from last 24 hours
                time_threshold = timezone.now() - timedelta(hours=24)

                queries = QueryPerformance.objects.filter(
                    executed_at__gte=time_threshold,
                    execution_time__gte=1.0  # Queries taking 1+ seconds
                ).order_by('-execution_time').values(
                    'query_type',
                    'execution_time',
                    'executed_at',
                    'rows_affected'
                )[:limit]

                slow_queries = list(queries)

            except ImportError:
                logger.warning("QueryPerformance model not available")

        except (DatabaseError, ImportError, AttributeError, KeyError, TypeError) as e:
            logger.error(f"Error fetching slow queries: {e}")

        return slow_queries

    def _get_index_usage(self) -> List[Dict[str, Any]]:
        """
        Get index usage statistics from PostgreSQL.

        Returns:
            list: Index usage statistics
        """
        index_stats = []

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        idx_scan as scans,
                        idx_tup_read as tuples_read,
                        idx_tup_fetch as tuples_fetched
                    FROM pg_stat_user_indexes
                    WHERE schemaname = 'public'
                    ORDER BY idx_scan DESC
                    LIMIT 20
                """)

                columns = [col[0] for col in cursor.description]
                for row in cursor.fetchall():
                    index_stats.append(dict(zip(columns, row)))

        except (DatabaseError, OSError, AttributeError, KeyError) as e:
            logger.error(f"Error fetching index usage: {e}")

        return index_stats

    def _get_database_size(self) -> Dict[str, Any]:
        """
        Get database size statistics.

        Returns:
            dict: Database size metrics
        """
        size_stats = {
            'total_size_mb': 0.0,
            'table_sizes': [],
        }

        try:
            with connection.cursor() as cursor:
                # Get total database size
                cursor.execute("""
                    SELECT pg_database_size(current_database()) / (1024.0 * 1024.0) as size_mb
                """)
                row = cursor.fetchone()
                if row:
                    size_stats['total_size_mb'] = round(row[0], 2)

                # Get largest tables
                cursor.execute("""
                    SELECT
                        schemaname,
                        tablename,
                        pg_total_relation_size(schemaname||'.'||tablename) / (1024.0 * 1024.0) as size_mb
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10
                """)

                columns = [col[0] for col in cursor.description]
                for row in cursor.fetchall():
                    table_stat = dict(zip(columns, row))
                    table_stat['size_mb'] = round(table_stat['size_mb'], 2)
                    size_stats['table_sizes'].append(table_stat)

        except (DatabaseError, OSError, AttributeError, KeyError) as e:
            logger.error(f"Error fetching database size: {e}")

        return size_stats


class DatabaseMetricsAPIView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    API endpoint for real-time database metrics (JSON).

    Accessible at: /admin/monitoring/database/api/metrics/

    Used by dashboard JavaScript for live updates.
    """

    def test_func(self):
        """Only staff users can access monitoring APIs"""
        return self.request.user.is_staff

    def get(self, request, *args, **kwargs):
        """Return JSON metrics for AJAX updates"""

        dashboard = DatabasePerformanceDashboardView()
        dashboard.request = request

        metrics = {
            'timestamp': timezone.now().isoformat(),
            'connection_stats': dashboard._get_connection_stats(),
            'query_performance': dashboard._get_query_performance(),
            'database_size': dashboard._get_database_size(),
        }

        return JsonResponse(metrics, safe=False)
