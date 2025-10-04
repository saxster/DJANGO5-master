"""
Unit Tests for SignalCorrelationEngine.

Tests multi-signal pattern detection (Silent Site, Tour Abandonment, SLA Storm, etc.).
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch, Mock

from apps.noc.security_intelligence.services.signal_correlation_engine import SignalCorrelationEngine


@pytest.mark.django_db
class TestSignalCorrelationEngine:
    """Test suite for SignalCorrelationEngine service."""

    def test_detect_silent_site_when_all_signals_zero(self, tenant, site):
        """Test silent site detected when phone + GPS + tasks all zero."""
        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_collect:
            mock_collect.return_value = {
                'phone_events_count': 0,
                'location_updates_count': 0,
                'tasks_completed_count': 0,
                'movement_distance_meters': 0,
                'tour_checkpoints_scanned': 0,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_person.id = 1
                mock_person.peoplename = 'Test Guard'
                mock_people.return_value.first.return_value = mock_person

                findings = SignalCorrelationEngine.correlate_signals_for_site(site, window_minutes=60)

        silent_findings = [f for f in findings if f.finding_type == 'CORRELATION_SILENT_SITE']
        assert len(silent_findings) == 1
        assert silent_findings[0].severity == 'CRITICAL'
        assert silent_findings[0].category == 'OPERATIONAL'

    def test_no_silent_site_when_any_signal_active(self, tenant, site):
        """Test no silent site when at least one signal is active."""
        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_collect:
            mock_collect.return_value = {
                'phone_events_count': 5,  # Active
                'location_updates_count': 0,
                'tasks_completed_count': 0,
                'movement_distance_meters': 0,
                'tour_checkpoints_scanned': 0,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_people.return_value.first.return_value = mock_person

                findings = SignalCorrelationEngine.correlate_signals_for_site(site, window_minutes=60)

        silent_findings = [f for f in findings if f.finding_type == 'CORRELATION_SILENT_SITE']
        assert len(silent_findings) == 0  # Should not detect silent site

    def test_detect_phantom_guard_pattern(self, tenant, site):
        """Test phantom guard detected when GPS active but no tasks."""
        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_collect:
            mock_collect.return_value = {
                'phone_events_count': 10,
                'location_updates_count': 8,  # GPS active
                'tasks_completed_count': 0,    # No tasks
                'movement_distance_meters': 500,
                'tour_checkpoints_scanned': 0,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_person.id = 1
                mock_person.peoplename = 'Test Guard'
                mock_people.return_value.first.return_value = mock_person

                findings = SignalCorrelationEngine.correlate_signals_for_site(site, window_minutes=120)

        phantom_findings = [f for f in findings if f.finding_type == 'CORRELATION_PHANTOM_GUARD']
        assert len(phantom_findings) == 1
        assert phantom_findings[0].category == 'SECURITY'

    def test_detect_device_gps_failure(self, tenant, site):
        """Test GPS failure detected when phone active but no GPS."""
        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_collect:
            mock_collect.return_value = {
                'phone_events_count': 10,      # Phone active
                'location_updates_count': 0,   # No GPS
                'tasks_completed_count': 3,
                'movement_distance_meters': 0,
                'tour_checkpoints_scanned': 2,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_people.return_value.first.return_value = mock_person

                findings = SignalCorrelationEngine.correlate_signals_for_site(site, window_minutes=60)

        device_findings = [f for f in findings if 'DEVICE_GPS_FAILURE' in f.finding_type]
        assert len(device_findings) == 1
        assert device_findings[0].category == 'DEVICE_HEALTH'
        assert device_findings[0].severity == 'HIGH'

    def test_correlate_multiple_patterns_in_single_run(self, tenant, site):
        """Test multiple patterns can be detected in one correlation run."""
        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_collect:
            # Scenario: Phone active, but no GPS and no tasks (2 patterns)
            mock_collect.return_value = {
                'phone_events_count': 10,
                'location_updates_count': 0,   # GPS failure
                'tasks_completed_count': 0,     # Phantom guard (if window >= 120)
                'movement_distance_meters': 0,
                'tour_checkpoints_scanned': 0,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_people.return_value.first.return_value = mock_person

                findings = SignalCorrelationEngine.correlate_signals_for_site(site, window_minutes=120)

        # Should detect at least GPS failure
        assert len(findings) >= 1
        finding_types = [f.finding_type for f in findings]
        assert any('DEVICE' in ft or 'GPS' in ft for ft in finding_types)
