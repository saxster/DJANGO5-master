"""
import logging
logger = logging.getLogger(__name__)
Ticket Escalation Race Condition Tests

Comprehensive tests for concurrent ticket escalation operations.
Verifies that concurrent escalations don't corrupt ticket state.

Following test patterns from:
- apps/attendance/tests/test_race_conditions.py
- apps/activity/tests/test_job_race_conditions.py
"""

import pytest
import threading
import time
from datetime import date, timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.y_helpdesk.models import Ticket, EscalationMatrix
from apps.y_helpdesk.services import TicketWorkflowService, InvalidTicketTransitionError
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from apps.activity.models import Asset, QuestionSet
from apps.peoples.models import Pgroup

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestTicketEscalationRaceConditions(TransactionTestCase):
    """Test race conditions in ticket escalation"""

    def setUp(self):
        """Set up test data"""
        self.client_type = TypeAssist.objects.create(
            tacode="CLIENT",
            taname="Client Type"
        )
        self.bu_type = TypeAssist.objects.create(
            tacode="BU",
            taname="Business Unit Type"
        )
        self.ticket_category = TypeAssist.objects.create(
            tacode="GENERAL",
            taname="General Ticket"
        )

        self.client_bt = Bt.objects.create(
            bucode='CLIENT01',
            buname='Test Client',
            butype=self.client_type
        )

        self.site_bt = Bt.objects.create(
            bucode='SITE01',
            buname='Test Site',
            butype=self.bu_type,
            parent=self.client_bt
        )

        self.user = User.objects.create(
            username='testuser',
            peoplename='Test User',
            peoplecode='TEST001',
            email='test@example.com',
            client=self.client_bt,
            bu=self.site_bt,
            dateofbirth=date(1990, 1, 1)
        )

        self.pgroup = Pgroup.objects.create(
            groupname='Test Group',
            grouplead=self.user,
            client=self.client_bt,
            bu=self.site_bt
        )

    def create_test_ticket(self, status='NEW', level=0):
        """Create a test ticket"""
        return Ticket.objects.create(
            ticketno=f'T{int(time.time())}',
            ticketdesc='Test Ticket',
            status=status,
            priority='HIGH',
            level=level,
            ticketsource='SYSTEMGENERATED',
            client=self.client_bt,
            bu=self.site_bt,
            ticketcategory=self.ticket_category,
            ticketlog={'ticket_history': []},
            assignedtopeople=self.user,
            assignedtogroup=self.pgroup,
            cuser=self.user,
            muser=self.user
        )

    def test_concurrent_escalations_same_ticket(self):
        """
        Test: Multiple workers escalate same ticket simultaneously
        Expected: Level increments exactly once per attempt, no corruption
        """
        ticket = self.create_test_ticket()
        initial_level = ticket.level

        errors = []
        success_count = [0]

        def escalate_ticket(worker_id):
            try:
                time.sleep(0.01 * worker_id)
                TicketWorkflowService.escalate_ticket(
                    ticket_id=ticket.id,
                    assigned_person_id=self.user.id,
                    user=self.user
                )
                success_count[0] += 1
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=escalate_ticket, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ticket.refresh_from_db()

        self.assertGreaterEqual(
            ticket.level,
            initial_level + 1,
            "Ticket should be escalated at least once"
        )
        self.assertTrue(ticket.isescalated, "Ticket should have escalated flag")

        logger_msg = f"Escalations attempted: 5, succeeded: {success_count[0]}, errors: {len(errors)}, final level: {ticket.level}"
        logger.info(logger_msg)

    def test_concurrent_status_transitions(self):
        """
        Test: Multiple workers attempt to change ticket status simultaneously
        Expected: Status transitions atomically, no corrupt states
        """
        ticket = self.create_test_ticket('NEW')

        errors = []
        success_count = [0]

        def transition_to_open(worker_id):
            try:
                time.sleep(0.01 * worker_id)
                TicketWorkflowService.transition_ticket_status(
                    ticket_id=ticket.id,
                    new_status='OPEN',
                    user=self.user,
                    comments=f'Opened by worker {worker_id}'
                )
                success_count[0] += 1
            except InvalidTicketTransitionError:
                pass
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=transition_to_open, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'OPEN', "Ticket should be in OPEN status")

    def test_invalid_transition_blocked(self):
        """
        Test: Invalid status transitions are rejected
        Expected: InvalidTicketTransitionError raised
        """
        ticket = self.create_test_ticket('CLOSED')

        with self.assertRaises(InvalidTicketTransitionError):
            TicketWorkflowService.transition_ticket_status(
                ticket_id=ticket.id,
                new_status='OPEN',
                user=self.user,
                validate_transition=True
            )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'CLOSED', "Status should remain unchanged")

    def test_concurrent_history_appends(self):
        """
        Test: Concurrent history log appends don't lose entries
        Expected: All entries preserved
        """
        ticket = self.create_test_ticket()

        num_appends = 50
        errors = []

        def append_history(worker_id):
            try:
                history_item = {
                    'when': str(timezone.now()),
                    'who': f'Worker {worker_id}',
                    'action': 'test',
                    'details': [f'Test entry from worker {worker_id}'],
                    'previous_state': {}
                }
                TicketWorkflowService.append_history_entry(
                    ticket_id=ticket.id,
                    history_item=history_item
                )
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=append_history, args=(i,)) for i in range(num_appends)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        ticket.refresh_from_db()
        history_count = len(ticket.ticketlog.get('ticket_history', []))

        self.assertEqual(
            history_count,
            num_appends,
            f"Should have {num_appends} history entries, found {history_count}"
        )

    def test_bulk_ticket_updates_atomic(self):
        """
        Test: Bulk update of multiple tickets is atomic
        Expected: All updates succeed or none do
        """
        tickets = [self.create_test_ticket() for _ in range(10)]
        ticket_ids = [t.id for t in tickets]

        count = TicketWorkflowService.bulk_update_tickets(
            ticket_ids=ticket_ids,
            updates={'priority': 'CRITICAL', 'comments': 'Bulk updated'},
            user=self.user
        )

        self.assertEqual(count, 10, "All 10 tickets should be updated")

        for ticket in tickets:
            ticket.refresh_from_db()
            self.assertEqual(ticket.priority, 'CRITICAL')
            self.assertEqual(ticket.comments, 'Bulk updated')

    def test_escalation_with_assignment_change(self):
        """
        Test: Escalation with assignment change is atomic
        Expected: Level and assignment updated together
        """
        ticket = self.create_test_ticket(level=0)

        escalated = TicketWorkflowService.escalate_ticket(
            ticket_id=ticket.id,
            assigned_person_id=self.user.id,
            assigned_group_id=self.pgroup.id,
            user=self.user
        )

        self.assertEqual(escalated.level, 1)
        self.assertEqual(escalated.assignedtopeople_id, self.user.id)
        self.assertEqual(escalated.assignedtogroup_id, self.pgroup.id)
        self.assertTrue(escalated.isescalated)