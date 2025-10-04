"""
Unit Tests for Security Anomaly Orchestrator.

Tests end-to-end anomaly detection and NOC alert integration.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestSecurityAnomalyOrchestrator:
    """Test orchestrator service integration."""

    def test_process_attendance_creates_anomaly_log(
        self, security_config, attendance_event, other_person
    ):
        """Test that processing attendance creates anomaly logs."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import (
            ShiftScheduleCache,
            AttendanceAnomalyLog
        )

        ShiftScheduleCache.objects.create(
            tenant=attendance_event.tenant,
            person=other_person,
            site=attendance_event.bu,
            shift_date=attendance_event.datefor,
            scheduled_start=attendance_event.punchintime,
            scheduled_end=attendance_event.punchintime + timedelta(hours=8),
            cache_valid_until=timezone.now() + timedelta(days=1)
        )

        anomalies = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        assert len(anomalies) > 0
        assert AttendanceAnomalyLog.objects.filter(
            attendance_event=attendance_event
        ).count() > 0

    def test_process_attendance_creates_noc_alert(
        self, security_config, attendance_event, other_person
    ):
        """Test that processing creates NOC alerts."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import (
            ShiftScheduleCache,
            AttendanceAnomalyLog
        )

        ShiftScheduleCache.objects.create(
            tenant=attendance_event.tenant,
            person=other_person,
            site=attendance_event.bu,
            shift_date=attendance_event.datefor,
            scheduled_start=attendance_event.punchintime,
            scheduled_end=attendance_event.punchintime + timedelta(hours=8),
            cache_valid_until=timezone.now() + timedelta(days=1)
        )

        anomalies = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        for anomaly in anomalies:
            assert anomaly.noc_alert is not None
            assert anomaly.noc_alert.alert_type == 'SECURITY_ANOMALY'
            assert anomaly.noc_alert.severity == anomaly.severity

    def test_process_attendance_no_config_returns_empty(self, attendance_event):
        """Test that no config returns empty results."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator

        anomalies = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        assert len(anomalies) == 0

    def test_anomaly_log_status_updates(
        self, security_config, attendance_event, other_person, test_person
    ):
        """Test anomaly log status update methods."""
        from apps.noc.security_intelligence.models import AttendanceAnomalyLog

        anomaly_log = AttendanceAnomalyLog.objects.create(
            tenant=attendance_event.tenant,
            anomaly_type='WRONG_PERSON',
            severity='HIGH',
            person=attendance_event.people,
            site=attendance_event.bu,
            attendance_event=attendance_event,
            detected_at=timezone.now(),
            confidence_score=0.95,
            expected_person=other_person
        )

        anomaly_log.mark_confirmed(test_person, "Confirmed after investigation")

        assert anomaly_log.status == 'CONFIRMED'
        assert anomaly_log.investigated_by == test_person
        assert anomaly_log.investigated_at is not None
        assert 'investigation' in anomaly_log.investigation_notes.lower()

    def test_anomaly_log_false_positive(
        self, security_config, attendance_event, other_person, test_person
    ):
        """Test marking anomaly as false positive."""
        from apps.noc.security_intelligence.models import AttendanceAnomalyLog

        anomaly_log = AttendanceAnomalyLog.objects.create(
            tenant=attendance_event.tenant,
            anomaly_type='WRONG_PERSON',
            severity='HIGH',
            person=attendance_event.people,
            site=attendance_event.bu,
            attendance_event=attendance_event,
            detected_at=timezone.now(),
            confidence_score=0.95,
            expected_person=other_person
        )

        anomaly_log.mark_false_positive(test_person, "Schedule was updated")

        assert anomaly_log.status == 'FALSE_POSITIVE'
        assert anomaly_log.investigated_by == test_person