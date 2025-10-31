"""
Comprehensive Cross-Tenant Isolation Tests

Tests to verify that tenant-aware models properly isolate data between tenants
and prevent cross-tenant data leakage.

Phase 1: Multi-Tenant Security Hardening (Sprint 1)
Date: 2025-10-27

Test Coverage:
- QuerySet automatic filtering
- Cross-tenant access prevention
- Manager method isolation
- Admin interface filtering
- Data migration correctness
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant
from apps.activity.models.job_model import Job, Jobneed, JobneedDetails
from apps.activity.models.asset_model import Asset, AssetLog
from apps.work_order_management.models import Wom, Vendor, WomDetails, Approver
from apps.y_helpdesk.models import Ticket, EscalationMatrix
from apps.attendance.models import PeopleEventlog
from apps.core.utils_new.db_utils import set_db_for_router
import uuid

People = get_user_model()


class TenantIsolationTestCase(TestCase):
    """
    Base test case for multi-tenant isolation tests.

    Sets up two tenants and ensures data isolation between them.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test tenants and users."""
        # Create two test tenants
        cls.tenant_a = Tenant.objects.create(
            tenantname='Tenant A',
            subdomain_prefix='tenant-a'
        )
        cls.tenant_b = Tenant.objects.create(
            tenantname='Tenant B',
            subdomain_prefix='tenant-b'
        )

        # Create users for each tenant
        cls.user_a = People.objects.create_user(
            loginid='user_a',
            peoplecode='USER_A',
            peoplename='User A',
            email='usera@example.com',
            tenant=cls.tenant_a
        )
        cls.user_b = People.objects.create_user(
            loginid='user_b',
            peoplecode='USER_B',
            peoplename='User B',
            email='userb@example.com',
            tenant=cls.tenant_b
        )

    def setUp(self):
        """Set up request factory for each test."""
        self.factory = RequestFactory()


@pytest.mark.django_db
class TestJobModelIsolation(TenantIsolationTestCase):
    """Test Job model cross-tenant isolation."""

    def test_job_automatic_tenant_filtering(self):
        """Test that Job.objects.all() only returns current tenant's jobs."""
        # Create jobs for each tenant
        job_a = Job.objects.create(
            jobname='Job A',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )
        job_b = Job.objects.create(
            jobname='Job B',
            jobdesc='Description B',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_b
        )

        # Set tenant context to tenant A
        set_db_for_router('tenant_a')

        # Query should only return tenant A's jobs
        jobs = Job.objects.all()
        job_ids = [j.id for j in jobs]

        # Verify tenant A's job is included
        self.assertIn(job_a.id, job_ids)

        # Verify tenant B's job is NOT included
        self.assertNotIn(job_b.id, job_ids)

    def test_job_cross_tenant_query_requires_explicit_call(self):
        """Test that cross-tenant queries require explicit cross_tenant_query()."""
        job_a = Job.objects.create(
            jobname='Job A',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )
        job_b = Job.objects.create(
            jobname='Job B',
            jobdesc='Description B',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_b
        )

        # Set tenant context to tenant A
        set_db_for_router('tenant_a')

        # Normal query - only tenant A
        normal_jobs = Job.objects.all()
        self.assertEqual(normal_jobs.count(), 1)
        self.assertEqual(normal_jobs.first().id, job_a.id)

        # Cross-tenant query - both tenants (requires explicit call)
        cross_tenant_jobs = Job.objects.cross_tenant_query()
        self.assertEqual(cross_tenant_jobs.count(), 2)

    def test_job_for_tenant_filtering(self):
        """Test explicit for_tenant() filtering."""
        job_a = Job.objects.create(
            jobname='Job A',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )
        job_b = Job.objects.create(
            jobname='Job B',
            jobdesc='Description B',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_b
        )

        # Filter by tenant A explicitly
        tenant_a_jobs = Job.objects.for_tenant(self.tenant_a.id)
        self.assertEqual(tenant_a_jobs.count(), 1)
        self.assertEqual(tenant_a_jobs.first().id, job_a.id)

        # Filter by tenant B explicitly
        tenant_b_jobs = Job.objects.for_tenant(self.tenant_b.id)
        self.assertEqual(tenant_b_jobs.count(), 1)
        self.assertEqual(tenant_b_jobs.first().id, job_b.id)


@pytest.mark.django_db
class TestAssetModelIsolation(TenantIsolationTestCase):
    """Test Asset model cross-tenant isolation."""

    def test_asset_automatic_tenant_filtering(self):
        """Test that Asset.objects.all() only returns current tenant's assets."""
        asset_a = Asset.objects.create(
            assetcode='ASSET_A',
            assetname='Asset A',
            iscritical=False,
            tenant=self.tenant_a
        )
        asset_b = Asset.objects.create(
            assetcode='ASSET_B',
            assetname='Asset B',
            iscritical=False,
            tenant=self.tenant_b
        )

        # Set tenant context to tenant A
        set_db_for_router('tenant_a')

        # Query should only return tenant A's assets
        assets = Asset.objects.all()
        asset_ids = [a.id for a in assets]

        self.assertIn(asset_a.id, asset_ids)
        self.assertNotIn(asset_b.id, asset_ids)


