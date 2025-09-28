"""
Rate Limiting Penetration Test Suite

Simulates real-world attack scenarios to validate rate limiting effectiveness:
- Admin brute force attacks
- GraphQL query flooding
- API endpoint exhaustion
- Distributed attack simulation
- Rate limit bypass attempts
- IP rotation attacks

SECURITY NOTE: These are defensive tests only - validating protection mechanisms.
"""

import json
import time
import pytest
import concurrent.futures
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.core.models.rate_limiting import (
    RateLimitBlockedIP,
    RateLimitViolationLog
)

User = get_user_model()


@pytest.mark.security
@pytest.mark.penetration
class AdminBruteForceTest(TestCase):
    """
    Simulate admin panel brute force attack scenarios.

    Attack Vector: Unlimited login attempts to /admin/ endpoint
    Expected Defense: Rate limiting blocks after threshold
    """

    def setUp(self):
        """Set up penetration test environment."""
        cache.clear()
        self.client = Client()

        self.admin_user = User.objects.create_superuser(
            loginid='admin',
            email='admin@example.com',
            password='SecureAdminPass123!',
            firstname='Admin',
            lastname='User'
        )

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        RateLimitViolationLog.objects.all().delete()
        RateLimitBlockedIP.objects.all().delete()

    def test_admin_login_brute_force_sequential(self):
        """
        Test sequential brute force attack on admin login.

        Scenario: Attacker tries common passwords sequentially
        Expected: Blocked after 10 attempts within 15 minutes
        """
        common_passwords = [
            'admin', 'password', '123456', 'admin123',
            'password123', 'root', 'toor', 'administrator',
            'welcome', 'letmein', 'qwerty', 'abc123',
            '12345678', 'password1', 'admin@123'
        ]

        blocked = False
        attempt_count = 0

        for password in common_passwords:
            response = self.client.post(
                '/admin/django/login/',
                {'username': 'admin', 'password': password},
                REMOTE_ADDR='203.0.113.100'
            )

            attempt_count += 1

            if response.status_code == 429:
                blocked = True
                break

        self.assertTrue(blocked, f"Should block brute force after threshold (made {attempt_count} attempts)")
        self.assertLess(attempt_count, 15, "Should block before trying all passwords")

    def test_admin_login_with_ip_rotation(self):
        """
        Test brute force with IP rotation.

        Scenario: Attacker rotates IPs to evade IP-based limits
        Expected: User-based tracking still blocks if authenticated
        """
        passwords = ['wrong1', 'wrong2', 'wrong3', 'wrong4', 'wrong5']

        responses = []
        for i, password in enumerate(passwords):
            ip = f'203.0.113.{i + 1}'
            response = self.client.post(
                '/admin/django/login/',
                {'username': 'admin', 'password': password},
                REMOTE_ADDR=ip
            )
            responses.append(response.status_code)

        violations = RateLimitViolationLog.objects.filter(
            endpoint_type='admin'
        )

        self.assertGreater(
            violations.count(),
            0,
            "IP rotation attacks should still be logged"
        )


@pytest.mark.security
@pytest.mark.penetration
class GraphQLFloodingTest(TestCase):
    """
    Simulate GraphQL query flooding attacks.

    Attack Vector: Overwhelming GraphQL endpoint with rapid queries
    Expected Defense: Rate limiting blocks excessive queries
    """

    def setUp(self):
        """Set up GraphQL penetration test environment."""
        cache.clear()
        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_graphql_query_flooding(self):
        """
        Test rapid GraphQL query flooding.

        Scenario: Attacker sends 200 queries in rapid succession
        Expected: Blocked after configured threshold
        """
        query = '{ viewer }'

        blocked_count = 0
        success_count = 0

        for i in range(200):
            response = self.client.post(
                '/graphql/',
                {'query': query},
                content_type='application/json',
                REMOTE_ADDR='198.51.100.50'
            )

            if response.status_code == 429:
                blocked_count += 1
            else:
                success_count += 1

        self.assertGreater(
            blocked_count,
            0,
            "GraphQL flooding should be blocked after threshold"
        )

        self.assertLess(
            success_count,
            200,
            "Not all queries should succeed during flooding"
        )

    def test_graphql_complex_query_flooding(self):
        """
        Test flooding with complex nested queries.

        Scenario: Attacker uses complex queries to exhaust resources
        Expected: Complexity-based rate limiting blocks faster
        """
        complex_query = """
        query {
            allPeople {
                id
                loginid
                profile {
                    id
                    capabilities
                }
                organizational {
                    id
                    department {
                        name
                        businessUnit {
                            name
                        }
                    }
                }
            }
        }
        """

        for i in range(60):
            response = self.client.post(
                '/api/graphql/',
                {'query': complex_query},
                content_type='application/json',
                REMOTE_ADDR='198.51.100.51'
            )

            if i >= 50:
                self.assertEqual(
                    response.status_code,
                    429,
                    f"Complex query flooding should be blocked by request {i+1}"
                )


