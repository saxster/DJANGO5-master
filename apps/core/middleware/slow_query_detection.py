"""
Slow Query Detection Middleware

Addresses Issue #18: Missing Database Indexes
Automatic detection and alerting for slow database queries with index recommendations.

Features:
- Real-time slow query detection (configurable threshold)
- Automatic index recommendation
- Integration with correlation IDs for debugging
- Configurable alerting and logging
- Performance metrics collection

Complies with: .claude/rules.md Rule #12 (Database Query Optimization)
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import timedelta

from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('slow_queries')


class SlowQueryDetectionMiddleware(MiddlewareMixin):
    """
    Middleware to detect and log slow database queries.

    Monitors query execution times and automatically logs slow queries
    with index recommendations for performance optimization.
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        self.slow_threshold_ms = getattr(settings, 'SLOW_QUERY_THRESHOLD_MS', 100)
        self.critical_threshold_ms = getattr(settings, 'CRITICAL_QUERY_THRESHOLD_MS', 500)
        self.enable_monitoring = getattr(settings, 'ENABLE_SLOW_QUERY_MONITORING', True)
        super().__init__(get_response)

    def process_request(self, request):
        """Initialize query monitoring for request."""
        if not self.enable_monitoring:
            return None

        request._query_start_time = time.time()
        request._initial_query_count = len(connection.queries)
        return None

    def process_response(self, request, response):
        """Analyze queries executed during request processing."""
        if not self.enable_monitoring or not hasattr(request, '_query_start_time'):
            return response

        request_time = (time.time() - request._query_start_time) * 1000

        if hasattr(connection, 'queries'):
            current_queries = connection.queries[request._initial_query_count:]
            self._analyze_queries(request, current_queries, request_time)

        return response

    def _analyze_queries(self, request, queries: List[Dict], total_time_ms: float):
        """Analyze queries for performance issues."""
        correlation_id = getattr(request, 'correlation_id', 'unknown')
        slow_queries = []
        critical_queries = []

        for query in queries:
            try:
                query_time_ms = float(query.get('time', 0)) * 1000

                if query_time_ms >= self.critical_threshold_ms:
                    critical_queries.append((query, query_time_ms))
                elif query_time_ms >= self.slow_threshold_ms:
                    slow_queries.append((query, query_time_ms))

            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Could not parse query time: {type(e).__name__}",
                    extra={'correlation_id': correlation_id}
                )

        if critical_queries:
            self._log_critical_queries(request, critical_queries, correlation_id)

        if slow_queries:
            self._log_slow_queries(request, slow_queries, correlation_id)

        if len(queries) > 20:
            self._log_query_count_warning(request, len(queries), correlation_id)

    def _log_slow_queries(self, request, slow_queries: List, correlation_id: str):
        """Log slow queries with recommendations."""
        for query, query_time in slow_queries[:5]:
            sql = query.get('sql', '')
            table_name = self._extract_table_name(sql)
            recommendations = self._generate_index_recommendations(sql, table_name)

            logger.warning(
                f"Slow query detected: {query_time:.2f}ms",
                extra={
                    'correlation_id': correlation_id,
                    'path': request.path,
                    'method': request.method,
                    'query_time_ms': query_time,
                    'table': table_name,
                    'sql_preview': sql[:200],
                    'recommendations': recommendations,
                }
            )

            self._cache_slow_query_metrics(table_name, query_time)

    def _log_critical_queries(self, request, critical_queries: List, correlation_id: str):
        """Log critically slow queries requiring immediate attention."""
        for query, query_time in critical_queries:
            sql = query.get('sql', '')
            table_name = self._extract_table_name(sql)

            logger.error(
                f"CRITICAL: Extremely slow query: {query_time:.2f}ms",
                extra={
                    'correlation_id': correlation_id,
                    'path': request.path,
                    'method': request.method,
                    'query_time_ms': query_time,
                    'table': table_name,
                    'sql_preview': sql[:300],
                    'severity': 'CRITICAL',
                }
            )

            self._increment_critical_query_counter(table_name)

    def _log_query_count_warning(self, request, query_count: int, correlation_id: str):
        """Log warning for excessive query count (potential N+1)."""
        logger.warning(
            f"High query count detected: {query_count} queries",
            extra={
                'correlation_id': correlation_id,
                'path': request.path,
                'method': request.method,
                'query_count': query_count,
                'recommendation': 'Investigate potential N+1 queries - use select_related/prefetch_related',
            }
        )

    def _extract_table_name(self, sql: str) -> str:
        """Extract primary table name from SQL query."""
        sql_upper = sql.upper()

        if 'FROM' in sql_upper:
            from_index = sql_upper.index('FROM')
            remaining = sql[from_index + 4:].strip()
            parts = remaining.split()
            if parts:
                table_name = parts[0].strip('"\'')
                return table_name.replace('"', '').replace('`', '')

        return 'unknown'

    def _generate_index_recommendations(self, sql: str, table_name: str) -> List[str]:
        """Generate index recommendations based on query patterns."""
        recommendations = []
        sql_upper = sql.upper()

        if 'WHERE' in sql_upper and 'INDEX' not in sql_upper:
            recommendations.append(f"Consider adding index on WHERE clause fields in {table_name}")

        if 'ORDER BY' in sql_upper and 'INDEX' not in sql_upper:
            recommendations.append(f"Consider adding index on ORDER BY fields in {table_name}")

        if 'JOIN' in sql_upper:
            recommendations.append(f"Verify foreign key indexes exist for joins in {table_name}")

        if any(kw in sql_upper for kw in ['LIKE', 'ILIKE', 'SIMILAR']):
            recommendations.append(f"Consider GIN/trigram index for text search in {table_name}")

        return recommendations

    def _cache_slow_query_metrics(self, table_name: str, query_time: float):
        """Cache slow query metrics for dashboard display."""
        cache_key = f'slow_query_metrics_{table_name}'
        metrics = cache.get(cache_key, {'count': 0, 'total_time': 0, 'max_time': 0})

        metrics['count'] += 1
        metrics['total_time'] += query_time
        metrics['max_time'] = max(metrics['max_time'], query_time)
        metrics['avg_time'] = metrics['total_time'] / metrics['count']
        metrics['last_seen'] = timezone.now().isoformat()

        cache.set(cache_key, metrics, 3600)

    def _increment_critical_query_counter(self, table_name: str):
        """Increment critical query counter for alerting."""
        cache_key = f'critical_queries_{table_name}'
        count = cache.get(cache_key, 0)
        cache.incr(cache_key)

        if count >= 10:
            logger.critical(
                f"Multiple critical slow queries on {table_name}",
                extra={
                    'table': table_name,
                    'count': count,
                    'action_required': 'Immediate index optimization needed',
                }
            )


__all__ = ['SlowQueryDetectionMiddleware']