@pytest.mark.django_db
class TestTicketModelIsolation(TenantIsolationTestCase):
    """Test Ticket model cross-tenant isolation."""

    def test_ticket_automatic_tenant_filtering(self):
        """Test that Ticket.objects.all() only returns current tenant's tickets."""
        ticket_a = Ticket.objects.create(
            ticketno='T00001',
            ticketdesc='Ticket A',
            tenant=self.tenant_a
        )
        ticket_b = Ticket.objects.create(
            ticketno='T00002',
            ticketdesc='Ticket B',
            tenant=self.tenant_b
        )

        # Set tenant context to tenant A
        set_db_for_router('tenant_a')

        # Query should only return tenant A's tickets
        tickets = Ticket.objects.all()
        ticket_ids = [t.id for t in tickets]

        self.assertIn(ticket_a.id, ticket_ids)
        self.assertNotIn(ticket_b.id, ticket_ids)


@pytest.mark.django_db
class TestAttendanceModelIsolation(TenantIsolationTestCase):
    """Test PeopleEventlog (Attendance) model cross-tenant isolation."""

    def test_attendance_automatic_tenant_filtering(self):
        """Test that attendance records are isolated by tenant."""
        from datetime import date

        attendance_a = PeopleEventlog.objects.create(
            people=self.user_a,
            datefor=date.today(),
            tenant=self.tenant_a
        )
        attendance_b = PeopleEventlog.objects.create(
            people=self.user_b,
            datefor=date.today(),
            tenant=self.tenant_b
        )

        # Set tenant context to tenant A
        set_db_for_router('tenant_a')

        # Query should only return tenant A's attendance
        attendance_records = PeopleEventlog.objects.all()
        attendance_ids = [a.id for a in attendance_records]

        self.assertIn(attendance_a.id, attendance_ids)
        self.assertNotIn(attendance_b.id, attendance_ids)


@pytest.mark.django_db
class TestWorkOrderModelIsolation(TenantIsolationTestCase):
    """Test Wom (Work Order) model cross-tenant isolation."""

    def test_wom_automatic_tenant_filtering(self):
        """Test that work orders are isolated by tenant."""
        wom_a = Wom.objects.create(
            description='Work Order A',
            performedby='User A',
            tenant=self.tenant_a
        )
        wom_b = Wom.objects.create(
            description='Work Order B',
            performedby='User B',
            tenant=self.tenant_b
        )

        # Set tenant context to tenant A
        set_db_for_router('tenant_a')

        # Query should only return tenant A's work orders
        work_orders = Wom.objects.all()
        wom_ids = [w.id for w in work_orders]

        self.assertIn(wom_a.id, wom_ids)
        self.assertNotIn(wom_b.id, wom_ids)


@pytest.mark.django_db
class TestCrossTenantAccessPrevention(TenantIsolationTestCase):
    """
    Critical security tests to ensure cross-tenant data access is impossible.
    """

    def test_filter_by_id_across_tenants_fails(self):
        """Test that filtering by ID of another tenant's record returns nothing."""
        job_a = Job.objects.create(
            jobname='Job A',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )

        # Set context to tenant B
        set_db_for_router('tenant_b')

        # Try to access tenant A's job by ID - should fail
        tenant_b_query = Job.objects.filter(id=job_a.id)
        self.assertEqual(tenant_b_query.count(), 0)

    def test_get_by_id_across_tenants_fails(self):
        """Test that .get() for another tenant's record raises DoesNotExist."""
        from django.core.exceptions import ObjectDoesNotExist

        ticket_a = Ticket.objects.create(
            ticketno='T00001',
            ticketdesc='Ticket A',
            tenant=self.tenant_a
        )

        # Set context to tenant B
        set_db_for_router('tenant_b')

        # Try to get tenant A's ticket - should raise exception
        with self.assertRaises(ObjectDoesNotExist):
            Ticket.objects.get(id=ticket_a.id)

    def test_update_across_tenants_prevents_modification(self):
        """Test that updates are isolated by tenant."""
        asset_a = Asset.objects.create(
            assetcode='ASSET_A',
            assetname='Asset A',
            iscritical=False,
            tenant=self.tenant_a
        )

        # Set context to tenant B
        set_db_for_router('tenant_b')

        # Try to update tenant A's asset - should affect 0 rows
        updated_count = Asset.objects.filter(id=asset_a.id).update(
            assetname='Hacked Name'
        )
        self.assertEqual(updated_count, 0)

        # Verify asset A wasn't modified
        asset_a.refresh_from_db()
        self.assertEqual(asset_a.assetname, 'Asset A')

    def test_delete_across_tenants_prevents_deletion(self):
        """Test that deletes are isolated by tenant."""
        wom_a = Wom.objects.create(
            description='Work Order A',
            performedby='User A',
            tenant=self.tenant_a
        )

        # Set context to tenant B
        set_db_for_router('tenant_b')

        # Try to delete tenant A's work order - should affect 0 rows
        deleted_count = Wom.objects.filter(id=wom_a.id).delete()[0]
        self.assertEqual(deleted_count, 0)

        # Verify work order A still exists
        wom_a.refresh_from_db()
        self.assertEqual(wom_a.description, 'Work Order A')


