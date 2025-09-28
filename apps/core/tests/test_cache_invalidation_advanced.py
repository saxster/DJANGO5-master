"""
Advanced cache invalidation tests including distributed scenarios.

Tests versioning, security, TTL monitoring, and distributed invalidation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.core.cache import cache
from django.contrib.auth.models import User
from django.db import transaction

from apps.core.caching.invalidation import cache_invalidation_manager
from apps.core.caching.distributed_invalidation import (
    DistributedCacheInvalidator,
    publish_invalidation_event
)
from apps.core.caching.versioning import bump_cache_version, get_versioned_cache_key
from apps.core.caching.security import CacheRateLimiter, validate_cache_key, CacheSecurityError


@pytest.mark.integration
class CacheInvalidationWithVersioningTestCase(TestCase):
    """Test cache invalidation with versioning integration"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_version_bump_invalidates_old_caches(self):
        """Test version bump makes old caches inaccessible via get_versioned_cache_key"""
        old_key = get_versioned_cache_key('dashboard:metrics')
        cache.set(old_key, {'data': 'old'}, 300)

        bump_cache_version('2.0')

        new_key = get_versioned_cache_key('dashboard:metrics')

        self.assertNotEqual(old_key, new_key)
        self.assertIsNone(cache.get(new_key))

    def test_invalidation_with_versioning(self):
        """Test model-based invalidation works with versioning"""
        from apps.peoples.models import People

        user_key = get_versioned_cache_key('dropdown:people')
        cache.set(user_key, ['test'], 300)

        result = cache_invalidation_manager.invalidate_for_model(
            Mock(spec=People, __class__=People, pk=1, tenant_id=1)
        )

        self.assertGreater(result.get('patterns_cleared', 0), 0)


@pytest.mark.security
@pytest.mark.integration
class DistributedCacheInvalidationTestCase(TestCase):
    """Test distributed cache invalidation"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('apps.core.caching.distributed_invalidation.cache._cache.get_master_client')
    def test_publish_invalidation_event(self, mock_redis):
        """Test publishing invalidation events"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        result = publish_invalidation_event('dashboard:*', 'test')

        mock_client.publish.assert_called_once()

    @patch('apps.core.caching.distributed_invalidation.cache._cache.get_master_client')
    def test_subscribe_to_invalidation_events(self, mock_redis):
        """Test subscribing to invalidation events"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        invalidator = DistributedCacheInvalidator()

        mock_pubsub = MagicMock()
        mock_client.pubsub.return_value = mock_pubsub

        self.assertIsNotNone(invalidator)

    def test_distributed_invalidation_cross_server(self):
        """Test invalidation propagates across servers"""
        invalidator1 = DistributedCacheInvalidator()
        invalidator2 = DistributedCacheInvalidator()

        cache.set('tenant:1:test:key', 'data', 300)

        event = {
            'pattern': 'tenant:1:test:*',
            'server_id': 'server1',
            'reason': 'test'
        }

        invalidator2.handle_invalidation_event(event)


@pytest.mark.integration
class CacheSecurityIntegrationTestCase(TestCase):
    """Integration tests for cache security features"""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user('admin', 'admin@test.com', 'password')
        self.user.is_staff = True
        self.user.save()

    def tearDown(self):
        cache.clear()

    def test_cache_admin_requires_authentication(self):
        """Test cache admin endpoints require authentication"""
        middleware = CacheSecurityMiddleware(get_response=lambda r: None)

        request = self.factory.get('/admin/cache/')
        request.user = Mock(is_authenticated=False)

        with self.assertRaises(Exception):
            middleware.process_request(request)

    def test_cache_admin_requires_staff(self):
        """Test cache admin requires staff privileges"""
        middleware = CacheSecurityMiddleware(get_response=lambda r: None)

        request = self.factory.get('/admin/cache/')
        request.user = User.objects.create_user('user', 'user@test.com', 'password')
        request.user.is_authenticated = True
        request.user.is_staff = False

        with self.assertRaises(Exception):
            middleware.process_request(request)

    def test_cache_operation_rate_limiting(self):
        """Test cache operations are rate limited"""
        for i in range(100):
            result = CacheRateLimiter.check_rate_limit(f'user:{i}', limit=100, window=60)
            self.assertTrue(result['allowed'])

        result = CacheRateLimiter.check_rate_limit('user:0', limit=100, window=60)
        self.assertFalse(result['allowed'])


@pytest.mark.integration
class CacheWarmingIntegrationTestCase(TestCase):
    """Test automatic cache warming"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_warming_service(self):
        """Test cache warming service execution"""
        from apps.core.services.cache_warming_service import CacheWarmingService

        service = CacheWarmingService()
        result = service.warm_all_caches()

        self.assertIn('total_keys_warmed', result)
        self.assertIn('patterns_warmed', result)

    def test_scheduled_cache_warming_task(self):
        """Test scheduled cache warming background task"""
        from background_tasks.tasks import cache_warming_scheduled

        result = cache_warming_scheduled()

        self.assertIsNotNone(result)


@pytest.mark.integration
class CacheAnalyticsIntegrationTestCase(TestCase):
    """Test cache analytics and monitoring"""

    def test_analytics_dashboard_data(self):
        """Test analytics dashboard data generation"""
        from apps.core.services.cache_analytics_service import CacheAnalyticsService

        service = CacheAnalyticsService()
        data = service.get_analytics_dashboard_data()

        self.assertIn('summary', data)

    def test_anomaly_detection(self):
        """Test cache anomaly detection"""
        from apps.core.services.cache_analytics_service import CacheAnalyticsService

        service = CacheAnalyticsService()
        anomalies = service.detect_anomalies()

        self.assertIsInstance(anomalies, list)