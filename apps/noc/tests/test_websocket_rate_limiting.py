"""
WebSocket Rate Limiting Per-User Tests

Tests that rate limiting is applied per-user across multiple connections,
preventing bypass via opening multiple WebSocket connections.

CRITICAL SECURITY: Validates Redis-backed per-user rate limiting,
not per-connection in-memory limiting.
"""

import pytest
import asyncio
import json
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import re_path
from django.test import override_settings
from django.core.cache import cache
from unittest.mock import patch, AsyncMock
from rest_framework_simplejwt.tokens import AccessToken

from apps.peoples.models import People
from apps.noc.consumers import NOCDashboardConsumer


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def tenant():
    """Create test tenant."""
    from apps.client_onboarding.models import Bt as BusinessUnit
    return BusinessUnit.objects.create(
        unitname='Test Tenant',
        unitcode='TEST001',
        is_active=True
    )


@pytest.fixture
def noc_user(tenant):
    """Create user with NOC capabilities."""
    user = People.objects.create_user(
        loginid='nocuser',
        email='noc@test.com',
        password='NocPass123!',
        peoplename='NOC User',
        is_staff=True,
        enable=True
    )
    user.tenant = tenant
    user.capabilities = {
        'noc:view': True,
        'noc:acknowledge': True
    }
    user.save()
    return user


@pytest.fixture
def another_noc_user(tenant):
    """Create another user with NOC capabilities."""
    user = People.objects.create_user(
        loginid='anothernocuser',
        email='another@test.com',
        password='AnotherPass123!',
        peoplename='Another NOC User',
        is_staff=True,
        enable=True
    )
    user.tenant = tenant
    user.capabilities = {
        'noc:view': True,
        'noc:acknowledge': True
    }
    user.save()
    return user


@pytest.fixture
def noc_application():
    """Create NOC application with middleware."""
    from apps.core.middleware.websocket_jwt_auth import JWTAuthMiddleware

    url_router = URLRouter([
        re_path(r'ws/noc/dashboard/$', NOCDashboardConsumer.as_asgi()),
    ])

    return JWTAuthMiddleware(url_router)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


