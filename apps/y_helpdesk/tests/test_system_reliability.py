"""
Tests for system reliability fixes

These tests verify:
- System-generated tickets have proper history logging
- Ticket numbering race conditions are handled
- Background task ticket creation works correctly
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.db import transaction, IntegrityError
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

from apps.y_helpdesk.models import Ticket
from apps.onboarding.models import Bt, TypeAssist
from apps.peoples.models import People
from background_tasks.utils import create_ticket_for_autoclose


@pytest.mark.reliability
class SystemTicketHistoryTestCase(TestCase):
    """Test system-generated ticket history logging"""

    def setUp(self):
        """Set up test data"""
        # Create client and site
        self.client_type, _ = TypeAssist.objects.get_or_create(tacode="CLIENT", taname="Client")
        self.site_type, _ = TypeAssist.objects.get_or_create(tacode="SITE", taname="Site")

        self.client = Bt.objects.create(
            bucode="TESTCLIENT",
            buname="Test Client",
            identifier=self.client_type,
            id=20
        )
        self.site = Bt.objects.create(
            bucode="TESTSITE",
            buname="Test Site",
            identifier=self.site_type,
            parent=self.client,
            id=21
        )

        # Create category
        self.category = TypeAssist.objects.create(
            tacode="AUTOCLOSE",
            taname="Auto Close Category",
            client=self.client,
            bu=self.site,
            enable=True
        )

        # Create user
        self.user = People.objects.create(
            loginid="systemuser",
            peoplecode="SYSTEM",
            peoplename="System User",
            email="system@test.com",
            dateofbirth="1990-01-01",
            dateofjoin="2020-01-01",
            client=self.client,
            bu=self.site
        )

    def test_system_generated_ticket_has_initial_history(self):
        """Test that system-generated tickets get initial history entry"""
        jobneed_data = {
            'bu_id': self.site.id,
            'client_id': self.client.id,
            'asset_id': None,
            'ticketcategory_id': self.category.id,
            'priority': 'HIGH',
            'people_id': self.user.id,
            'pgroup_id': None,
            'qset_id': None,
        }

        # Create ticket via background task function
        ticket_data = create_ticket_for_autoclose(jobneed_data, "Test autoclose ticket")

        # Get the created ticket
        ticket = Ticket.objects.get(ticketno=ticket_data['ticketno'])

        # Verify ticket was created as system-generated
        self.assertEqual(ticket.ticketsource, Ticket.TicketSource.SYSTEMGENERATED.value)

        # Verify history entry exists
        history = ticket.ticketlog.get('ticket_history', [])
        self.assertGreater(len(history), 0, "System ticket should have initial history entry")

        # Verify history entry content
        first_entry = history[0]
        self.assertIn('action', first_entry)
        self.assertEqual(first_entry['action'], 'created')

    def test_manual_ticket_creation_also_has_history(self):
        """Test that manually created tickets also get history"""
        ticket = Ticket.objects.create(
            ticketdesc="Manual test ticket",
            client=self.client,
            bu=self.site,
            assignedtopeople=self.user,
            status=Ticket.Status.NEW.value,
            priority=Ticket.Priority.MEDIUM.value,
            ticketsource=Ticket.TicketSource.USERDEFINED.value
        )

        # Manually call store_ticket_history (as would happen in views)
        from apps.core import utils
        utils.store_ticket_history(ticket, user=self.user)

        # Verify history entry exists
        ticket.refresh_from_db()
        history = ticket.ticketlog.get('ticket_history', [])
        self.assertGreater(len(history), 0, "Manual ticket should have history entry")


@pytest.mark.reliability
class TicketNumberingRaceConditionTestCase(TransactionTestCase):
    """Test ticket numbering race condition handling"""

    def setUp(self):
        """Set up test data"""
        # Create client and site
        self.client_type, _ = TypeAssist.objects.get_or_create(tacode="CLIENT", taname="Client")
        self.site_type, _ = TypeAssist.objects.get_or_create(tacode="SITE", taname="Site")

        self.client = Bt.objects.create(
            bucode="RACECLIENT",
            buname="Race Test Client",
            identifier=self.client_type,
            id=30
        )
        self.site = Bt.objects.create(
            bucode="RACESITE",
            buname="Race Test Site",
            identifier=self.site_type,
            parent=self.client,
            id=31
        )

        self.user = People.objects.create(
            loginid="raceuser",
            peoplecode="RACE",
            peoplename="Race User",
            email="race@test.com",
            dateofbirth="1990-01-01",
            dateofjoin="2020-01-01",
            client=self.client,
            bu=self.site
        )

    def create_ticket_concurrent(self, thread_id):
        """Helper function to create tickets concurrently"""
        try:
            with transaction.atomic():
                ticket = Ticket.objects.create(
                    ticketdesc=f"Concurrent ticket {thread_id}",
                    client=self.client,
                    bu=self.site,
                    assignedtopeople=self.user,
                    status=Ticket.Status.NEW.value,
                    priority=Ticket.Priority.MEDIUM.value,
                    ticketsource=Ticket.TicketSource.USERDEFINED.value
                )
                return ticket.ticketno
        except IntegrityError as e:
            # This would be handled by the retry logic in handle_valid_form
            return f"COLLISION_{thread_id}"

    def test_concurrent_ticket_creation(self):
        """Test that concurrent ticket creation doesn't create duplicate numbers"""
        # Create multiple tickets concurrently
        num_threads = 5
        results = []

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(self.create_ticket_concurrent, i)
                for i in range(num_threads)
            ]

            for future in as_completed(futures):
                results.append(future.result())

        # Check that we got some successful ticket numbers
        successful_tickets = [r for r in results if not r.startswith("COLLISION_")]

        # Verify no duplicate ticket numbers
        unique_numbers = set(successful_tickets)
        self.assertEqual(len(unique_numbers), len(successful_tickets),
                        f"Duplicate ticket numbers found: {successful_tickets}")

    def test_ticket_numbering_sequence(self):
        """Test that ticket numbers follow proper sequence"""
        # Create a few tickets in sequence
        tickets = []
        for i in range(3):
            ticket = Ticket.objects.create(
                ticketdesc=f"Sequential ticket {i}",
                client=self.client,
                bu=self.site,
                assignedtopeople=self.user,
                status=Ticket.Status.NEW.value,
                priority=Ticket.Priority.MEDIUM.value,
            )
            tickets.append(ticket)

        # Verify sequential numbering
        numbers = [int(t.ticketno.split('#')[1]) for t in tickets if '#' in t.ticketno]
        for i in range(1, len(numbers)):
            self.assertEqual(numbers[i], numbers[i-1] + 1,
                           f"Non-sequential numbering: {numbers}")

    @patch('apps.y_helpdesk.views.time.sleep')
    @patch('apps.y_helpdesk.views.random.uniform')
    def test_handle_valid_form_retry_mechanism(self, mock_uniform, mock_sleep):
        """Test the retry mechanism in handle_valid_form"""
        from apps.y_helpdesk.views import TicketView
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware

        mock_uniform.return_value = 0.025
        mock_sleep.return_value = None

        view = TicketView()
        factory = RequestFactory()

        # Create a request with form data
        request = factory.post('/', {
            'ticketdesc': 'Test retry ticket',
            'status': 'NEW',
            'priority': 'MEDIUM',
            'assignedtopeople': str(self.user.id),
        })
        request.user = self.user

        # Add session middleware and data
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        request.session['client_id'] = self.client.id
        request.session['assignedsites'] = [self.site.id]
        request.session.save()

        # Mock form
        form = MagicMock()
        form.save.side_effect = [
            IntegrityError("duplicate key value violates unique constraint \"ticketno\""),
            MagicMock(id=123, ticketno="TEST#1")  # Success on second try
        ]

        response = view.handle_valid_form(form, request)

        # Verify retry was attempted
        self.assertEqual(form.save.call_count, 2)
        mock_sleep.assert_called_once()
        self.assertEqual(response.status_code, 200)


