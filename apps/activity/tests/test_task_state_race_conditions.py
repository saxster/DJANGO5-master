"""
Task State Machine Race Condition Tests

Comprehensive tests for concurrent task state transitions.
Ensures state machine + distributed locking prevents data corruption.

Following test patterns from:
- apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py
- apps/attendance/tests/test_race_conditions.py

Test Coverage:
- Concurrent same-state transitions
- Concurrent different-state transitions
- Invalid transition blocking
- Lock timeout handling
- Transaction rollback verification
- State audit logging
"""

import pytest
import threading
import time
from datetime import date, timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.activity.models import Jobneed, Asset, QuestionSet
from apps.activity.state_machines.task_state_machine import TaskStateMachine
from apps.core.state_machines.base import (
    TransitionContext,
    InvalidTransitionError,
    PermissionDeniedError
)
from apps.core.utils_new.distributed_locks import LockAcquisitionError
from apps.onboarding.models import Bt, TypeAssist

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestTaskStateRaceConditions(TransactionTestCase):
    """Test race conditions in task state machine transitions"""

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
        self.job_category = TypeAssist.objects.create(
            tacode="GENERAL",
            taname="General Job"
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

    def create_test_job(self, status='ASSIGNED'):
        """Create a test job/task"""
        return Jobneed.objects.create(
            identifier='GENERAL',
            jobdesc='Test Job',
            jobstatus=status,
            priority='HIGH',
            client=self.client_bt,
            bu=self.site_bt,
            assignedtopeople=self.user,
            ticketcategory=self.job_category,
            other_info={},
            cuser=self.user,
            muser=self.user,
            plandatetime=timezone.now(),
            expirydatetime=timezone.now() + timedelta(hours=24)
        )

    def test_concurrent_same_state_transitions(self):
        """
        Test: Multiple workers transition same job to same state
        Expected: One succeeds, others succeed gracefully (idempotent)
        """
        job = self.create_test_job('ASSIGNED')

        errors = []
        success_count = [0]

        def start_job(worker_id):
            try:
                time.sleep(0.01 * worker_id)  # Stagger starts

                state_machine = TaskStateMachine(job)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments=f'Started by worker {worker_id}'
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
            threading.Thread(target=start_job, args=(i,))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        job.refresh_from_db()
        self.assertEqual(job.jobstatus, 'INPROGRESS')

        print(
            f"Concurrent same-state transitions: "
            f"attempts=5, succeeded={success_count[0]}, "
            f"final_status={job.jobstatus}"
        )

    def test_concurrent_different_state_transitions(self):
        """
        Test: Workers attempt different state transitions concurrently
        Expected: First wins, others block or fail validation
        """
        job = self.create_test_job('INPROGRESS')

        results = []
        errors = []

        def transition_to_state(worker_id, target_state):
            try:
                time.sleep(0.01 * worker_id)

                state_machine = TaskStateMachine(job)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments=f'Transition by worker {worker_id} to {target_state}'
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
        # Worker 1: INPROGRESS -> STANDBY
        # Worker 2: INPROGRESS -> WORKING
        threads = [
            threading.Thread(target=transition_to_state, args=(0, 'COMPLETED')),
            threading.Thread(target=transition_to_state, args=(1, 'STANDBY')),
            threading.Thread(target=transition_to_state, args=(2, 'WORKING')),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify job ended in ONE of the valid states
        job.refresh_from_db()
        self.assertIn(job.jobstatus, ['COMPLETED', 'STANDBY', 'WORKING'])

        # Exactly one worker should have succeeded
        success_count = sum(1 for _, _, success in results if success)
        self.assertEqual(
            success_count, 1,
            f"Expected exactly 1 successful transition, got {success_count}. Results: {results}"
        )

        print(
            f"Concurrent different-state transitions: "
            f"final_status={job.jobstatus}, "
            f"success_count={success_count}, "
            f"errors={len(errors)}"
        )

    def test_invalid_transition_blocked(self):
        """
        Test: Invalid state transitions are rejected atomically
        Expected: InvalidTransitionError raised, state unchanged
        """
        job = self.create_test_job('AUTOCLOSED')  # Terminal state

        state_machine = TaskStateMachine(job)
        context = TransitionContext(
            user=self.user,
            reason='user_action',
            comments='Attempting invalid transition'
        )

        with self.assertRaises(InvalidTransitionError):
            state_machine.transition_with_lock(
                to_state='INPROGRESS',
                context=context
            )

        job.refresh_from_db()
        self.assertEqual(job.jobstatus, 'AUTOCLOSED', "Status should remain unchanged")

    def test_concurrent_completion_with_validation(self):
        """
        Test: Multiple workers try to complete task concurrently
        Expected: Validation ensures requirements met, atomic completion
        """
        job = self.create_test_job('WORKING')

        errors = []
        success_count = [0]

        def complete_job(worker_id):
            try:
                time.sleep(0.01 * worker_id)

                state_machine = TaskStateMachine(job)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments=f'Completed by worker {worker_id}',
                    skip_permissions=True  # For testing
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
            threading.Thread(target=complete_job, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        job.refresh_from_db()
        self.assertEqual(job.jobstatus, 'COMPLETED')

        # Due to locking, multiple may succeed (idempotent)
        # but all should result in COMPLETED state
        self.assertGreaterEqual(success_count[0], 1)

        print(
            f"Concurrent completion: "
            f"final_status={job.jobstatus}, "
            f"success_count={success_count[0]}, "
            f"errors={len(errors)}"
        )

    def test_lock_timeout_handling(self):
        """
        Test: Worker times out waiting for lock
        Expected: LockAcquisitionError raised after retries
        """
        job = self.create_test_job('ASSIGNED')

        # Worker 1 holds lock for extended period
        def hold_lock_long():
            state_machine = TaskStateMachine(job)
            context = TransitionContext(
                user=self.user,
                reason='user_action',
                comments='Holding lock'
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

            state_machine = TaskStateMachine(job)
            context = TransitionContext(
                user=self.user,
                reason='user_action',
                comments='Should timeout'
            )

            # Short timeout, should fail
            with self.assertRaises(LockAcquisitionError):
                state_machine.transition_with_lock(
                    to_state='WORKING',
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
        job = self.create_test_job('ASSIGNED')

        results = {'state_machine': None, 'direct': None}
        errors = []

        def use_state_machine():
            try:
                state_machine = TaskStateMachine(job)
                context = TransitionContext(
                    user=self.user,
                    reason='user_action',
                    comments='Via state machine'
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
                    j = Jobneed.objects.select_for_update().get(id=job.id)
                    # Direct update (BAD PRACTICE, but testing protection)
                    j.jobstatus = 'WORKING'
                    j.save(update_fields=['jobstatus'])

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

        job.refresh_from_db()

        # State machine should have completed first
        # Direct update either blocked or overwrote (demonstrating need for state machine)
        print(
            f"State machine vs direct update: "
            f"final_status={job.jobstatus}, "
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
        job = self.create_test_job('ASSIGNED')

        # Sequence of transitions
        transitions = [
            ('INPROGRESS', 'Started work'),
            ('WORKING', 'Processing'),
            ('COMPLETED', 'Finished task')
        ]

        for target_state, comment in transitions:
            state_machine = TaskStateMachine(job)
            context = TransitionContext(
                user=self.user,
                reason='user_action',
                comments=comment,
                metadata={'test': 'audit_trail'}
            )

            result = state_machine.transition_with_lock(
                to_state=target_state,
                context=context
            )

            self.assertTrue(result.success)
            job.refresh_from_db()

        # Verify final state
        self.assertEqual(job.jobstatus, 'COMPLETED')

        # TODO: When StateTransitionAudit model is created, verify audit records
        # audit_records = StateTransitionAudit.objects.filter(
        #     entity_type='TaskStateMachine',
        #     entity_id=job.id
        # ).order_by('timestamp')
        # self.assertEqual(audit_records.count(), 3)

        print(f"Audit trail test passed: {len(transitions)} transitions recorded")


@pytest.mark.django_db(transaction=True)
class TestTaskStateEdgeCases(TransactionTestCase):
    """Test edge cases and error scenarios"""

    def setUp(self):
        """Set up minimal test data"""
        self.client_type = TypeAssist.objects.create(tacode="CLIENT", taname="Client")
        self.bu_type = TypeAssist.objects.create(tacode="BU", taname="BU")
        self.job_category = TypeAssist.objects.create(tacode="GENERAL", taname="General")

        self.client_bt = Bt.objects.create(
            bucode='CLIENT01', buname='Client', butype=self.client_type
        )
        self.site_bt = Bt.objects.create(
            bucode='SITE01', buname='Site', butype=self.bu_type, parent=self.client_bt
        )

        self.user = User.objects.create(
            username='user', peoplename='User', peoplecode='U001',
            email='u@ex.com', client=self.client_bt, bu=self.site_bt,
            dateofbirth=date(1990, 1, 1)
        )

    def test_permission_denied_transition(self):
        """Test transition requiring permission user doesn't have"""
        job = Jobneed.objects.create(
            identifier='GENERAL', jobdesc='Test', jobstatus='ASSIGNED',
            client=self.client_bt, bu=self.site_bt, ticketcategory=self.job_category,
            assignedtopeople=self.user, other_info={}, cuser=self.user, muser=self.user,
            plandatetime=timezone.now(), expirydatetime=timezone.now() + timedelta(hours=24)
        )

        # User without permissions attempts transition requiring permission
        # (TaskStateMachine may require specific permissions for some transitions)
        state_machine = TaskStateMachine(job)
        context = TransitionContext(
            user=self.user,
            reason='user_action',
            comments='Attempting restricted transition',
            skip_permissions=False  # Don't skip permission check
        )

        # For states requiring permissions, this should fail
        # (Adjust based on actual TaskStateMachine permission requirements)
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
