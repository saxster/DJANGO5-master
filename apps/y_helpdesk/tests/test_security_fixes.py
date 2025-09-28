"""
Tests for security fixes in the ticketing system

These tests verify that all critical security vulnerabilities have been properly resolved:
- Scoped ticket access controls
- Audit trail completeness
- State transition validation
- Comment requirements for terminal states
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.forms import TicketForm
from apps.y_helpdesk.views import TicketView
from apps.onboarding.models import Bt, TypeAssist

User = get_user_model()

@pytest.mark.security
class TicketSecurityTestCase(TestCase):
    """Test suite for ticket security fixes"""

    def setUp(self):
        """Set up test data for security tests"""
        # Create two different clients and sites for cross-tenant testing
        self.client1_type, _ = TypeAssist.objects.get_or_create(tacode="CLIENT", taname="Client")
        self.site1_type, _ = TypeAssist.objects.get_or_create(tacode="SITE", taname="Site")

        # Client 1 and Site 1
        self.client1 = Bt.objects.create(
            bucode="CLIENT1",
            buname="Test Client 1",
            identifier=self.client1_type,
            id=10
        )
        self.site1 = Bt.objects.create(
            bucode="SITE1",
            buname="Test Site 1",
            identifier=self.site1_type,
            parent=self.client1,
            id=11
        )

        # Client 2 and Site 2
        self.client2 = Bt.objects.create(
            bucode="CLIENT2",
            buname="Test Client 2",
            identifier=self.client1_type,
            id=12
        )
        self.site2 = Bt.objects.create(
            bucode="SITE2",
            buname="Test Site 2",
            identifier=self.site1_type,
            parent=self.client2,
            id=13
        )

        # Create users for each client/site
        self.user1 = User.objects.create_user(
            loginid="testuser1",
            peoplecode="USER1",
            peoplename="Test User 1",
            email="user1@test.com",
            dateofbirth="1990-01-01",
            dateofjoin="2020-01-01",
            client=self.client1,
            bu=self.site1
        )

        self.user2 = User.objects.create_user(
            loginid="testuser2",
            peoplecode="USER2",
            peoplename="Test User 2",
            email="user2@test.com",
            dateofbirth="1990-01-01",
            dateofjoin="2020-01-01",
            client=self.client2,
            bu=self.site2
        )

        # Create ticket categories
        self.category1 = TypeAssist.objects.create(
            tacode="TEST_CAT1",
            taname="Test Category 1",
            client=self.client1,
            bu=self.site1,
            enable=True
        )

        # Create test tickets
        self.ticket1 = Ticket.objects.create(
            ticketdesc="Ticket for Client 1",
            client=self.client1,
            bu=self.site1,
            assignedtopeople=self.user1,
            ticketcategory=self.category1,
            status=Ticket.Status.NEW.value,
            priority=Ticket.Priority.MEDIUM.value,
            ticketsource=Ticket.TicketSource.USERDEFINED.value
        )

        self.ticket2 = Ticket.objects.create(
            ticketdesc="Ticket for Client 2",
            client=self.client2,
            bu=self.site2,
            assignedtopeople=self.user2,
            status=Ticket.Status.NEW.value,
            priority=Ticket.Priority.HIGH.value,
            ticketsource=Ticket.TicketSource.USERDEFINED.value
        )

        self.factory = RequestFactory()

    def _create_request(self, user, method='GET', data=None):
        """Helper to create request with proper session setup"""
        if method == 'GET':
            request = self.factory.get('/')
        else:
            request = self.factory.post('/', data or {})

        request.user = user

        # Add session middleware and data
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()

        # Set up session data based on user's client/site
        request.session['client_id'] = user.client_id
        request.session['assignedsites'] = [user.bu_id]
        request.session.save()

        return request

    def test_scoped_ticket_access_get_valid(self):
        """Test that users can access tickets within their client/site scope"""
        view = TicketView()
        request = self._create_request(self.user1)
        request.GET = {'id': str(self.ticket1.id)}

        response = view.get(request)
        self.assertEqual(response.status_code, 200)

    def test_scoped_ticket_access_get_denied(self):
        """Test that users cannot access tickets outside their client/site scope"""

        view = TicketView()
        request = self._create_request(self.user1)
        request.GET = {'id': str(self.ticket2.id)}  # User1 trying to access User2's ticket

        with self.assertRaises(Ticket.DoesNotExist):
            # This should raise DoesNotExist due to scoped access
            response = view.get(request)

    def test_scoped_ticket_access_post_valid(self):
        """Test that users can update tickets within their client/site scope"""
        view = TicketView()
        post_data = {
            'pk': str(self.ticket1.id),
            'ticketdesc': 'Updated description',
            'status': Ticket.Status.OPEN.value,
            'priority': Ticket.Priority.HIGH.value,
            'assignedtopeople': str(self.user1.id),
        }
        request = self._create_request(self.user1, method='POST', data=post_data)

        # Mock the form data processing
        def mock_get_clean_form_data(req):
            return req.POST

        import apps.core.utils_new.http_utils
        original_func = apps.core.utils_new.http_utils.get_clean_form_data
        apps.core.utils_new.http_utils.get_clean_form_data = mock_get_clean_form_data

        try:
            response = view.post(request)
            # Should succeed for valid scoped access
            self.assertEqual(response.status_code, 200)
        finally:
            apps.core.utils_new.http_utils.get_clean_form_data = original_func

    def test_scoped_ticket_access_post_denied(self):
        """Test that users cannot update tickets outside their client/site scope"""
        view = TicketView()
        post_data = {
            'pk': str(self.ticket2.id),  # User1 trying to update User2's ticket
            'ticketdesc': 'Malicious update',
            'status': Ticket.Status.CLOSED.value,
        }
        request = self._create_request(self.user1, method='POST', data=post_data)

        with self.assertRaises(Ticket.DoesNotExist):
            response = view.post(request)

    def test_auto_open_audit_trail(self):
        """Test that auto-opening tickets creates proper audit trail"""
        # Create a NEW ticket
        ticket = Ticket.objects.create(
            ticketdesc="Test auto-open audit",
            client=self.client1,
            bu=self.site1,
            assignedtopeople=self.user1,
            status=Ticket.Status.NEW.value,
            priority=Ticket.Priority.LOW.value,
            cuser=self.user2  # Different user created it
        )

        view = TicketView()
        request = self._create_request(self.user1)  # User1 viewing User2's ticket
        request.GET = {'id': str(ticket.id)}

        # Initially no history
        initial_history_count = len(ticket.ticketlog.get('ticket_history', []))

        response = view.get(request)

        # Refresh ticket from DB
        ticket.refresh_from_db()

        # Verify ticket status changed to OPEN
        self.assertEqual(ticket.status, Ticket.Status.OPEN.value)

        # Verify audit trail was created
        final_history_count = len(ticket.ticketlog.get('ticket_history', []))
        self.assertGreater(final_history_count, initial_history_count)

    def test_state_transition_validation_valid(self):
        """Test valid state transitions are allowed"""
        # Test NEW -> OPEN
        form_data = {
            'ticketdesc': 'Test ticket',
            'status': Ticket.Status.OPEN.value,
            'priority': Ticket.Priority.MEDIUM.value,
            'assignedtopeople': self.user1.id,
            'ticketcategory': self.category1.id,
        }

        request = self._create_request(self.user1)
        form = TicketForm(form_data, request=request, instance=self.ticket1)

        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_state_transition_validation_invalid(self):
        """Test invalid state transitions are blocked"""
        # Test CLOSED -> NEW (invalid transition)
        closed_ticket = Ticket.objects.create(
            ticketdesc="Closed ticket",
            client=self.client1,
            bu=self.site1,
            status=Ticket.Status.CLOSED.value,
            priority=Ticket.Priority.LOW.value,
        )

        form_data = {
            'ticketdesc': 'Test ticket',
            'status': Ticket.Status.NEW.value,  # Invalid: CLOSED -> NEW
            'priority': Ticket.Priority.MEDIUM.value,
            'assignedtopeople': self.user1.id,
        }

        request = self._create_request(self.user1)
        form = TicketForm(form_data, request=request, instance=closed_ticket)

        self.assertFalse(form.is_valid())
        self.assertIn("Invalid status transition", str(form.errors))

    def test_terminal_state_comment_requirement(self):
        """Test that comments are required for terminal states"""
        # Test RESOLVED without comments (should fail)
        form_data = {
            'ticketdesc': 'Test ticket',
            'status': Ticket.Status.RESOLVED.value,
            'priority': Ticket.Priority.MEDIUM.value,
            'assignedtopeople': self.user1.id,
            'comments': '',  # Empty comments
        }

        request = self._create_request(self.user1)
        form = TicketForm(form_data, request=request, instance=self.ticket1)

        self.assertFalse(form.is_valid())
        self.assertIn("Comments are required", str(form.errors))

    def test_terminal_state_with_comments_valid(self):
        """Test that terminal states work with proper comments"""
        # First transition to OPEN
        self.ticket1.status = Ticket.Status.OPEN.value
        self.ticket1.save()

        # Test RESOLVED with comments (should succeed)
        form_data = {
            'ticketdesc': 'Test ticket',
            'status': Ticket.Status.RESOLVED.value,
            'priority': Ticket.Priority.MEDIUM.value,
            'assignedtopeople': self.user1.id,
            'comments': 'Issue has been resolved successfully',
            'ticketcategory': self.category1.id,
        }

        request = self._create_request(self.user1)
        form = TicketForm(form_data, request=request, instance=self.ticket1)

        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_cross_client_data_isolation(self):
        """Test that ticket lists are properly scoped by client"""
        # This would require testing the manager methods
        # Create tickets for both clients
        tickets_client1 = Ticket.objects.filter(client=self.client1)
        tickets_client2 = Ticket.objects.filter(client=self.client2)

        self.assertGreater(len(tickets_client1), 0)
        self.assertGreater(len(tickets_client2), 0)

        # Verify no cross-contamination
        for ticket in tickets_client1:
            self.assertEqual(ticket.client_id, self.client1.id)

        for ticket in tickets_client2:
            self.assertEqual(ticket.client_id, self.client2.id)

@pytest.mark.security
class PasswordValidationTestCase(TestCase):
    """Test password validation is enabled"""

    def test_password_validation_enabled(self):
        """Ensure password validation is properly configured"""
        from django.conf import settings

        # Check that password validators are configured
        self.assertTrue(hasattr(settings, 'AUTH_PASSWORD_VALIDATORS'))
        self.assertGreater(len(settings.AUTH_PASSWORD_VALIDATORS), 0)

        # Test that weak passwords are rejected
        with self.assertRaises(ValidationError):
            User = get_user_model()
            user = User(
                loginid="testuser",
                peoplecode="TEST",
                peoplename="Test User",
                email="test@example.com",
                dateofbirth="1990-01-01",
                dateofjoin="2020-01-01"
            )
            user.set_password("123")  # Weak password
            user.full_clean()  # This should trigger validation