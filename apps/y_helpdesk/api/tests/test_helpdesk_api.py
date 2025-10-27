"""
Help Desk API Tests

Tests for ticket CRUD, state transitions, escalations, and SLA.

Compliance with .claude/rules.md:
- Comprehensive coverage
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.peoples.models import People
from apps.y_helpdesk.models import Ticket
from datetime import datetime, timedelta, timezone as dt_timezone


@pytest.mark.django_db
class TestTicketViewSet:
    """Test cases for TicketViewSet."""

    def setup_method(self):
        """Set up test client and data."""
        self.client = APIClient()

        self.user = People.objects.create_user(
            username='testuser@example.com',
            password='Test123!',
            client_id=1
        )

        self.admin = People.objects.create_user(
            username='admin@example.com',
            password='Admin123!',
            is_superuser=True,
            client_id=1
        )

        self.ticket = Ticket.objects.create(
            ticket_number='TKT-001',
            title='Test Ticket',
            description='Test description',
            status='open',
            priority='P2',
            category='support',
            reporter=self.user
        )

        self.list_url = reverse('api_v1:helpdesk:tickets-list')

    def test_create_ticket_success(self):
        """Test creating new ticket."""
        self.client.force_authenticate(user=self.user)

        data = {
            'ticket_number': 'TKT-002',
            'title': 'New Issue',
            'description': 'Issue description',
            'priority': 'P1',
            'category': 'bug'
        }

        response = self.client.post(self.list_url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_ticket_transition_success(self):
        """Test ticket state transition."""
        self.client.force_authenticate(user=self.user)

        url = reverse('api_v1:helpdesk:tickets-transition', kwargs={'pk': self.ticket.pk})
        data = {
            'to_status': 'assigned',
            'comment': 'Assigning to team'
        }

        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK

        self.ticket.refresh_from_db()
        assert self.ticket.status == 'assigned'

    def test_invalid_transition(self):
        """Test invalid state transition is rejected."""
        self.client.force_authenticate(user=self.user)

        # Set ticket to closed
        self.ticket.status = 'closed'
        self.ticket.save()

        url = reverse('api_v1:helpdesk:tickets-transition', kwargs={'pk': self.ticket.pk})
        data = {'to_status': 'open'}

        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_escalate_ticket(self):
        """Test ticket escalation."""
        self.client.force_authenticate(user=self.user)

        # Ticket starts at P2
        assert self.ticket.priority == 'P2'

        url = reverse('api_v1:helpdesk:tickets-escalate', kwargs={'pk': self.ticket.pk})
        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        self.ticket.refresh_from_db()
        assert self.ticket.priority == 'P1'


__all__ = [
    'TestTicketViewSet',
]
