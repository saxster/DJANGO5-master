"""Performance tests for admin enhancement features."""

import pytest
from django.test.utils import override_settings
from django.utils import timezone
from apps.y_helpdesk.models import Ticket
from apps.core.services.activity_timeline_service import ActivityTimelineService
from apps.attendance.models import Attendance


@pytest.mark.django_db
class TestPerformance:
    """Performance and query optimization tests."""

    def test_dashboard_query_count(self, client, user, django_assert_num_queries):
        """Test team dashboard doesn't have N+1 queries."""
        client.force_login(user)
        
        # Dashboard should use select_related/prefetch_related
        with django_assert_num_queries(15):  # Adjust based on optimization
            response = client.get('/admin/dashboard/team/')
            assert response.status_code == 200

    def test_timeline_performance(self, person_with_activity, django_assert_max_num_queries):
        """Test timeline is performant with optimized queries."""
        service = ActivityTimelineService()
        
        with django_assert_max_num_queries(20):
            events = service.get_person_timeline(person_with_activity)
            assert len(events) > 0

    def test_smart_assignment_with_many_agents(self, tenant, user):
        """Test smart assignment performance with many agents."""
        from django.contrib.auth import get_user_model
        from apps.y_helpdesk.models import TicketCategory
        from apps.peoples.models import AgentSkill
        from apps.core.services.smart_assignment_service import SmartAssignmentService
        
        User = get_user_model()
        category = TicketCategory.objects.create(
            tenant=tenant,
            name="Support"
        )
        
        # Create many agents with skills
        agents = []
        for i in range(50):
            agent = User.objects.create_user(
                username=f"agent{i}",
                email=f"agent{i}@test.com",
                tenant=tenant
            )
            agents.append(agent)
            
            AgentSkill.objects.create(
                agent=agent,
                category=category,
                skill_level=(i % 5) + 1,
                tickets_resolved=i * 10
            )
        
        # Create ticket
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Test assignment",
            category=category,
            status="OPEN"
        )
        
        # Should complete in reasonable time
        import time
        start = time.time()
        suggestions = SmartAssignmentService.suggest_assignee(ticket)
        duration = time.time() - start
        
        assert len(suggestions) > 0
        assert duration < 1.0  # Should complete in under 1 second

    def test_bulk_operations_performance(self, tenant, user):
        """Test bulk operations are optimized."""
        from apps.core.services.approval_service import ApprovalService
        
        # Create many tickets
        tickets = []
        for i in range(100):
            ticket = Ticket.objects.create(
                tenant=tenant,
                cuser=user,
                ticketdesc=f"Bulk test {i}",
                status="OPEN"
            )
            tickets.append(ticket.id)
        
        # Bulk operation should use optimized queries
        import time
        start = time.time()
        
        # Simulate bulk status update
        Ticket.objects.filter(id__in=tickets[:50]).update(status="CLOSED")
        
        duration = time.time() - start
        assert duration < 0.5  # Should be fast

    def test_priority_alert_calculation_performance(self, tenant, user):
        """Test priority alert calculation is fast."""
        from apps.y_helpdesk.services.priority_alert_service import PriorityAlertService
        
        # Create many tickets
        tickets = []
        for i in range(20):
            ticket = Ticket.objects.create(
                tenant=tenant,
                cuser=user,
                ticketdesc=f"Priority test {i}",
                priority="HIGH",
                status="OPEN"
            )
            tickets.append(ticket)
        
        service = PriorityAlertService()
        
        # Calculate risk for all tickets
        import time
        start = time.time()
        
        for ticket in tickets:
            risk = service.check_ticket_risk(ticket)
            assert 'risk_level' in risk
        
        duration = time.time() - start
        assert duration < 2.0  # Should process 20 tickets in under 2 seconds

    def test_saved_view_export_performance(self, tenant, user):
        """Test export generation is optimized."""
        from apps.core.models import DashboardSavedView
        from apps.core.services.view_export_service import ViewExportService
        
        # Create many tickets
        for i in range(100):
            Ticket.objects.create(
                tenant=tenant,
                cuser=user,
                ticketdesc=f"Export test {i}",
                priority="HIGH",
                status="OPEN"
            )
        
        saved_view = DashboardSavedView.objects.create(
            tenant=tenant,
            cuser=user,
            name="Large Export",
            view_type='TICKETS',
            filters={'priority': 'HIGH'},
            page_url='/admin/y_helpdesk/ticket/'
        )
        
        # Export should use streaming/chunking
        import time
        start = time.time()
        
        result = ViewExportService.generate_export(saved_view, format='CSV')
        
        duration = time.time() - start
        assert result is not None
        assert duration < 3.0  # Should export 100 records in under 3 seconds

    def test_timeline_with_large_history(self, tenant, user):
        """Test timeline performance with extensive history."""
        service = ActivityTimelineService()
        
        # Create extensive activity history
        for i in range(100):
            Ticket.objects.create(
                tenant=tenant,
                cuser=user,
                ticketdesc=f"History ticket {i}",
                status="OPEN"
            )
        
        for i in range(50):
            Attendance.objects.create(
                tenant=tenant,
                people=user,
                attendance_date=timezone.now().date(),
                check_in=timezone.now()
            )
        
        # Timeline should use pagination/limiting
        import time
        start = time.time()
        
        events = service.get_person_timeline(user, limit=50)
        
        duration = time.time() - start
        assert len(events) <= 50
        assert duration < 1.0  # Should be fast with limit

    @override_settings(DEBUG=True)
    def test_query_optimization_with_debug(self, client, user, django_assert_max_num_queries):
        """Test query count with DEBUG=True to catch all queries."""
        from django.db import connection
        from django.test.utils import override_settings
        
        client.force_login(user)
        
        # Reset queries
        connection.queries_log.clear()
        
        response = client.get('/admin/dashboard/team/')
        
        # Should have reasonable number of queries
        query_count = len(connection.queries)
        assert query_count < 30  # Adjust based on actual optimization

    def test_concurrent_access_performance(self, tenant):
        """Test system handles concurrent access."""
        from django.contrib.auth import get_user_model
        from threading import Thread
        import time
        
        User = get_user_model()
        
        # Create multiple users
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f"concurrent{i}",
                email=f"concurrent{i}@test.com",
                tenant=tenant
            )
            users.append(user)
        
        # Function to create tickets
        def create_tickets(user):
            for i in range(10):
                Ticket.objects.create(
                    tenant=tenant,
                    cuser=user,
                    ticketdesc=f"Concurrent {i}",
                    status="OPEN"
                )
        
        # Run concurrent operations
        threads = []
        start = time.time()
        
        for user in users:
            thread = Thread(target=create_tickets, args=(user,))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
        
        duration = time.time() - start
        
        # Should handle concurrent operations efficiently
        assert duration < 5.0
        assert Ticket.objects.filter(tenant=tenant).count() == 50
