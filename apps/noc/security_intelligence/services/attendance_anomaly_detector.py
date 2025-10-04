"""
Attendance Anomaly Detector Service.

Core detection logic for attendance-related security anomalies.
Detects wrong person, unauthorized access, impossible shifts, overtime violations.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Sum, F
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance

logger = logging.getLogger('noc.security_intelligence')


class AttendanceAnomalyDetector:
    """Detects attendance-related security anomalies."""

    def __init__(self, config):
        """
        Initialize detector with configuration.

        Args:
            config: SecurityAnomalyConfig instance
        """
        self.config = config

    def detect_wrong_person(self, attendance_event):
        """
        Detect if wrong person marked attendance.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Anomaly details or None
        """
        from apps.noc.security_intelligence.models import ShiftScheduleCache

        try:
            scheduled = ShiftScheduleCache.get_scheduled_person(
                tenant=attendance_event.tenant,
                site=attendance_event.bu,
                date=attendance_event.datefor
            )

            if scheduled and scheduled.id != attendance_event.people.id:
                return {
                    'anomaly_type': 'WRONG_PERSON',
                    'severity': 'HIGH',
                    'expected_person': scheduled,
                    'actual_person': attendance_event.people,
                    'confidence_score': 0.95,
                    'evidence_data': {
                        'expected_id': scheduled.id,
                        'expected_name': scheduled.peoplename,
                        'actual_id': attendance_event.people.id,
                        'actual_name': attendance_event.people.peoplename,
                    }
                }
        except (ValueError, AttributeError) as e:
            logger.error(f"Wrong person detection error: {e}", exc_info=True)

        return None

    def detect_unauthorized_site_access(self, attendance_event):
        """
        Detect unauthorized site access.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Anomaly details or None
        """
        try:
            from apps.peoples.models import People

            person = attendance_event.people
            site = attendance_event.bu

            if not hasattr(person, 'organizational') or person.organizational.bu_id != site.id:
                return {
                    'anomaly_type': 'UNAUTHORIZED_SITE',
                    'severity': self.config.unauthorized_access_severity,
                    'confidence_score': 0.90,
                    'evidence_data': {
                        'person_id': person.id,
                        'person_name': person.peoplename,
                        'site_id': site.id,
                        'site_name': site.name,
                        'assigned_site_id': person.organizational.bu_id if hasattr(person, 'organizational') else None,
                    }
                }
        except (ValueError, AttributeError) as e:
            logger.error(f"Unauthorized access detection error: {e}", exc_info=True)

        return None

    def detect_impossible_back_to_back(self, attendance_event):
        """
        Detect impossible consecutive shifts.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Anomaly details or None
        """
        from apps.attendance.models import PeopleEventlog

        try:
            previous_shift = PeopleEventlog.objects.filter(
                people=attendance_event.people,
                datefor__lt=attendance_event.datefor,
                punchouttime__isnull=False
            ).order_by('-datefor').first()

            if previous_shift and previous_shift.bu_id != attendance_event.bu_id:
                if previous_shift.endlocation and attendance_event.startlocation:
                    distance_m = previous_shift.endlocation.distance(attendance_event.startlocation)
                    distance_km = distance_m / 1000

                    time_between = (attendance_event.punchintime - previous_shift.punchouttime).total_seconds() / 60
                    required_time = (distance_km / self.config.max_travel_speed_kmh) * 60

                    if time_between < required_time:
                        return {
                            'anomaly_type': 'IMPOSSIBLE_SHIFTS',
                            'severity': 'CRITICAL',
                            'distance_km': distance_km,
                            'time_available_minutes': time_between,
                            'time_required_minutes': required_time,
                            'confidence_score': 0.85,
                            'evidence_data': {
                                'previous_site': previous_shift.bu.name,
                                'current_site': attendance_event.bu.name,
                                'travel_speed_required_kmh': (distance_km / time_between) * 60 if time_between > 0 else 0,
                            }
                        }
        except (ValueError, AttributeError) as e:
            logger.error(f"Impossible shifts detection error: {e}", exc_info=True)

        return None

    def detect_overtime_violation(self, attendance_event):
        """
        Detect overtime violations.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Anomaly details or None
        """
        from apps.attendance.models import PeopleEventlog

        try:
            last_24h = timezone.now() - timedelta(hours=24)

            work_duration = PeopleEventlog.objects.filter(
                people=attendance_event.people,
                datefor__gte=last_24h.date(),
                punchintime__isnull=False,
                punchouttime__isnull=False
            ).aggregate(
                total_seconds=Sum(F('punchouttime') - F('punchintime'))
            )['total_seconds']

            if work_duration:
                work_hours = work_duration.total_seconds() / 3600

                if work_hours > self.config.max_continuous_work_hours:
                    return {
                        'anomaly_type': 'OVERTIME_VIOLATION',
                        'severity': 'HIGH',
                        'continuous_work_hours': work_hours,
                        'confidence_score': 0.98,
                        'evidence_data': {
                            'max_allowed_hours': self.config.max_continuous_work_hours,
                            'exceeded_by_hours': work_hours - self.config.max_continuous_work_hours,
                        }
                    }
        except (ValueError, AttributeError) as e:
            logger.error(f"Overtime detection error: {e}", exc_info=True)

        return None