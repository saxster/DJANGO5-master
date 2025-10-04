"""
Test suite for WebSocket Metrics Collection

Tests WebSocket connection tracking, throttling metrics,
message throughput, and connection duration monitoring.

Total: 38 tests
"""

import pytest
from django.test import TestCase
from unittest.mock import Mock, patch
from monitoring.services.websocket_metrics_collector import websocket_metrics, WebSocketMetricsCollector


class TestConnectionAttemptMetrics(TestCase):
    """Test connection attempt metrics (10 tests)."""

    def setUp(self):
        self.collector = WebSocketMetricsCollector()

    def test_record_accepted_connection(self):
        """Test recording of accepted connection."""
        self.collector.record_connection_attempt(
            accepted=True,
            user_type='authenticated',
            client_ip='192.168.1.100',
            user_id=123
        )
        stats = self.collector.get_websocket_stats()
        assert stats['accepted_connections'] > 0

    def test_record_rejected_connection(self):
        """Test recording of rejected connection."""
        self.collector.record_connection_attempt(
            accepted=False,
            user_type='anonymous',
            client_ip='192.168.1.100',
            rejection_reason='rate_limit_exceeded'
        )
        stats = self.collector.get_websocket_stats()
        assert stats['rejected_connections'] > 0

    def test_track_by_user_type(self):
        """Test connection tracking by user type."""
        user_types = ['anonymous', 'authenticated', 'staff']
        for user_type in user_types:
            self.collector.record_connection_attempt(
                accepted=True,
                user_type=user_type,
                client_ip='192.168.1.100'
            )
        stats = self.collector.get_websocket_stats()
        assert len(stats['connections_by_user_type']) == 3

    def test_track_by_client_ip(self):
        """Test connection tracking by client IP."""
        for i in range(5):
            self.collector.record_connection_attempt(
                accepted=True,
                user_type='authenticated',
                client_ip=f'192.168.1.{100 + i}'
            )
        stats = self.collector.get_websocket_stats()
        assert len(stats['connections_by_ip']) >= 5

    def test_rejection_reason_tracking(self):
        """Test tracking of rejection reasons."""
        reasons = ['rate_limit_exceeded', 'auth_failed', 'invalid_origin']
        for reason in reasons:
            self.collector.record_connection_attempt(
                accepted=False,
                user_type='anonymous',
                client_ip='192.168.1.100',
                rejection_reason=reason
            )
        stats = self.collector.get_websocket_stats()
        assert len(stats['rejection_reasons']) == 3

    def test_connection_with_correlation_id(self):
        """Test connection tracking with correlation ID."""
        correlation_id = '550e8400-e29b-41d4-a716-446655440000'
        self.collector.record_connection_attempt(
            accepted=True,
            user_type='authenticated',
            client_ip='192.168.1.100',
            correlation_id=correlation_id
        )
        # Should not raise exceptions

    def test_acceptance_rate_calculation(self):
        """Test acceptance rate calculation."""
        # 80% accepted, 20% rejected
        for i in range(100):
            self.collector.record_connection_attempt(
                accepted=i % 5 != 0,
                user_type='authenticated',
                client_ip='192.168.1.100',
                rejection_reason='rate_limit_exceeded' if i % 5 == 0 else None
            )
        stats = self.collector.get_websocket_stats()
        assert abs(stats['acceptance_rate'] - 0.80) < 0.05

    def test_connection_rate_per_second(self):
        """Test connection rate calculation."""
        for _ in range(50):
            self.collector.record_connection_attempt(
                accepted=True,
                user_type='authenticated',
                client_ip='192.168.1.100'
            )
        stats = self.collector.get_websocket_stats(window_minutes=1)
        assert stats['connections_per_second'] > 0

    def test_peak_connection_rate(self):
        """Test peak connection rate tracking."""
        # Simulate burst of connections
        for _ in range(100):
            self.collector.record_connection_attempt(
                accepted=True,
                user_type='authenticated',
                client_ip='192.168.1.100'
            )
        stats = self.collector.get_websocket_stats()
        assert stats['peak_connection_rate'] >= 100

    def test_connection_attempts_by_time(self):
        """Test connection attempts grouped by time."""
        for _ in range(20):
            self.collector.record_connection_attempt(
                accepted=True,
                user_type='authenticated',
                client_ip='192.168.1.100'
            )
        stats = self.collector.get_websocket_stats()
        assert stats['connection_attempts_timeline'] is not None


