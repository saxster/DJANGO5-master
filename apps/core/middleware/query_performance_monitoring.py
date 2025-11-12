"""
Query Performance Monitoring Middleware.

This middleware monitors database query performance in real-time,
detects N+1 query patterns, and provides performance analytics.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from apps.core.middleware.logging_sanitization import sanitized_warning, sanitized_info

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger('query_performance')


class QueryPerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor and analyze database query performance.

    Features:
    - N+1 query detection
    - Slow query logging
    - Performance metrics collection
    - Query pattern analysis
    - Alert thresholds
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.slow_query_threshold = getattr(settings, 'SLOW_QUERY_THRESHOLD', 0.1)  # 100ms
        self.n_plus_one_threshold = getattr(settings, 'N_PLUS_ONE_THRESHOLD', 10)  # 10 queries
        self.monitoring_enabled = getattr(settings, 'QUERY_MONITORING_ENABLED', True)
        self.sample_rate = getattr(settings, 'QUERY_MONITORING_SAMPLE_RATE', 1.0)  # 100%

    def process_request(self, request):
        """Initialize query monitoring for request."""
        if not self.monitoring_enabled:
            return

        # Skip monitoring for certain paths
        skip_paths = ['/admin/jsi18n/', '/static/', '/media/']
        if any(request.path.startswith(path) for path in skip_paths):
            return

        # Initialize query tracking
        request._query_start_time = time.time()
        request._query_count_start = len(connection.queries)
        request._queries_log = []

    def process_response(self, request, response):
        """Analyze queries and generate performance report."""
        if not self.monitoring_enabled or not hasattr(request, '_query_start_time'):
            return response

        # Calculate query metrics
        total_time = time.time() - request._query_start_time
        query_count = len(connection.queries) - request._query_count_start

        if query_count == 0:
            return response

        # Get queries executed during this request
        queries = connection.queries[request._query_count_start:]

        # Analyze query performance
        analysis = self._analyze_query_performance(queries, total_time, request)

        # Log performance issues
        self._log_performance_issues(analysis, request)

        # Store metrics for analytics
        self._store_performance_metrics(analysis, request)

        # Add performance headers (development only)
        if settings.DEBUG:
            response['X-Query-Count'] = str(query_count)
            response['X-Query-Time'] = f"{analysis['total_query_time']:.3f}s"
            response['X-N-Plus-One-Score'] = str(analysis['n_plus_one_score'])

        return response

    def _analyze_query_performance(self, queries: List[Dict], total_time: float, request) -> Dict[str, Any]:
        """
        Analyze query performance and detect issues.

        Args:
            queries: List of query dictionaries
            total_time: Total request time
            request: Django request object

        Returns:
            dict: Performance analysis results
        """
        analysis = {
            'query_count': len(queries),
            'total_query_time': sum(float(q['time']) for q in queries),
            'slow_queries': [],
            'similar_queries': [],
            'n_plus_one_score': 0,
            'optimization_suggestions': [],
            'request_path': request.path,
            'request_method': request.method,
            'timestamp': time.time()
        }

        # Analyze individual queries
        query_patterns = {}

        for query in queries:
            query_time = float(query['time'])
            sql = query['sql']

            # Detect slow queries
            if query_time > self.slow_query_threshold:
                analysis['slow_queries'].append({
                    'sql': sql[:200] + '...' if len(sql) > 200 else sql,
                    'time': query_time,
                    'stack_trace': query.get('stack', [])
                })

            # Pattern analysis for N+1 detection
            normalized_sql = self._normalize_sql(sql)
            if normalized_sql in query_patterns:
                query_patterns[normalized_sql]['count'] += 1
                query_patterns[normalized_sql]['total_time'] += query_time
            else:
                query_patterns[normalized_sql] = {
                    'count': 1,
                    'total_time': query_time,
                    'example_sql': sql
                }

        # Detect N+1 queries
        for pattern, data in query_patterns.items():
            if data['count'] >= self.n_plus_one_threshold:
                analysis['similar_queries'].append({
                    'pattern': pattern,
                    'count': data['count'],
                    'total_time': data['total_time'],
                    'example_sql': data['example_sql'][:200] + '...'
                })
                analysis['n_plus_one_score'] += data['count']

        # Generate optimization suggestions
        analysis['optimization_suggestions'] = self._generate_suggestions(analysis)

        return analysis

    def _normalize_sql(self, sql: str) -> str:
        """
        Normalize SQL query to detect similar patterns.

        Args:
            sql: Raw SQL query

        Returns:
            str: Normalized SQL pattern
        """
        import re

        # Remove specific values and normalize patterns
        normalized = sql.upper()

        # Replace numeric literals
        normalized = re.sub(r'\b\d+\b', 'N', normalized)

        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'VALUE'", normalized)
        normalized = re.sub(r'"[^"]*"', '"VALUE"', normalized)

        # Replace IN clauses with multiple values
        normalized = re.sub(r'IN \([^)]+\)', 'IN (VALUES)', normalized)

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def _generate_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Generate optimization suggestions based on analysis.

        Args:
            analysis: Query analysis results

        Returns:
            list: List of optimization suggestions
        """
        suggestions = []

        # N+1 query suggestions
        if analysis['similar_queries']:
            suggestions.append(
                "Consider using select_related() or prefetch_related() to eliminate N+1 queries"
            )
            suggestions.append(
                "Review legacy resolvers and ensure DataLoaders are being used"
            )

        # Slow query suggestions
        if analysis['slow_queries']:
            suggestions.append(
                "Add database indexes for slow queries"
            )
            suggestions.append(
                "Consider query optimization or result caching"
            )

        # High query count suggestions
        if analysis['query_count'] > 50:
            suggestions.append(
                "Reduce overall query count with bulk operations"
            )
            suggestions.append(
                "Use QueryOptimizer.optimize_queryset() for automatic optimization"
            )

        return suggestions

    def _log_performance_issues(self, analysis: Dict[str, Any], request):
        """
        Log performance issues based on analysis.

        Args:
            analysis: Query analysis results
            request: Django request object
        """
        path = analysis['request_path']
        query_count = analysis['query_count']
        total_time = analysis['total_query_time']

        # Log N+1 queries
        if analysis['similar_queries']:
            for similar in analysis['similar_queries']:
                sanitized_warning(
                    logger,
                    f"N+1 query detected on {path}",
                    extra={
                        'query_pattern': similar['pattern'],
                        'occurrence_count': similar['count'],
                        'total_time': similar['total_time'],
                        'request_path': path,
                        'request_method': analysis['request_method']
                    }
                )

        # Log slow queries
        if analysis['slow_queries']:
            for slow in analysis['slow_queries']:
                sanitized_warning(
                    logger,
                    f"Slow query detected on {path}",
                    extra={
                        'query_time': slow['time'],
                        'sql_snippet': slow['sql'],
                        'request_path': path,
                        'request_method': analysis['request_method']
                    }
                )

        # Log high query count
        if query_count > 20:
            sanitized_warning(
                logger,
                f"High query count on {path}",
                extra={
                    'query_count': query_count,
                    'total_time': total_time,
                    'request_path': path,
                    'request_method': analysis['request_method']
                }
            )

        # Log successful optimizations
        if query_count <= 5 and total_time < 0.1:
            sanitized_info(
                logger,
                f"Well-optimized endpoint: {path}",
                extra={
                    'query_count': query_count,
                    'total_time': total_time,
                    'request_path': path
                }
            )

    def _store_performance_metrics(self, analysis: Dict[str, Any], request):
        """
        Store performance metrics for analytics.

        Args:
            analysis: Query analysis results
            request: Django request object
        """
        if not settings.DEBUG:
            return

        # Store in cache for development analytics
        cache_key = f"query_performance_{request.path.replace('/', '_')}"

        # Get existing metrics
        existing_metrics = cache.get(cache_key, {
            'total_requests': 0,
            'avg_query_count': 0,
            'avg_query_time': 0,
            'n_plus_one_detections': 0,
            'slow_query_detections': 0
        })

        # Update metrics
        total_requests = existing_metrics['total_requests'] + 1
        existing_metrics.update({
            'total_requests': total_requests,
            'avg_query_count': (
                (existing_metrics['avg_query_count'] * (total_requests - 1) +
                 analysis['query_count']) / total_requests
            ),
            'avg_query_time': (
                (existing_metrics['avg_query_time'] * (total_requests - 1) +
                 analysis['total_query_time']) / total_requests
            ),
            'n_plus_one_detections': (
                existing_metrics['n_plus_one_detections'] +
                len(analysis['similar_queries'])
            ),
            'slow_query_detections': (
                existing_metrics['slow_query_detections'] +
                len(analysis['slow_queries'])
            ),
            'last_updated': time.time()
        })

        # Store updated metrics (expire after 1 hour)
        cache.set(cache_key, existing_metrics, SECONDS_IN_HOUR)


