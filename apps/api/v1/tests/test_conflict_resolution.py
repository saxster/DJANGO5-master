"""
Comprehensive Tests for Conflict Auto-Resolution Engine

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.api.v1.services.conflict_resolution_service import ConflictResolutionService
from apps.core.models.sync_conflict_policy import TenantConflictPolicy, ConflictResolutionLog
from apps.tenants.models import Tenant
from apps.peoples.models import People


@pytest.mark.unit
class TestConflictResolutionService(TestCase):
    """Test conflict resolution strategies."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = ConflictResolutionService()
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        self.server_entry = {
            'mobile_id': 'uuid-123',
            'version': 3,
            'status': 'in_progress',
            'updated_at': '2025-09-28T10:00:00Z'
        }

        self.client_entry = {
            'mobile_id': 'uuid-123',
            'version': 2,
            'status': 'completed',
            'updated_at': '2025-09-28T09:00:00Z'
        }

    def test_client_wins_policy(self):
        """Test client_wins resolution strategy."""
        result = self.service.resolve_conflict(
            domain='journal',
            server_entry=self.server_entry,
            client_entry=self.client_entry
        )

        self.assertEqual(result['resolution'], 'resolved')
        self.assertEqual(result['strategy_used'], 'client_wins')
        self.assertEqual(result['winning_entry'], self.client_entry)

    def test_server_wins_policy(self):
        """Test server_wins resolution strategy."""
        result = self.service.resolve_conflict(
            domain='attendance',
            server_entry=self.server_entry,
            client_entry=self.client_entry
        )

        self.assertEqual(result['resolution'], 'resolved')
        self.assertEqual(result['strategy_used'], 'server_wins')
        self.assertEqual(result['winning_entry'], self.server_entry)

    def test_most_recent_wins_policy(self):
        """Test most_recent_wins resolution strategy."""
        result = self.service.resolve_conflict(
            domain='task',
            server_entry=self.server_entry,
            client_entry=self.client_entry
        )

        self.assertEqual(result['resolution'], 'resolved')
        self.assertTrue('most_recent_wins' in result['strategy_used'])
        self.assertEqual(result['winning_entry']['mobile_id'], 'uuid-123')

    def test_preserve_escalation_policy(self):
        """Test preserve_escalation smart merge strategy."""
        server_with_escalation = {
            **self.server_entry,
            'escalation_level': 2,
            'escalated_at': '2025-09-28T08:00:00Z',
            'status': 'escalated'
        }

        result = self.service.resolve_conflict(
            domain='ticket',
            server_entry=server_with_escalation,
            client_entry=self.client_entry
        )

        self.assertEqual(result['resolution'], 'resolved')
        self.assertEqual(result['strategy_used'], 'preserve_escalation')
        self.assertEqual(result['winning_entry']['escalation_level'], 2)
        self.assertEqual(result['winning_entry']['status'], 'escalated')

    def test_tenant_custom_policy(self):
        """Test tenant-specific policy override."""
        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='task',
            resolution_policy='client_wins',
            auto_resolve=True
        )

        result = self.service.resolve_conflict(
            domain='task',
            server_entry=self.server_entry,
            client_entry=self.client_entry,
            tenant_id=self.tenant.id
        )

        self.assertEqual(result['strategy_used'], 'client_wins')

    def test_invalid_domain_defaults_to_manual(self):
        """Test unknown domain requires manual resolution."""
        result = self.service.resolve_conflict(
            domain='unknown_domain',
            server_entry=self.server_entry,
            client_entry=self.client_entry
        )

        self.assertEqual(result['resolution'], 'manual_required')
        self.assertIsNone(result['winning_entry'])


@pytest.mark.unit
class TestTenantConflictPolicy(TestCase):
    """Test TenantConflictPolicy model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

    def test_policy_creation(self):
        """Test policy creation with valid data."""
        policy = TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='task',
            resolution_policy='most_recent_wins',
            auto_resolve=True
        )

        self.assertEqual(policy.tenant, self.tenant)
        self.assertEqual(policy.domain, 'task')
        self.assertTrue(policy.auto_resolve)

    def test_policy_unique_constraint(self):
        """Test unique_together constraint on tenant+domain."""
        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='task',
            resolution_policy='client_wins'
        )

        with self.assertRaises(Exception):
            TenantConflictPolicy.objects.create(
                tenant=self.tenant,
                domain='task',
                resolution_policy='server_wins'
            )

    def test_manual_policy_validation(self):
        """Test validation prevents auto_resolve=True with manual policy."""
        with self.assertRaises(ValidationError):
            policy = TenantConflictPolicy(
                tenant=self.tenant,
                domain='task',
                resolution_policy='manual',
                auto_resolve=True
            )
            policy.save()


@pytest.mark.integration
class TestConflictResolutionIntegration(TestCase):
    """Integration tests for conflict resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = ConflictResolutionService()
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

    def test_end_to_end_conflict_resolution(self):
        """Test complete conflict resolution workflow."""
        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='task',
            resolution_policy='most_recent_wins',
            auto_resolve=True,
            notify_on_conflict=True
        )

        server_entry = {
            'mobile_id': 'uuid-456',
            'version': 5,
            'status': 'completed',
            'updated_at': '2025-09-28T12:00:00Z'
        }

        client_entry = {
            'mobile_id': 'uuid-456',
            'version': 4,
            'status': 'in_progress',
            'updated_at': '2025-09-28T11:00:00Z'
        }

        result = self.service.resolve_conflict(
            domain='task',
            server_entry=server_entry,
            client_entry=client_entry,
            tenant_id=self.tenant.id
        )

        self.assertEqual(result['resolution'], 'resolved')
        self.assertEqual(result['winning_entry']['version'], 5)
        self.assertEqual(result['winning_entry']['updated_at'], '2025-09-28T12:00:00Z')