"""
Monitoring API Key Authentication Tests

Tests the API key authentication system for monitoring endpoints that replaced
@csrf_exempt decorators with secure API key validation.

Test Coverage:
1. API key validation and extraction
2. IP whitelisting enforcement
3. Rate limiting per API key
4. Monitoring endpoint access control
5. API key rotation and expiration

Security Compliance:
- Rule #3: Alternative Protection - API key authentication for monitoring endpoints
- CVSS 8.1 vulnerability remediation
- Production-grade monitoring system integration

Author: Security Remediation Team
Date: 2025-09-27
"""

import pytest
import hashlib
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, Client, RequestFactory
from django.core.cache import cache
from django.utils import timezone

from apps.core.models import APIKey
from apps.core.models.monitoring_api_key import (
    MonitoringAPIKey, MonitoringPermission, MonitoringAPIAccessLog
)
from apps.core.decorators import require_monitoring_api_key
from apps.peoples.models import People


@pytest.mark.security
class MonitoringAPIKeyAuthenticationTest(TestCase):
    """
    Test monitoring API key authentication decorator.

    Validates that require_monitoring_api_key correctly authenticates
    requests from external monitoring systems.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client()

        self.admin_user = People.objects.create_user(
            loginid='monitoring_admin',
            email='monitoring@example.com',
            password='monitoring123',
            firstname='Monitoring',
            lastname='Admin'
        )
        self.admin_user.is_staff = True
        self.admin_user.save()

        self.api_key_instance, self.raw_api_key = MonitoringAPIKey.create_key(
            name="Test Prometheus",
            monitoring_system="prometheus",
            permissions=[
                MonitoringPermission.HEALTH_CHECK.value,
                MonitoringPermission.METRICS.value
            ],
            allowed_ips=None,
            expires_days=30,
            created_by=self.admin_user
        )

        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_monitoring_endpoint_rejects_without_api_key(self):
        """
        Test that monitoring endpoints reject requests without API key.
        """
        response = self.client.get('/monitoring/health/')

        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertEqual(response_data['code'], 'API_KEY_REQUIRED')

    def test_monitoring_endpoint_accepts_with_valid_api_key_in_header(self):
        """
        Test that monitoring endpoints accept requests with valid API key in Authorization header.
        """
        response = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_api_key}'
        )

        self.assertNotEqual(response.status_code, 401)

    def test_monitoring_endpoint_accepts_with_api_key_in_x_monitoring_header(self):
        """
        Test that monitoring endpoints accept API key in X-Monitoring-API-Key header.
        """
        response = self.client.get(
            '/monitoring/metrics/',
            HTTP_X_MONITORING_API_KEY=self.raw_api_key
        )

        self.assertNotEqual(response.status_code, 401)

    def test_monitoring_endpoint_warns_on_query_param_api_key(self):
        """
        Test that using API key in query param works but logs a warning.
        """
        with self.assertLogs('apps.core.decorators', level='WARNING') as log_context:
            response = self.client.get(
                f'/monitoring/health/?api_key={self.raw_api_key}'
            )

            self.assertNotEqual(response.status_code, 401)
            self.assertTrue(
                any('query string' in log.lower() for log in log_context.output),
                "Expected warning about API key in query string"
            )

    def test_monitoring_endpoint_rejects_invalid_api_key(self):
        """
        Test that monitoring endpoints reject invalid API keys.
        """
        response = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION='Bearer invalid_key_abc123'
        )

        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertEqual(response_data['code'], 'API_KEY_INVALID')

    def test_monitoring_endpoint_rejects_expired_api_key(self):
        """
        Test that monitoring endpoints reject expired API keys.
        """
        self.api_key_instance.expires_at = timezone.now() - timedelta(hours=1)
        self.api_key_instance.save()

        cache.clear()

        response = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_api_key}'
        )

        self.assertEqual(response.status_code, 401)

    def test_monitoring_endpoint_rejects_inactive_api_key(self):
        """
        Test that monitoring endpoints reject inactive API keys.
        """
        self.api_key_instance.is_active = False
        self.api_key_instance.save()

        cache.clear()

        response = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_api_key}'
        )

        self.assertEqual(response.status_code, 401)


@pytest.mark.security
class MonitoringAPIKeyIPWhitelistTest(TestCase):
    """
    Test IP whitelisting for monitoring API keys.

    Validates that API keys with IP restrictions only allow requests
    from whitelisted IP addresses.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client()

        admin_user = People.objects.create_user(
            loginid='ip_test_admin',
            email='iptest@example.com',
            password='iptest123',
            firstname='IP',
            lastname='Admin'
        )

        self.restricted_key_instance, self.restricted_raw_key = MonitoringAPIKey.create_key(
            name="IP Restricted Prometheus",
            monitoring_system="prometheus",
            permissions=[MonitoringPermission.HEALTH_CHECK.value],
            allowed_ips=["192.168.1.100", "10.0.0.50"],
            created_by=admin_user
        )

        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_whitelisted_ip_allowed(self):
        """
        Test that requests from whitelisted IPs are allowed.
        """
        response = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.restricted_raw_key}',
            REMOTE_ADDR='192.168.1.100'
        )

        self.assertNotEqual(response.status_code, 401)

    def test_non_whitelisted_ip_rejected(self):
        """
        Test that requests from non-whitelisted IPs are rejected.
        """
        response = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.restricted_raw_key}',
            REMOTE_ADDR='192.168.1.200'
        )

        self.assertEqual(response.status_code, 401)

    def test_ip_whitelist_with_x_forwarded_for(self):
        """
        Test IP whitelisting works with X-Forwarded-For header (proxy support).
        """
        response = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.restricted_raw_key}',
            HTTP_X_FORWARDED_FOR='10.0.0.50, 192.168.1.1'
        )

        self.assertNotEqual(response.status_code, 401)


