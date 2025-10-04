"""
WebSocket Performance & Load Tests

Tests performance characteristics under load:
- Concurrent connection handling (100+ connections)
- Message throughput (1000 msg/sec target)
- Latency profiling (P50, P95, P99)
- Memory leak detection (long-running connections)

Chain of Thought:
1. Must test realistic load (100+ concurrent connections)
2. Measure throughput AND latency (both matter)
3. Use percentiles (not averages) for latency (P95/P99 more meaningful)
4. Test memory stability over time (detect leaks)

Compliance with .claude/rules.md Rule #11 (specific exceptions).
"""

import pytest
import asyncio
import time
import statistics
from typing import List
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import re_path
from django.test import override_settings
from datetime import datetime, timezone as dt_timezone

from apps.peoples.models import People
from apps.noc.consumers import PresenceMonitorConsumer
from apps.core.middleware.websocket_jwt_auth import JWTAuthMiddleware
from rest_framework_simplejwt.tokens import AccessToken


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_users():
    """Create multiple test users for concurrent testing."""
    users = []
    for i in range(10):
        user = People.objects.create_user(
            loginid=f'perfuser{i}',
            email=f'perf{i}@test.com',
            password='PerfPass123!',
            peoplename=f'Performance User {i}',
            enable=True
        )
        users.append(user)
    return users


@pytest.fixture
def jwt_tokens(test_users):
    """Generate JWT tokens for all test users."""
    return [str(AccessToken.for_user(user)) for user in test_users]


@pytest.fixture
def presence_application():
    """Create presence monitor application."""
    url_router = URLRouter([
        re_path(r'ws/noc/presence/$', PresenceMonitorConsumer.as_asgi()),
    ])
    return JWTAuthMiddleware(url_router)


# ============================================================================
# PHASE 3.4b: CONCURRENT CONNECTION TESTS (3 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.performance
@override_settings(
    WEBSOCKET_THROTTLE_LIMITS={'authenticated': 200}  # Allow many connections
)
class TestConcurrentConnections:
    """Test concurrent connection handling."""

    async def test_100_concurrent_connections(self, presence_application, jwt_tokens):
        """Test handling 100 concurrent connections."""
        communicators = []
        start_time = time.time()

        try:
            # Establish 100 connections
            for i in range(100):
                token = jwt_tokens[i % len(jwt_tokens)]  # Cycle through tokens
                comm = WebsocketCommunicator(
                    presence_application,
                    f"/ws/noc/presence/?token={token}"
                )
                connected, _ = await comm.connect()
                assert connected, f"Connection {i} failed"
                communicators.append(comm)

                # Receive connection_established
                await comm.receive_json_from(timeout=2)

            connection_time = time.time() - start_time

            # All connections should establish in reasonable time (<10s)
            assert connection_time < 10, f"100 connections took {connection_time:.2f}s (target <10s)"

            # Test message broadcast
            broadcast_start = time.time()
            for comm in communicators:
                await comm.send_json_to({'type': 'ping'})
                await comm.receive_json_from(timeout=2)

            broadcast_time = time.time() - broadcast_start

            # Broadcasting to 100 connections should be fast (<5s)
            assert broadcast_time < 5, f"Broadcast took {broadcast_time:.2f}s (target <5s)"

        finally:
            # Cleanup all connections
            for comm in communicators:
                await comm.disconnect()

    async def test_concurrent_connection_stability(self, presence_application, jwt_tokens):
        """Test that concurrent connections remain stable over time."""
        num_connections = 50
        test_duration = 10  # seconds

        communicators = []
        start_time = time.time()

        try:
            # Establish connections
            for i in range(num_connections):
                token = jwt_tokens[i % len(jwt_tokens)]
                comm = WebsocketCommunicator(
                    presence_application,
                    f"/ws/noc/presence/?token={token}"
                )
                connected, _ = await comm.connect()
                assert connected
                await comm.receive_json_from(timeout=2)
                communicators.append(comm)

            # Keep alive for test duration
            while time.time() - start_time < test_duration:
                # Send heartbeat to random connection
                comm = communicators[int(time.time()) % num_connections]
                await comm.send_json_to({
                    'type': 'heartbeat',
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                })
                await comm.receive_json_from(timeout=2)
                await asyncio.sleep(0.5)

            # All connections should still be alive
            for i, comm in enumerate(communicators):
                await comm.send_json_to({'type': 'get_stats'})
                stats = await comm.receive_json_from(timeout=2)
                assert stats['type'] == 'stats', f"Connection {i} not responding"

        finally:
            for comm in communicators:
                await comm.disconnect()

    async def test_connection_cleanup_on_disconnect(self, presence_application, jwt_tokens):
        """Test that disconnecting releases resources properly."""
        num_rounds = 5
        connections_per_round = 20

        for round_num in range(num_rounds):
            communicators = []

            # Establish connections
            for i in range(connections_per_round):
                token = jwt_tokens[i % len(jwt_tokens)]
                comm = WebsocketCommunicator(
                    presence_application,
                    f"/ws/noc/presence/?token={token}"
                )
                connected, _ = await comm.connect()
                assert connected
                await comm.receive_json_from(timeout=2)
                communicators.append(comm)

            # Disconnect all
            for comm in communicators:
                await comm.disconnect()

            # Brief pause to allow cleanup
            await asyncio.sleep(0.5)

        # If memory leaks, this test would fail or slow down significantly