@pytest.mark.reliability
class AttendanceIntegrationTestCase(TestCase):
    """Test attendance ticket integration"""

    def setUp(self):
        """Set up test data"""
        from apps.attendance.ticket_integration import AttendanceTicketService

        # Create client and site
        self.client_type, _ = TypeAssist.objects.get_or_create(tacode="CLIENT", taname="Client")
        self.site_type, _ = TypeAssist.objects.get_or_create(tacode="SITE", taname="Site")

        self.client = Bt.objects.create(
            bucode="ATTENDCLIENT",
            buname="Attendance Client",
            identifier=self.client_type,
            id=40
        )
        self.site = Bt.objects.create(
            bucode="ATTENDSITE",
            buname="Attendance Site",
            identifier=self.site_type,
            parent=self.client,
            id=41
        )

        self.user = People.objects.create(
            loginid="attenduser",
            peoplecode="ATTEND",
            peoplename="Attendance User",
            email="attend@test.com",
            dateofbirth="1990-01-01",
            dateofjoin="2020-01-01",
            client=self.client,
            bu=self.site
        )

        self.service = AttendanceTicketService

    def test_attendance_categories_creation(self):
        """Test that attendance categories are created properly"""
        categories = self.service.ensure_attendance_categories_exist(
            self.client.id, self.site.id
        )

        self.assertGreater(len(categories), 0)
        self.assertIn('ATTENDANCE_MISMATCH', categories)
        self.assertIn('ATTENDANCE_MISSING_IN', categories)

    def test_attendance_ticket_creation(self):
        """Test creating attendance tickets"""
        ticket = self.service.create_attendance_ticket(
            'ATTENDANCE_MISMATCH',
            'Test attendance mismatch',
            self.user.id,
            self.client.id,
            self.site.id
        )

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.ticketsource, Ticket.TicketSource.SYSTEMGENERATED.value)
        self.assertEqual(ticket.status, Ticket.Status.NEW.value)

        # Verify history was created
        history = ticket.ticketlog.get('ticket_history', [])
        self.assertGreater(len(history), 0)

    def test_attendance_ticket_resolution(self):
        """Test resolving attendance tickets"""
        # Create some attendance tickets
        ticket1 = self.service.create_attendance_ticket(
            'ATTENDANCE_MISMATCH',
            'Mismatch 1',
            self.user.id,
            self.client.id,
            self.site.id
        )

        ticket2 = self.service.create_attendance_ticket(
            'ATTENDANCE_MISSING_IN',
            'Missing checkin',
            self.user.id,
            self.client.id,
            self.site.id
        )

        # Resolve tickets for the user
        resolved_count = self.service.resolve_attendance_tickets(
            self.user.id,
            resolution_comment="Attendance corrected"
        )

        self.assertEqual(resolved_count, 2)

        # Verify tickets are resolved
        ticket1.refresh_from_db()
        ticket2.refresh_from_db()
        self.assertEqual(ticket1.status, Ticket.Status.RESOLVED.value)
        self.assertEqual(ticket2.status, Ticket.Status.RESOLVED.value)
        self.assertEqual(ticket1.comments, "Attendance corrected")

    def test_get_open_attendance_tickets(self):
        """Test getting open attendance tickets"""
        # Create mix of attendance and regular tickets
        attendance_ticket = self.service.create_attendance_ticket(
            'ATTENDANCE_MISMATCH',
            'Open mismatch',
            self.user.id,
            self.client.id,
            self.site.id
        )

        regular_ticket = Ticket.objects.create(
            ticketdesc="Regular ticket",
            client=self.client,
            bu=self.site,
            assignedtopeople=self.user,
            status=Ticket.Status.NEW.value,
            priority=Ticket.Priority.MEDIUM.value,
        )

        # Get open attendance tickets
        open_tickets = list(self.service.get_open_attendance_tickets(
            people_id=self.user.id,
            client_id=self.client.id
        ))

        # Should only return attendance tickets
        self.assertEqual(len(open_tickets), 1)
        self.assertEqual(open_tickets[0].id, attendance_ticket.id)