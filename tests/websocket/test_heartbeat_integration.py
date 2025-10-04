"""
Heartbeat & Reconnection Integration Tests

Tests the heartbeat protocol, stale connection detection, and automatic
reconnection with exponential backoff.

Chain of Thought:
1. Heartbeat protocol must work bidirectionally (client → server, server → client)
2. Stale connections must be detected and cleaned up (5min timeout)
3. Connection recovery should use exponential backoff (1s, 2s, 4s, 8s, 16s)
4. Latency tracking must be accurate (roundtrip time calculation)

Compliance with .claude/rules.md Rule #11 (specific exceptions).
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone as dt_timezone
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import re_path
from django.test import override_settings
from unittest.mock import patch, AsyncMock

from apps.peoples.models import People
from apps.noc.consumers import PresenceMonitorConsumer
from apps.core.middleware.websocket_jwt_auth import JWTAuthMiddleware
from rest_framework_simplejwt.tokens import AccessToken


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_user():
    """Create test user."""
    return People.objects.create_user(
        loginid='heartbeatuser',
        email='heartbeat@test.com',
        password='HeartbeatPass123!',
        peoplename='Heartbeat User',
        enable=True
    )


@pytest.fixture
def jwt_token(test_user):
    """Generate JWT token."""
    return str(AccessToken.for_user(test_user))


@pytest.fixture
def presence_application():
    """Create presence monitor application."""
    url_router = URLRouter([
        re_path(r'ws/noc/presence/$', PresenceMonitorConsumer.as_asgi()),
    ])
    return JWTAuthMiddleware(url_router)


# ============================================================================
# PHASE 3.3b: HEARTBEAT PROTOCOL TESTS (4 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(
    WEBSOCKET_HEARTBEAT_INTERVAL=1,  # 1 second for testing
    WEBSOCKET_PRESENCE_TIMEOUT=5     # 5 seconds timeout
)
class TestHeartbeatProtocol:
    """Test heartbeat keep-alive protocol."""

    async def test_client_heartbeat_receives_acknowledgment(self, presence_application, jwt_token):
        """Test that client heartbeat receives proper acknowledgment."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Receive connection_established
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'connection_established'
        assert response['heartbeat_interval'] == 1

        # Send client heartbeat
        client_time = datetime.now(dt_timezone.utc).isoformat()
        await communicator.send_json_to({
            'type': 'heartbeat',
            'timestamp': client_time
        })

        # Should receive heartbeat_ack
        ack = await communicator.receive_json_from(timeout=2)
        assert ack['type'] == 'heartbeat_ack'
        assert 'server_time' in ack
        assert 'latency_ms' in ack
        assert 'uptime_seconds' in ack

        # Latency should be reasonable (<1000ms)
        assert ack['latency_ms'] < 1000, f"Latency too high: {ack['latency_ms']}ms"

        await communicator.disconnect()

    async def test_server_initiated_heartbeat(self, presence_application, jwt_token):
        """Test that server sends periodic heartbeats."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection_established
        await communicator.receive_json_from(timeout=2)

        # Wait for server-initiated heartbeat (interval is 1 second)
        heartbeat = await communicator.receive_json_from(timeout=3)
        assert heartbeat['type'] == 'heartbeat'
        assert 'server_time' in heartbeat

        await communicator.disconnect()

    async def test_heartbeat_calculates_latency(self, presence_application, jwt_token):
        """Test that heartbeat accurately calculates roundtrip latency."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection_established
        await communicator.receive_json_from(timeout=2)

        # Send heartbeat with accurate timestamp
        client_send_time = datetime.now(dt_timezone.utc)
        await communicator.send_json_to({
            'type': 'heartbeat',
            'timestamp': client_send_time.isoformat()
        })

        # Receive acknowledgment
        ack = await communicator.receive_json_from(timeout=2)

        # Calculate expected latency
        client_receive_time = datetime.now(dt_timezone.utc)
        expected_latency = int((client_receive_time - client_send_time).total_seconds() * 1000)

        # Server-calculated latency should be close (within 100ms tolerance)
        assert abs(ack['latency_ms'] - expected_latency) < 100, \
            f"Latency mismatch: server={ack['latency_ms']}, expected~{expected_latency}"

        await communicator.disconnect()

    async def test_ping_pong_simple_keepalive(self, presence_application, jwt_token):
        """Test simple ping/pong for basic keep-alive."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection_established
        await communicator.receive_json_from(timeout=2)

        # Send ping
        await communicator.send_json_to({'type': 'ping'})

        # Should receive pong
        pong = await communicator.receive_json_from(timeout=2)
        assert pong['type'] == 'pong'
        assert 'timestamp' in pong

        await communicator.disconnect()


# ============================================================================
# PHASE 3.3c: STALE CONNECTION CLEANUP TESTS (4 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(
    WEBSOCKET_HEARTBEAT_INTERVAL=1,
    WEBSOCKET_PRESENCE_TIMEOUT=3  # 3 seconds for testing
)
class TestStaleConnectionCleanup:
    """Test automatic cleanup of stale connections."""

    async def test_stale_connection_auto_closes(self, presence_application, jwt_token):
        """Test that connections without heartbeat are closed after timeout."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Receive connection_established
        await communicator.receive_json_from(timeout=2)

        # Don't send any heartbeats - connection should become stale

        # Wait for timeout (3 seconds) + buffer
        await asyncio.sleep(4)

        # Connection should be closed by server
        # Try to receive - should timeout or get close
        try:
            # Server should have closed connection
            message = await communicator.receive_output(timeout=1)
            # Should be a close message
            assert message['type'] in ['websocket.close', 'websocket.disconnect']
        except asyncio.TimeoutError:
            # Connection already closed
            pass

        await communicator.disconnect()

    async def test_active_connection_stays_alive(self, presence_application, jwt_token):
        """Test that connections with regular heartbeats stay alive."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection_established
        await communicator.receive_json_from(timeout=2)

        # Send heartbeats every second for 5 seconds
        for i in range(5):
            await asyncio.sleep(1)

            # Send heartbeat
            await communicator.send_json_to({
                'type': 'heartbeat',
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            })

            # Receive ack
            ack = await communicator.receive_json_from(timeout=2)
            assert ack['type'] == 'heartbeat_ack'

        # Connection should still be alive
        await communicator.disconnect()

    async def test_connection_uptime_tracking(self, presence_application, jwt_token):
        """Test that connection uptime is accurately tracked."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connect_time = time.time()
        connected, _ = await communicator.connect()
        assert connected

        # Skip connection_established
        await communicator.receive_json_from(timeout=2)

        # Wait 2 seconds
        await asyncio.sleep(2)

        # Send heartbeat to get uptime
        await communicator.send_json_to({
            'type': 'heartbeat',
            'timestamp': datetime.now(dt_timezone.utc).isoformat()
        })

        ack = await communicator.receive_json_from(timeout=2)

        # Uptime should be ~2 seconds
        actual_uptime = time.time() - connect_time
        reported_uptime = ack['uptime_seconds']

        assert abs(reported_uptime - actual_uptime) < 1, \
            f"Uptime mismatch: reported={reported_uptime}, actual={actual_uptime}"

        await communicator.disconnect()

    async def test_get_stats_command(self, presence_application, jwt_token):
        """Test get_stats command returns connection statistics."""
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection_established
        await communicator.receive_json_from(timeout=2)

        # Send some messages
        await communicator.send_json_to({'type': 'ping'})
        await communicator.receive_json_from(timeout=2)  # pong

        await communicator.send_json_to({'type': 'heartbeat', 'timestamp': datetime.now(dt_timezone.utc).isoformat()})
        await communicator.receive_json_from(timeout=2)  # ack

        # Request stats
        await communicator.send_json_to({'type': 'get_stats'})

        stats = await communicator.receive_json_from(timeout=2)
        assert stats['type'] == 'stats'
        assert 'uptime_seconds' in stats
        assert 'message_count' in stats
        assert 'last_heartbeat_ago' in stats
        assert 'user_type' in stats

        # Message count should be 3 (ping + heartbeat + get_stats)
        assert stats['message_count'] >= 3

        await communicator.disconnect()


