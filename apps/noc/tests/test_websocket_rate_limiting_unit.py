"""
Unit Tests for WebSocket Per-User Rate Limiting

Tests the Redis-backed per-user rate limiting implementation
without requiring full database setup. Uses mocks for async/cache operations.

CRITICAL SECURITY: Validates that rate limiting is per-user, not per-connection.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from django.core.cache import cache
from apps.noc.consumers.noc_dashboard_consumer import NOCDashboardConsumer


# ============================================================================
# UNIT TESTS: Rate Limiting Logic
# ============================================================================

class TestRateLimitingLogic:
    """Unit tests for rate limiting implementation."""

    @pytest.mark.asyncio
    async def test_first_message_increments_cache(self):
        """Test that first message increments cache counter."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=123)

        # Mock cache operations
        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            mock_cache.incr.return_value = 1
            mock_cache.expire.return_value = None

            # First message should be allowed
            result = await consumer._check_rate_limit()

            assert result is True
            mock_cache.incr.assert_called_once_with('websocket:rate:123')
            mock_cache.expire.assert_called_once_with('websocket:rate:123', 60)

    @pytest.mark.asyncio
    async def test_below_limit_allowed(self):
        """Test that messages below limit are allowed."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=456)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # Second message (count = 2)
            mock_cache.incr.return_value = 2
            mock_cache.expire.return_value = None

            result = await consumer._check_rate_limit()

            assert result is True
            assert mock_cache.incr.called

    @pytest.mark.asyncio
    async def test_at_limit_allowed(self):
        """Test that message at exact limit is allowed."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=789)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # 100th message (at RATE_LIMIT_MAX)
            mock_cache.incr.return_value = 100
            mock_cache.expire.return_value = None

            result = await consumer._check_rate_limit()

            assert result is True

    @pytest.mark.asyncio
    async def test_exceeds_limit_blocked(self):
        """Test that message exceeding limit is blocked."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=999)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # 101st message (exceeds RATE_LIMIT_MAX)
            mock_cache.incr.return_value = 101
            mock_cache.expire.return_value = None

            result = await consumer._check_rate_limit()

            assert result is False

    @pytest.mark.asyncio
    async def test_cache_failure_fails_open(self):
        """Test that cache failure fails open (allows request)."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=111)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # Simulate cache unavailable
            mock_cache.incr.side_effect = Exception("Redis connection lost")

            result = await consumer._check_rate_limit()

            # Should fail open (return True) to prevent blocking users
            assert result is True

    @pytest.mark.asyncio
    async def test_per_user_isolation(self):
        """Test that different users have separate counters."""
        consumer1 = NOCDashboardConsumer()
        consumer1.user = MagicMock(id=111)

        consumer2 = NOCDashboardConsumer()
        consumer2.user = MagicMock(id=222)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # User 1 at limit
            mock_cache.incr.return_value = 100
            result1 = await consumer1._check_rate_limit()
            assert result1 is True

            # User 2 at low count
            mock_cache.incr.return_value = 50
            result2 = await consumer2._check_rate_limit()
            assert result2 is True

            # Verify different cache keys were used
            calls = [call[0][0] for call in mock_cache.incr.call_args_list]
            assert 'websocket:rate:111' in calls
            assert 'websocket:rate:222' in calls

    @pytest.mark.asyncio
    async def test_expiry_set_only_on_first_message(self):
        """Test that cache expiry is set only on first message."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=333)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # First message (count = 1)
            mock_cache.incr.return_value = 1
            await consumer._check_rate_limit()

            # Expiry should be set
            assert mock_cache.expire.called

            # Reset mock
            mock_cache.reset_mock()

            # Second message (count = 2)
            mock_cache.incr.return_value = 2
            await consumer._check_rate_limit()

            # Expiry should NOT be set on subsequent messages
            assert not mock_cache.expire.called


# ============================================================================
# INTEGRATION TESTS: Cache Key Format
# ============================================================================

class TestCacheKeyFormat:
    """Test cache key naming convention."""

    @pytest.mark.asyncio
    async def test_cache_key_format(self):
        """Test that cache key follows websocket:rate:{user_id} format."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=12345)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            mock_cache.incr.return_value = 1

            await consumer._check_rate_limit()

            # Verify cache key format
            expected_key = 'websocket:rate:12345'
            mock_cache.incr.assert_called_with(expected_key)

    @pytest.mark.asyncio
    async def test_window_constant_used(self):
        """Test that RATE_LIMIT_WINDOW constant is used for expiry."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=444)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            mock_cache.incr.return_value = 1

            await consumer._check_rate_limit()

            # Verify correct TTL (RATE_LIMIT_WINDOW = 60)
            mock_cache.expire.assert_called_once()
            call_args = mock_cache.expire.call_args[0]
            assert call_args[1] == 60  # RATE_LIMIT_WINDOW

    @pytest.mark.asyncio
    async def test_max_constant_enforced(self):
        """Test that RATE_LIMIT_MAX constant is enforced."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=555)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # Message at limit + 1
            mock_cache.incr.return_value = consumer.RATE_LIMIT_MAX + 1

            result = await consumer._check_rate_limit()

            assert result is False
            assert consumer.RATE_LIMIT_MAX == 100  # Verify constant value


# ============================================================================
# TESTS: Security Scenarios
# ============================================================================

class TestSecurityScenarios:
    """Test security-critical scenarios."""

    @pytest.mark.asyncio
    async def test_no_per_connection_state(self):
        """
        Test that rate limiting doesn't use per-connection state.

        Multiple consumer instances for same user should share limit.
        """
        # Simulate multiple connections from same user
        consumer1 = NOCDashboardConsumer()
        consumer1.user = MagicMock(id=666)

        consumer2 = NOCDashboardConsumer()
        consumer2.user = MagicMock(id=666)  # Same user

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            # Both consumers should use same cache key
            mock_cache.incr.side_effect = [1, 2, 3]

            await consumer1._check_rate_limit()
            await consumer2._check_rate_limit()

            # Verify both used same cache key
            calls = mock_cache.incr.call_args_list
            assert calls[0][0][0] == calls[1][0][0]
            assert 'websocket:rate:666' in calls[0][0][0]

    @pytest.mark.asyncio
    async def test_redis_atomic_increment_critical(self):
        """Test that atomic cache.incr() is used, not get/set."""
        consumer = NOCDashboardConsumer()
        consumer.user = MagicMock(id=777)

        with patch('apps.noc.consumers.noc_dashboard_consumer.cache') as mock_cache:
            mock_cache.incr.return_value = 50

            await consumer._check_rate_limit()

            # Must use cache.incr(), not get() then set()
            assert mock_cache.incr.called
            assert not mock_cache.get.called