@pytest.mark.security
class MonitoringAPIKeyRateLimitTest(TestCase):
    """
    Test rate limiting for monitoring API keys.

    Validates that monitoring endpoints enforce rate limits per API key
    to prevent abuse and ensure fair usage.
    """

    def setUp(self):
        self.client = Client()

        admin_user = People.objects.create_user(
            loginid='rate_test_admin',
            email='ratetest@example.com',
            password='ratetest123',
            firstname='Rate',
            lastname='Admin'
        )

        self.key_instance, self.raw_key = MonitoringAPIKey.create_key(
            name="Rate Limited Grafana",
            monitoring_system="grafana",
            permissions=[MonitoringPermission.METRICS.value],
            created_by=admin_user
        )

        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_rate_limit_enforced_after_1000_requests(self):
        """
        Test that rate limiting is enforced after 1000 requests per hour.

        Note: This is a simplified test - full test would make 1000 requests.
        """
        cache_key = f"monitoring_rate:{self.key_instance.id}"
        cache.set(cache_key, 999, 3600)

        response1 = self.client.get(
            '/monitoring/metrics/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertNotEqual(response1.status_code, 429)

        response2 = self.client.get(
            '/monitoring/metrics/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertEqual(response2.status_code, 429)
        response_data = response2.json()
        self.assertEqual(response_data['code'], 'RATE_LIMIT_EXCEEDED')

    def test_rate_limit_independent_per_api_key(self):
        """
        Test that rate limits are tracked independently per API key.
        """
        admin_user = People.objects.get(loginid='rate_test_admin')

        key2_instance, raw_key2 = MonitoringAPIKey.create_key(
            name="Second Grafana",
            monitoring_system="grafana",
            permissions=[MonitoringPermission.METRICS.value],
            created_by=admin_user
        )

        cache_key1 = f"monitoring_rate:{self.key_instance.id}"
        cache.set(cache_key1, 1000, 3600)

        response1 = self.client.get(
            '/monitoring/metrics/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertEqual(response1.status_code, 429)

        response2 = self.client.get(
            '/monitoring/metrics/',
            HTTP_AUTHORIZATION=f'Bearer {raw_key2}'
        )
        self.assertNotEqual(response2.status_code, 429)


@pytest.mark.security
class MonitoringAPIKeyRotationTest(TestCase):
    """
    Test API key rotation functionality.

    Validates that keys can be rotated with grace periods for zero-downtime
    updates to monitoring systems.
    """

    def setUp(self):
        self.admin_user = People.objects.create_user(
            loginid='rotation_admin',
            email='rotation@example.com',
            password='rotation123',
            firstname='Rotation',
            lastname='Admin'
        )

        self.original_key, self.original_raw_key = MonitoringAPIKey.create_key(
            name="To Be Rotated",
            monitoring_system="prometheus",
            permissions=[MonitoringPermission.ADMIN.value],
            rotation_schedule='monthly',
            created_by=self.admin_user
        )

        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_key_rotation_creates_new_key_and_expires_old(self):
        """
        Test that key rotation creates a new key and sets expiration on old key.
        """
        original_id = self.original_key.id
        original_expires_at = self.original_key.expires_at

        new_key, new_raw_key = self.original_key.rotate_key(created_by=self.admin_user)

        self.assertNotEqual(new_key.id, original_id)
        self.assertNotEqual(new_raw_key, self.original_raw_key)

        self.original_key.refresh_from_db()
        self.assertIsNotNone(self.original_key.expires_at)
        self.assertNotEqual(self.original_key.expires_at, original_expires_at)

    def test_both_keys_valid_during_grace_period(self):
        """
        Test that both old and new keys work during grace period.
        """
        client = Client()

        new_key, new_raw_key = self.original_key.rotate_key(created_by=self.admin_user)

        cache.clear()

        response1 = client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.original_raw_key}'
        )
        self.assertNotEqual(response1.status_code, 401, "Old key should work during grace period")

        response2 = client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {new_raw_key}'
        )
        self.assertNotEqual(response2.status_code, 401, "New key should work immediately")

    def test_old_key_expires_after_grace_period(self):
        """
        Test that old key expires after grace period.
        """
        new_key, new_raw_key = self.original_key.rotate_key(created_by=self.admin_user)

        self.original_key.expires_at = timezone.now() - timedelta(hours=1)
        self.original_key.save()

        cache.clear()

        client = Client()

        response = client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.original_raw_key}'
        )
        self.assertEqual(response.status_code, 401)

    def test_rotation_preserves_permissions_and_settings(self):
        """
        Test that key rotation preserves permissions and configuration.
        """
        new_key, new_raw_key = self.original_key.rotate_key(created_by=self.admin_user)

        self.assertEqual(new_key.permissions, self.original_key.permissions)
        self.assertEqual(new_key.monitoring_system, self.original_key.monitoring_system)
        self.assertEqual(new_key.allowed_ips, self.original_key.allowed_ips)
        self.assertEqual(new_key.rotation_schedule, self.original_key.rotation_schedule)


