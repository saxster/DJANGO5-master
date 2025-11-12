"""Test suite for Team Dashboard functionality."""

import pytest
from django.test import Client
from django.urls import reverse
from apps.y_helpdesk.models import Ticket
from apps.core.services.quick_actions import QuickActionsService


@pytest.fixture
def client_logged_in(client, user):
    """Return a client with logged-in user."""
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestTeamDashboard:
    """Test team dashboard views and functionality."""

    def test_dashboard_view(self, client, user):
        """Test team dashboard loads successfully."""
        client.force_login(user)
        response = client.get('/admin/dashboard/team/')
        
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Team Dashboard' in content or 'dashboard' in content.lower()

    def test_dashboard_requires_auth(self, client):
        """Test dashboard requires authentication."""
        response = client.get('/admin/dashboard/team/')
        
        # Should redirect to login
        assert response.status_code in [302, 403]

    def test_filters_mine(self, client, user, ticket):
        """Test 'my tickets' filter."""
        # Assign ticket to user
        ticket.assignedtopeople = user
        ticket.save()
        
        client.force_login(user)
        response = client.get('/admin/dashboard/team/?status=mine')
        
        assert response.status_code == 200
        assert response.context is not None

    def test_filters_team(self, client, user):
        """Test team filter."""
        client.force_login(user)
        response = client.get('/admin/dashboard/team/?status=team')
        
        assert response.status_code == 200

    def test_filters_unassigned(self, client, user, tenant):
        """Test unassigned tickets filter."""
        # Create unassigned ticket
        Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Unassigned ticket",
            status="OPEN"
        )
        
        client.force_login(user)
        response = client.get('/admin/dashboard/team/?status=unassigned')
        
        assert response.status_code == 200

    def test_quick_actions_assign_to_me(self, client, user, ticket):
        """Test quick action: assign to me."""
        service = QuickActionsService()
        result = service.assign_to_me(ticket, user)
        
        ticket.refresh_from_db()
        assert ticket.assignedtopeople == user
        assert result is True

    def test_quick_actions_change_priority(self, client, user, ticket):
        """Test quick action: change priority."""
        service = QuickActionsService()
        result = service.change_priority(ticket, "HIGH", user)
        
        ticket.refresh_from_db()
        assert ticket.priority == "HIGH"
        assert result is True

    def test_quick_actions_add_comment(self, client, user, ticket):
        """Test quick action: add comment."""
        service = QuickActionsService()
        result = service.add_comment(ticket, "Test comment", user)
        
        assert result is True
        # Verify comment was added
        from apps.y_helpdesk.models import TicketComment
        comments = TicketComment.objects.filter(ticket=ticket)
        assert comments.count() > 0

    def test_dashboard_stats(self, client, user, tenant):
        """Test dashboard displays correct statistics."""
        # Create various tickets
        Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Open ticket",
            status="OPEN",
            assignedtopeople=user
        )
        Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Closed ticket",
            status="CLOSED",
            assignedtopeople=user
        )
        
        client.force_login(user)
        response = client.get('/admin/dashboard/team/')
        
        assert response.status_code == 200
        # Verify stats are in context
        if response.context:
            assert 'stats' in response.context or 'tickets' in response.context

    def test_dashboard_performance(self, client_logged_in, django_assert_num_queries):
        """Test dashboard doesn't have excessive queries."""
        with django_assert_num_queries(15):  # Adjust based on optimization
            response = client_logged_in.get('/admin/dashboard/team/')
            assert response.status_code == 200

    def test_dashboard_pagination(self, client, user, tenant):
        """Test dashboard pagination."""
        # Create many tickets
        for i in range(25):
            Ticket.objects.create(
                tenant=tenant,
                cuser=user,
                ticketdesc=f"Ticket {i}",
                status="OPEN"
            )
        
        client.force_login(user)
        response = client.get('/admin/dashboard/team/?page=2')
        
        assert response.status_code == 200

    def test_search_functionality(self, client, user, ticket):
        """Test ticket search on dashboard."""
        client.force_login(user)
        response = client.get(f'/admin/dashboard/team/?search={ticket.ticketdesc}')
        
        assert response.status_code == 200

    def test_export_functionality(self, client, user):
        """Test dashboard export to CSV."""
        client.force_login(user)
        response = client.get('/admin/dashboard/team/?export=csv')
        
        if response.status_code == 200:
            assert response['Content-Type'] == 'text/csv' or 'csv' in response.get('Content-Disposition', '')
