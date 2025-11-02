"""
Infrastructure Metrics Collector

Collects system, database, and application metrics for anomaly detection.

Metrics collected:
- System: CPU, memory, disk I/O
- Database: Connection count, query times
- Application: Celery queue depth, request latency, error rates

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
"""

import logging
import psutil
from typing import Dict, Any, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import connection, DatabaseError
from django.core.cache import cache

logger = logging.getLogger('monitoring.infrastructure')

__all__ = ['InfrastructureCollector']


class InfrastructureCollector:
    """
    Collects infrastructure metrics for anomaly detection.

    Rule #7 compliant: < 150 lines
    """

    @staticmethod
    def collect_all_metrics() -> List[Dict[str, Any]]:
        """
        Collect all infrastructure metrics.

        Returns:
            List of metric dicts with: timestamp, metric_name, value, tags, metadata
        """
        metrics = []
        timestamp = timezone.now()

        # Collect system metrics
        metrics.extend(InfrastructureCollector._collect_system_metrics(timestamp))

        # Collect database metrics
        metrics.extend(InfrastructureCollector._collect_database_metrics(timestamp))

        # Collect application metrics
        metrics.extend(InfrastructureCollector._collect_application_metrics(timestamp))

        logger.debug(f"Collected {len(metrics)} infrastructure metrics")
        return metrics

    @staticmethod
    def _collect_system_metrics(timestamp: datetime) -> List[Dict[str, Any]]:
        """Collect system-level metrics using psutil."""
        metrics = []

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append({
                'timestamp': timestamp,
                'metric_name': 'cpu_percent',
                'value': cpu_percent,
                'tags': {'type': 'system'},
                'metadata': {'unit': 'percent'}
            })

            # Memory usage
            memory = psutil.virtual_memory()
            metrics.append({
                'timestamp': timestamp,
                'metric_name': 'memory_percent',
                'value': memory.percent,
                'tags': {'type': 'system'},
                'metadata': {
                    'unit': 'percent',
                    'total_mb': memory.total / 1024**2,
                    'available_mb': memory.available / 1024**2
                }
            })

            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                metrics.append({
                    'timestamp': timestamp,
                    'metric_name': 'disk_io_read_mb',
                    'value': disk_io.read_bytes / 1024**2,
                    'tags': {'type': 'system'},
                    'metadata': {'unit': 'megabytes'}
                })
                metrics.append({
                    'timestamp': timestamp,
                    'metric_name': 'disk_io_write_mb',
                    'value': disk_io.write_bytes / 1024**2,
                    'tags': {'type': 'system'},
                    'metadata': {'unit': 'megabytes'}
                })

        except Exception as e:
            logger.warning(f"Error collecting system metrics: {e}")

        return metrics

    @staticmethod
    def _collect_database_metrics(timestamp: datetime) -> List[Dict[str, Any]]:
        """Collect database metrics from Django connection."""
        metrics = []

        try:
            # Active connections (approximated by query count)
            from django.db import connections
            db_connections_active = sum(
                1 for conn in connections.all()
                if conn.connection is not None
            )
            metrics.append({
                'timestamp': timestamp,
                'metric_name': 'db_connections_active',
                'value': db_connections_active,
                'tags': {'type': 'database'},
                'metadata': {'unit': 'connections'}
            })

            # Query time (from recent queries if DEBUG=True)
            if connection.queries:
                recent_queries = connection.queries[-10:]  # Last 10 queries
                avg_time = sum(float(q['time']) for q in recent_queries) / len(recent_queries)
                metrics.append({
                    'timestamp': timestamp,
                    'metric_name': 'db_query_time_ms',
                    'value': avg_time * 1000,  # Convert to milliseconds
                    'tags': {'type': 'database'},
                    'metadata': {'unit': 'milliseconds', 'sample_size': len(recent_queries)}
                })

        except DatabaseError as e:
            logger.warning(f"Error collecting database metrics: {e}")

        return metrics

    @staticmethod
    def _collect_application_metrics(timestamp: datetime) -> List[Dict[str, Any]]:
        """Collect application-level metrics from Redis/cache."""
        metrics = []

        try:
            # Celery queue depth (if available in cache)
            celery_queue_depth = cache.get('celery_queue_depth', 0)
            metrics.append({
                'timestamp': timestamp,
                'metric_name': 'celery_queue_depth',
                'value': celery_queue_depth,
                'tags': {'type': 'application'},
                'metadata': {'unit': 'tasks'}
            })

            # Request latency p95 (if available in cache)
            request_latency_p95 = cache.get('request_latency_p95', 0)
            if request_latency_p95:
                metrics.append({
                    'timestamp': timestamp,
                    'metric_name': 'request_latency_p95',
                    'value': request_latency_p95,
                    'tags': {'type': 'application'},
                    'metadata': {'unit': 'milliseconds', 'percentile': 95}
                })

            # Error rate (if available in cache)
            error_rate = cache.get('error_rate_per_second', 0)
            metrics.append({
                'timestamp': timestamp,
                'metric_name': 'error_rate',
                'value': error_rate,
                'tags': {'type': 'application'},
                'metadata': {'unit': 'errors_per_second'}
            })

        except Exception as e:
            logger.warning(f"Error collecting application metrics: {e}")

        return metrics
