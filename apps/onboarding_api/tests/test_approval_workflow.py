"""
Integration tests for AI Approval Workflow.

Tests complete approval workflow including:
- Dry-run approval
- Two-person approval workflow
- Secondary approval decisions
- Tenant boundary enforcement
- Audit trail generation

Following .claude/rules.md security and testing requirements.
"""

import pytest
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import (
    AIChangeSet,
    ChangeSetApproval,
    ConversationSession,
    LLMRecommendation
)

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class ApprovalWorkflowIntegrationTests(TestCase):
    """Integration tests for complete approval workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            password='testpass123',
            isadmin=True
        )

        self.secondary_approver = User.objects.create_user(
            loginid='secondary_approver',
            email='secondary@example.com',
            password='testpass123',
            isadmin=True
        )

        self.bu = Bt.objects.create(
            buname='Test Business Unit',
            bucode='TEST001',
            enable=True
        )

        self.user.client = self.bu
        self.user.save()

        self.secondary_approver.client = self.bu
        self.secondary_approver.save()

        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.bu,
            language='en',
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP
        )

        self.recommendation = LLMRecommendation.objects.create(
            session=self.session,
            maker_output={'recommendation': 'test'},
            confidence_score=0.9
        )

    def test_dry_run_approval_succeeds(self):
        """Test that dry-run approval works without applying changes."""
        self.client.force_authenticate(user=self.user)

        url = reverse('onboarding_api:recommendations-approve')
        data = {
            'session_id': str(self.session.session_id),
            'approved_items': [str(self.recommendation.recommendation_id)],
            'rejected_items': [],
            'reasons': {},
            'modifications': {},
            'dry_run': True
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('system_configuration', response.data)
        self.assertIn('implementation_plan', response.data)

    def test_low_risk_approval_single_approval(self):
        """Test that low-risk changes proceed with single approval."""
        self.client.force_authenticate(user=self.user)

        url = reverse('onboarding_api:recommendations-approve')
        data = {
            'session_id': str(self.session.session_id),
            'approved_items': [str(self.recommendation.recommendation_id)],
            'rejected_items': [],
            'reasons': {},
            'modifications': {},
            'dry_run': False
        }

        response = self.client.post(url, data, format='json')

        self.assertIn(response.status_code, [200, 201])

    def test_high_risk_requires_two_person_approval(self):
        """Test that high-risk changes require two-person approval."""
        self.client.force_authenticate(user=self.user)

        approved_items = []
        for i in range(15):
            rec = LLMRecommendation.objects.create(
                session=self.session,
                maker_output={'recommendation': f'test_{i}'},
                confidence_score=0.9
            )
            approved_items.append(str(rec.recommendation_id))

        url = reverse('onboarding_api:recommendations-approve')
        data = {
            'session_id': str(self.session.session_id),
            'approved_items': approved_items,
            'rejected_items': [],
            'reasons': {},
            'modifications': {},
            'dry_run': False
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get('two_person_approval_required'))
        self.assertIn('changeset_id', response.data)
        self.assertIn('risk_score', response.data)

    def test_secondary_approval_flow(self):
        """Test complete secondary approval workflow."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="High risk test changeset",
            total_changes=15
        )

        primary_approval = changeset.create_approval_request(
            approver=self.user,
            approval_level='primary',
            request_meta={'ip_address': '127.0.0.1'}
        )
        primary_approval.approve(reason="Primary approval granted")

        secondary_approval = changeset.create_approval_request(
            approver=self.secondary_approver,
            approval_level='secondary',
            request_meta={'ip_address': '127.0.0.1'}
        )

        self.client.force_authenticate(user=self.secondary_approver)

        url = reverse('onboarding_api:secondary-approval-decide', kwargs={
            'approval_id': secondary_approval.approval_id
        })
        data = {
            'decision': 'approve',
            'reason': 'Secondary approval granted'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['decision'], 'approved')

    def test_secondary_approval_rejection_blocks_changeset(self):
        """Test that secondary approval rejection blocks changeset."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="High risk test changeset",
            total_changes=15
        )

        primary_approval = changeset.create_approval_request(
            approver=self.user,
            approval_level='primary',
            request_meta={}
        )
        primary_approval.approve()

        secondary_approval = changeset.create_approval_request(
            approver=self.secondary_approver,
            approval_level='secondary',
            request_meta={}
        )

        self.client.force_authenticate(user=self.secondary_approver)

        url = reverse('onboarding_api:secondary-approval-decide', kwargs={
            'approval_id': secondary_approval.approval_id
        })
        data = {
            'decision': 'reject',
            'reason': 'Too risky'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['decision'], 'rejected')

        changeset.refresh_from_db()
        self.assertFalse(changeset.can_be_applied())


@pytest.mark.security
@pytest.mark.django_db
class ApprovalSecurityTests(TestCase):
    """Security tests for approval workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.bu1 = Bt.objects.create(
            buname='Client 1',
            bucode='CLIENT1',
            enable=True
        )
        self.bu2 = Bt.objects.create(
            buname='Client 2',
            bucode='CLIENT2',
            enable=True
        )

        self.user1 = User.objects.create_user(
            loginid='user1',
            email='user1@client1.com',
            password='testpass123',
            isadmin=True,
            client=self.bu1
        )

        self.user2 = User.objects.create_user(
            loginid='user2',
            email='user2@client2.com',
            password='testpass123',
            isadmin=True,
            client=self.bu2
        )

        self.session1 = ConversationSession.objects.create(
            user=self.user1,
            client=self.bu1,
            language='en'
        )

    def test_tenant_boundary_enforcement_approval(self):
        """Test that users cannot approve changesets from other tenants."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session1,
            approved_by=self.user1,
            description="Client 1 changeset"
        )

        approval = changeset.create_approval_request(
            approver=self.user2,
            approval_level='secondary',
            request_meta={}
        )

        self.client.force_authenticate(user=self.user2)

        url = reverse('onboarding_api:secondary-approval-decide', kwargs={
            'approval_id': approval.approval_id
        })
        data = {
            'decision': 'approve',
            'reason': 'Trying to approve'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 403)
        self.assertIn('tenant_boundary_violation', response.data.get('error', '').lower() or str(response.data))

    def test_unauthorized_approver_cannot_decide(self):
        """Test that non-assigned approvers cannot make approval decisions."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session1,
            approved_by=self.user1,
            description="Test changeset"
        )

        approval = changeset.create_approval_request(
            approver=self.user1,
            approval_level='primary',
            request_meta={}
        )

        unauthorized_user = User.objects.create_user(
            loginid='unauthorized',
            email='unauthorized@client1.com',
            password='testpass123',
            client=self.bu1
        )

        self.client.force_authenticate(user=unauthorized_user)

        url = reverse('onboarding_api:secondary-approval-decide', kwargs={
            'approval_id': approval.approval_id
        })
        data = {
            'decision': 'approve',
            'reason': 'Unauthorized approval'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 403)


