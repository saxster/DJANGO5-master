"""
Query Optimization Middleware.

This middleware automatically optimizes database queries during request processing
to prevent N+1 query problems and improve performance.
"""
import time
import logging
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from apps.core.error_handling import ErrorHandler
from apps.core.utils_new.sanitized_logging import sanitized_warning

logger = logging.getLogger("query_optimization")


class QueryOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware to monitor and optimize database queries during request processing.

    This middleware:
    1. Tracks query count and execution time
    2. Identifies potential N+1 query problems
    3. Provides performance insights in development
    4. Logs optimization opportunities
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Initialize query tracking for the request."""
        # Store initial query count and time
        request._query_start_time = time.time()
        request._query_start_count = len(connection.queries)

        # Initialize tracking data
        request._query_tracking = {
            'start_time': request._query_start_time,
            'start_count': request._query_start_count,
            'potential_n_plus_one': [],
            'slow_queries': [],
            'optimization_applied': False
        }

        return None

    def process_response(self, request, response):
        """Analyze query performance and provide optimization insights."""
        try:
            # Calculate query metrics
            end_time = time.time()
            end_count = len(connection.queries)

            query_count = end_count - request._query_start_count
            total_time = end_time - request._query_start_time
            query_time = self._calculate_query_time(request._query_start_count, end_count)

            # Store metrics in request for potential use
            request._query_metrics = {
                'count': query_count,
                'total_time': total_time,
                'query_time': query_time,
                'efficiency_ratio': query_time / total_time if total_time > 0 else 0
            }

            # Add headers in development mode
            if getattr(settings, 'DEBUG', False):
                response['X-Query-Count'] = str(query_count)
                response['X-Query-Time'] = f"{query_time:.3f}s"
                response['X-Total-Time'] = f"{total_time:.3f}s"

            # Analyze and log performance issues
            self._analyze_performance(request, response)

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'query_optimization_middleware',
                    'path': request.path,
                    'method': request.method
                }
            )
            sanitized_warning(
                logger,
                f"Query analysis failed (ID: {correlation_id})"
            )

        return response

    def _calculate_query_time(self, start_count: int, end_count: int) -> float:
        """
        Calculate total time spent on database queries.

        Args:
            start_count: Starting query count
            end_count: Ending query count

        Returns:
            float: Total query time in seconds
        """
        total_time = 0.0

        try:
            queries = connection.queries[start_count:end_count]
            for query in queries:
                if 'time' in query and query['time']:
                    total_time += float(query['time'])
        except (IndexError, ValueError, KeyError):
            # If we can't calculate exact time, return 0
            pass

        return total_time

    def _analyze_performance(self, request, response):
        """
        Analyze query performance and log optimization opportunities.

        Args:
            request: HTTP request object
            response: HTTP response object
        """
        metrics = getattr(request, '_query_metrics', {})
        query_count = metrics.get('count', 0)
        query_time = metrics.get('query_time', 0)

        # Define performance thresholds
        thresholds = {
            'high_query_count': getattr(settings, 'QUERY_COUNT_WARNING_THRESHOLD', 10),
            'slow_query_time': getattr(settings, 'QUERY_TIME_WARNING_THRESHOLD', 0.5),
            'n_plus_one_threshold': getattr(settings, 'N_PLUS_ONE_THRESHOLD', 5)
        }

        issues = []

        # Check for high query count (potential N+1)
        if query_count > thresholds['high_query_count']:
            issues.append(f"High query count: {query_count} queries")
            self._detect_n_plus_one_patterns(request)

        # Check for slow queries
        if query_time > thresholds['slow_query_time']:
            issues.append(f"Slow query time: {query_time:.3f}s")

        # Log performance issues
        if issues:
            correlation_id = getattr(request, 'correlation_id', 'unknown')
            safe_user_ref = getattr(request, 'safe_user_ref', 'Anonymous')

            sanitized_warning(
                logger,
                f"Performance issues detected: {', '.join(issues)}",
                extra={
                    'correlation_id': correlation_id,
                    'user_ref': safe_user_ref,
                    'path': request.path,
                    'method': request.method,
                    'query_count': query_count,
                    'query_time': query_time,
                    'issues': issues
                }
            )

            # Add optimization recommendations in development
            if getattr(settings, 'DEBUG', False):
                self._add_optimization_recommendations(request, response, issues)

    def _detect_n_plus_one_patterns(self, request):
        """
        Detect potential N+1 query patterns.

        Args:
            request: HTTP request object
        """
        try:
            start_count = request._query_start_count
            queries = connection.queries[start_count:]

            # Group similar queries
            query_patterns = {}
            for query in queries:
                sql = query.get('sql', '')
                # Normalize SQL by removing specific IDs
                normalized = self._normalize_sql_for_pattern_detection(sql)

                if normalized in query_patterns:
                    query_patterns[normalized] += 1
                else:
                    query_patterns[normalized] = 1

            # Identify potential N+1 patterns
            n_plus_one_patterns = []
            for pattern, count in query_patterns.items():
                if count >= 3:  # 3 or more similar queries might indicate N+1
                    n_plus_one_patterns.append({
                        'pattern': pattern[:100],  # Truncate for logging
                        'count': count
                    })

            if n_plus_one_patterns:
                correlation_id = getattr(request, 'correlation_id', 'unknown')
                sanitized_warning(
                    logger,
                    f"Potential N+1 query patterns detected",
                    extra={
                        'correlation_id': correlation_id,
                        'patterns': n_plus_one_patterns,
                        'path': request.path
                    }
                )

        except (ValueError, TypeError) as e:
            # Don't let pattern detection errors affect request processing
            sanitized_warning(logger, f"N+1 pattern detection failed: {type(e).__name__}")

    def _normalize_sql_for_pattern_detection(self, sql: str) -> str:
        """
        Normalize SQL query for pattern detection.

        Args:
            sql: Raw SQL query

        Returns:
            str: Normalized SQL pattern
        """
        import re

        # Remove specific numeric values that might indicate ID-based queries
        normalized = re.sub(r'\b\d+\b', 'ID', sql)

        # Remove quoted string values
        normalized = re.sub(r"'[^']*'", 'VALUE', normalized)
        normalized = re.sub(r'"[^"]*"', 'VALUE', normalized)

        # Normalize whitespace
        normalized = ' '.join(normalized.split())

        return normalized

    def _add_optimization_recommendations(self, request, response, issues: list):
        """
        Add optimization recommendations to response in development mode.

        Args:
            request: HTTP request object
            response: HTTP response object
            issues: List of performance issues
        """
        recommendations = []

        metrics = getattr(request, '_query_metrics', {})
        query_count = metrics.get('count', 0)

        if query_count > 10:
            recommendations.append("Consider using select_related() for foreign key relationships")
            recommendations.append("Consider using prefetch_related() for many-to-many relationships")
            recommendations.append("Use QueryOptimizer.optimize_queryset() for automatic optimization")

        if metrics.get('query_time', 0) > 0.5:
            recommendations.append("Review database indexes for slow queries")
            recommendations.append("Consider query optimization or caching for complex operations")

        if recommendations:
            # Add as header for development debugging
            response['X-Optimization-Tips'] = '; '.join(recommendations[:3])  # Limit header size


class QueryCountMonitoringMiddleware(MiddlewareMixin):
    """
    Lightweight middleware to monitor query counts and detect excessive database usage.

    This middleware is suitable for production environments where detailed query
    analysis might be too expensive.
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Track initial query count."""
        request._monitor_start_count = len(connection.queries)
        return None

    def process_response(self, request, response):
        """Monitor final query count and log if excessive."""
        try:
            end_count = len(connection.queries)
            query_count = end_count - getattr(request, '_monitor_start_count', 0)

            # Log excessive query usage
            threshold = getattr(settings, 'QUERY_COUNT_ALERT_THRESHOLD', 25)
            if query_count > threshold:
                correlation_id = getattr(request, 'correlation_id', 'unknown')
                safe_user_ref = getattr(request, 'safe_user_ref', 'Anonymous')

                sanitized_warning(
                    logger,
                    f"Excessive database queries detected",
                    extra={
                        'correlation_id': correlation_id,
                        'user_ref': safe_user_ref,
                        'path': request.path,
                        'method': request.method,
                        'query_count': query_count,
                        'threshold': threshold
                    }
                )

        except (ValueError, TypeError) as e:
            # Don't let monitoring errors affect request processing
            pass

        return response