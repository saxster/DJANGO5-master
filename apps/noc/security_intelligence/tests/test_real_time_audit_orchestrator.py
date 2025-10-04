"""
Unit Tests for RealTimeAuditOrchestrator.

Tests multi-cadence audit execution, finding creation, and evidence collection.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock

from apps.noc.security_intelligence.models import (
    SiteAuditSchedule,
    AuditFinding,
    FindingRunbook
)
from apps.noc.security_intelligence.services.real_time_audit_orchestrator import RealTimeAuditOrchestrator


@pytest.mark.django_db
class TestRealTimeAuditOrchestrator:
    """Test suite for RealTimeAuditOrchestrator service."""

    @pytest.fixture
    def setup_data(self, tenant, site):
        """Create test data."""
        # Create audit schedule
        schedule = SiteAuditSchedule.objects.create(
            tenant=tenant,
            site=site,
            enabled=True,
            audit_frequency_minutes=15,
            heartbeat_frequency_minutes=5,
            critical_signals=['phone_events', 'location_updates'],
            signal_thresholds={
                'phone_events': {'min_count': 1, 'window_minutes': 60},
                'location_updates': {'min_count': 1, 'window_minutes': 60},
            },
            collect_evidence=True,
            alert_on_finding=True,
        )

        # Create runbook
        runbook = FindingRunbook.objects.create(
            tenant=tenant,
            finding_type='CRITICAL_SIGNAL_PHONE_EVENTS_LOW',
            title='Low phone activity',
            category='DEVICE_HEALTH',
            severity='HIGH',
            description='Phone activity below threshold',
            steps=['Check device', 'Contact guard'],
        )

        return {
            'schedule': schedule,
            'runbook': runbook,
        }

    def test_run_heartbeat_check_creates_finding_when_signal_low(self, setup_data, tenant, site):
        """Test heartbeat check creates finding when signal is below threshold."""
        orchestrator = RealTimeAuditOrchestrator()

        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_collect:
            mock_collect.return_value = {
                'phone_events_count': 0,  # Below threshold
                'location_updates_count': 5,
                'movement_distance_meters': 100,
                'tasks_completed_count': 2,
                'tour_checkpoints_scanned': 1,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_person.id = 1
                mock_person.peoplename = 'Test Guard'
                mock_people.return_value.first.return_value = mock_person

                findings = orchestrator.run_heartbeat_check(site)

        assert len(findings) > 0
        finding = findings[0]
        assert finding.finding_type == 'CRITICAL_SIGNAL_PHONE_EVENTS_LOW'
        assert finding.severity == 'HIGH'
        assert finding.category == 'DEVICE_HEALTH'

    def test_run_comprehensive_audit_collects_evidence(self, setup_data, tenant, site):
        """Test comprehensive audit collects evidence when enabled."""
        orchestrator = RealTimeAuditOrchestrator()

        with patch('apps.noc.security_intelligence.services.evidence_collector.EvidenceCollector.collect_evidence') as mock_evidence:
            mock_evidence.return_value = {
                'location_history': [{'lat': 12.34, 'lon': 56.78}],
                'task_logs': [],
                'tour_logs': [],
            }

            with patch('apps.noc.security_intelligence.services.task_compliance_monitor.TaskComplianceMonitor.check_tour_compliance') as mock_tours:
                mock_tours.return_value = []

                findings = orchestrator.run_comprehensive_audit(site)

        # Verify evidence collection was attempted
        # (actual findings depend on compliance monitor returning violations)
        assert setup_data['schedule'].total_audits_run > 0

    def test_create_finding_links_runbook(self, setup_data, tenant, site):
        """Test finding creation properly links to runbook."""
        orchestrator = RealTimeAuditOrchestrator()

        finding = orchestrator._create_finding(
            site=site,
            finding_type='CRITICAL_SIGNAL_PHONE_EVENTS_LOW',
            category='DEVICE_HEALTH',
            severity='HIGH',
            title='Test finding',
            description='Test description',
            evidence={'test': 'data'}
        )

        assert finding is not None
        assert finding.runbook_id == setup_data['runbook']
        assert finding.recommended_actions == setup_data['runbook'].steps
        assert finding.evidence == {'test': 'data'}

    def test_alerts_created_for_findings_above_threshold(self, setup_data, tenant, site):
        """Test alerts are created for findings meeting severity threshold."""
        orchestrator = RealTimeAuditOrchestrator()

        finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site,
            finding_type='TEST_FINDING',
            category='SECURITY',
            severity='HIGH',
            title='Test',
            description='Test'
        )

        with patch('apps.noc.services.correlation_service.AlertCorrelationService.process_alert') as mock_alert:
            mock_alert.return_value = Mock(id=123)

            orchestrator._create_alert_for_finding(finding)

        finding.refresh_from_db()
        assert finding.noc_alert_id is not None

    def test_heartbeat_respects_maintenance_window(self, setup_data, tenant, site):
        """Test heartbeat skips sites in maintenance window."""
        now = timezone.now()
        setup_data['schedule'].maintenance_windows = [
            {
                'start': (now - timedelta(hours=1)).isoformat(),
                'end': (now + timedelta(hours=1)).isoformat(),
            }
        ]
        setup_data['schedule'].save()

        orchestrator = RealTimeAuditOrchestrator()

        findings = orchestrator.run_heartbeat_check(site)

        # No findings should be created during maintenance
        assert len(findings) == 0
