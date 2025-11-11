"""
Tests for Journal Security Middleware.

Focuses on:
- Redis-based rate limiting (Nov 2025 security fix)
- Cross-worker enforcement
- Sliding window behavior
- Graceful degradation
- Tenant isolation
- Privacy violation detection
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError

from apps.journal.middleware import JournalSecurityMiddleware

User = get_user_model()


class TestJournalRateLimitingRedis(TestCase):
    """
    Test Redis-based rate limiting.

    Critical security fix (Nov 2025): Rate limiting moved from in-memory dict
    to Redis sorted sets to enable cross-worker enforcement.
    """

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()
        self.middleware = JournalSecurityMiddleware(lambda r: Mock(status_code=200))

        # Create test user with tenant
        from apps.tenants.models import Tenant
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            tenant=self.tenant
        )

    def test_rate_limit_enforced_within_window(self):
        """Test rate limits enforced within time window."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        # Make requests up to the limit (20 requests per hour for analytics)
        for i in range(20):
            result = self.middleware._check_rate_limits(request, f'corr-{i}')
            self.assertTrue(
                result['allowed'],
                f"Request {i+1}/20 should be allowed"
            )

        # 21st request should be blocked
        result = self.middleware._check_rate_limits(request, 'corr-21')
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'rate_limit_exceeded')
        self.assertEqual(result['status_code'], 429)
        self.assertIn('retry_after', result)

    def test_rate_limit_sliding_window(self):
        """Test sliding window rate limiting behavior."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis.zadd = MagicMock()
        mock_redis.zremrangebyscore = MagicMock()
        mock_redis.zcard = MagicMock()
        mock_redis.expire = MagicMock()

        with patch('django.core.cache.cache.client.get_client', return_value=mock_redis):
            # First request at time 1000
            with patch('time.time', return_value=1000.0):
                mock_redis.zcard.return_value = 1
                result = self.middleware._check_rate_limits(request, 'corr-1')
                self.assertTrue(result['allowed'])

                # Verify old entries removed (outside 60-minute window)
                mock_redis.zremrangebyscore.assert_called_once()
                args = mock_redis.zremrangebyscore.call_args[0]
                self.assertEqual(args[0], f"journal_rate_limit:{self.user.id}:/api/v1/journal/analytics/")
                self.assertEqual(args[1], '-inf')
                self.assertAlmostEqual(args[2], 1000.0 - 3600, delta=1)  # 60 minutes ago

            # Simulate 61 minutes passing (outside window)
            with patch('time.time', return_value=1000.0 + 3660):  # 61 minutes
                mock_redis.zcard.return_value = 1  # Old request expired, only new one counts
                result = self.middleware._check_rate_limits(request, 'corr-2')
                self.assertTrue(result['allowed'])

    def test_rate_limit_different_endpoints_independent(self):
        """Test different endpoints have independent rate limits."""
        user = self.user

        # Make 20 requests to analytics endpoint
        analytics_request = self.factory.get('/api/v1/journal/analytics/')
        analytics_request.user = user

        for i in range(20):
            result = self.middleware._check_rate_limits(analytics_request, f'analytics-{i}')
            self.assertTrue(result['allowed'])

        # Should still be able to make requests to search endpoint (different limit)
        search_request = self.factory.get('/api/v1/journal/search/')
        search_request.user = user

        for i in range(50):  # Search has 50 requests/hour limit
            result = self.middleware._check_rate_limits(search_request, f'search-{i}')
            self.assertTrue(result['allowed'], f"Search request {i+1}/50 should be allowed")

    def test_rate_limit_key_includes_user_and_endpoint(self):
        """Test rate limit keys are scoped to user + endpoint."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        mock_redis = MagicMock()
        mock_redis.zadd = MagicMock()
        mock_redis.zremrangebyscore = MagicMock()
        mock_redis.zcard = MagicMock(return_value=1)
        mock_redis.expire = MagicMock()

        with patch('django.core.cache.cache.client.get_client', return_value=mock_redis):
            self.middleware._check_rate_limits(request, 'test-corr-id')

            # Verify correct Redis key format
            zadd_call = mock_redis.zadd.call_args
            redis_key = zadd_call[0][0]

            expected_key = f"journal_rate_limit:{self.user.id}:/api/v1/journal/analytics/"
            self.assertEqual(redis_key, expected_key)

    def test_redis_unavailable_graceful_degradation(self):
        """Test graceful degradation when Redis unavailable."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        # Mock Redis connection failure
        with patch('django.core.cache.cache.client.get_client') as mock_get_client:
            mock_get_client.side_effect = RedisConnectionError("Redis unavailable")

            result = self.middleware._check_rate_limits(request, 'corr-1')

            # Should allow request (fail-open mode)
            self.assertTrue(result['allowed'])

    def test_redis_error_during_zadd_graceful_degradation(self):
        """Test graceful degradation when Redis zadd fails."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        mock_redis = MagicMock()
        mock_redis.zadd.side_effect = RedisError("ZADD operation failed")

        with patch('django.core.cache.cache.client.get_client', return_value=mock_redis):
            result = self.middleware._check_rate_limits(request, 'corr-1')

            # Should allow request (fail-open mode)
            self.assertTrue(result['allowed'])

    def test_redis_expiry_set_on_rate_limit_key(self):
        """Test Redis key expiry set to window duration for cleanup."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        mock_redis = MagicMock()
        mock_redis.zadd = MagicMock()
        mock_redis.zremrangebyscore = MagicMock()
        mock_redis.zcard = MagicMock(return_value=1)
        mock_redis.expire = MagicMock()

        with patch('django.core.cache.cache.client.get_client', return_value=mock_redis):
            self.middleware._check_rate_limits(request, 'test-corr-id')

            # Verify expire was called with correct TTL
            mock_redis.expire.assert_called_once()
            args = mock_redis.expire.call_args[0]

            # TTL should be 60 minutes (3600 seconds) for analytics endpoint
            self.assertEqual(args[1], 3600)

    def test_rate_limit_uses_sorted_set_with_timestamps(self):
        """Test rate limiting uses Redis sorted sets with timestamps as scores."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        mock_redis = MagicMock()
        mock_redis.zadd = MagicMock()
        mock_redis.zremrangebyscore = MagicMock()
        mock_redis.zcard = MagicMock(return_value=1)
        mock_redis.expire = MagicMock()

        correlation_id = 'test-corr-123'

        with patch('django.core.cache.cache.client.get_client', return_value=mock_redis):
            with patch('time.time', return_value=1234567890.5):
                self.middleware._check_rate_limits(request, correlation_id)

                # Verify ZADD called with correlation_id as member, timestamp as score
                zadd_call = mock_redis.zadd.call_args
                zadd_dict = zadd_call[0][1]

                self.assertIn(correlation_id, zadd_dict)
                self.assertAlmostEqual(zadd_dict[correlation_id], 1234567890.5, delta=0.1)

    def test_no_rate_limit_for_non_configured_endpoints(self):
        """Test endpoints not in RATE_LIMITS don't get rate limited."""
        request = self.factory.get('/api/v1/journal/entries/')  # Not in RATE_LIMITS
        request.user = self.user

        # Make 1000 requests - should all be allowed
        for i in range(100):
            result = self.middleware._check_rate_limits(request, f'corr-{i}')
            self.assertTrue(result['allowed'])

    def test_rate_limit_logs_warning_on_exceeded(self):
        """Test rate limit exceeded logs warning with details."""
        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        # Exhaust rate limit
        for i in range(20):
            self.middleware._check_rate_limits(request, f'setup-{i}')

        # Next request should log warning
        with patch('apps.journal.middleware.logger') as mock_logger:
            result = self.middleware._check_rate_limits(request, 'test-corr')

            self.assertFalse(result['allowed'])

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            log_call = mock_logger.warning.call_args
            log_message = log_call[0][0]

            self.assertIn('Rate limit exceeded', log_message)
            self.assertIn(str(self.user.id), log_message)

    def test_rate_limit_multi_worker_simulation(self):
        """
        Simulate multi-worker scenario where different workers enforce same limits.

        This is the critical fix: in-memory dict didn't work across workers,
        Redis sorted sets do.
        """
        # Simulate Worker 1
        worker1_middleware = JournalSecurityMiddleware(lambda r: Mock(status_code=200))

        request1 = self.factory.get('/api/v1/journal/analytics/')
        request1.user = self.user

        # Worker 1 makes 10 requests
        for i in range(10):
            result = worker1_middleware._check_rate_limits(request1, f'worker1-{i}')
            self.assertTrue(result['allowed'])

        # Simulate Worker 2 (new middleware instance)
        worker2_middleware = JournalSecurityMiddleware(lambda r: Mock(status_code=200))

        request2 = self.factory.get('/api/v1/journal/analytics/')
        request2.user = self.user

        # Worker 2 makes 10 more requests (should see worker 1's requests via Redis)
        for i in range(10):
            result = worker2_middleware._check_rate_limits(request2, f'worker2-{i}')
            self.assertTrue(result['allowed'])

        # 21st request (across both workers) should be blocked
        result = worker2_middleware._check_rate_limits(request2, 'worker2-final')
        self.assertFalse(result['allowed'])

    def test_rate_limit_persists_through_middleware_restart(self):
        """Test rate limits persist when middleware restarts (simulating worker restart)."""
        # First middleware instance makes requests
        middleware1 = JournalSecurityMiddleware(lambda r: Mock(status_code=200))

        request = self.factory.get('/api/v1/journal/analytics/')
        request.user = self.user

        for i in range(15):
            result = middleware1._check_rate_limits(request, f'before-restart-{i}')
            self.assertTrue(result['allowed'])

        # Simulate worker restart - create new middleware instance
        del middleware1
        middleware2 = JournalSecurityMiddleware(lambda r: Mock(status_code=200))

        # New middleware should still see previous requests (via Redis)
        for i in range(5):
            result = middleware2._check_rate_limits(request, f'after-restart-{i}')
            self.assertTrue(result['allowed'])

        # 21st request should be blocked
        result = middleware2._check_rate_limits(request, 'after-restart-limit')
        self.assertFalse(result['allowed'])


class TestJournalMiddlewareStartup(TestCase):
    """Test middleware initialization and startup validation."""

    def test_middleware_initializes_without_rate_limit_storage(self):
        """Test middleware no longer creates in-memory rate limit storage."""
        middleware = JournalSecurityMiddleware(lambda r: Mock())

        # Should NOT have rate_limit_storage attribute (removed in Nov 2025 fix)
        self.assertFalse(hasattr(middleware, 'rate_limit_storage'))

    def test_middleware_comment_mentions_redis(self):
        """Test middleware __init__ comment references Redis."""
        import inspect
        source = inspect.getsource(JournalSecurityMiddleware.__init__)

        # Should mention Redis in comments
        self.assertIn('Redis', source)
