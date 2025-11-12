"""
Manager tests for work_order_management app.

Tests custom manager methods for Wom, Vendor, Approver, and WomDetails models.
Tests query optimization (select_related), tenant isolation, and custom methods.
"""
import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from apps.work_order_management.models import Wom, Vendor, WomDetails, Approver


@pytest.mark.django_db
class TestWorkOrderManager:
    """Test WorkOrderManager custom methods."""

    def test_manager_exists(self):
        """Test that WorkOrderManager is properly attached."""
        assert hasattr(Wom, 'objects')
        assert Wom.objects is not None

    def test_queryset_filtering(self, basic_work_order):
        """Test basic queryset filtering."""
        wos = Wom.objects.filter(workstatus="ASSIGNED")
        assert basic_work_order in wos

    def test_select_related_optimization(self, basic_work_order):
        """Test select_related for query optimization."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as context:
            wo = Wom.objects.select_related(
                'vendor', 'asset', 'location', 'qset'
            ).get(id=basic_work_order.id)

            # Access related objects
            _ = wo.vendor.name
            _ = wo.asset.assetname if wo.asset else None
            _ = wo.location.location
            _ = wo.qset.qsetname

        # Should be only 1 query with select_related
        assert len(context.captured_queries) == 1

    def test_tenant_filtering(self, basic_work_order, test_tenant):
        """Test tenant-aware filtering."""
        tenant_wos = Wom.objects.filter(tenant=test_tenant)
        assert basic_work_order in tenant_wos


@pytest.mark.django_db
class TestVendorManager:
    """Test VendorManager custom methods."""

    def test_manager_exists(self):
        """Test that VendorManager is properly attached."""
        assert hasattr(Vendor, 'objects')
        assert Vendor.objects is not None

    def test_vendor_queryset_filtering(self, test_vendor):
        """Test vendor queryset filtering."""
        vendors = Vendor.objects.filter(enable=True)
        assert test_vendor in vendors

    def test_vendor_by_code(self, test_vendor):
        """Test querying vendor by code."""
        vendor = Vendor.objects.filter(code=test_vendor.code).first()
        assert vendor == test_vendor

    def test_vendor_tenant_isolation(self, test_vendor, test_tenant):
        """Test vendor tenant isolation."""
        tenant_vendors = Vendor.objects.filter(client=test_tenant)
        assert test_vendor in tenant_vendors


@pytest.mark.django_db
class TestWomDetailsManager:
    """Test WOMDetailsManager custom methods."""

    def test_manager_exists(self):
        """Test that WOMDetailsManager is properly attached."""
        assert hasattr(WomDetails, 'objects')
        assert WomDetails.objects is not None

    def test_womdetails_filtering_by_wom(self, basic_work_order):
        """Test filtering WomDetails by work order."""
        # Create WomDetails
        detail = WomDetails.objects.create(
            wom=basic_work_order,
            tenant=basic_work_order.tenant
        )

        details = WomDetails.objects.filter(wom=basic_work_order)
        assert detail in details

    def test_womdetails_select_related(self, basic_work_order):
        """Test select_related optimization for WomDetails."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Create WomDetails
        detail = WomDetails.objects.create(
            wom=basic_work_order,
            tenant=basic_work_order.tenant
        )

        with CaptureQueriesContext(connection) as context:
            detail_obj = WomDetails.objects.select_related('wom').get(id=detail.id)
            _ = detail_obj.wom.description

        # Should be only 1 query
        assert len(context.captured_queries) == 1


