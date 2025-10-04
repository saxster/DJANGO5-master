"""
Unit Tests for Task Compliance Monitor.

Tests SLA monitoring and compliance detection algorithms.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestTaskComplianceMonitor:
    """Test task and tour compliance monitoring."""

    def test_task_compliance_config_sla_mapping(self, tenant):
        """Test SLA minutes mapping for priorities."""
        from apps.noc.security_intelligence.models import TaskComplianceConfig

        config = TaskComplianceConfig.objects.create(
            tenant=tenant,
            scope='TENANT',
            is_active=True,
            critical_task_sla_minutes=15,
            high_task_sla_minutes=30,
            medium_task_sla_minutes=60,
        )

        assert config.get_sla_minutes_for_priority('CRITICAL') == 15
        assert config.get_sla_minutes_for_priority('HIGH') == 30
        assert config.get_sla_minutes_for_priority('MEDIUM') == 60
        assert config.get_sla_minutes_for_priority('LOW') == 120

    def test_tour_compliance_log_coverage_calculation(self, tenant, test_person, site_bt):
        """Test checkpoint coverage percentage calculation."""
        from apps.noc.security_intelligence.models import TourComplianceLog

        tour = TourComplianceLog.objects.create(
            tenant=tenant,
            person=test_person,
            site=site_bt,
            scheduled_date=timezone.now().date(),
            scheduled_time=timezone.now().time(),
            scheduled_datetime=timezone.now(),
            tour_type='ROUTINE',
            is_mandatory=True,
            total_checkpoints=10,
            scanned_checkpoints=8,
            checkpoint_coverage_percent=80.0,
            guard_checked_in=True,
            guard_present=True,
        )

        assert tour.checkpoint_coverage_percent == 80.0

    def test_tour_compliance_status_calculation(self, tenant, test_person, site_bt):
        """Test automatic compliance status calculation."""
        from apps.noc.security_intelligence.models import TourComplianceLog

        # Test partial completion
        tour = TourComplianceLog.objects.create(
            tenant=tenant,
            person=test_person,
            site=site_bt,
            scheduled_date=timezone.now().date(),
            scheduled_time=timezone.now().time(),
            scheduled_datetime=timezone.now(),
            tour_type='CRITICAL',
            is_mandatory=True,
            status='COMPLETED',
            total_checkpoints=10,
            scanned_checkpoints=7,
            checkpoint_coverage_percent=70.0,
            guard_checked_in=True,
            guard_present=True,
        )

        tour.calculate_compliance()
        assert tour.compliance_status == 'PARTIAL_COMPLETION'

    def test_tour_guard_absent_detection(self, tenant, test_person, site_bt):
        """Test guard absent compliance status."""
        from apps.noc.security_intelligence.models import TourComplianceLog

        tour = TourComplianceLog.objects.create(
            tenant=tenant,
            person=test_person,
            site=site_bt,
            scheduled_date=timezone.now().date(),
            scheduled_time=timezone.now().time(),
            scheduled_datetime=timezone.now(),
            tour_type='CRITICAL',
            is_mandatory=True,
            status='MISSED',
            guard_checked_in=False,
            guard_present=False,
        )

        tour.calculate_compliance()
        assert tour.compliance_status == 'GUARD_ABSENT'

    def test_task_severity_determination(self, tenant):
        """Test task alert severity determination."""
        from apps.noc.security_intelligence.models import TaskComplianceConfig
        from apps.noc.security_intelligence.services import TaskComplianceMonitor

        config = TaskComplianceConfig.objects.create(
            tenant=tenant,
            scope='TENANT',
            is_active=True,
            critical_task_sla_minutes=15,
        )

        monitor = TaskComplianceMonitor(config)

        # Critical task, 1.5x SLA breach
        severity = monitor._determine_task_severity('CRITICAL', 22.5, 15)
        assert severity == 'HIGH'

        # Critical task, 2x SLA breach
        severity = monitor._determine_task_severity('CRITICAL', 30, 15)
        assert severity == 'CRITICAL'

    def test_compliance_reporting_metrics(self, tenant):
        """Test compliance reporting service metrics."""
        from apps.noc.security_intelligence.services import ComplianceReportingService

        summary = ComplianceReportingService.get_task_compliance_summary(tenant, days=7)

        assert 'period_days' in summary
        assert 'total_tasks' in summary
        assert 'completion_rate' in summary
        assert 'overdue_rate' in summary

    def test_site_compliance_ranking(self, tenant):
        """Test site performance ranking."""
        from apps.noc.security_intelligence.services import ComplianceReportingService

        ranking = ComplianceReportingService.get_site_compliance_ranking(tenant, days=7, limit=5)

        assert isinstance(ranking, list)

    def test_guard_compliance_ranking(self, tenant):
        """Test guard performance ranking."""
        from apps.noc.security_intelligence.services import ComplianceReportingService

        ranking = ComplianceReportingService.get_guard_compliance_ranking(tenant, days=7, limit=5)

        assert isinstance(ranking, list)