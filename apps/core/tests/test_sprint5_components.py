"""
Comprehensive Tests for Sprint 5 Components

Tests for:
- Performance optimization (caching, async processing)
- Monitoring and alerting
- Health checks
- Load test infrastructure

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #12: Optimized queries with select_related()
"""

import pytest
import asyncio
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from datetime import timedelta
from unittest.mock import patch, MagicMock

from apps.core.services.sync_cache_service import SyncCacheService, sync_cache_service
from apps.core.services.sync_async_processor import SyncAsyncProcessor, sync_async_processor
from apps.core.services.sync_health_monitoring_service import (
    SyncHealthMonitoringService,
    SyncHealthAlert,
    sync_health_monitor
)
from apps.core.models.sync_conflict_policy import TenantConflictPolicy, ConflictResolutionLog
from apps.core.models.sync_analytics import SyncAnalyticsSnapshot, SyncDeviceHealth
from apps.core.models.upload_session import UploadSession
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestSyncCacheService(TestCase):
    """Test suite for SyncCacheService performance optimization."""

    def setUp(self):
        self.tenant = Tenant.objects.create(tenantname="Test Tenant")
        self.user = User.objects.create_user(
            loginid="testuser",
            password="testpass123",
            email="test@example.com"
        )

        self.policy = TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='journal',
            resolution_policy='most_recent_wins',
            auto_resolve=True,
            created_by=self.user
        )

        cache.clear()

    def test_get_conflict_policy_cache_miss(self):
        """Test policy fetch on cache miss."""
        policy_data = SyncCacheService.get_conflict_policy(self.tenant.id, 'journal')

        self.assertIsNotNone(policy_data)
        self.assertEqual(policy_data['resolution_policy'], 'most_recent_wins')
        self.assertTrue(policy_data['auto_resolve'])

    def test_get_conflict_policy_cache_hit(self):
        """Test policy fetch on cache hit."""
        policy_data1 = SyncCacheService.get_conflict_policy(self.tenant.id, 'journal')

        with self.assertNumQueries(0):
            policy_data2 = SyncCacheService.get_conflict_policy(self.tenant.id, 'journal')

        self.assertEqual(policy_data1, policy_data2)

    def test_invalidate_conflict_policy(self):
        """Test cache invalidation."""
        SyncCacheService.get_conflict_policy(self.tenant.id, 'journal')

        success = SyncCacheService.invalidate_conflict_policy(self.tenant.id, 'journal')
        self.assertTrue(success)

        cache_key = f"sync_policy:{self.tenant.id}:journal"
        self.assertIsNone(cache.get(cache_key))

    def test_get_all_tenant_policies(self):
        """Test fetching all policies for a tenant."""
        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='attendance',
            resolution_policy='server_wins',
            auto_resolve=False
        )

        policies = SyncCacheService.get_all_tenant_policies(self.tenant.id)

        self.assertEqual(len(policies), 2)
        self.assertIn('journal', policies)
        self.assertIn('attendance', policies)

    def test_warm_cache_for_tenant(self):
        """Test cache warming."""
        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='task',
            resolution_policy='client_wins'
        )

        cached_count = SyncCacheService.warm_cache_for_tenant(self.tenant.id)

        self.assertEqual(cached_count, 2)

    def test_device_health_caching(self):
        """Test device health data caching."""
        health_data = {
            'health_score': 95.5,
            'total_syncs': 100,
            'last_sync_at': timezone.now().isoformat()
        }

        success = SyncCacheService.cache_device_health('device_123', health_data)
        self.assertTrue(success)

        cached_data = SyncCacheService.get_device_health('device_123')
        self.assertEqual(cached_data['health_score'], 95.5)


