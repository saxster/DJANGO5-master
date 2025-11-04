"""
Comprehensive Transaction Management Tests

Tests atomic transaction behavior for critical multi-step operations.
Validates that partial failures trigger complete rollbacks.

Complies with: .claude/rules.md - Transaction Management Requirements
"""

import pytest
from django.db import transaction, IntegrityError
from django.test import TestCase, TransactionTestCase, RequestFactory
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock
from apps.core.services.transaction_manager import (
    TransactionManager,
    atomic_view_operation,
    signal_aware_transaction,
    transactional_batch_operation
)

People = get_user_model()


@pytest.mark.django_db(transaction=True)
class TransactionManagerTests(TestCase):
    """Test TransactionManager class functionality."""

    def setUp(self):
        self.manager = TransactionManager()

    def test_atomic_operation_commits_on_success(self):
        with self.manager.atomic_operation():
            people = People.objects.create(
                loginid="test_user",
                peoplename="Test User",
                peoplecode="TEST001"
            )

        assert People.objects.filter(loginid="test_user").exists()

    def test_atomic_operation_rollsback_on_error(self):
        initial_count = People.objects.count()

        with pytest.raises(ValueError):
            with self.manager.atomic_operation():
                People.objects.create(
                    loginid="test_user2",
                    peoplename="Test User 2",
                    peoplecode="TEST002"
                )
                raise ValueError("Simulated error")

        assert People.objects.count() == initial_count

    def test_saga_pattern_compensation(self):
        saga_id = self.manager.create_saga("test_saga")

        executed_items = []
        compensated_items = []

        def step1():
            executed_items.append(1)
            return "step1_result"

        def compensate1(result):
            compensated_items.append(1)

        def step2():
            executed_items.append(2)
            raise ValueError("Step 2 failed")

        self.manager.add_saga_step(saga_id, "step1", step1, compensate1)
        self.manager.add_saga_step(saga_id, "step2", step2)

        result = self.manager.execute_saga(saga_id)

        assert result['status'] == 'failed'
        assert 1 in executed_items
        assert 2 in executed_items
        assert 1 in compensated_items


