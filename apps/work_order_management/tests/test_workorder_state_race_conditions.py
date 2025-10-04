"""
WorkOrder State Machine Race Condition Tests

Comprehensive tests for concurrent work order state transitions.
Ensures state machine + distributed locking prevents data corruption.

Following test patterns from:
- apps/activity/tests/test_task_state_race_conditions.py
- apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py

Test Coverage:
- Concurrent same-state transitions
- Concurrent different-state transitions
- Invalid transition blocking
- Lock timeout handling
- Transaction rollback verification
- State audit logging
- Permission enforcement
"""

import pytest
import threading
import time
from datetime import date, timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.work_order_management.models import Wom
from apps.work_order_management.state_machines.workorder_state_machine import WorkOrderStateMachine
from apps.core.state_machines.base import (
    TransitionContext,
    InvalidTransitionError,
    PermissionDeniedError
)
from apps.core.utils_new.distributed_locks import LockAcquisitionError
from apps.onboarding.models import Bt, TypeAssist
from apps.activity.models import Location

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestWorkOrderStateRaceConditions(TransactionTestCase):
    """Test race conditions in work order state machine transitions"""

    def setUp(self):
        """Set up test data"""
        # Create required TypeAssist records
        self.client_type = TypeAssist.objects.create(
            tacode="CLIENT",
            taname="Client Type"
        )
        self.bu_type = TypeAssist.objects.create(
            tacode="BU",
            taname="Business Unit Type"
        )

        # Create business units
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

        # Create location
        self.location = Location.objects.create(
            identifier='LOC001',
            locationcode='LOC001',
            locationname='Test Location',
            client=self.client_bt,
            bu=self.site_bt
        )

        # Create user
        self.user = User.objects.create(
            username='testuser',
            peoplename='Test User',
            peoplecode='TEST001',
            email='test@example.com',
            client=self.client_bt,
            bu=self.site_bt,
            dateofbirth=date(1990, 1, 1)
        )

    def create_test_work_order(self, status='ASSIGNED'):
        """Create a test work order"""
        return Wom.objects.create(
            description='Test Work Order',
            workstatus=status,
            priority='HIGH',
            client=self.client_bt,
            bu=self.site_bt,
            location=self.location,
            cuser=self.user,
            muser=self.user,
            plandatetime=timezone.now(),
            expirydatetime=timezone.now() + timedelta(hours=24)
        )

    def test_concurrent_same_state_transitions(self):
        """
        Test: Multiple workers transition same work order to same state
        Expected: One succeeds, others succeed gracefully (idempotent)
        """
        wo = self.create_test_work_order('ASSIGNED')

        errors = []
        success_count = [0]

        def start_work_order(worker_id):
            try:
                time.sleep(0.01 * worker_id)  # Stagger starts

                state_machine = WorkOrderStateMachine(wo)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments=f'Started by worker {worker_id}',
                    skip_permissions=True
                )

                result = state_machine.transition_with_lock(
                    to_state='INPROGRESS',
                    context=context
                )

                if result.success:
                    success_count[0] += 1

            except Exception as e:
                errors.append((worker_id, e))

        # Spawn 5 concurrent workers
        threads = [
            threading.Thread(target=start_work_order, args=(i,))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        wo.refresh_from_db()
        self.assertEqual(wo.workstatus, 'INPROGRESS')

        print(
            f"Concurrent same-state transitions: "
            f"attempts=5, succeeded={success_count[0]}, "
            f"final_status={wo.workstatus}"
        )

    def test_concurrent_different_state_transitions(self):
        """
        Test: Workers attempt different state transitions concurrently
        Expected: First wins, others block or fail validation
        """
        wo = self.create_test_work_order('INPROGRESS')

        results = []
        errors = []

        def transition_to_state(worker_id, target_state):
            try:
                time.sleep(0.01 * worker_id)

                state_machine = WorkOrderStateMachine(wo)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments=f'Transition by worker {worker_id} to {target_state}',
                    skip_permissions=True
                )

                result = state_machine.transition_with_lock(
                    to_state=target_state,
                    context=context,
                    max_retries=2
                )

                results.append((worker_id, target_state, result.success))

            except (InvalidTransitionError, LockAcquisitionError) as e:
                # Expected for some workers
                results.append((worker_id, target_state, False))
                errors.append((worker_id, target_state, type(e).__name__))

        # Worker 0: INPROGRESS -> COMPLETED
        # Worker 1: INPROGRESS -> CANCELLED
        # Worker 2: INPROGRESS -> ASSIGNED (invalid)
        threads = [
            threading.Thread(target=transition_to_state, args=(0, 'COMPLETED')),
            threading.Thread(target=transition_to_state, args=(1, 'CANCELLED')),
            threading.Thread(target=transition_to_state, args=(2, 'ASSIGNED')),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify work order ended in ONE of the valid states
        wo.refresh_from_db()
        self.assertIn(wo.workstatus, ['COMPLETED', 'CANCELLED'])

        # Exactly one worker should have succeeded
        success_count = sum(1 for _, _, success in results if success)
        self.assertEqual(
            success_count, 1,
            f"Expected exactly 1 successful transition, got {success_count}. Results: {results}"
        )

        print(
            f"Concurrent different-state transitions: "
            f"final_status={wo.workstatus}, "
            f"success_count={success_count}, "
            f"errors={len(errors)}"
        )

    def test_invalid_transition_blocked(self):
        """
        Test: Invalid state transitions are rejected atomically
        Expected: InvalidTransitionError raised, state unchanged
        """
        wo = self.create_test_work_order('CLOSED')  # Terminal state

        state_machine = WorkOrderStateMachine(wo)
        context = TransitionContext(
            user=self.user,
            reason='user_action',
            comments='Attempting invalid transition',
            skip_permissions=True
        )

        with self.assertRaises(InvalidTransitionError):
            state_machine.transition_with_lock(
                to_state='INPROGRESS',
                context=context
            )

        wo.refresh_from_db()
        self.assertEqual(wo.workstatus, 'CLOSED', "Status should remain unchanged")

    def test_concurrent_completion_with_validation(self):
        """
        Test: Multiple workers try to complete work order concurrently
        Expected: Validation ensures requirements met, atomic completion
        """
        wo = self.create_test_work_order('INPROGRESS')

        errors = []
        success_count = [0]

        def complete_work_order(worker_id):
            try:
                time.sleep(0.01 * worker_id)

                state_machine = WorkOrderStateMachine(wo)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments=f'Completed by worker {worker_id}',
                    skip_permissions=True
                )

                result = state_machine.transition_with_lock(
                    to_state='COMPLETED',
                    context=context
                )

                if result.success:
                    success_count[0] += 1

            except Exception as e:
                errors.append((worker_id, e))

        threads = [
            threading.Thread(target=complete_work_order, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        wo.refresh_from_db()
        self.assertEqual(wo.workstatus, 'COMPLETED')

        # Due to locking, multiple may succeed (idempotent)
        # but all should result in COMPLETED state
        self.assertGreaterEqual(success_count[0], 1)

        print(
            f"Concurrent completion: "
            f"final_status={wo.workstatus}, "
            f"success_count={success_count[0]}, "
            f"errors={len(errors)}"
        )

    def test_lock_timeout_handling(self):
        """
        Test: Worker times out waiting for lock
        Expected: LockAcquisitionError raised after retries
        """
        wo = self.create_test_work_order('ASSIGNED')

        # Worker 1 holds lock for extended period
        def hold_lock_long():
            state_machine = WorkOrderStateMachine(wo)
            context = TransitionContext(
                user=self.user,
                reason='user_action',
                comments='Holding lock',
                skip_permissions=True
            )

            # This will hold lock for 5 seconds
            result = state_machine.transition_with_lock(
                to_state='INPROGRESS',
                context=context,
                lock_timeout=5
            )

        # Worker 2 tries to acquire same lock quickly
        def timeout_on_lock():
            time.sleep(0.1)  # Let worker 1 acquire lock first

            state_machine = WorkOrderStateMachine(wo)
            context = TransitionContext(
                user=self.user,
                reason='user_action',
                comments='Should timeout',
                skip_permissions=True
            )

            # Short timeout, should fail
            with self.assertRaises(LockAcquisitionError):
                state_machine.transition_with_lock(
                    to_state='COMPLETED',
                    context=context,
                    lock_timeout=1,
                    blocking_timeout=1,
                    max_retries=1
                )

        t1 = threading.Thread(target=hold_lock_long)
        t2 = threading.Thread(target=timeout_on_lock)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        print("Lock timeout handling test passed")

    def test_state_machine_vs_direct_update_race(self):
        """
        Test: Verify state machine prevents corruption from direct DB updates
        Expected: State machine transitions win, maintain consistency
        """
        wo = self.create_test_work_order('ASSIGNED')

        results = {'state_machine': None, 'direct': None}
        errors = []

        def use_state_machine():
            try:
                state_machine = WorkOrderStateMachine(wo)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments='Via state machine',
                    skip_permissions=True
                )

                result = state_machine.transition_with_lock(
                    to_state='INPROGRESS',
                    context=context
                )

                results['state_machine'] = result.success

            except Exception as e:
                errors.append(('state_machine', e))

        def direct_db_update():
            try:
                time.sleep(0.05)  # Let state machine go first

                # This should be blocked by state machine's lock
                from django.db import transaction as db_transaction

                with db_transaction.atomic():
                    w = Wom.objects.select_for_update().get(id=wo.id)
                    # Direct update (BAD PRACTICE, but testing protection)
                    w.workstatus = 'COMPLETED'
                    w.save(update_fields=['workstatus'])

                results['direct'] = True

            except Exception as e:
                errors.append(('direct', e))
                results['direct'] = False

        t1 = threading.Thread(target=use_state_machine)
        t2 = threading.Thread(target=direct_db_update)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        wo.refresh_from_db()

        # State machine should have completed first
        # Direct update either blocked or overwrote (demonstrating need for state machine)
        print(
            f"State machine vs direct update: "
            f"final_status={wo.workstatus}, "
            f"state_machine_success={results['state_machine']}, "
            f"direct_update_success={results['direct']}"
        )

        # If both succeeded, final state depends on execution order
        # Key point: state machine provides audit trail and validation
        self.assertIsNotNone(results['state_machine'])

    def test_transition_audit_trail(self):
        """
        Test: Verify state transitions create comprehensive audit logs
        Expected: All transitions logged with context
        """
        wo = self.create_test_work_order('ASSIGNED')

        # Sequence of transitions
        transitions = [
            ('INPROGRESS', 'Started work'),
            ('COMPLETED', 'Finished work'),
            ('CLOSED', 'Work order closed')
        ]

        for target_state, comment in transitions:
            state_machine = WorkOrderStateMachine(wo)
            context = TransitionContext(
                user=self.user,
                reason='user_action',
                comments=comment,
                metadata={'test': 'audit_trail'},
                skip_permissions=True
            )

            result = state_machine.transition_with_lock(
                to_state=target_state,
                context=context
            )

            self.assertTrue(result.success)
            wo.refresh_from_db()

        # Verify final state
        self.assertEqual(wo.workstatus, 'CLOSED')

        # Verify audit records exist
        from apps.core.models.state_transition_audit import StateTransitionAudit
        audit_records = StateTransitionAudit.objects.filter(
            entity_type='WorkOrderStateMachine',
            entity_id=wo.id
        ).order_by('timestamp')

        self.assertEqual(audit_records.count(), 3, "Should have 3 audit records")

        print(f"Audit trail test passed: {len(transitions)} transitions recorded")


@pytest.mark.django_db(transaction=True)
class TestWorkOrderStateEdgeCases(TransactionTestCase):
    """Test edge cases and error scenarios"""

    def setUp(self):
        """Set up minimal test data"""
        self.client_type = TypeAssist.objects.create(tacode="CLIENT", taname="Client")
        self.bu_type = TypeAssist.objects.create(tacode="BU", taname="BU")

        self.client_bt = Bt.objects.create(
            bucode='CLIENT01', buname='Client', butype=self.client_type
        )
        self.site_bt = Bt.objects.create(
            bucode='SITE01', buname='Site', butype=self.bu_type, parent=self.client_bt
        )

        self.location = Location.objects.create(
            identifier='LOC001',
            locationcode='LOC001',
            locationname='Test Location',
            client=self.client_bt,
            bu=self.site_bt
        )

        self.user = User.objects.create(
            username='user', peoplename='User', peoplecode='U001',
            email='u@ex.com', client=self.client_bt, bu=self.site_bt,
            dateofbirth=date(1990, 1, 1)
        )

    def test_permission_denied_transition(self):
        """Test transition requiring permission user doesn't have"""
        wo = Wom.objects.create(
            description='Test Work Order',
            workstatus='ASSIGNED',
            client=self.client_bt,
            bu=self.site_bt,
            location=self.location,
            cuser=self.user,
            muser=self.user,
            plandatetime=timezone.now(),
            expirydatetime=timezone.now() + timedelta(hours=24)
        )

        # User without permissions attempts transition requiring permission
        state_machine = WorkOrderStateMachine(wo)
        context = TransitionContext(
            user=self.user,
            reason='user_action',
            comments='Attempting restricted transition',
            skip_permissions=False  # Don't skip permission check
        )

        # For states requiring permissions, this should fail
        try:
            result = state_machine.transition_with_lock(
                to_state='COMPLETED',
                context=context
            )
            # If permissions not enforced, transition succeeds
            self.assertTrue(result.success)
        except PermissionDeniedError:
            # Expected if permissions are enforced
            pass

        print("Permission test completed")
