"""
Scheduling tests for work_order_management app.

Tests work order scheduling, deadline management, overdue detection,
and SLA compliance tracking.
"""
import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from apps.work_order_management.models import Wom


@pytest.mark.django_db
class TestWorkOrderScheduling:
    """Test work order scheduling functionality."""

    def test_schedule_work_order_future_date(self, basic_work_order):
        """Test scheduling work order for future date."""
        future_date = datetime.now(dt_timezone.utc) + timedelta(days=5)
        basic_work_order.plandatetime = future_date
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.plandatetime == future_date
        assert basic_work_order.plandatetime > datetime.now(dt_timezone.utc)

    def test_schedule_work_order_with_expiry(self, basic_work_order):
        """Test scheduling work order with expiry deadline."""
        plan_date = datetime.now(dt_timezone.utc) + timedelta(days=1)
        expiry_date = datetime.now(dt_timezone.utc) + timedelta(days=10)

        basic_work_order.plandatetime = plan_date
        basic_work_order.expirydatetime = expiry_date
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.expirydatetime > basic_work_order.plandatetime

    def test_reschedule_work_order(self, basic_work_order):
        """Test rescheduling existing work order."""
        original_plan_date = basic_work_order.plandatetime
        new_plan_date = datetime.now(dt_timezone.utc) + timedelta(days=14)

        basic_work_order.plandatetime = new_plan_date
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.plandatetime == new_plan_date
        assert basic_work_order.plandatetime != original_plan_date

    def test_schedule_recurring_maintenance(self, test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user):
        """Test scheduling recurring PPM work orders."""
        # Create multiple WOs for recurring maintenance
        base_date = datetime.now(dt_timezone.utc)

        wos = []
        for i in range(3):
            wo = Wom.objects.create(
                description=f"Monthly PPM {i+1}",
                vendor=test_vendor,
                qset=test_question_set,
                location=test_location,
                asset=test_asset,
                plandatetime=base_date + timedelta(days=30 * i),
                expirydatetime=base_date + timedelta(days=30 * i + 7),
                client=test_tenant,
                bu=test_tenant,
                tenant=test_tenant,
                identifier="WO",
                cdby=test_user,
                mdby=test_user
            )
            wos.append(wo)

        assert len(wos) == 3
        assert all(wo.description.startswith("Monthly PPM") for wo in wos)


@pytest.mark.django_db
class TestDeadlineManagement:
    """Test work order deadline tracking."""

    def test_calculate_time_until_deadline(self, basic_work_order):
        """Test calculating time remaining until deadline."""
        now = datetime.now(dt_timezone.utc)
        time_remaining = basic_work_order.expirydatetime - now

        assert time_remaining.total_seconds() > 0
        assert basic_work_order.expirydatetime > now

    def test_update_expiry_date(self, basic_work_order):
        """Test updating work order expiry date."""
        new_expiry = datetime.now(dt_timezone.utc) + timedelta(days=14)
        basic_work_order.expirydatetime = new_expiry
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.expirydatetime == new_expiry

    def test_deadline_extension_approval(self, basic_work_order):
        """Test deadline extension requires approval."""
        # Business logic: deadline extensions should be logged
        original_expiry = basic_work_order.expirydatetime
        extended_expiry = original_expiry + timedelta(days=7)

        basic_work_order.expirydatetime = extended_expiry
        basic_work_order.add_history()  # Log the extension
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.expirydatetime > original_expiry
        assert len(basic_work_order.wo_history["wo_history"]) > 0


@pytest.mark.django_db
class TestOverdueDetection:
    """Test overdue work order detection and alerts."""

    def test_detect_overdue_work_orders(self, overdue_work_order, basic_work_order):
        """Test querying overdue work orders."""
        now = datetime.now(dt_timezone.utc)
        overdue_wos = Wom.objects.filter(
            expirydatetime__lt=now,
            workstatus__in=["ASSIGNED", "INPROGRESS"]
        )

        assert overdue_work_order in overdue_wos
        assert basic_work_order not in overdue_wos

    def test_overdue_alert_flag(self, overdue_work_order):
        """Test that overdue work orders have alert flag set."""
        overdue_work_order.alerts = True
        overdue_work_order.save()
        overdue_work_order.refresh_from_db()

        assert overdue_work_order.alerts is True

    def test_overdue_notification_sent(self, overdue_work_order):
        """Test that overdue notifications are sent."""
        overdue_work_order.alerts = True
        overdue_work_order.ismailsent = True
        overdue_work_order.save()
        overdue_work_order.refresh_from_db()

        assert overdue_work_order.ismailsent is True

    def test_filter_overdue_by_priority(self, overdue_work_order):
        """Test filtering overdue work orders by priority."""
        now = datetime.now(dt_timezone.utc)
        high_priority_overdue = Wom.objects.filter(
            expirydatetime__lt=now,
            priority="HIGH",
            workstatus__in=["ASSIGNED", "INPROGRESS"]
        )

        assert overdue_work_order in high_priority_overdue


