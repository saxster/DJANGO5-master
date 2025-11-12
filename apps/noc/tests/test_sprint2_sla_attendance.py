"""
Integration Tests for Sprint 2: SLA Logic & Attendance Expectations

Tests the complete flow of SLA calculation and attendance expectation
integration with NOC aggregation service.

Following CLAUDE.md testing standards:
- Unit tests for each service
- Integration tests for NOC aggregation
- Business logic edge cases
- Performance benchmarks

Created: 2025-10-11
"""

import pytest
from datetime import datetime, date, time, timedelta
from django.utils import timezone
from django.test import TestCase
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.models.sla_policy import SLAPolicy
from apps.y_helpdesk.services.sla_calculator import SLACalculator
from apps.attendance.services.attendance_expectation_service import AttendanceExpectationService
from apps.noc.services.aggregation_service import NOCAggregationService
from apps.client_onboarding.models import Bt
from apps.peoples.models import People, Pgbelonging


@pytest.mark.django_db
class TestSLAPolicy(TestCase):
    """Test SLA Policy model and business rules."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            butype='CLIENT'
        )

    def test_sla_policy_creation(self):
        """Test SLA policy model creation."""
        policy = SLAPolicy.objects.create(
            policy_name='Critical Incident SLA',
            client=self.client,
            priority='P1',
            response_time_minutes=30,
            resolution_time_minutes=240,
            escalation_threshold_minutes=180,
            exclude_weekends=True,
            is_active=True
        )

        assert policy.policy_name == 'Critical Incident SLA'
        assert policy.priority == 'P1'
        assert policy.resolution_time_minutes == 240  # 4 hours

    def test_sla_policy_validation(self):
        """Test SLA policy validation rules."""
        with pytest.raises(Exception):  # ValidationError
            policy = SLAPolicy(
                policy_name='Invalid SLA',
                priority='P1',
                response_time_minutes=300,  # 5 hours
                resolution_time_minutes=240,  # 4 hours (less than response!)
                escalation_threshold_minutes=180
            )
            policy.clean()  # Should raise ValidationError


@pytest.mark.django_db
class TestSLACalculator(TestCase):
    """Test SLA Calculator service."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            bucode='CLIENT002',
            buname='SLA Test Client',
            butype='CLIENT'
        )

        self.site = Bt.objects.create(
            bucode='SITE001',
            buname='Test Site',
            butype='SITE',
            parent=self.client
        )

        # Create SLA policy
        self.sla_policy = SLAPolicy.objects.create(
            policy_name='Standard P1 SLA',
            client=self.client,
            priority='P1',
            response_time_minutes=30,
            resolution_time_minutes=240,  # 4 hours
            escalation_threshold_minutes=180,
            is_active=True
        )

        self.calculator = SLACalculator()

    def test_ticket_not_overdue(self):
        """Test ticket within SLA is not marked overdue."""
        # Create ticket 2 hours ago
        created_at = timezone.now() - timedelta(hours=2)

        ticket = Ticket.objects.create(
            bu=self.site,
            client=self.client,
            priority='P1',
            status='OPEN',
            cdtz=created_at
        )

        is_overdue = self.calculator.is_ticket_overdue(ticket)

        # 2 hours < 4 hours (resolution target)
        assert not is_overdue

    def test_ticket_overdue(self):
        """Test ticket exceeding SLA is marked overdue."""
        # Create ticket 5 hours ago
        created_at = timezone.now() - timedelta(hours=5)

        ticket = Ticket.objects.create(
            bu=self.site,
            client=self.client,
            priority='P1',
            status='OPEN',
            cdtz=created_at
        )

        is_overdue = self.calculator.is_ticket_overdue(ticket)

        # 5 hours > 4 hours (resolution target)
        assert is_overdue

    def test_sla_metrics_calculation(self):
        """Test comprehensive SLA metrics."""
        created_at = timezone.now() - timedelta(hours=3)

        ticket = Ticket.objects.create(
            bu=self.site,
            client=self.client,
            priority='P1',
            status='OPEN',
            cdtz=created_at
        )

        metrics = self.calculator.calculate_sla_metrics(ticket)

        assert not metrics['is_overdue']  # 3 hours < 4 hours
        assert metrics['requires_escalation']  # 3 hours > 3 hours (180 min)
        assert metrics['elapsed_minutes'] >= 180
        assert metrics['remaining_minutes'] > 0
        assert metrics['policy_name'] == 'Standard P1 SLA'

    def test_default_sla_fallback(self):
        """Test default SLA when no policy configured."""
        # Create ticket with P2 priority (no policy)
        ticket = Ticket.objects.create(
            bu=self.site,
            client=self.client,
            priority='P2',
            status='OPEN'
        )

        metrics = self.calculator.calculate_sla_metrics(ticket)

        assert metrics['target_resolution_minutes'] == 480  # 8 hours default for P2
        assert metrics['policy_name'] == 'Default'


