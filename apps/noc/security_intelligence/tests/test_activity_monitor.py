"""
Unit Tests for Activity Monitor Service.

Tests inactivity detection algorithms and scoring logic.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestActivityMonitorService:
    """Test activity monitoring and inactivity detection."""

    def test_calculate_inactivity_score_all_signals_zero(self, security_config):
        """Test maximum inactivity score when all signals are zero."""
        from apps.noc.security_intelligence.services import ActivityMonitorService

        monitor = ActivityMonitorService(security_config)

        signals = {
            'phone_events': 0,
            'movement_meters': 0,
            'tasks_completed': 0,
            'tour_scans': 0,
        }

        score = monitor._calculate_inactivity_score(signals, is_deep_night=False)

        assert score >= 0.8
        assert score <= 1.0

    def test_calculate_inactivity_score_some_activity(self, security_config):
        """Test lower score with some activity."""
        from apps.noc.security_intelligence.services import ActivityMonitorService

        monitor = ActivityMonitorService(security_config)

        signals = {
            'phone_events': 5,
            'movement_meters': 50,
            'tasks_completed': 0,
            'tour_scans': 0,
        }

        score = monitor._calculate_inactivity_score(signals, is_deep_night=False)

        assert score < 0.8
        assert score >= 0.0

    def test_deep_night_increases_score(self, security_config):
        """Test that deep night hours increase inactivity score."""
        from apps.noc.security_intelligence.services import ActivityMonitorService

        monitor = ActivityMonitorService(security_config)

        signals = {
            'phone_events': 0,
            'movement_meters': 5,
            'tasks_completed': 0,
            'tour_scans': 0,
        }

        regular_score = monitor._calculate_inactivity_score(signals, is_deep_night=False)
        deep_night_score = monitor._calculate_inactivity_score(signals, is_deep_night=True)

        assert deep_night_score > regular_score

    def test_create_inactivity_alert(self, security_config, attendance_event):
        """Test creation of inactivity alert."""
        from apps.noc.security_intelligence.models import (
            GuardActivityTracking,
            InactivityAlert,
        )
        from apps.noc.security_intelligence.services import ActivityMonitorService

        tracking = GuardActivityTracking.objects.create(
            tenant=attendance_event.tenant,
            person=attendance_event.people,
            site=attendance_event.bu,
            tracking_start=timezone.now() - timedelta(hours=2),
            tracking_end=timezone.now(),
            shift_type='NIGHT',
            phone_events_count=0,
            location_updates_count=0,
            movement_distance_meters=0,
            tasks_completed_count=0,
            tour_checkpoints_scanned=0,
        )

        monitor = ActivityMonitorService(security_config)

        analysis = {
            'inactivity_score': 0.95,
            'is_inactive': True,
            'signals': {
                'phone_events': 0,
                'movement_meters': 0,
                'tasks_completed': 0,
                'tour_scans': 0,
            },
            'duration_minutes': 120,
            'is_deep_night': True,
        }

        alert = monitor.create_inactivity_alert(tracking, analysis)

        assert alert is not None
        assert alert.severity in ['HIGH', 'CRITICAL']
        assert alert.inactivity_score == 0.95
        assert alert.is_deep_night is True
        assert alert.no_phone_activity is True
        assert alert.no_movement is True

    def test_determine_severity(self, security_config):
        """Test severity determination logic."""
        from apps.noc.security_intelligence.services import ActivityMonitorService

        monitor = ActivityMonitorService(security_config)

        assert monitor._determine_severity(0.95, False) == 'CRITICAL'
        assert monitor._determine_severity(0.85, False) == 'HIGH'
        assert monitor._determine_severity(0.65, False) == 'MEDIUM'
        assert monitor._determine_severity(0.50, False) == 'LOW'

    def test_guard_activity_tracking_properties(self, security_config, attendance_event):
        """Test GuardActivityTracking model properties."""
        from apps.noc.security_intelligence.models import GuardActivityTracking

        night_tracking = GuardActivityTracking.objects.create(
            tenant=attendance_event.tenant,
            person=attendance_event.people,
            site=attendance_event.bu,
            tracking_start=timezone.now().replace(hour=22, minute=0),
            tracking_end=timezone.now().replace(hour=23, minute=59),
            shift_type='NIGHT',
        )

        assert night_tracking.is_night_shift is True

        deep_night_tracking = GuardActivityTracking.objects.create(
            tenant=attendance_event.tenant,
            person=attendance_event.people,
            site=attendance_event.bu,
            tracking_start=timezone.now().replace(hour=2, minute=0),
            tracking_end=timezone.now().replace(hour=3, minute=59),
            shift_type='NIGHT',
        )

        assert deep_night_tracking.is_deep_night is True

    def test_inactivity_alert_status_updates(self, security_config, attendance_event, test_person):
        """Test inactivity alert status update methods."""
        from apps.noc.security_intelligence.models import (
            GuardActivityTracking,
            InactivityAlert,
        )

        tracking = GuardActivityTracking.objects.create(
            tenant=attendance_event.tenant,
            person=attendance_event.people,
            site=attendance_event.bu,
            tracking_start=timezone.now() - timedelta(hours=2),
            tracking_end=timezone.now(),
            shift_type='NIGHT',
        )

        alert = InactivityAlert.objects.create(
            tenant=attendance_event.tenant,
            person=attendance_event.people,
            site=attendance_event.bu,
            activity_tracking=tracking,
            detected_at=timezone.now(),
            severity='HIGH',
            inactivity_score=0.85,
            inactivity_duration_minutes=120,
        )

        alert.mark_verified('CALL', "Guard answered phone")
        assert alert.verification_attempted is True
        assert alert.verification_method == 'CALL'
        assert alert.status == 'VERIFYING'

        alert.mark_confirmed(test_person, "Confirmed sleeping on duty")
        assert alert.status == 'CONFIRMED'
        assert alert.resolved_by == test_person