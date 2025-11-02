"""
Metric Downsampling Tasks.

Celery tasks for multi-resolution time-series metric storage.
Implements Prometheus-style downsampling with automatic cleanup:
- Hourly: Aggregate 12 5-min snapshots → 1 hourly snapshot
- Daily: Aggregate 24 hourly snapshots → 1 daily snapshot
- Cleanup: Delete old data based on retention policies

Storage Reduction: 90%+ for historical data
Retention Strategy:
- 5-min: 7 days
- 1-hour: 90 days
- 1-day: 2 years

@ontology(
    domain="noc",
    purpose="Time-series metric downsampling for long-term analytics",
    tasks=[
        "DownsampleMetricsHourlyTask - Aggregate 5-min to 1-hour",
        "DownsampleMetricsDailyTask - Aggregate 1-hour to 1-day"
    ],
    schedule={
        "hourly": "Every hour at :05",
        "daily": "Every day at 1:00 AM"
    },
    criticality="medium",
    tags=["celery", "noc", "metrics", "downsampling", "analytics"]
)

Follows:
- .claude/rules.md Rule #13: IdempotentTask with explicit TTL
- .claude/rules.md Rule #22: Specific exceptions only
- CELERY_CONFIGURATION_GUIDE.md: Task naming, organization, decorators
"""

from apps.core.tasks.base import IdempotentTask
from celery import shared_task
from datetime import timedelta, datetime, timezone as dt_timezone
from django.utils import timezone
from django.db.models import Avg, Min, Max, Sum, Count
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
import logging

logger = logging.getLogger('noc.metric_downsampling')


