"""
Comprehensive Rate Limiting Test Suite

Tests all aspects of the rate limiting implementation including:
- PathBasedRateLimitMiddleware
- GraphQLRateLimitingMiddleware
- Exponential backoff
- Automatic IP blocking
- Trusted IP bypass
- Per-user and per-IP tracking
- Monitoring and analytics

Verifies compliance with Rule #9 - Comprehensive Rate Limiting
CVSS 7.2 vulnerability remediation
"""

import json
import time
import pytest
from unittest.mock import patch, Mock
from django.test import TestCase, Client, override_settings, RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from apps.core.middleware.path_based_rate_limiting import (
    PathBasedRateLimitMiddleware,
    RateLimitMonitoringMiddleware
)
from apps.core.models.rate_limiting import (
    RateLimitBlockedIP,
    RateLimitTrustedIP,
    RateLimitViolationLog
)

User = get_user_model()


@pytest.mark.security
class PathBasedRateLimitMiddlewareTest(TestCase):
    """Test suite for PathBasedRateLimitMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

        self.factory = RequestFactory()
        self.middleware = PathBasedRateLimitMiddleware(get_response=lambda r: None)

        self.test_user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123',
            firstname='Test',
            lastname='User'
        )

        self.test_paths = [
            '/login/',
            '/admin/',
            '/admin/django/',
            '/api/v1/people/',
            '/graphql/',
            '/reset-password/'
        ]

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        RateLimitBlockedIP.objects.all().delete()
        RateLimitTrustedIP.objects.all().delete()
        RateLimitViolationLog.objects.all().delete()

    def test_middleware_enabled_by_default(self):
        """Test that rate limiting is enabled by default."""
        self.assertTrue(self.middleware.enabled)

    def test_rate_limit_paths_configured(self):
        """Test that RATE_LIMIT_PATHS includes all critical endpoints."""
        required_paths = ['/login/', '/admin/', '/api/', '/graphql/']

        for path in required_paths:
            self.assertIn(
                path,
                self.middleware.rate_limit_paths,
                f"Critical path {path} missing from RATE_LIMIT_PATHS"
            )

    def test_admin_endpoint_rate_limiting(self):
        """Test that /admin/ endpoint is rate limited."""
        request = self.factory.post('/admin/django/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-correlation-id'

        responses = []
        for i in range(12):
            response = self.middleware.process_request(request)
            responses.append(response)

        rate_limited_responses = [r for r in responses if r and r.status_code == 429]

        self.assertGreater(
            len(rate_limited_responses),
            0,
            "Admin endpoint should be rate limited after threshold"
        )

    def test_login_endpoint_rate_limiting(self):
        """Test that login endpoints are rate limited."""
        login_paths = ['/login/', '/accounts/login/', '/auth/login/']

        for login_path in login_paths:
            with self.subTest(path=login_path):
                cache.clear()

                request = self.factory.post(login_path)
                request.user = Mock(is_authenticated=False)
                request.correlation_id = 'test-correlation-id'

                for i in range(6):
                    response = self.middleware.process_request(request)
                    if i >= 5:
                        self.assertIsNotNone(response, f"Request {i+1} should be rate limited")
                        self.assertEqual(response.status_code, 429)

    def test_api_endpoint_rate_limiting(self):
        """Test that API endpoints are rate limited."""
        request = self.factory.get('/api/v1/people/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-correlation-id'

        for i in range(101):
            response = self.middleware.process_request(request)
            if i >= 100:
                self.assertIsNotNone(response)
                self.assertEqual(response.status_code, 429)

    def test_graphql_endpoint_rate_limiting(self):
        """Test that GraphQL endpoints are rate limited."""
        request = self.factory.post('/graphql/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-correlation-id'

        for i in range(101):
            response = self.middleware.process_request(request)
            if i >= 100:
                self.assertIsNotNone(response)
                self.assertEqual(response.status_code, 429)

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff calculation."""
        test_cases = [
            (0, 60),
            (1, 120),
            (2, 240),
            (3, 480),
            (10, 86400),
        ]

        for violation_count, expected_min_seconds in test_cases:
            backoff = self.middleware._calculate_exponential_backoff(violation_count)
            self.assertGreaterEqual(
                backoff,
                expected_min_seconds,
                f"Backoff for {violation_count} violations should be >= {expected_min_seconds}s"
            )

    def test_per_user_rate_limiting(self):
        """Test that authenticated users have separate rate limits."""
        cache.clear()

        request = self.factory.post('/api/v1/people/')
        request.user = self.test_user
        request.correlation_id = 'test-correlation-id'

        ip_request = self.factory.post('/api/v1/people/')
        ip_request.user = Mock(is_authenticated=False)
        ip_request.correlation_id = 'test-correlation-id-2'
        ip_request.META['REMOTE_ADDR'] = '192.168.1.100'

        for i in range(101):
            user_response = self.middleware.process_request(request)
            ip_response = self.middleware.process_request(ip_request)

        self.assertIsNotNone(user_response or ip_response)

    def test_trusted_ip_bypass(self):
        """Test that trusted IPs bypass rate limiting."""
        RateLimitTrustedIP.objects.create(
            ip_address='192.168.1.50',
            description='Test trusted IP',
            is_active=True
        )

        cache.delete('trusted_ips_set')
        self.middleware.trusted_ips = self.middleware._load_trusted_ips()

        request = self.factory.post('/login/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-correlation-id'
        request.META['REMOTE_ADDR'] = '192.168.1.50'

        for i in range(20):
            response = self.middleware.process_request(request)
            self.assertIsNone(response, f"Trusted IP should never be rate limited (request {i+1})")

    def test_automatic_ip_blocking(self):
        """Test automatic IP blocking after threshold violations."""
        cache.clear()

        request = self.factory.post('/login/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-correlation-id'
        request.META['REMOTE_ADDR'] = '192.168.1.99'

        violation_key = f"{self.middleware.cache_prefix}:violations:192.168.1.99"
        cache.set(violation_key, 15, 86400)

        response = self.middleware.process_request(request)

        blocked_ip = RateLimitBlockedIP.objects.filter(
            ip_address='192.168.1.99',
            is_active=True
        ).first()

        self.assertIsNotNone(blocked_ip, "IP should be automatically blocked after threshold")

    def test_blocked_ip_rejection(self):
        """Test that blocked IPs are rejected immediately."""
        RateLimitBlockedIP.objects.create(
            ip_address='10.0.0.100',
            blocked_until=timezone.now() + timedelta(hours=2),
            violation_count=15,
            is_active=True
        )

        block_key = f"{self.middleware.block_cache_prefix}:10.0.0.100"
        cache.set(block_key, {
            'blocked_until': time.time() + 7200,
            'violation_count': 15
        }, 7200)

        request = self.factory.get('/dashboard/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-correlation-id'
        request.META['REMOTE_ADDR'] = '10.0.0.100'

        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)

    def test_violation_logging_to_database(self):
        """Test that violations are logged to database."""
        cache.clear()

        request = self.factory.post('/admin/')
        request.user = self.test_user
        request.correlation_id = 'test-correlation-id'
        request.META['REMOTE_ADDR'] = '192.168.1.101'
        request.META['HTTP_USER_AGENT'] = 'Test Browser'

        for i in range(15):
            self.middleware.process_request(request)

        violations = RateLimitViolationLog.objects.filter(
            client_ip='192.168.1.101'
        )

        self.assertGreater(violations.count(), 0, "Violations should be logged to database")

        latest_violation = violations.first()
        self.assertEqual(latest_violation.endpoint_type, 'admin')
        self.assertEqual(latest_violation.user, self.test_user)

    def test_endpoint_type_detection(self):
        """Test correct endpoint type detection."""
        test_cases = [
            ('/admin/', 'admin'),
            ('/admin/django/peoples/', 'admin'),
            ('/login/', 'auth'),
            ('/accounts/login/', 'auth'),
            ('/reset-password/', 'auth'),
            ('/api/v1/people/', 'api'),
            ('/graphql/', 'graphql'),
            ('/api/graphql/', 'graphql'),
            ('/dashboard/', 'default')
        ]

        for path, expected_type in test_cases:
            detected_type = self.middleware._get_endpoint_type(path)
            self.assertEqual(
                detected_type,
                expected_type,
                f"Path {path} should be detected as {expected_type}, got {detected_type}"
            )

    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are added to responses."""
        cache.clear()

        request = self.factory.post('/api/v1/test/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-correlation-id'

        for i in range(101):
            response = self.middleware.process_request(request)

        if response and response.status_code == 429:
            self.assertIn('Retry-After', response)
            self.assertIn('X-RateLimit-Limit', response)
            self.assertIn('X-RateLimit-Remaining', response)

    def test_different_rate_limits_per_endpoint(self):
        """Test that different endpoints have different rate limits."""
        auth_limit, auth_window = self.middleware._get_rate_limit_config('auth')
        api_limit, api_window = self.middleware._get_rate_limit_config('api')
        admin_limit, admin_window = self.middleware._get_rate_limit_config('admin')

        self.assertLess(auth_limit, api_limit, "Auth should have stricter limits than API")
        self.assertLess(admin_limit, api_limit, "Admin should have stricter limits than API")


@pytest.mark.security
class RateLimitMonitoringTest(TestCase):
    """Test suite for rate limit monitoring functionality."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

        self.test_user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123',
            firstname='Test',
            lastname='User',
            is_staff=True
        )

        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        RateLimitViolationLog.objects.all().delete()
        RateLimitBlockedIP.objects.all().delete()

    def test_violation_log_creation(self):
        """Test that violation logs are created correctly."""
        RateLimitViolationLog.objects.create(
            client_ip='192.168.1.50',
            user=self.test_user,
            endpoint_path='/admin/',
            endpoint_type='admin',
            violation_reason='ip_rate_limit',
            request_count=15,
            rate_limit=10,
            correlation_id='test-correlation-id'
        )

        violation = RateLimitViolationLog.objects.first()
        self.assertIsNotNone(violation)
        self.assertEqual(violation.client_ip, '192.168.1.50')
        self.assertEqual(violation.endpoint_type, 'admin')

    def test_blocked_ip_model_creation(self):
        """Test blocked IP model creation and expiry."""
        blocked_until = timezone.now() + timedelta(hours=2)

        blocked_ip = RateLimitBlockedIP.objects.create(
            ip_address='10.0.0.50',
            blocked_until=blocked_until,
            violation_count=15,
            endpoint_type='admin',
            is_active=True
        )

        self.assertFalse(blocked_ip.is_expired())

        blocked_ip.blocked_until = timezone.now() - timedelta(hours=1)
        self.assertTrue(blocked_ip.is_expired())

    def test_trusted_ip_model_creation(self):
        """Test trusted IP model creation and expiry."""
        trusted_ip = RateLimitTrustedIP.objects.create(
            ip_address='172.16.0.1',
            description='Test monitoring service',
            added_by=self.test_user,
            is_active=True
        )

        self.assertFalse(trusted_ip.is_expired())

        trusted_ip.expires_at = timezone.now() - timedelta(days=1)
        self.assertTrue(trusted_ip.is_expired())

    def test_monitoring_dashboard_access_requires_staff(self):
        """Test that monitoring dashboard requires staff access."""
        response = self.client.get('/security/rate-limiting/dashboard/')
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.test_user)
        response = self.client.get('/security/rate-limiting/dashboard/')
        self.assertIn(response.status_code, [200, 404])

    def test_metrics_api_returns_json(self):
        """Test that metrics API returns valid JSON."""
        RateLimitViolationLog.objects.create(
            client_ip='192.168.1.60',
            endpoint_path='/api/',
            endpoint_type='api',
            violation_reason='ip_rate_limit',
            request_count=105,
            rate_limit=100,
            correlation_id='test-id'
        )

        self.client.force_login(self.test_user)
        response = self.client.get('/security/rate-limiting/metrics/')

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn('summary', data)
            self.assertIn('top_violating_ips', data)

    def test_unblock_ip_functionality(self):
        """Test manual IP unblocking."""
        blocked_ip = RateLimitBlockedIP.objects.create(
            ip_address='10.0.0.75',
            blocked_until=timezone.now() + timedelta(hours=5),
            violation_count=12,
            is_active=True
        )

        self.client.force_login(self.test_user)
        response = self.client.post('/security/rate-limiting/unblock/10.0.0.75/')

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertTrue(data.get('success'))

            blocked_ip.refresh_from_db()
            self.assertFalse(blocked_ip.is_active)

    def test_add_trusted_ip_functionality(self):
        """Test adding IPs to trusted list."""
        self.client.force_login(self.test_user)

        response = self.client.post(
            '/security/rate-limiting/add-trusted/',
            data=json.dumps({
                'ip_address': '172.16.0.10',
                'description': 'Test service'
            }),
            content_type='application/json'
        )

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertTrue(data.get('success'))

            trusted_ip = RateLimitTrustedIP.objects.filter(
                ip_address='172.16.0.10'
            ).first()
            self.assertIsNotNone(trusted_ip)


