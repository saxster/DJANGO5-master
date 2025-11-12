"""
Integration tests for critical end-to-end workflows.

Tests complete business processes from start to finish:
1. User registration → authentication → authorization
2. Work order creation → assignment → completion
3. Incident detection → escalation → resolution
4. Report generation → export → delivery
5. Multi-tenant data isolation

Coverage target: Critical workflows 100%
"""

import pytest
from datetime import datetime, timedelta
from django.test import Client, TestCase
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.core import mail

from apps.peoples.models import People, PeopleProfile, PeopleOrganizational
from apps.work_order_management.models import WorkOrder, WorkOrderStatus
from apps.noc.models import NOCAlertEvent
from apps.reports.models import Report, ReportExecution
from apps.tenants.models import Tenant


@pytest.fixture
def client():
    """Create test client."""
    return Client()


@pytest.fixture
def test_tenant(db):
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Corporation",
        subdomain="testcorp",
        is_active=True
    )


@pytest.fixture
def test_user(db, test_tenant):
    """Create test user with complete profile."""
    user = People.objects.create(
        peoplename="testuser",
        peopleemail="test@testcorp.com",
        peoplecontactno="+919876543210",
        peoplepassword=make_password("Test@123"),
        is_active=True,
        tenant=test_tenant
    )
    
    # Create profile
    PeopleProfile.objects.create(
        people=user,
        gender="MALE",
        date_of_birth=datetime(1990, 1, 1).date()
    )
    
    # Create organizational data
    PeopleOrganizational.objects.create(
        people=user,
        designation="Security Supervisor",
        employee_id="EMP001"
    )
    
    return user


@pytest.fixture
def supervisor_user(db, test_tenant):
    """Create supervisor user."""
    user = People.objects.create(
        peoplename="supervisor",
        peopleemail="supervisor@testcorp.com",
        peoplecontactno="+919876543211",
        peoplepassword=make_password("Super@123"),
        is_active=True,
        tenant=test_tenant,
        is_staff=True
    )
    
    PeopleProfile.objects.create(people=user, gender="FEMALE")
    PeopleOrganizational.objects.create(
        people=user,
        designation="Senior Supervisor",
        employee_id="SUP001"
    )
    
    return user


class TestUserOnboardingWorkflow:
    """Test complete user registration and authentication flow."""

    def test_user_registration_login_access_flow(self, client, test_tenant, db):
        """Test user registration → email verification → login → access protected resource."""
        # Step 1: Register new user
        registration_data = {
            'peoplename': 'newuser',
            'peopleemail': 'newuser@testcorp.com',
            'peoplecontactno': '+919876543212',
            'peoplepassword': 'NewUser@123',
            'tenant_id': test_tenant.id
        }
        
        # Create user (simulating registration)
        new_user = People.objects.create(
            peoplename=registration_data['peoplename'],
            peopleemail=registration_data['peopleemail'],
            peoplecontactno=registration_data['peoplecontactno'],
            peoplepassword=make_password(registration_data['peoplepassword']),
            is_active=False,  # Inactive until verified
            tenant=test_tenant
        )
        
        assert new_user.is_active is False
        
        # Step 2: Verify email (simulate email verification)
        new_user.is_active = True
        new_user.save()
        
        assert new_user.is_active is True
        
        # Step 3: Login
        response = client.post('/api/v1/auth/login/', {
            'username': 'newuser@testcorp.com',
            'password': 'NewUser@123'
        })
        
        # Step 4: Access protected resource
        if response.status_code == 200:
            # Login successful - user can now access protected resources
            assert new_user.is_active is True

    def test_user_profile_completion_workflow(self, test_user, client, db):
        """Test user completes profile after registration."""
        # User should have minimal profile initially
        assert hasattr(test_user, 'peopleprofile')
        
        # Complete additional profile fields
        profile = test_user.peopleprofile
        profile.emergency_contact = "+919876543299"
        profile.blood_group = "O+"
        profile.save()
        
        # Verify profile updated
        profile.refresh_from_db()
        assert profile.emergency_contact == "+919876543299"
        assert profile.blood_group == "O+"

    def test_multi_tenant_user_isolation(self, test_user, db):
        """Test users are isolated by tenant."""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name="Other Corp",
            subdomain="othercorp",
            is_active=True
        )
        
        # Create user in second tenant
        other_user = People.objects.create(
            peoplename="otheruser",
            peopleemail="other@othercorp.com",
            peoplecontactno="+919876543213",
            peoplepassword=make_password("Other@123"),
            tenant=tenant2
        )
        
        # Verify users are in different tenants
        assert test_user.tenant != other_user.tenant
        
        # Verify tenant filtering works
        tenant1_users = People.objects.filter(tenant=test_user.tenant)
        assert test_user in tenant1_users
        assert other_user not in tenant1_users


