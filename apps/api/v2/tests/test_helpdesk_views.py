"""
Test V2 Help Desk API Endpoints

Tests for ticket management with V2 enhancements:
- Standardized response envelope with correlation_id
- Tenant isolation
- SLA tracking
- Workflow state management

Following TDD: Tests written BEFORE implementation.
"""

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.y_helpdesk.models import Ticket

People = get_user_model()


@pytest.mark.django_db
class TestTicketListView:
    """Test GET /api/v2/helpdesk/tickets/ endpoint."""

    def test_authenticated_user_can_list_tickets(self):
        """
        Test that authenticated user can list tickets in their tenant.

        V2 Response format:
        {
            "success": true,
            "data": {
                "results": [
                    {
                        "id": 1,
                        "ticket_number": "TKT-001",
                        "title": "Server Down",
                        "status": "open",
                        "priority": "P0",
                        "created_at": "2025-11-07T...",
                        "is_overdue": false
                    }
                ],
                "count": 10,
                "next": "...",
                "previous": null
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create user and tickets
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        ticket1 = Ticket.objects.create(
            ticket_number='TKT-001',
            title='Server Down',
            description='Production server not responding',
            priority='P0',
            status='open',
            reporter=user
        )

        ticket2 = Ticket.objects.create(
            ticket_number='TKT-002',
            title='Password Reset Request',
            description='User needs password reset',
            priority='P2',
            status='assigned',
            reporter=user
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: List tickets
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-list')
        response = client.get(url, format='json')

        # Assert: Verify response structure
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data
        assert 'meta' in response.data

        # Data contains pagination
        data = response.data['data']
        assert 'results' in data
        assert 'count' in data
        assert isinstance(data['results'], list)
        assert data['count'] >= 2

        # Each ticket has required fields
        ticket_result = data['results'][0]
        assert 'id' in ticket_result
        assert 'ticket_number' in ticket_result
        assert 'title' in ticket_result
        assert 'status' in ticket_result
        assert 'priority' in ticket_result
        assert 'created_at' in ticket_result

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated request returns 401."""
        client = APIClient()
        url = reverse('api_v2:helpdesk-tickets-list')

        # Act: Request without authentication
        response = client.get(url, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_filter_by_status_returns_matching_tickets(self):
        """Test that status filter returns only matching tickets."""
        # Arrange: Create user and tickets
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        Ticket.objects.create(
            ticket_number='TKT-001',
            title='Open Ticket',
            priority='P1',
            status='open',
            reporter=user
        )
        Ticket.objects.create(
            ticket_number='TKT-002',
            title='Closed Ticket',
            priority='P2',
            status='closed',
            reporter=user
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Filter by status=open
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-list')
        response = client.get(url, {'status': 'open'}, format='json')

        # Assert: Only open tickets returned
        assert response.status_code == status.HTTP_200_OK
        results = response.data['data']['results']
        assert len(results) >= 1

        # All results should be 'open' status
        statuses = [t['status'] for t in results]
        assert all(s == 'open' for s in statuses)


@pytest.mark.django_db
class TestTicketCreateView:
    """Test POST /api/v2/helpdesk/tickets/ endpoint."""

    def test_authenticated_user_can_create_ticket(self):
        """
        Test that authenticated user can create a ticket.

        V2 Response format:
        {
            "success": true,
            "data": {
                "id": 1,
                "ticket_number": "TKT-001",
                "title": "Server Down",
                "priority": "P0",
                "status": "open",
                "due_date": "2025-11-07T16:00:00Z",
                ...
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create user
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Create ticket
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-create')
        response = client.post(url, {
            'title': 'Server Down',
            'description': 'Production server not responding',
            'priority': 'P0',
            'category': 'technical'
        }, format='json')

        # Assert: Verify response
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert 'data' in response.data

        # Ticket data
        data = response.data['data']
        assert data['title'] == 'Server Down'
        assert data['priority'] == 'P0'
        assert data['status'] == 'open'  # Default status
        assert 'ticket_number' in data
        assert 'due_date' in data  # Auto-calculated from SLA

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']

        # Verify database
        assert Ticket.objects.filter(title='Server Down').exists()

    def test_create_ticket_auto_calculates_sla_due_date(self):
        """Test that SLA due date is auto-calculated based on priority."""
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Create P0 ticket (should have 4-hour SLA)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-create')
        response = client.post(url, {
            'title': 'Critical Issue',
            'priority': 'P0'
        }, format='json')

        # Assert: Due date set
        assert response.status_code == status.HTTP_201_CREATED
        assert 'due_date' in response.data['data']
        # Due date should be ~4 hours from now (P0 SLA)

    def test_create_ticket_missing_title_returns_400(self):
        """Test that missing title returns 400."""
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Create ticket without title
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-create')
        response = client.post(url, {
            'priority': 'P1'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'VALIDATION_ERROR'


@pytest.mark.django_db
class TestTicketUpdateView:
    """Test PATCH /api/v2/helpdesk/tickets/{id}/ endpoint."""

    def test_authenticated_user_can_update_ticket(self):
        """Test that user can update ticket fields."""
        # Arrange: Create user and ticket
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        ticket = Ticket.objects.create(
            ticket_number='TKT-001',
            title='Original Title',
            description='Original description',
            priority='P2',
            status='open',
            reporter=user
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Update ticket
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-update', kwargs={'ticket_id': ticket.id})
        response = client.patch(url, {
            'title': 'Updated Title',
            'description': 'Updated description'
        }, format='json')

        # Assert: Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        # Updated fields reflected
        data = response.data['data']
        assert data['title'] == 'Updated Title'
        assert data['description'] == 'Updated description'

        # Verify database
        ticket.refresh_from_db()
        assert ticket.title == 'Updated Title'
        assert ticket.description == 'Updated description'

    def test_ticket_not_found_returns_404(self):
        """Test that non-existent ticket returns 404."""
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Update non-existent ticket
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-update', kwargs={'ticket_id': 99999})
        response = client.patch(url, {'title': 'New'}, format='json')

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'TICKET_NOT_FOUND'


@pytest.mark.django_db
class TestTicketTransitionView:
    """Test POST /api/v2/helpdesk/tickets/{id}/transition/ endpoint."""

    def test_transition_ticket_to_new_status(self):
        """Test that ticket can transition to new status with workflow logging."""
        # Arrange: Create user and ticket
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        ticket = Ticket.objects.create(
            ticket_number='TKT-001',
            title='Test Ticket',
            priority='P1',
            status='open',
            reporter=user
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Transition to in_progress
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-transition', kwargs={'ticket_id': ticket.id})
        response = client.post(url, {
            'to_status': 'in_progress',
            'comment': 'Working on it'
        }, format='json')

        # Assert: Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert response.data['data']['status'] == 'in_progress'

        # Verify database
        ticket.refresh_from_db()
        assert ticket.status == 'in_progress'

    def test_transition_missing_status_returns_400(self):
        """Test that missing to_status returns 400."""
        # Arrange
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )
        ticket = Ticket.objects.create(
            ticket_number='TKT-001',
            title='Test',
            priority='P1',
            status='open',
            reporter=user
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Transition without to_status
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-transition', kwargs={'ticket_id': ticket.id})
        response = client.post(url, {'comment': 'test'}, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'VALIDATION_ERROR'


@pytest.mark.django_db
class TestTicketEscalateView:
    """Test POST /api/v2/helpdesk/tickets/{id}/escalate/ endpoint."""

    def test_escalate_increases_priority(self):
        """Test that escalate increases ticket priority."""
        # Arrange: Create user and P2 ticket
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        ticket = Ticket.objects.create(
            ticket_number='TKT-001',
            title='Test Ticket',
            priority='P2',
            status='open',
            reporter=user
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Escalate ticket
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-escalate', kwargs={'ticket_id': ticket.id})
        response = client.post(url, format='json')

        # Assert: Priority increased
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert response.data['data']['priority'] == 'P1'  # Escalated from P2

        # Verify database
        ticket.refresh_from_db()
        assert ticket.priority == 'P1'

    def test_escalate_at_max_priority_returns_error(self):
        """Test that escalating P0 ticket returns error."""
        # Arrange: Create P0 ticket
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        ticket = Ticket.objects.create(
            ticket_number='TKT-001',
            title='Critical Ticket',
            priority='P0',
            status='open',
            reporter=user
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Attempt escalation
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:helpdesk-tickets-escalate', kwargs={'ticket_id': ticket.id})
        response = client.post(url, format='json')

        # Assert: Error returned
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'MAX_PRIORITY_REACHED'