class QueryOptimizationEnforcementMiddleware(MiddlewareMixin):
    """
    Middleware to enforce query optimization standards.

    This middleware can block requests that exceed performance thresholds
    in development environments.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.enforcement_enabled = getattr(settings, 'QUERY_OPTIMIZATION_ENFORCEMENT', False)
        self.max_queries_threshold = getattr(settings, 'MAX_QUERIES_THRESHOLD', 100)
        self.max_query_time_threshold = getattr(settings, 'MAX_QUERY_TIME_THRESHOLD', 5.0)

    def process_request(self, request):
        """Initialize enforcement tracking."""
        if not self.enforcement_enabled or not settings.DEBUG:
            return

        request._enforcement_start_queries = len(connection.queries)
        request._enforcement_start_time = time.time()

    def process_response(self, request, response):
        """Enforce query optimization standards."""
        if not self.enforcement_enabled or not settings.DEBUG:
            return response

        if not hasattr(request, '_enforcement_start_queries'):
            return response

        # Calculate metrics
        query_count = len(connection.queries) - request._enforcement_start_queries
        total_time = time.time() - request._enforcement_start_time

        # Check thresholds
        violations = []

        if query_count > self.max_queries_threshold:
            violations.append(f"Query count ({query_count}) exceeds threshold ({self.max_queries_threshold})")

        if total_time > self.max_query_time_threshold:
            violations.append(f"Query time ({total_time:.2f}s) exceeds threshold ({self.max_query_time_threshold}s)")

        # Log violations
        if violations:
            sanitized_warning(
                logger,
                f"Query optimization violation on {request.path}",
                extra={
                    'violations': violations,
                    'query_count': query_count,
                    'total_time': total_time,
                    'request_path': request.path
                }
            )

            # Add violation headers for debugging
            response['X-Query-Violations'] = '; '.join(violations)

        return response


def get_query_performance_stats(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get query performance statistics for development analytics.

    Args:
        path: Optional specific path to get stats for

    Returns:
        dict: Performance statistics
    """
    if path:
        cache_key = f"query_performance_{path.replace('/', '_')}"
        return cache.get(cache_key, {})

    # Get all performance stats
    all_stats = {}

    # This would require a more sophisticated caching strategy
    # For now, return empty dict
    return all_stats


def clear_query_performance_stats():
    """Clear all query performance statistics."""
    # This would clear all performance-related cache keys
    # Implementation would depend on cache backend capabilities
    pass


# Utility functions for manual query monitoring
class QueryMonitor:
    """Context manager for manual query monitoring."""

    def __init__(self, name: str = "manual_monitoring"):
        self.name = name
        self.start_queries = 0
        self.start_time = 0

    def __enter__(self):
        self.start_queries = len(connection.queries)
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        query_count = len(connection.queries) - self.start_queries
        total_time = time.time() - self.start_time

        sanitized_info(
            logger,
            f"Query monitoring: {self.name}",
            extra={
                'query_count': query_count,
                'total_time': total_time,
                'monitor_name': self.name
            }
        )


# Export classes and functions
__all__ = [
    'QueryPerformanceMonitoringMiddleware',
    'QueryOptimizationEnforcementMiddleware',
    'QueryMonitor',
    'get_query_performance_stats',
    'clear_query_performance_stats',
]