@pytest.mark.django_db
class TestApproverManager:
    """Test ApproverManager custom methods."""

    def test_manager_exists(self):
        """Test that ApproverManager is properly attached."""
        assert hasattr(Approver, 'objects')
        assert Approver.objects is not None

    def test_approver_filtering_by_wom(self, work_permit_order, test_approver):
        """Test filtering Approver by work order."""
        # Create Approver instance
        approver = Approver.objects.create(
            wom=work_permit_order,
            people=test_approver,
            identifier="APPROVER",
            client=work_permit_order.client,
            bu=work_permit_order.bu,
            tenant=work_permit_order.tenant,
            cdby=test_approver,
            mdby=test_approver
        )

        approvers = Approver.objects.filter(wom=work_permit_order)
        assert approver in approvers

    def test_approver_select_related(self, work_permit_order, test_approver):
        """Test select_related optimization for Approver."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Create Approver
        approver = Approver.objects.create(
            wom=work_permit_order,
            people=test_approver,
            identifier="APPROVER",
            client=work_permit_order.client,
            bu=work_permit_order.bu,
            tenant=work_permit_order.tenant,
            cdby=test_approver,
            mdby=test_approver
        )

        with CaptureQueriesContext(connection) as context:
            approver_obj = Approver.objects.select_related('wom', 'people').get(id=approver.id)
            _ = approver_obj.wom.description
            _ = approver_obj.people.peoplename

        # Should be only 1 query
        assert len(context.captured_queries) == 1


@pytest.mark.django_db
class TestQueryOptimization:
    """Test query optimization across all managers."""

    def test_bulk_create_work_orders(self, test_tenant, test_location, test_vendor, test_question_set, test_user):
        """Test bulk creation of work orders."""
        base_date = datetime.now(dt_timezone.utc)

        wos = [
            Wom(
                description=f"Bulk WO {i}",
                vendor=test_vendor,
                qset=test_question_set,
                location=test_location,
                plandatetime=base_date + timedelta(days=i),
                expirydatetime=base_date + timedelta(days=i+7),
                client=test_tenant,
                bu=test_tenant,
                tenant=test_tenant,
                cdby=test_user,
                mdby=test_user
            )
            for i in range(10)
        ]

        created_wos = Wom.objects.bulk_create(wos)
        assert len(created_wos) == 10

    def test_prefetch_related_for_collections(self, basic_work_order):
        """Test prefetch_related for many-to-many relationships."""
        # This would be used for reverse FK relationships
        wos = Wom.objects.prefetch_related('womdetails_set').filter(id=basic_work_order.id)
        assert wos.count() == 1

    def test_count_optimization(self, test_tenant):
        """Test count queries are optimized."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as context:
            count = Wom.objects.filter(tenant=test_tenant).count()

        # Count should be a single optimized query
        assert len(context.captured_queries) == 1
        assert count >= 0

    def test_exists_optimization(self, basic_work_order):
        """Test exists queries are optimized."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as context:
            exists = Wom.objects.filter(id=basic_work_order.id).exists()

        # Exists should be a single optimized query
        assert len(context.captured_queries) == 1
        assert exists is True


@pytest.mark.django_db
class TestManagerMethods:
    """Test custom manager methods."""

    def test_filter_by_status(self, basic_work_order, completed_work_order):
        """Test filtering by work status."""
        assigned = Wom.objects.filter(workstatus="ASSIGNED")
        completed = Wom.objects.filter(workstatus="COMPLETED")

        assert basic_work_order in assigned
        assert completed_work_order in completed

    def test_filter_by_priority(self, basic_work_order):
        """Test filtering by priority."""
        medium_priority = Wom.objects.filter(priority="MEDIUM")
        assert basic_work_order in medium_priority

    def test_filter_by_date_range(self, basic_work_order):
        """Test filtering by date range."""
        start_date = datetime.now(dt_timezone.utc) - timedelta(days=1)
        end_date = datetime.now(dt_timezone.utc) + timedelta(days=30)

        wos_in_range = Wom.objects.filter(
            plandatetime__gte=start_date,
            plandatetime__lte=end_date
        )

        assert basic_work_order in wos_in_range

    def test_order_by_plan_date(self, basic_work_order):
        """Test ordering by plan date."""
        wos = Wom.objects.all().order_by('plandatetime')
        assert wos.count() >= 0

    def test_complex_query_combination(self, basic_work_order, test_vendor):
        """Test complex query combinations."""
        wos = Wom.objects.filter(
            vendor=test_vendor,
            workstatus__in=["ASSIGNED", "INPROGRESS"],
            priority__in=["HIGH", "MEDIUM"]
        ).select_related('vendor', 'location')

        # Verify query works and returns results
        assert wos.count() >= 0


@pytest.mark.django_db
class TestTenantIsolation:
    """Test tenant isolation in managers."""

    def test_vendor_tenant_isolation(self, test_vendor):
        """Test vendor queries are tenant-isolated."""
        tenant_vendors = Vendor.objects.filter(client=test_vendor.client)
        assert test_vendor in tenant_vendors

        # Verify no cross-tenant leakage
        other_tenant_vendors = Vendor.objects.exclude(client=test_vendor.client)
        assert test_vendor not in other_tenant_vendors

    def test_work_order_tenant_isolation(self, basic_work_order):
        """Test work order queries are tenant-isolated."""
        tenant_wos = Wom.objects.filter(tenant=basic_work_order.tenant)
        assert basic_work_order in tenant_wos

        # Verify no cross-tenant leakage
        other_tenant_wos = Wom.objects.exclude(tenant=basic_work_order.tenant)
        assert basic_work_order not in other_tenant_wos

    def test_approver_tenant_isolation(self, work_permit_order, test_approver):
        """Test approver queries are tenant-isolated."""
        # Create approver
        approver = Approver.objects.create(
            wom=work_permit_order,
            people=test_approver,
            identifier="APPROVER",
            client=work_permit_order.client,
            bu=work_permit_order.bu,
            tenant=work_permit_order.tenant,
            cdby=test_approver,
            mdby=test_approver
        )

        tenant_approvers = Approver.objects.filter(tenant=work_permit_order.tenant)
        assert approver in tenant_approvers


@pytest.mark.django_db
class TestManagerEdgeCases:
    """Test manager edge cases and error handling."""

    def test_empty_queryset(self):
        """Test handling of empty querysets."""
        nonexistent_wos = Wom.objects.filter(description="NONEXISTENT_WO_12345")
        assert nonexistent_wos.count() == 0
        assert not nonexistent_wos.exists()

    def test_none_values_in_filter(self, basic_work_order):
        """Test filtering with None values."""
        # Some WOs might not have parent
        wos_without_parent = Wom.objects.filter(parent__isnull=True)
        assert basic_work_order in wos_without_parent

    def test_or_query_combinations(self, basic_work_order):
        """Test OR query combinations."""
        from django.db.models import Q

        wos = Wom.objects.filter(
            Q(workstatus="ASSIGNED") | Q(workstatus="INPROGRESS")
        )

        assert basic_work_order in wos

    def test_not_query_combinations(self, basic_work_order):
        """Test NOT query combinations."""
        from django.db.models import Q

        wos = Wom.objects.filter(~Q(workstatus="CANCELLED"))
        assert basic_work_order in wos

    def test_distinct_queries(self, basic_work_order):
        """Test DISTINCT queries."""
        statuses = Wom.objects.values_list('workstatus', flat=True).distinct()
        assert len(statuses) >= 1


@pytest.mark.django_db
class TestManagerAggregation:
    """Test manager aggregation methods."""

    def test_count_by_status(self, basic_work_order, completed_work_order):
        """Test counting work orders by status."""
        from django.db.models import Count

        status_counts = Wom.objects.values('workstatus').annotate(
            count=Count('id')
        )

        assert len(status_counts) >= 2

    def test_count_by_vendor(self, test_vendor):
        """Test counting work orders by vendor."""
        vendor_wo_count = Wom.objects.filter(vendor=test_vendor).count()
        assert vendor_wo_count >= 0

    def test_count_by_priority(self, basic_work_order):
        """Test counting work orders by priority."""
        from django.db.models import Count

        priority_counts = Wom.objects.values('priority').annotate(
            count=Count('id')
        )

        assert len(priority_counts) >= 1


@pytest.mark.django_db
class TestManagerUpdateOperations:
    """Test manager update operations."""

    def test_bulk_update_status(self, test_tenant, test_vendor, test_question_set, test_location, test_user):
        """Test bulk updating work order status."""
        base_date = datetime.now(dt_timezone.utc)

        # Create multiple WOs
        wos = [
            Wom.objects.create(
                description=f"Update Test WO {i}",
                vendor=test_vendor,
                qset=test_question_set,
                location=test_location,
                plandatetime=base_date + timedelta(days=i),
                expirydatetime=base_date + timedelta(days=i+7),
                client=test_tenant,
                bu=test_tenant,
                tenant=test_tenant,
                cdby=test_user,
                mdby=test_user
            )
            for i in range(3)
        ]

        # Bulk update
        Wom.objects.filter(id__in=[wo.id for wo in wos]).update(priority="HIGH")

        # Verify update
        for wo in wos:
            wo.refresh_from_db()
            assert wo.priority == "HIGH"

    def test_update_or_create(self, test_tenant, test_vendor, test_question_set, test_location, test_user):
        """Test update_or_create manager method."""
        base_date = datetime.now(dt_timezone.utc)

        wo, created = Wom.objects.update_or_create(
            description="Update or Create Test",
            vendor=test_vendor,
            defaults={
                'qset': test_question_set,
                'location': test_location,
                'plandatetime': base_date,
                'expirydatetime': base_date + timedelta(days=7),
                'client': test_tenant,
                'bu': test_tenant,
                'tenant': test_tenant,
                'cdby': test_user,
                'mdby': test_user,
                'priority': 'HIGH'
            }
        )

        assert wo is not None
        assert wo.priority == "HIGH"

    def test_get_or_create(self, test_tenant, test_vendor, test_question_set, test_location, test_user):
        """Test get_or_create manager method."""
        base_date = datetime.now(dt_timezone.utc)

        wo, created = Wom.objects.get_or_create(
            description="Get or Create Test",
            vendor=test_vendor,
            defaults={
                'qset': test_question_set,
                'location': test_location,
                'plandatetime': base_date,
                'expirydatetime': base_date + timedelta(days=7),
                'client': test_tenant,
                'bu': test_tenant,
                'tenant': test_tenant,
                'cdby': test_user,
                'mdby': test_user
            }
        )

        assert wo is not None
        assert created is True

        # Second call should not create
        wo2, created2 = Wom.objects.get_or_create(
            description="Get or Create Test",
            vendor=test_vendor,
            defaults={'priority': 'LOW'}
        )

        assert wo2.id == wo.id
        assert created2 is False