class TestActiveConnectionMetrics(TestCase):
    """Test active connection metrics (8 tests)."""

    def setUp(self):
        self.collector = WebSocketMetricsCollector()

    def test_track_active_connections(self):
        """Test tracking of currently active connections."""
        self.collector.record_connection_opened(
            user_type='authenticated',
            user_id=123
        )
        stats = self.collector.get_websocket_stats()
        assert stats['active_connections'] > 0

    def test_track_by_user_type(self):
        """Test active connections by user type."""
        user_types = ['anonymous', 'authenticated', 'staff']
        for user_type in user_types:
            self.collector.record_connection_opened(
                user_type=user_type
            )
        stats = self.collector.get_websocket_stats()
        assert len(stats['active_by_user_type']) == 3

    def test_connection_lifecycle(self):
        """Test full connection lifecycle."""
        # Open connection
        self.collector.record_connection_opened(
            user_type='authenticated',
            user_id=123
        )
        stats = self.collector.get_websocket_stats()
        initial_count = stats['active_connections']

        # Close connection
        self.collector.record_connection_closed(
            user_type='authenticated',
            duration_seconds=120.0
        )
        stats = self.collector.get_websocket_stats()
        assert stats['active_connections'] < initial_count

    def test_max_concurrent_connections(self):
        """Test tracking of maximum concurrent connections."""
        for i in range(50):
            self.collector.record_connection_opened(
                user_type='authenticated',
                user_id=i
            )
        stats = self.collector.get_websocket_stats()
        assert stats['max_concurrent_connections'] >= 50

    def test_connection_churn_rate(self):
        """Test calculation of connection churn rate."""
        # Open and close connections rapidly
        for _ in range(20):
            self.collector.record_connection_opened(user_type='authenticated')
            self.collector.record_connection_closed(user_type='authenticated', duration_seconds=5.0)
        stats = self.collector.get_websocket_stats()
        assert stats['churn_rate'] is not None

    def test_long_lived_connections(self):
        """Test tracking of long-lived connections."""
        # Simulate connections that have been active for a while
        for _ in range(10):
            self.collector.record_connection_opened(user_type='authenticated')
        stats = self.collector.get_websocket_stats()
        assert stats['long_lived_connections'] >= 0

    def test_idle_connection_detection(self):
        """Test detection of idle connections."""
        self.collector.record_connection_opened(user_type='authenticated')
        # Simulate idle connection (no messages)
        stats = self.collector.get_websocket_stats()
        assert 'idle_connections' in stats

    def test_connection_capacity_utilization(self):
        """Test capacity utilization calculation."""
        max_capacity = 1000
        current_active = 750
        utilization = (current_active / max_capacity) * 100
        # Simulate scenario
        for _ in range(750):
            self.collector.record_connection_opened(user_type='authenticated')
        stats = self.collector.get_websocket_stats()
        assert stats['capacity_utilization'] is not None


