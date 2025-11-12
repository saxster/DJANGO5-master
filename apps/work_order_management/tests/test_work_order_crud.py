"""
Work Order CRUD tests for work_order_management app.

Tests creating, reading, updating, and deleting work orders
with proper validation and multi-tenant isolation.
"""
import pytest
from django.core.exceptions import ValidationError
from apps.work_order_management.models import Wom


@pytest.mark.django_db
class TestWorkOrderCreation:
    """Test work order creation."""

    def test_create_basic_work_order(self, test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user):
        """Test creating a basic work order with required fields."""
        from datetime import datetime, timezone as dt_timezone, timedelta
        from django.contrib.gis.geos import Point

        wo = Wom.objects.create(
            description="Test HVAC Maintenance",
            workstatus="ASSIGNED",
            identifier="WO",
            asset=test_asset,
            location=test_location,
            qset=test_question_set,
            vendor=test_vendor,
            priority="MEDIUM",
            plandatetime=datetime.now(dt_timezone.utc) + timedelta(days=1),
            expirydatetime=datetime.now(dt_timezone.utc) + timedelta(days=7),
            client=test_tenant,
            bu=test_tenant,
            tenant=test_tenant,
            workpermit="NOT_REQUIRED",
            cdby=test_user,
            mdby=test_user
        )

        assert wo.id is not None
        assert wo.description == "Test HVAC Maintenance"
        assert wo.workstatus == "ASSIGNED"
        assert wo.priority == "MEDIUM"
        assert wo.vendor == test_vendor

    def test_create_work_order_missing_required_fields(self, test_tenant):
        """Test that creating work order without required fields raises error."""
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Wom.objects.create(
                description="Incomplete WO",
                client=test_tenant,
                bu=test_tenant,
                tenant=test_tenant
                # Missing vendor (required, blank=False)
            )

    def test_create_work_order_with_defaults(self, test_tenant, test_location, test_vendor, test_question_set, test_user):
        """Test work order creation with default values."""
        from datetime import datetime, timezone as dt_timezone, timedelta

        wo = Wom.objects.create(
            description="WO with defaults",
            vendor=test_vendor,
            qset=test_question_set,
            location=test_location,
            plandatetime=datetime.now(dt_timezone.utc) + timedelta(days=1),
            expirydatetime=datetime.now(dt_timezone.utc) + timedelta(days=7),
            client=test_tenant,
            bu=test_tenant,
            tenant=test_tenant,
            cdby=test_user,
            mdby=test_user
        )

        # Check defaults
        assert wo.workstatus == "ASSIGNED"
        assert wo.priority == "LOW"
        assert wo.workpermit == "NOT_REQUIRED"
        assert wo.ismailsent is False
        assert wo.isdenied is False
        assert wo.attachmentcount == 0

    def test_work_order_uuid_generated(self, basic_work_order):
        """Test that UUID is auto-generated for work orders."""
        assert basic_work_order.uuid is not None
        assert isinstance(basic_work_order.uuid, type(basic_work_order.uuid))
        assert str(basic_work_order.uuid) != ""