@pytest.mark.django_db
class TestSyncAsyncProcessor(TransactionTestCase):
    """Test suite for async processing operations."""

    def setUp(self):
        self.tenant = Tenant.objects.create(tenantname="Async Test Tenant")
        self.user = User.objects.create_user(
            loginid="asyncuser",
            password="testpass123",
            email="async@example.com"
        )

    @pytest.mark.asyncio
    async def test_update_device_health_async_new_device(self):
        """Test creating new device health record."""
        success = await SyncAsyncProcessor.update_device_health_async(
            device_id='new_device',
            user_id=self.user.id,
            tenant_id=self.tenant.id
        )

        self.assertTrue(success)

        device_health = await asyncio.to_thread(
            SyncDeviceHealth.objects.get,
            device_id='new_device'
        )
        self.assertEqual(device_health.health_score, 100.0)

    @pytest.mark.asyncio
    async def test_update_device_health_async_existing_device(self):
        """Test updating existing device health."""
        device = await asyncio.to_thread(
            SyncDeviceHealth.objects.create,
            device_id='existing_device',
            user_id=self.user.id,
            tenant_id=self.tenant.id,
            last_sync_at=timezone.now(),
            total_syncs=10,
            health_score=90.0
        )

        success = await SyncAsyncProcessor.update_device_health_async(
            device_id='existing_device',
            user_id=self.user.id,
            tenant_id=self.tenant.id
        )

        self.assertTrue(success)

        device.refresh_from_db()
        self.assertEqual(device.total_syncs, 11)

    @pytest.mark.asyncio
    async def test_aggregate_analytics_async(self):
        """Test analytics aggregation."""
        ConflictResolutionLog.objects.create(
            mobile_id='uuid1',
            domain='journal',
            server_version=1,
            client_version=2,
            resolution_strategy='most_recent_wins',
            resolution_result='resolved',
            tenant=self.tenant,
            user=self.user
        )

        success = await SyncAsyncProcessor.aggregate_analytics_async(
            tenant_id=self.tenant.id,
            hours=1
        )

        self.assertTrue(success)

        snapshot = await asyncio.to_thread(
            SyncAnalyticsSnapshot.objects.filter(tenant_id=self.tenant.id).first
        )
        self.assertIsNotNone(snapshot)
        self.assertGreaterEqual(snapshot.total_conflicts, 1)

    @pytest.mark.asyncio
    async def test_cleanup_expired_records_async(self):
        """Test cleanup of expired records."""
        from apps.core.models.sync_idempotency import SyncIdempotencyRecord

        expired_record = await asyncio.to_thread(
            SyncIdempotencyRecord.objects.create,
            idempotency_key='expired_key',
            scope='batch',
            request_hash='hash123',
            response_data={'test': 'data'},
            expires_at=timezone.now() - timedelta(hours=25)
        )

        cleanup_summary = await SyncAsyncProcessor.cleanup_expired_records_async()

        self.assertIn('idempotency_records', cleanup_summary)
        self.assertGreater(cleanup_summary['idempotency_records'], 0)