class TestConnectionDurationMetrics(TestCase):
    """Test connection duration metrics (8 tests)."""

    def setUp(self):
        self.collector = WebSocketMetricsCollector()

    def test_record_connection_duration(self):
        """Test recording of connection duration."""
        self.collector.record_connection_closed(
            user_type='authenticated',
            duration_seconds=120.5
        )
        stats = self.collector.get_websocket_stats()
        assert stats['total_closed_connections'] > 0

    def test_avg_connection_duration(self):
        """Test average connection duration calculation."""
        durations = [30.0, 60.0, 90.0, 120.0, 150.0]
        for duration in durations:
            self.collector.record_connection_closed(
                user_type='authenticated',
                duration_seconds=duration
            )
        stats = self.collector.get_websocket_stats()
        assert 60.0 < stats['avg_connection_duration'] < 120.0

    def test_duration_percentiles(self):
        """Test connection duration percentiles."""
        for i in range(100):
            self.collector.record_connection_closed(
                user_type='authenticated',
                duration_seconds=float(i)
            )
        stats = self.collector.get_websocket_stats()
        assert stats['duration_p50'] is not None
        assert stats['duration_p95'] is not None

    def test_duration_by_user_type(self):
        """Test duration tracking by user type."""
        user_types = {
            'anonymous': 30.0,
            'authenticated': 120.0,
            'staff': 300.0
        }
        for user_type, duration in user_types.items():
            for _ in range(10):
                self.collector.record_connection_closed(
                    user_type=user_type,
                    duration_seconds=duration
                )
        stats = self.collector.get_websocket_stats()
        assert stats['avg_duration_by_user_type']['staff'] > stats['avg_duration_by_user_type']['anonymous']

    def test_short_connection_detection(self):
        """Test detection of abnormally short connections."""
        for _ in range(10):
            self.collector.record_connection_closed(
                user_type='authenticated',
                duration_seconds=0.5  # Less than 1 second
            )
        stats = self.collector.get_websocket_stats()
        assert stats['short_connections'] >= 10

    def test_max_connection_duration(self):
        """Test tracking of maximum connection duration."""
        max_duration = 3600.0  # 1 hour
        self.collector.record_connection_closed(
            user_type='authenticated',
            duration_seconds=max_duration
        )
        stats = self.collector.get_websocket_stats()
        assert stats['max_duration'] >= max_duration

    def test_duration_distribution(self):
        """Test connection duration distribution."""
        # Simulate various duration ranges
        for i in range(100):
            duration = i * 10.0  # 0 to 1000 seconds
            self.collector.record_connection_closed(
                user_type='authenticated',
                duration_seconds=duration
            )
        stats = self.collector.get_websocket_stats()
        assert stats['duration_distribution'] is not None

    def test_duration_correlation_with_messages(self):
        """Test correlation between duration and message count."""
        # Longer connections typically send more messages
        for i in range(10):
            duration = float(i * 60)
            message_count = i * 100
            self.collector.record_connection_closed(
                user_type='authenticated',
                duration_seconds=duration
            )
            for _ in range(message_count):
                self.collector.record_message_sent(user_type='authenticated')
        stats = self.collector.get_websocket_stats()
        assert stats['duration_message_correlation'] is not None


class TestMessageThroughputMetrics(TestCase):
    """Test message throughput metrics (6 tests)."""

    def setUp(self):
        self.collector = WebSocketMetricsCollector()

    def test_record_messages_sent(self):
        """Test recording of messages sent."""
        for _ in range(100):
            self.collector.record_message_sent(user_type='authenticated')
        stats = self.collector.get_websocket_stats()
        assert stats['total_messages_sent'] >= 100

    def test_record_messages_received(self):
        """Test recording of messages received."""
        for _ in range(100):
            self.collector.record_message_received(user_type='authenticated')
        stats = self.collector.get_websocket_stats()
        assert stats['total_messages_received'] >= 100

    def test_messages_per_second(self):
        """Test messages per second calculation."""
        for _ in range(500):
            self.collector.record_message_sent(user_type='authenticated')
        stats = self.collector.get_websocket_stats(window_minutes=1)
        assert stats['messages_per_second'] > 0

    def test_message_throughput_by_user_type(self):
        """Test message throughput breakdown by user type."""
        user_types = ['anonymous', 'authenticated', 'staff']
        for user_type in user_types:
            for _ in range(50):
                self.collector.record_message_sent(user_type=user_type)
        stats = self.collector.get_websocket_stats()
        assert len(stats['throughput_by_user_type']) == 3

    def test_bidirectional_message_ratio(self):
        """Test ratio of sent to received messages."""
        # Send 2x more messages than received
        for _ in range(200):
            self.collector.record_message_sent(user_type='authenticated')
        for _ in range(100):
            self.collector.record_message_received(user_type='authenticated')
        stats = self.collector.get_websocket_stats()
        assert abs(stats['message_send_receive_ratio'] - 2.0) < 0.1

    def test_peak_message_rate(self):
        """Test peak message rate tracking."""
        # Simulate burst of messages
        for _ in range(1000):
            self.collector.record_message_sent(user_type='authenticated')
        stats = self.collector.get_websocket_stats()
        assert stats['peak_message_rate'] >= 1000


