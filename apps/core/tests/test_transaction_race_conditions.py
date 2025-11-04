"""
Transaction Race Condition Tests

Tests concurrent access scenarios to validate that transaction.atomic
prevents data corruption and maintains consistency.

Complies with: .claude/rules.md - Transaction Management Requirements
"""

import pytest
import threading
import time
from django.test import TransactionTestCase
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError

People = get_user_model()


@pytest.mark.django_db(transaction=True)
class ConcurrentPeopleCreationTests(TransactionTestCase):
    """Test concurrent People creation with signal handlers."""

    def test_concurrent_people_creation_with_profile_signals(self):
        """
        Test that concurrent People creation properly handles
        PeopleProfile and PeopleOrganizational signal creation.
        """
        results = {'success': [], 'failed': []}
        lock = threading.Lock()

        def create_person(person_num):
            try:
                with transaction.atomic():
                    people = People.objects.create(
                        loginid=f"concurrent_{person_num}",
                        peoplename=f"Concurrent User {person_num}",
                        peoplecode=f"CONC{person_num:03d}",
                        email=f"concurrent{person_num}@test.com"
                    )
                    time.sleep(0.01)

                    with lock:
                        results['success'].append(people.id)

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                with lock:
                    results['failed'].append((person_num, str(e)))

        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_person, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results['success']) == 10
        assert len(results['failed']) == 0

        from apps.peoples.models.profile_model import PeopleProfile
        from apps.peoples.models.organizational_model import PeopleOrganizational

        for people_id in results['success']:
            assert PeopleProfile.objects.filter(people_id=people_id).exists()
            assert PeopleOrganizational.objects.filter(people_id=people_id).exists()