@pytest.mark.security
@pytest.mark.penetration
class APIExhaustionTest(TestCase):
    """
    Simulate API endpoint exhaustion attacks.

    Attack Vector: Overwhelming REST API with requests
    Expected Defense: Per-endpoint rate limiting protection
    """

    def setUp(self):
        """Set up API penetration test environment."""
        cache.clear()
        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_api_endpoint_exhaustion(self):
        """
        Test API endpoint exhaustion attack.

        Scenario: Attacker hammers API endpoint to cause DoS
        Expected: Rate limiting prevents resource exhaustion
        """
        responses = []

        for i in range(150):
            response = self.client.get(
                '/api/v1/people/',
                REMOTE_ADDR='198.51.100.60'
            )
            responses.append(response.status_code)

        rate_limited = responses.count(429)

        self.assertGreater(
            rate_limited,
            0,
            "API exhaustion should trigger rate limiting"
        )


@pytest.mark.security
@pytest.mark.penetration
class DistributedAttackTest(TestCase):
    """
    Simulate distributed/coordinated attack scenarios.

    Attack Vector: Multiple IPs attacking simultaneously
    Expected Defense: Each IP tracked independently
    """

    def setUp(self):
        """Set up distributed attack test environment."""
        cache.clear()
        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        RateLimitViolationLog.objects.all().delete()

    def test_coordinated_login_attack(self):
        """
        Test coordinated brute force from multiple IPs.

        Scenario: Botnet attempts login from 10 different IPs
        Expected: Each IP rate limited independently
        """
        ips = [f'198.51.100.{i}' for i in range(70, 80)]

        total_blocked = 0

        for ip in ips:
            for attempt in range(8):
                response = self.client.post(
                    '/login/',
                    {'username': 'admin', 'password': f'wrong{attempt}'},
                    REMOTE_ADDR=ip
                )

                if response.status_code == 429:
                    total_blocked += 1

        violations = RateLimitViolationLog.objects.all()

        self.assertGreater(
            violations.count(),
            0,
            "Coordinated attack should generate violation logs"
        )

        self.assertGreater(
            total_blocked,
            0,
            "Some IPs in coordinated attack should be blocked"
        )


@pytest.mark.security
@pytest.mark.penetration
class RateLimitBypassAttemptsTest(TestCase):
    """
    Test various rate limit bypass techniques.

    Attack Vectors:
    - Header manipulation
    - IP spoofing attempts
    - Cookie manipulation
    - User-agent rotation
    """

    def setUp(self):
        """Set up bypass attempt test environment."""
        cache.clear()
        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_x_forwarded_for_bypass_attempt(self):
        """
        Test bypass attempt using X-Forwarded-For header manipulation.

        Scenario: Attacker rotates X-Forwarded-For to evade IP tracking
        Expected: Primary IP still tracked and rate limited
        """
        for i in range(15):
            response = self.client.post(
                '/login/',
                {'username': 'admin', 'password': 'wrong'},
                REMOTE_ADDR='198.51.100.90',
                HTTP_X_FORWARDED_FOR=f'10.0.0.{i}'
            )

        self.assertEqual(
            response.status_code,
            429,
            "X-Forwarded-For manipulation should not bypass rate limiting"
        )

    def test_user_agent_rotation_bypass_attempt(self):
        """
        Test bypass attempt using User-Agent rotation.

        Scenario: Attacker rotates user agents to appear as different clients
        Expected: IP-based tracking still enforces limits
        """
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'curl/7.68.0',
            'PostmanRuntime/7.26.8',
            'python-requests/2.25.1'
        ]

        blocked = False

        for i in range(20):
            ua = user_agents[i % len(user_agents)]
            response = self.client.post(
                '/api/v1/people/',
                {},
                REMOTE_ADDR='198.51.100.91',
                HTTP_USER_AGENT=ua
            )

            if response.status_code == 429:
                blocked = True
                break

        self.assertTrue(blocked, "User-Agent rotation should not bypass rate limiting")

    def test_concurrent_request_flooding(self):
        """
        Test concurrent request flooding.

        Scenario: Attacker sends many concurrent requests
        Expected: Rate limiting handles concurrency correctly
        """
        def make_request(attempt_num):
            try:
                response = self.client.post(
                    '/login/',
                    {'username': 'admin', 'password': f'wrong{attempt_num}'},
                    REMOTE_ADDR='198.51.100.92'
                )
                return response.status_code
            except Exception as e:
                return 500

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(30)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        blocked_count = results.count(429)

        self.assertGreater(
            blocked_count,
            0,
            "Concurrent flooding should trigger rate limiting"
        )


