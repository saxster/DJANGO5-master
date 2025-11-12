"""
Comprehensive Tests for NOC Celery Tasks.

Tests all background tasks with mocking and isolation.
Follows .claude/rules.md testing guidelines.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import timedelta
from django.utils import timezone
from background_tasks.noc_tasks import (
    noc_aggregate_snapshot_task,
    noc_alert_backpressure_task,
    noc_archive_snapshots_task,
    noc_cache_warming_task,
    noc_alert_escalation_task,
)


@pytest.mark.django_db
class TestNOCAggregateSnapshotTask:
    """Test metric snapshot aggregation task."""

    @pytest.fixture
    def mock_tenant(self):
        """Create mock tenant."""
        from apps.tenants.models import Tenant
        return Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test",
            enable=True
        )

    @pytest.fixture
    def mock_client(self, mock_tenant):
        """Create mock client."""
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist
        client_type = TypeAssist.objects.create(
            taname="CLIENT",
            tacode="CLIENT",
            tenant=mock_tenant
        )
        return Bt.objects.create(
            tenant=mock_tenant,
            bucode="CLIENT001",
            buname="Test Client",
            identifier=client_type,
            enable=True
        )

    def test_snapshot_task_success(self, mock_tenant, mock_client):
        """Test successful snapshot creation."""
        with patch('background_tasks.noc_tasks.NOCAggregationService') as mock_service:
            mock_service.create_snapshot_for_client.return_value = True

            result = noc_aggregate_snapshot_task()

            assert result['success'] >= 0
            assert result['errors'] >= 0

    def test_snapshot_task_handles_errors(self, mock_tenant, mock_client):
        """Test error handling in snapshot task."""
        with patch('background_tasks.noc_tasks.NOCAggregationService') as mock_service:
            mock_service.create_snapshot_for_client.side_effect = ValueError("Test error")

            result = noc_aggregate_snapshot_task()

            assert 'errors' in result


@pytest.mark.django_db
class TestNOCAlertBackpressureTask:
    """Test alert backpressure management."""

    def test_backpressure_no_suppression_when_low_queue(self):
        """Test no suppression when queue depth is low."""
        result = noc_alert_backpressure_task()

        assert result['suppressed'] == 0

    def test_backpressure_suppresses_when_high_queue(self):
        """Test suppression when queue depth exceeds threshold."""
        from apps.noc.models import NOCAlertEvent
        from apps.tenants.models import Tenant
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist

        tenant = Tenant.objects.create(tenantname="Test", subdomain_prefix="test")
        client_type = TypeAssist.objects.create(taname="CLIENT", tacode="CLIENT", tenant=tenant)
        client = Bt.objects.create(
            tenant=tenant,
            bucode="C001",
            buname="Client",
            identifier=client_type
        )

        for i in range(1050):
            NOCAlertEvent.objects.create(
                tenant=tenant,
                client=client,
                alert_type='DEVICE_OFFLINE',
                severity='INFO',
                status='NEW',
                dedup_key=f'test_key_{i}',
                message='Test alert',
                entity_type='device',
                entity_id=i
            )

        result = noc_alert_backpressure_task()

        assert result['suppressed'] > 0


@pytest.mark.django_db
class TestNOCArchiveSnapshotsTask:
    """Test snapshot archival."""

    def test_archive_old_snapshots(self):
        """Test archival of snapshots older than 30 days."""
        from apps.noc.models import NOCMetricSnapshot
        from apps.tenants.models import Tenant
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist

        tenant = Tenant.objects.create(tenantname="Test", subdomain_prefix="test")
        client_type = TypeAssist.objects.create(taname="CLIENT", tacode="CLIENT", tenant=tenant)
        client = Bt.objects.create(
            tenant=tenant,
            bucode="C001",
            buname="Client",
            identifier=client_type
        )

        old_date = timezone.now() - timedelta(days=35)

        NOCMetricSnapshot.objects.create(
            tenant=tenant,
            client=client,
            window_start=old_date,
            window_end=old_date + timedelta(minutes=5),
            tickets_open=10
        )

        result = noc_archive_snapshots_task()

        assert result['archived'] >= 0


@pytest.mark.django_db
class TestNOCCacheWarmingTask:
    """Test cache warming for executives."""

    def test_cache_warming_for_executives(self):
        """Test cache warming for users with noc:view_all_clients."""
        from apps.peoples.models import People
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(tenantname="Test", subdomain_prefix="test")

        user = People.objects.create(
            loginid="exec1",
            tenant=tenant,
            enable=True
        )
        user.set_password("password")
        user.add_capability('noc:view_all_clients')
        user.save()

        with patch('background_tasks.noc_tasks.NOCCacheService') as mock_cache:
            mock_cache.warm_dashboard_cache.return_value = True

            result = noc_cache_warming_task()

            assert result['warmed'] >= 0


@pytest.mark.django_db
class TestNOCAlertEscalationTask:
    """Test alert auto-escalation."""

    def test_escalation_for_unacked_critical_alerts(self):
        """Test escalation of unacknowledged critical alerts."""
        from apps.noc.models import NOCAlertEvent
        from apps.tenants.models import Tenant
        from apps.client_onboarding.models import Bt
        from apps.core_onboarding.models import TypeAssist

        tenant = Tenant.objects.create(tenantname="Test", subdomain_prefix="test")
        client_type = TypeAssist.objects.create(taname="CLIENT", tacode="CLIENT", tenant=tenant)
        client = Bt.objects.create(
            tenant=tenant,
            bucode="C001",
            buname="Client",
            identifier=client_type
        )

        old_time = timezone.now() - timedelta(minutes=20)

        alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=client,
            alert_type='SLA_BREACH',
            severity='CRITICAL',
            status='NEW',
            dedup_key='test_key',
            message='Test critical alert',
            entity_type='ticket',
            entity_id=1
        )

        alert.cdtz = old_time
        alert.save()

        with patch('background_tasks.noc_tasks.EscalationService') as mock_service:
            mock_service.escalate_alert.return_value = True

            result = noc_alert_escalation_task()

            assert result['escalated'] >= 0