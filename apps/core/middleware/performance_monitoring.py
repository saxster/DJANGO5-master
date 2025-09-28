"""
Performance Monitoring Middleware

Tracks request performance, identifies heavy operations, and provides
comprehensive monitoring capabilities for async task migration.

Key features:
- Request timing and performance metrics
- Database query analysis
- Heavy operation detection
- Performance trend analysis
- Real-time alerts for performance issues
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from apps.core.utils_new.sql_security import QueryValidator


logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Comprehensive performance monitoring middleware.

    Tracks:
    - Request response times
    - Database query counts and timing
    - Heavy operation detection
    - Memory usage patterns
    - Async task correlation
    """

    # Performance thresholds
    SLOW_REQUEST_THRESHOLD = 2.0  # 2 seconds
    VERY_SLOW_REQUEST_THRESHOLD = 5.0  # 5 seconds
    HIGH_QUERY_COUNT_THRESHOLD = 50
    SLOW_QUERY_THRESHOLD = 0.1  # 100ms

    # Cache keys
    PERFORMANCE_STATS_KEY = 'performance_stats'
    SLOW_REQUESTS_KEY = 'slow_requests'
    PERFORMANCE_ALERTS_KEY = 'performance_alerts'

    def __init__(self, get_response):
        self.get_response = get_response
        self.local = threading.local()

    def process_request(self, request: HttpRequest) -> None:
        """Initialize performance tracking for request."""
        try:
            # Initialize tracking data
            self.local.start_time = time.time()
            self.local.start_queries = len(connection.queries)
            self.local.request_id = str(uuid.uuid4())
            self.local.heavy_operations = []

            # Store request metadata
            request.performance_data = {
                'request_id': self.local.request_id,
                'start_time': self.local.start_time,
                'path': request.path,
                'method': request.method,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'is_ajax': request.headers.get('X-Requested-With') == 'XMLHttpRequest',
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
            }

            # Check for async task correlation
            task_id = request.headers.get('X-Task-ID') or request.GET.get('task_id')
            if task_id:
                request.performance_data['related_task_id'] = task_id

            logger.debug(f"Performance tracking started for request {self.local.request_id}")

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to initialize performance tracking: {str(e)}")

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Process response and collect performance metrics."""
        try:
            if not hasattr(self.local, 'start_time'):
                return response

            # Calculate timing metrics
            end_time = time.time()
            request_duration = end_time - self.local.start_time

            # Database metrics
            end_queries = len(connection.queries)
            query_count = end_queries - self.local.start_queries
            query_time = self._calculate_query_time()

            # Build performance metrics
            performance_metrics = {
                'request_id': self.local.request_id,
                'duration': request_duration,
                'query_count': query_count,
                'query_time': query_time,
                'status_code': response.status_code,
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
                'timestamp': timezone.now(),
                'path': request.path,
                'method': request.method,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'heavy_operations': getattr(self.local, 'heavy_operations', [])
            }

            # Classify request performance
            performance_metrics['classification'] = self._classify_performance(
                request_duration, query_count, query_time
            )

            # Store metrics
            self._store_performance_metrics(performance_metrics)

            # Check for alerts
            self._check_performance_alerts(performance_metrics)

            # Add performance headers in debug mode
            if settings.DEBUG:
                response['X-Request-Duration'] = f"{request_duration:.3f}s"
                response['X-Query-Count'] = str(query_count)
                response['X-Query-Time'] = f"{query_time:.3f}s"
                response['X-Request-ID'] = self.local.request_id

            # Log slow requests
            if request_duration > self.SLOW_REQUEST_THRESHOLD:
                self._log_slow_request(performance_metrics)

            logger.debug(f"Performance tracking completed for request {self.local.request_id}")

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to process performance metrics: {str(e)}")

        return response

    def _calculate_query_time(self) -> float:
        """Calculate total time spent on database queries."""
        try:
            if not hasattr(self.local, 'start_queries'):
                return 0.0

            query_time = 0.0
            current_queries = connection.queries[self.local.start_queries:]

            for query in current_queries:
                try:
                    query_time += float(query.get('time', 0))
                except (ValueError, TypeError):
                    continue

            return query_time

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to calculate query time: {str(e)}")
            return 0.0

    def _classify_performance(
        self,
        duration: float,
        query_count: int,
        query_time: float
    ) -> Dict[str, Any]:
        """Classify request performance and identify issues."""
        classification = {
            'overall': 'good',
            'issues': [],
            'recommendations': []
        }

        # Duration classification
        if duration > self.VERY_SLOW_REQUEST_THRESHOLD:
            classification['overall'] = 'critical'
            classification['issues'].append('very_slow_response')
            classification['recommendations'].append('Consider async processing for heavy operations')
        elif duration > self.SLOW_REQUEST_THRESHOLD:
            classification['overall'] = 'warning'
            classification['issues'].append('slow_response')
            classification['recommendations'].append('Optimize request processing')

        # Query analysis
        if query_count > self.HIGH_QUERY_COUNT_THRESHOLD:
            classification['overall'] = max(classification['overall'], 'warning', key=lambda x: ['good', 'warning', 'critical'].index(x))
            classification['issues'].append('high_query_count')
            classification['recommendations'].append('Use select_related() and prefetch_related()')

        # Query time analysis
        if query_time > duration * 0.5:  # Queries taking >50% of request time
            classification['overall'] = max(classification['overall'], 'warning', key=lambda x: ['good', 'warning', 'critical'].index(x))
            classification['issues'].append('database_bottleneck')
            classification['recommendations'].append('Optimize database queries and add indexes')

        # Async operation opportunities
        if duration > 1.0 and 'pdf' in str(getattr(self.local, 'heavy_operations', [])).lower():
            classification['recommendations'].append('Move PDF generation to async tasks')

        if duration > 1.0 and 'api' in str(getattr(self.local, 'heavy_operations', [])).lower():
            classification['recommendations'].append('Move external API calls to async tasks')

        return classification

    def _store_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """Store performance metrics for analysis."""
        try:
            # Store individual request metrics
            cache_key = f"perf_request_{metrics['request_id']}"
            cache.set(cache_key, metrics, timeout=3600)  # 1 hour

            # Update aggregated statistics
            self._update_performance_stats(metrics)

            # Store slow requests separately
            if metrics['duration'] > self.SLOW_REQUEST_THRESHOLD:
                self._store_slow_request(metrics)

        except (ConnectionError, ValueError) as e:
            logger.error(f"Failed to store performance metrics: {str(e)}")

    def _update_performance_stats(self, metrics: Dict[str, Any]) -> None:
        """Update aggregated performance statistics."""
        try:
            # Get current stats
            stats = cache.get(self.PERFORMANCE_STATS_KEY, {
                'total_requests': 0,
                'total_duration': 0.0,
                'total_queries': 0,
                'slow_requests': 0,
                'critical_requests': 0,
                'last_updated': timezone.now(),
                'hourly_stats': {}
            })

            # Update counters
            stats['total_requests'] += 1
            stats['total_duration'] += metrics['duration']
            stats['total_queries'] += metrics['query_count']

            if metrics['classification']['overall'] == 'warning':
                stats['slow_requests'] += 1
            elif metrics['classification']['overall'] == 'critical':
                stats['critical_requests'] += 1

            # Update hourly stats
            hour_key = metrics['timestamp'].strftime('%Y-%m-%d-%H')
            if hour_key not in stats['hourly_stats']:
                stats['hourly_stats'][hour_key] = {
                    'requests': 0,
                    'avg_duration': 0.0,
                    'slow_requests': 0
                }

            hourly = stats['hourly_stats'][hour_key]
            hourly['requests'] += 1
            hourly['avg_duration'] = (
                (hourly['avg_duration'] * (hourly['requests'] - 1) + metrics['duration'])
                / hourly['requests']
            )

            if metrics['duration'] > self.SLOW_REQUEST_THRESHOLD:
                hourly['slow_requests'] += 1

            stats['last_updated'] = timezone.now()

            # Clean old hourly stats (keep last 48 hours)
            cutoff_time = timezone.now() - timedelta(hours=48)
            cutoff_key = cutoff_time.strftime('%Y-%m-%d-%H')
            stats['hourly_stats'] = {
                k: v for k, v in stats['hourly_stats'].items()
                if k >= cutoff_key
            }

            # Update cache
            cache.set(self.PERFORMANCE_STATS_KEY, stats, timeout=86400)  # 24 hours

        except (ConnectionError, ValueError) as e:
            logger.error(f"Failed to update performance stats: {str(e)}")

    def _store_slow_request(self, metrics: Dict[str, Any]) -> None:
        """Store slow request for detailed analysis."""
        try:
            slow_requests = cache.get(self.SLOW_REQUESTS_KEY, [])

            # Add current request
            slow_request = {
                'request_id': metrics['request_id'],
                'duration': metrics['duration'],
                'path': metrics['path'],
                'method': metrics['method'],
                'query_count': metrics['query_count'],
                'query_time': metrics['query_time'],
                'timestamp': metrics['timestamp'],
                'classification': metrics['classification'],
                'user_id': metrics['user_id']
            }

            slow_requests.append(slow_request)

            # Keep only last 100 slow requests
            slow_requests = slow_requests[-100:]

            cache.set(self.SLOW_REQUESTS_KEY, slow_requests, timeout=86400)

        except (ConnectionError, ValueError) as e:
            logger.error(f"Failed to store slow request: {str(e)}")

    def _check_performance_alerts(self, metrics: Dict[str, Any]) -> None:
        """Check if performance alerts should be triggered."""
        try:
            alerts = []

            # Critical response time alert
            if metrics['duration'] > self.VERY_SLOW_REQUEST_THRESHOLD:
                alerts.append({
                    'type': 'critical_response_time',
                    'message': f"Very slow request: {metrics['duration']:.2f}s",
                    'request_id': metrics['request_id'],
                    'timestamp': metrics['timestamp']
                })

            # High query count alert
            if metrics['query_count'] > self.HIGH_QUERY_COUNT_THRESHOLD:
                alerts.append({
                    'type': 'high_query_count',
                    'message': f"High query count: {metrics['query_count']} queries",
                    'request_id': metrics['request_id'],
                    'timestamp': metrics['timestamp']
                })

            # Database bottleneck alert
            if metrics['query_time'] > metrics['duration'] * 0.7:
                alerts.append({
                    'type': 'database_bottleneck',
                    'message': f"Database bottleneck: {metrics['query_time']:.2f}s of {metrics['duration']:.2f}s",
                    'request_id': metrics['request_id'],
                    'timestamp': metrics['timestamp']
                })

            if alerts:
                self._store_performance_alerts(alerts)

        except (ConnectionError, ValueError) as e:
            logger.error(f"Failed to check performance alerts: {str(e)}")

    def _store_performance_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Store performance alerts."""
        try:
            current_alerts = cache.get(self.PERFORMANCE_ALERTS_KEY, [])
            current_alerts.extend(alerts)

            # Keep only last 50 alerts
            current_alerts = current_alerts[-50:]

            cache.set(self.PERFORMANCE_ALERTS_KEY, current_alerts, timeout=86400)

            # Log critical alerts
            for alert in alerts:
                if alert['type'] == 'critical_response_time':
                    logger.warning(f"Performance Alert: {alert['message']} - Request ID: {alert['request_id']}")

        except (ConnectionError, ValueError) as e:
            logger.error(f"Failed to store performance alerts: {str(e)}")

    def _log_slow_request(self, metrics: Dict[str, Any]) -> None:
        """Log detailed information about slow requests."""
        try:
            log_data = {
                'request_id': metrics['request_id'],
                'duration': f"{metrics['duration']:.3f}s",
                'path': metrics['path'],
                'method': metrics['method'],
                'query_count': metrics['query_count'],
                'query_time': f"{metrics['query_time']:.3f}s",
                'issues': metrics['classification']['issues'],
                'recommendations': metrics['classification']['recommendations']
            }

            if metrics['duration'] > self.VERY_SLOW_REQUEST_THRESHOLD:
                logger.warning(f"CRITICAL slow request detected: {log_data}")
            else:
                logger.info(f"Slow request detected: {log_data}")

        except (ConnectionError, ValueError) as e:
            logger.error(f"Failed to log slow request: {str(e)}")

    @classmethod
    def get_performance_stats(cls) -> Dict[str, Any]:
        """Get current performance statistics."""
        try:
            stats = cache.get(cls.PERFORMANCE_STATS_KEY, {})

            if stats.get('total_requests', 0) > 0:
                stats['avg_duration'] = stats['total_duration'] / stats['total_requests']
                stats['avg_queries'] = stats['total_queries'] / stats['total_requests']
                stats['slow_request_rate'] = (stats['slow_requests'] / stats['total_requests']) * 100
            else:
                stats.update({
                    'avg_duration': 0.0,
                    'avg_queries': 0.0,
                    'slow_request_rate': 0.0
                })

            return stats

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Failed to get performance stats: {str(e)}")
            return {}

    @classmethod
    def get_slow_requests(cls, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent slow requests."""
        try:
            slow_requests = cache.get(cls.SLOW_REQUESTS_KEY, [])
            return slow_requests[-limit:] if slow_requests else []

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Failed to get slow requests: {str(e)}")
            return []

    @classmethod
    def get_performance_alerts(cls, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent performance alerts."""
        try:
            alerts = cache.get(cls.PERFORMANCE_ALERTS_KEY, [])
            return alerts[-limit:] if alerts else []

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Failed to get performance alerts: {str(e)}")
            return []

    @classmethod
    def record_heavy_operation(cls, operation_type: str, operation_data: Dict[str, Any]) -> None:
        """Record a heavy operation for current request."""
        try:
            # This would be called by views performing heavy operations
            local = getattr(cls._get_current_middleware(), 'local', None)
            if local and hasattr(local, 'heavy_operations'):
                local.heavy_operations.append({
                    'type': operation_type,
                    'data': operation_data,
                    'timestamp': time.time()
                })

        except (ConnectionError, DatabaseError, IntegrityError, ValueError) as e:
            logger.error(f"Failed to record heavy operation: {str(e)}")

    @classmethod
    def _get_current_middleware(cls):
        """Get current middleware instance (helper for heavy operation recording)."""
        # This is a simplified approach - in production, you'd use thread-local storage
        # or context variables to track the current middleware instance
        return cls