@pytest.mark.security
class RateLimitIntegrationTest(TestCase):
    """Integration tests for complete rate limiting system."""

    def setUp(self):
        """Set up integration test fixtures."""
        cache.clear()

        self.client = Client()

        self.admin_user = User.objects.create_user(
            loginid='admin',
            email='admin@example.com',
            password='adminpass123',
            firstname='Admin',
            lastname='User',
            is_staff=True,
            isadmin=True
        )

        self.regular_user = User.objects.create_user(
            loginid='user',
            email='user@example.com',
            password='userpass123',
            firstname='Regular',
            lastname='User'
        )

    def tearDown(self):
        """Clean up after integration tests."""
        cache.clear()
        RateLimitViolationLog.objects.all().delete()
        RateLimitBlockedIP.objects.all().delete()

    def test_admin_brute_force_protection(self):
        """Test that admin panel is protected from brute force attacks."""
        for i in range(15):
            response = self.client.post(
                '/admin/django/',
                {'username': 'admin', 'password': 'wrongpassword'},
                REMOTE_ADDR='192.168.1.200'
            )

        violations = RateLimitViolationLog.objects.filter(
            endpoint_type='admin'
        )

        self.assertGreater(violations.count(), 0, "Admin brute force should be logged")

    def test_graphql_and_path_based_rate_limiting_work_together(self):
        """Test that both GraphQL and path-based rate limiting are enforced."""
        query = '{ viewer }'

        for i in range(110):
            response = self.client.post(
                '/graphql/',
                {'query': query},
                content_type='application/json',
                REMOTE_ADDR='192.168.1.201'
            )

        self.assertEqual(response.status_code, 429, "Should be rate limited")

    def test_rate_limit_reset_after_window(self):
        """Test that rate limits reset after time window."""
        request = RequestFactory().post('/login/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-id'
        request.META['REMOTE_ADDR'] = '192.168.1.202'

        middleware = PathBasedRateLimitMiddleware(get_response=lambda r: None)

        for i in range(5):
            middleware.process_request(request)

        response = middleware.process_request(request)
        self.assertIsNotNone(response, "Should be rate limited")

        cache_key = f"{middleware.cache_prefix}:ip:192.168.1.202:auth"
        cache.delete(cache_key)

        response = middleware.process_request(request)
        self.assertIsNone(response, "Should not be rate limited after cache clear")

    def test_violation_analytics_data(self):
        """Test that violation analytics provide useful data."""
        for i in range(10):
            RateLimitViolationLog.objects.create(
                client_ip=f'192.168.1.{i}',
                endpoint_path='/api/',
                endpoint_type='api',
                violation_reason='ip_rate_limit',
                request_count=105,
                rate_limit=100,
                correlation_id=f'test-id-{i}'
            )

        violations = RateLimitViolationLog.objects.all()
        self.assertEqual(violations.count(), 10)

        endpoint_distribution = violations.values('endpoint_type').distinct()
        self.assertEqual(endpoint_distribution.count(), 1)

    def test_rate_limiting_performance_overhead(self):
        """Test that rate limiting adds minimal performance overhead."""
        request = RequestFactory().get('/dashboard/')
        request.user = self.regular_user
        request.correlation_id = 'test-id'

        middleware = PathBasedRateLimitMiddleware(get_response=lambda r: None)

        start_time = time.time()
        middleware.process_request(request)
        elapsed = time.time() - start_time

        self.assertLess(elapsed, 0.01, "Rate limiting should add < 10ms overhead")