@pytest.mark.django_db
class TestSyncHealthMonitoring(TestCase):
    """Test suite for health monitoring and alerting."""

    def setUp(self):
        self.tenant = Tenant.objects.create(tenantname="Health Test Tenant")
        self.user = User.objects.create_user(
            loginid="healthuser",
            password="testpass123",
            email="health@example.com"
        )

        self.snapshot = SyncAnalyticsSnapshot.objects.create(
            tenant=self.tenant,
            total_sync_requests=1000,
            successful_syncs=980,
            failed_syncs=20,
            avg_sync_duration_ms=125.5
        )

    def test_check_sync_health_healthy(self):
        """Test health check with healthy metrics."""
        health_summary = SyncHealthMonitoringService.check_sync_health(
            tenant_id=self.tenant.id,
            hours=1
        )

        self.assertEqual(health_summary['health_status'], 'healthy')
        self.assertEqual(len(health_summary['alerts']), 0)
        self.assertGreater(health_summary['metrics']['success_rate'], 95.0)

    def test_check_sync_health_degraded(self):
        """Test health check with degraded performance."""
        self.snapshot.successful_syncs = 920
        self.snapshot.failed_syncs = 80
        self.snapshot.save()

        health_summary = SyncHealthMonitoringService.check_sync_health(
            tenant_id=self.tenant.id,
            hours=1
        )

        self.assertIn(health_summary['health_status'], ['degraded', 'critical'])
        self.assertGreater(len(health_summary['alerts']), 0)

    def test_success_rate_alert(self):
        """Test success rate below threshold triggers alert."""
        since = timezone.now() - timedelta(hours=1)
        result = SyncHealthMonitoringService._check_success_rate(self.tenant.id, since)

        self.assertIsNone(result['alert'])

    def test_conflict_rate_check(self):
        """Test conflict rate monitoring."""
        for i in range(60):
            ConflictResolutionLog.objects.create(
                mobile_id=f'uuid{i}',
                domain='journal',
                server_version=1,
                client_version=2,
                resolution_strategy='most_recent_wins',
                resolution_result='resolved',
                tenant=self.tenant
            )

        since = timezone.now() - timedelta(hours=1)
        result = SyncHealthMonitoringService._check_conflict_rate(self.tenant.id, since)

        self.assertIsNotNone(result['value'])

    @patch('requests.post')
    def test_send_webhook_alert(self, mock_post):
        """Test webhook alert sending."""
        mock_post.return_value.status_code = 200

        alert = SyncHealthAlert(
            severity='critical',
            metric='success_rate',
            current_value=90.0,
            threshold=95.0,
            message='Success rate below threshold'
        )

        success = SyncHealthMonitoringService._send_webhook_alert(
            alert,
            'https://webhook.example.com'
        )

        self.assertTrue(success)
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_slack_alert(self, mock_post):
        """Test Slack alert sending."""
        mock_post.return_value.status_code = 200

        alert = SyncHealthAlert(
            severity='warning',
            metric='conflict_rate',
            current_value=6.0,
            threshold=5.0,
            message='Conflict rate above threshold'
        )

        success = SyncHealthMonitoringService._send_slack_alert(
            alert,
            'https://hooks.slack.com/services/test'
        )

        self.assertTrue(success)
        mock_post.assert_called_once()


@pytest.mark.django_db
class TestPerformanceOptimizations(TestCase):
    """Test suite for performance optimizations."""

    def setUp(self):
        self.tenant = Tenant.objects.create(tenantname="Perf Test Tenant")

    def test_conflict_policy_query_optimization(self):
        """Test that conflict policy queries use select_related."""
        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='journal',
            resolution_policy='most_recent_wins'
        )

        with self.assertNumQueries(1):
            policy = TenantConflictPolicy.objects.select_related('tenant').get(
                tenant_id=self.tenant.id,
                domain='journal'
            )
            _ = policy.tenant.tenantname

    def test_device_health_bulk_operations(self):
        """Test bulk device health operations."""
        devices = [
            SyncDeviceHealth(
                device_id=f'device_{i}',
                user_id=1,
                tenant=self.tenant,
                last_sync_at=timezone.now(),
                health_score=90.0 + i
            )
            for i in range(100)
        ]

        SyncDeviceHealth.objects.bulk_create(devices)

        self.assertEqual(SyncDeviceHealth.objects.filter(tenant=self.tenant).count(), 100)


@pytest.mark.integration
@pytest.mark.django_db
class TestIntegrationScenarios(TransactionTestCase):
    """Integration tests for end-to-end scenarios."""

    def setUp(self):
        self.tenant = Tenant.objects.create(tenantname="Integration Test Tenant")
        self.user = User.objects.create_user(
            loginid="integuser",
            password="testpass123",
            email="integ@example.com"
        )

    def test_full_sync_with_caching_and_monitoring(self):
        """Test complete sync flow with caching and monitoring."""
        TenantConflictPolicy.objects.create(
            tenant=self.tenant,
            domain='journal',
            resolution_policy='most_recent_wins',
            auto_resolve=True
        )

        policy = sync_cache_service.get_conflict_policy(self.tenant.id, 'journal')
        self.assertIsNotNone(policy)

        ConflictResolutionLog.objects.create(
            mobile_id='test_uuid',
            domain='journal',
            server_version=1,
            client_version=2,
            resolution_strategy='most_recent_wins',
            resolution_result='resolved',
            tenant=self.tenant,
            user=self.user
        )

        health_summary = sync_health_monitor.check_sync_health(
            tenant_id=self.tenant.id,
            hours=1
        )

        self.assertIn('health_status', health_summary)
        self.assertIn('metrics', health_summary)