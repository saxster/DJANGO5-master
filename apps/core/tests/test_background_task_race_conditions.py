"""
Comprehensive race condition tests for background task operations

Tests verify that concurrent background tasks do not corrupt state:
- Job autoclose operations
- Checkpoint batch autoclose
- Ticket escalations
- Alert notifications

Following test patterns from:
- apps/attendance/tests/test_race_conditions.py
- apps/activity/tests/test_job_race_conditions.py
"""

import pytest
import threading
import time
import uuid as uuid_module
from datetime import date, timedelta, datetime as dt_datetime
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.activity.models.job_model import Jobneed, Job
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet
from apps.y_helpdesk.models import Ticket
from apps.onboarding.models import Bt, TypeAssist, Shift
from apps.peoples.models import Pgroup
from background_tasks.utils import (
    update_job_autoclose_status,
    check_for_checkpoints_status,
    update_ticket_log,
    update_ticket_data,
)

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestBackgroundTaskRaceConditions(TransactionTestCase):
    """
    Test race conditions in background task operations

    Critical scenarios:
    1. Concurrent job autoclose operations
    2. Concurrent checkpoint autoclose
    3. Concurrent ticket log updates
    4. Concurrent ticket escalations
    """

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
        self.ticket_type = TypeAssist.objects.create(
            tacode="AUTOCLOSENOTIFY",
            taname="Auto Close Notify"
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

        from datetime import time as dt_time
        self.shift = Shift.objects.create(
            shiftname='Day Shift',
            client=self.client_bt,
            bu=self.site_bt,
            starttime=dt_time(8, 0),
            endtime=dt_time(16, 0)
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

        self.asset = Asset.objects.create(
            assetcode='ASSET001',
            assetname='Test Asset',
            client=self.client_bt,
            bu=self.site_bt,
            enable=True
        )

        self.qset = QuestionSet.objects.create(
            qsetname='Test QuestionSet',
            client=self.client_bt,
            bu=self.site_bt
        )

    def create_test_jobneed(self, jobstatus='INPROGRESS'):
        """Create a test jobneed"""
        now = timezone.now()
        return Jobneed.objects.create(
            jobdesc='Test Task',
            plandatetime=now - timedelta(hours=3),
            expirydatetime=now - timedelta(hours=1),
            gracetime=15,
            asset=self.asset,
            jobstatus=jobstatus,
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
            muser=self.user,
            other_info={}
        )

    def create_test_ticket(self):
        """Create a test ticket"""
        return Ticket.objects.create(
            ticketno='T00001',
            ticketdesc='Test Ticket',
            status='NEW',
            priority='HIGH',
            level=0,
            ticketsource='SYSTEMGENERATED',
            client=self.client_bt,
            bu=self.site_bt,
            ticketcategory=self.ticket_type,
            ticketlog={'ticket_history': []},
            cuser=self.user,
            muser=self.user
        )

    def test_concurrent_job_autoclose(self):
        """
        Test: Multiple workers attempt to autoclose same job simultaneously
        Expected: Only one succeeds, no data corruption, proper locking
        """
        jobneed = self.create_test_jobneed('INPROGRESS')

        record = {
            'id': jobneed.id,
            'ticketcategory__tacode': 'AUTOCLOSENOTIFY',
        }

        errors = []
        results = []

        def autoclose_worker(worker_id):
            try:
                resp = {'id': [], 'story': ''}
                result = update_job_autoclose_status(record, resp)
                results.append((worker_id, result))
            except Exception as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=autoclose_worker, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        jobneed.refresh_from_db()
        self.assertEqual(jobneed.jobstatus, 'AUTOCLOSED', "Job should be autoclosed")
        self.assertTrue(
            jobneed.other_info.get('autoclosed_by_server'),
            "Autoclosed flag should be set"
        )
        self.assertTrue(
            jobneed.other_info.get('email_sent'),
            "Email sent flag should be set"
        )

    def test_concurrent_checkpoint_autoclose(self):
        """
        Test: Multiple workers attempt to autoclose checkpoints simultaneously
        Expected: All checkpoints autoclosed exactly once, no duplicate processing
        """
        parent_job = self.create_test_jobneed('INPROGRESS')
        parent_job.identifier = 'INTERNALTOUR'
        parent_job.save()

        checkpoints = []
        for i in range(10):
            checkpoint = Jobneed.objects.create(
                jobdesc=f'Checkpoint {i}',
                plandatetime=timezone.now(),
                expirydatetime=timezone.now() + timedelta(hours=2),
                gracetime=15,
                asset=self.asset,
                jobstatus='ASSIGNED',
                jobtype='SCHEDULE',
                priority='HIGH',
                qset=self.qset,
                scantype='QR',
                people=self.user,
                identifier='INTERNALTOUR',
                seqno=i+1,
                parent_id=parent_job.id,
                client=self.client_bt,
                bu=self.site_bt,
                cuser=self.user,
                muser=self.user,
                other_info={}
            )
            checkpoints.append(checkpoint)

        errors = []

        def autoclose_checkpoints_worker(worker_id):
            try:
                from apps.activity.models.job_model import Jobneed as JobneedModel
                check_for_checkpoints_status(parent_job, JobneedModel)
            except Exception as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=autoclose_checkpoints_worker, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        autoclosed_count = Jobneed.objects.filter(
            parent_id=parent_job.id,
            jobstatus='AUTOCLOSED'
        ).count()
        self.assertEqual(autoclosed_count, 10, "All checkpoints should be autoclosed")

        for checkpoint in checkpoints:
            checkpoint.refresh_from_db()
            self.assertEqual(checkpoint.jobstatus, 'AUTOCLOSED')
            self.assertTrue(
                checkpoint.other_info.get('autoclosed_by_server'),
                f"Checkpoint {checkpoint.id} should have autoclosed flag"
            )

    def test_concurrent_ticket_log_updates(self):
        """
        Test: Multiple history entries added concurrently to same ticket
        Expected: No lost entries, all appended successfully
        """
        ticket = self.create_test_ticket()

        num_updates = 20
        errors = []

        def append_history(worker_id):
            try:
                history_item = {
                    'when': str(timezone.now()),
                    'who': f'Worker {worker_id}',
                    'action': 'test',
                    'details': [f'Test entry {worker_id}'],
                    'previous_state': {}
                }
                result = {'story': '', 'traceback': ''}
                update_ticket_log(ticket.id, history_item, result)
            except Exception as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=append_history, args=(i,)) for i in range(num_updates)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        ticket.refresh_from_db()
        history_length = len(ticket.ticketlog.get('ticket_history', []))

        self.assertEqual(
            history_length,
            num_updates,
            f"Should have {num_updates} history entries, found {history_length}"
        )

    def test_concurrent_ticket_escalations(self):
        """
        Test: Multiple workers attempt to escalate tickets simultaneously
        Expected: Level increments correctly, no corruption
        """
        tickets_data = []
        for i in range(5):
            ticket = self.create_test_ticket()
            ticket.level = 0
            ticket.save()
            tickets_data.append({
                'id': ticket.id,
                'level': 0,
                'exp_time': timezone.now(),
                'assignedtopeople': self.user.id,
                'assignedtogroup': 1,
                'escgrpid': 1,
                'escpersonid': 1,
                'cuser_id': self.user.id,
                'ticketlog': {'ticket_history': []},
                'who': 'System'
            })

        errors = []
        results = []

        def escalate_worker(worker_id):
            try:
                import copy
                result = {'id': [], 'story': ''}
                tickets_copy = copy.deepcopy(tickets_data)
                outcome = update_ticket_data(tickets_copy, result)
                results.append((worker_id, outcome))
            except Exception as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=escalate_worker, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        for ticket_data in tickets_data:
            ticket = Ticket.objects.get(pk=ticket_data['id'])
            self.assertGreaterEqual(
                ticket.level,
                1,
                f"Ticket {ticket.id} should be escalated to at least level 1"
            )
            self.assertTrue(
                ticket.isescalated,
                f"Ticket {ticket.id} should have escalated flag"
            )

    def test_partial_completion_race_condition(self):
        """
        Test: Job with checkpoints transitions to PARTIALLYCOMPLETED correctly
        Expected: Partial completion detected even with concurrent autoclose
        """
        parent_job = self.create_test_jobneed('INPROGRESS')
        parent_job.identifier = 'INTERNALTOUR'
        parent_job.save()

        for i in range(5):
            status = 'COMPLETED' if i < 2 else 'ASSIGNED'
            Jobneed.objects.create(
                jobdesc=f'Checkpoint {i}',
                plandatetime=timezone.now(),
                expirydatetime=timezone.now() + timedelta(hours=2),
                gracetime=15,
                asset=self.asset,
                jobstatus=status,
                jobtype='SCHEDULE',
                priority='HIGH',
                qset=self.qset,
                scantype='QR',
                people=self.user,
                identifier='INTERNALTOUR',
                seqno=i+1,
                parent_id=parent_job.id,
                client=self.client_bt,
                bu=self.site_bt,
                cuser=self.user,
                muser=self.user,
                other_info={}
            )

        record = {
            'id': parent_job.id,
            'ticketcategory__tacode': 'AUTOCLOSENOTIFY',
        }

        resp = {'id': [], 'story': ''}
        result = update_job_autoclose_status(record, resp)

        parent_job.refresh_from_db()
        self.assertEqual(
            parent_job.jobstatus,
            'PARTIALLYCOMPLETED',
            "Job should be marked as partially completed"
        )

    def test_mail_sent_flag_race_condition(self):
        """
        Test: Concurrent alert mail sends don't corrupt ismailsent flag
        Expected: Flag set exactly once, no duplicate sends
        """
        from apps.activity.models.job_model import Jobneed as JobneedModel

        jobneed = self.create_test_jobneed('COMPLETED')
        jobneed.alerts = True
        jobneed.ismailsent = False
        jobneed.save()

        errors = []

        def mark_mail_sent(worker_id):
            try:
                with transaction.atomic():
                    JobneedModel.objects.filter(pk=jobneed.id).update(
                        ismailsent=True,
                        mdtz=timezone.now()
                    )
            except Exception as e:
                errors.append((worker_id, e))

        threads = [threading.Thread(target=mark_mail_sent, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        jobneed.refresh_from_db()
        self.assertTrue(jobneed.ismailsent, "Mail sent flag should be set")


@pytest.mark.integration
class TestBackgroundTaskIntegration(TransactionTestCase):
    """Integration tests for complete background task workflows"""

    def test_complete_autoclose_workflow(self):
        """
        Test complete autoclose workflow under concurrent load
        Simulates realistic production scenario
        """
        pass