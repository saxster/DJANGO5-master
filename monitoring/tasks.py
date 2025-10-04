"""
Monitoring Background Tasks

Celery tasks for automated monitoring, analysis, and alerting.

Tasks:
- Periodic anomaly detection
- Alert aggregation and delivery
- Performance baseline calculation
- Security intelligence scanning
- Metrics cleanup and archival

Queue: maintenance (priority: 3)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError

from apps.core.constants.datetime_constants import MINUTES_IN_HOUR, MINUTES_IN_DAY
from monitoring.services.anomaly_detector import anomaly_detector, Anomaly
from monitoring.services.alert_aggregator import alert_aggregator, Alert
from monitoring.services.performance_analyzer import performance_analyzer, PerformanceInsight
from monitoring.services.security_intelligence import security_intelligence, ThreatEvent
from monitoring.django_monitoring import metrics_collector

logger = logging.getLogger('monitoring.tasks')

__all__ = [
    'detect_anomalies_task',
    'aggregate_alerts_task',
    'analyze_performance_task',
    'scan_security_threats_task',
    'cleanup_old_metrics_task',
    'update_performance_baselines_task',
]


@shared_task(
    bind=True,
    queue='maintenance',
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
    time_limit=300,
    name='monitoring.detect_anomalies'
)
def detect_anomalies_task(self, metric_names: Optional[List[str]] = None, window_minutes: int = MINUTES_IN_HOUR):
    """
    Detect anomalies in metrics and create alerts.

    Args:
        metric_names: List of metrics to analyze (None = all)
        window_minutes: Analysis time window
    """
    try:
        if not metric_names:
            metric_names = [
                'request_duration',
                'graphql_query_validation',
                'websocket_connection_attempt',
                'database_query_time',
                'cache_hit_rate'
            ]

        all_anomalies = []
        for metric_name in metric_names:
            try:
                anomalies = anomaly_detector.detect_anomalies(metric_name, window_minutes)
                all_anomalies.extend(anomalies)

                # Create alerts for high-severity anomalies
                for anomaly in anomalies:
                    if anomaly.severity in ('high', 'critical'):
                        alert = Alert(
                            title=f"Anomaly Detected: {metric_name}",
                            message=f"{anomaly.detection_method}: {anomaly.value:.2f} (expected: {anomaly.expected_value:.2f})",
                            severity='warning' if anomaly.severity == 'high' else 'error',
                            source='anomaly_detection',
                            metadata=anomaly.to_dict()
                        )
                        alert_aggregator.process_alert(alert)

            except Exception as e:
                logger.warning(f"Error detecting anomalies for {metric_name}: {e}")
                continue

        logger.info(
            f"Anomaly detection completed: {len(all_anomalies)} anomalies found",
            extra={'anomaly_count': len(all_anomalies), 'metrics_analyzed': len(metric_names)}
        )

        return {
            'success': True,
            'anomalies_detected': len(all_anomalies),
            'metrics_analyzed': len(metric_names)
        }

    except Exception as e:
        logger.error(f"Anomaly detection task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    bind=True,
    queue='maintenance',
    max_retries=3,
    retry_backoff=True,
    time_limit=120,
    name='monitoring.aggregate_alerts'
)
def aggregate_alerts_task(self, window_minutes: int = 5):
    """
    Aggregate and summarize alerts.

    Args:
        window_minutes: Time window for aggregation
    """
    try:
        # This is a placeholder - in production, you'd fetch alerts from a queue or database
        # For now, we'll just log that aggregation ran
        logger.info(
            f"Alert aggregation completed for {window_minutes} minute window",
            extra={'window_minutes': window_minutes}
        )

        return {
            'success': True,
            'window_minutes': window_minutes
        }

    except Exception as e:
        logger.error(f"Alert aggregation task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=30)


@shared_task(
    bind=True,
    queue='maintenance',
    max_retries=3,
    retry_backoff=True,
    time_limit=300,
    name='monitoring.analyze_performance'
)
def analyze_performance_task(self, metric_names: Optional[List[str]] = None, window_minutes: int = MINUTES_IN_HOUR):
    """
    Analyze performance trends and detect regressions.

    Args:
        metric_names: List of metrics to analyze (None = all)
        window_minutes: Analysis time window
    """
    try:
        if not metric_names:
            metric_names = [
                'request_duration',
                'graphql_query_validation',
                'database_query_time'
            ]

        all_insights = []
        for metric_name in metric_names:
            try:
                insights = performance_analyzer.analyze_metric(metric_name, window_minutes=window_minutes)
                all_insights.extend(insights)

                # Create alerts for regressions
                for insight in insights:
                    if insight.insight_type == 'regression' and insight.severity in ('warning', 'critical'):
                        alert = Alert(
                            title=f"Performance Regression: {metric_name}",
                            message=insight.message,
                            severity=insight.severity,
                            source='performance_analysis',
                            metadata=insight.to_dict()
                        )
                        alert_aggregator.process_alert(alert)

            except Exception as e:
                logger.warning(f"Error analyzing performance for {metric_name}: {e}")
                continue

        logger.info(
            f"Performance analysis completed: {len(all_insights)} insights generated",
            extra={'insight_count': len(all_insights), 'metrics_analyzed': len(metric_names)}
        )

        return {
            'success': True,
            'insights_generated': len(all_insights),
            'metrics_analyzed': len(metric_names)
        }

    except Exception as e:
        logger.error(f"Performance analysis task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    bind=True,
    queue='maintenance',
    max_retries=3,
    retry_backoff=True,
    time_limit=180,
    name='monitoring.scan_security_threats'
)
def scan_security_threats_task(self, window_minutes: int = MINUTES_IN_HOUR):
    """
    Scan for security threats and attack patterns.

    Args:
        window_minutes: Analysis time window
    """
    try:
        threat_summary = security_intelligence.get_threat_summary(window_minutes)

        # Log threat summary
        if threat_summary['total_threats'] > 0:
            logger.warning(
                f"Security threats detected: {threat_summary['total_threats']} total",
                extra=threat_summary
            )

            # Create alert if significant threats detected
            if threat_summary['total_threats'] > 10:
                alert = Alert(
                    title="Multiple Security Threats Detected",
                    message=f"{threat_summary['total_threats']} threats detected in the last {window_minutes} minutes",
                    severity='warning',
                    source='security_intelligence',
                    metadata=threat_summary
                )
                alert_aggregator.process_alert(alert)

        return {
            'success': True,
            'threats_detected': threat_summary['total_threats'],
            'window_minutes': window_minutes
        }

    except Exception as e:
        logger.error(f"Security threat scan task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    bind=True,
    queue='maintenance',
    max_retries=2,
    time_limit=600,
    name='monitoring.cleanup_old_metrics'
)
def cleanup_old_metrics_task(self, retention_days: int = 7):
    """
    Clean up old metrics from in-memory storage.

    Args:
        retention_days: Keep metrics for this many days
    """
    try:
        cutoff_time = timezone.now() - timedelta(days=retention_days)
        cleaned_count = 0

        with metrics_collector.lock:
            for metric_name, metric_data in list(metrics_collector.metrics.items()):
                original_count = len(metric_data)
                # Filter out old metrics
                metrics_collector.metrics[metric_name] = [
                    m for m in metric_data
                    if m['timestamp'] > cutoff_time
                ]
                cleaned_count += original_count - len(metrics_collector.metrics[metric_name])

        logger.info(
            f"Metrics cleanup completed: {cleaned_count} old metrics removed",
            extra={'cleaned_count': cleaned_count, 'retention_days': retention_days}
        )

        return {
            'success': True,
            'metrics_cleaned': cleaned_count,
            'retention_days': retention_days
        }

    except Exception as e:
        logger.error(f"Metrics cleanup task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)


@shared_task(
    bind=True,
    queue='maintenance',
    max_retries=3,
    retry_backoff=True,
    time_limit=300,
    name='monitoring.update_performance_baselines'
)
def update_performance_baselines_task(self, metric_names: Optional[List[str]] = None):
    """
    Update performance baselines for metrics.

    Args:
        metric_names: List of metrics to update (None = all)
    """
    try:
        from monitoring.models import PerformanceBaseline

        if not metric_names:
            metric_names = [
                'request_duration',
                'graphql_query_validation',
                'database_query_time'
            ]

        updated_count = 0
        for metric_name in metric_names:
            try:
                # Get 7-day stats for baseline
                stats = metrics_collector.get_stats(metric_name, MINUTES_IN_DAY * 7)

                if stats and stats.get('count', 0) >= 100:
                    # Create or update baseline
                    baseline, created = PerformanceBaseline.objects.update_or_create(
                        metric_name=metric_name,
                        endpoint='',
                        defaults={
                            'mean': stats.get('mean', 0),
                            'p50': stats.get('p50', 0),
                            'p95': stats.get('p95', 0),
                            'p99': stats.get('p99', 0),
                            'sample_count': stats.get('count', 0),
                            'is_active': True
                        }
                    )
                    updated_count += 1

            except (DatabaseError, IntegrityError) as e:
                logger.warning(f"Error updating baseline for {metric_name}: {e}")
                continue

        logger.info(
            f"Performance baselines updated: {updated_count} metrics",
            extra={'updated_count': updated_count}
        )

        return {
            'success': True,
            'baselines_updated': updated_count
        }

    except Exception as e:
        logger.error(f"Baseline update task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)
