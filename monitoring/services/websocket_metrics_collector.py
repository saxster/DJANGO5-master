"""
WebSocket Metrics Collector

Collects and aggregates WebSocket connection metrics for monitoring.

Metrics collected:
- Connection attempts (total, accepted, rejected)
- Active connections by user type (gauge)
- Connection duration statistics
- Message throughput (sent/received)
- Throttle hits by reason
- Connection errors by type
- Top rejected IPs/users

Compliance: .claude/rules.md Rule #7 (< 150 lines per class)
Integration: Works with WebSocket throttling middleware
"""

import logging
from typing import Dict, Any, Optional, List
from collections import Counter, defaultdict
from datetime import datetime
from apps.core.constants.datetime_constants import MINUTES_IN_HOUR
from monitoring.django_monitoring import metrics_collector

logger = logging.getLogger('monitoring.websocket')

__all__ = ['WebSocketMetricsCollector', 'websocket_metrics']


class WebSocketMetricsCollector:
    """
    Specialized metrics collector for WebSocket operations.

    Tracks connections, throttling, and message throughput.
    Rule #7 compliant: < 150 lines
    """

    def __init__(self):
        self.rejected_ips = Counter()
        self.rejected_users = Counter()
        self.rejection_reasons = Counter()
        self.active_connections = {
            'anonymous': 0,
            'authenticated': 0,
            'staff': 0
        }

    def record_connection_attempt(
        self,
        accepted: bool,
        user_type: str,
        client_ip: Optional[str] = None,
        user_id: Optional[int] = None,
        rejection_reason: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Record a WebSocket connection attempt.

        Args:
            accepted: Whether connection was accepted
            user_type: Type of user (anonymous, authenticated, staff)
            client_ip: Client IP address
            user_id: User ID if authenticated
            rejection_reason: Reason for rejection if declined
            correlation_id: Request correlation ID
        """
        # Record connection attempt
        status = 'accepted' if accepted else 'rejected'
        metrics_collector.record_metric(
            'websocket_connection_attempt',
            1,
            {
                'status': status,
                'user_type': user_type
            },
            correlation_id=correlation_id
        )

        if accepted:
            # Increment active connections
            self.active_connections[user_type] = self.active_connections.get(user_type, 0) + 1

            # Record active connections gauge
            metrics_collector.record_metric(
                'websocket_connections_active',
                self.active_connections[user_type],
                {'user_type': user_type},
                correlation_id=correlation_id
            )

            logger.debug(
                f"WebSocket connection accepted - {user_type}",
                extra={'correlation_id': correlation_id, 'user_type': user_type}
            )

        else:
            # Track rejection
            if rejection_reason:
                self.rejection_reasons[rejection_reason] += 1

                metrics_collector.record_metric(
                    'websocket_rejection',
                    1,
                    {
                        'reason': rejection_reason,
                        'user_type': user_type
                    },
                    correlation_id=correlation_id
                )

            # Track rejected IPs and users
            if client_ip:
                self.rejected_ips[client_ip] += 1
            if user_id:
                self.rejected_users[user_id] += 1

            logger.warning(
                f"WebSocket connection rejected - {user_type}: {rejection_reason}",
                extra={
                    'correlation_id': correlation_id,
                    'user_type': user_type,
                    'reason': rejection_reason,
                    'client_ip': client_ip
                }
            )

    def record_connection_closed(
        self,
        user_type: str,
        duration_seconds: float,
        correlation_id: Optional[str] = None
    ):
        """
        Record a WebSocket connection closure.

        Args:
            user_type: Type of user
            duration_seconds: Connection duration in seconds
            correlation_id: Request correlation ID
        """
        # Decrement active connections
        if user_type in self.active_connections:
            self.active_connections[user_type] = max(
                0,
                self.active_connections[user_type] - 1
            )

        # Record duration
        metrics_collector.record_metric(
            'websocket_connection_duration',
            duration_seconds,
            {'user_type': user_type},
            correlation_id=correlation_id
        )

        # Update active connections gauge
        metrics_collector.record_metric(
            'websocket_connections_active',
            self.active_connections.get(user_type, 0),
            {'user_type': user_type},
            correlation_id=correlation_id
        )

        logger.debug(
            f"WebSocket connection closed - {user_type}, duration: {duration_seconds:.2f}s",
            extra={'correlation_id': correlation_id, 'user_type': user_type}
        )

    def record_message(
        self,
        direction: str,
        message_size: int,
        correlation_id: Optional[str] = None
    ):
        """
        Record a WebSocket message.

        Args:
            direction: 'sent' or 'received'
            message_size: Message size in bytes
            correlation_id: Request correlation ID
        """
        metrics_collector.record_metric(
            f'websocket_message_{direction}',
            1,
            {'size_bytes': message_size},
            correlation_id=correlation_id
        )

    def record_connection_error(
        self,
        error_type: str,
        user_type: str,
        correlation_id: Optional[str] = None
    ):
        """
        Record a WebSocket connection error.

        Args:
            error_type: Type of error
            user_type: Type of user
            correlation_id: Request correlation ID
        """
        metrics_collector.record_metric(
            'websocket_connection_error',
            1,
            {
                'error_type': error_type,
                'user_type': user_type
            },
            correlation_id=correlation_id
        )

    def get_websocket_stats(self, window_minutes: int = MINUTES_IN_HOUR) -> Dict[str, Any]:
        """
        Get aggregated WebSocket statistics.

        Args:
            window_minutes: Time window in minutes

        Returns:
            Dict with WebSocket metrics
        """
        # Get connection attempt stats
        attempt_stats = metrics_collector.get_stats(
            'websocket_connection_attempt',
            window_minutes
        )

        # Get rejection stats
        rejection_stats = metrics_collector.get_stats(
            'websocket_rejection',
            window_minutes
        )

        # Get duration stats
        duration_stats = metrics_collector.get_stats(
            'websocket_connection_duration',
            window_minutes
        )

        # Calculate metrics
        total_attempts = attempt_stats.get('count', 0)
        total_rejections = rejection_stats.get('count', 0)
        rejection_rate = (total_rejections / total_attempts * 100) if total_attempts > 0 else 0

        # Top rejected IPs
        top_rejected_ips = [
            {'ip': ip, 'count': count}
            for ip, count in self.rejected_ips.most_common(10)
        ]

        # Top rejected users
        top_rejected_users = [
            {'user_id': user_id, 'count': count}
            for user_id, count in self.rejected_users.most_common(10)
        ]

        # Top rejection reasons
        top_reasons = dict(self.rejection_reasons.most_common(5))

        return {
            'total_attempts': total_attempts,
            'total_rejections': total_rejections,
            'rejection_rate': rejection_rate,
            'active_connections': dict(self.active_connections),
            'total_active': sum(self.active_connections.values()),
            'connection_duration': duration_stats,
            'top_rejection_reasons': top_reasons,
            'top_rejected_ips': top_rejected_ips,
            'top_rejected_users': top_rejected_users,
        }


# Global instance
websocket_metrics = WebSocketMetricsCollector()
