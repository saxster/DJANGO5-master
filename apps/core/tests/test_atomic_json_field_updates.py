"""
Atomic JSON Field Update Tests

Tests for safe concurrent updates to JSONField values using
AtomicJSONFieldUpdater utility.

Verifies:
- No lost updates when modifying JSON fields concurrently
- Array append operations preserve all entries
- Custom update functions work correctly
- Context manager provides safe updates
"""

import pytest
import threading
import time
from datetime import date, timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.activity.models.job_model import Jobneed
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet
from apps.y_helpdesk.models import Ticket
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from apps.core.utils_new.atomic_json_updater import (
    AtomicJSONFieldUpdater,
    update_json_field_safely,
)

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestAtomicJSONFieldUpdates(TransactionTestCase):
    """Test atomic JSON field update utilities"""

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

    def create_test_jobneed(self):
        """Create a test jobneed with JSON field"""
        now = timezone.now()
        return Jobneed.objects.create(
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
            muser=self.user,
            other_info={
                'counter': 0,
                'processed': False,
                'metadata': {}
            }
        )

    def test_concurrent_json_field_updates(self):
        """
        Test: Multiple threads update same JSON field concurrently
        Expected: No lost updates, all changes preserved
        """
        jobneed = self.create_test_jobneed()
        num_updates = 50

        errors = []

        def update_counter(worker_id):
            try:
                time.sleep(0.01 * worker_id)

                def increment_counter(json_data):
                    json_data['counter'] = json_data.get('counter', 0) + 1
                    json_data[f'worker_{worker_id}'] = True
                    return json_data

                AtomicJSONFieldUpdater.update_with_function(
                    model_class=Jobneed,
                    instance_id=jobneed.id,
                    field_name='other_info',
                    update_func=increment_counter
                )
            except Exception as e:
                errors.append((worker_id, e))

        threads = [
            threading.Thread(target=update_counter, args=(i,))
            for i in range(num_updates)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        jobneed.refresh_from_db()

        self.assertEqual(
            jobneed.other_info.get('counter'),
            num_updates,
            f"Counter should be {num_updates}, found {jobneed.other_info.get('counter')}"
        )

        for i in range(num_updates):
            self.assertIn(
                f'worker_{i}',
                jobneed.other_info,
                f"Worker {i} update should be preserved"
            )

    def test_json_array_append_atomic(self):
        """
        Test: Concurrent appends to JSON array
        Expected: No lost entries
        """
        jobneed = self.create_test_jobneed()
        jobneed.other_info = {'events': []}
        jobneed.save()

        num_appends = 30
        errors = []

        def append_event(worker_id):
            try:
                AtomicJSONFieldUpdater.append_to_json_array(
                    model_class=Jobneed,
                    instance_id=jobneed.id,
                    field_name='other_info',
                    array_key='events',
                    item={'worker': worker_id, 'timestamp': str(timezone.now())}
                )
            except Exception as e:
                errors.append((worker_id, e))

        threads = [
            threading.Thread(target=append_event, args=(i,))
            for i in range(num_appends)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        jobneed.refresh_from_db()
        events = jobneed.other_info.get('events', [])

        self.assertEqual(
            len(events),
            num_appends,
            f"Should have {num_appends} events, found {len(events)}"
        )

    def test_json_context_manager(self):
        """
        Test: Context manager for JSON field updates
        Expected: Changes applied atomically on context exit
        """
        jobneed = self.create_test_jobneed()

        with update_json_field_safely(Jobneed, jobneed.id, 'other_info') as json_data:
            json_data['processed'] = True
            json_data['processed_at'] = str(timezone.now())
            json_data['metadata'] = {'test': True}

        jobneed.refresh_from_db()

        self.assertTrue(jobneed.other_info.get('processed'))
        self.assertIsNotNone(jobneed.other_info.get('processed_at'))
        self.assertEqual(jobneed.other_info.get('metadata'), {'test': True})

    def test_concurrent_ticket_log_appends(self):
        """
        Test: Concurrent appends to ticket log history
        Expected: No lost entries
        """
        ticket = Ticket.objects.create(
            ticketno='T00001',
            ticketdesc='Test Ticket',
            status='NEW',
            priority='HIGH',
            level=0,
            ticketsource='SYSTEMGENERATED',
            client=self.client_bt,
            bu=self.site_bt,
            ticketlog={'ticket_history': []},
            cuser=self.user,
            muser=self.user
        )

        num_appends = 40
        errors = []

        def append_history(worker_id):
            try:
                history_item = {
                    'worker': worker_id,
                    'when': str(timezone.now()),
                    'action': 'test'
                }
                AtomicJSONFieldUpdater.append_to_json_array(
                    model_class=Ticket,
                    instance_id=ticket.id,
                    field_name='ticketlog',
                    array_key='ticket_history',
                    item=history_item
                )
            except Exception as e:
                errors.append((worker_id, e))

        threads = [
            threading.Thread(target=append_history, args=(i,))
            for i in range(num_appends)
        ]

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

    def test_json_array_max_length_enforcement(self):
        """
        Test: Array max length trimming works correctly
        Expected: Old entries removed when max length exceeded
        """
        jobneed = self.create_test_jobneed()
        jobneed.other_info = {'audit_trail': []}
        jobneed.save()

        for i in range(150):
            AtomicJSONFieldUpdater.append_to_json_array(
                model_class=Jobneed,
                instance_id=jobneed.id,
                field_name='other_info',
                array_key='audit_trail',
                item={'event': i},
                max_length=100
            )

        jobneed.refresh_from_db()
        trail = jobneed.other_info.get('audit_trail', [])

        self.assertEqual(
            len(trail),
            100,
            "Array should be trimmed to max_length of 100"
        )

        self.assertEqual(
            trail[0]['event'],
            50,
            "Oldest entries should be removed (0-49)"
        )
        self.assertEqual(
            trail[-1]['event'],
            149,
            "Latest entry should be preserved"
        )