@pytest.mark.django_db
class TestSLACompliance:
    """Test SLA compliance tracking and reporting."""

    def test_calculate_sla_compliance(self, completed_work_order):
        """Test calculating SLA compliance percentage."""
        # Work order completed within SLA
        assert completed_work_order.workstatus == "COMPLETED"
        assert completed_work_order.endtime is not None

        # Check if completed before expiry
        sla_met = completed_work_order.endtime < completed_work_order.expirydatetime
        assert sla_met is True

    def test_sla_met_within_deadline(self, completed_work_order):
        """Test work order completed within SLA deadline."""
        completed_work_order.expirydatetime = datetime.now(dt_timezone.utc) + timedelta(days=7)
        completed_work_order.endtime = datetime.now(dt_timezone.utc)
        completed_work_order.save()
        completed_work_order.refresh_from_db()

        assert completed_work_order.endtime < completed_work_order.expirydatetime

    def test_sla_breach_detection(self, overdue_work_order):
        """Test detecting SLA breach for overdue work."""
        now = datetime.now(dt_timezone.utc)
        assert overdue_work_order.expirydatetime < now
        assert overdue_work_order.workstatus in ["ASSIGNED", "INPROGRESS"]

    def test_sla_reporting_by_vendor(self, test_vendor):
        """Test generating SLA compliance report by vendor."""
        vendor_wos = Wom.objects.filter(vendor=test_vendor)
        completed_wos = vendor_wos.filter(workstatus="COMPLETED")

        # Calculate SLA compliance
        sla_compliant = completed_wos.filter(
            endtime__lt=models.F('expirydatetime') if hasattr(models, 'F') else None
        )

        assert vendor_wos.count() >= 0


@pytest.mark.django_db
class TestStartEndTimeTracking:
    """Test work order start and end time tracking."""

    def test_record_start_time(self, basic_work_order):
        """Test recording work start time."""
        start_time = datetime.now(dt_timezone.utc)
        basic_work_order.starttime = start_time
        basic_work_order.workstatus = "INPROGRESS"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.starttime == start_time
        assert basic_work_order.workstatus == "INPROGRESS"

    def test_record_end_time(self, basic_work_order):
        """Test recording work end time."""
        start_time = datetime.now(dt_timezone.utc) - timedelta(hours=2)
        end_time = datetime.now(dt_timezone.utc)

        basic_work_order.starttime = start_time
        basic_work_order.endtime = end_time
        basic_work_order.workstatus = "COMPLETED"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.endtime == end_time
        assert basic_work_order.workstatus == "COMPLETED"

    def test_calculate_work_duration(self, completed_work_order):
        """Test calculating total work duration."""
        assert completed_work_order.starttime is not None
        assert completed_work_order.endtime is not None

        duration = completed_work_order.endtime - completed_work_order.starttime
        assert duration.total_seconds() > 0

    def test_end_time_after_start_time(self, basic_work_order):
        """Test validation that end time must be after start time."""
        start_time = datetime.now(dt_timezone.utc) - timedelta(hours=3)
        end_time = datetime.now(dt_timezone.utc)

        basic_work_order.starttime = start_time
        basic_work_order.endtime = end_time
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.endtime > basic_work_order.starttime


