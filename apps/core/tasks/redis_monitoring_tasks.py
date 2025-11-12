"""
Celery tasks for Redis performance monitoring and alerting.

Provides automated metrics collection, performance monitoring,
and alerting for Redis instances.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.core.mail import mail_admins
from django.conf import settings
from apps.core.services.redis_metrics_collector import redis_metrics_collector
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='maintenance',
    priority=6
)
def collect_redis_performance_metrics(self, instance_name='main'):
    """
    Collect Redis performance metrics and store for analysis.

    Args:
        instance_name (str): Name identifier for the Redis instance

    Returns:
        Dictionary with collection results
    """
    try:
        # Collect current metrics
        metrics = redis_metrics_collector.collect_metrics(instance_name)

        if not metrics:
            logger.warning(f"Failed to collect metrics for Redis instance: {instance_name}")
            return {
                'status': 'failed',
                'message': 'Unable to collect Redis metrics',
                'instance_name': instance_name,
                'timestamp': timezone.now().isoformat()
            }

        # Analyze performance and generate alerts
        performance_alerts = redis_metrics_collector.analyze_performance(metrics)

        # Store metrics for historical analysis (in production, store in database)
        metrics_summary = {
            'timestamp': metrics.timestamp.isoformat(),
            'instance_name': metrics.instance_name,
            'memory_usage_mb': metrics.used_memory / 1024 / 1024,
            'hit_ratio': metrics.hit_ratio,
            'ops_per_second': metrics.instantaneous_ops_per_sec,
            'connected_clients': metrics.connected_clients,
            'fragmentation_ratio': metrics.memory_fragmentation_ratio,
            'alerts_count': len(performance_alerts),
            'critical_alerts': len([a for a in performance_alerts if a.alert_level == 'critical'])
        }

        # Send alerts for critical performance issues
        critical_alerts = [a for a in performance_alerts if a.alert_level == 'critical']
        if critical_alerts and getattr(settings, 'REDIS_PERFORMANCE_ALERTS_ENABLED', True):
            _send_performance_alerts(instance_name, critical_alerts, metrics)

        logger.info(
            f"Redis metrics collected for {instance_name}: "
            f"{metrics.hit_ratio}% hit ratio, {len(performance_alerts)} alerts"
        )

        return {
            'status': 'completed',
            'instance_name': instance_name,
            'metrics_summary': metrics_summary,
            'alerts_generated': len(performance_alerts),
            'timestamp': timezone.now().isoformat()
        }

    except CACHE_EXCEPTIONS as exc:
        logger.error(f"Redis metrics collection failed for {instance_name}: {exc}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

        return {
            'status': 'failed',
            'error': str(exc),
            'instance_name': instance_name,
            'retries': self.request.retries,
            'timestamp': timezone.now().isoformat()
        }


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='maintenance',
    priority=5
)
def analyze_redis_performance_trends(self, hours_back=24):
    """
    Analyze Redis performance trends and generate insights.

    Args:
        hours_back (int): Hours of history to analyze

    Returns:
        Dictionary with trend analysis results
    """
    try:
        logger.info(f"Starting Redis performance trend analysis for last {hours_back} hours")

        # Get performance trends
        trends = redis_metrics_collector.get_performance_trends(hours_back)

        if 'error' in trends:
            logger.warning(f"Trend analysis error: {trends['error']}")
            return {
                'status': 'failed',
                'error': trends['error'],
                'timestamp': timezone.now().isoformat()
            }

        # Analyze trends for significant changes
        insights = []

        # Memory trend analysis
        if 'used_memory' in trends.get('trends', {}):
            memory_trend = trends['trends']['used_memory']
            if memory_trend['trend_direction'] == 'increasing':
                growth_rate = (memory_trend['current'] - memory_trend['min']) / memory_trend['min']
                if growth_rate > 0.2:  # 20% growth
                    insights.append(
                        f"Significant memory growth detected: {growth_rate:.1%} increase in {hours_back}h"
                    )

        # Performance trend analysis
        if 'hit_ratio' in trends.get('trends', {}):
            hit_ratio_trend = trends['trends']['hit_ratio']
            if hit_ratio_trend['trend_direction'] == 'decreasing':
                if hit_ratio_trend['current'] < 80:
                    insights.append(
                        f"Cache hit ratio declining: {hit_ratio_trend['current']:.1f}% (was {hit_ratio_trend['max']:.1f}%)"
                    )

        # Operations trend analysis
        if 'instantaneous_ops_per_sec' in trends.get('trends', {}):
            ops_trend = trends['trends']['instantaneous_ops_per_sec']
            if ops_trend['max'] > 15000:
                insights.append(
                    f"High load periods detected: peak {ops_trend['max']} ops/sec"
                )

        result = {
            'status': 'completed',
            'hours_analyzed': hours_back,
            'data_points': trends.get('data_points', 0),
            'trends_summary': trends.get('summary', {}),
            'insights': insights,
            'timestamp': timezone.now().isoformat()
        }

        # Send insights email if significant issues found
        if len(insights) > 0 and getattr(settings, 'REDIS_TREND_ALERTS_ENABLED', True):
            _send_trend_analysis_email(result)

        logger.info(f"Redis trend analysis completed: {len(insights)} insights generated")
        return result

    except (ValueError, TypeError, AttributeError) as exc:
        logger.error(f"Redis trend analysis failed: {exc}")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {
            'status': 'failed',
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(
    queue='maintenance',
    priority=4
)
def generate_redis_capacity_report():
    """
    Generate comprehensive Redis capacity planning report.

    Returns:
        Dictionary with capacity analysis and recommendations
    """
    try:
        logger.info("Generating Redis capacity planning report")

        # Collect current metrics
        current_metrics = redis_metrics_collector.collect_metrics('main')

        if not current_metrics:
            return {
                'status': 'failed',
                'error': 'Unable to collect current metrics',
                'timestamp': timezone.now().isoformat()
            }

        # Get capacity recommendations
        recommendations = redis_metrics_collector.get_capacity_recommendations(current_metrics)

        # Get performance trends for capacity analysis
        trends_7d = redis_metrics_collector.get_performance_trends(hours_back=168)  # 7 days

        # Calculate capacity projections
        capacity_analysis = {
            'current_usage': {
                'memory_mb': current_metrics.used_memory / 1024 / 1024,
                'memory_percent': (
                    (current_metrics.used_memory / current_metrics.maxmemory) * 100
                    if current_metrics.maxmemory > 0 else 0
                ),
                'connections': current_metrics.connected_clients,
                'ops_per_second': current_metrics.instantaneous_ops_per_sec
            },
            'growth_analysis': {},
            'capacity_recommendations': recommendations,
            'scaling_suggestions': []
        }

        # Analyze growth trends
        if 'trends' in trends_7d:
            trends_data = trends_7d['trends']

            # Memory growth analysis
            if 'used_memory' in trends_data:
                memory_trend = trends_data['used_memory']
                memory_growth_7d = memory_trend['current'] - memory_trend['min']
                weekly_growth_mb = memory_growth_7d / 1024 / 1024

                capacity_analysis['growth_analysis']['memory'] = {
                    'weekly_growth_mb': weekly_growth_mb,
                    'trend_direction': memory_trend['trend_direction'],
                    'projected_monthly_growth_mb': weekly_growth_mb * 4.3  # 4.3 weeks in month
                }

                # Scaling suggestions based on growth
                if weekly_growth_mb > 100:  # More than 100MB growth per week
                    capacity_analysis['scaling_suggestions'].append(
                        f"High memory growth rate: {weekly_growth_mb:.1f}MB/week - "
                        f"consider increasing memory allocation"
                    )

        # Add general scaling suggestions
        if current_metrics.instantaneous_ops_per_sec > 10000:
            capacity_analysis['scaling_suggestions'].append(
                "High operations rate - consider read replicas for horizontal scaling"
            )

        if current_metrics.connected_clients > 5000:
            capacity_analysis['scaling_suggestions'].append(
                "High connection count - consider connection pooling optimization"
            )

        report = {
            'status': 'completed',
            'report_period': '7 days',
            'capacity_analysis': capacity_analysis,
            'redis_info': {
                'version': current_metrics.redis_version,
                'uptime_hours': current_metrics.uptime_in_seconds / 3600,
                'role': current_metrics.instance_role
            },
            'timestamp': timezone.now().isoformat()
        }

        logger.info("Redis capacity planning report generated successfully")
        return report

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Failed to generate Redis capacity report: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _send_performance_alerts(instance_name, alerts, metrics):
    """Send email notification for critical Redis performance alerts."""
    try:
        subject = f"[CRITICAL] Redis Performance Alert - {instance_name}"

        message_parts = [
            f"Critical Redis performance issues detected on instance: {instance_name}",
            "",
            f"Current Status:",
            f"- Memory Usage: {metrics.used_memory_human}",
            f"- Hit Ratio: {metrics.hit_ratio}%",
            f"- Operations/Second: {metrics.instantaneous_ops_per_sec}",
            f"- Connected Clients: {metrics.connected_clients}",
            f"- Fragmentation Ratio: {metrics.memory_fragmentation_ratio:.2f}",
            "",
            "Critical Alerts:"
        ]

        for alert in alerts:
            message_parts.extend([
                f"- {alert.message}",
                f"  Current: {alert.current_value}, Threshold: {alert.threshold_value}",
                f"  Recommendation: {alert.recommendation}",
                ""
            ])

        message_parts.extend([
            "Please investigate immediately to prevent service degradation.",
            f"Dashboard: {settings.SITE_URL}/admin/redis/dashboard/",
            f"Report generated at: {timezone.now()}"
        ])

        message = "\n".join(message_parts)

        mail_admins(subject, message, fail_silently=False)
        logger.info(f"Redis performance alert email sent for {instance_name}")

    except CACHE_EXCEPTIONS as e:
        logger.error(f"Failed to send Redis performance alert email: {e}")


def _send_trend_analysis_email(analysis_result):
    """Send email notification for significant performance trends."""
    try:
        subject = "[INFO] Redis Performance Trend Analysis"

        insights = analysis_result['insights']
        summary = analysis_result['trends_summary']

        message_parts = [
            f"Redis performance trend analysis completed:",
            "",
            f"Analysis Period: {analysis_result['hours_analyzed']} hours",
            f"Data Points: {analysis_result['data_points']}",
            "",
            "Key Insights:"
        ]

        for insight in insights:
            message_parts.append(f"- {insight}")

        if summary:
            message_parts.extend([
                "",
                "Performance Summary:",
                f"- Overall Health: {summary.get('overall_health', 'unknown')}",
                f"- Peak Ops/Sec: {summary.get('peak_ops_per_sec', 0)}",
                f"- Average Hit Ratio: {summary.get('avg_hit_ratio', 0):.1f}%",
                f"- Memory Growth: {summary.get('memory_growth_mb', 0):.1f}MB"
            ])

        message_parts.extend([
            "",
            f"Dashboard: {settings.SITE_URL}/admin/redis/dashboard/",
            f"Generated at: {timezone.now()}"
        ])

        message = "\n".join(message_parts)

        mail_admins(subject, message, fail_silently=False)
        logger.info("Redis trend analysis email sent successfully")

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Failed to send trend analysis email: {e}")


# Export public interface
__all__ = [
    'collect_redis_performance_metrics',
    'analyze_redis_performance_trends',
    'generate_redis_capacity_report'
]