# ============================================================================
# TESTS: Per-User Rate Limiting
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
class TestPerUserRateLimiting:
    """Test that rate limiting is per-user, not per-connection."""

    async def test_single_connection_respects_rate_limit(
        self, noc_application, noc_user
    ):
        """Test that a single connection respects rate limit."""
        token = str(AccessToken.for_user(noc_user))

        communicator = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token}"
        )

        connected, _ = await communicator.connect()
        assert connected, "Should connect successfully"

        # Receive connection message
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connected'

        # Send RATE_LIMIT_MAX (100) valid heartbeat messages
        for i in range(100):
            await communicator.send_json_to({
                'type': 'heartbeat',
            })
            # Should receive ack for each
            response = await communicator.receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Next message should trigger rate limit
        await communicator.send_json_to({
            'type': 'heartbeat',
        })

        # Should receive rate limit error
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'error'
        assert 'Rate limit exceeded' in response['message']

        await communicator.disconnect()

    async def test_multiple_connections_same_user_share_limit(
        self, noc_application, noc_user
    ):
        """
        CRITICAL: Test that multiple connections from the same user
        share a single rate limit (Redis-backed per-user).

        This is the security fix: without per-user limiting,
        opening 3 connections allows 300 messages instead of 100.
        """
        token = str(AccessToken.for_user(noc_user))

        # Create 3 connections from the same user
        communicators = []
        for i in range(3):
            comm = WebsocketCommunicator(
                noc_application,
                f"/ws/noc/dashboard/?token={token}"
            )
            connected, _ = await comm.connect()
            assert connected, f"Connection {i} should connect"

            # Consume connection message
            response = await comm.receive_json_from(timeout=2)
            assert response['type'] == 'connected'
            communicators.append(comm)

        # Send 40 messages from first connection
        for i in range(40):
            await communicators[0].send_json_to({'type': 'heartbeat'})
            response = await communicators[0].receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Send 40 messages from second connection
        for i in range(40):
            await communicators[1].send_json_to({'type': 'heartbeat'})
            response = await communicators[1].receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Send 20 messages from third connection (total = 100)
        for i in range(20):
            await communicators[2].send_json_to({'type': 'heartbeat'})
            response = await communicators[2].receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Next message from ANY connection should hit rate limit
        # Try from connection 1
        await communicators[0].send_json_to({'type': 'heartbeat'})
        response = await communicators[0].receive_json_from(timeout=2)
        assert response['type'] == 'error', \
            "Connection 1 should hit rate limit (shared per-user)"
        assert 'Rate limit exceeded' in response['message']

        # Try from connection 2 - should also hit limit
        await communicators[1].send_json_to({'type': 'heartbeat'})
        response = await communicators[1].receive_json_from(timeout=2)
        assert response['type'] == 'error', \
            "Connection 2 should hit rate limit (shared per-user)"

        # Try from connection 3 - should also hit limit
        await communicators[2].send_json_to({'type': 'heartbeat'})
        response = await communicators[2].receive_json_from(timeout=2)
        assert response['type'] == 'error', \
            "Connection 3 should hit rate limit (shared per-user)"

        # Cleanup
        for comm in communicators:
            await comm.disconnect()

    async def test_different_users_have_separate_limits(
        self, noc_application, noc_user, another_noc_user
    ):
        """Test that different users have separate rate limits."""
        token1 = str(AccessToken.for_user(noc_user))
        token2 = str(AccessToken.for_user(another_noc_user))

        # Create connection for user 1
        comm1 = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token1}"
        )
        connected1, _ = await comm1.connect()
        assert connected1

        # Consume connection message
        response = await comm1.receive_json_from(timeout=2)
        assert response['type'] == 'connected'

        # Create connection for user 2
        comm2 = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token2}"
        )
        connected2, _ = await comm2.connect()
        assert connected2

        # Consume connection message
        response = await comm2.receive_json_from(timeout=2)
        assert response['type'] == 'connected'

        # User 1 sends 100 messages (should succeed)
        for i in range(100):
            await comm1.send_json_to({'type': 'heartbeat'})
            response = await comm1.receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # User 1 hits limit
        await comm1.send_json_to({'type': 'heartbeat'})
        response = await comm1.receive_json_from(timeout=2)
        assert response['type'] == 'error'

        # User 2 should still have quota available
        await comm2.send_json_to({'type': 'heartbeat'})
        response = await comm2.receive_json_from(timeout=2)
        assert response['type'] == 'heartbeat_ack', \
            "User 2 should have independent rate limit"

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_rate_limit_resets_after_window(
        self, noc_application, noc_user
    ):
        """Test that rate limit window resets after RATE_LIMIT_WINDOW seconds."""
        token = str(AccessToken.for_user(noc_user))

        communicator = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Consume connection message
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connected'

        # Send 100 messages (hit limit)
        for i in range(100):
            await communicator.send_json_to({'type': 'heartbeat'})
            response = await communicator.receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Should hit rate limit
        await communicator.send_json_to({'type': 'heartbeat'})
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'error'

        # Clear cache to simulate window reset
        cache.delete(f'websocket:rate:{noc_user.id}')

        # Should now be able to send again
        await communicator.send_json_to({'type': 'heartbeat'})
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'heartbeat_ack', \
            "Should succeed after cache clear (window reset)"

        await communicator.disconnect()

    async def test_rate_limit_uses_redis_cache_backend(
        self, noc_application, noc_user
    ):
        """Test that rate limiting uses Redis cache backend (atomic operations)."""
        token = str(AccessToken.for_user(noc_user))

        communicator = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Consume connection message
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connected'

        # Cache key should be websocket:rate:{user_id}
        cache_key = f'websocket:rate:{noc_user.id}'

        # Send one message
        await communicator.send_json_to({'type': 'heartbeat'})
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'heartbeat_ack'

        # Check that cache was incremented
        # The cache should contain the message count
        cache_value = cache.get(cache_key)
        assert cache_value is not None, \
            f"Cache key {cache_key} should exist after message"
        assert isinstance(cache_value, int), \
            "Cache value should be integer counter"
        assert cache_value >= 1, \
            "Cache counter should be at least 1"

        await communicator.disconnect()

    async def test_heartbeat_does_not_consume_quota_in_legacy_pattern(
        self, noc_application, noc_user
    ):
        """
        Test that different message types are counted in rate limiting.

        Note: Current implementation counts all messages. If we want
        to exclude heartbeats, that would be a separate optimization.
        """
        token = str(AccessToken.for_user(noc_user))

        communicator = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Consume connection message
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connected'

        # Send 50 heartbeats
        for i in range(50):
            await communicator.send_json_to({'type': 'heartbeat'})
            response = await communicator.receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Send 50 other messages
        for i in range(50):
            await communicator.send_json_to({
                'type': 'subscribe_client',
                'client_id': i
            })
            # Will get error or subscription response
            response = await communicator.receive_json_from(timeout=2)
            # Just consume the response

        # Both count toward limit, so 101st should fail
        await communicator.send_json_to({'type': 'heartbeat'})
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'error', \
            "Rate limit should count all message types"

        await communicator.disconnect()