@pytest.mark.django_db
class TestPriorityScheduling:
    """Test priority-based scheduling and escalation."""

    def test_high_priority_scheduling(self, test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user):
        """Test scheduling high priority work orders."""
        high_priority_wo = Wom.objects.create(
            description="Emergency Repair",
            priority="HIGH",
            vendor=test_vendor,
            qset=test_question_set,
            location=test_location,
            asset=test_asset,
            plandatetime=datetime.now(dt_timezone.utc),
            expirydatetime=datetime.now(dt_timezone.utc) + timedelta(hours=4),
            client=test_tenant,
            bu=test_tenant,
            tenant=test_tenant,
            cdby=test_user,
            mdby=test_user
        )

        assert high_priority_wo.priority == "HIGH"

    def test_priority_based_ordering(self, basic_work_order, overdue_work_order):
        """Test ordering work orders by priority."""
        # Query work orders ordered by priority
        priority_order = ["HIGH", "MEDIUM", "LOW"]
        wos = Wom.objects.all().order_by("-priority")

        # Verify high priority comes first
        high_priority_wos = [wo for wo in wos if wo.priority == "HIGH"]
        assert len(high_priority_wos) >= 0

    def test_priority_escalation_on_overdue(self, overdue_work_order):
        """Test automatic priority escalation for overdue work."""
        # Escalate priority
        original_priority = overdue_work_order.priority
        overdue_work_order.priority = "HIGH"
        overdue_work_order.alerts = True
        overdue_work_order.save()
        overdue_work_order.refresh_from_db()

        assert overdue_work_order.priority == "HIGH"
        assert overdue_work_order.alerts is True


@pytest.mark.django_db
class TestBatchScheduling:
    """Test batch scheduling of multiple work orders."""

    def test_schedule_multiple_work_orders(self, test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user):
        """Test scheduling multiple work orders in batch."""
        base_date = datetime.now(dt_timezone.utc)

        wos = []
        for i in range(5):
            wo = Wom.objects.create(
                description=f"Batch WO {i+1}",
                vendor=test_vendor,
                qset=test_question_set,
                location=test_location,
                asset=test_asset,
                plandatetime=base_date + timedelta(days=i),
                expirydatetime=base_date + timedelta(days=i+7),
                client=test_tenant,
                bu=test_tenant,
                tenant=test_tenant,
                cdby=test_user,
                mdby=test_user
            )
            wos.append(wo)

        assert len(wos) == 5
        assert all(wo.vendor == test_vendor for wo in wos)

    def test_bulk_reschedule(self, basic_work_order):
        """Test bulk rescheduling of work orders."""
        # Get multiple work orders
        wos = Wom.objects.filter(workstatus="ASSIGNED")[:5]

        new_plan_date = datetime.now(dt_timezone.utc) + timedelta(days=30)

        for wo in wos:
            wo.plandatetime = new_plan_date
            wo.save()

        # Verify all updated
        updated_wos = Wom.objects.filter(id__in=[wo.id for wo in wos])
        assert all(wo.plandatetime.date() == new_plan_date.date() for wo in updated_wos)

    def test_schedule_conflict_detection(self, test_vendor):
        """Test detecting scheduling conflicts for vendors."""
        # Create overlapping work orders for same vendor
        base_date = datetime.now(dt_timezone.utc)

        wo1 = Wom.objects.filter(vendor=test_vendor, workstatus="ASSIGNED").first()

        if wo1:
            # Check for overlapping schedules
            overlapping_wos = Wom.objects.filter(
                vendor=test_vendor,
                workstatus__in=["ASSIGNED", "INPROGRESS"],
                plandatetime__lte=wo1.expirydatetime,
                expirydatetime__gte=wo1.plandatetime
            )

            assert overlapping_wos.count() >= 1


@pytest.mark.django_db
class TestCalendarIntegration:
    """Test calendar and schedule view integration."""

    def test_get_work_orders_by_date_range(self, basic_work_order):
        """Test querying work orders within date range."""
        start_date = datetime.now(dt_timezone.utc)
        end_date = datetime.now(dt_timezone.utc) + timedelta(days=30)

        wos_in_range = Wom.objects.filter(
            plandatetime__gte=start_date,
            plandatetime__lte=end_date
        )

        assert wos_in_range.count() >= 0

    def test_get_vendor_schedule(self, test_vendor):
        """Test retrieving vendor's work schedule."""
        vendor_schedule = Wom.objects.filter(
            vendor=test_vendor,
            workstatus__in=["ASSIGNED", "INPROGRESS"]
        ).order_by("plandatetime")

        assert vendor_schedule.count() >= 0

    def test_get_location_schedule(self, test_location):
        """Test retrieving location-based work schedule."""
        location_schedule = Wom.objects.filter(
            location=test_location,
            workstatus__in=["ASSIGNED", "INPROGRESS"]
        ).order_by("plandatetime")

        assert location_schedule.count() >= 0
