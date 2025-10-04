"""
Spatial Query Performance Monitoring Service

Tracks spatial query execution times, detects slow queries, and provides
real-time performance metrics for dashboard integration.

Following .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #11: Specific exception handling
- Rule #13: Use constants instead of magic numbers
"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import contextmanager
from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY

logger = logging.getLogger(__name__)


class SpatialQueryPerformanceMonitor:
    """
    Monitor and track spatial query performance with slow query detection.

    Features:
    - Execution time tracking
    - Slow query alerting (>500ms threshold)
    - Real-time metrics collection
    - Dashboard integration support
    """

    # Performance thresholds (in milliseconds)
    SLOW_QUERY_THRESHOLD_MS = 500
    VERY_SLOW_QUERY_THRESHOLD_MS = 1000
    CRITICAL_SLOW_QUERY_THRESHOLD_MS = 2000

    # Cache keys
    METRICS_KEY = "spatial_query_metrics:{date}"
    SLOW_QUERIES_KEY = "spatial_slow_queries:{date}"
    ALERT_HISTORY_KEY = "spatial_query_alerts:{date}"

    # Limits
    MAX_SLOW_QUERIES_STORED = 100
    MAX_METRICS_PER_DAY = 10000

    def __init__(self):
        """Initialize performance monitor."""
        self.alert_callback = None

    def set_alert_callback(self, callback):
        """
        Set callback function for slow query alerts.

        Args:
            callback: Function that accepts (query_info: Dict) -> None
        """
        self.alert_callback = callback

    @contextmanager
    def track_query(self, query_type: str, query_params: Optional[Dict] = None):
        """
        Context manager to track query execution time.

        Usage:
            with monitor.track_query('geofence_check', {'geofence_id': 123}):
                # Your spatial query code here
                result = perform_spatial_query()

        Args:
            query_type: Type of spatial query (e.g., 'geofence_check', 'distance_calc')
            query_params: Optional parameters for the query

        Yields:
            Dict with 'start_time' key for additional tracking
        """
        start_time = time.time()
        tracking_info = {'start_time': start_time}

        try:
            yield tracking_info
        finally:
            elapsed_ms = (time.time() - start_time) * 1000

            # Record metrics
            self._record_query_execution(
                query_type=query_type,
                execution_time_ms=elapsed_ms,
                query_params=query_params or {}
            )

            # Check for slow query
            if elapsed_ms > self.SLOW_QUERY_THRESHOLD_MS:
                self._handle_slow_query(
                    query_type=query_type,
                    execution_time_ms=elapsed_ms,
                    query_params=query_params or {}
                )

    def _record_query_execution(
        self,
        query_type: str,
        execution_time_ms: float,
        query_params: Dict
    ):
        """
        Record query execution metrics.

        Args:
            query_type: Type of spatial query
            execution_time_ms: Execution time in milliseconds
            query_params: Query parameters
        """
        try:
            date_str = datetime.now().strftime('%Y%m%d')
            metrics_key = self.METRICS_KEY.format(date=date_str)

            # Get existing metrics
            metrics = cache.get(metrics_key, {
                'total_queries': 0,
                'total_time_ms': 0.0,
                'queries_by_type': {},
                'last_updated': None
            })

            # Update metrics
            metrics['total_queries'] += 1
            metrics['total_time_ms'] += execution_time_ms
            metrics['last_updated'] = timezone.now().isoformat()

            # Track by query type
            if query_type not in metrics['queries_by_type']:
                metrics['queries_by_type'][query_type] = {
                    'count': 0,
                    'total_time_ms': 0.0,
                    'avg_time_ms': 0.0,
                    'min_time_ms': execution_time_ms,
                    'max_time_ms': execution_time_ms
                }

            type_metrics = metrics['queries_by_type'][query_type]
            type_metrics['count'] += 1
            type_metrics['total_time_ms'] += execution_time_ms
            type_metrics['avg_time_ms'] = (
                type_metrics['total_time_ms'] / type_metrics['count']
            )
            type_metrics['min_time_ms'] = min(
                type_metrics['min_time_ms'], execution_time_ms
            )
            type_metrics['max_time_ms'] = max(
                type_metrics['max_time_ms'], execution_time_ms
            )

            # Prevent memory overflow
            if metrics['total_queries'] < self.MAX_METRICS_PER_DAY:
                cache.set(metrics_key, metrics, SECONDS_IN_DAY)

        except (DatabaseError, ValueError, TypeError) as e:
            logger.error(f"Failed to record query metrics: {e}")

    def _handle_slow_query(
        self,
        query_type: str,
        execution_time_ms: float,
        query_params: Dict
    ):
        """
        Handle slow query detection and alerting.

        Args:
            query_type: Type of spatial query
            execution_time_ms: Execution time in milliseconds
            query_params: Query parameters
        """
        try:
            # Determine severity
            if execution_time_ms > self.CRITICAL_SLOW_QUERY_THRESHOLD_MS:
                severity = 'CRITICAL'
            elif execution_time_ms > self.VERY_SLOW_QUERY_THRESHOLD_MS:
                severity = 'HIGH'
            else:
                severity = 'MEDIUM'

            # Create slow query record
            slow_query_info = {
                'timestamp': timezone.now().isoformat(),
                'query_type': query_type,
                'execution_time_ms': round(execution_time_ms, 2),
                'severity': severity,
                'query_params': query_params
            }

            # Store slow query
            date_str = datetime.now().strftime('%Y%m%d')
            slow_queries_key = self.SLOW_QUERIES_KEY.format(date=date_str)

            slow_queries = cache.get(slow_queries_key, [])
            slow_queries.append(slow_query_info)

            # Keep only recent slow queries
            if len(slow_queries) > self.MAX_SLOW_QUERIES_STORED:
                slow_queries = slow_queries[-self.MAX_SLOW_QUERIES_STORED:]

            cache.set(slow_queries_key, slow_queries, SECONDS_IN_DAY)

            # Log slow query
            logger.warning(
                f"Slow spatial query detected: {query_type} "
                f"took {execution_time_ms:.2f}ms (severity: {severity})"
            )

            # Trigger alert callback if set
            if self.alert_callback:
                try:
                    self.alert_callback(slow_query_info)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")

        except (DatabaseError, ValueError, TypeError) as e:
            logger.error(f"Failed to handle slow query: {e}")

    def get_performance_metrics(
        self,
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific date.

        Args:
            date: Date to get metrics for (default: today)

        Returns:
            Dictionary containing performance metrics
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime('%Y%m%d')
        metrics_key = self.METRICS_KEY.format(date=date_str)

        metrics = cache.get(metrics_key, {
            'total_queries': 0,
            'total_time_ms': 0.0,
            'queries_by_type': {},
            'last_updated': None
        })

        # Calculate overall average
        if metrics['total_queries'] > 0:
            metrics['avg_time_ms'] = (
                metrics['total_time_ms'] / metrics['total_queries']
            )
        else:
            metrics['avg_time_ms'] = 0.0

        return metrics

    def get_slow_queries(
        self,
        date: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> List[Dict]:
        """
        Get slow queries for a specific date.

        Args:
            date: Date to get slow queries for (default: today)
            severity: Filter by severity (MEDIUM, HIGH, CRITICAL)

        Returns:
            List of slow query records
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime('%Y%m%d')
        slow_queries_key = self.SLOW_QUERIES_KEY.format(date=date_str)

        slow_queries = cache.get(slow_queries_key, [])

        # Filter by severity if specified
        if severity:
            slow_queries = [
                q for q in slow_queries
                if q.get('severity') == severity
            ]

        return slow_queries

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get summary data for dashboard display.

        Returns:
            Dictionary with dashboard-ready metrics
        """
        metrics = self.get_performance_metrics()
        slow_queries = self.get_slow_queries()

        # Count by severity
        slow_by_severity = {
            'CRITICAL': 0,
            'HIGH': 0,
            'MEDIUM': 0
        }
        for query in slow_queries:
            severity = query.get('severity', 'MEDIUM')
            slow_by_severity[severity] += 1

        return {
            'total_queries_today': metrics.get('total_queries', 0),
            'avg_query_time_ms': round(metrics.get('avg_time_ms', 0.0), 2),
            'slow_queries_count': len(slow_queries),
            'slow_queries_by_severity': slow_by_severity,
            'queries_by_type': metrics.get('queries_by_type', {}),
            'last_updated': metrics.get('last_updated'),
            'health_status': self._calculate_health_status(metrics, slow_queries)
        }

    def _calculate_health_status(
        self,
        metrics: Dict,
        slow_queries: List
    ) -> str:
        """
        Calculate overall health status of spatial query performance.

        Args:
            metrics: Performance metrics
            slow_queries: List of slow queries

        Returns:
            Health status: 'HEALTHY', 'WARNING', or 'CRITICAL'
        """
        total_queries = metrics.get('total_queries', 0)
        avg_time_ms = metrics.get('avg_time_ms', 0.0)

        # No queries = healthy by default
        if total_queries == 0:
            return 'HEALTHY'

        # Check critical slow queries
        critical_count = sum(
            1 for q in slow_queries
            if q.get('severity') == 'CRITICAL'
        )

        if critical_count > 5:
            return 'CRITICAL'

        # Check average query time
        if avg_time_ms > self.SLOW_QUERY_THRESHOLD_MS:
            return 'WARNING'

        # Check slow query percentage
        slow_percentage = (len(slow_queries) / total_queries) * 100
        if slow_percentage > 10:
            return 'WARNING'

        return 'HEALTHY'


# Singleton instance
spatial_query_monitor = SpatialQueryPerformanceMonitor()