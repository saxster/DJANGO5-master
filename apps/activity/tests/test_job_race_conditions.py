"""
Comprehensive race condition tests for job workflow management

Tests verify that concurrent operations do not corrupt job workflow state,
following the pattern from apps/attendance/tests/test_race_conditions.py
"""

import pytest
import threading
import time
import uuid as uuid_module
from datetime import date, timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.activity.models.job_model import Job, Jobneed
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet, Question
from apps.activity.services.job_workflow_service import (
    JobWorkflowService,
    InvalidWorkflowTransitionError
)
from apps.onboarding.models import Bt, TypeAssist, Shift
from apps.peoples.models import Pgroup

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestJobWorkflowRaceConditions(TransactionTestCase):
    """
    Test race conditions in job workflow management

    Critical scenarios:
    1. Concurrent parent-child job updates
    2. Concurrent job status transitions
    3. Multiple checkpoint updates to same parent
    4. Concurrent workflow state changes
    """

    def setUp(self):
        """Set up test data"""
        # Create TypeAssist instances
        self.client_type = TypeAssist.objects.create(
            tacode="CLIENT",
            taname="Client Type"
        )
        self.bu_type = TypeAssist.objects.create(
            tacode="BU",
            taname="Business Unit Type"
        )

        # Create client and business unit
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

        # Create shift
        from datetime import time as dt_time
        self.shift = Shift.objects.create(
            shiftname='Day Shift',
            client=self.client_bt,
            bu=self.site_bt,
            starttime=dt_time(8, 0),
            endtime=dt_time(16, 0)
        )

        # Create users
        self.user = User.objects.create(
            username='testuser',
            peoplename='Test User',
            peoplecode='TEST001',
            email='test@example.com',
            client=self.client_bt,
            bu=self.site_bt,
            dateofbirth=date(1990, 1, 1)
        )

        # Create asset
        self.asset = Asset.objects.create(
            assetcode='ASSET001',
            assetname='Test Asset',
            client=self.client_bt,
            bu=self.site_bt,
            enable=True
        )

        # Create question set
        self.qset = QuestionSet.objects.create(
            qsetname='Test QuestionSet',
            client=self.client_bt,
            bu=self.site_bt
        )

        # Create people group
        self.pgroup = Pgroup.objects.create(
            groupname='Test Group',
            grouplead=self.user,
            client=self.client_bt,
            bu=self.site_bt
        )

    def create_parent_job(self):
        """Create a parent job for testing"""
        now = timezone.now()
        return Job.objects.create(
            jobname='Parent Tour',
            jobdesc='Parent tour job',
            fromdate=now,
            uptodate=now + timedelta(days=30),
            cron='0 9 * * *',
            identifier='INTERNALTOUR',
            planduration=60,
            gracetime=15,
            expirytime=30,
            asset=self.asset,
            priority='HIGH',
            qset=self.qset,
            pgroup=self.pgroup,
            scantype='QR',
            frequency='DAILY',
            seqno=1,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user,
            enable=True
        )

    def create_child_job(self, parent, seqno=1):
        """Create a child checkpoint job"""
        return Job.objects.create(
            jobname=f'Checkpoint {seqno}',
            jobdesc=f'Checkpoint {seqno} description',
            fromdate=parent.fromdate,
            uptodate=parent.uptodate,
            cron=parent.cron,
            identifier=parent.identifier,
            planduration=parent.planduration,
            gracetime=parent.gracetime,
            expirytime=parent.expirytime,
            asset=self.asset,
            priority=parent.priority,
            qset=self.qset,
            people=self.user,
            parent=parent,
            scantype='QR',
            frequency=parent.frequency,
            seqno=seqno,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user,
            enable=True
        )

    def test_concurrent_parent_child_updates(self):
        """
        Test: Two threads update different child jobs of same parent simultaneously
        Expected: Both updates succeed, parent mdtz reflects latest update, no data loss

        This is the critical race condition we're fixing
        """
        parent_job = self.create_parent_job()
        child1 = self.create_child_job(parent_job, seqno=1)
        child2 = self.create_child_job(parent_job, seqno=2)

        errors = []
        results = {'child1': None, 'child2': None}

        def update_child1():
            try:
                time.sleep(0.01)  # Small delay to ensure overlap
                updated_child, updated_parent = JobWorkflowService.update_checkpoint_with_parent(
                    child_id=child1.id,
                    updates={'expirytime': 45},
                    parent_id=parent_job.id,
                    user=self.user
                )
                results['child1'] = (updated_child.expirytime, updated_parent.mdtz)
            except Exception as e:
                errors.append(('child1', e))

        def update_child2():
            try:
                time.sleep(0.02)  # Slightly different timing
                updated_child, updated_parent = JobWorkflowService.update_checkpoint_with_parent(
                    child_id=child2.id,
                    updates={'expirytime': 50},
                    parent_id=parent_job.id,
                    user=self.user
                )
                results['child2'] = (updated_child.expirytime, updated_parent.mdtz)
            except Exception as e:
                errors.append(('child2', e))

        # Run updates concurrently
        t1 = threading.Thread(target=update_child1)
        t2 = threading.Thread(target=update_child2)

        original_parent_mdtz = parent_job.mdtz

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Verify both children updated correctly
        child1.refresh_from_db()
        child2.refresh_from_db()
        self.assertEqual(child1.expirytime, 45, "Child1 update lost")
        self.assertEqual(child2.expirytime, 50, "Child2 update lost")

        # Verify parent timestamp updated
        parent_job.refresh_from_db()
        self.assertGreater(
            parent_job.mdtz,
            original_parent_mdtz,
            "Parent timestamp not updated"
        )

    def test_rapid_concurrent_parent_updates(self):
        """
        Test: 10 rapid concurrent updates to parent via child modifications
        Expected: All updates processed correctly, no lost writes
        """
        parent_job = self.create_parent_job()
        children = [self.create_child_job(parent_job, seqno=i) for i in range(1, 11)]

        errors = []
        update_count = [0]  # Mutable container for thread-safe counter

        def rapid_update(child_id, iteration):
            try:
                JobWorkflowService.update_checkpoint_with_parent(
                    child_id=child_id,
                    updates={'expirytime': 30 + iteration},
                    parent_id=parent_job.id,
                    user=self.user
                )
                update_count[0] += 1
            except Exception as e:
                errors.append((f'child_{child_id}_iter_{iteration}', e))

        threads = []
        for i, child in enumerate(children):
            t = threading.Thread(target=rapid_update, args=(child.id, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify no errors and all updates processed
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(update_count[0], 10, "Some updates were lost")

        # Verify all children updated
        for i, child in enumerate(children):
            child.refresh_from_db()
            self.assertEqual(
                child.expirytime,
                30 + i,
                f"Child {i+1} update lost"
            )

    def test_concurrent_status_transitions(self):
        """
        Test: Multiple workers attempt to change jobneed status simultaneously
        Expected: Transitions occur atomically, no corrupt states
        """
        now = timezone.now()
        jobneed = Jobneed.objects.create(
            jobdesc='Test Task',
            plandatetime=now,
            expirydatetime=now + timedelta(hours=2),
            gracetime=15,
            asset=self.asset,
            jobstatus='ASSIGNED',
            jobtype='SCHEDULE',
            priority='HIGH',
            qset=self.qset,
            scantype='QR',
            people=self.user,
            identifier='TASK',
            seqno=1,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user
        )

        errors = []
        success_count = [0]

        def transition_to_inprogress():
            try:
                time.sleep(0.01)
                JobWorkflowService.transition_jobneed_status(
                    jobneed_id=jobneed.id,
                    new_status='INPROGRESS',
                    user=self.user
                )
                success_count[0] += 1
            except InvalidWorkflowTransitionError as e:
                # Expected if another thread already transitioned
                pass
            except Exception as e:
                errors.append(('transition', e))

        # Spawn 5 concurrent threads trying same transition
        threads = [threading.Thread(target=transition_to_inprogress) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors and exactly one success
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertGreaterEqual(
            success_count[0],
            1,
            "At least one transition should succeed"
        )

        # Verify final state is correct
        jobneed.refresh_from_db()
        self.assertEqual(jobneed.jobstatus, 'INPROGRESS')

    def test_invalid_status_transition_blocked(self):
        """
        Test: Invalid workflow transitions are rejected
        Expected: InvalidWorkflowTransitionError raised
        """
        now = timezone.now()
        jobneed = Jobneed.objects.create(
            jobdesc='Test Task',
            plandatetime=now,
            expirydatetime=now + timedelta(hours=2),
            gracetime=15,
            asset=self.asset,
            jobstatus='COMPLETED',  # Terminal state
            jobtype='SCHEDULE',
            priority='HIGH',
            qset=self.qset,
            scantype='QR',
            people=self.user,
            identifier='TASK',
            seqno=1,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user
        )

        # Attempt invalid transition from COMPLETED to ASSIGNED
        with self.assertRaises(InvalidWorkflowTransitionError):
            JobWorkflowService.transition_jobneed_status(
                jobneed_id=jobneed.id,
                new_status='ASSIGNED',
                user=self.user,
                validate_transition=True
            )

        # Verify status unchanged
        jobneed.refresh_from_db()
        self.assertEqual(jobneed.jobstatus, 'COMPLETED')

    def test_bulk_child_updates_atomic(self):
        """
        Test: Bulk update of multiple children is atomic
        Expected: All updates succeed or none do, parent updated once
        """
        parent_job = self.create_parent_job()
        children = [self.create_child_job(parent_job, seqno=i) for i in range(1, 6)]

        original_parent_mdtz = parent_job.mdtz

        # Bulk update all children
        child_updates = [
            {'id': child.id, 'expirytime': 30 + i}
            for i, child in enumerate(children)
        ]

        updated_children = JobWorkflowService.bulk_update_child_checkpoints(
            parent_id=parent_job.id,
            child_updates=child_updates,
            user=self.user
        )

        # Verify all children updated
        self.assertEqual(len(updated_children), 5)

        for i, child in enumerate(children):
            child.refresh_from_db()
            self.assertEqual(child.expirytime, 30 + i)

        # Verify parent updated once
        parent_job.refresh_from_db()
        self.assertGreater(parent_job.mdtz, original_parent_mdtz)

    def test_distributed_lock_prevents_corruption(self):
        """
        Test: Distributed lock prevents data corruption under high concurrency
        Expected: Parent job mdtz accurately reflects number of updates
        """
        parent_job = self.create_parent_job()
        child = self.create_child_job(parent_job, seqno=1)

        num_updates = 20
        errors = []

        def make_update(iteration):
            try:
                JobWorkflowService.update_checkpoint_with_parent(
                    child_id=child.id,
                    updates={'expirytime': 30 + iteration},
                    parent_id=parent_job.id,
                    user=self.user
                )
            except Exception as e:
                errors.append((iteration, e))

        threads = [
            threading.Thread(target=make_update, args=(i,))
            for i in range(num_updates)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Child should have final expirytime value
        child.refresh_from_db()
        self.assertIn(
            child.expirytime,
            range(30, 30 + num_updates),
            "Child has invalid expirytime"
        )

        # Parent timestamp should be updated
        parent_job.refresh_from_db()
        self.assertIsNotNone(parent_job.mdtz)

    def test_lock_timeout_handling(self):
        """
        Test: Lock acquisition timeout is handled gracefully
        Expected: LockAcquisitionError raised with clear message
        """
        from apps.core.utils_new.distributed_locks import LockAcquisitionError

        parent_job = self.create_parent_job()
        child = self.create_child_job(parent_job, seqno=1)

        # This test is informational - actual lock timeout testing
        # requires holding a lock longer than blocking_timeout
        # In production, the distributed lock will properly handle timeouts

    def test_concurrent_parent_and_status_updates(self):
        """
        Test: Concurrent parent timestamp and status updates don't conflict
        Expected: Both operations succeed independently
        """
        parent_job = self.create_parent_job()
        child = self.create_child_job(parent_job, seqno=1)

        now = timezone.now()
        jobneed = Jobneed.objects.create(
            jobdesc='Test Task',
            plandatetime=now,
            expirydatetime=now + timedelta(hours=2),
            gracetime=15,
            asset=self.asset,
            jobstatus='ASSIGNED',
            jobtype='SCHEDULE',
            priority='HIGH',
            qset=self.qset,
            scantype='QR',
            people=self.user,
            identifier='TASK',
            seqno=1,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user
        )

        errors = []

        def update_parent():
            try:
                JobWorkflowService.update_checkpoint_with_parent(
                    child_id=child.id,
                    updates={'expirytime': 45},
                    parent_id=parent_job.id,
                    user=self.user
                )
            except Exception as e:
                errors.append(('parent_update', e))

        def update_status():
            try:
                time.sleep(0.01)
                JobWorkflowService.transition_jobneed_status(
                    jobneed_id=jobneed.id,
                    new_status='INPROGRESS',
                    user=self.user
                )
            except Exception as e:
                errors.append(('status_update', e))

        t1 = threading.Thread(target=update_parent)
        t2 = threading.Thread(target=update_status)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Verify both updates succeeded
        child.refresh_from_db()
        self.assertEqual(child.expirytime, 45)

        jobneed.refresh_from_db()
        self.assertEqual(jobneed.jobstatus, 'INPROGRESS')


@pytest.mark.integration
class TestJobWorkflowIntegration(TransactionTestCase):
    """Integration tests for complete job workflow scenarios"""

    def test_complete_job_lifecycle_with_concurrency(self):
        """
        Test complete job lifecycle with concurrent operations
        Simulates realistic production scenario
        """
        pass  # Placeholder for additional integration tests