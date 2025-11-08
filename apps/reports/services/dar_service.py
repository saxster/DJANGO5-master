"""
Daily Activity Report (DAR) Service.

Generates comprehensive shift reports for security operations:
- Shift summary (guards, hours, coverage)
- Incidents and events
- Tours completed with checkpoint details
- SOS alerts
- Device events (offline, battery warnings)
- Photos and media evidence
- Exceptions (late, early, no-shows)
- Supervisor notes

Industry-standard compliance requirement for security contracts.

Following CLAUDE.md:
- Rule #7: Service methods <50 lines
- Rule #11: Specific exception handling
- Rule #14: Query optimization with select_related/prefetch_related
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.db.models import Q, Count, Avg, Prefetch
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.attendance.models import Attendance, SosAlert, Geofence
from apps.activity.models import Job, DeviceEvent, Location, Asset
from apps.scheduler.models import Tour, Schedule
from apps.onboarding.models import Bt, Shift
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class DARService:
    """Service for generating Daily Activity Reports."""

    @classmethod
    def generate_dar(
        cls,
        site_id: int,
        shift_date: datetime.date,
        shift_type: str,
        supervisor_notes: Optional[str] = None
    ) -> Dict:
        """
        Generate comprehensive Daily Activity Report for a shift.

        Args:
            site_id: Site identifier (Location or Bt)
            shift_date: Date of shift
            shift_type: Shift type (DAY, NIGHT, EVENING)
            supervisor_notes: Optional supervisor comments

        Returns:
            Dictionary with report data for template rendering

        Raises:
            ValueError: If site not found or invalid date
        """
        try:
            # Get site details
            site = cls._get_site_details(site_id)

            # Get shift time boundaries
            shift_start, shift_end = cls._get_shift_boundaries(
                shift_date,
                shift_type,
                site
            )

            # Gather all sections
            report_data = {
                'site': site,
                'shift_date': shift_date,
                'shift_type': shift_type,
                'shift_start': shift_start,
                'shift_end': shift_end,
                'generated_at': timezone.now(),
                'supervisor_notes': supervisor_notes,

                # Main sections
                'summary': cls._get_shift_summary(site_id, shift_start, shift_end),
                'incidents': cls._get_incidents(site_id, shift_start, shift_end),
                'tours': cls._get_tours_completed(site_id, shift_start, shift_end),
                'sos_alerts': cls._get_sos_alerts(site_id, shift_start, shift_end),
                'device_events': cls._get_device_events(site_id, shift_start, shift_end),
                'media': cls._get_media_evidence(site_id, shift_start, shift_end),
                'exceptions': cls._get_attendance_exceptions(site_id, shift_start, shift_end),
            }

            logger.info(
                "dar_generated",
                extra={
                    'site_id': site_id,
                    'shift_date': shift_date.isoformat(),
                    'shift_type': shift_type,
                    'incidents_count': len(report_data['incidents']),
                    'tours_count': len(report_data['tours'])
                }
            )

            return report_data

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                "dar_generation_failed",
                extra={
                    'site_id': site_id,
                    'shift_date': shift_date.isoformat(),
                    'error': str(e)
                },
                exc_info=True
            )
            raise

    @classmethod
    def _get_site_details(cls, site_id: int) -> Dict:
        """Get site information."""
        from apps.activity.models import Location

        try:
            location = Location.objects.select_related('client').get(id=site_id)
            return {
                'id': location.id,
                'name': location.name,
                'address': location.address or '',
                'client_name': location.client.orgname if location.client else 'N/A',
                'client_logo': location.client.logo_url if hasattr(location.client, 'logo_url') else None
            }
        except Location.DoesNotExist:
            raise ValueError(f"Site {site_id} not found")

    @classmethod
    def _get_shift_boundaries(
        cls,
        shift_date: datetime.date,
        shift_type: str,
        site: Dict
    ) -> tuple:
        """
        Get shift start and end times.

        Args:
            shift_date: Date of shift
            shift_type: DAY, NIGHT, EVENING
            site: Site details dictionary

        Returns:
            Tuple of (start_datetime, end_datetime)
        """
        # Default shift times (can be overridden by site configuration)
        shift_times = {
            'DAY': (datetime.time(6, 0), datetime.time(14, 0)),
            'EVENING': (datetime.time(14, 0), datetime.time(22, 0)),
            'NIGHT': (datetime.time(22, 0), datetime.time(6, 0)),
        }

        start_time, end_time = shift_times.get(
            shift_type.upper(),
            (datetime.time(0, 0), datetime.time(23, 59))
        )

        shift_start = timezone.make_aware(
            datetime.combine(shift_date, start_time)
        )

        # Handle night shift crossing midnight
        if shift_type.upper() == 'NIGHT':
            next_day = shift_date + timedelta(days=1)
            shift_end = timezone.make_aware(
                datetime.combine(next_day, end_time)
            )
        else:
            shift_end = timezone.make_aware(
                datetime.combine(shift_date, end_time)
            )

        return shift_start, shift_end

    @classmethod
    def _get_shift_summary(
        cls,
        site_id: int,
        shift_start: datetime,
        shift_end: datetime
    ) -> Dict:
        """
        Get shift summary statistics.

        Returns:
            - guards_assigned: int
            - guards_present: int
            - total_hours_worked: float
            - coverage_percentage: float
            - posts_covered: int
            - posts_total: int
        """
        attendance_records = Attendance.objects.filter(
            location_id=site_id,
            checkin__gte=shift_start,
            checkin__lt=shift_end
        ).select_related('people')

        guards_assigned = attendance_records.count()
        guards_present = attendance_records.filter(
            checkout__isnull=False
        ).count()

        # Calculate total hours using database aggregation (avoid N+1 loop)
        from django.db.models import F, ExpressionWrapper, DurationField, Sum
        from django.db.models.functions import Extract
        
        total_seconds = attendance_records.filter(
            checkout__isnull=False
        ).annotate(
            duration=ExpressionWrapper(
                F('checkout') - F('checkin'),
                output_field=DurationField()
            )
        ).aggregate(
            total=Sum(Extract('duration', 'epoch'))
        )['total'] or 0
        
        total_hours = float(total_seconds) / 3600 if total_seconds else 0.0

        # Get post coverage (if post assignments exist in other_data)
        posts_covered = 0
        posts_total = 0  # Would come from site configuration

        coverage_percentage = (guards_present / guards_assigned * 100) if guards_assigned > 0 else 0

        return {
            'guards_assigned': guards_assigned,
            'guards_present': guards_present,
            'total_hours_worked': round(total_hours, 2),
            'average_hours_per_guard': round(total_hours / guards_present, 2) if guards_present > 0 else 0,
            'coverage_percentage': round(coverage_percentage, 2),
            'posts_covered': posts_covered,
            'posts_total': posts_total
        }

    @classmethod
    def _get_incidents(
        cls,
        site_id: int,
        shift_start: datetime,
        shift_end: datetime
    ) -> List[Dict]:
        """
        Get all incidents during shift.

        Includes:
        - DeviceEvents with severity >= MEDIUM
        - SOS alerts
        - Jobs marked as incidents
        """
        incidents = []

        # Device events
        device_events = DeviceEvent.objects.filter(
            location_id=site_id,
            timestamp__gte=shift_start,
            timestamp__lt=shift_end
        ).select_related('device', 'reported_by').order_by('timestamp')

        for event in device_events:
            severity = event.other_data.get('severity', 'LOW') if event.other_data else 'LOW'
            if severity in ['MEDIUM', 'HIGH', 'CRITICAL']:
                incidents.append({
                    'timestamp': event.timestamp,
                    'type': 'DEVICE_EVENT',
                    'severity': severity,
                    'description': event.description or f"Device: {event.device_id}",
                    'reported_by': event.reported_by.fullname if event.reported_by else 'System',
                    'status': event.status or 'OPEN'
                })

        # Jobs marked as incidents
        from apps.activity.models import Job
        incident_jobs = Job.objects.filter(
            location_id=site_id,
            created_date__gte=shift_start,
            created_date__lt=shift_end
        ).filter(
            Q(other_data__is_incident=True) | Q(jobtype__icontains='incident')
        ).select_related('created_by').order_by('created_date')

        for job in incident_jobs:
            incidents.append({
                'timestamp': job.created_date,
                'type': 'INCIDENT',
                'severity': job.other_data.get('severity', 'MEDIUM') if job.other_data else 'MEDIUM',
                'description': job.description,
                'reported_by': job.created_by.fullname if job.created_by else 'Unknown',
                'status': job.status or 'OPEN'
            })

        # Sort by timestamp
        incidents.sort(key=lambda x: x['timestamp'])

        return incidents

    @classmethod
    def _get_tours_completed(
        cls,
        site_id: int,
        shift_start: datetime,
        shift_end: datetime
    ) -> List[Dict]:
        """
        Get all tours completed during shift with checkpoint details.
        """
        tours = []

        from apps.scheduler.models import Tour
        completed_tours = Tour.objects.filter(
            site_id=site_id,
            completed_date__gte=shift_start,
            completed_date__lt=shift_end
        ).select_related('assigned_to').prefetch_related('checkpoints').order_by('completed_date')

        for tour in completed_tours:
            checkpoint_data = tour.other_data.get('checkpoints', []) if tour.other_data else []

            tours.append({
                'tour_id': tour.id,
                'tour_name': tour.name or f"Tour {tour.id}",
                'assigned_to': tour.assigned_to.fullname if tour.assigned_to else 'Unassigned',
                'start_time': tour.start_date,
                'end_time': tour.completed_date,
                'duration_minutes': (tour.completed_date - tour.start_date).total_seconds() / 60 if tour.completed_date and tour.start_date else 0,
                'checkpoints_total': len(checkpoint_data),
                'checkpoints_scanned': sum(1 for cp in checkpoint_data if cp.get('scanned')),
                'completion_rate': (sum(1 for cp in checkpoint_data if cp.get('scanned')) / len(checkpoint_data) * 100) if checkpoint_data else 0,
                'status': tour.status or 'COMPLETED'
            })

        return tours

    @classmethod
    def _get_sos_alerts(
        cls,
        site_id: int,
        shift_start: datetime,
        shift_end: datetime
    ) -> List[Dict]:
        """Get SOS alerts triggered during shift."""
        sos_alerts = SosAlert.objects.filter(
            location_id=site_id,
            timestamp__gte=shift_start,
            timestamp__lt=shift_end
        ).select_related('people').order_by('timestamp')

        return [{
            'timestamp': alert.timestamp,
            'guard_name': alert.people.fullname if alert.people else 'Unknown',
            'location': f"{alert.latitude}, {alert.longitude}" if alert.latitude and alert.longitude else 'N/A',
            'status': alert.status or 'OPEN',
            'response_time_minutes': (alert.resolved_at - alert.timestamp).total_seconds() / 60 if alert.resolved_at else None,
            'notes': alert.notes or ''
        } for alert in sos_alerts]

    @classmethod
    def _get_device_events(
        cls,
        site_id: int,
        shift_start: datetime,
        shift_end: datetime
    ) -> List[Dict]:
        """Get device-related events (offline, battery warnings, etc.)."""
        device_events = DeviceEvent.objects.filter(
            location_id=site_id,
            timestamp__gte=shift_start,
            timestamp__lt=shift_end,
            event_type__in=['OFFLINE', 'LOW_BATTERY', 'SIGNAL_WEAK', 'RECONNECTED']
        ).order_by('timestamp')

        return [{
            'timestamp': event.timestamp,
            'device_id': event.device_id,
            'event_type': event.event_type,
            'description': event.description or event.event_type.replace('_', ' ').title(),
            'severity': event.other_data.get('severity', 'LOW') if event.other_data else 'LOW'
        } for event in device_events]

    @classmethod
    def _get_media_evidence(
        cls,
        site_id: int,
        shift_start: datetime,
        shift_end: datetime
    ) -> List[Dict]:
        """Get photos and media uploaded during shift."""
        # This would query attachment/media models
        # For now, return empty list
        return []

    @classmethod
    def _get_attendance_exceptions(
        cls,
        site_id: int,
        shift_start: datetime,
        shift_end: datetime
    ) -> List[Dict]:
        """
        Get attendance exceptions (late, early, no-shows).
        """
        exceptions = []

        attendance_records = Attendance.objects.filter(
            location_id=site_id,
            checkin__gte=shift_start,
            checkin__lt=shift_end
        ).select_related('people')

        for record in attendance_records:
            # Check for late arrival (more than 15 minutes)
            if record.other_data and record.other_data.get('minutes_late', 0) > 15:
                exceptions.append({
                    'type': 'LATE_ARRIVAL',
                    'guard_name': record.people.fullname if record.people else 'Unknown',
                    'scheduled_time': record.other_data.get('scheduled_checkin'),
                    'actual_time': record.checkin,
                    'minutes_late': record.other_data.get('minutes_late'),
                    'reason': record.other_data.get('late_reason', 'No reason provided')
                })

            # Check for early departure
            if record.checkout and record.other_data and record.other_data.get('minutes_early', 0) > 15:
                exceptions.append({
                    'type': 'EARLY_DEPARTURE',
                    'guard_name': record.people.fullname if record.people else 'Unknown',
                    'scheduled_time': record.other_data.get('scheduled_checkout'),
                    'actual_time': record.checkout,
                    'minutes_early': record.other_data.get('minutes_early'),
                    'reason': record.other_data.get('early_reason', 'No reason provided')
                })

        # TODO: Check for no-shows (scheduled but no attendance record)

        return exceptions