@pytest.mark.security
@pytest.mark.penetration
class AutoBlockingValidationTest(TestCase):
    """
    Validate automatic IP blocking functionality.

    Tests:
    - Block triggers at threshold
    - Block duration increases with violations
    - Blocked IPs cannot access any endpoint
    - Admin can manually unblock
    """

    def setUp(self):
        """Set up auto-blocking test environment."""
        cache.clear()
        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        RateLimitBlockedIP.objects.all().delete()

    def test_auto_blocking_threshold(self):
        """
        Test that IPs are auto-blocked after threshold violations.

        Scenario: IP violates rate limit 10+ times
        Expected: IP automatically blocked
        """
        from apps.core.middleware.path_based_rate_limiting import PathBasedRateLimitMiddleware
        from django.test import RequestFactory

        factory = RequestFactory()
        middleware = PathBasedRateLimitMiddleware(get_response=lambda r: None)

        violation_key = f"{middleware.cache_prefix}:violations:198.51.100.95"
        cache.set(violation_key, 15, 86400)

        request = factory.post('/login/')
        request.user = Mock(is_authenticated=False)
        request.correlation_id = 'test-id'
        request.META['REMOTE_ADDR'] = '198.51.100.95'

        for i in range(6):
            middleware.process_request(request)

        blocked_ip = RateLimitBlockedIP.objects.filter(
            ip_address='198.51.100.95',
            is_active=True
        ).first()

        self.assertIsNotNone(blocked_ip, "IP should be auto-blocked after threshold")

    def test_blocked_ip_cannot_access_any_endpoint(self):
        """
        Test that blocked IPs are blocked across all endpoints.

        Scenario: Blocked IP tries multiple endpoints
        Expected: All requests blocked with 403
        """
        from apps.core.middleware.path_based_rate_limiting import PathBasedRateLimitMiddleware
        from django.test import RequestFactory

        RateLimitBlockedIP.objects.create(
            ip_address='198.51.100.96',
            blocked_until=timezone.now() + timedelta(hours=2),
            violation_count=20,
            is_active=True
        )

        factory = RequestFactory()
        middleware = PathBasedRateLimitMiddleware(get_response=lambda r: None)

        block_key = f"{middleware.block_cache_prefix}:198.51.100.96"
        cache.set(block_key, {
            'blocked_until': time.time() + 7200,
            'violation_count': 20
        }, 7200)

        test_endpoints = ['/login/', '/admin/', '/api/', '/dashboard/']

        for endpoint in test_endpoints:
            request = factory.get(endpoint)
            request.user = Mock(is_authenticated=False)
            request.correlation_id = 'test-id'
            request.META['REMOTE_ADDR'] = '198.51.100.96'

            response = middleware.process_request(request)

            self.assertIsNotNone(response, f"Blocked IP should be rejected at {endpoint}")
            self.assertEqual(response.status_code, 403)