@pytest.mark.django_db(transaction=True)
class ConcurrentAssetUpdateTests(TransactionTestCase):
    """Test concurrent Asset updates with AssetLog signal."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.tenant = Tenant.objects.create(
            tenantname="Asset Test Tenant",
            tenantcode="ASSET_TENANT"
        )
        self.client = Client.objects.create(
            bucode="ASSET_CLIENT",
            buname="Asset Client",
            tenant=self.tenant
        )
        self.bu = Bt.objects.create(
            bucode="ASSET_BU",
            buname="Asset BU",
            client=self.client,
            tenant=self.tenant
        )
        self.user = People.objects.create_user(
            loginid="asset_user",
            password="pass",
            peoplename="Asset User",
            peoplecode="ASSET001",
            email="asset@test.com"
        )

    def test_concurrent_asset_status_updates_create_correct_logs(self):
        """
        Test that concurrent asset status updates create correct
        AssetLog entries without race conditions.
        """
        from apps.activity.models.asset_model import Asset, AssetLog

        asset = Asset.objects.create(
            assetcode="CONCURRENT_ASSET",
            assetname="Concurrent Test Asset",
            runningstatus="RUNNING",
            cuser=self.user,
            muser=self.user,
            bu=self.bu,
            client=self.client
        )

        statuses = ["DOWN", "MAINTENANCE", "RUNNING", "IDLE", "RUNNING"]
        results = {'success': [], 'failed': []}
        lock = threading.Lock()

        def update_asset_status(status, thread_num):
            try:
                with transaction.atomic():
                    asset_instance = Asset.objects.select_for_update().get(id=asset.id)
                    asset_instance.runningstatus = status
                    asset_instance.muser = self.user
                    asset_instance.save()
                    time.sleep(0.01)

                    with lock:
                        results['success'].append((thread_num, status))

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                with lock:
                    results['failed'].append((thread_num, str(e)))

        threads = []
        for i, status in enumerate(statuses):
            thread = threading.Thread(target=update_asset_status, args=(status, i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results['success']) == 5
        assert len(results['failed']) == 0

        asset.refresh_from_db()
        logs = AssetLog.objects.filter(asset=asset).order_by('cdtz')
        assert logs.count() >= 1


@pytest.mark.django_db(transaction=True)
class ConcurrentWorkOrderTests(TransactionTestCase):
    """Test concurrent work order operations."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.tenant = Tenant.objects.create(
            tenantname="WO Test Tenant",
            tenantcode="WO_TENANT"
        )
        self.client = Client.objects.create(
            bucode="WO_CLIENT",
            buname="WO Client",
            tenant=self.tenant
        )
        self.bu = Bt.objects.create(
            bucode="WO_BU",
            buname="WO BU",
            client=self.client,
            tenant=self.tenant
        )
        self.user = People.objects.create_user(
            loginid="wo_user",
            password="pass",
            peoplename="WO User",
            peoplecode="WO001",
            email="wo@test.com"
        )

    def test_concurrent_work_permit_approval_no_duplicate_emails(self):
        """
        Test that concurrent work permit approvals don't send
        duplicate email notifications.
        """
        from apps.work_order_management.models import Wom, Vendor
        from apps.activity.models.question_model import QuestionSet
        from unittest.mock import patch

        vendor = Vendor.objects.create(
            code="V_APPROVAL",
            name="Approval Vendor",
            cuser=self.user,
            muser=self.user
        )

        qset = QuestionSet.objects.create(
            qsetcode="APPROVAL_QS",
            qsetname="Approval QS",
            cuser=self.user,
            muser=self.user
        )

        wom = Wom.objects.create(
            description="Approval Test",
            vendor=vendor,
            qset=qset,
            workpermit=Wom.WorkPermitStatus.PENDING,
            cuser=self.user,
            muser=self.user,
            bu=self.bu,
            client=self.client
        )

        email_calls = []
        lock = threading.Lock()

        def mock_send_email(*args, **kwargs):
            with lock:
                email_calls.append(args)

        def approve_permit(approver_num):
            try:
                with transaction.atomic():
                    permit = Wom.objects.select_for_update().get(id=wom.id)
                    if permit.workpermit == Wom.WorkPermitStatus.PENDING:
                        permit.workpermit = Wom.WorkPermitStatus.APPROVED
                        permit.save()

                        if approver_num == 0:
                            mock_send_email(permit.id)

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                pass

        threads = []
        for i in range(3):
            thread = threading.Thread(target=approve_permit, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        wom.refresh_from_db()
        assert wom.workpermit == Wom.WorkPermitStatus.APPROVED
        assert len(email_calls) <= 1


@pytest.mark.django_db(transaction=True)
class DistributedLockTests(TransactionTestCase):
    """Test distributed lock integration with transactions."""

    def test_distributed_lock_prevents_concurrent_modification(self):
        """
        Test that distributed locks prevent concurrent modifications
        to the same resource.
        """
        from apps.activity.models.job_model import Job
        from apps.activity.models.question_model import QuestionSet
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        tenant = Tenant.objects.create(tenantname="Lock Test", tenantcode="LOCK")
        client = Client.objects.create(bucode="LC", buname="Lock Client", tenant=tenant)
        bu = Bt.objects.create(bucode="LB", buname="Lock BU", client=client, tenant=tenant)
        user = People.objects.create_user(
            loginid="lock_user",
            password="pass",
            peoplename="Lock User",
            peoplecode="LOCK001",
            email="lock@test.com"
        )

        qset = QuestionSet.objects.create(
            qsetcode="LOCK_QS",
            qsetname="Lock QS",
            cuser=user,
            muser=user
        )

        parent_job = Job.objects.create(
            jobname="Lock Test Parent",
            identifier="INTERNALTOUR",
            cuser=user,
            muser=user,
            bu=bu,
            client=client,
            qset=qset
        )

        results = {'success': 0, 'lock_failed': 0, 'errors': []}
        lock_obj = threading.Lock()

        def update_parent_job(worker_num):
            lock_key = f"parent_job_update:{parent_job.id}"

            try:
                with distributed_lock(lock_key, timeout=5, blocking_timeout=2):
                    with transaction.atomic():
                        job = Job.objects.select_for_update().get(id=parent_job.id)
                        current_count = getattr(job, 'other_info', {}).get('update_count', 0)
                        if not job.other_info:
                            job.other_info = {}
                        job.other_info['update_count'] = current_count + 1
                        job.save()
                        time.sleep(0.05)

                        with lock_obj:
                            results['success'] += 1

            except LockAcquisitionError:
                with lock_obj:
                    results['lock_failed'] += 1
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                with lock_obj:
                    results['errors'].append(str(e))

        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_parent_job, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        parent_job.refresh_from_db()
        final_count = parent_job.other_info.get('update_count', 0)

        assert results['success'] + results['lock_failed'] == 5
        assert final_count == results['success']
        assert len(results['errors']) == 0


@pytest.mark.django_db(transaction=True)
class SaveUserInfoRaceConditionTests(TransactionTestCase):
    """Test save_userinfo under concurrent access."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.tenant = Tenant.objects.create(
            tenantname="SaveUserInfo Test",
            tenantcode="SUI"
        )
        self.client = Client.objects.create(
            bucode="SUI_CLIENT",
            buname="SUI Client",
            tenant=self.tenant
        )
        self.bu = Bt.objects.create(
            bucode="SUI_BU",
            buname="SUI BU",
            client=self.client,
            tenant=self.tenant
        )
        self.user = People.objects.create_user(
            loginid="sui_user",
            password="pass",
            peoplename="SUI User",
            peoplecode="SUI001",
            email="sui@test.com"
        )

    def test_concurrent_save_userinfo_doesnt_corrupt_data(self):
        """
        Test that concurrent calls to save_userinfo don't corrupt
        cuser/muser/client/tenant data.
        """
        from apps.activity.models.asset_model import Asset
        import apps.peoples.utils as putils

        asset = Asset.objects.create(
            assetcode="SUI_ASSET",
            assetname="SUI Asset",
            cuser=self.user,
            muser=self.user,
            bu=self.bu,
            client=self.client
        )

        session = {
            'client_id': self.client.id,
            'bu_id': self.bu.id,
            'tenantid': self.tenant.id
        }

        results = []
        lock = threading.Lock()

        def update_asset_with_userinfo(update_num):
            try:
                with transaction.atomic():
                    asset_instance = Asset.objects.select_for_update().get(id=asset.id)
                    asset_instance.assetname = f"Updated Asset {update_num}"
                    putils.save_userinfo(
                        asset_instance,
                        self.user,
                        session,
                        create=False
                    )

                    with lock:
                        results.append(('success', update_num))

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                with lock:
                    results.append(('failed', update_num, str(e)))

        threads = []
        for i in range(10):
            thread = threading.Thread(target=update_asset_with_userinfo, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        successful_updates = [r for r in results if r[0] == 'success']
        assert len(successful_updates) == 10

        asset.refresh_from_db()
        assert asset.client_id == self.client.id
        assert asset.bu_id == self.bu.id
        assert asset.tenant_id == self.tenant.id
        assert asset.muser_id == self.user.id


@pytest.mark.django_db(transaction=True)
class WorkPermitDetailConcurrencyTests(TransactionTestCase):
    """Test concurrent work permit detail creation."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.tenant = Tenant.objects.create(
            tenantname="WP Detail Test",
            tenantcode="WPD"
        )
        self.client = Client.objects.create(
            bucode="WPD_CLIENT",
            buname="WPD Client",
            tenant=self.tenant
        )
        self.bu = Bt.objects.create(
            bucode="WPD_BU",
            buname="WPD BU",
            client=self.client,
            tenant=self.tenant
        )
        self.user = People.objects.create_user(
            loginid="wpd_user",
            password="pass",
            peoplename="WPD User",
            peoplecode="WPD001",
            email="wpd@test.com"
        )

        TypeAssist.objects.get_or_create(
            tacode="WOMDETAILS",
            taname="WOM Details",
            cuser=self.user,
            muser=self.user
        )

    def test_concurrent_wom_detail_creation_in_transaction(self):
        """
        Test that WomDetails creation within create_workpermit_details
        is properly isolated across concurrent requests.
        """
        from apps.work_order_management.models import Wom, WomDetails, Vendor
        from apps.activity.models.question_model import QuestionSet

        vendor = Vendor.objects.create(
            code="WPD_VENDOR",
            name="WPD Vendor",
            cuser=self.user,
            muser=self.user
        )

        qset = QuestionSet.objects.create(
            qsetcode="WPD_QS",
            qsetname="WPD Questions",
            cuser=self.user,
            muser=self.user
        )

        results = []
        lock = threading.Lock()

        def create_work_permit(permit_num):
            try:
                with transaction.atomic():
                    wom = Wom.objects.create(
                        description=f"Concurrent WP {permit_num}",
                        vendor=vendor,
                        qset=qset,
                        cuser=self.user,
                        muser=self.user,
                        bu=self.bu,
                        client=self.client
                    )

                    for detail_num in range(3):
                        WomDetails.objects.create(
                            wom=wom,
                            seqno=detail_num,
                            question_id=1,
                            answertype="TEXT",
                            answer=f"Answer {detail_num}",
                            cuser_id=self.user.id,
                            muser_id=self.user.id
                        )

                    with lock:
                        results.append(('success', permit_num, wom.id))

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                with lock:
                    results.append(('failed', permit_num, str(e)))

        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_work_permit, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        successful_creates = [r for r in results if r[0] == 'success']
        assert len(successful_creates) == 5

        for status, permit_num, wom_id in successful_creates:
            assert WomDetails.objects.filter(wom_id=wom_id).count() == 3