@pytest.mark.django_db
class TestAttendanceExpectation(TestCase):
    """Test Attendance Expectation service."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            bucode='CLIENT003',
            buname='Attendance Client',
            butype='CLIENT'
        )

        self.site = Bt.objects.create(
            bucode='SITE002',
            buname='Attendance Site',
            butype='SITE',
            parent=self.client
        )

        # Create test users
        self.users = []
        for i in range(5):
            user = People.objects.create(
                peoplecode=f'GUARD{i:03d}',
                peoplename=f'Guard {i}',
                loginid=f'guard{i}',
                mobno=f'+9198765432{i:02d}',
                email=f'guard{i}@example.com',
                client=self.client,
                bu=self.site,
                is_active=True,
                enable=True
            )
            self.users.append(user)

            # Assign to site
            Pgbelonging.objects.create(
                people=user,
                assignsites=self.site,
                bu=self.site,
                client=self.client
            )

        self.service = AttendanceExpectationService()

    def test_expected_attendance_calculation(self):
        """Test expected attendance calculation."""
        metrics = self.service.calculate_attendance_metrics(
            sites=[self.site],
            target_date=date.today()
        )

        # Should expect all 5 guards
        assert metrics['attendance_expected'] == 5

    def test_actual_attendance_with_check_ins(self):
        """Test actual attendance with check-ins."""
        from apps.attendance.models import PeopleEventlog

        # Create attendance records for 3 guards
        today_start = datetime.combine(date.today(), datetime.min.time())

        for user in self.users[:3]:
            PeopleEventlog.objects.create(
                people=user,
                bu=self.site,
                client=self.client,
                checkin=timezone.now(),
                cdtz=today_start
            )

        metrics = self.service.calculate_attendance_metrics(
            sites=[self.site],
            target_date=date.today()
        )

        assert metrics['attendance_present'] == 3
        assert metrics['attendance_missing'] == 2  # 5 expected - 3 present


@pytest.mark.django_db
class TestNOCAggregationIntegration(TestCase):
    """Test NOC Aggregation with SLA and Attendance integration."""

    def setUp(self):
        """Set up test data."""
        self.client = Bt.objects.create(
            bucode='CLIENT004',
            buname='NOC Test Client',
            butype='CLIENT'
        )

        self.site = Bt.objects.create(
            bucode='SITE003',
            buname='NOC Test Site',
            butype='SITE',
            parent=self.client
        )

        # Create SLA policy
        SLAPolicy.objects.create(
            policy_name='Test SLA',
            client=self.client,
            priority='P1',
            response_time_minutes=30,
            resolution_time_minutes=240,
            escalation_threshold_minutes=180,
            is_active=True
        )

    def test_noc_snapshot_with_sla_integration(self):
        """Test NOC snapshot creation with SLA calculations."""
        # Create overdue ticket (5 hours ago)
        Ticket.objects.create(
            bu=self.site,
            client=self.client,
            priority='P1',
            status='OPEN',
            cdtz=timezone.now() - timedelta(hours=5)
        )

        # Create NOC snapshot
        snapshot = NOCAggregationService.create_snapshot_for_client(self.client.id)

        assert snapshot is not None
        assert snapshot.tickets_overdue == 1  # Should detect overdue via SLA

    def test_noc_snapshot_with_attendance_integration(self):
        """Test NOC snapshot with attendance expectations."""
        snapshot = NOCAggregationService.create_snapshot_for_client(self.client.id)

        assert snapshot is not None
        # Should have attendance metrics (even if zero)
        assert hasattr(snapshot, 'attendance_expected')
        assert hasattr(snapshot, 'attendance_present')
        assert hasattr(snapshot, 'attendance_missing')


# Performance benchmarks
@pytest.mark.benchmark
@pytest.mark.django_db
class TestSprint2Performance(TestCase):
    """Performance benchmarks for Sprint 2 features."""

    def test_sla_calculation_performance(self):
        """Verify SLA calculation completes within 20ms."""
        import time

        client = Bt.objects.create(bucode='PERFCLIENT', buname='Perf Client', butype='CLIENT')
        site = Bt.objects.create(bucode='PERFSITE', buname='Perf Site', butype='SITE', parent=client)

        ticket = Ticket.objects.create(
            bu=site,
            client=client,
            priority='P1',
            status='OPEN'
        )

        calculator = SLACalculator()

        start = time.time()
        result = calculator.is_ticket_overdue(ticket)
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 20, f"SLA calculation took {duration_ms}ms (threshold: 20ms)"
        assert result is not None

    def test_attendance_calculation_performance(self):
        """Verify attendance calculation completes within 100ms."""
        import time

        site = Bt.objects.create(bucode='ATTNSITE', buname='Attendance Site', butype='SITE')

        service = AttendanceExpectationService()

        start = time.time()
        metrics = service.calculate_attendance_metrics([site])
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 100, f"Attendance calc took {duration_ms}ms (threshold: 100ms)"
        assert metrics is not None
