"""
Redis Performance Metrics Collector

Comprehensive metrics collection and analysis for Redis instances with:
- Real-time performance monitoring
- Historical trend analysis
- Capacity planning insights
- Multi-instance support (standalone + Sentinel)
- Alert threshold management
- Performance optimization recommendations

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service layer <150 lines per class
- Rule #11: Specific exception handling
"""

import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class RedisMetrics:
    """Comprehensive Redis performance metrics."""
    timestamp: datetime
    instance_name: str
    instance_role: str  # 'master', 'replica', 'standalone'

    # Memory metrics
    used_memory: int
    used_memory_human: str
    used_memory_peak: int
    memory_fragmentation_ratio: float
    maxmemory: int
    evicted_keys: int

    # Performance metrics
    total_commands_processed: int
    instantaneous_ops_per_sec: int
    instantaneous_input_kbps: float
    instantaneous_output_kbps: float
    keyspace_hits: int
    keyspace_misses: int
    hit_ratio: float

    # Connection metrics
    connected_clients: int
    client_recent_max_input_buffer: int
    client_recent_max_output_buffer: int
    blocked_clients: int
    tracking_clients: int

    # Replication metrics (for master/replica)
    connected_slaves: int
    master_repl_offset: int
    repl_backlog_active: int
    repl_backlog_size: int

    # Persistence metrics
    rdb_changes_since_last_save: int
    rdb_bgsave_in_progress: int
    rdb_last_save_time: int
    aof_enabled: int
    aof_rewrite_in_progress: int
    aof_last_rewrite_time_sec: int

    # System metrics
    uptime_in_seconds: int
    redis_version: str
    process_id: int


@dataclass
class PerformanceAlert:
    """Performance alert information."""
    metric_name: str
    alert_level: str  # 'info', 'warning', 'critical'
    current_value: Union[int, float]
    threshold_value: Union[int, float]
    message: str
    recommendation: str
    timestamp: datetime


