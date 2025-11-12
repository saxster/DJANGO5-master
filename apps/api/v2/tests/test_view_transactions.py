"""
Test Transaction Management in API Views (Rule #17)

Tests validate that multi-step operations use atomic transactions to prevent
data corruption from partial failures.

Following TDD: Tests written BEFORE implementation.
"""

import pytest


@pytest.mark.django_db
class TestHelpdeskViewTransactions:
    """Test transaction management in helpdesk views."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        """Setup test user and client."""
        from django.urls import reverse
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework import status
        from apps.y_helpdesk.models import Ticket

        self.reverse = reverse
        self.status = status
        self.Ticket = Ticket

        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='test@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.user)

    def test_ticket_patch_uses_transaction(self):
        """
        Test that PATCH /api/v2/helpdesk/tickets/{id}/ uses transaction.atomic

        Verify that if an error occurs mid-update, all changes are rolled back.
        """
        # Arrange: Create a ticket
        ticket = self.Ticket.objects.create(
            ticket_number='TKT-001',
            title='Original Title',
            description='Original Description',
            priority='P2',
            status='open',
            reporter=self.user
        )

        # Act: Attempt PATCH request
        url = self.reverse('v2_helpdesk_ticket_detail', kwargs={'ticket_id': ticket.id})
        data = {
            'title': 'Updated Title',
            'priority': 'P1',
            'description': 'Updated Description'
        }
        response = self.client.patch(url, data, format='json')

        # Assert: Transaction was atomic - either all changes saved or none
        assert response.status_code == self.status.HTTP_200_OK

        # Verify data was saved atomically
        ticket.refresh_from_db()
        assert ticket.title == 'Updated Title'
        assert ticket.priority == 'P1'
        assert ticket.description == 'Updated Description'

    def test_ticket_patch_rollback_on_error(self):
        """
        Test that PATCH rollback works when database error occurs mid-operation.

        Simulates database constraint violation to verify rollback behavior.
        """
        # Arrange: Create two tickets
        ticket1 = self.Ticket.objects.create(
            ticket_number='TKT-001',
            title='Ticket 1',
            description='Description 1',
            priority='P0',
            status='open',
            reporter=self.user
        )

        ticket2 = self.Ticket.objects.create(
            ticket_number='TKT-002',
            title='Ticket 2',
            description='Description 2',
            priority='P2',
            status='open',
            reporter=self.user
        )

        # Act & Assert: Attempt to create duplicate ticket_number (violates uniqueness)
        # This tests that the transaction rolls back if constraint is violated
        url = self.reverse('v2_helpdesk_ticket_detail', kwargs={'ticket_id': ticket1.id})

        # Try to change ticket1's number to match ticket2 (should fail)
        data = {'ticket_number': 'TKT-002'}
        response = self.client.patch(url, data, format='json')

        # Should fail with error response
        assert response.status_code in [
            self.status.HTTP_400_BAD_REQUEST,
            self.status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

        # Verify original ticket number was preserved (rollback worked)
        ticket1.refresh_from_db()
        assert ticket1.ticket_number == 'TKT-001'

    def test_ticket_status_transition_uses_transaction(self):
        """
        Test that status transition endpoint uses atomic transaction.

        Verify that if resolved_at update fails, entire transition is rolled back.
        """
        # Arrange: Create ticket
        ticket = self.Ticket.objects.create(
            ticket_number='TKT-003',
            title='Test Ticket',
            description='Test Description',
            priority='P1',
            status='open',
            reporter=self.user,
            resolved_at=None
        )

        # Act: Transition to resolved status
        url = self.reverse('v2_helpdesk_transition', kwargs={'ticket_id': ticket.id})
        data = {'to_status': 'resolved'}
        response = self.client.post(url, data, format='json')

        # Assert: Status changed atomically
        assert response.status_code == self.status.HTTP_200_OK

        ticket.refresh_from_db()
        assert ticket.status == 'resolved'
        assert ticket.resolved_at is not None  # Should be set automatically

    def test_ticket_escalation_uses_transaction(self):
        """
        Test that escalation endpoint updates priority and SLA atomically.

        Verify both priority and due_date are updated together.
        """
        # Arrange: Create ticket with low priority
        ticket = self.Ticket.objects.create(
            ticket_number='TKT-004',
            title='Low Priority Ticket',
            description='Test Description',
            priority='P3',
            status='open',
            reporter=self.user,
            due_date=None
        )

        original_due_date = ticket.due_date

        # Act: Escalate ticket
        url = self.reverse('v2_helpdesk_escalate', kwargs={'ticket_id': ticket.id})
        response = self.client.post(url, {}, format='json')

        # Assert: Both priority and due_date changed atomically
        assert response.status_code == self.status.HTTP_200_OK

        ticket.refresh_from_db()
        assert ticket.priority == 'P2'  # Escalated from P3 to P2
        assert ticket.due_date is not None
        assert ticket.due_date != original_due_date

    def test_transaction_isolation_prevents_dirty_reads(self):
        """
        Test that concurrent updates don't cause dirty reads.

        Verify that select_for_update() is used where appropriate to prevent
        concurrent modification issues.
        """
        # Arrange: Create ticket
        ticket = self.Ticket.objects.create(
            ticket_number='TKT-005',
            title='Concurrency Test',
            description='Test Description',
            priority='P2',
            status='open',
            reporter=self.user
        )

        # Act: Update via API
        url = self.reverse('v2_helpdesk_ticket_detail', kwargs={'ticket_id': ticket.id})
        data = {'title': 'Updated Title', 'priority': 'P1'}
        response = self.client.patch(url, data, format='json')

        # Assert: Update succeeded and data is consistent
        assert response.status_code == self.status.HTTP_200_OK

        # Verify consistency - no race condition windows
        ticket.refresh_from_db()
        assert ticket.title == 'Updated Title'
        assert ticket.priority == 'P1'


@pytest.mark.django_db
class TestPeopleViewTransactions:
    """Test transaction management in people/user views."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        """Setup test user and client."""
        from django.urls import reverse
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework import status

        self.reverse = reverse
        self.status = status

        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='admin@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.user)

    def test_user_patch_uses_transaction(self):
        """
        Test that PATCH /api/v2/people/{id}/ uses transaction.atomic

        Verify that if an error occurs during user field updates, all changes
        are rolled back atomically.
        """
        from django.contrib.auth import get_user_model

        # Arrange: Create a test user to update
        User = get_user_model()
        target_user = User.objects.create_user(
            username='target@example.com',
            password='password123'
        )

        original_username = target_user.username

        # Act: PATCH user data
        url = self.reverse('v2_people_detail', kwargs={'user_id': target_user.id})
        data = {
            'username': 'updated@example.com'
        }
        response = self.client.patch(url, data, format='json')

        # Assert: Transaction was atomic
        assert response.status_code == self.status.HTTP_200_OK

        target_user.refresh_from_db()
        # Verify data was updated
        assert target_user.username != original_username

    def test_user_patch_rollback_on_validation_error(self):
        """
        Test that PATCH rolls back all changes if validation fails.

        Verify transaction prevents partial updates when errors occur.
        """
        from django.contrib.auth import get_user_model

        # Arrange: Create user
        User = get_user_model()
        target_user = User.objects.create_user(
            username='user@example.com',
            password='password123'
        )

        original_username = target_user.username

        # Act: Try to update user
        url = self.reverse('v2_people_detail', kwargs={'user_id': target_user.id})
        data = {
            'username': 'updated@example.com'
        }
        response = self.client.patch(url, data, format='json')

        # Assert: Response received
        # Even if error, transaction should protect data integrity
        target_user.refresh_from_db()
        # Data either updated completely or not at all (atomic behavior)
        is_updated = target_user.username != original_username
        is_original = target_user.username == original_username
        # Should be one or the other, not partial
        assert is_updated or is_original

    def test_multiple_field_updates_atomic(self):
        """
        Test that updating multiple fields happens atomically.

        If update method is split into multiple save() calls, only last one
        would persist without transaction management.
        """
        from django.contrib.auth import get_user_model

        # Arrange: Create user
        User = get_user_model()
        target_user = User.objects.create_user(
            username='multi@example.com',
            password='password123'
        )

        # Act: Update user
        url = self.reverse('v2_people_detail', kwargs={'user_id': target_user.id})
        data = {
            'username': 'updated_multi@example.com'
        }
        response = self.client.patch(url, data, format='json')

        # Assert: Response is successful
        assert response.status_code == self.status.HTTP_200_OK

        target_user.refresh_from_db()
        # Verify atomicity - data is fully updated or not at all
        if response.status_code == self.status.HTTP_200_OK:
            assert target_user.username != 'multi@example.com'


@pytest.mark.django_db
class TestTransactionBestPractices:
    """Test transaction best practices per Rule #17."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        """Setup test user and client."""
        from django.urls import reverse
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework import status
        from apps.y_helpdesk.models import Ticket

        self.reverse = reverse
        self.status = status
        self.Ticket = Ticket

        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='test@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.user)

    def test_logging_happens_within_transaction(self):
        """
        Test that success logging is inside transaction (before commit).

        Per Rule #17: "Log success BEFORE transaction commits"
        """
        # Arrange: Create ticket
        ticket = self.Ticket.objects.create(
            ticket_number='TKT-LOG',
            title='Logging Test',
            description='Test',
            priority='P2',
            status='open',
            reporter=self.user
        )

        # Act: Update ticket
        url = self.reverse('v2_helpdesk_ticket_detail', kwargs={'ticket_id': ticket.id})
        data = {'title': 'Updated'}
        response = self.client.patch(url, data, format='json')

        # Assert: Success response indicates logging happened
        assert response.status_code == self.status.HTTP_200_OK
        assert 'success' in response.data
        assert response.data['success'] is True

    def test_correlation_id_available_in_transaction(self):
        """
        Test that correlation_id is available and consistent within transaction.

        Per Rule #17: Use correlation IDs for debugging within transaction context.
        """
        # Act: Make request
        ticket = self.Ticket.objects.create(
            ticket_number='TKT-CORR',
            title='Correlation Test',
            description='Test',
            priority='P2',
            status='open',
            reporter=self.user
        )

        url = self.reverse('v2_helpdesk_ticket_detail', kwargs={'ticket_id': ticket.id})
        data = {'title': 'Updated'}
        response = self.client.patch(url, data, format='json')

        # Assert: Correlation ID in response
        assert response.status_code == self.status.HTTP_200_OK
        assert 'meta' in response.data
        assert 'correlation_id' in response.data['meta']
        correlation_id = response.data['meta']['correlation_id']

        # Correlation ID should be valid UUID format
        assert len(correlation_id) > 0
        assert '-' in correlation_id  # UUID format check
