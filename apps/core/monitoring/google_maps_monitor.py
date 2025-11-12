"""
Google Maps Performance Monitoring
Real-time monitoring and analytics for Google Maps API usage.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.db import models
from django.utils import timezone
from dataclasses import dataclass, asdict
import json
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import SERIALIZATION_EXCEPTIONS


logger = logging.getLogger(__name__)


@dataclass
class GoogleMapsMetric:
    """Data class for Google Maps API metrics."""
    timestamp: datetime
    operation: str
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    cache_hit: bool = False
    api_calls_count: int = 1
    user_id: Optional[int] = None
    session_key: Optional[str] = None


class GoogleMapsMonitor:
    """
    Performance monitoring system for Google Maps API usage.
    """

    def __init__(self):
        self.cache_key_prefix = "gmaps_monitor"
        self.metrics_retention_hours = 24
        self.alert_thresholds = {
            'error_rate_threshold': 0.1,  # 10% error rate
            'avg_response_time_threshold': 2000,  # 2 seconds
            'api_calls_per_minute_threshold': 100,
            'cache_hit_rate_threshold': 0.7  # 70% cache hit rate
        }

    def record_metric(self, operation: str, start_time: float, success: bool = True,
                     error_message: str = None, cache_hit: bool = False,
                     user_id: int = None, session_key: str = None):
        """
        Record a Google Maps API operation metric.

        Args:
            operation: Type of operation (geocode, directions, etc.)
            start_time: Start time from time.time()
            success: Whether the operation succeeded
            error_message: Error message if failed
            cache_hit: Whether this was served from cache
            user_id: User ID if available
            session_key: Session key for tracking
        """
        try:
            duration_ms = (time.time() - start_time) * 1000

            metric = GoogleMapsMetric(
                timestamp=timezone.now(),
                operation=operation,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
                cache_hit=cache_hit,
                user_id=user_id,
                session_key=session_key
            )

            # Store in cache for real-time monitoring
            self._store_metric(metric)

            # Log significant events
            if not success:
                logger.error(f"Google Maps {operation} failed: {error_message} (duration: {duration_ms:.1f}ms)")
            elif duration_ms > self.alert_thresholds['avg_response_time_threshold']:
                logger.warning(f"Google Maps {operation} slow response: {duration_ms:.1f}ms")

            # Check for alerts
            self._check_alerts()

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to record Google Maps metric: {str(e)}")

    def _store_metric(self, metric: GoogleMapsMetric):
        """Store metric in cache for real-time access."""
        try:
            # Store individual metric
            metric_key = f"{self.cache_key_prefix}:metric:{int(time.time() * 1000)}"
            cache.set(metric_key, asdict(metric), timeout=self.metrics_retention_hours * 3600)

            # Update running statistics
            stats_key = f"{self.cache_key_prefix}:stats:current"
            current_stats = cache.get(stats_key, {
                'total_calls': 0,
                'successful_calls': 0,
                'cache_hits': 0,
                'total_duration': 0.0,
                'operations': {},
                'last_updated': timezone.now().isoformat()
            })

            current_stats['total_calls'] += 1
            current_stats['total_duration'] += metric.duration_ms

            if metric.success:
                current_stats['successful_calls'] += 1

            if metric.cache_hit:
                current_stats['cache_hits'] += 1

            if metric.operation not in current_stats['operations']:
                current_stats['operations'][metric.operation] = {'count': 0, 'duration': 0.0}

            current_stats['operations'][metric.operation]['count'] += 1
            current_stats['operations'][metric.operation]['duration'] += metric.duration_ms
            current_stats['last_updated'] = timezone.now().isoformat()

            cache.set(stats_key, current_stats, timeout=self.metrics_retention_hours * 3600)

        except CACHE_EXCEPTIONS as e:
            logger.error(f"Failed to store metric: {str(e)}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get current performance statistics.

        Returns:
            Dictionary containing performance metrics
        """
        stats_key = f"{self.cache_key_prefix}:stats:current"
        current_stats = cache.get(stats_key, {})

        if not current_stats:
            return {
                'total_calls': 0,
                'success_rate': 0.0,
                'cache_hit_rate': 0.0,
                'avg_response_time': 0.0,
                'operations': {},
                'status': 'No data available',
                'last_updated': None
            }

        total_calls = current_stats.get('total_calls', 0)
        successful_calls = current_stats.get('successful_calls', 0)
        cache_hits = current_stats.get('cache_hits', 0)
        total_duration = current_stats.get('total_duration', 0.0)

        stats = {
            'total_calls': total_calls,
            'success_rate': (successful_calls / total_calls) if total_calls > 0 else 0.0,
            'cache_hit_rate': (cache_hits / total_calls) if total_calls > 0 else 0.0,
            'avg_response_time': (total_duration / total_calls) if total_calls > 0 else 0.0,
            'operations': current_stats.get('operations', {}),
            'status': self._get_health_status(current_stats),
            'last_updated': current_stats.get('last_updated'),
            'alerts': self._get_active_alerts(current_stats)
        }

        return stats

    def _get_health_status(self, stats: Dict[str, Any]) -> str:
        """Determine overall health status based on metrics."""
        total_calls = stats.get('total_calls', 0)
        successful_calls = stats.get('successful_calls', 0)
        cache_hits = stats.get('cache_hits', 0)
        total_duration = stats.get('total_duration', 0.0)

        if total_calls == 0:
            return 'No Activity'

        success_rate = successful_calls / total_calls
        cache_hit_rate = cache_hits / total_calls
        avg_response_time = total_duration / total_calls

        # Check thresholds
        if success_rate < (1 - self.alert_thresholds['error_rate_threshold']):
            return 'Critical - High Error Rate'

        if avg_response_time > self.alert_thresholds['avg_response_time_threshold']:
            return 'Warning - Slow Response'

        if cache_hit_rate < self.alert_thresholds['cache_hit_rate_threshold']:
            return 'Warning - Low Cache Hit Rate'

        return 'Healthy'

    def _get_active_alerts(self, stats: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get list of active alerts based on current metrics."""
        alerts = []
        total_calls = stats.get('total_calls', 0)

        if total_calls == 0:
            return alerts

        successful_calls = stats.get('successful_calls', 0)
        cache_hits = stats.get('cache_hits', 0)
        total_duration = stats.get('total_duration', 0.0)

        success_rate = successful_calls / total_calls
        cache_hit_rate = cache_hits / total_calls
        avg_response_time = total_duration / total_calls

        if success_rate < (1 - self.alert_thresholds['error_rate_threshold']):
            alerts.append({
                'type': 'error',
                'message': f'High error rate: {(1-success_rate)*100:.1f}%',
                'threshold': f'{self.alert_thresholds["error_rate_threshold"]*100:.1f}%'
            })

        if avg_response_time > self.alert_thresholds['avg_response_time_threshold']:
            alerts.append({
                'type': 'warning',
                'message': f'Slow average response: {avg_response_time:.0f}ms',
                'threshold': f'{self.alert_thresholds["avg_response_time_threshold"]}ms'
            })

        if cache_hit_rate < self.alert_thresholds['cache_hit_rate_threshold']:
            alerts.append({
                'type': 'info',
                'message': f'Low cache hit rate: {cache_hit_rate*100:.1f}%',
                'threshold': f'{self.alert_thresholds["cache_hit_rate_threshold"]*100:.1f}%'
            })

        return alerts

    def _check_alerts(self):
        """Check if any alert conditions are met and log them."""
        stats = self.get_performance_stats()
        alerts = stats.get('alerts', [])

        for alert in alerts:
            if alert['type'] == 'error':
                logger.error(f"Google Maps Alert: {alert['message']}")
            elif alert['type'] == 'warning':
                logger.warning(f"Google Maps Alert: {alert['message']}")
            elif alert['type'] == 'info':
                logger.info(f"Google Maps Alert: {alert['message']}")

    def get_recent_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Get recent metrics for detailed analysis.

        Args:
            hours: Number of hours of history to retrieve

        Returns:
            List of recent metrics
        """
        try:
            # This is a simplified implementation - in production,
            # you'd want to use a proper time-series database
            metrics = []
            cutoff_time = timezone.now() - timedelta(hours=hours)

            # In a real implementation, you'd query stored metrics
            # For now, return current stats formatted as time series
            stats = self.get_performance_stats()
            if stats['total_calls'] > 0:
                metrics.append({
                    'timestamp': stats['last_updated'],
                    'metrics': stats
                })

            return metrics

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to get recent metrics: {str(e)}")
            return []

    def clear_metrics(self):
        """Clear all stored metrics (for testing/debugging)."""
        try:
            stats_key = f"{self.cache_key_prefix}:stats:current"
            cache.delete(stats_key)
            logger.info("Google Maps metrics cleared")
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to clear metrics: {str(e)}")

    def export_metrics(self, format: str = 'json') -> str:
        """
        Export current metrics for external analysis.

        Args:
            format: Export format ('json', 'csv')

        Returns:
            Formatted metrics string
        """
        try:
            stats = self.get_performance_stats()

            if format.lower() == 'json':
                return json.dumps(stats, indent=2, default=str)
            elif format.lower() == 'csv':
                # Simple CSV format for basic stats
                csv_lines = [
                    'metric,value',
                    f'total_calls,{stats["total_calls"]}',
                    f'success_rate,{stats["success_rate"]:.3f}',
                    f'cache_hit_rate,{stats["cache_hit_rate"]:.3f}',
                    f'avg_response_time_ms,{stats["avg_response_time"]:.1f}',
                    f'status,{stats["status"]}'
                ]
                return '\n'.join(csv_lines)
            else:
                return json.dumps(stats, indent=2, default=str)

        except SERIALIZATION_EXCEPTIONS as e:
            logger.error(f"Failed to export metrics: {str(e)}")
            return f"Export failed: {str(e)}"


# Global monitor instance
google_maps_monitor = GoogleMapsMonitor()


# Context manager for easy metric recording
class GoogleMapsMetricContext:
    """Context manager for recording Google Maps API metrics."""

    def __init__(self, operation: str, user_id: int = None, session_key: str = None):
        self.operation = operation
        self.user_id = user_id
        self.session_key = session_key
        self.start_time = None
        self.cache_hit = False

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        error_message = str(exc_val) if exc_val else None

        google_maps_monitor.record_metric(
            operation=self.operation,
            start_time=self.start_time,
            success=success,
            error_message=error_message,
            cache_hit=self.cache_hit,
            user_id=self.user_id,
            session_key=self.session_key
        )

    def mark_cache_hit(self):
        """Mark this operation as a cache hit."""
        self.cache_hit = True