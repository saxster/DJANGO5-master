"""
Comprehensive Tests for Sync Analytics

Following .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.core.models.sync_analytics import SyncAnalyticsSnapshot, SyncDeviceHealth
from apps.core.services.sync_analytics_service import SyncAnalyticsService
from apps.core.models.sync_conflict_policy import ConflictResolutionLog
from apps.tenants.models import Tenant
from apps.peoples.models import People


@pytest.mark.unit
class TestSyncAnalyticsSnapshot(TestCase):
    """Test SyncAnalyticsSnapshot model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

    def test_snapshot_creation(self):
        """Test creating analytics snapshot."""
        snapshot = SyncAnalyticsSnapshot.objects.create(
            tenant=self.tenant,
            total_sync_requests=100,
            successful_syncs=95,
            failed_syncs=5,
            total_conflicts=10,
            auto_resolved_conflicts=8,
            manual_conflicts=2
        )

        self.assertEqual(snapshot.total_sync_requests, 100)
        self.assertEqual(snapshot.success_rate_pct, 95.0)

    def test_success_rate_calculation(self):
        """Test success rate percentage calculation."""
        snapshot = SyncAnalyticsSnapshot.objects.create(
            tenant=self.tenant,
            total_sync_requests=200,
            successful_syncs=180,
            failed_syncs=20
        )

        self.assertEqual(snapshot.success_rate_pct, 90.0)

    def test_zero_requests_success_rate(self):
        """Test success rate with zero requests."""
        snapshot = SyncAnalyticsSnapshot.objects.create(
            tenant=self.tenant,
            total_sync_requests=0,
            successful_syncs=0,
            failed_syncs=0
        )

        self.assertEqual(snapshot.success_rate_pct, 0.0)


@pytest.mark.unit
class TestSyncDeviceHealth(TestCase):
    """Test SyncDeviceHealth model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        self.user = People.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com"
        )

    def test_device_health_creation(self):
        """Test creating device health record."""
        device_health = SyncDeviceHealth.objects.create(
            device_id="device-123",
            user=self.user,
            tenant=self.tenant,
            last_sync_at=timezone.now(),
            total_syncs=50,
            failed_syncs_count=2,
            avg_sync_duration_ms=150.0
        )

        self.assertEqual(device_health.device_id, "device-123")
        self.assertEqual(device_health.total_syncs, 50)

    def test_health_score_calculation(self):
        """Test health score calculation algorithm."""
        device_health = SyncDeviceHealth.objects.create(
            device_id="device-456",
            user=self.user,
            tenant=self.tenant,
            last_sync_at=timezone.now() - timedelta(hours=1),
            total_syncs=100,
            failed_syncs_count=10,
            conflicts_encountered=5,
            avg_sync_duration_ms=200.0
        )

        device_health.update_health_score()

        self.assertGreater(device_health.health_score, 50.0)
        self.assertLess(device_health.health_score, 100.0)

    def test_perfect_health_score(self):
        """Test perfect health score with no failures."""
        device_health = SyncDeviceHealth.objects.create(
            device_id="device-789",
            user=self.user,
            tenant=self.tenant,
            last_sync_at=timezone.now(),
            total_syncs=100,
            failed_syncs_count=0,
            conflicts_encountered=0,
            avg_sync_duration_ms=100.0
        )

        device_health.update_health_score()

        self.assertGreater(device_health.health_score, 90.0)


@pytest.mark.unit
class TestSyncAnalyticsService(TestCase):
    """Test SyncAnalyticsService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SyncAnalyticsService()
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        self.user = People.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com"
        )

    def test_create_snapshot_from_logs(self):
        """Test snapshot creation from conflict logs."""
        for i in range(10):
            ConflictResolutionLog.objects.create(
                mobile_id=f"uuid-{i}",
                domain='task',
                server_version=3,
                client_version=2,
                resolution_strategy='most_recent_wins',
                resolution_result='resolved' if i < 8 else 'manual_required',
                tenant=self.tenant
            )

        snapshot = self.service.create_snapshot(
            tenant_id=self.tenant.id,
            time_window_hours=1
        )

        self.assertEqual(snapshot.total_conflicts, 10)
        self.assertEqual(snapshot.auto_resolved_conflicts, 8)
        self.assertEqual(snapshot.manual_conflicts, 2)

    def test_update_device_health_on_success(self):
        """Test device health update on successful sync."""
        device_health = self.service.update_device_health(
            device_id="device-success",
            user=self.user,
            sync_success=True,
            sync_duration_ms=150.0,
            conflict_occurred=False
        )

        self.assertEqual(device_health.total_syncs, 1)
        self.assertEqual(device_health.failed_syncs_count, 0)

    def test_update_device_health_on_failure(self):
        """Test device health update on failed sync."""
        device_health = self.service.update_device_health(
            device_id="device-fail",
            user=self.user,
            sync_success=False,
            sync_duration_ms=300.0,
            conflict_occurred=True
        )

        self.assertEqual(device_health.total_syncs, 1)
        self.assertEqual(device_health.failed_syncs_count, 1)
        self.assertEqual(device_health.conflicts_encountered, 1)

    def test_get_dashboard_metrics(self):
        """Test dashboard metrics aggregation."""
        ConflictResolutionLog.objects.create(
            mobile_id="uuid-test",
            domain='task',
            server_version=3,
            client_version=2,
            resolution_strategy='client_wins',
            resolution_result='resolved',
            tenant=self.tenant
        )

        metrics = self.service.get_dashboard_metrics(tenant_id=self.tenant.id)

        self.assertIn('latest_snapshot', metrics)
        self.assertIn('trend_7days', metrics)
        self.assertIn('unhealthy_devices', metrics)
        self.assertIn('conflict_hotspots', metrics)


@pytest.mark.integration
class TestSyncAnalyticsIntegration(TestCase):
    """Integration tests for sync analytics."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SyncAnalyticsService()
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        self.user = People.objects.create(
            loginid="testuser",
            peoplename="Test User",
            email="test@example.com"
        )

    def test_end_to_end_analytics_workflow(self):
        """Test complete analytics workflow."""
        for i in range(20):
            ConflictResolutionLog.objects.create(
                mobile_id=f"uuid-{i}",
                domain='task' if i % 2 == 0 else 'ticket',
                server_version=3,
                client_version=2,
                resolution_strategy='most_recent_wins',
                resolution_result='resolved',
                tenant=self.tenant,
                user=self.user
            )

        snapshot = self.service.create_snapshot(
            tenant_id=self.tenant.id,
            time_window_hours=1
        )

        self.assertEqual(snapshot.total_conflicts, 20)

        for j in range(5):
            self.service.update_device_health(
                device_id=f"device-{j}",
                user=self.user,
                sync_success=True,
                sync_duration_ms=150.0 + j * 10
            )

        metrics = self.service.get_dashboard_metrics(tenant_id=self.tenant.id)

        self.assertIsNotNone(metrics['latest_snapshot'])
        self.assertGreater(len(metrics['conflict_hotspots']), 0)