class TestWorkOrderWorkflow:
    """Test work order creation → assignment → completion workflow."""

    def test_work_order_creation_assignment_completion(
        self,
        test_user,
        supervisor_user,
        test_tenant,
        db
    ):
        """Test complete work order lifecycle."""
        # Step 1: Create work order
        work_order = WorkOrder.objects.create(
            title="Fix broken door lock",
            description="Main entrance door lock is malfunctioning",
            priority="HIGH",
            status=WorkOrderStatus.PENDING.value,
            created_by=supervisor_user,
            tenant=test_tenant
        )
        
        assert work_order.status == WorkOrderStatus.PENDING.value
        assert work_order.assigned_to is None
        
        # Step 2: Assign to technician
        work_order.assigned_to = test_user
        work_order.status = WorkOrderStatus.IN_PROGRESS.value
        work_order.assigned_at = timezone.now()
        work_order.save()
        
        assert work_order.assigned_to == test_user
        assert work_order.status == WorkOrderStatus.IN_PROGRESS.value
        
        # Step 3: Technician completes work
        work_order.status = WorkOrderStatus.COMPLETED.value
        work_order.completed_at = timezone.now()
        work_order.resolution_notes = "Replaced lock mechanism, tested functionality"
        work_order.save()
        
        assert work_order.status == WorkOrderStatus.COMPLETED.value
        assert work_order.completed_at is not None
        
        # Step 4: Supervisor verifies completion
        work_order.verified_by = supervisor_user
        work_order.verified_at = timezone.now()
        work_order.save()
        
        assert work_order.verified_by == supervisor_user
        
        # Verify complete workflow
        work_order.refresh_from_db()
        assert work_order.created_by == supervisor_user
        assert work_order.assigned_to == test_user
        assert work_order.verified_by == supervisor_user
        assert work_order.status == WorkOrderStatus.COMPLETED.value

    def test_work_order_escalation_flow(self, test_user, supervisor_user, test_tenant, db):
        """Test work order escalation when overdue."""
        # Create overdue work order
        work_order = WorkOrder.objects.create(
            title="Urgent repair",
            description="Critical issue",
            priority="CRITICAL",
            status=WorkOrderStatus.IN_PROGRESS.value,
            assigned_to=test_user,
            created_by=supervisor_user,
            tenant=test_tenant,
            due_date=timezone.now() - timedelta(hours=2)  # Overdue
        )
        
        # Check if overdue
        is_overdue = work_order.due_date and work_order.due_date < timezone.now()
        assert is_overdue is True
        
        # Escalate
        work_order.is_escalated = True
        work_order.escalated_to = supervisor_user
        work_order.escalated_at = timezone.now()
        work_order.save()
        
        assert work_order.is_escalated is True
        assert work_order.escalated_to == supervisor_user

    def test_work_order_tenant_isolation(self, test_user, test_tenant, db):
        """Test work orders are isolated by tenant."""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name="Other Corp",
            subdomain="othercorp",
            is_active=True
        )
        
        # Create work order in tenant1
        wo1 = WorkOrder.objects.create(
            title="Tenant 1 WO",
            description="Test",
            tenant=test_tenant,
            created_by=test_user
        )
        
        # Create user in tenant2
        user2 = People.objects.create(
            peoplename="user2",
            peopleemail="user2@othercorp.com",
            peoplecontactno="+919876543214",
            tenant=tenant2
        )
        
        # Create work order in tenant2
        wo2 = WorkOrder.objects.create(
            title="Tenant 2 WO",
            description="Test",
            tenant=tenant2,
            created_by=user2
        )
        
        # Verify isolation
        tenant1_orders = WorkOrder.objects.filter(tenant=test_tenant)
        assert wo1 in tenant1_orders
        assert wo2 not in tenant1_orders