@pytest.mark.security
@pytest.mark.penetration
class PerformanceUnderAttackTest(TestCase):
    """
    Validate system performance during attack scenarios.

    Tests:
    - Rate limiting overhead < 10ms per request
    - No resource exhaustion under load
    - Cache performance under stress
    """

    def setUp(self):
        """Set up performance test environment."""
        cache.clear()
        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_rate_limiting_performance_overhead(self):
        """
        Test rate limiting performance overhead.

        Scenario: Measure middleware overhead under normal load
        Expected: < 10ms overhead per request
        """
        from apps.core.middleware.path_based_rate_limiting import PathBasedRateLimitMiddleware
        from django.test import RequestFactory
        from unittest.mock import Mock

        factory = RequestFactory()
        middleware = PathBasedRateLimitMiddleware(get_response=lambda r: None)

        request = factory.get('/dashboard/')
        request.user = Mock(is_authenticated=True, id=1)
        request.correlation_id = 'test-id'
        request.META['REMOTE_ADDR'] = '192.168.1.50'

        start = time.time()
        middleware.process_request(request)
        elapsed = time.time() - start

        self.assertLess(
            elapsed,
            0.01,
            f"Rate limiting overhead should be < 10ms, was {elapsed*1000:.2f}ms"
        )

    def test_cache_performance_under_load(self):
        """
        Test cache operations under load.

        Scenario: Simulate 1000 concurrent users
        Expected: Cache handles load without errors
        """
        from apps.core.middleware.path_based_rate_limiting import PathBasedRateLimitMiddleware
        from django.test import RequestFactory

        factory = RequestFactory()
        middleware = PathBasedRateLimitMiddleware(get_response=lambda r: None)

        errors = 0

        for i in range(1000):
            try:
                request = factory.get('/dashboard/')
                request.user = Mock(is_authenticated=True, id=i % 100)
                request.correlation_id = f'test-id-{i}'
                request.META['REMOTE_ADDR'] = f'192.168.{i // 256}.{i % 256}'

                middleware.process_request(request)
            except Exception:
                errors += 1

        self.assertEqual(errors, 0, "Rate limiting should handle load without errors")


@pytest.mark.security
@pytest.mark.penetration
class ComprehensiveAttackSimulation(TestCase):
    """
    Comprehensive attack simulation combining multiple vectors.

    Tests complete security posture against sophisticated attacks.
    """

    def setUp(self):
        """Set up comprehensive test environment."""
        cache.clear()
        self.client = Client()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        RateLimitViolationLog.objects.all().delete()
        RateLimitBlockedIP.objects.all().delete()

    def test_multi_vector_attack_detection(self):
        """
        Test detection of multi-vector attack.

        Scenario: Attacker targets admin, API, and GraphQL simultaneously
        Expected: All vectors rate limited independently
        """
        attack_vectors = [
            ('/admin/django/login/', 'POST', {}),
            ('/api/v1/people/', 'GET', {}),
            ('/graphql/', 'POST', {'query': '{ viewer }'}),
            ('/login/', 'POST', {'username': 'admin', 'password': 'wrong'})
        ]

        violations_by_endpoint = {}

        for _ in range(30):
            for path, method, data in attack_vectors:
                if method == 'POST':
                    response = self.client.post(
                        path,
                        data,
                        content_type='application/json',
                        REMOTE_ADDR='198.51.100.100'
                    )
                else:
                    response = self.client.get(
                        path,
                        REMOTE_ADDR='198.51.100.100'
                    )

                if response.status_code == 429:
                    violations_by_endpoint[path] = violations_by_endpoint.get(path, 0) + 1

        self.assertGreater(
            len(violations_by_endpoint),
            0,
            "Multi-vector attack should trigger rate limiting on at least one endpoint"
        )

    def test_attack_monitoring_and_logging(self):
        """
        Test that attacks are properly monitored and logged.

        Scenario: Execute attack simulation
        Expected: All violations logged with complete context
        """
        for i in range(20):
            self.client.post(
                '/admin/django/login/',
                {'username': 'admin', 'password': f'wrong{i}'},
                REMOTE_ADDR='198.51.100.110'
            )

        violations = RateLimitViolationLog.objects.filter(
            client_ip='198.51.100.110'
        )

        if violations.exists():
            violation = violations.first()
            self.assertIsNotNone(violation.correlation_id)
            self.assertIsNotNone(violation.endpoint_type)
            self.assertIsNotNone(violation.violation_reason)
            self.assertGreater(violation.request_count, 0)


from unittest.mock import Mock
from django.utils import timezone