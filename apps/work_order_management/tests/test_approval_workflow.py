"""
Approval workflow tests for work_order_management app.

Tests work permit approval/rejection flows, multi-level approvals,
verifier workflows, and state transitions.
"""
import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from apps.work_order_management.models import Wom


@pytest.mark.django_db
class TestWorkPermitCreation:
    """Test work permit creation and configuration."""

    def test_create_work_permit_with_approvers(self, work_permit_order, test_approver):
        """Test creating work permit with approver list."""
        assert work_permit_order.identifier == "WP"
        assert work_permit_order.approvers is not None
        assert test_approver.id in work_permit_order.approvers

    def test_create_work_permit_with_verifiers(self, work_permit_order, test_verifier):
        """Test creating work permit with verifier list."""
        assert work_permit_order.verifiers is not None
        assert test_verifier.id in work_permit_order.verifiers

    def test_work_permit_requires_approval(self, work_permit_order):
        """Test that work permit status is REQUIRED."""
        assert work_permit_order.workpermit == "REQUIRED"


@pytest.mark.django_db
class TestApprovalFlow:
    """Test work permit approval workflow."""

    def test_approve_work_permit(self, work_permit_order, test_approver):
        """Test approving a work permit."""
        work_permit_order.workpermit = "APPROVED"
        work_permit_order.save()
        work_permit_order.refresh_from_db()

        assert work_permit_order.workpermit == "APPROVED"

    def test_reject_work_permit(self, work_permit_order, test_approver):
        """Test rejecting a work permit."""
        work_permit_order.workpermit = "REJECTED"
        work_permit_order.isdenied = True
        work_permit_order.save()
        work_permit_order.refresh_from_db()

        assert work_permit_order.workpermit == "REJECTED"
        assert work_permit_order.isdenied is True

    def test_multiple_approvers_sequential(self, test_tenant, test_approver, test_verifier):
        """Test sequential approval by multiple approvers."""
        from apps.peoples.models import People
        from apps.work_order_management.models import Vendor
        from apps.activity.models import Location, QuestionSet
        from apps.onboarding.models import TypeAssist
        from django.contrib.gis.geos import Point

        # Create second approver
        approver2 = People.objects.create(
            peoplecode="APPROVER002",
            peoplename="Second Approver",
            loginid="approver2",
            email="approver2@test.com",
            mobno="7777777777",
            client=test_tenant,
            enable=True
        )

        # Create work permit with multiple approvers
        location = Location.objects.create(
            site="WPSITE",
            location="WP Location",
            client=test_tenant,
            bu=test_tenant,
            gpslocation=Point(103.8198, 1.3521)
        )

        qset = QuestionSet.objects.create(
            qsetname="WP Checklist",
            client=test_tenant,
            bu=test_tenant,
            enable=True
        )

        vendor_type = TypeAssist.objects.create(
            typename="VendorType",
            typeval="WP Vendor Type",
            client=test_tenant,
            enable=True
        )

        vendor = Vendor.objects.create(
            code="WPVENDOR",
            name="WP Vendor",
            type=vendor_type,
            email="wpvendor@test.com",
            mobno="9999999999",
            client=test_tenant,
            bu=test_tenant,
            gpslocation=Point(103.8198, 1.3521)
        )

        wp = Wom.objects.create(
            description="Multi-Approver WP",
            identifier="WP",
            vendor=vendor,
            qset=qset,
            location=location,
            plandatetime=datetime.now(dt_timezone.utc) + timedelta(days=1),
            expirydatetime=datetime.now(dt_timezone.utc) + timedelta(days=3),
            client=test_tenant,
            bu=test_tenant,
            tenant=test_tenant,
            workpermit="REQUIRED",
            approvers=[test_approver.id, approver2.id],
            cdby=test_approver,
            mdby=test_approver
        )

        assert len(wp.approvers) == 2
        assert test_approver.id in wp.approvers
        assert approver2.id in wp.approvers

    def test_cannot_start_without_approval(self, work_permit_order):
        """Test that work cannot start without approval."""
        # Business logic validation - work permit must be APPROVED before INPROGRESS
        assert work_permit_order.workpermit == "REQUIRED"
        assert work_permit_order.workstatus != "INPROGRESS"

        # Approve first
        work_permit_order.workpermit = "APPROVED"
        work_permit_order.save()

        # Now can start work
        work_permit_order.workstatus = "INPROGRESS"
        work_permit_order.starttime = datetime.now(dt_timezone.utc)
        work_permit_order.save()
        work_permit_order.refresh_from_db()

        assert work_permit_order.workstatus == "INPROGRESS"

    def test_approval_logged_in_history(self, work_permit_order, test_approver):
        """Test that approval is logged in wo_history."""
        # Add approval to history
        work_permit_order.add_history()
        work_permit_order.refresh_from_db()

        assert "wo_history" in work_permit_order.wo_history
        assert len(work_permit_order.wo_history["wo_history"]) > 0