@pytest.mark.integration
@pytest.mark.django_db
class RollbackWorkflowTests(TestCase):
    """Tests for changeset rollback functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            password='testpass123',
            isadmin=True
        )

        self.bu = Bt.objects.create(
            buname='Test BU',
            bucode='TEST001',
            enable=True
        )

        self.user.client = self.bu
        self.user.save()

        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.bu,
            language='en'
        )

    def test_can_rollback_applied_changeset(self):
        """Test rollback of successfully applied changeset."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Applied changeset",
            status=AIChangeSet.StatusChoices.APPLIED,
            total_changes=5,
            successful_changes=5
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('onboarding_api:changesets-rollback', kwargs={
            'changeset_id': changeset.changeset_id
        })
        data = {
            'reason': 'Testing rollback'
        }

        response = self.client.post(url, data, format='json')

        self.assertIn(response.status_code, [200, 202])

    def test_cannot_rollback_pending_changeset(self):
        """Test that pending changeset cannot be rolled back."""
        changeset = AIChangeSet.objects.create(
            conversation_session=self.session,
            approved_by=self.user,
            description="Pending changeset",
            status=AIChangeSet.StatusChoices.PENDING
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('onboarding_api:changesets-rollback', kwargs={
            'changeset_id': changeset.changeset_id
        })
        data = {
            'reason': 'Attempting rollback'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 400)