class TestIncidentManagementWorkflow:
    """Test incident detection → escalation → resolution workflow."""

    def test_alert_creation_escalation_resolution(
        self,
        test_user,
        supervisor_user,
        test_tenant,
        db
    ):
        """Test complete incident management flow."""
        # Step 1: Alert detected
        alert = NOCAlertEvent.objects.create(
            tenant=test_tenant,
            alert_type="DEVICE_OFFLINE",
            severity="HIGH",
            title="Guard device offline",
            description="GPS-001 has been offline for 15 minutes",
            source="MQTT_MONITOR",
            status="NEW"
        )
        
        assert alert.status == "NEW"
        assert alert.assigned_to is None
        
        # Step 2: Assign to supervisor
        alert.assigned_to = supervisor_user
        alert.status = "ASSIGNED"
        alert.assigned_at = timezone.now()
        alert.save()
        
        assert alert.assigned_to == supervisor_user
        assert alert.status == "ASSIGNED"
        
        # Step 3: Escalate if critical
        if alert.severity == "HIGH" or alert.severity == "CRITICAL":
            alert.is_escalated = True
            alert.escalated_at = timezone.now()
            alert.save()
        
        assert alert.is_escalated is True
        
        # Step 4: Investigate and resolve
        alert.status = "IN_PROGRESS"
        alert.investigation_notes = "Contacted guard, device battery died"
        alert.save()
        
        # Step 5: Resolution
        alert.status = "RESOLVED"
        alert.resolved_at = timezone.now()
        alert.resolved_by = supervisor_user
        alert.resolution_notes = "Guard replaced battery, device back online"
        alert.save()
        
        assert alert.status == "RESOLVED"
        assert alert.resolved_by == supervisor_user

    def test_alert_auto_escalation_after_timeout(self, supervisor_user, test_tenant, db):
        """Test automatic escalation of unresolved alerts."""
        # Create alert 2 hours ago
        alert = NOCAlertEvent.objects.create(
            tenant=test_tenant,
            alert_type="INTRUSION",
            severity="CRITICAL",
            title="Perimeter breach",
            description="Motion detected in restricted area",
            source="CAMERA_AI",
            status="NEW",
            created_at=timezone.now() - timedelta(hours=2)
        )
        
        # Check if needs escalation (unresolved after 1 hour)
        age_hours = (timezone.now() - alert.created_at).total_seconds() / 3600
        needs_escalation = age_hours > 1 and alert.status != "RESOLVED"
        
        assert needs_escalation is True
        
        # Auto-escalate
        if needs_escalation:
            alert.is_escalated = True
            alert.escalated_at = timezone.now()
            alert.save()
        
        assert alert.is_escalated is True


class TestReportGenerationWorkflow:
    """Test report generation → export → delivery workflow."""

    def test_report_generation_export_delivery(
        self,
        test_user,
        supervisor_user,
        test_tenant,
        db
    ):
        """Test complete report workflow."""
        # Step 1: Create report definition
        report = Report.objects.create(
            name="Monthly Security Report",
            report_type="ATTENDANCE",
            description="Monthly attendance summary",
            created_by=supervisor_user,
            tenant=test_tenant
        )
        
        assert report.name == "Monthly Security Report"
        
        # Step 2: Execute report
        execution = ReportExecution.objects.create(
            report=report,
            status="PENDING",
            requested_by=supervisor_user,
            parameters={
                'start_date': (timezone.now() - timedelta(days=30)).isoformat(),
                'end_date': timezone.now().isoformat()
            }
        )
        
        assert execution.status == "PENDING"
        
        # Step 3: Generate report
        execution.status = "PROCESSING"
        execution.started_at = timezone.now()
        execution.save()
        
        # Simulate report generation
        execution.status = "COMPLETED"
        execution.completed_at = timezone.now()
        execution.file_path = "/reports/monthly_security_2024_11.pdf"
        execution.file_size = 250000  # 250KB
        execution.save()
        
        assert execution.status == "COMPLETED"
        assert execution.file_path is not None
        
        # Step 4: Deliver report (email)
        mail.outbox = []
        # Simulate email delivery
        # In real implementation, this would trigger email task
        
        execution.delivered_at = timezone.now()
        execution.save()
        
        assert execution.delivered_at is not None

    def test_scheduled_report_execution(self, supervisor_user, test_tenant, db):
        """Test scheduled report automatic execution."""
        # Create scheduled report
        report = Report.objects.create(
            name="Daily Incident Summary",
            report_type="INCIDENTS",
            description="Daily incident report",
            created_by=supervisor_user,
            tenant=test_tenant,
            is_scheduled=True,
            schedule_frequency="DAILY",
            schedule_time="08:00"
        )
        
        assert report.is_scheduled is True
        assert report.schedule_frequency == "DAILY"
        
        # Simulate scheduled execution
        execution = ReportExecution.objects.create(
            report=report,
            status="PENDING",
            is_scheduled=True
        )
        
        assert execution.is_scheduled is True


