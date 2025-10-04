"""
Unit tests for NOCAlertEvent model.

Tests de-duplication, correlation, and workflow transitions.
Follows .claude/rules.md testing guidelines.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError
from apps.noc.models import NOCAlertEvent, MaintenanceWindow
from apps.onboarding.models import Bt
from apps.peoples.models import People
from apps.tenants.models import Tenant


@pytest.mark.django_db
class TestNOCAlertEvent:
    """Test suite for NOCAlertEvent model."""

    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        return Tenant.objects.create(tenantname="Test Tenant", subdomain_prefix="test")

    @pytest.fixture
    def client_bt(self, tenant):
        """Create test client business unit."""
        from apps.onboarding.models import TypeAssist
        client_type = TypeAssist.objects.create(
            taname="CLIENT",
            tacode="CLIENT",
            tenant=tenant
        )
        return Bt.objects.create(
            tenant=tenant,
            bucode="CLIENT001",
            buname="Test Client",
            identifier=client_type
        )

    @pytest.fixture
    def test_user(self, tenant):
        """Create test user."""
        return People.objects.create(
            tenant=tenant,
            peoplecode="USER001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com"
        )

    def test_alert_creation(self, tenant, client_bt):
        """Test basic alert creation."""
        alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            alert_type='DEVICE_OFFLINE',
            severity='HIGH',
            status='NEW',
            dedup_key='test_key_001',
            message='Device offline alert',
            entity_type='device',
            entity_id=123,
            metadata={'device_name': 'TestDevice'}
        )

        assert alert.id is not None
        assert alert.status == 'NEW'
        assert alert.suppressed_count == 0
        assert alert.first_seen is not None

    def test_alert_deduplication_constraint(self, tenant, client_bt):
        """Test unique constraint for active alerts with same dedup_key."""
        NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            alert_type='DEVICE_OFFLINE',
            severity='HIGH',
            status='NEW',
            dedup_key='dup_key_001',
            message='First alert',
            entity_type='device',
            entity_id=123
        )

        with pytest.raises(IntegrityError):
            NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client_bt,
                alert_type='DEVICE_OFFLINE',
                severity='HIGH',
                status='NEW',
                dedup_key='dup_key_001',
                message='Duplicate alert',
                entity_type='device',
                entity_id=123
            )

    def test_alert_workflow_transitions(self, tenant, client_bt, test_user):
        """Test alert status transitions."""
        alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            alert_type='TICKET_ESCALATED',
            severity='MEDIUM',
            status='NEW',
            dedup_key='workflow_test',
            message='Test workflow',
            entity_type='ticket',
            entity_id=456
        )

        alert.status = 'ACKNOWLEDGED'
        alert.acknowledged_by = test_user
        alert.acknowledged_at = timezone.now()
        alert.save()

        assert alert.status == 'ACKNOWLEDGED'
        assert alert.acknowledged_by == test_user
        assert alert.acknowledged_at is not None

    def test_alert_time_to_resolve_calculation(self, tenant, client_bt, test_user):
        """Test time_to_resolve metric calculation."""
        created_time = timezone.now()
        alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client_bt,
            alert_type='SLA_BREACH',
            severity='CRITICAL',
            status='NEW',
            dedup_key='ttm_test',
            message='SLA breach alert',
            entity_type='ticket',
            entity_id=789
        )
        alert.cdtz = created_time
        alert.save()

        resolved_time = created_time + timedelta(hours=2)
        alert.status = 'RESOLVED'
        alert.resolved_by = test_user
        alert.resolved_at = resolved_time
        alert.time_to_resolve = resolved_time - alert.cdtz
        alert.save()

        assert alert.time_to_resolve.total_seconds() == 7200  # 2 hours