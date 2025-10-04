"""
Unit tests for AI Changeset Models.

Tests AI changeset functionality including:
- Risk score calculation
- Two-person approval requirements
- Rollback capability
- Approval workflows

Following .claude/rules.md Rule #9: Specific exception handling
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.onboarding.models import (
    AIChangeSet,
    AIChangeRecord,
    ChangeSetApproval,
    ConversationSession,
    Bt
)

User = get_user_model()


@pytest.mark.django_db
class AIChangeSetModelTests(TestCase):
    """Test suite for AIChangeSet model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Bt.objects.create(
            buname='Test Client',
            bucode='TEST001',
            enable=True
        )
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.client,
            language='en',
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP
        )

    def test_changeset_creation(self):
        """Test basic changeset creation."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Test changeset",
            total_changes=5
        )

        self.assertIsNotNone(changeset.changeset_id)
        self.assertEqual(changeset.status, AIChangeSet.StatusChoices.PENDING)
        self.assertEqual(changeset.total_changes, 5)

    def test_risk_score_calculation_low(self):
        """Test risk score calculation for low-risk changeset."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Low risk changeset",
            total_changes=3
        )

        risk_score = changeset.calculate_risk_score()
        self.assertLessEqual(risk_score, 0.3)

    def test_risk_score_calculation_high(self):
        """Test risk score calculation for high-risk changeset."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="High risk changeset",
            total_changes=25
        )

        AIChangeRecord.objects.create(
            changeset=changeset,
            sequence_order=1,
            model_name='Bt',
            app_label='onboarding',
            object_id='1',
            action=AIChangeRecord.ActionChoices.DELETE
        )

        risk_score = changeset.calculate_risk_score()
        self.assertGreaterEqual(risk_score, 0.5)

    def test_two_person_approval_required_high_risk(self):
        """Test that high-risk changesets require two-person approval."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="High risk changeset",
            total_changes=15
        )

        self.assertTrue(changeset.requires_two_person_approval())

    def test_two_person_approval_not_required_low_risk(self):
        """Test that low-risk changesets don't require two-person approval."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Low risk changeset",
            total_changes=3
        )

        self.assertFalse(changeset.requires_two_person_approval())

    def test_can_be_applied_single_approval(self):
        """Test that low-risk changeset can be applied with single approval."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Low risk changeset",
            total_changes=3
        )

        self.assertTrue(changeset.can_be_applied())

    def test_can_be_applied_requires_two_approvals(self):
        """Test that high-risk changeset requires two approvals."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="High risk changeset",
            total_changes=15
        )

        changeset.create_approval_request(
            approver=self.user,
            approval_level='primary',
            request_meta={}
        )

        self.assertFalse(changeset.can_be_applied())

        secondary_user = User.objects.create_user(
            loginid='secondary_approver',
            email='secondary@example.com',
            password='testpass123',
            isadmin=True
        )

        secondary_approval = changeset.create_approval_request(
            approver=secondary_user,
            approval_level='secondary',
            request_meta={}
        )

        changeset.approvals.filter(approval_level='primary').update(
            status=ChangeSetApproval.StatusChoices.APPROVED
        )

        self.assertFalse(changeset.can_be_applied())

        secondary_approval.approve()

        self.assertTrue(changeset.can_be_applied())

    def test_can_rollback_applied_changeset(self):
        """Test that applied changeset can be rolled back."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Applied changeset",
            status=AIChangeSet.StatusChoices.APPLIED,
            applied_at=timezone.now()
        )

        self.assertTrue(changeset.can_rollback())

    def test_cannot_rollback_pending_changeset(self):
        """Test that pending changeset cannot be rolled back."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Pending changeset",
            status=AIChangeSet.StatusChoices.PENDING
        )

        self.assertFalse(changeset.can_rollback())

    def test_cannot_rollback_already_rolled_back(self):
        """Test that already rolled back changeset cannot be rolled back again."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Rolled back changeset",
            status=AIChangeSet.StatusChoices.ROLLED_BACK,
            applied_at=timezone.now(),
            rolled_back_at=timezone.now()
        )

        self.assertFalse(changeset.can_rollback())

    def test_rollback_complexity_low(self):
        """Test rollback complexity calculation for simple changeset."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Simple changeset",
            total_changes=3,
            successful_changes=3,
            failed_changes=0
        )

        complexity = changeset.get_rollback_complexity()
        self.assertEqual(complexity, "low")

    def test_rollback_complexity_high_with_failures(self):
        """Test rollback complexity for changeset with failures."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Failed changeset",
            total_changes=5,
            successful_changes=3,
            failed_changes=2
        )

        complexity = changeset.get_rollback_complexity()
        self.assertEqual(complexity, "high")