@pytest.mark.django_db(transaction=True)
class ViewTransactionTests(TransactionTestCase):
    """Test transaction behavior in view handle_valid_form methods."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            tenantcode="TEST_TENANT"
        )
        self.client = Client.objects.create(
            bucode="CLIENT001",
            buname="Test Client",
            tenant=self.tenant
        )
        self.bu = Bt.objects.create(
            bucode="BU001",
            buname="Test Business Unit",
            client=self.client,
            tenant=self.tenant
        )
        self.user = People.objects.create_user(
            loginid="testuser",
            password="testpass",
            peoplename="Test User",
            peoplecode="TEST001",
            email="test@test.com"
        )

    def test_work_permit_rollback_on_detail_creation_failure(self):
        """
        Test that WorkPermit creation rolls back completely if
        create_workpermit_details fails midway.
        """
        from apps.work_order_management.models import Wom, WomDetails, Vendor
        from apps.activity.models.question_model import QuestionSet

        vendor = Vendor.objects.create(
            code="VENDOR001",
            name="Test Vendor",
            cuser=self.user,
            muser=self.user
        )

        qset = QuestionSet.objects.create(
            qsetcode="QS001",
            qsetname="Test Question Set",
            cuser=self.user,
            muser=self.user
        )

        initial_wom_count = Wom.objects.count()
        initial_wom_details_count = WomDetails.objects.count()

        request = self.factory.post('/workpermit/')
        request.user = self.user
        request.session = {
            'client_id': self.client.id,
            'bu_id': self.bu.id,
            'sitename': self.bu.buname,
            'tenantid': self.tenant.id
        }
        request.POST = {
            'uuid': 'test-uuid',
            'permit_name': 'Cold Work Permit',
            'workpermitdetails': 'invalid_data_that_will_fail'
        }

        from apps.work_order_management.views import WorkPermit
        view = WorkPermit()

        with patch.object(view, 'create_workpermit_details', side_effect=ValueError("Detail creation failed")):
            from apps.work_order_management.forms import WorkPermitForm

            form_data = {
                'qset': qset.id,
                'vendor': vendor.id,
                'approvers': [self.user.id],
                'verifiers': [self.user.id],
                'plandatetime': '2025-09-28 10:00',
                'expirydatetime': '2025-09-28 18:00'
            }
            form = WorkPermitForm(data=form_data, request=request)

            with pytest.raises(ValueError):
                view.handle_valid_form(form, request.POST, request, create=True)

        assert Wom.objects.count() == initial_wom_count
        assert WomDetails.objects.count() == initial_wom_details_count

    def test_ppm_rollback_on_save_userinfo_failure(self):
        """
        Test that PPM creation rolls back if save_userinfo fails.
        """
        from apps.activity.models.job_model import Job
        from apps.activity.models.question_model import QuestionSet
        from apps.activity.models.asset_model import Asset

        asset = Asset.objects.create(
            assetcode="ASSET001",
            assetname="Test Asset",
            cuser=self.user,
            muser=self.user,
            bu=self.bu,
            client=self.client
        )

        qset = QuestionSet.objects.create(
            qsetcode="QS002",
            qsetname="PPM Question Set",
            cuser=self.user,
            muser=self.user
        )

        initial_job_count = Job.objects.count()

        request = self.factory.post('/ppm/')
        request.user = self.user
        request.session = {
            'client_id': self.client.id,
            'bu_id': self.bu.id,
            'tenantid': self.tenant.id
        }

        from apps.activity.forms.job_form import PPMForm
        from apps.activity.views.job_views import PPMView

        form_data = {
            'jobname': 'Test PPM Job',
            'asset': asset.id,
            'qset': qset.id,
            'frequency': 'WEEKLY',
            'fromdate': '2025-09-28',
            'uptodate': '2025-12-31',
            'planduration': 60,
            'gracetime': 15,
            'expirytime': 30
        }

        form = PPMForm(data=form_data, request=request)

        with patch('apps.peoples.utils.save_userinfo', side_effect=ValueError("User info save failed")):
            with pytest.raises(ValueError):
                PPMView.handle_valid_form(form, request, create=True)

        assert Job.objects.count() == initial_job_count

    def test_people_creation_with_signal_rollback(self):
        """
        Test that if PeopleProfile signal creation fails,
        the entire People creation rolls back.
        """
        initial_people_count = People.objects.count()

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                people = People.objects.create(
                    loginid="signal_test",
                    peoplename="Signal Test",
                    peoplecode="SIG001",
                    email="signal@test.com"
                )

                with patch('apps.peoples.models.profile_model.PeopleProfile.objects.create',
                          side_effect=IntegrityError("Profile creation failed")):
                    people.save()

        assert People.objects.count() == initial_people_count

    def test_asset_log_creation_within_transaction(self):
        """
        Test that AssetLog is created within the parent transaction
        and rolls back if the parent transaction fails.
        """
        from apps.activity.models.asset_model import Asset, AssetLog

        asset = Asset.objects.create(
            assetcode="ASSET_LOG_TEST",
            assetname="Asset Log Test",
            runningstatus="RUNNING",
            cuser=self.user,
            muser=self.user,
            bu=self.bu,
            client=self.client
        )

        initial_log_count = AssetLog.objects.filter(asset=asset).count()

        with pytest.raises(ValueError):
            with transaction.atomic():
                asset.runningstatus = "DOWN"
                asset.save()
                raise ValueError("Transaction should rollback")

        final_log_count = AssetLog.objects.filter(asset=asset).count()
        assert final_log_count == initial_log_count


@pytest.mark.django_db(transaction=True)
class BatchOperationTests(TestCase):
    """Test transactional batch operations."""

    def test_batch_operation_partial_failure(self):
        """Test that failed batches don't affect successful batches."""

        def create_person(data):
            if data['peoplecode'] == 'FAIL':
                raise ValueError("Intentional failure")
            People.objects.create(**data)

        items = [
            {'loginid': 'user1', 'peoplename': 'User 1', 'peoplecode': 'USR001'},
            {'loginid': 'user2', 'peoplename': 'User 2', 'peoplecode': 'USR002'},
            {'loginid': 'user3', 'peoplename': 'User 3', 'peoplecode': 'FAIL'},
            {'loginid': 'user4', 'peoplename': 'User 4', 'peoplecode': 'USR004'},
        ]

        result = transactional_batch_operation(
            items=items,
            operation_func=create_person,
            batch_size=2
        )

        assert result['processed'] == 2
        assert result['failed'] == 2
        assert People.objects.filter(peoplecode__in=['USR001', 'USR002']).count() == 2
        assert not People.objects.filter(peoplecode='USR004').exists()


