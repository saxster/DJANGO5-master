"""
Temporal Anomaly Detector

Detects time-based anomalies in attendance patterns.

Anomalies:
- Check-in at unusual hours (2 AM on weekend)
- Impossibly short rest periods between shifts
- Working excessive hours without breaks
- Inconsistent shift patterns
"""

from typing import Dict, Any, List
from django.utils import timezone
from datetime import timedelta
from apps.attendance.models import PeopleEventlog
import logging

logger = logging.getLogger(__name__)


class TemporalAnomalyDetector:
    """Detects time-based attendance anomalies"""

    # Business rules
    MINIMUM_REST_PERIOD_HOURS = 8  # Minimum hours between shifts
    MAXIMUM_SHIFT_HOURS = 12  # Maximum continuous work hours
    UNUSUAL_HOURS_START = 22  # 10 PM
    UNUSUAL_HOURS_END = 6  # 6 AM

    def __init__(self, employee):
        self.employee = employee

    def detect_anomalies(self, attendance_record) -> Dict[str, Any]:
        """
        Detect temporal anomalies.

        Returns:
            Dict with detected anomalies and risk score
        """
        anomalies = []

        # Check unusual hours
        if self._is_unusual_hour(attendance_record):
            anomalies.append({
                'type': 'unusual_hour',
                'severity': 'medium',
                'description': f'Check-in at unusual hour: {attendance_record.punchintime.hour}:00',
                'score': 0.5,
            })

        # Check rest period
        rest_anomaly = self._check_rest_period(attendance_record)
        if rest_anomaly:
            anomalies.append(rest_anomaly)

        # Check excessive hours
        if attendance_record.duration and attendance_record.duration > self.MAXIMUM_SHIFT_HOURS * 60:
            anomalies.append({
                'type': 'excessive_hours',
                'severity': 'high',
                'description': f'Shift duration {attendance_record.duration / 60:.1f} hours (max: {self.MAXIMUM_SHIFT_HOURS})',
                'score': 0.7,
            })

        # Check weekend work (if not typical)
        if attendance_record.datefor and attendance_record.datefor.isoweekday() in [6, 7]:
            # Check if weekend work is typical for this employee
            from apps.attendance.models.user_behavior_profile import UserBehaviorProfile
            try:
                profile = UserBehaviorProfile.objects.get(employee=self.employee)
                if 6 not in profile.typical_work_days and 7 not in profile.typical_work_days:
                    anomalies.append({
                        'type': 'unusual_weekend_work',
                        'severity': 'low',
                        'description': f'Working on weekend: {attendance_record.datefor.strftime("%A")}',
                        'score': 0.3,
                    })
            except UserBehaviorProfile.DoesNotExist:
                pass

        # Calculate overall score
        total_score = sum(a['score'] for a in anomalies) if anomalies else 0.0

        return {
            'anomalies': anomalies,
            'temporal_score': min(total_score, 1.0),
            'count': len(anomalies),
        }

    def _is_unusual_hour(self, record) -> bool:
        """Check if check-in is during unusual hours"""
        if not record.punchintime:
            return False

        hour = record.punchintime.hour
        return self.UNUSUAL_HOURS_START <= hour or hour < self.UNUSUAL_HOURS_END

    def _check_rest_period(self, record) -> Optional[Dict[str, Any]]:
        """Check if employee had sufficient rest between shifts"""
        if not record.punchintime:
            return None

        # Get previous shift for this employee
        previous = PeopleEventlog.objects.filter(
            people=self.employee,
            punchouttime__isnull=False,
            punchouttime__lt=record.punchintime
        ).order_by('-punchouttime').first()

        if not previous:
            return None

        # Calculate rest period
        rest_period = record.punchintime - previous.punchouttime
        rest_hours = rest_period.total_seconds() / 3600

        if rest_hours < self.MINIMUM_REST_PERIOD_HOURS:
            return {
                'type': 'insufficient_rest',
                'severity': 'high',
                'description': f'Only {rest_hours:.1f} hours rest between shifts (minimum: {self.MINIMUM_REST_PERIOD_HOURS})',
                'score': 0.8,
            }

        return None