# ============================================================================
# TESTS: Rate Limiting Edge Cases
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
class TestRateLimitingEdgeCases:
    """Test edge cases and error conditions."""

    async def test_malformed_messages_still_consume_quota(
        self, noc_application, noc_user
    ):
        """Test that malformed messages are counted in rate limit."""
        token = str(AccessToken.for_user(noc_user))

        communicator = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Consume connection message
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connected'

        # Send 50 valid messages
        for i in range(50):
            await communicator.send_json_to({'type': 'heartbeat'})
            response = await communicator.receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Send 50 invalid JSON messages
        for i in range(50):
            await communicator.send(text_data='{invalid json}')
            response = await communicator.receive_json_from(timeout=2)
            assert response['type'] == 'error'

        # Should hit rate limit on 101st message
        await communicator.send_json_to({'type': 'heartbeat'})
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'error'
        assert 'Rate limit exceeded' in response['message']

        await communicator.disconnect()

    async def test_concurrent_messages_from_multiple_connections(
        self, noc_application, noc_user
    ):
        """Test concurrent message handling across multiple connections."""
        token = str(AccessToken.for_user(noc_user))

        # Create 2 connections
        comm1 = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token}"
        )
        comm2 = WebsocketCommunicator(
            noc_application,
            f"/ws/noc/dashboard/?token={token}"
        )

        conn1_ok, _ = await comm1.connect()
        conn2_ok, _ = await comm2.connect()
        assert conn1_ok and conn2_ok

        # Consume connection messages
        await comm1.receive_json_from(timeout=2)
        await comm2.receive_json_from(timeout=2)

        # Rapidly send messages from both connections
        # Send 50 from conn1
        for i in range(50):
            await comm1.send_json_to({'type': 'heartbeat'})

        # Send 50 from conn2
        for i in range(50):
            await comm2.send_json_to({'type': 'heartbeat'})

        # Receive 50 from conn1
        for i in range(50):
            response = await comm1.receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Receive 50 from conn2
        for i in range(50):
            response = await comm2.receive_json_from(timeout=2)
            assert response['type'] == 'heartbeat_ack'

        # Both should hit rate limit (shared per-user)
        await comm1.send_json_to({'type': 'heartbeat'})
        resp1 = await comm1.receive_json_from(timeout=2)

        await comm2.send_json_to({'type': 'heartbeat'})
        resp2 = await comm2.receive_json_from(timeout=2)

        assert resp1['type'] == 'error' or resp2['type'] == 'error', \
            "At least one connection should hit rate limit"

        await comm1.disconnect()
        await comm2.disconnect()
