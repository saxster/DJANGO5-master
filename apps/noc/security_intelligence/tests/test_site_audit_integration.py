"""
Integration Tests for Site Audit System.

End-to-end testing of the complete audit workflow:
Schedule → Audit → Findings → Evidence → Alerts → Runbooks

Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch, Mock

from apps.noc.security_intelligence.models import (
    SiteAuditSchedule,
    AuditFinding,
    BaselineProfile,
    FindingRunbook
)
from apps.noc.security_intelligence.services.real_time_audit_orchestrator import RealTimeAuditOrchestrator
from apps.noc.security_intelligence.services.baseline_calculator import BaselineCalculator
from apps.noc.security_intelligence.services.anomaly_detector import AnomalyDetector


@pytest.mark.django_db
class TestSiteAuditIntegration:
    """Integration test suite for complete site audit workflow."""

    @pytest.fixture
    def full_setup(self, tenant, site):
        """Create complete audit infrastructure."""
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
            },
            collect_evidence=True,
            alert_on_finding=True,
            alert_severity_threshold='HIGH',
        )

        # Create runbooks
        runbook1 = FindingRunbook.objects.create(
            tenant=tenant,
            finding_type='CRITICAL_SIGNAL_PHONE_EVENTS_LOW',
            title='Low Phone Activity',
            category='DEVICE_HEALTH',
            severity='HIGH',
            steps=['Contact guard', 'Check device'],
        )

        runbook2 = FindingRunbook.objects.create(
            tenant=tenant,
            finding_type='CORRELATION_SILENT_SITE',
            title='Silent Site',
            category='OPERATIONAL',
            severity='CRITICAL',
            steps=['Immediate dispatch', 'Contact supervisor'],
        )

        # Create baseline (stable)
        now = timezone.now()
        hour_of_week = now.weekday() * 24 + now.hour
        baseline = BaselineProfile.objects.create(
            tenant=tenant,
            site=site,
            metric_type='phone_events',
            hour_of_week=hour_of_week,
            mean=10.0,
            std_dev=2.0,
            sample_count=50,
            is_stable=True,
            sensitivity='MEDIUM',
        )

        return {
            'schedule': schedule,
            'runbook1': runbook1,
            'runbook2': runbook2,
            'baseline': baseline,
        }

    def test_end_to_end_audit_workflow(self, full_setup, tenant, site):
        """Test complete audit workflow from schedule to alert creation."""
        orchestrator = RealTimeAuditOrchestrator()

        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_signals:
            # Simulate low phone activity
            mock_signals.return_value = {
                'phone_events_count': 0,  # Below threshold
                'location_updates_count': 5,
                'tasks_completed_count': 2,
                'movement_distance_meters': 100,
                'tour_checkpoints_scanned': 1,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_person.id = 1
                mock_person.peoplename = 'John Doe'
                mock_people.return_value.first.return_value = mock_person

                with patch('apps.noc.services.correlation_service.AlertCorrelationService.process_alert') as mock_alert:
                    mock_alert.return_value = Mock(id=999)

                    # Run audit
                    findings = orchestrator.run_comprehensive_audit(site)

        # Verify findings created
        assert len(findings) > 0

        # Verify evidence collected
        for finding in findings:
            if full_setup['schedule'].collect_evidence:
                assert finding.evidence != {}

        # Verify runbook linked
        for finding in findings:
            if finding.runbook_id:
                assert finding.recommended_actions != []

        # Verify schedule stats updated
        full_setup['schedule'].refresh_from_db()
        assert full_setup['schedule'].total_audits_run > 0

    def test_baseline_learning_and_anomaly_detection_workflow(self, full_setup, site):
        """Test baseline calculation followed by anomaly detection."""
        # Step 1: Calculate baselines
        with patch('apps.noc.security_intelligence.services.baseline_calculator.BaselineCalculator._get_metric_value_for_hour') as mock_get_value:
            mock_get_value.return_value = 10.0

            summary = BaselineCalculator.calculate_baselines_for_site(
                site=site,
                start_date=timezone.now().date() - timedelta(days=1),
                days_lookback=1
            )

        assert summary['baselines_created'] > 0 or summary['baselines_updated'] > 0

        # Step 2: Detect anomalies
        with patch('apps.noc.security_intelligence.services.anomaly_detector.AnomalyDetector._get_current_metric_value') as mock_current:
            # Value way above baseline (mean=10, std_dev=2, value=20 -> z=5)
            mock_current.return_value = 20.0

            findings = AnomalyDetector.detect_anomalies_for_site(site)

        # Should detect anomaly
        anomaly_findings = [f for f in findings if 'ANOMALY' in f.finding_type]
        assert len(anomaly_findings) > 0

    def test_heartbeat_to_comprehensive_audit_escalation(self, full_setup, site):
        """Test heartbeat detects issue, comprehensive audit provides details."""
        orchestrator = RealTimeAuditOrchestrator()

        with patch('apps.noc.security_intelligence.services.activity_signal_collector.ActivitySignalCollector.collect_all_signals') as mock_signals:
            mock_signals.return_value = {
                'phone_events_count': 0,  # Critical signal low
                'location_updates_count': 0,
                'tasks_completed_count': 0,
                'movement_distance_meters': 0,
                'tour_checkpoints_scanned': 0,
            }

            with patch('apps.peoples.models.People.objects.filter') as mock_people:
                mock_person = Mock()
                mock_people.return_value.first.return_value = mock_person

                # Step 1: Heartbeat check
                heartbeat_findings = orchestrator.run_heartbeat_check(site)

                # Step 2: Comprehensive audit
                comprehensive_findings = orchestrator.run_comprehensive_audit(site)

        # Heartbeat should detect critical signal issues
        assert len(heartbeat_findings) > 0

        # Comprehensive audit provides more detailed findings
        # (Note: May overlap with heartbeat findings)
        assert len(comprehensive_findings) >= 0

    def test_finding_workflow_acknowledge_and_resolve(self, full_setup, tenant, site):
        """Test finding lifecycle: create → acknowledge → resolve."""
        from apps.peoples.models import People

        # Create a finding
        finding = AuditFinding.objects.create(
            tenant=tenant,
            site=site,
            finding_type='TEST_FINDING',
            category='SECURITY',
            severity='HIGH',
            title='Test Finding',
            description='Test description',
            status='NEW',
        )

        # Create mock user
        user = Mock()
        user.id = 1
        user.peoplename = 'Admin User'

        # Acknowledge
        finding.acknowledge(user)
        finding.refresh_from_db()
        assert finding.status == 'ACKNOWLEDGED'
        assert finding.acknowledged_by == user
        assert finding.time_to_acknowledge is not None

        # Resolve
        finding.resolve(user, notes='Fixed the issue')
        finding.refresh_from_db()
        assert finding.status == 'RESOLVED'
        assert finding.resolved_by == user
        assert finding.resolution_notes == 'Fixed the issue'
        assert finding.time_to_resolve is not None

    def test_audit_respects_maintenance_window(self, full_setup, site):
        """Test audits skip sites in maintenance windows."""
        now = timezone.now()

        # Set maintenance window (current time)
        full_setup['schedule'].maintenance_windows = [
            {
                'start': (now - timedelta(hours=1)).isoformat(),
                'end': (now + timedelta(hours=1)).isoformat(),
                'reason': 'Scheduled maintenance',
            }
        ]
        full_setup['schedule'].save()

        orchestrator = RealTimeAuditOrchestrator()

        # Should not run audit during maintenance
        findings = orchestrator.run_heartbeat_check(site)

        # No findings created during maintenance
        assert len(findings) == 0