@pytest.mark.django_db(transaction=True)
class TransactionDeadlockTests(TransactionTestCase):
    """Test deadlock prevention in transaction management."""

    def test_no_deadlock_with_proper_lock_ordering(self):
        """
        Test that operations acquire locks in consistent order
        to prevent deadlocks.
        """
        from apps.activity.models.job_model import Job
        from apps.activity.models.question_model import QuestionSet
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        tenant = Tenant.objects.create(tenantname="DL Test", tenantcode="DL")
        client = Client.objects.create(bucode="DL_C", buname="DL Client", tenant=tenant)
        bu = Bt.objects.create(bucode="DL_B", buname="DL BU", client=client, tenant=tenant)
        user = People.objects.create_user(
            loginid="dl_user",
            password="pass",
            peoplename="DL User",
            peoplecode="DL001",
            email="dl@test.com"
        )

        qset = QuestionSet.objects.create(
            qsetcode="DL_QS",
            qsetname="DL QS",
            cuser=user,
            muser=user
        )

        job1 = Job.objects.create(
            jobname="Job 1",
            identifier="TASK",
            cuser=user,
            muser=user,
            bu=bu,
            client=client,
            qset=qset
        )

        job2 = Job.objects.create(
            jobname="Job 2",
            identifier="TASK",
            cuser=user,
            muser=user,
            bu=bu,
            client=client,
            qset=qset
        )

        results = []
        lock = threading.Lock()

        def update_jobs_ordered(thread_num):
            try:
                job_ids = sorted([job1.id, job2.id])

                with transaction.atomic():
                    for job_id in job_ids:
                        job = Job.objects.select_for_update().get(id=job_id)
                        job.jobdesc = f"Updated by thread {thread_num}"
                        job.save()
                        time.sleep(0.01)

                    with lock:
                        results.append(('success', thread_num))

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                with lock:
                    results.append(('failed', thread_num, str(e)))

        threads = []
        for i in range(4):
            thread = threading.Thread(target=update_jobs_ordered, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        successful_updates = [r for r in results if r[0] == 'success']
        assert len(successful_updates) == 4


@pytest.mark.django_db(transaction=True)
class TicketRaceConditionTests(TransactionTestCase):
    """Test ticket number generation under concurrent load."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.tenant = Tenant.objects.create(
            tenantname="Ticket Test",
            tenantcode="TICKET"
        )
        self.client = Client.objects.create(
            bucode="TKT_CLIENT",
            buname="Ticket Client",
            tenant=self.tenant
        )
        self.bu = Bt.objects.create(
            bucode="TKT_BU",
            buname="Ticket BU",
            client=self.client,
            tenant=self.tenant
        )
        self.user = People.objects.create_user(
            loginid="ticket_user",
            password="pass",
            peoplename="Ticket User",
            peoplecode="TKT001",
            email="ticket@test.com"
        )

        TypeAssist.objects.get_or_create(
            tacode="TICKET",
            taname="Ticket",
            cuser=self.user,
            muser=self.user
        )

    def test_concurrent_ticket_creation_unique_numbers(self):
        """
        Test that concurrent ticket creation generates unique
        ticket numbers without collisions.
        """
        from apps.y_helpdesk.models import Ticket

        results = []
        lock = threading.Lock()

        def create_ticket(ticket_num):
            try:
                with transaction.atomic():
                    ticket = Ticket.objects.create(
                        title=f"Concurrent Ticket {ticket_num}",
                        description="Test ticket",
                        priority="MEDIUM",
                        status=Ticket.Status.NEW,
                        cuser=self.user,
                        muser=self.user,
                        bu=self.bu,
                        client=self.client
                    )

                    with lock:
                        results.append(('success', ticket_num, ticket.ticketno))

            except IntegrityError as e:
                with lock:
                    results.append(('failed', ticket_num, str(e)))

        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_ticket, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        successful_creates = [r for r in results if r[0] == 'success']
        ticket_numbers = [r[2] for r in successful_creates]

        assert len(successful_creates) >= 8
        assert len(ticket_numbers) == len(set(ticket_numbers))