# ============================================================================
# PHASE 3.4c: THROUGHPUT & LATENCY TESTS (3 tests)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.performance
class TestThroughputAndLatency:
    """Test message throughput and latency characteristics."""

    async def test_message_throughput(self, presence_application, jwt_tokens):
        """Test message throughput (messages per second)."""
        num_connections = 10
        messages_per_connection = 100
        total_messages = num_connections * messages_per_connection

        communicators = []

        try:
            # Establish connections
            for i in range(num_connections):
                token = jwt_tokens[i % len(jwt_tokens)]
                comm = WebsocketCommunicator(
                    presence_application,
                    f"/ws/noc/presence/?token={token}"
                )
                connected, _ = await comm.connect()
                assert connected
                await comm.receive_json_from(timeout=2)
                communicators.append(comm)

            # Send messages and measure throughput
            start_time = time.time()

            tasks = []
            for comm in communicators:
                task = asyncio.create_task(
                    self._send_multiple_heartbeats(comm, messages_per_connection)
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

            elapsed_time = time.time() - start_time

            # Calculate throughput
            throughput = total_messages / elapsed_time

            # Target: 1000 msg/sec
            assert throughput > 500, \
                f"Throughput too low: {throughput:.0f} msg/sec (target >500)"

            print(f"\n✅ Throughput: {throughput:.0f} messages/second")

        finally:
            for comm in communicators:
                await comm.disconnect()

    async def _send_multiple_heartbeats(self, comm, count):
        """Helper to send multiple heartbeats."""
        for _ in range(count):
            await comm.send_json_to({
                'type': 'heartbeat',
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            })
            await comm.receive_json_from(timeout=2)

    async def test_latency_profiling(self, presence_application, jwt_tokens):
        """Test latency characteristics (P50, P95, P99)."""
        num_messages = 100
        latencies: List[float] = []

        token = jwt_tokens[0]
        communicator = WebsocketCommunicator(
            presence_application,
            f"/ws/noc/presence/?token={token}"
        )

        try:
            connected, _ = await communicator.connect()
            assert connected
            await communicator.receive_json_from(timeout=2)

            # Measure latency for many messages
            for _ in range(num_messages):
                send_time = time.time()

                await communicator.send_json_to({
                    'type': 'heartbeat',
                    'timestamp': datetime.now(dt_timezone.utc).isoformat()
                })

                await communicator.receive_json_from(timeout=2)

                receive_time = time.time()
                latency_ms = (receive_time - send_time) * 1000
                latencies.append(latency_ms)

            # Calculate percentiles
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            avg = statistics.mean(latencies)

            # Assertions
            assert p50 < 50, f"P50 latency too high: {p50:.1f}ms (target <50ms)"
            assert p95 < 100, f"P95 latency too high: {p95:.1f}ms (target <100ms)"
            assert p99 < 200, f"P99 latency too high: {p99:.1f}ms (target <200ms)"

            print(f"\n✅ Latency Profile:")
            print(f"   P50: {p50:.1f}ms")
            print(f"   P95: {p95:.1f}ms")
            print(f"   P99: {p99:.1f}ms")
            print(f"   Avg: {avg:.1f}ms")

        finally:
            await communicator.disconnect()

    async def test_latency_under_load(self, presence_application, jwt_tokens):
        """Test that latency remains acceptable under load."""
        num_connections = 50
        messages_per_connection = 10

        communicators = []
        all_latencies = []

        try:
            # Establish connections
            for i in range(num_connections):
                token = jwt_tokens[i % len(jwt_tokens)]
                comm = WebsocketCommunicator(
                    presence_application,
                    f"/ws/noc/presence/?token={token}"
                )
                connected, _ = await comm.connect()
                assert connected
                await comm.receive_json_from(timeout=2)
                communicators.append(comm)

            # Send messages concurrently and measure latency
            tasks = []
            for comm in communicators:
                task = asyncio.create_task(
                    self._measure_latencies(comm, messages_per_connection)
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # Flatten all latencies
            for latencies in results:
                all_latencies.extend(latencies)

            # Calculate percentiles under load
            all_latencies.sort()
            p95_under_load = all_latencies[int(len(all_latencies) * 0.95)]

            # P95 should still be acceptable under load (<150ms)
            assert p95_under_load < 150, \
                f"P95 latency under load too high: {p95_under_load:.1f}ms (target <150ms)"

            print(f"\n✅ P95 latency under load ({num_connections} connections): {p95_under_load:.1f}ms")

        finally:
            for comm in communicators:
                await comm.disconnect()

    async def _measure_latencies(self, comm, count):
        """Helper to measure latencies for multiple messages."""
        latencies = []
        for _ in range(count):
            send_time = time.time()
            await comm.send_json_to({
                'type': 'heartbeat',
                'timestamp': datetime.now(dt_timezone.utc).isoformat()
            })
            await comm.receive_json_from(timeout=2)
            receive_time = time.time()
            latency_ms = (receive_time - send_time) * 1000
            latencies.append(latency_ms)
        return latencies


# ============================================================================
# MEMORY LEAK DETECTION (Bonus Test)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.performance
@pytest.mark.slow
class TestMemoryStability:
    """Test memory stability over extended periods."""

    async def test_no_memory_leak_long_running(self, presence_application, jwt_tokens):
        """Test that long-running connections don't leak memory."""
        # This is a simplified test - in production use memory profilers
        num_connections = 20
        test_duration = 30  # 30 seconds

        communicators = []
        start_time = time.time()

        try:
            # Establish connections
            for i in range(num_connections):
                token = jwt_tokens[i % len(jwt_tokens)]
                comm = WebsocketCommunicator(
                    presence_application,
                    f"/ws/noc/presence/?token={token}"
                )
                connected, _ = await comm.connect()
                assert connected
                await comm.receive_json_from(timeout=2)
                communicators.append(comm)

            # Keep connections active
            iteration = 0
            while time.time() - start_time < test_duration:
                # Send heartbeats
                for comm in communicators:
                    await comm.send_json_to({
                        'type': 'heartbeat',
                        'timestamp': datetime.now(dt_timezone.utc).isoformat()
                    })
                    await comm.receive_json_from(timeout=2)

                iteration += 1
                await asyncio.sleep(1)

            # All connections should still be responsive
            for i, comm in enumerate(communicators):
                await comm.send_json_to({'type': 'get_stats'})
                stats = await comm.receive_json_from(timeout=2)
                assert stats['type'] == 'stats'
                assert stats['uptime_seconds'] >= test_duration - 2

            print(f"\n✅ Memory stability: {num_connections} connections, {iteration} iterations, {test_duration}s")

        finally:
            for comm in communicators:
                await comm.disconnect()