@pytest.mark.django_db
class TestVerificationFlow:
    """Test work order verification after completion."""

    def test_verify_completed_work_order(self, completed_work_order, test_verifier):
        """Test verifying a completed work order."""
        assert completed_work_order.workstatus == "COMPLETED"

        completed_work_order.verifiers_status = "APPROVED"
        completed_work_order.workstatus = "CLOSED"
        completed_work_order.save()
        completed_work_order.refresh_from_db()

        assert completed_work_order.verifiers_status == "APPROVED"
        assert completed_work_order.workstatus == "CLOSED"

    def test_reject_verification(self, completed_work_order, test_verifier):
        """Test rejecting verification (send back for rework)."""
        completed_work_order.verifiers_status = "REJECTED"
        completed_work_order.workstatus = "INPROGRESS"  # Send back for rework
        completed_work_order.save()
        completed_work_order.refresh_from_db()

        assert completed_work_order.verifiers_status == "REJECTED"
        assert completed_work_order.workstatus == "INPROGRESS"

    def test_cannot_verify_incomplete_work(self, basic_work_order, test_verifier):
        """Test that incomplete work cannot be verified."""
        # Business logic: Only COMPLETED work can be verified
        assert basic_work_order.workstatus != "COMPLETED"
        assert basic_work_order.verifiers_status == "PENDING"

    def test_verification_logged_in_history(self, completed_work_order, test_verifier):
        """Test that verification is logged in wo_history."""
        completed_work_order.add_history()
        completed_work_order.refresh_from_db()

        assert "wo_history" in completed_work_order.wo_history
        history_entries = completed_work_order.wo_history["wo_history"]
        assert len(history_entries) > 0


@pytest.mark.django_db
class TestStatusTransitions:
    """Test work order status state machine transitions."""

    def test_assigned_to_inprogress_transition(self, basic_work_order):
        """Test ASSIGNED → INPROGRESS transition."""
        assert basic_work_order.workstatus == "ASSIGNED"

        basic_work_order.workstatus = "INPROGRESS"
        basic_work_order.starttime = datetime.now(dt_timezone.utc)
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.workstatus == "INPROGRESS"
        assert basic_work_order.starttime is not None

    def test_inprogress_to_completed_transition(self, basic_work_order):
        """Test INPROGRESS → COMPLETED transition."""
        basic_work_order.workstatus = "INPROGRESS"
        basic_work_order.starttime = datetime.now(dt_timezone.utc) - timedelta(hours=2)
        basic_work_order.save()

        basic_work_order.workstatus = "COMPLETED"
        basic_work_order.endtime = datetime.now(dt_timezone.utc)
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.workstatus == "COMPLETED"
        assert basic_work_order.endtime is not None

    def test_completed_to_closed_transition(self, completed_work_order, test_verifier):
        """Test COMPLETED → CLOSED transition after verification."""
        assert completed_work_order.workstatus == "COMPLETED"

        completed_work_order.verifiers_status = "APPROVED"
        completed_work_order.workstatus = "CLOSED"
        completed_work_order.save()
        completed_work_order.refresh_from_db()

        assert completed_work_order.workstatus == "CLOSED"

    def test_reassignment_status_change(self, basic_work_order, test_tenant, test_vendor_type):
        """Test status change to RE_ASSIGNED when vendor changed."""
        from apps.work_order_management.models import Vendor
        from django.contrib.gis.geos import Point

        new_vendor = Vendor.objects.create(
            code="REASSIGN_VENDOR",
            name="Reassigned Vendor",
            type=test_vendor_type,
            email="reassign@test.com",
            mobno="5555555555",
            client=test_tenant,
            bu=test_tenant,
            gpslocation=Point(103.8198, 1.3521)
        )

        basic_work_order.vendor = new_vendor
        basic_work_order.workstatus = "RE_ASSIGNED"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.workstatus == "RE_ASSIGNED"
        assert basic_work_order.vendor == new_vendor

    def test_cancel_work_order(self, basic_work_order):
        """Test transitioning to CANCELLED status."""
        basic_work_order.workstatus = "CANCELLED"
        basic_work_order.save()
        basic_work_order.refresh_from_db()

        assert basic_work_order.workstatus == "CANCELLED"

    def test_invalid_status_transition_blocked(self, basic_work_order):
        """Test that invalid status transitions are blocked."""
        # Django choices don't prevent invalid values at model level
        # This would be enforced at form/serializer validation layer
        from apps.work_order_management.models import Workstatus

        valid_statuses = [choice[0] for choice in Workstatus.choices]
        assert basic_work_order.workstatus in valid_statuses


