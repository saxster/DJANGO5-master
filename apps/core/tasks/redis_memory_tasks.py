"""
Celery tasks for Redis memory management and optimization.

These tasks handle automated Redis memory monitoring, optimization,
and alerting for the enterprise Django platform.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.core.mail import mail_admins
from django.conf import settings
from apps.core.services.redis_memory_manager import redis_memory_manager

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='maintenance',
    priority=4
)
def monitor_redis_memory(self):
    """
    Monitor Redis memory usage and generate alerts if needed.

    This task runs regularly to check Redis memory health and
    send notifications for critical issues.
    """
    try:
        # Get memory statistics
        stats = redis_memory_manager.get_memory_stats()

        if not stats:
            logger.error("Unable to retrieve Redis memory statistics")
            return {
                'status': 'error',
                'message': 'Failed to connect to Redis',
                'timestamp': timezone.now().isoformat()
            }

        # Check memory health
        alerts = redis_memory_manager.check_memory_health()

        result = {
            'status': 'completed',
            'timestamp': timezone.now().isoformat(),
            'memory_stats': {
                'used_memory_human': stats.used_memory_human,
                'memory_fragmentation_ratio': stats.memory_fragmentation_ratio,
                'hit_ratio': stats.hit_ratio,
                'evicted_keys': stats.evicted_keys
            },
            'alerts_count': len(alerts),
            'alerts': []
        }

        # Process alerts
        critical_alerts = []
        for alert in alerts:
            alert_data = {
                'level': alert.level,
                'message': alert.message,
                'current_usage': alert.current_usage,
                'recommended_action': alert.recommended_action
            }
            result['alerts'].append(alert_data)

            # Collect critical/emergency alerts for notification
            if alert.level in ['critical', 'emergency']:
                critical_alerts.append(alert)

        # Send notifications for critical alerts
        if critical_alerts and getattr(settings, 'REDIS_MEMORY_ALERTS_ENABLED', True):
            _send_memory_alert_email(critical_alerts, stats)

        # Trigger automatic optimization for emergency situations
        if any(alert.level == 'emergency' for alert in alerts):
            logger.warning("Emergency Redis memory situation detected - triggering optimization")
            optimize_redis_memory.apply_async(
                kwargs={'force': True},
                queue='maintenance',
                priority=8
            )

        logger.info(f"Redis memory monitoring completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Redis memory monitoring failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
    queue='maintenance',
    priority=6
)
def optimize_redis_memory(self, force=False, alert_threshold=85.0):
    """
    Optimize Redis memory usage by cleaning up old/unnecessary data.

    Args:
        force (bool): Force optimization even if recently performed
        alert_threshold (float): Memory usage threshold to trigger optimization
    """
    try:
        # Get current memory stats
        stats = redis_memory_manager.get_memory_stats()

        if not stats:
            logger.error("Unable to retrieve Redis memory statistics for optimization")
            return {
                'status': 'error',
                'message': 'Failed to connect to Redis',
                'timestamp': timezone.now().isoformat()
            }

        # Calculate current usage
        if stats.maxmemory > 0:
            usage_percentage = (stats.used_memory / stats.maxmemory) * 100
        else:
            import psutil
            system_memory = psutil.virtual_memory().total
            usage_percentage = (stats.used_memory / system_memory) * 100

        # Check if optimization is needed
        if not force and usage_percentage < alert_threshold:
            return {
                'status': 'skipped',
                'message': f'Memory usage at {usage_percentage:.1f}% - below threshold {alert_threshold}%',
                'timestamp': timezone.now().isoformat()
            }

        # Perform optimization
        logger.info(f"Starting Redis memory optimization - usage at {usage_percentage:.1f}%")
        optimization_results = redis_memory_manager.optimize_memory_usage(force=force)

        result = {
            'status': 'completed',
            'timestamp': timezone.now().isoformat(),
            'initial_usage_percentage': usage_percentage,
            'optimization_results': optimization_results
        }

        # Log results
        if optimization_results['status'] == 'completed':
            keys_cleaned = optimization_results['keys_cleaned']
            memory_freed = optimization_results.get('memory_freed', 0)
            logger.info(
                f"Redis memory optimization completed: "
                f"{keys_cleaned} keys cleaned, "
                f"{memory_freed / (1024 * 1024):.1f} MB freed"
            )
        else:
            logger.warning(f"Redis memory optimization status: {optimization_results['status']}")

        return result

    except Exception as exc:
        logger.error(f"Redis memory optimization failed: {exc}")
        # Limited retries for optimization tasks
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300)  # 5 minute delay
        else:
            # Send alert about failed optimization
            _send_optimization_failure_email(str(exc))
            raise


@shared_task(queue='maintenance', priority=5)
def generate_redis_memory_report():
    """
    Generate a comprehensive Redis memory usage report.

    This task creates detailed reports for monitoring and capacity planning.
    """
    try:
        # Get comprehensive statistics
        stats = redis_memory_manager.get_memory_stats()

        if not stats:
            logger.error("Unable to generate Redis memory report - connection failed")
            return {'status': 'error', 'message': 'Redis connection failed'}

        # Get health check results
        alerts = redis_memory_manager.check_memory_health()
        recommendations = redis_memory_manager.get_optimization_recommendations()

        # Calculate usage percentage
        if stats.maxmemory > 0:
            usage_percentage = (stats.used_memory / stats.maxmemory) * 100
        else:
            import psutil
            system_memory = psutil.virtual_memory().total
            usage_percentage = (stats.used_memory / system_memory) * 100

        report = {
            'timestamp': timezone.now().isoformat(),
            'memory_overview': {
                'used_memory': stats.used_memory,
                'used_memory_human': stats.used_memory_human,
                'usage_percentage': round(usage_percentage, 2),
                'maxmemory': stats.maxmemory,
                'maxmemory_human': stats.maxmemory_human,
                'peak_memory': stats.used_memory_peak,
                'peak_memory_human': stats.used_memory_peak_human
            },
            'performance_metrics': {
                'fragmentation_ratio': stats.memory_fragmentation_ratio,
                'hit_ratio': stats.hit_ratio,
                'total_hits': stats.keyspace_hits,
                'total_misses': stats.keyspace_misses,
                'evicted_keys': stats.evicted_keys,
                'expired_keys': stats.expired_keys
            },
            'health_status': {
                'alerts_count': len(alerts),
                'critical_alerts': len([a for a in alerts if a.level in ['critical', 'emergency']]),
                'warnings': len([a for a in alerts if a.level == 'warning'])
            },
            'recommendations': recommendations
        }

        logger.info("Redis memory report generated successfully")
        return report

    except Exception as e:
        logger.error(f"Failed to generate Redis memory report: {e}")
        return {'status': 'error', 'message': str(e)}


def _send_memory_alert_email(alerts, stats):
    """Send email notification for critical Redis memory alerts."""
    try:
        subject = f"[CRITICAL] Redis Memory Alert - {len(alerts)} issues detected"

        message_parts = [
            "Critical Redis memory issues detected:",
            "",
            f"Current Memory Usage: {stats.used_memory_human}",
            f"Fragmentation Ratio: {stats.memory_fragmentation_ratio:.2f}",
            f"Cache Hit Ratio: {stats.hit_ratio}%",
            "",
            "Alerts:"
        ]

        for alert in alerts:
            message_parts.extend([
                f"- [{alert.level.upper()}] {alert.message}",
                f"  Recommended Action: {alert.recommended_action}",
                ""
            ])

        message_parts.extend([
            "Please take immediate action to prevent service degradation.",
            f"Report generated at: {timezone.now()}"
        ])

        message = "\n".join(message_parts)

        mail_admins(subject, message, fail_silently=False)
        logger.info("Redis memory alert email sent successfully")

    except Exception as e:
        logger.error(f"Failed to send Redis memory alert email: {e}")


def _send_optimization_failure_email(error_message):
    """Send email notification for failed Redis optimization."""
    try:
        subject = "[ERROR] Redis Memory Optimization Failed"

        message = f"""
Redis memory optimization task failed with the following error:

Error: {error_message}

Please investigate and manually run optimization if needed:
python manage.py optimize_redis_memory --force

Generated at: {timezone.now()}
"""

        mail_admins(subject, message, fail_silently=False)
        logger.info("Redis optimization failure email sent successfully")

    except Exception as e:
        logger.error(f"Failed to send optimization failure email: {e}")


# Export public interface
__all__ = [
    'monitor_redis_memory',
    'optimize_redis_memory',
    'generate_redis_memory_report'
]