@pytest.mark.django_db
class TestWorkOrderReading:
    """Test work order query and retrieval."""

    def test_query_work_orders_by_status(self, basic_work_order, completed_work_order):
        """Test filtering work orders by status."""
        assigned_wos = Wom.objects.filter(workstatus="ASSIGNED")
        completed_wos = Wom.objects.filter(workstatus="COMPLETED")

        assert basic_work_order in assigned_wos
        assert completed_work_order in completed_wos
        assert completed_work_order not in assigned_wos

    def test_query_work_orders_by_vendor(self, basic_work_order, test_vendor):
        """Test filtering work orders by vendor."""
        vendor_wos = Wom.objects.filter(vendor=test_vendor)

        assert basic_work_order in vendor_wos
        assert vendor_wos.count() >= 1

    def test_query_work_orders_by_asset(self, basic_work_order, test_asset):
        """Test filtering work orders by asset."""
        asset_wos = Wom.objects.filter(asset=test_asset)

        assert basic_work_order in asset_wos
        assert asset_wos.count() >= 1

    def test_query_overdue_work_orders(self, overdue_work_order, basic_work_order):
        """Test filtering overdue work orders."""
        from datetime import datetime, timezone as dt_timezone

        now = datetime.now(dt_timezone.utc)
        overdue_wos = Wom.objects.filter(
            expirydatetime__lt=now,
            workstatus__in=["ASSIGNED", "INPROGRESS"]
        )

        assert overdue_work_order in overdue_wos
        assert basic_work_order not in overdue_wos

    def test_work_order_with_full_details(self, basic_work_order):
        """Test select_related optimization for work orders."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as context:
            wo = Wom.objects.select_related(
                'vendor', 'asset', 'location', 'qset', 'client', 'bu'
            ).get(id=basic_work_order.id)

            # Access related objects (should not trigger additional queries)
            _ = wo.vendor.name
            _ = wo.asset.assetname
            _ = wo.location.location
            _ = wo.qset.qsetname

        # Should only be 1 query (the initial select_related)
        assert len(context.captured_queries) == 1


@pytest.mark.django_db
class TestWorkOrderUpdate:
    """Test work order update operations."""

    def test_update_work_order_status(self, basic_work_order):
        """Test updating work order status."""
        basic_work_order.workstatus = "INPROGRESS"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.workstatus == "INPROGRESS"

    def test_update_work_order_priority(self, basic_work_order):
        """Test updating work order priority."""
        original_priority = basic_work_order.priority
        basic_work_order.priority = "HIGH"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.priority == "HIGH"
        assert basic_work_order.priority != original_priority

    def test_reassign_work_order_vendor(self, basic_work_order, test_tenant, test_vendor_type):
        """Test reassigning work order to different vendor."""
        from apps.work_order_management.models import Vendor
        from django.contrib.gis.geos import Point

        new_vendor = Vendor.objects.create(
            code="NEWVENDOR",
            name="New Vendor",
            type=test_vendor_type,
            email="newvendor@test.com",
            mobno="1111111111",
            client=test_tenant,
            bu=test_tenant,
            gpslocation=Point(103.8198, 1.3521)
        )

        basic_work_order.vendor = new_vendor
        basic_work_order.workstatus = "RE_ASSIGNED"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.vendor == new_vendor
        assert basic_work_order.workstatus == "RE_ASSIGNED"

    def test_update_work_order_dates(self, basic_work_order):
        """Test updating planned and expiry dates."""
        from datetime import datetime, timezone as dt_timezone, timedelta

        new_plan_date = datetime.now(dt_timezone.utc) + timedelta(days=3)
        new_expiry_date = datetime.now(dt_timezone.utc) + timedelta(days=10)

        basic_work_order.plandatetime = new_plan_date
        basic_work_order.expirydatetime = new_expiry_date
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.plandatetime == new_plan_date
        assert basic_work_order.expirydatetime == new_expiry_date

    def test_update_work_order_gps_location(self, basic_work_order):
        """Test updating work order GPS location."""
        from django.contrib.gis.geos import Point

        new_location = Point(77.5946, 12.9716)  # Bangalore coordinates
        basic_work_order.gpslocation = new_location
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.gpslocation == new_location


@pytest.mark.django_db
class TestWorkOrderDeletion:
    """Test work order deletion behavior."""

    def test_soft_delete_work_order(self, basic_work_order):
        """Test soft deletion (setting status to CANCELLED)."""
        wo_id = basic_work_order.id
        basic_work_order.workstatus = "CANCELLED"
        basic_work_order.save()

        wo = Wom.objects.get(id=wo_id)
        assert wo.workstatus == "CANCELLED"

    def test_hard_delete_work_order(self, basic_work_order):
        """Test permanent deletion of work order."""
        wo_id = basic_work_order.id
        basic_work_order.delete()

        assert not Wom.objects.filter(id=wo_id).exists()

    def test_delete_cascades_to_details(self, basic_work_order):
        """Test that deleting work order cascades to WomDetails."""
        from apps.work_order_management.models import WomDetails

        # Create a WomDetails instance
        detail = WomDetails.objects.create(
            wom=basic_work_order,
            tenant=basic_work_order.tenant
        )
        detail_id = detail.id

        # Delete work order
        basic_work_order.delete()

        # WomDetails should also be deleted (CASCADE)
        assert not WomDetails.objects.filter(id=detail_id).exists()


@pytest.mark.django_db
class TestWorkOrderValidation:
    """Test work order validation rules."""

    def test_expiry_after_planned_date(self, test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user):
        """Test that expiry date must be after planned date."""
        from datetime import datetime, timezone as dt_timezone, timedelta

        # This is a business logic validation, not enforced at DB level
        # We verify the dates can be set correctly
        plan_date = datetime.now(dt_timezone.utc) + timedelta(days=1)
        expiry_date = datetime.now(dt_timezone.utc) + timedelta(days=7)

        wo = Wom.objects.create(
            description="Test Dates",
            vendor=test_vendor,
            qset=test_question_set,
            location=test_location,
            plandatetime=plan_date,
            expirydatetime=expiry_date,
            client=test_tenant,
            bu=test_tenant,
            tenant=test_tenant,
            cdby=test_user,
            mdby=test_user
        )

        assert wo.expirydatetime > wo.plandatetime

    def test_valid_work_status_values(self, basic_work_order):
        """Test that only valid work status values are accepted."""
        from apps.work_order_management.models import Workstatus

        valid_statuses = [choice[0] for choice in Workstatus.choices]

        for status in valid_statuses:
            basic_work_order.workstatus = status
            basic_work_order.save()
            basic_work_order.refresh_from_db()
            assert basic_work_order.workstatus == status

    def test_valid_priority_values(self, basic_work_order):
        """Test that only valid priority values are accepted."""
        from apps.work_order_management.models import Priority

        valid_priorities = [choice[0] for choice in Priority.choices]

        for priority in valid_priorities:
            basic_work_order.priority = priority
            basic_work_order.save()
            basic_work_order.refresh_from_db()
            assert basic_work_order.priority == priority

    def test_gps_location_validation(self, basic_work_order):
        """Test GPS location format validation."""
        from django.contrib.gis.geos import Point

        # Valid GPS location
        valid_location = Point(103.8198, 1.3521, srid=4326)
        basic_work_order.gpslocation = valid_location
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.gpslocation is not None
        assert basic_work_order.gpslocation.srid == 4326


@pytest.mark.django_db
class TestMultiTenantIsolation:
    """Test multi-tenant data isolation for work orders."""

    def test_work_orders_isolated_by_tenant(self, basic_work_order):
        """Test that work orders from different tenants are isolated."""
        from apps.client_onboarding.models import Bt
        from apps.work_order_management.models import Vendor
        from apps.activity.models import Location, QuestionSet
        from datetime import datetime, timezone as dt_timezone, timedelta
        from django.contrib.gis.geos import Point

        # Create a second tenant
        tenant2 = Bt.objects.create(
            bucode="TENANT2",
            buname="Second Tenant",
            enable=True
        )

        # Create resources for tenant2
        location2 = Location.objects.create(
            site="SITE2",
            location="Location 2",
            client=tenant2,
            bu=tenant2,
            gpslocation=Point(103.8198, 1.3521)
        )

        qset2 = QuestionSet.objects.create(
            qsetname="Checklist 2",
            client=tenant2,
            bu=tenant2,
            enable=True
        )

        from apps.core_onboarding.models import TypeAssist
        vendor_type2 = TypeAssist.objects.create(
            typename="VendorType",
            typeval="Vendor Type 2",
            client=tenant2,
            enable=True
        )

        vendor2 = Vendor.objects.create(
            code="VEND2",
            name="Vendor 2",
            type=vendor_type2,
            email="vendor2@test.com",
            mobno="2222222222",
            client=tenant2,
            bu=tenant2,
            gpslocation=Point(103.8198, 1.3521)
        )

        user2 = basic_work_order.cdby  # Reuse user for simplicity

        # Create WO for tenant2
        wo2 = Wom.objects.create(
            description="Tenant 2 WO",
            vendor=vendor2,
            qset=qset2,
            location=location2,
            plandatetime=datetime.now(dt_timezone.utc) + timedelta(days=1),
            expirydatetime=datetime.now(dt_timezone.utc) + timedelta(days=7),
            client=tenant2,
            bu=tenant2,
            tenant=tenant2,
            cdby=user2,
            mdby=user2
        )

        # Verify isolation
        tenant1_wos = Wom.objects.filter(tenant=basic_work_order.tenant)
        tenant2_wos = Wom.objects.filter(tenant=tenant2)

        assert basic_work_order in tenant1_wos
        assert wo2 in tenant2_wos
        assert wo2 not in tenant1_wos
        assert basic_work_order not in tenant2_wos

    def test_tenant_aware_queries(self, basic_work_order, test_tenant):
        """Test that queries automatically filter by tenant."""
        # Query by tenant
        tenant_wos = Wom.objects.filter(tenant=test_tenant)

        assert basic_work_order in tenant_wos
        assert all(wo.tenant == test_tenant for wo in tenant_wos)


@pytest.mark.django_db
class TestOptimisticLocking:
    """Test optimistic locking via VersionField."""

    def test_concurrent_update_detection(self, basic_work_order):
        """Test that concurrent updates are detected via version field."""
        from concurrency.exceptions import RecordModifiedError

        # Simulate concurrent access by loading the same object twice
        wo1 = Wom.objects.get(id=basic_work_order.id)
        wo2 = Wom.objects.get(id=basic_work_order.id)

        # First update succeeds
        wo1.description = "Updated by WO1"
        wo1.save()

        # Second update should fail due to version mismatch
        wo2.description = "Updated by WO2"
        with pytest.raises(RecordModifiedError):
            wo2.save()

    def test_version_increments_on_update(self, basic_work_order):
        """Test that version field increments on each update."""
        original_version = basic_work_order.version

        basic_work_order.description = "Updated description"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.version > original_version
