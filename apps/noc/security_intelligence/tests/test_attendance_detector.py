"""
Unit Tests for Attendance Anomaly Detector.

Tests all anomaly detection methods for attendance-related security issues.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.gis.geos import Point


@pytest.mark.django_db
class TestAttendanceAnomalyDetector:
    """Test attendance anomaly detection methods."""

    def test_detect_wrong_person(self, security_config, attendance_event, other_person):
        """Test detection of wrong person at site."""
        from apps.noc.security_intelligence.services import AttendanceAnomalyDetector
        from apps.noc.security_intelligence.models import ShiftScheduleCache

        ShiftScheduleCache.objects.create(
            tenant=attendance_event.tenant,
            person=other_person,
            site=attendance_event.bu,
            shift_date=attendance_event.datefor,
            scheduled_start=attendance_event.punchintime,
            scheduled_end=attendance_event.punchintime + timedelta(hours=8),
            cache_valid_until=timezone.now() + timedelta(days=1)
        )

        detector = AttendanceAnomalyDetector(security_config)
        result = detector.detect_wrong_person(attendance_event)

        assert result is not None
        assert result['anomaly_type'] == 'WRONG_PERSON'
        assert result['severity'] == 'HIGH'
        assert result['expected_person'] == other_person
        assert result['actual_person'] == attendance_event.people
        assert result['confidence_score'] >= 0.9

    def test_detect_unauthorized_site_access(self, security_config, attendance_event):
        """Test detection of unauthorized site access."""
        from apps.noc.security_intelligence.services import AttendanceAnomalyDetector

        detector = AttendanceAnomalyDetector(security_config)
        result = detector.detect_unauthorized_site_access(attendance_event)

        assert result is not None
        assert result['anomaly_type'] == 'UNAUTHORIZED_SITE'
        assert result['severity'] == 'CRITICAL'

    def test_detect_impossible_back_to_back(self, security_config, attendance_event, site_bt):
        """Test detection of impossible consecutive shifts."""
        from apps.noc.security_intelligence.services import AttendanceAnomalyDetector
        from apps.attendance.models import PeopleEventlog
        from apps.onboarding.models import Bt

        distant_site = Bt.objects.create(
            tenant=attendance_event.tenant,
            name='Distant Site',
            bttype='SITE',
            gpslocation=Point(80.0, 13.0),  # ~250km away
            enable=True
        )

        previous_shift = PeopleEventlog.objects.create(
            tenant=attendance_event.tenant,
            people=attendance_event.people,
            bu=distant_site,
            datefor=attendance_event.datefor - timedelta(days=1),
            punchintime=attendance_event.punchintime - timedelta(hours=2),
            punchouttime=attendance_event.punchintime - timedelta(minutes=30),
            endlocation=Point(80.0, 13.0)
        )

        detector = AttendanceAnomalyDetector(security_config)
        result = detector.detect_impossible_back_to_back(attendance_event)

        assert result is not None
        assert result['anomaly_type'] == 'IMPOSSIBLE_SHIFTS'
        assert result['severity'] == 'CRITICAL'
        assert result['distance_km'] > 200
        assert result['time_available_minutes'] < result['time_required_minutes']

    def test_detect_overtime_violation(self, security_config, attendance_event):
        """Test detection of overtime violations."""
        from apps.noc.security_intelligence.services import AttendanceAnomalyDetector
        from apps.attendance.models import PeopleEventlog

        for i in range(18):
            PeopleEventlog.objects.create(
                tenant=attendance_event.tenant,
                people=attendance_event.people,
                bu=attendance_event.bu,
                datefor=timezone.now().date(),
                punchintime=timezone.now() - timedelta(hours=18-i),
                punchouttime=timezone.now() - timedelta(hours=17-i)
            )

        detector = AttendanceAnomalyDetector(security_config)
        result = detector.detect_overtime_violation(attendance_event)

        assert result is not None
        assert result['anomaly_type'] == 'OVERTIME_VIOLATION'
        assert result['severity'] == 'HIGH'
        assert result['continuous_work_hours'] > security_config.max_continuous_work_hours

    def test_no_anomaly_for_scheduled_person(self, security_config, attendance_event):
        """Test no anomaly when correct person attends."""
        from apps.noc.security_intelligence.services import AttendanceAnomalyDetector
        from apps.noc.security_intelligence.models import ShiftScheduleCache

        ShiftScheduleCache.objects.create(
            tenant=attendance_event.tenant,
            person=attendance_event.people,
            site=attendance_event.bu,
            shift_date=attendance_event.datefor,
            scheduled_start=attendance_event.punchintime,
            scheduled_end=attendance_event.punchintime + timedelta(hours=8),
            cache_valid_until=timezone.now() + timedelta(days=1)
        )

        detector = AttendanceAnomalyDetector(security_config)
        result = detector.detect_wrong_person(attendance_event)

        assert result is None