class TestThrottlingMetrics(TestCase):
    """Test throttling metrics (6 tests)."""

    def setUp(self):
        self.collector = WebSocketMetricsCollector()

    def test_track_throttle_hits(self):
        """Test tracking of throttle hits."""
        for _ in range(10):
            self.collector.record_connection_attempt(
                accepted=False,
                user_type='anonymous',
                client_ip='192.168.1.100',
                rejection_reason='rate_limit_exceeded'
            )
        stats = self.collector.get_websocket_stats()
        assert stats['throttle_hits'] >= 10

    def test_throttle_hit_rate(self):
        """Test throttle hit rate calculation."""
        # 90 accepted, 10 throttled
        for i in range(100):
            self.collector.record_connection_attempt(
                accepted=i < 90,
                user_type='anonymous',
                client_ip='192.168.1.100',
                rejection_reason='rate_limit_exceeded' if i >= 90 else None
            )
        stats = self.collector.get_websocket_stats()
        assert abs(stats['throttle_rate'] - 0.10) < 0.05

    def test_throttling_by_ip(self):
        """Test throttling tracking by IP address."""
        # Single IP hitting rate limit
        for _ in range(20):
            self.collector.record_connection_attempt(
                accepted=False,
                user_type='anonymous',
                client_ip='192.168.1.100',
                rejection_reason='rate_limit_exceeded'
            )
        stats = self.collector.get_websocket_stats()
        assert '192.168.1.100' in stats['top_throttled_ips']

    def test_throttling_by_user_type(self):
        """Test throttling breakdown by user type."""
        user_types = ['anonymous', 'authenticated']
        for user_type in user_types:
            for _ in range(5):
                self.collector.record_connection_attempt(
                    accepted=False,
                    user_type=user_type,
                    client_ip='192.168.1.100',
                    rejection_reason='rate_limit_exceeded'
                )
        stats = self.collector.get_websocket_stats()
        assert len(stats['throttling_by_user_type']) == 2

    def test_throttle_effectiveness(self):
        """Test calculation of throttle effectiveness."""
        # Throttle should prevent attacks
        # 20 legitimate requests accepted
        for _ in range(20):
            self.collector.record_connection_attempt(
                accepted=True,
                user_type='authenticated',
                client_ip='192.168.1.50'
            )
        # 100 attack requests throttled
        for _ in range(100):
            self.collector.record_connection_attempt(
                accepted=False,
                user_type='anonymous',
                client_ip='192.168.1.100',
                rejection_reason='rate_limit_exceeded'
            )
        stats = self.collector.get_websocket_stats()
        assert stats['throttle_effectiveness'] > 0.80

    def test_false_positive_throttling(self):
        """Test detection of potential false positive throttling."""
        # Legitimate users getting throttled
        for _ in range(5):
            self.collector.record_connection_attempt(
                accepted=False,
                user_type='staff',  # Staff should rarely be throttled
                client_ip='192.168.1.200',
                user_id=1,
                rejection_reason='rate_limit_exceeded'
            )
        stats = self.collector.get_websocket_stats()
        assert stats['staff_throttle_hits'] >= 5