@pytest.mark.django_db
class AIChangeRecordModelTests(TestCase):
    """Test suite for AIChangeRecord model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Bt.objects.create(
            buname='Test Client',
            bucode='TEST001',
            enable=True
        )
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.client,
            language='en'
        )
        self.changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Test changeset"
        )

    def test_change_record_creation(self):
        """Test basic change record creation."""
        record = AIChangeRecord.objects.create(
            changeset=self.changeset,
            sequence_order=1,
            model_name='Bt',
            app_label='onboarding',
            object_id='1',
            action=AIChangeRecord.ActionChoices.CREATE,
            after_state={'buname': 'New BU'},
            status=AIChangeRecord.StatusChoices.SUCCESS
        )

        self.assertIsNotNone(record.record_id)
        self.assertEqual(record.action, AIChangeRecord.ActionChoices.CREATE)
        self.assertEqual(record.status, AIChangeRecord.StatusChoices.SUCCESS)

    def test_change_record_unique_sequence(self):
        """Test that sequence_order is unique within changeset."""
        AIChangeRecord.objects.create(
            changeset=self.changeset,
            sequence_order=1,
            model_name='Bt',
            app_label='onboarding',
            object_id='1',
            action=AIChangeRecord.ActionChoices.CREATE
        )

        with self.assertRaises(Exception):
            AIChangeRecord.objects.create(
                changeset=self.changeset,
                sequence_order=1,
                model_name='Bt',
                app_label='onboarding',
                object_id='2',
                action=AIChangeRecord.ActionChoices.CREATE
            )


@pytest.mark.django_db
class ChangeSetApprovalModelTests(TestCase):
    """Test suite for ChangeSetApproval model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Bt.objects.create(
            buname='Test Client',
            bucode='TEST001',
            enable=True
        )
        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.client,
            language='en'
        )
        self.changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Test changeset"
        )

    def test_approval_creation(self):
        """Test basic approval creation."""
        approval = ChangeSetApproval.objects.create(
            changeset=self.changeset,
            approver=self.user,
            approval_level='primary'
        )

        self.assertIsNotNone(approval.approval_id)
        self.assertEqual(approval.status, ChangeSetApproval.StatusChoices.PENDING)
        self.assertTrue(approval.is_pending())

    def test_approve_approval(self):
        """Test approving a pending approval."""
        approval = ChangeSetApproval.objects.create(
            changeset=self.changeset,
            approver=self.user,
            approval_level='primary'
        )

        approval.approve(reason="All looks good")

        self.assertEqual(approval.status, ChangeSetApproval.StatusChoices.APPROVED)
        self.assertIsNotNone(approval.decision_at)
        self.assertEqual(approval.reason, "All looks good")
        self.assertFalse(approval.is_pending())

    def test_reject_approval(self):
        """Test rejecting a pending approval."""
        approval = ChangeSetApproval.objects.create(
            changeset=self.changeset,
            approver=self.user,
            approval_level='primary'
        )

        approval.reject(reason="Too risky")

        self.assertEqual(approval.status, ChangeSetApproval.StatusChoices.REJECTED)
        self.assertIsNotNone(approval.decision_at)
        self.assertEqual(approval.reason, "Too risky")

    def test_escalate_approval(self):
        """Test escalating an approval."""
        approval = ChangeSetApproval.objects.create(
            changeset=self.changeset,
            approver=self.user,
            approval_level='secondary'
        )

        approval.escalate(reason="Needs senior review")

        self.assertEqual(approval.status, ChangeSetApproval.StatusChoices.ESCALATED)
        self.assertIsNotNone(approval.decision_at)
        self.assertEqual(approval.reason, "Needs senior review")

    def test_cannot_approve_already_decided(self):
        """Test that already approved approval cannot be approved again."""
        approval = ChangeSetApproval.objects.create(
            changeset=self.changeset,
            approver=self.user,
            approval_level='primary'
        )

        approval.approve(reason="First approval")

        with self.assertRaises(ValidationError):
            approval.approve(reason="Second approval")

    def test_cannot_reject_already_approved(self):
        """Test that already approved approval cannot be rejected."""
        approval = ChangeSetApproval.objects.create(
            changeset=self.changeset,
            approver=self.user,
            approval_level='primary'
        )

        approval.approve(reason="Approved")

        with self.assertRaises(ValidationError):
            approval.reject(reason="Rejected")