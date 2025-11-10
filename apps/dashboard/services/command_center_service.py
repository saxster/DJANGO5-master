"""
Command Center Service - Real-time operational intelligence aggregation.

Aggregates data from 6 sources for unified command center view:
1. NOC Alerts (top critical alerts)
2. Device Health (devices at risk)
3. SLA Risks (tickets at risk of breach)
4. Attendance Anomalies (today's issues)
5. Active SOS (open emergencies)
6. Incomplete Tours (overdue patrols)

Following CLAUDE.md:
- Rule #7: Service methods <50 lines
- Rule #14: Query optimization with select_related/prefetch_related
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from typing import Dict, List
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.core.cache import cache
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)

# Cache TTL for summary stats (30 seconds)
SUMMARY_CACHE_TTL = 30


class CommandCenterService:
    """Service for real-time operational intelligence aggregation."""

    @classmethod
    def get_live_summary(cls, tenant_id: int) -> Dict:
        """
        Aggregate real-time operational data for command center.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary with:
                - critical_alerts: Top 10 alerts by priority
                - devices_at_risk: Devices with health <70
                - sla_at_risk: Tickets with breach probability >=0.7
                - attendance_anomalies: Today's late/no-show
                - active_sos: Open SOS alerts
                - incomplete_tours: Overdue tours
                - summary_stats: Aggregate counts

        Examples:
            >>> CommandCenterService.get_live_summary(tenant_id=1)
            {
                'critical_alerts': [...],
                'devices_at_risk': [...],
                'summary_stats': {'alerts_today': 45, ...}
            }
        """
        # Check cache first
        cache_key = f"command_center_summary:{tenant_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            logger.debug(
                "command_center_cache_hit",
                extra={'tenant_id': tenant_id}
            )
            return cached_data

        try:
            summary = {
                'critical_alerts': cls._get_critical_alerts(tenant_id),
                'devices_at_risk': cls._get_devices_at_risk(tenant_id),
                'sla_at_risk': cls._get_sla_at_risk(tenant_id),
                'attendance_anomalies': cls._get_attendance_anomalies(tenant_id),
                'active_sos': cls._get_active_sos(tenant_id),
                'incomplete_tours': cls._get_incomplete_tours(tenant_id),
                'summary_stats': cls._get_summary_stats(tenant_id),
                'last_updated': timezone.now().isoformat()
            }

            # Cache for 30 seconds
            cache.set(cache_key, summary, SUMMARY_CACHE_TTL)

            logger.info(
                "command_center_summary_generated",
                extra={
                    'tenant_id': tenant_id,
                    'alerts_count': len(summary['critical_alerts']),
                    'devices_at_risk_count': len(summary['devices_at_risk'])
                }
            )

            return summary

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "command_center_summary_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)},
                exc_info=True
            )
            raise

    @classmethod
    def _get_critical_alerts(cls, tenant_id: int) -> List[Dict]:
        """
        Get top 10 critical alerts by priority score.

        Uses existing AlertPriorityScorer if available, otherwise severity.
        """
        from apps.noc.models import Alert  # Assuming Alert model exists

        try:
            alerts = Alert.objects.filter(
                tenant_id=tenant_id,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).select_related('device', 'site', 'assigned_to').order_by(
                '-severity', '-created_at'
            )[:10]

            return [{
                'id': alert.id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'description': alert.description,
                'device_id': alert.device_id,
                'site_name': alert.site.name if alert.site else 'Unknown',
                'assigned_to': alert.assigned_to.fullname if alert.assigned_to else 'Unassigned',
                'created_at': alert.created_at.isoformat(),
                'priority_score': alert.other_data.get('ai_priority_score', 0) if alert.other_data else 0,
                'url': f"/noc/alerts/{alert.id}/"
            } for alert in alerts]

        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                "critical_alerts_retrieval_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)}
            )
            return []

    @classmethod
    def _get_devices_at_risk(cls, tenant_id: int) -> List[Dict]:
        """
        Get devices with health score <70.

        Health scores computed by DeviceHealthService.
        """
        from apps.mqtt.models import DeviceTelemetry
        from apps.monitoring.services.device_health_service import DeviceHealthService

        try:
            # Get devices with recent telemetry (last 24 hours)
            twenty_four_hours_ago = timezone.now() - timedelta(hours=24)

            recent_devices = DeviceTelemetry.objects.filter(
                tenant_id=tenant_id,
                timestamp__gte=twenty_four_hours_ago
            ).values('device_id').distinct()

            # Compute health scores and filter devices below threshold
            devices_at_risk = []

            for device_data in recent_devices:
                device_id = device_data['device_id']
                health_result = DeviceHealthService.compute_health_score(
                    device_id=device_id,
                    tenant_id=tenant_id
                )

                # Only include devices with health score below warning threshold
                if health_result['health_score'] < DeviceHealthService.HEALTH_WARNING:
                    devices_at_risk.append({
                        'device_id': device_id,
                        'health_score': health_result['health_score'],
                        'status': health_result['status'],
                        'components': health_result.get('components', {})
                    })

            return devices_at_risk

        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                "devices_at_risk_retrieval_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)}
            )
            return []

    @classmethod
    def _get_sla_at_risk(cls, tenant_id: int) -> List[Dict]:
        """
        Get tickets with SLA breach probability >=0.7.

        Uses existing SLABreachPredictor predictions stored in other_data.
        """
        from apps.y_helpdesk.models import Ticket

        try:
            tickets = Ticket.objects.filter(
                tenant_id=tenant_id,
                status__in=['OPEN', 'ASSIGNED'],
                sla_policy__isnull=False
            ).select_related('assigned_to', 'created_by')

            at_risk_tickets = []

            for ticket in tickets:
                if ticket.other_data and 'sla_predictions' in ticket.other_data:
                    predictions = ticket.other_data['sla_predictions']
                    if predictions:
                        latest_prediction = predictions[-1]
                        probability = latest_prediction.get('breach_probability', 0)
                        
                        if probability >= 0.7:
                            at_risk_tickets.append({
                                'id': ticket.id,
                                'title': ticket.title,
                                'priority': ticket.priority,
                                'breach_probability': probability,
                                'time_to_sla': cls._calculate_time_to_sla(ticket),
                                'assigned_to': ticket.assigned_to.fullname if ticket.assigned_to else 'Unassigned',
                                'created_at': ticket.created_at.isoformat(),
                                'url': f"/helpdesk/tickets/{ticket.id}/"
                            })

            return sorted(at_risk_tickets, key=lambda x: x['breach_probability'], reverse=True)[:10]

        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                "sla_at_risk_retrieval_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)}
            )
            return []

    @classmethod
    def _get_attendance_anomalies(cls, tenant_id: int) -> List[Dict]:
        """Get today's attendance anomalies (late, early, no-shows)."""
        from apps.attendance.models import Attendance

        try:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            attendance = Attendance.objects.filter(
                tenant_id=tenant_id,
                checkin__gte=today_start,
                checkin__lt=today_end
            ).select_related('people', 'location')

            anomalies = []

            for record in attendance:
                if record.other_data:
                    minutes_late = record.other_data.get('minutes_late', 0)
                    minutes_early = record.other_data.get('minutes_early', 0)

                    if minutes_late > 15:
                        anomalies.append({
                            'type': 'LATE_ARRIVAL',
                            'guard_name': record.people.fullname if record.people else 'Unknown',
                            'site_name': record.location.name if record.location else 'Unknown',
                            'minutes': minutes_late,
                            'timestamp': record.checkin.isoformat(),
                            'severity': 'HIGH' if minutes_late > 60 else 'MEDIUM'
                        })

                    if minutes_early > 15:
                        anomalies.append({
                            'type': 'EARLY_DEPARTURE',
                            'guard_name': record.people.fullname if record.people else 'Unknown',
                            'site_name': record.location.name if record.location else 'Unknown',
                            'minutes': minutes_early,
                            'timestamp': record.checkout.isoformat() if record.checkout else None,
                            'severity': 'MEDIUM'
                        })

            return sorted(anomalies, key=lambda x: x.get('minutes', 0), reverse=True)[:10]

        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                "attendance_anomalies_retrieval_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)}
            )
            return []

    @classmethod
    def _get_active_sos(cls, tenant_id: int) -> List[Dict]:
        """Get active (OPEN) SOS alerts."""
        from apps.attendance.models import SosAlert

        try:
            sos_alerts = SosAlert.objects.filter(
                tenant_id=tenant_id,
                status='OPEN'
            ).select_related('people', 'location').order_by('-timestamp')[:10]

            return [{
                'id': alert.id,
                'guard_name': alert.people.fullname if alert.people else 'Unknown',
                'location': f"{alert.latitude}, {alert.longitude}" if alert.latitude and alert.longitude else 'Unknown',
                'site_name': alert.location.name if alert.location else 'Unknown',
                'timestamp': alert.timestamp.isoformat(),
                'elapsed_minutes': (timezone.now() - alert.timestamp).total_seconds() / 60,
                'severity': 'CRITICAL',
                'url': f"/attendance/sos/{alert.id}/"
            } for alert in sos_alerts]

        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                "active_sos_retrieval_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)}
            )
            return []

    @classmethod
    def _get_incomplete_tours(cls, tenant_id: int) -> List[Dict]:
        """Get tours that are overdue (>30 minutes past scheduled end)."""
        from apps.scheduler.models import Tour

        try:
            now = timezone.now()
            overdue_threshold = now - timedelta(minutes=30)

            tours = Tour.objects.filter(
                tenant_id=tenant_id,
                status='IN_PROGRESS',
                scheduled_end__lt=overdue_threshold
            ).select_related('assigned_to', 'site').order_by('scheduled_end')[:10]

            return [{
                'id': tour.id,
                'tour_name': tour.name or f"Tour {tour.id}",
                'assigned_to': tour.assigned_to.fullname if tour.assigned_to else 'Unassigned',
                'site_name': tour.site.name if tour.site else 'Unknown',
                'scheduled_end': tour.scheduled_end.isoformat(),
                'overdue_minutes': (now - tour.scheduled_end).total_seconds() / 60,
                'completion_rate': tour.other_data.get('completion_rate', 0) if tour.other_data else 0,
                'url': f"/scheduler/tours/{tour.id}/"
            } for tour in tours]

        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                "incomplete_tours_retrieval_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)}
            )
            return []

    @classmethod
    def _get_summary_stats(cls, tenant_id: int) -> Dict:
        """Get aggregate statistics for summary cards."""
        from apps.noc.models import Alert
        from apps.y_helpdesk.models import Ticket
        from apps.mqtt.models import DeviceTelemetry
        from apps.attendance.models import Attendance

        try:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # Alerts today
            alerts_today = Alert.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=today_start,
                status__in=['OPEN', 'ACKNOWLEDGED']
            ).count()

            # Open tickets
            tickets_open = Ticket.objects.filter(
                tenant_id=tenant_id,
                status__in=['OPEN', 'ASSIGNED']
            ).count()

            # Devices offline (no telemetry in last hour)
            one_hour_ago = timezone.now() - timedelta(hours=1)
            devices_online = DeviceTelemetry.objects.filter(
                tenant_id=tenant_id,
                timestamp__gte=one_hour_ago
            ).values('device_id').distinct().count()

            # Guards on duty (checked in, not checked out)
            guards_on_duty = Attendance.objects.filter(
                tenant_id=tenant_id,
                checkin__gte=today_start,
                checkout__isnull=True
            ).count()

            return {
                'alerts_today': alerts_today,
                'tickets_open': tickets_open,
                'devices_online': devices_online,
                'guards_on_duty': guards_on_duty
            }

        except DATABASE_EXCEPTIONS as e:
            logger.warning(
                "summary_stats_retrieval_failed",
                extra={'tenant_id': tenant_id, 'error': str(e)}
            )
            return {
                'alerts_today': 0,
                'tickets_open': 0,
                'devices_online': 0,
                'guards_on_duty': 0
            }

    @classmethod
    def _calculate_time_to_sla(cls, ticket) -> str:
        """Calculate human-readable time to SLA deadline."""
        if not ticket.sla_deadline:
            return "No SLA"

        time_remaining = ticket.sla_deadline - timezone.now()
        
        if time_remaining.total_seconds() < 0:
            return "BREACHED"
        
        hours = time_remaining.total_seconds() / 3600
        
        if hours < 1:
            minutes = time_remaining.total_seconds() / 60
            return f"{int(minutes)} minutes"
        elif hours < 24:
            return f"{int(hours)} hours"
        else:
            days = hours / 24
            return f"{int(days)} days"

    @classmethod
    def invalidate_cache(cls, tenant_id: int) -> None:
        """
        Invalidate command center cache for a tenant.

        Call this when significant events occur (new alert, SOS, etc.)
        """
        cache_key = f"command_center_summary:{tenant_id}"
        cache.delete(cache_key)

        logger.info(
            "command_center_cache_invalidated",
            extra={'tenant_id': tenant_id}
        )
