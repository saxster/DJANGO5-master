"""Integration tests for admin enhancement features."""

import pytest
from django.utils import timezone
from datetime import timedelta
from apps.y_helpdesk.models import Ticket, TicketCategory
from apps.core.models import Runbook
from apps.core.services.smart_assignment_service import SmartAssignmentService
from apps.y_helpdesk.services.priority_alert_service import PriorityAlertService
from apps.core.services.quick_action_service import QuickActionService
from apps.peoples.models import AgentSkill


@pytest.mark.django_db
class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow(self, client, user, tenant):
        """Test complete workflow: create ticket -> suggest -> assign -> alert."""
        # 1. Create ticket category and skilled agent
        category = TicketCategory.objects.create(
            tenant=tenant,
            name="Network",
            description="Network issues"
        )
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        agent = User.objects.create_user(
            username="network_expert",
            email="expert@test.com",
            tenant=tenant
        )
        
        AgentSkill.objects.create(
            agent=agent,
            category=category,
            skill_level=5,
            certified=True,
            tickets_resolved=100
        )
        
        # 2. Create urgent ticket
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Network outage",
            category=category,
            priority="URGENT",
            status="OPEN",
            sla_due=timezone.now() + timedelta(hours=2)
        )
        
        # 3. Get smart assignment suggestions
        suggestions = SmartAssignmentService.suggest_assignee(ticket)
        assert len(suggestions) > 0
        assert suggestions[0]['agent'] == agent
        
        # 4. Auto-assign
        SmartAssignmentService.auto_assign(ticket)
        ticket.refresh_from_db()
        assert ticket.assignedtopeople == agent
        
        # 5. Check for priority alerts
        risk = PriorityAlertService.check_ticket_risk(ticket)
        assert 'risk_level' in risk
        assert risk['risk_level'] in ['medium', 'high']
        
        # 6. Apply quick action
        runbook = Runbook.objects.create(
            tenant=tenant,
            cuser=user,
            name="Escalation Runbook",
            automated_steps=[
                {"action_type": "add_tag", "value": "escalated"}
            ]
        )
        
        result = QuickActionService.execute_action(runbook, ticket, user)
        assert result['success'] is True

    def test_approval_to_execution_workflow(self, tenant, user):
        """Test approval workflow from request to execution."""
        from apps.core.services.approval_service import ApprovalService
        from apps.core.models import ApprovalGroup
        from apps.peoples.models import Pgroup
        
        # 1. Create approval group and approver
        pgroup = Pgroup.objects.create(tenant=tenant, name="Approvers")
        approval_group = ApprovalGroup.objects.create(
            tenant=tenant,
            name="Data Approvers",
            pgroup=pgroup,
            min_approvals=1
        )
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        approver = User.objects.create_user(
            username="approver",
            email="approver@test.com",
            tenant=tenant
        )
        pgroup.people.add(approver)
        
        # 2. Create approval request
        request = ApprovalService.create_approval_request(
            user=user,
            action_type="Bulk Delete",
            target_model="Ticket",
            target_ids=[1, 2, 3],
            reason="Cleanup",
            approval_group=approval_group
        )
        
        assert request.status == 'PENDING'
        
        # 3. Approve request
        ApprovalService.approve_request(request, approver, "Approved")
        request.refresh_from_db()
        assert request.status == 'APPROVED'
        
        # 4. Execute approved action
        result = ApprovalService.execute_approved_action(request)
        assert result['success'] is True

    def test_dashboard_to_action_workflow(self, client, user, tenant):
        """Test workflow from dashboard view to ticket action."""
        # 1. Login and access dashboard
        client.force_login(user)
        response = client.get('/admin/dashboard/team/')
        assert response.status_code == 200
        
        # 2. Create and filter tickets
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Dashboard test",
            priority="HIGH",
            status="OPEN"
        )
        
        # 3. Apply filter
        response = client.get('/admin/dashboard/team/?priority=HIGH')
        assert response.status_code == 200
        
        # 4. Quick action: assign to me
        from apps.core.services.quick_actions import QuickActionsService
        service = QuickActionsService()
        result = service.assign_to_me(ticket, user)
        
        ticket.refresh_from_db()
        assert ticket.assignedtopeople == user

    def test_timeline_generation_workflow(self, tenant, user):
        """Test timeline generation with multiple activity types."""
        from apps.core.services.activity_timeline_service import ActivityTimelineService
        from apps.attendance.models import Attendance
        
        # 1. Create various activities
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Timeline test",
            status="OPEN"
        )
        
        Attendance.objects.create(
            tenant=tenant,
            people=user,
            attendance_date=timezone.now().date(),
            check_in=timezone.now()
        )
        
        # 2. Generate timeline
        service = ActivityTimelineService()
        events = service.get_person_timeline(user)
        
        # 3. Verify all activity types are included
        assert len(events) >= 2
        event_types = {e['type'] for e in events}
        assert 'ticket_created' in event_types or 'attendance' in event_types

    def test_saved_view_to_export_workflow(self, tenant, user):
        """Test workflow from saving view to scheduled export."""
        from apps.core.models import DashboardSavedView
        from apps.core.services.view_export_service import ViewExportService
        
        # 1. Create tickets
        for i in range(5):
            Ticket.objects.create(
                tenant=tenant,
                cuser=user,
                ticketdesc=f"Export test {i}",
                priority="HIGH",
                status="OPEN"
            )
        
        # 2. Save view with filters
        saved_view = DashboardSavedView.objects.create(
            tenant=tenant,
            cuser=user,
            name="High Priority Report",
            view_type='TICKETS',
            filters={'priority': 'HIGH'},
            page_url='/admin/y_helpdesk/ticket/'
        )
        
        # 3. Generate export
        result = ViewExportService.generate_export(saved_view, format='CSV')
        assert result is not None
        
        # 4. Schedule recurring export
        task = ViewExportService.schedule_export(
            saved_view,
            frequency='DAILY',
            recipients=['manager@test.com']
        )
        assert task is not None

    def test_multi_tenant_isolation(self, user):
        """Test multi-tenant data isolation in workflows."""
        from apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Create two tenants
        tenant1 = Tenant.objects.create(name="Tenant 1")
        tenant2 = Tenant.objects.create(name="Tenant 2")
        
        # Create users for each tenant
        user1 = User.objects.create_user(
            username="user1",
            email="user1@test.com",
            tenant=tenant1
        )
        
        user2 = User.objects.create_user(
            username="user2",
            email="user2@test.com",
            tenant=tenant2
        )
        
        # Create tickets for each tenant
        ticket1 = Ticket.objects.create(
            tenant=tenant1,
            cuser=user1,
            ticketdesc="Tenant 1 ticket",
            status="OPEN"
        )
        
        ticket2 = Ticket.objects.create(
            tenant=tenant2,
            cuser=user2,
            ticketdesc="Tenant 2 ticket",
            status="OPEN"
        )
        
        # Verify isolation
        tenant1_tickets = Ticket.objects.filter(tenant=tenant1)
        assert ticket1 in tenant1_tickets
        assert ticket2 not in tenant1_tickets

    def test_error_handling_workflow(self, tenant, user):
        """Test error handling in integrated workflows."""
        # 1. Try to assign non-existent ticket
        with pytest.raises(Ticket.DoesNotExist):
            SmartAssignmentService.auto_assign(
                Ticket.objects.get(id=999999)
            )
        
        # 2. Try to execute runbook with invalid user
        runbook = Runbook.objects.create(
            tenant=tenant,
            cuser=user,
            name="Test",
            automated_steps=[]
        )
        
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Test",
            status="OPEN"
        )
        
        # Invalid user should fail gracefully
        result = QuickActionService.execute_action(runbook, ticket, None)
        assert result['success'] is False