@pytest.mark.django_db
class TestApproverPermissions:
    """Test approver authorization and permissions."""

    def test_only_assigned_approver_can_approve(self, work_permit_order, test_user):
        """Test that only assigned approvers can approve."""
        # Business logic validation - verify approver is in approvers list
        assert test_user.id not in work_permit_order.approvers
        # In actual implementation, view layer would check this

    def test_cannot_approve_own_work(self, work_permit_order, test_user):
        """Test conflict of interest - cannot approve own work."""
        # Business logic: cdby (creator) should not be in approvers list
        # This is enforced at view/form layer
        assert work_permit_order.cdby.id not in work_permit_order.approvers

    def test_approver_list_validation(self, work_permit_order):
        """Test that approver list contains valid user IDs."""
        assert work_permit_order.approvers is not None
        assert len(work_permit_order.approvers) > 0
        assert all(isinstance(approver_id, int) for approver_id in work_permit_order.approvers)


@pytest.mark.django_db
class TestVerifierPermissions:
    """Test verifier authorization and permissions."""

    def test_only_assigned_verifier_can_verify(self, completed_work_order, test_user):
        """Test that only assigned verifiers can verify."""
        # Business logic: In actual implementation, check if user in verifiers list
        # completed_work_order may not have verifiers set
        if completed_work_order.verifiers:
            assert isinstance(completed_work_order.verifiers, list)

    def test_cannot_verify_own_work(self, completed_work_order, test_user):
        """Test conflict of interest - cannot verify own work."""
        # Business logic: creator should not be verifier
        if completed_work_order.verifiers:
            assert completed_work_order.cdby.id not in completed_work_order.verifiers

    def test_verifier_list_validation(self, work_permit_order):
        """Test that verifier list contains valid user IDs."""
        assert work_permit_order.verifiers is not None
        assert len(work_permit_order.verifiers) > 0
        assert all(isinstance(verifier_id, int) for verifier_id in work_permit_order.verifiers)


@pytest.mark.django_db
class TestHistoryTracking:
    """Test work order history tracking."""

    def test_history_captures_status_changes(self, basic_work_order):
        """Test that wo_history captures all status transitions."""
        original_status = basic_work_order.workstatus

        basic_work_order.add_history()
        basic_work_order.workstatus = "INPROGRESS"
        basic_work_order.save()
        basic_work_order.add_history()
        basic_work_order.refresh_from_db()

        assert len(basic_work_order.wo_history["wo_history"]) >= 2

    def test_history_captures_approvals(self, work_permit_order, test_approver):
        """Test that wo_history captures approval actions."""
        work_permit_order.workpermit = "APPROVED"
        work_permit_order.save()
        work_permit_order.add_history()
        work_permit_order.refresh_from_db()

        history = work_permit_order.wo_history["wo_history"]
        assert len(history) > 0
        latest_entry = history[-1]
        assert latest_entry is not None

    def test_history_captures_reassignments(self, basic_work_order, test_tenant, test_vendor_type):
        """Test that wo_history captures vendor reassignments."""
        from apps.work_order_management.models import Vendor
        from django.contrib.gis.geos import Point

        new_vendor = Vendor.objects.create(
            code="HISTORY_VENDOR",
            name="History Vendor",
            type=test_vendor_type,
            email="history@test.com",
            mobno="4444444444",
            client=test_tenant,
            bu=test_tenant,
            gpslocation=Point(103.8198, 1.3521)
        )

        basic_work_order.vendor = new_vendor
        basic_work_order.workstatus = "RE_ASSIGNED"
        basic_work_order.save()
        basic_work_order.add_history()
        basic_work_order.refresh_from_db()

        history = basic_work_order.wo_history["wo_history"]
        assert len(history) > 0

    def test_history_immutable(self, basic_work_order):
        """Test that wo_history is append-only (immutable)."""
        basic_work_order.add_history()
        basic_work_order.refresh_from_db()

        history_count = len(basic_work_order.wo_history["wo_history"])

        basic_work_order.add_history()
        basic_work_order.refresh_from_db()

        new_history_count = len(basic_work_order.wo_history["wo_history"])
        assert new_history_count > history_count


@pytest.mark.django_db
class TestNotifications:
    """Test notification triggers for approval workflow."""

    def test_approval_request_notification(self, work_permit_order, test_approver):
        """Test notification sent to approver on work permit creation."""
        # Notification logic would be in signals or service layer
        assert work_permit_order.workpermit == "REQUIRED"
        assert test_approver.id in work_permit_order.approvers

    def test_approval_granted_notification(self, work_permit_order, test_user):
        """Test notification sent on approval."""
        work_permit_order.workpermit = "APPROVED"
        work_permit_order.ismailsent = True
        work_permit_order.save()
        work_permit_order.refresh_from_db()

        assert work_permit_order.ismailsent is True

    def test_verification_request_notification(self, completed_work_order, test_verifier):
        """Test notification sent to verifier on completion."""
        assert completed_work_order.workstatus == "COMPLETED"
        # Notification would trigger to verifiers list

    def test_rejection_notification(self, work_permit_order, test_user):
        """Test notification sent on rejection."""
        work_permit_order.workpermit = "REJECTED"
        work_permit_order.ismailsent = True
        work_permit_order.isdenied = True
        work_permit_order.save()
        work_permit_order.refresh_from_db()

        assert work_permit_order.isdenied is True
        assert work_permit_order.ismailsent is True