@pytest.mark.security
class MonitoringEndpointAccessTest(TestCase):
    """
    Test access to monitoring endpoints with API key authentication.

    Validates all 6 monitoring endpoints work correctly with API keys.
    """

    def setUp(self):
        self.client = Client()

        admin_user = People.objects.create_user(
            loginid='endpoint_admin',
            email='endpoint@example.com',
            password='endpoint123',
            firstname='Endpoint',
            lastname='Admin'
        )

        self.key_instance, self.raw_key = MonitoringAPIKey.create_key(
            name="Full Access Monitoring",
            monitoring_system="datadog",
            permissions=[MonitoringPermission.ADMIN.value],
            created_by=admin_user
        )

        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_health_check_endpoint_requires_api_key(self):
        """
        Test HealthCheckEndpoint requires API key authentication.
        """
        response = self.client.get('/monitoring/health/')
        self.assertEqual(response.status_code, 401)

        response_with_key = self.client.get(
            '/monitoring/health/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertNotEqual(response_with_key.status_code, 401)

    def test_metrics_endpoint_requires_api_key(self):
        """
        Test MetricsEndpoint requires API key authentication.
        """
        response = self.client.get('/monitoring/metrics/')
        self.assertEqual(response.status_code, 401)

        response_with_key = self.client.get(
            '/monitoring/metrics/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertNotEqual(response_with_key.status_code, 401)

    def test_query_performance_endpoint_requires_api_key(self):
        """
        Test QueryPerformanceView requires API key authentication.
        """
        response = self.client.get('/monitoring/query-performance/')
        self.assertEqual(response.status_code, 401)

        response_with_key = self.client.get(
            '/monitoring/query-performance/?window=30',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertNotEqual(response_with_key.status_code, 401)

    def test_cache_performance_endpoint_requires_api_key(self):
        """
        Test CachePerformanceView requires API key authentication.
        """
        response = self.client.get('/monitoring/cache-performance/')
        self.assertEqual(response.status_code, 401)

        response_with_key = self.client.get(
            '/monitoring/cache-performance/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertNotEqual(response_with_key.status_code, 401)

    def test_alerts_endpoint_requires_api_key(self):
        """
        Test AlertsView requires API key authentication.
        """
        response = self.client.get('/monitoring/alerts/')
        self.assertEqual(response.status_code, 401)

        response_with_key = self.client.get(
            '/monitoring/alerts/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertNotEqual(response_with_key.status_code, 401)

    def test_dashboard_endpoint_requires_api_key(self):
        """
        Test DashboardDataView requires API key authentication.
        """
        response = self.client.get('/monitoring/dashboard/')
        self.assertEqual(response.status_code, 401)

        response_with_key = self.client.get(
            '/monitoring/dashboard/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        self.assertNotEqual(response_with_key.status_code, 401)


@pytest.mark.security
class MonitoringAPIKeyPermissionTest(TestCase):
    """
    Test granular permission enforcement for monitoring API keys.

    Validates that permission checks work correctly (when implemented).
    """

    def setUp(self):
        self.admin_user = People.objects.create_user(
            loginid='perm_admin',
            email='perm@example.com',
            password='perm123',
            firstname='Perm',
            lastname='Admin'
        )

        self.limited_key, self.limited_raw_key = MonitoringAPIKey.create_key(
            name="Health Check Only",
            monitoring_system="custom",
            permissions=[MonitoringPermission.HEALTH_CHECK.value],
            created_by=self.admin_user
        )

        self.admin_key, self.admin_raw_key = MonitoringAPIKey.create_key(
            name="Full Admin Access",
            monitoring_system="custom",
            permissions=[MonitoringPermission.ADMIN.value],
            created_by=self.admin_user
        )

        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_has_permission_method(self):
        """
        Test has_permission method on MonitoringAPIKey model.
        """
        self.assertTrue(
            self.limited_key.has_permission(MonitoringPermission.HEALTH_CHECK.value)
        )
        self.assertFalse(
            self.limited_key.has_permission(MonitoringPermission.METRICS.value)
        )

        self.assertTrue(
            self.admin_key.has_permission(MonitoringPermission.HEALTH_CHECK.value)
        )
        self.assertTrue(
            self.admin_key.has_permission(MonitoringPermission.METRICS.value)
        )
        self.assertTrue(
            self.admin_key.has_permission(MonitoringPermission.ADMIN.value)
        )


@pytest.mark.security
class MonitoringAPIKeyModelTest(TestCase):
    """
    Test MonitoringAPIKey model methods and utilities.
    """

    def setUp(self):
        self.admin_user = People.objects.create_user(
            loginid='model_admin',
            email='model@example.com',
            password='model123',
            firstname='Model',
            lastname='Admin'
        )

    def test_generate_key_creates_secure_key(self):
        """
        Test that generate_key creates secure random keys.
        """
        key1, hash1 = MonitoringAPIKey.generate_key()
        key2, hash2 = MonitoringAPIKey.generate_key()

        self.assertNotEqual(key1, key2)
        self.assertNotEqual(hash1, hash2)
        self.assertEqual(len(key1), 43)
        self.assertEqual(len(hash1), 64)

    def test_is_expired_method(self):
        """
        Test is_expired method correctly identifies expired keys.
        """
        key_instance, _ = MonitoringAPIKey.create_key(
            name="Expiring Key",
            monitoring_system="custom",
            permissions=[MonitoringPermission.HEALTH_CHECK.value],
            expires_days=30,
            created_by=self.admin_user
        )

        self.assertFalse(key_instance.is_expired())

        key_instance.expires_at = timezone.now() - timedelta(hours=1)
        key_instance.save()

        self.assertTrue(key_instance.is_expired())

    def test_needs_rotation_method(self):
        """
        Test needs_rotation method identifies keys needing rotation.
        """
        key_instance, _ = MonitoringAPIKey.create_key(
            name="Rotation Test Key",
            monitoring_system="custom",
            permissions=[MonitoringPermission.HEALTH_CHECK.value],
            rotation_schedule='monthly',
            created_by=self.admin_user
        )

        self.assertFalse(key_instance.needs_rotation())

        key_instance.next_rotation_at = timezone.now() - timedelta(days=1)
        key_instance.save()

        self.assertTrue(key_instance.needs_rotation())

    def test_get_keys_needing_rotation_queryset(self):
        """
        Test get_keys_needing_rotation class method.
        """
        key1, _ = MonitoringAPIKey.create_key(
            name="Needs Rotation",
            monitoring_system="custom",
            permissions=[MonitoringPermission.HEALTH_CHECK.value],
            rotation_schedule='monthly',
            created_by=self.admin_user
        )
        key1.next_rotation_at = timezone.now() - timedelta(days=1)
        key1.save()

        key2, _ = MonitoringAPIKey.create_key(
            name="Does Not Need Rotation",
            monitoring_system="custom",
            permissions=[MonitoringPermission.HEALTH_CHECK.value],
            rotation_schedule='yearly',
            created_by=self.admin_user
        )

        keys_needing_rotation = MonitoringAPIKey.get_keys_needing_rotation()

        self.assertIn(key1, keys_needing_rotation)
        self.assertNotIn(key2, keys_needing_rotation)

    def test_cleanup_expired_keys(self):
        """
        Test cleanup_expired_keys removes old expired keys.
        """
        old_key, _ = MonitoringAPIKey.create_key(
            name="Old Expired Key",
            monitoring_system="custom",
            permissions=[MonitoringPermission.HEALTH_CHECK.value],
            created_by=self.admin_user
        )
        old_key.expires_at = timezone.now() - timedelta(days=2)
        old_key.is_active = False
        old_key.save()

        deleted_count = MonitoringAPIKey.cleanup_expired_keys(grace_period_hours=24)

        self.assertEqual(deleted_count, 1)
        self.assertFalse(MonitoringAPIKey.objects.filter(id=old_key.id).exists())


@pytest.mark.security
class MonitoringAPIDecoratorTest(TestCase):
    """
    Test the require_monitoring_api_key decorator directly.

    Unit tests for decorator behavior independent of view implementation.
    """

    def setUp(self):
        self.factory = RequestFactory()

        admin_user = People.objects.create_user(
            loginid='decorator_admin',
            email='decorator@example.com',
            password='decorator123',
            firstname='Decorator',
            lastname='Admin'
        )

        self.key_instance, self.raw_key = MonitoringAPIKey.create_key(
            name="Decorator Test Key",
            monitoring_system="custom",
            permissions=[MonitoringPermission.METRICS.value],
            created_by=admin_user
        )

        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_decorator_attaches_api_key_to_request(self):
        """
        Test that decorator attaches API key object to request.
        """
        @require_monitoring_api_key
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({
                'authenticated': request.monitoring_authenticated,
                'key_name': request.monitoring_api_key.get('name')
            })

        request = self.factory.get(
            '/test/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        request.correlation_id = 'test-correlation-id'

        response = test_view(request)
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)
        self.assertTrue(response_data['authenticated'])
        self.assertEqual(response_data['key_name'], 'Decorator Test Key')

    def test_decorator_caches_api_key_validation(self):
        """
        Test that decorator caches API key validation results.
        """
        @require_monitoring_api_key
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({'status': 'ok'})

        request = self.factory.get(
            '/test/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        request.correlation_id = 'test-correlation-id'

        with self.assertNumQueries(1):
            response1 = test_view(request)
            self.assertEqual(response1.status_code, 200)

        request2 = self.factory.get(
            '/test/',
            HTTP_AUTHORIZATION=f'Bearer {self.raw_key}'
        )
        request2.correlation_id = 'test-correlation-id-2'

        with self.assertNumQueries(0):
            response2 = test_view(request2)
            self.assertEqual(response2.status_code, 200)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])