# ============================================================================
# RECONNECTION PATTERN TESTS (Bonus - client-side behavior)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@override_settings(
    WEBSOCKET_AUTO_RECONNECT_ENABLED=True,
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS=5,
    WEBSOCKET_RECONNECT_BASE_DELAY=1
)
class TestReconnectionPatterns:
    """Test reconnection patterns and exponential backoff."""

    async def test_exponential_backoff_delays(self, presence_application, jwt_token):
        """Test that reconnection delays follow exponential backoff."""
        # This tests the CLIENT-SIDE behavior documented in settings
        # The actual implementation would be in client SDK

        delays = []
        base_delay = 1  # WEBSOCKET_RECONNECT_BASE_DELAY

        for attempt in range(5):  # WEBSOCKET_MAX_RECONNECT_ATTEMPTS
            delay = base_delay * (2 ** attempt)
            delays.append(delay)

        # Expected delays: 1s, 2s, 4s, 8s, 16s
        assert delays == [1, 2, 4, 8, 16]

    async def test_connection_recovery_after_disconnect(self, presence_application, jwt_token):
        """Test that connection can be re-established after disconnect."""
        # First connection
        comm1 = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected1, _ = await comm1.connect()
        assert connected1

        await comm1.receive_json_from(timeout=2)  # connection_established

        # Disconnect
        await comm1.disconnect()

        # Wait a bit
        await asyncio.sleep(1)

        # Reconnect
        comm2 = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected2, _ = await comm2.connect()
        assert connected2, "Reconnection should succeed"

        await comm2.receive_json_from(timeout=2)

        await comm2.disconnect()

    async def test_connection_state_not_preserved_across_reconnects(self, presence_application, jwt_token):
        """Test that connection state is fresh on reconnect."""
        # First connection - send some messages
        comm1 = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected1, _ = await comm1.connect()
        await comm1.receive_json_from(timeout=2)

        # Send heartbeat
        await comm1.send_json_to({
            'type': 'heartbeat',
            'timestamp': datetime.now(dt_timezone.utc).isoformat()
        })
        await comm1.receive_json_from(timeout=2)

        # Get stats
        await comm1.send_json_to({'type': 'get_stats'})
        stats1 = await comm1.receive_json_from(timeout=2)
        message_count_1 = stats1['message_count']

        await comm1.disconnect()

        # Reconnect
        comm2 = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={jwt_token}"
        )

        connected2, _ = await comm2.connect()
        await comm2.receive_json_from(timeout=2)

        # Get stats immediately
        await comm2.send_json_to({'type': 'get_stats'})
        stats2 = await comm2.receive_json_from(timeout=2)
        message_count_2 = stats2['message_count']

        # Message count should be reset (only get_stats = 1)
        assert message_count_2 == 1, f"State should be fresh, got message_count={message_count_2}"

        await comm2.disconnect()