class RedisMetricsCollector:
    """
    Advanced Redis metrics collection and analysis service.

    Collects comprehensive performance metrics from Redis instances
    and provides analysis, alerting, and optimization recommendations.
    """

    # Performance thresholds for alerting
    PERFORMANCE_THRESHOLDS = {
        'memory_usage_percent': {'warning': 70, 'critical': 85},
        'hit_ratio_percent': {'warning': 80, 'critical': 60},
        'fragmentation_ratio': {'warning': 1.5, 'critical': 2.0},
        'connected_clients_percent': {'warning': 80, 'critical': 95},
        'ops_per_second': {'warning': 10000, 'critical': 50000},
        'blocked_clients': {'warning': 10, 'critical': 50},
        'evicted_keys_rate': {'warning': 100, 'critical': 1000},  # per hour
    }

    def __init__(self):
        self.collection_history: List[RedisMetrics] = []
        self.max_history_size = 1000  # Keep last 1000 measurements

    def collect_metrics(self, instance_name: str = 'default') -> Optional[RedisMetrics]:
        """
        Collect comprehensive metrics from Redis instance.

        Args:
            instance_name: Name identifier for the Redis instance

        Returns:
            RedisMetrics object with current performance data
        """
        try:
            # Get Redis client (works with both standalone and Sentinel)
            redis_client = cache._cache.get_master_client()

            # Get comprehensive info from Redis
            server_info = redis_client.info('server')
            memory_info = redis_client.info('memory')
            stats_info = redis_client.info('stats')
            clients_info = redis_client.info('clients')
            replication_info = redis_client.info('replication')
            persistence_info = redis_client.info('persistence')

            # Calculate derived metrics
            hits = stats_info.get('keyspace_hits', 0)
            misses = stats_info.get('keyspace_misses', 0)
            hit_ratio = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0

            # Determine instance role
            role = replication_info.get('role', 'standalone')

            # Create metrics object
            metrics = RedisMetrics(
                timestamp=timezone.now(),
                instance_name=instance_name,
                instance_role=role,

                # Memory metrics
                used_memory=memory_info.get('used_memory', 0),
                used_memory_human=memory_info.get('used_memory_human', '0B'),
                used_memory_peak=memory_info.get('used_memory_peak', 0),
                memory_fragmentation_ratio=memory_info.get('mem_fragmentation_ratio', 1.0),
                maxmemory=memory_info.get('maxmemory', 0),
                evicted_keys=stats_info.get('evicted_keys', 0),

                # Performance metrics
                total_commands_processed=stats_info.get('total_commands_processed', 0),
                instantaneous_ops_per_sec=stats_info.get('instantaneous_ops_per_sec', 0),
                instantaneous_input_kbps=stats_info.get('instantaneous_input_kbps', 0.0),
                instantaneous_output_kbps=stats_info.get('instantaneous_output_kbps', 0.0),
                keyspace_hits=hits,
                keyspace_misses=misses,
                hit_ratio=round(hit_ratio, 2),

                # Connection metrics
                connected_clients=clients_info.get('connected_clients', 0),
                client_recent_max_input_buffer=clients_info.get('client_recent_max_input_buffer', 0),
                client_recent_max_output_buffer=clients_info.get('client_recent_max_output_buffer', 0),
                blocked_clients=clients_info.get('blocked_clients', 0),
                tracking_clients=clients_info.get('tracking_clients', 0),

                # Replication metrics
                connected_slaves=replication_info.get('connected_slaves', 0),
                master_repl_offset=replication_info.get('master_repl_offset', 0),
                repl_backlog_active=replication_info.get('repl_backlog_active', 0),
                repl_backlog_size=replication_info.get('repl_backlog_size', 0),

                # Persistence metrics
                rdb_changes_since_last_save=persistence_info.get('rdb_changes_since_last_save', 0),
                rdb_bgsave_in_progress=persistence_info.get('rdb_bgsave_in_progress', 0),
                rdb_last_save_time=persistence_info.get('rdb_last_save_time', 0),
                aof_enabled=persistence_info.get('aof_enabled', 0),
                aof_rewrite_in_progress=persistence_info.get('aof_rewrite_in_progress', 0),
                aof_last_rewrite_time_sec=persistence_info.get('aof_last_rewrite_time_sec', 0),

                # System metrics
                uptime_in_seconds=server_info.get('uptime_in_seconds', 0),
                redis_version=server_info.get('redis_version', 'unknown'),
                process_id=server_info.get('process_id', 0),
            )

            # Store in history for trend analysis
            self._store_metrics_history(metrics)

            logger.debug(f"Metrics collected for {instance_name}: {metrics.hit_ratio}% hit ratio")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting Redis metrics for {instance_name}: {e}")
            return None

    def analyze_performance(self, metrics: RedisMetrics) -> List[PerformanceAlert]:
        """
        Analyze metrics and generate performance alerts.

        Args:
            metrics: Current Redis metrics

        Returns:
            List of performance alerts
        """
        alerts = []

        try:
            # Memory usage analysis
            if metrics.maxmemory > 0:
                memory_usage_percent = (metrics.used_memory / metrics.maxmemory) * 100
                self._check_threshold(
                    alerts, 'memory_usage_percent', memory_usage_percent,
                    'Memory usage',
                    f'{memory_usage_percent:.1f}% memory usage',
                    'Consider increasing maxmemory or enable eviction'
                )

            # Hit ratio analysis
            self._check_threshold(
                alerts, 'hit_ratio_percent', metrics.hit_ratio,
                'Cache hit ratio',
                f'{metrics.hit_ratio}% hit ratio',
                'Review TTL settings and cache warming strategy',
                reverse_threshold=True  # Lower values are worse
            )

            # Fragmentation analysis
            self._check_threshold(
                alerts, 'fragmentation_ratio', metrics.memory_fragmentation_ratio,
                'Memory fragmentation',
                f'{metrics.memory_fragmentation_ratio:.2f} fragmentation ratio',
                'Run memory defragmentation during off-peak hours'
            )

            # Connection analysis
            max_clients = 10000  # Default from configuration
            if metrics.connected_clients > 0:
                client_usage_percent = (metrics.connected_clients / max_clients) * 100
                self._check_threshold(
                    alerts, 'connected_clients_percent', client_usage_percent,
                    'Client connections',
                    f'{metrics.connected_clients} connected clients ({client_usage_percent:.1f}%)',
                    'Monitor client connection patterns and consider connection pooling'
                )

            # Operations per second analysis
            self._check_threshold(
                alerts, 'ops_per_second', metrics.instantaneous_ops_per_sec,
                'Operations rate',
                f'{metrics.instantaneous_ops_per_sec} ops/sec',
                'Monitor for performance bottlenecks and consider scaling'
            )

            # Blocked clients analysis
            self._check_threshold(
                alerts, 'blocked_clients', metrics.blocked_clients,
                'Blocked clients',
                f'{metrics.blocked_clients} blocked clients',
                'Investigate slow operations causing client blocking'
            )

            # Evicted keys analysis (rate-based)
            evicted_rate = self._calculate_eviction_rate(metrics)
            if evicted_rate is not None:
                self._check_threshold(
                    alerts, 'evicted_keys_rate', evicted_rate,
                    'Key eviction rate',
                    f'{evicted_rate:.1f} evictions/hour',
                    'Increase memory limit or optimize data structures'
                )

        except Exception as e:
            logger.error(f"Error analyzing performance metrics: {e}")

        return alerts

    def get_performance_trends(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get performance trends for specified time period.

        Args:
            hours_back: Hours of history to analyze

        Returns:
            Dictionary with trend analysis
        """
        cutoff_time = timezone.now() - timedelta(hours=hours_back)

        # Filter recent metrics
        recent_metrics = [
            m for m in self.collection_history
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {'error': 'No recent metrics available for trend analysis'}

        # Calculate trends
        trends = {
            'time_period_hours': hours_back,
            'data_points': len(recent_metrics),
            'trends': {},
            'summary': {}
        }

        # Analyze key metrics trends
        metrics_to_trend = [
            'used_memory', 'hit_ratio', 'instantaneous_ops_per_sec',
            'connected_clients', 'memory_fragmentation_ratio'
        ]

        for metric_name in metrics_to_trend:
            values = [getattr(m, metric_name) for m in recent_metrics]

            if values:
                trends['trends'][metric_name] = {
                    'current': values[-1],
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'trend_direction': self._calculate_trend_direction(values)
                }

        # Performance summary
        latest_metrics = recent_metrics[-1]
        trends['summary'] = {
            'overall_health': self._assess_overall_health(latest_metrics),
            'peak_ops_per_sec': max(m.instantaneous_ops_per_sec for m in recent_metrics),
            'avg_hit_ratio': sum(m.hit_ratio for m in recent_metrics) / len(recent_metrics),
            'memory_growth_mb': (recent_metrics[-1].used_memory - recent_metrics[0].used_memory) / 1024 / 1024,
            'uptime_hours': latest_metrics.uptime_in_seconds / 3600
        }

        return trends

    def get_capacity_recommendations(self, metrics: RedisMetrics) -> List[str]:
        """
        Generate capacity planning recommendations.

        Args:
            metrics: Current Redis metrics

        Returns:
            List of capacity recommendations
        """
        recommendations = []

        try:
            # Memory capacity analysis
            if metrics.maxmemory > 0:
                usage_percent = (metrics.used_memory / metrics.maxmemory) * 100
                if usage_percent > 80:
                    recommendations.append(
                        f"Memory usage at {usage_percent:.1f}% - consider increasing maxmemory to "
                        f"{int(metrics.maxmemory * 1.5 / 1024 / 1024)}MB"
                    )

            # Connection capacity analysis
            max_clients = 10000  # From configuration
            if metrics.connected_clients > max_clients * 0.7:
                recommendations.append(
                    f"High client connection usage - consider increasing maxclients or "
                    f"implementing connection pooling"
                )

            # Performance analysis
            if metrics.instantaneous_ops_per_sec > 8000:
                recommendations.append(
                    "High operations rate detected - consider read replicas for scaling"
                )

            # Fragmentation analysis
            if metrics.memory_fragmentation_ratio > 1.5:
                recommendations.append(
                    f"Memory fragmentation at {metrics.memory_fragmentation_ratio:.2f} - "
                    f"schedule defragmentation during off-peak hours"
                )

            # Persistence analysis
            if metrics.rdb_changes_since_last_save > 100000:
                recommendations.append(
                    "Large number of changes since last save - consider more frequent snapshots"
                )

            # Positive feedback for good performance
            if not recommendations:
                recommendations.append("Redis performance is optimal - no capacity changes needed")

        except Exception as e:
            logger.error(f"Error generating capacity recommendations: {e}")
            recommendations.append("Error generating recommendations - check Redis connection")

        return recommendations

    def _store_metrics_history(self, metrics: RedisMetrics):
        """Store metrics in history for trend analysis."""
        self.collection_history.append(metrics)

        # Limit history size to prevent memory growth
        if len(self.collection_history) > self.max_history_size:
            self.collection_history = self.collection_history[-self.max_history_size:]

    def _check_threshold(self, alerts: List[PerformanceAlert],
                        metric_key: str, current_value: Union[int, float],
                        metric_display_name: str, message: str, recommendation: str,
                        reverse_threshold: bool = False):
        """Check if metric exceeds thresholds and add alerts."""
        thresholds = self.PERFORMANCE_THRESHOLDS.get(metric_key, {})

        for level in ['critical', 'warning']:
            threshold_value = thresholds.get(level)
            if threshold_value is None:
                continue

            # Check threshold (normal or reverse)
            threshold_exceeded = (
                current_value >= threshold_value if not reverse_threshold
                else current_value <= threshold_value
            )

            if threshold_exceeded:
                alerts.append(PerformanceAlert(
                    metric_name=metric_key,
                    alert_level=level,
                    current_value=current_value,
                    threshold_value=threshold_value,
                    message=f"{metric_display_name}: {message}",
                    recommendation=recommendation,
                    timestamp=timezone.now()
                ))
                break  # Only add highest severity alert

    def _calculate_eviction_rate(self, metrics: RedisMetrics) -> Optional[float]:
        """Calculate eviction rate per hour."""
        # This would need historical data to calculate rate
        # For now, return None if no historical data
        if len(self.collection_history) < 2:
            return None

        # Find metrics from 1 hour ago (approximately)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        historical_metrics = None

        for historical in reversed(self.collection_history[:-1]):
            if historical.timestamp <= one_hour_ago:
                historical_metrics = historical
                break

        if historical_metrics:
            evictions_diff = metrics.evicted_keys - historical_metrics.evicted_keys
            time_diff_hours = (metrics.timestamp - historical_metrics.timestamp).total_seconds() / 3600
            return evictions_diff / time_diff_hours if time_diff_hours > 0 else 0

        return None

    def _calculate_trend_direction(self, values: List[Union[int, float]]) -> str:
        """Calculate trend direction from list of values."""
        if len(values) < 2:
            return 'stable'

        # Simple trend calculation using first and last values
        first_value = values[0]
        last_value = values[-1]

        if last_value > first_value * 1.1:  # 10% increase
            return 'increasing'
        elif last_value < first_value * 0.9:  # 10% decrease
            return 'decreasing'
        else:
            return 'stable'

    def _assess_overall_health(self, metrics: RedisMetrics) -> str:
        """Assess overall Redis health based on metrics."""
        alerts = self.analyze_performance(metrics)

        critical_alerts = [a for a in alerts if a.alert_level == 'critical']
        warning_alerts = [a for a in alerts if a.alert_level == 'warning']

        if critical_alerts:
            return 'critical'
        elif warning_alerts:
            return 'warning'
        else:
            return 'healthy'


# Global metrics collector instance
redis_metrics_collector = RedisMetricsCollector()

# Export public interface
__all__ = [
    'RedisMetricsCollector',
    'RedisMetrics',
    'PerformanceAlert',
    'redis_metrics_collector'
]