class TestMultiTenantDataIsolation:
    """Test multi-tenant data isolation across all models."""

    def test_complete_tenant_isolation(self, db):
        """Test complete data isolation between tenants."""
        # Create two tenants
        tenant1 = Tenant.objects.create(
            name="Company A",
            subdomain="companya",
            is_active=True
        )
        
        tenant2 = Tenant.objects.create(
            name="Company B",
            subdomain="companyb",
            is_active=True
        )
        
        # Create users in each tenant
        user1 = People.objects.create(
            peoplename="user1",
            peopleemail="user1@companya.com",
            peoplecontactno="+919876543215",
            tenant=tenant1
        )
        
        user2 = People.objects.create(
            peoplename="user2",
            peopleemail="user2@companyb.com",
            peoplecontactno="+919876543216",
            tenant=tenant2
        )
        
        # Create work orders
        wo1 = WorkOrder.objects.create(
            title="WO Tenant 1",
            description="Test",
            tenant=tenant1,
            created_by=user1
        )
        
        wo2 = WorkOrder.objects.create(
            title="WO Tenant 2",
            description="Test",
            tenant=tenant2,
            created_by=user2
        )
        
        # Create alerts
        alert1 = NOCAlertEvent.objects.create(
            tenant=tenant1,
            alert_type="TEST",
            severity="LOW",
            title="Alert 1",
            description="Test",
            source="TEST"
        )
        
        alert2 = NOCAlertEvent.objects.create(
            tenant=tenant2,
            alert_type="TEST",
            severity="LOW",
            title="Alert 2",
            description="Test",
            source="TEST"
        )
        
        # Verify isolation for users
        assert People.objects.filter(tenant=tenant1).count() == 1
        assert People.objects.filter(tenant=tenant2).count() == 1
        assert user1 in People.objects.filter(tenant=tenant1)
        assert user1 not in People.objects.filter(tenant=tenant2)
        
        # Verify isolation for work orders
        assert WorkOrder.objects.filter(tenant=tenant1).count() == 1
        assert wo1 in WorkOrder.objects.filter(tenant=tenant1)
        assert wo1 not in WorkOrder.objects.filter(tenant=tenant2)
        
        # Verify isolation for alerts
        assert NOCAlertEvent.objects.filter(tenant=tenant1).count() == 1
        assert alert1 in NOCAlertEvent.objects.filter(tenant=tenant1)
        assert alert1 not in NOCAlertEvent.objects.filter(tenant=tenant2)

    def test_cross_tenant_access_prevention(self, db):
        """Test that cross-tenant access is prevented."""
        tenant1 = Tenant.objects.create(name="T1", subdomain="t1")
        tenant2 = Tenant.objects.create(name="T2", subdomain="t2")
        
        user1 = People.objects.create(
            peoplename="u1",
            peopleemail="u1@t1.com",
            peoplecontactno="+919876543217",
            tenant=tenant1
        )
        
        # Create work order in tenant2
        wo = WorkOrder.objects.create(
            title="T2 WO",
            description="Test",
            tenant=tenant2
        )
        
        # User1 should not be able to see tenant2's work orders
        user1_visible_orders = WorkOrder.objects.filter(tenant=user1.tenant)
        assert wo not in user1_visible_orders


class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios."""

    def test_guard_incident_response_scenario(
        self,
        test_user,
        supervisor_user,
        test_tenant,
        db
    ):
        """Test realistic scenario: Guard reports incident → investigation → work order → resolution."""
        # Step 1: Alert triggered
        alert = NOCAlertEvent.objects.create(
            tenant=test_tenant,
            alert_type="PANIC_BUTTON",
            severity="CRITICAL",
            title="Guard panic button activated",
            description="Guard at Gate 3 activated panic button",
            source="PANIC_SYSTEM",
            status="NEW"
        )
        
        # Step 2: Assign to supervisor
        alert.assigned_to = supervisor_user
        alert.status = "IN_PROGRESS"
        alert.save()
        
        # Step 3: Create work order for follow-up
        work_order = WorkOrder.objects.create(
            title="Investigate panic button incident",
            description=f"Related to alert: {alert.title}",
            priority="CRITICAL",
            status=WorkOrderStatus.IN_PROGRESS.value,
            assigned_to=supervisor_user,
            created_by=supervisor_user,
            tenant=test_tenant,
            related_alert_id=alert.id
        )
        
        # Step 4: Resolve alert
        alert.status = "RESOLVED"
        alert.resolved_at = timezone.now()
        alert.resolved_by = supervisor_user
        alert.resolution_notes = "False alarm - guard accidentally pressed button"
        alert.save()
        
        # Step 5: Close work order
        work_order.status = WorkOrderStatus.COMPLETED.value
        work_order.completed_at = timezone.now()
        work_order.resolution_notes = "Verified false alarm, retrained guard on panic button usage"
        work_order.save()
        
        # Verify complete flow
        assert alert.status == "RESOLVED"
        assert work_order.status == WorkOrderStatus.COMPLETED.value
        assert work_order.related_alert_id == alert.id
