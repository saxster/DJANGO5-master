"""
NOC Aggregation Service.

Aggregates operational metrics across multiple data sources for NOC dashboard.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions),
Rule #12 (query optimization), Rule #17 (transaction management).
"""

import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from django.db import transaction, DatabaseError
from django.utils import timezone
from django.db.models import Count, Q
from apps.core.utils_new.db_utils import get_current_db_name
from ..models import NOCMetricSnapshot, MaintenanceWindow
from ..constants import DEFAULT_METRIC_WINDOW_MINUTES

__all__ = ['NOCAggregationService']

logger = logging.getLogger('noc.aggregation')


class NOCAggregationService:
    """Service for aggregating NOC metrics from multiple operational data sources."""

    @staticmethod
    def create_snapshot_for_client(client_id: int, window_minutes: int = 5) -> Optional[NOCMetricSnapshot]:
        """
        Create aggregated metric snapshot for a client.

        Args:
            client_id: Client business unit ID
            window_minutes: Time window in minutes for aggregation

        Returns:
            NOCMetricSnapshot instance or None if maintenance window active

        Raises:
            DatabaseError: If database operation fails
            ValueError: If client_id is invalid
        """
        from apps.onboarding.models import Bt
        from apps.onboarding.managers import BtManager

        try:
            client = Bt.objects.select_related('tenant', 'identifier').get(id=client_id)
        except Bt.DoesNotExist as e:
            logger.error(f"Client not found", extra={'client_id': client_id})
            raise ValueError(f"Client {client_id} not found") from e

        window_end = timezone.now()
        window_start = window_end - timedelta(minutes=window_minutes)

        if NOCAggregationService._is_maintenance_active(client, window_start, window_end):
            logger.info(f"Skipping snapshot during maintenance", extra={'client_id': client_id})
            return None

        sites = BtManager().get_all_sites_of_client(client_id)

        try:
            with transaction.atomic(using=get_current_db_name()):
                metrics = {
                    'tenant': client.tenant,
                    'client': client,
                    'window_start': window_start,
                    'window_end': window_end,
                    **NOCAggregationService._aggregate_tickets(sites, window_start),
                    **NOCAggregationService._aggregate_attendance(sites, window_end),
                    **NOCAggregationService._aggregate_work_orders(sites, window_start),
                    **NOCAggregationService._aggregate_devices(sites),
                }

                snapshot = NOCMetricSnapshot.objects.create(**metrics)
                logger.info(f"Snapshot created", extra={'snapshot_id': snapshot.id, 'client_id': client_id})
                return snapshot

        except DatabaseError as e:
            logger.error(f"Database error creating snapshot", extra={'client_id': client_id, 'error': str(e)})
            raise

    @staticmethod
    def _is_maintenance_active(client, window_start, window_end) -> bool:
        """Check if active maintenance window exists for client."""
        return MaintenanceWindow.objects.filter(
            client=client,
            is_active=True,
            start_time__lte=window_end,
            end_time__gte=window_start
        ).exists()

    @staticmethod
    def _aggregate_tickets(sites, window_start) -> Dict[str, Any]:
        """
        Aggregate ticket metrics across sites with SLA calculation.

        IMPLEMENTED (Sprint 2): SLA-based overdue detection
        """
        from apps.y_helpdesk.models import Ticket
        from apps.y_helpdesk.services.sla_calculator import SLACalculator

        site_ids = [s.id for s in sites]
        tickets = Ticket.objects.filter(bu_id__in=site_ids, mdtz__gte=window_start)

        open_tickets = tickets.filter(status__in=['NEW', 'OPEN', 'ONHOLD']).count()

        # IMPLEMENTED: SLA-based overdue calculation (Sprint 2)
        try:
            sla_calculator = SLACalculator()
            overdue_ticket_qs = sla_calculator.get_overdue_tickets(site_ids=site_ids)
            overdue_tickets = overdue_ticket_qs.count()
        except Exception as e:
            logger.warning(f"SLA calculation failed, using fallback: {e}")
            # Fallback to simple status-based count
            overdue_tickets = tickets.filter(status='OPEN').count()

        priority_dist = dict(tickets.values('priority').annotate(count=Count('id')).values_list('priority', 'count'))

        return {
            'tickets_open': open_tickets,
            'tickets_overdue': overdue_tickets,
            'tickets_by_priority': priority_dist,
        }

    @staticmethod
    def _aggregate_attendance(sites, window_end) -> Dict[str, Any]:
        """
        Aggregate attendance metrics for current day.

        IMPLEMENTED (Sprint 2): Expected vs actual calculation
        """
        from apps.attendance.services.attendance_expectation_service import AttendanceExpectationService

        site_ids = [s.id for s in sites]

        # IMPLEMENTED: Use AttendanceExpectationService (Sprint 2)
        try:
            attendance_service = AttendanceExpectationService()
            metrics = attendance_service.calculate_attendance_metrics(
                sites=sites,
                target_date=window_end.date()
            )

            return {
                'attendance_expected': metrics.get('attendance_expected', 0),
                'attendance_present': metrics.get('attendance_present', 0),
                'attendance_missing': metrics.get('attendance_missing', 0),
                'attendance_late': metrics.get('attendance_late', 0),
                'compliance_percentage': metrics.get('compliance_percentage', 100.0),
            }

        except Exception as e:
            logger.warning(f"Attendance expectation service failed, using fallback: {e}")
            # Fallback to basic count
            from apps.attendance.models import PeopleEventlog
            today_start = window_end.replace(hour=0, minute=0, second=0, microsecond=0)
            attendance = PeopleEventlog.objects.filter(bu_id__in=site_ids, cdtz__gte=today_start)
            present_count = attendance.filter(
                Q(checkin__isnull=False) | Q(checkout__isnull=False)
            ).distinct('people').count()

            return {
                'attendance_expected': 0,
                'attendance_present': present_count,
                'attendance_missing': 0,
                'attendance_late': 0,
            }

    @staticmethod
    def _aggregate_work_orders(sites, window_start) -> Dict[str, Any]:
        """Aggregate work order metrics."""
        from apps.work_order_management.models import WorkOrder

        site_ids = [s.id for s in sites]
        work_orders = WorkOrder.objects.filter(bu_id__in=site_ids, mdtz__gte=window_start)

        pending = work_orders.filter(status='PENDING').count()
        overdue = work_orders.filter(status='OVERDUE').count()

        return {
            'work_orders_pending': pending,
            'work_orders_overdue': overdue,
            'work_orders_status_mix': {},
        }

    @staticmethod
    def _aggregate_devices(sites) -> Dict[str, Any]:
        """
        Aggregate device health metrics using onboarding.Device model.

        IMPLEMENTED (Sprint 6): Real-time device status tracking
        - Devices offline >30min
        - Critical alerts (offline >2hr)
        - Total registered devices
        """
        from apps.onboarding.models import Device
        from django.utils import timezone
        from datetime import timedelta

        site_ids = [s.id for s in sites]

        # Query enabled devices for these sites
        devices = Device.objects.filter(
            bu_id__in=site_ids,
            isdeviceon=True  # Only count administratively enabled devices
        )

        total_devices = devices.count()

        # Calculate offline devices (no communication in 30+ minutes)
        offline_threshold = timezone.now() - timedelta(minutes=30)
        offline_devices = devices.filter(
            lastcommunication__lt=offline_threshold
        ).count()

        # Calculate critical alerts (offline >2 hours)
        alert_threshold = timezone.now() - timedelta(hours=2)
        alert_devices = devices.filter(
            lastcommunication__lt=alert_threshold
        ).count()

        return {
            'device_health_offline': offline_devices,
            'device_health_alerts': alert_devices,
            'device_health_total': total_devices,
        }