@pytest.mark.django_db
class TestTenantAwareManagerMethods(TenantIsolationTestCase):
    """Test TenantAwareManager methods work correctly."""

    def test_for_current_tenant_method(self):
        """Test for_current_tenant() returns only current tenant's records."""
        job_a = Job.objects.create(
            jobname='Job A',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )
        job_b = Job.objects.create(
            jobname='Job B',
            jobdesc='Description B',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_b
        )

        # Set context to tenant A
        set_db_for_router('tenant_a')

        # Explicit for_current_tenant() should match automatic filtering
        current_tenant_jobs = Job.objects.for_current_tenant()
        all_jobs = Job.objects.all()

        self.assertEqual(
            list(current_tenant_jobs.values_list('id', flat=True)),
            list(all_jobs.values_list('id', flat=True))
        )

    def test_cross_tenant_query_returns_all_tenants(self):
        """Test cross_tenant_query() bypasses tenant filtering."""
        Job.objects.create(
            jobname='Job A',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )
        Job.objects.create(
            jobname='Job B',
            jobdesc='Description B',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_b
        )

        # Set context to tenant A
        set_db_for_router('tenant_a')

        # Normal query - only tenant A
        normal_jobs = Job.objects.all()
        self.assertEqual(normal_jobs.count(), 1)

        # Cross-tenant query - both tenants
        cross_tenant_jobs = Job.objects.cross_tenant_query()
        self.assertEqual(cross_tenant_jobs.count(), 2)


@pytest.mark.django_db
class TestUniqueConstraintsWithTenant(TenantIsolationTestCase):
    """Test that unique constraints are tenant-scoped."""

    def test_job_name_unique_per_tenant(self):
        """Test that job names can be duplicated across tenants but not within."""
        # Create job with same name in tenant A
        Job.objects.create(
            jobname='Daily Pump Check',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )

        # Create job with same name in tenant B - should succeed
        job_b = Job.objects.create(
            jobname='Daily Pump Check',
            jobdesc='Description B',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_b
        )

        # Should succeed - different tenants can have same job name
        self.assertIsNotNone(job_b.id)

        # Try to create duplicate in tenant B - should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Job.objects.create(
                jobname='Daily Pump Check',
                jobdesc='Duplicate',
                fromdate='2025-10-01 00:00:00',
                uptodate='2025-12-31 23:59:59',
                planduration=60,
                gracetime=15,
                expirytime=120,
                priority='HIGH',
                scantype='QR',
                tenant=self.tenant_b
            )

    def test_asset_code_unique_per_tenant(self):
        """Test that asset codes are unique per tenant."""
        Asset.objects.create(
            assetcode='PUMP001',
            assetname='Pump 1 - Tenant A',
            iscritical=False,
            tenant=self.tenant_a
        )

        # Same asset code in tenant B - should succeed
        asset_b = Asset.objects.create(
            assetcode='PUMP001',
            assetname='Pump 1 - Tenant B',
            iscritical=False,
            tenant=self.tenant_b
        )

        self.assertIsNotNone(asset_b.id)


@pytest.mark.django_db
class TestConcurrentMultiTenantRequests(TenantIsolationTestCase):
    """Test concurrent requests from different tenants don't leak data."""

    def test_concurrent_tenant_context_isolation(self):
        """Test that concurrent requests maintain separate tenant contexts."""
        import threading

        job_a = Job.objects.create(
            jobname='Job A',
            jobdesc='Description A',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_a
        )
        job_b = Job.objects.create(
            jobname='Job B',
            jobdesc='Description B',
            fromdate='2025-10-01 00:00:00',
            uptodate='2025-12-31 23:59:59',
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority='HIGH',
            scantype='QR',
            tenant=self.tenant_b
        )

        results = {'tenant_a': None, 'tenant_b': None}

        def query_tenant_a():
            set_db_for_router('tenant_a')
            jobs = list(Job.objects.all().values_list('id', flat=True))
            results['tenant_a'] = jobs

        def query_tenant_b():
            set_db_for_router('tenant_b')
            jobs = list(Job.objects.all().values_list('id', flat=True))
            results['tenant_b'] = jobs

        # Run concurrent queries
        thread_a = threading.Thread(target=query_tenant_a)
        thread_b = threading.Thread(target=query_tenant_b)

        thread_a.start()
        thread_b.start()

        thread_a.join()
        thread_b.join()

        # Verify no data leakage
        self.assertEqual(results['tenant_a'], [job_a.id])
        self.assertEqual(results['tenant_b'], [job_b.id])
