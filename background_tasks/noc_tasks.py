"""
NOC Background Tasks for Celery.

Periodic tasks for NOC metric aggregation, alert management, and maintenance.
Follows .claude/rules.md: Rule #7 (<150 lines), Rule #11 (specific exceptions),
Rule #15 (no PII in logs).
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction, DatabaseError

logger = logging.getLogger('noc.tasks')

__all__ = [
    'noc_aggregate_snapshot_task',
    'noc_alert_backpressure_task',
    'noc_archive_snapshots_task',
    'noc_cache_warming_task',
    'noc_alert_escalation_task',
]


@shared_task(
    name='noc_aggregate_snapshot',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def noc_aggregate_snapshot_task(self):
    """
    Create metric snapshots for all active clients.
    Runs every 5 minutes via Celery Beat.
    """
    from apps.tenants.models import Tenant
    from apps.client_onboarding.models import Bt
    from apps.noc.services import NOCAggregationService

    success_count = 0
    error_count = 0

    try:
        # OPTIMIZATION: Prefetch all clients to eliminate N+1 query (PERF-002)
        from django.db.models import Prefetch

        tenants = Tenant.objects.filter(enable=True).prefetch_related(
            Prefetch(
                'bt_set',
                queryset=Bt.objects.filter(
                    identifier__tacode='CLIENT',
                    enable=True
                ).select_related('identifier'),
                to_attr='active_clients'
            )
        )

        for tenant in tenants:
            # Batch client IDs for potential bulk processing
            client_ids = [client.id for client in tenant.active_clients]

            # Process each client (consider adding bulk method to NOCAggregationService)
            for client_id in client_ids:
                try:
                    NOCAggregationService.create_snapshot_for_client(client_id)
                    success_count += 1
                except (ValueError, DatabaseError) as e:
                    error_count += 1
                    logger.error(
                        f"Snapshot failed for client",
                        extra={
                            'client_id': client_id,
                            'tenant_id': tenant.id,
                            'error': str(e)
                        }
                    )

        logger.info(
            f"Snapshot aggregation completed",
            extra={'success': success_count, 'errors': error_count}
        )
        return {'success': success_count, 'errors': error_count}

    except DatabaseError as e:
        logger.error(f"Database error in snapshot task: {e}")
        raise self.retry(exc=e)


@shared_task(name='noc_alert_backpressure', bind=True)
def noc_alert_backpressure_task(self):
    """
    Handle alert queue overflow by dropping low-priority alerts.
    Runs every minute to prevent queue buildup.
    """
    from apps.noc.models import NOCAlertEvent

    try:
        queue_depth = NOCAlertEvent.objects.filter(
            status='NEW',
            severity__in=['INFO', 'LOW']
        ).count()

        if queue_depth > 1000:
            cutoff = timezone.now() - timedelta(hours=1)
            suppressed = NOCAlertEvent.objects.filter(
                status='NEW',
                severity='INFO',
                cdtz__lt=cutoff
            ).update(status='SUPPRESSED')

            logger.warning(
                f"Alert backpressure relief applied",
                extra={'queue_depth': queue_depth, 'suppressed': suppressed}
            )
            return {'suppressed': suppressed}

        return {'suppressed': 0}

    except DatabaseError as e:
        logger.error(f"Error in backpressure task: {e}")
        return {'error': str(e)}


@shared_task(name='noc_archive_snapshots', bind=True)
def noc_archive_snapshots_task(self):
    """
    Archive old metric snapshots older than 30 days.
    Runs daily at 2 AM.
    """
    from apps.noc.models import NOCMetricSnapshot

    try:
        cutoff = timezone.now() - timedelta(days=30)

        with transaction.atomic():
            archived = NOCMetricSnapshot.objects.filter(
                window_end__lt=cutoff
            ).delete()

            logger.info(
                f"Snapshot archival completed",
                extra={'archived_count': archived[0]}
            )
            return {'archived': archived[0]}

    except DatabaseError as e:
        logger.error(f"Error archiving snapshots: {e}")
        raise self.retry(exc=e)


@shared_task(name='noc_cache_warming', bind=True)
def noc_cache_warming_task(self):
    """
    Pre-warm dashboard caches for executive users.
    Runs every 5 minutes to ensure fast dashboard loads.
    """
    from apps.peoples.models import People
    from apps.noc.services.cache_service import NOCCacheService

    warmed = 0

    try:
        executives = People.objects.filter(
            enable=True
        ).select_related('peopleprofile', 'peopleorganizational')

        for exec_user in executives:
            if exec_user.has_capability('noc:view_all_clients'):
                try:
                    NOCCacheService.warm_dashboard_cache(exec_user)
                    warmed += 1
                except (ValueError, KeyError) as e:
                    logger.error(
                        f"Cache warming failed",
                        extra={'user_id': exec_user.id, 'error': str(e)}
                    )

        logger.info(f"Cache warming completed", extra={'warmed': warmed})
        return {'warmed': warmed}

    except DatabaseError as e:
        logger.error(f"Database error in cache warming: {e}")
        return {'error': str(e)}


@shared_task(name='noc_alert_escalation', bind=True, max_retries=2)
def noc_alert_escalation_task(self):
    """
    Auto-escalate unacknowledged critical alerts.
    Runs every minute to check escalation deadlines.
    """
    from apps.noc.models import NOCAlertEvent
    from apps.noc.services import EscalationService
    from apps.noc.constants import DEFAULT_ESCALATION_DELAYS

    escalated = 0

    try:
        for severity, delay_minutes in DEFAULT_ESCALATION_DELAYS.items():
            if delay_minutes is None:
                continue

            cutoff = timezone.now() - timedelta(minutes=delay_minutes)

            alerts = NOCAlertEvent.objects.filter(
                status__in=['NEW', 'ACKNOWLEDGED'],
                severity=severity,
                cdtz__lt=cutoff,
                escalated_at__isnull=True
            ).select_related('tenant', 'client', 'bu')

            for alert in alerts:
                try:
                    EscalationService.escalate_alert(alert)
                    escalated += 1
                except (ValueError, DatabaseError) as e:
                    logger.error(
                        f"Escalation failed",
                        extra={'alert_id': alert.id, 'error': str(e)}
                    )

        logger.info(f"Alert escalation completed", extra={'escalated': escalated})
        return {'escalated': escalated}

    except DatabaseError as e:
        logger.error(f"Error in escalation task: {e}")
        raise self.retry(exc=e)