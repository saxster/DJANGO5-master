"""Test suite for Approval Workflows functionality."""

import pytest
from django.contrib.auth import get_user_model
from apps.core.models import ApprovalRequest, ApprovalGroup
from apps.core.services.approval_service import ApprovalService
from apps.peoples.models import Pgroup

User = get_user_model()


@pytest.fixture
def approval_group(tenant):
    """Create an approval group."""
    pgroup = Pgroup.objects.create(
        tenant=tenant,
        name="Approvers",
        description="Approval team"
    )
    return ApprovalGroup.objects.create(
        tenant=tenant,
        name="Data Approvers",
        pgroup=pgroup,
        min_approvals=1
    )


@pytest.fixture
def approver(tenant, approval_group):
    """Create a user with approval permissions."""
    user = User.objects.create_user(
        username="approver",
        email="approver@test.com",
        tenant=tenant
    )
    approval_group.pgroup.people.add(user)
    return user


@pytest.fixture
def approval_request(tenant, user, approval_group):
    """Create a pending approval request."""
    return ApprovalRequest.objects.create(
        tenant=tenant,
        requester=user,
        action_type="Delete items",
        target_model="Ticket",
        target_ids=[1, 2, 3],
        reason="Cleanup old data",
        approval_group=approval_group,
        status='PENDING'
    )


@pytest.mark.django_db
class TestApprovals:
    """Test approval workflow functionality."""

    def test_create_approval_request(self, user, approval_group):
        """Test creating an approval request."""
        request = ApprovalService.create_approval_request(
            user=user,
            action_type="Delete items",
            target_model="Ticket",
            target_ids=[1, 2, 3],
            reason="Cleanup old data",
            approval_group=approval_group
        )
        
        assert request.status == 'PENDING'
        assert request.requester == user
        assert request.action_type == "Delete items"
        assert request.target_ids == [1, 2, 3]
        assert request.approval_group == approval_group

    def test_approve_request(self, approval_request, approver):
        """Test approving a request."""
        ApprovalService.approve_request(
            approval_request,
            approver,
            "Looks good"
        )
        
        approval_request.refresh_from_db()
        assert approval_request.status == 'APPROVED'
        assert approval_request.approved_by == approver
        assert 'Looks good' in approval_request.approval_comment

    def test_deny_request(self, approval_request, approver):
        """Test denying a request."""
        ApprovalService.deny_request(
            approval_request,
            approver,
            "Not safe"
        )
        
        approval_request.refresh_from_db()
        assert approval_request.status == 'DENIED'
        assert 'Not safe' in approval_request.denial_reason
        assert approval_request.reviewed_by == approver

    def test_unauthorized_approval(self, approval_request, user):
        """Test that unauthorized users cannot approve."""
        with pytest.raises(PermissionError):
            ApprovalService.approve_request(
                approval_request,
                user,  # Not an approver
                "Trying to approve"
            )

    def test_multi_approval_requirement(self, tenant, user):
        """Test multi-approval requirements."""
        pgroup = Pgroup.objects.create(tenant=tenant, name="Senior Approvers")
        approval_group = ApprovalGroup.objects.create(
            tenant=tenant,
            name="High Risk Approvers",
            pgroup=pgroup,
            min_approvals=2  # Requires 2 approvals
        )
        
        # Create approvers
        approver1 = User.objects.create_user(
            username="approver1",
            email="ap1@test.com",
            tenant=tenant
        )
        approver2 = User.objects.create_user(
            username="approver2",
            email="ap2@test.com",
            tenant=tenant
        )
        pgroup.people.add(approver1, approver2)
        
        # Create request
        request = ApprovalService.create_approval_request(
            user=user,
            action_type="Delete critical data",
            target_model="Ticket",
            target_ids=[1, 2, 3],
            reason="Major cleanup",
            approval_group=approval_group
        )
        
        # First approval
        ApprovalService.approve_request(request, approver1, "Approved by first")
        request.refresh_from_db()
        assert request.status == 'PENDING'  # Still pending
        assert request.approval_count == 1
        
        # Second approval
        ApprovalService.approve_request(request, approver2, "Approved by second")
        request.refresh_from_db()
        assert request.status == 'APPROVED'  # Now approved
        assert request.approval_count == 2

    def test_request_expiration(self, approval_request):
        """Test approval request expiration."""
        from datetime import timedelta
        from django.utils import timezone
        
        # Set expiration in the past
        approval_request.expires_at = timezone.now() - timedelta(days=1)
        approval_request.save()
        
        # Check if expired
        assert ApprovalService.is_expired(approval_request) is True
        
        # Try to approve expired request
        with pytest.raises(ValueError):
            ApprovalService.approve_request(
                approval_request,
                approval_request.requester,
                "Late approval"
            )

    def test_request_cancellation(self, approval_request, user):
        """Test requester can cancel their own request."""
        ApprovalService.cancel_request(approval_request, user)
        
        approval_request.refresh_from_db()
        assert approval_request.status == 'CANCELLED'

    def test_approval_notifications(self, approval_request, mailoutbox):
        """Test notifications are sent to approvers."""
        ApprovalService.notify_approvers(approval_request)
        
        assert len(mailoutbox) > 0
        assert 'approval' in mailoutbox[0].subject.lower()

    def test_action_execution(self, approval_request, approver):
        """Test that approved actions are executed."""
        # Approve the request
        ApprovalService.approve_request(approval_request, approver, "Approved")
        
        # Execute the action
        result = ApprovalService.execute_approved_action(approval_request)
        
        assert result['success'] is True
        approval_request.refresh_from_db()
        assert approval_request.executed is True

    def test_audit_trail(self, approval_request, approver):
        """Test complete audit trail is maintained."""
        # Approve
        ApprovalService.approve_request(approval_request, approver, "Looks good")
        
        # Check audit fields
        approval_request.refresh_from_db()
        assert approval_request.approved_at is not None
        assert approval_request.approved_by == approver
        assert approval_request.approval_comment is not None
        
        # Verify history is tracked
        from apps.core.models import ApprovalHistory
        history = ApprovalHistory.objects.filter(approval_request=approval_request)
        assert history.count() > 0