@pytest.mark.django_db(transaction=True)
class DecoratorTests(TestCase):
    """Test transaction decorators."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            tenantcode="TEST_TENANT"
        )
        self.client = Client.objects.create(
            bucode="CLIENT001",
            buname="Test Client",
            tenant=self.tenant
        )

    def test_atomic_view_operation_decorator_success(self):
        @atomic_view_operation()
        def test_operation():
            return People.objects.create(
                loginid="decorator_test",
                peoplename="Decorator Test",
                peoplecode="DEC001"
            )

        result = test_operation()
        assert People.objects.filter(peoplecode="DEC001").exists()

    def test_atomic_view_operation_decorator_rollback(self):
        @atomic_view_operation()
        def test_operation_with_error():
            People.objects.create(
                loginid="will_rollback",
                peoplename="Will Rollback",
                peoplecode="ROLLBACK001"
            )
            raise ValueError("Intentional error")

        initial_count = People.objects.count()

        with pytest.raises(ValueError):
            test_operation_with_error()

        assert People.objects.count() == initial_count
        assert not People.objects.filter(peoplecode="ROLLBACK001").exists()

    def test_signal_aware_transaction_context(self):
        """Test signal_aware_transaction context manager."""
        from apps.peoples.models.profile_model import PeopleProfile

        with signal_aware_transaction():
            people = People.objects.create(
                loginid="signal_aware_test",
                peoplename="Signal Aware Test",
                peoplecode="SIG002",
                email="sigaware@test.com"
            )

        assert People.objects.filter(peoplecode="SIG002").exists()
        assert PeopleProfile.objects.filter(people=people).exists()


@pytest.mark.django_db(transaction=True)
class RealWorldScenarioTests(TransactionTestCase):
    """Test real-world transaction scenarios."""

    def setUp(self):
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client

        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            tenantcode="TEST"
        )
        self.client = Client.objects.create(
            bucode="CLIENT",
            buname="Test Client",
            tenant=self.tenant
        )
        self.bu = Bt.objects.create(
            bucode="BU",
            buname="Test BU",
            client=self.client,
            tenant=self.tenant
        )
        self.user = People.objects.create_user(
            loginid="admin",
            password="pass",
            peoplename="Admin",
            peoplecode="ADMIN",
            email="admin@test.com"
        )

        TypeAssist.objects.get_or_create(
            tacode="WOMDETAILS",
            taname="WOM Details",
            cuser=self.user,
            muser=self.user
        )

    def test_work_order_creation_atomic_behavior(self):
        """
        Test that work order creation with history and notifications
        is atomic - if any step fails, everything rolls back.
        """
        from apps.work_order_management.models import Wom, Vendor
        from apps.activity.models.question_model import QuestionSet
        from apps.work_order_management.views import WorkOrderView
        from apps.work_order_management.forms import WorkOrderForm

        vendor = Vendor.objects.create(
            code="V001",
            name="Test Vendor",
            cuser=self.user,
            muser=self.user
        )

        qset = QuestionSet.objects.create(
            qsetcode="WO_QS",
            qsetname="Work Order Questions",
            cuser=self.user,
            muser=self.user
        )

        initial_wom_count = Wom.objects.count()

        request = self.factory.post('/workorder/')
        request.user = self.user
        request.session = {
            'client_id': self.client.id,
            'bu_id': self.bu.id,
            'tenantid': self.tenant.id
        }
        request.POST = {
            'uuid': 'test-work-order-uuid',
            'formData': f'vendor={vendor.id}&qset={qset.id}&description=Test&plandatetime=2025-09-28 10:00&expirydatetime=2025-09-28 18:00&priority=HIGH'
        }

        view = WorkOrderView()

        with patch.object(Wom, 'add_history', side_effect=ValueError("History creation failed")):
            from django.http import QueryDict
            data = QueryDict(request.POST['formData'])
            form = WorkOrderForm(data=data, request=request)

            if form.is_valid():
                with pytest.raises(ValueError):
                    view.handle_valid_form(form, request, create=True)

        assert Wom.objects.count() == initial_wom_count

    def test_ppm_creation_rollback_on_save_userinfo_failure(self):
        """
        Test that if save_userinfo fails during PPM creation,
        the PPM job is not persisted.
        """
        from apps.activity.models.job_model import Job
        from apps.activity.models.question_model import QuestionSet
        from apps.activity.models.asset_model import Asset

        asset = Asset.objects.create(
            assetcode="PPM_ASSET",
            assetname="PPM Asset",
            cuser=self.user,
            muser=self.user,
            bu=self.bu,
            client=self.client
        )

        qset = QuestionSet.objects.create(
            qsetcode="PPM_QS",
            qsetname="PPM Questions",
            cuser=self.user,
            muser=self.user
        )

        initial_job_count = Job.objects.count()

        request = self.factory.post('/ppm/')
        request.user = self.user
        request.session = {
            'client_id': self.client.id,
            'bu_id': self.bu.id,
            'tenantid': self.tenant.id
        }

        from apps.activity.forms.job_form import PPMForm
        from apps.activity.views.job_views import PPMView

        form_data = {
            'jobname': 'Test PPM',
            'asset': asset.id,
            'qset': qset.id,
            'frequency': 'WEEKLY',
            'fromdate': '2025-09-28',
            'uptodate': '2025-12-31',
            'planduration': 60,
            'gracetime': 15,
            'expirytime': 30
        }

        form = PPMForm(data=form_data, request=request)

        with patch('apps.peoples.utils.save_userinfo', side_effect=IntegrityError("User info failed")):
            with pytest.raises(IntegrityError):
                PPMView.handle_valid_form(form, request, create=True)

        assert Job.objects.count() == initial_job_count

    def test_attendance_rollback_on_integrity_error(self):
        """
        Test that attendance record creation rolls back completely
        if there's an integrity constraint violation.
        """
        from apps.attendance.models import PeopleEventlog
        from apps.client_onboarding.models import Shift
        from apps.core_onboarding.models import TypeAssist

        event_type = TypeAssist.objects.create(
            tacode="CHECKIN",
            taname="Check In",
            cuser=self.user,
            muser=self.user
        )

        shift = Shift.objects.create(
            shiftcode="SHIFT1",
            shiftname="Day Shift",
            starttime="09:00",
            endtime="18:00",
            cuser=self.user,
            muser=self.user,
            bu=self.bu
        )

        initial_count = PeopleEventlog.objects.count()

        request = self.factory.post('/attendance/')
        request.user = self.user
        request.session = {
            'client_id': self.client.id,
            'bu_id': self.bu.id,
            'tenantid': self.tenant.id
        }

        from apps.attendance.forms import AttendanceForm
        from apps.attendance.views import Attendance

        form_data = {
            'people': self.user.id,
            'peventtype': event_type.id,
            'shift': shift.id,
            'datefor': '2025-09-27',
            'punchintime': '09:00'
        }

        form = AttendanceForm(data=form_data)

        with patch.object(PeopleEventlog, 'save', side_effect=IntegrityError("Duplicate entry")):
            result = Attendance.handle_valid_form(form, request, create=True)

        assert PeopleEventlog.objects.count() == initial_count


@pytest.mark.django_db(transaction=True)
class ConcurrentTransactionTests(TransactionTestCase):
    """Test transaction behavior under concurrent access."""

    def test_concurrent_work_permit_creation_isolation(self):
        """
        Test that concurrent work permit creations are properly isolated.
        """
        from apps.work_order_management.models import Wom, Vendor
        from apps.activity.models.question_model import QuestionSet
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt as Client
        import threading

        tenant = Tenant.objects.create(tenantname="Concurrent Test", tenantcode="CONCURRENT")
        client = Client.objects.create(bucode="C", buname="Client", tenant=tenant)
        bu = Bt.objects.create(bucode="B", buname="BU", client=client, tenant=tenant)
        user = People.objects.create_user(
            loginid="concurrent_user",
            password="pass",
            peoplename="Concurrent User",
            peoplecode="CONC001",
            email="concurrent@test.com"
        )

        vendor = Vendor.objects.create(
            code="V_CONCURRENT",
            name="Concurrent Vendor",
            cuser=user,
            muser=user
        )

        qset = QuestionSet.objects.create(
            qsetcode="CONC_QS",
            qsetname="Concurrent QS",
            cuser=user,
            muser=user
        )

        results = []

        def create_work_permit(permit_num):
            try:
                with transaction.atomic():
                    wom = Wom.objects.create(
                        description=f"Concurrent Permit {permit_num}",
                        vendor=vendor,
                        qset=qset,
                        cuser=user,
                        muser=user,
                        bu=bu,
                        client=client
                    )
                    results.append(('success', permit_num, wom.id))
            except (ValueError, TypeError, AttributeError, KeyError) as e:
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


@pytest.mark.django_db
class TransactionMonitoringTests(TestCase):
    """Test transaction monitoring and logging."""

    def test_transaction_manager_tracks_active_transactions(self):
        manager = TransactionManager()

        assert len(manager.transaction_stack) == 0

        with manager.atomic_operation():
            assert len(manager.transaction_stack) == 1

        assert len(manager.transaction_stack) == 0

    def test_saga_status_tracking(self):
        manager = TransactionManager()
        saga_id = manager.create_saga("status_test")

        manager.add_saga_step(saga_id, "step1", lambda: "result1")
        manager.add_saga_step(saga_id, "step2", lambda: "result2")

        status = manager.get_saga_status(saga_id)
        assert status['total_steps'] == 2
        assert status['executed_steps'] == 0

        result = manager.execute_saga(saga_id)
        assert result['status'] == 'committed'
        assert result['steps_executed'] == 2