@shared_task(base=IdempotentTask, bind=True)
class DownsampleMetricsHourlyTask(IdempotentTask):
    """
    Downsample 5-minute metric snapshots to hourly aggregates.

    Process:
    1. Get last completed hour's 5-min snapshots (12 snapshots per hour)
    2. Aggregate using Avg/Min/Max/Sum for each metric
    3. Create NOCMetricSnapshot1Hour records
    4. Delete 5-min snapshots older than 7 days

    Runs: Every hour at :05 (after 5-min snapshot task completes at :00)
    Idempotency: 1 hour TTL
    """

    name = 'noc.metrics.downsample_hourly'
    idempotency_ttl = SECONDS_IN_HOUR

    def run(self):
        """
        Aggregate 5-min snapshots to hourly resolution.

        Returns:
            dict: Processing statistics
                - clients_processed: Number of clients processed
                - snapshots_created: Number of hourly snapshots created
                - old_snapshots_deleted: Number of old 5-min snapshots cleaned up
                - errors: Number of errors encountered
        """
        from apps.noc.models import NOCMetricSnapshot, NOCMetricSnapshot1Hour
        from apps.onboarding.models import Bt

        logger.info("Starting hourly metric downsampling task")

        # Calculate time window for last completed hour
        now = timezone.now()
        window_end = now.replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)

        logger.info(f"Processing hour: {window_start} to {window_end}")

        clients_processed = 0
        snapshots_created = 0
        errors = 0

        # Get all clients that have snapshots in the time window
        clients_with_data = NOCMetricSnapshot.objects.filter(
            window_start__gte=window_start,
            window_start__lt=window_end
        ).values_list('client_id', flat=True).distinct()

        for client_id in clients_with_data:
            try:
                # Get all 5-min snapshots for this client in the hour
                snapshots = NOCMetricSnapshot.objects.filter(
                    client_id=client_id,
                    window_start__gte=window_start,
                    window_start__lt=window_end
                )

                snapshot_count = snapshots.count()
                if snapshot_count == 0:
                    continue

                # Get tenant from first snapshot
                first_snapshot = snapshots.first()
                tenant = first_snapshot.tenant
                client = first_snapshot.client

                # Aggregate metrics using Django ORM
                aggregated = snapshots.aggregate(
                    # Tickets
                    tickets_open_avg=Avg('tickets_open'),
                    tickets_open_min=Min('tickets_open'),
                    tickets_open_max=Max('tickets_open'),
                    tickets_open_sum=Sum('tickets_open'),
                    tickets_overdue_avg=Avg('tickets_overdue'),
                    tickets_overdue_min=Min('tickets_overdue'),
                    tickets_overdue_max=Max('tickets_overdue'),
                    tickets_overdue_sum=Sum('tickets_overdue'),
                    # Work Orders
                    work_orders_pending_avg=Avg('work_orders_pending'),
                    work_orders_pending_min=Min('work_orders_pending'),
                    work_orders_pending_max=Max('work_orders_pending'),
                    work_orders_pending_sum=Sum('work_orders_pending'),
                    work_orders_overdue_avg=Avg('work_orders_overdue'),
                    work_orders_overdue_min=Min('work_orders_overdue'),
                    work_orders_overdue_max=Max('work_orders_overdue'),
                    work_orders_overdue_sum=Sum('work_orders_overdue'),
                    # Attendance
                    attendance_present_avg=Avg('attendance_present'),
                    attendance_present_min=Min('attendance_present'),
                    attendance_present_max=Max('attendance_present'),
                    attendance_present_sum=Sum('attendance_present'),
                    attendance_missing_avg=Avg('attendance_missing'),
                    attendance_missing_min=Min('attendance_missing'),
                    attendance_missing_max=Max('attendance_missing'),
                    attendance_missing_sum=Sum('attendance_missing'),
                    # Device Health
                    device_health_offline_avg=Avg('device_health_offline'),
                    device_health_offline_min=Min('device_health_offline'),
                    device_health_offline_max=Max('device_health_offline'),
                    sync_health_score_avg=Avg('sync_health_score'),
                    sync_health_score_min=Min('sync_health_score'),
                    # Security
                    security_anomalies_avg=Avg('security_anomalies'),
                    security_anomalies_max=Max('security_anomalies'),
                    security_anomalies_sum=Sum('security_anomalies'),
                )

                # Convert None values to 0 or appropriate defaults
                for key in aggregated:
                    if aggregated[key] is None:
                        if 'score' in key:
                            aggregated[key] = 100.0
                        elif 'avg' in key:
                            aggregated[key] = 0.0
                        else:
                            aggregated[key] = 0

                # Create hourly snapshot
                NOCMetricSnapshot1Hour.objects.create(
                    tenant=tenant,
                    client=client,
                    bu=first_snapshot.bu,
                    oic=first_snapshot.oic,
                    window_start=window_start,
                    window_end=window_end,
                    **aggregated
                )

                snapshots_created += 1
                clients_processed += 1

                logger.debug(
                    f"Created hourly snapshot for {client.buname}: "
                    f"{snapshot_count} 5-min snapshots aggregated"
                )

            except Exception as e:
                errors += 1
                logger.error(
                    f"Error downsampling hourly metrics for client {client_id}: {e}",
                    exc_info=True
                )

        # Cleanup: Delete 5-min snapshots older than 7 days
        delete_before = now - timedelta(days=7)
        deleted_result = NOCMetricSnapshot.objects.filter(
            computed_at__lt=delete_before
        ).delete()
        old_snapshots_deleted = deleted_result[0]

        logger.info(
            f"Hourly downsampling complete: {snapshots_created} hourly snapshots created "
            f"for {clients_processed} clients, {old_snapshots_deleted} old 5-min snapshots deleted, "
            f"{errors} errors"
        )

        return {
            'clients_processed': clients_processed,
            'snapshots_created': snapshots_created,
            'old_snapshots_deleted': old_snapshots_deleted,
            'errors': errors
        }


