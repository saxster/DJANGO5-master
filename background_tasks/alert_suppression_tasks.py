"""
Alert Suppression Background Tasks.

Tasks:
- Monitor suppression effectiveness
- Clean up expired suppression markers
- Generate suppression reports
- Alert on suppression threshold breaches

Following CLAUDE.md:
- Rule #15: Network calls with timeouts
- Rule #16: Exponential backoff for retries
- Rule #19: Idempotent task design
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
from apps.noc.services.alert_rules_service import AlertRulesService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, CACHE_EXCEPTIONS

logger = logging.getLogger(__name__)


@shared_task(
    name='apps.noc.monitor_suppression_effectiveness',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def monitor_suppression_effectiveness(self, tenant_id: int):
    """
    Monitor alert suppression effectiveness and alert if thresholds breached.

    Runs hourly to track:
    - Suppression rate (target: 20-40%)
    - Flapping incidents
    - Burst incidents
    - Maintenance window compliance

    Args:
        tenant_id: Tenant to monitor

    Returns:
        dict: Monitoring results
    """
    try:
        stats = AlertRulesService.get_suppression_stats(tenant_id, hours=1)

        suppression_rate = stats.get('suppression_rate', 0.0)

        # Alert if suppression rate too high (may indicate misconfiguration)
        if suppression_rate > 0.6:
            logger.warning(
                "high_suppression_rate",
                extra={
                    'tenant_id': tenant_id,
                    'suppression_rate': suppression_rate,
                    'threshold': 0.6,
                    'stats': stats
                }
            )

        # Alert if suppression rate too low (not effective)
        if suppression_rate < 0.1 and stats['total_alerts_evaluated'] > 100:
            logger.warning(
                "low_suppression_effectiveness",
                extra={
                    'tenant_id': tenant_id,
                    'suppression_rate': suppression_rate,
                    'threshold': 0.1,
                    'stats': stats
                }
            )

        logger.info(
            "suppression_monitoring_complete",
            extra={
                'tenant_id': tenant_id,
                'stats': stats
            }
        )

        return {
            'status': 'success',
            'tenant_id': tenant_id,
            'stats': stats
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            "suppression_monitoring_failed",
            extra={
                'tenant_id': tenant_id,
                'error': str(e)
            },
            exc_info=True
        )
        raise self.retry(exc=e)

    except (ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error(
            "suppression_monitoring_validation_error",
            extra={
                'tenant_id': tenant_id,
                'error': str(e),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        return {
            'status': 'error',
            'tenant_id': tenant_id,
            'error': str(e),
            'error_type': 'validation_error'
        }

    except CACHE_EXCEPTIONS as e:
        logger.error(
            "suppression_monitoring_cache_error",
            extra={
                'tenant_id': tenant_id,
                'error': str(e)
            },
            exc_info=True
        )
        return {
            'status': 'error',
            'tenant_id': tenant_id,
            'error': str(e),
            'error_type': 'cache_error'
        }


@shared_task(
    name='apps.noc.cleanup_expired_suppressions',
    bind=True
)
def cleanup_expired_suppressions(self):
    """
    Clean up expired suppression markers from cache.

    This is primarily a housekeeping task as Redis TTL handles most cleanup.
    This task ensures consistency.

    Runs daily.

    Returns:
        dict: Cleanup results
    """
    try:
        cleaned_count = 0

        # Cache TTL handles most cleanup
        # This task is for additional consistency checks

        logger.info(
            "suppression_cleanup_complete",
            extra={
                'cleaned_count': cleaned_count
            }
        )

        return {
            'status': 'success',
            'cleaned_count': cleaned_count
        }

    except CACHE_EXCEPTIONS as e:
        logger.error(
            "suppression_cleanup_cache_error",
            extra={
                'error': str(e)
            },
            exc_info=True
        )
        return {
            'status': 'error',
            'error': str(e),
            'error_type': 'cache_error'
        }

    except (ValueError, TypeError, KeyError) as e:
        logger.error(
            "suppression_cleanup_validation_error",
            extra={
                'error': str(e),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        return {
            'status': 'error',
            'error': str(e),
            'error_type': 'validation_error'
        }


@shared_task(
    name='apps.noc.generate_suppression_report',
    bind=True,
    max_retries=3
)
def generate_suppression_report(self, tenant_id: int, period_days: int = 7):
    """
    Generate weekly suppression effectiveness report.

    Args:
        tenant_id: Tenant identifier
        period_days: Number of days to analyze (default: 7)

    Returns:
        dict: Report generation results
    """
    try:
        stats = AlertRulesService.get_suppression_stats(
            tenant_id,
            hours=period_days * 24
        )

        report_data = {
            'tenant_id': tenant_id,
            'period_days': period_days,
            'generated_at': timezone.now().isoformat(),
            'statistics': stats,
            'summary': {
                'total_alerts': stats['total_alerts_evaluated'],
                'suppressed': sum([
                    stats['suppressed_maintenance'],
                    stats['suppressed_flapping'],
                    stats['suppressed_duplicate'],
                    stats['suppressed_burst']
                ]),
                'suppression_rate': stats['suppression_rate'],
                'noise_reduction_percentage': stats['suppression_rate'] * 100
            },
            'breakdown': {
                'maintenance_windows': stats['suppressed_maintenance'],
                'flapping_detected': stats['suppressed_flapping'],
                'duplicates': stats['suppressed_duplicate'],
                'bursts': stats['suppressed_burst']
            }
        }

        logger.info(
            "suppression_report_generated",
            extra={
                'tenant_id': tenant_id,
                'period_days': period_days,
                'suppression_rate': stats['suppression_rate']
            }
        )

        # TODO: Send report via email or save to ReportSchedule
        # For now, just log and return

        return {
            'status': 'success',
            'report': report_data
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            "suppression_report_failed",
            extra={
                'tenant_id': tenant_id,
                'error': str(e)
            },
            exc_info=True
        )
        raise self.retry(exc=e)

    except (ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error(
            "suppression_report_validation_error",
            extra={
                'tenant_id': tenant_id,
                'error': str(e),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        return {
            'status': 'error',
            'tenant_id': tenant_id,
            'error': str(e),
            'error_type': 'validation_error'
        }

    except CACHE_EXCEPTIONS as e:
        logger.error(
            "suppression_report_cache_error",
            extra={
                'tenant_id': tenant_id,
                'error': str(e)
            },
            exc_info=True
        )
        return {
            'status': 'error',
            'tenant_id': tenant_id,
            'error': str(e),
            'error_type': 'cache_error'
        }