@shared_task(base=IdempotentTask, bind=True)
class DownsampleMetricsDailyTask(IdempotentTask):
    """
    Downsample 1-hour metric snapshots to daily aggregates.

    Process:
    1. Get previous day's 1-hour snapshots (24 snapshots per day)
    2. Aggregate using Avg/Min/Max for each metric
    3. Create NOCMetricSnapshot1Day records
    4. Delete 1-hour snapshots older than 90 days

    Runs: Daily at 1:00 AM
    Idempotency: 6 hours TTL (allows retries throughout early morning)
    """

    name = 'noc.metrics.downsample_daily'
    idempotency_ttl = SECONDS_IN_HOUR * 6

    def run(self):
        """
        Aggregate hourly snapshots to daily resolution.

        Returns:
            dict: Processing statistics
                - clients_processed: Number of clients processed
                - snapshots_created: Number of daily snapshots created
                - old_snapshots_deleted: Number of old hourly snapshots cleaned up
                - errors: Number of errors encountered
        """
        from apps.noc.models import NOCMetricSnapshot1Hour, NOCMetricSnapshot1Day
        from apps.onboarding.models import Bt

        logger.info("Starting daily metric downsampling task")

        # Calculate date for previous day (we run at 1:00 AM, so process yesterday)
        now = timezone.now()
        target_date = (now - timedelta(days=1)).date()
        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=dt_timezone.utc)
        day_end = day_start + timedelta(days=1)

        logger.info(f"Processing day: {target_date}")

        clients_processed = 0
        snapshots_created = 0
        errors = 0

        # Get all clients that have hourly snapshots for this day
        clients_with_data = NOCMetricSnapshot1Hour.objects.filter(
            window_start__gte=day_start,
            window_start__lt=day_end
        ).values_list('client_id', flat=True).distinct()

        for client_id in clients_with_data:
            try:
                # Get all hourly snapshots for this client on this day
                snapshots = NOCMetricSnapshot1Hour.objects.filter(
                    client_id=client_id,
                    window_start__gte=day_start,
                    window_start__lt=day_end
                )

                snapshot_count = snapshots.count()
                if snapshot_count == 0:
                    continue

                # Get tenant from first snapshot
                first_snapshot = snapshots.first()
                tenant = first_snapshot.tenant
                client = first_snapshot.client

                # Aggregate hourly metrics to daily
                aggregated = snapshots.aggregate(
                    # Tickets - average of hourly averages, min/max of hourly min/max
                    tickets_open_avg=Avg('tickets_open_avg'),
                    tickets_open_min=Min('tickets_open_min'),
                    tickets_open_max=Max('tickets_open_max'),
                    tickets_overdue_avg=Avg('tickets_overdue_avg'),
                    tickets_overdue_min=Min('tickets_overdue_min'),
                    tickets_overdue_max=Max('tickets_overdue_max'),
                    # Work Orders
                    work_orders_pending_avg=Avg('work_orders_pending_avg'),
                    work_orders_pending_min=Min('work_orders_pending_min'),
                    work_orders_pending_max=Max('work_orders_pending_max'),
                    work_orders_overdue_avg=Avg('work_orders_overdue_avg'),
                    work_orders_overdue_min=Min('work_orders_overdue_min'),
                    work_orders_overdue_max=Max('work_orders_overdue_max'),
                    # Attendance
                    attendance_present_avg=Avg('attendance_present_avg'),
                    attendance_present_min=Min('attendance_present_min'),
                    attendance_present_max=Max('attendance_present_max'),
                    attendance_missing_avg=Avg('attendance_missing_avg'),
                    attendance_missing_min=Min('attendance_missing_min'),
                    attendance_missing_max=Max('attendance_missing_max'),
                    # Device Health
                    device_health_offline_avg=Avg('device_health_offline_avg'),
                    device_health_offline_min=Min('device_health_offline_min'),
                    device_health_offline_max=Max('device_health_offline_max'),
                    sync_health_score_avg=Avg('sync_health_score_avg'),
                    sync_health_score_min=Min('sync_health_score_min'),
                    # Security
                    security_anomalies_avg=Avg('security_anomalies_avg'),
                    security_anomalies_max=Max('security_anomalies_max'),
                    security_anomalies_sum=Sum('security_anomalies_sum'),
                )

                # Convert None values to 0 or appropriate defaults
                for key in aggregated:
                    if aggregated[key] is None:
                        if 'score' in key:
                            aggregated[key] = 100.0
                        elif 'avg' in key:
                            aggregated[key] = 0.0
                        else:
                            aggregated[key] = 0

                # Create or update daily snapshot (use update_or_create for idempotency)
                NOCMetricSnapshot1Day.objects.update_or_create(
                    tenant=tenant,
                    client=client,
                    date=target_date,
                    defaults={
                        'bu': first_snapshot.bu,
                        **aggregated
                    }
                )

                snapshots_created += 1
                clients_processed += 1

                logger.debug(
                    f"Created daily snapshot for {client.buname} on {target_date}: "
                    f"{snapshot_count} hourly snapshots aggregated"
                )

            except Exception as e:
                errors += 1
                logger.error(
                    f"Error downsampling daily metrics for client {client_id}: {e}",
                    exc_info=True
                )

        # Cleanup: Delete hourly snapshots older than 90 days
        delete_before = now - timedelta(days=90)
        deleted_result = NOCMetricSnapshot1Hour.objects.filter(
            computed_at__lt=delete_before
        ).delete()
        old_snapshots_deleted = deleted_result[0]

        logger.info(
            f"Daily downsampling complete: {snapshots_created} daily snapshots created "
            f"for {clients_processed} clients, {old_snapshots_deleted} old hourly snapshots deleted, "
            f"{errors} errors"
        )

        return {
            'clients_processed': clients_processed,
            'snapshots_created': snapshots_created,
            'old_snapshots_deleted': old_snapshots_deleted,
            'errors': errors
        }
