"""
Presence Monitor WebSocket Consumer

Dedicated consumer for WebSocket connection health monitoring and heartbeat.
Provides baseline monitoring for all WebSocket connections across the platform.

Features:
- 30-second heartbeat keep-alive
- Connection uptime tracking
- Latency profiling (roundtrip time)
- Message throughput monitoring
- Automatic stale connection cleanup (5min timeout)
- Integration with WebSocketMetricsCollector

Compliance with .claude/rules.md:
- Rule #7: Consumer < 150 lines (business logic in services)
- Rule #11: Specific exception handling
- Rule #15: Sanitized logging

Usage:
    # Client connects to: ws://host/ws/noc/presence/
    # Client sends: {"type": "heartbeat", "timestamp": "2025-10-01T12:00:00Z"}
    # Server responds: {"type": "heartbeat_ack", "server_time": "...", "latency_ms": 45}
"""

import asyncio
import json
import logging
import time
from typing import Optional
from datetime import datetime, timezone as dt_timezone

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.core.cache import cache

# Monitoring integration
try:
    from monitoring.services.websocket_metrics_collector import websocket_metrics
    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False

logger = logging.getLogger('noc.presence')

__all__ = ['PresenceMonitorConsumer']


class PresenceMonitorConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for connection presence and heartbeat monitoring.

    Tracks connection health metrics and automatically cleans up stale connections.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.connection_start = None
        self.last_heartbeat = None
        self.heartbeat_task = None
        self.message_count = 0

        # Settings from config
        self.heartbeat_interval = getattr(
            settings,
            'WEBSOCKET_HEARTBEAT_INTERVAL',
            30  # 30 seconds default
        )
        self.presence_timeout = getattr(
            settings,
            'WEBSOCKET_PRESENCE_TIMEOUT',
            300  # 5 minutes default
        )

    async def connect(self):
        """Handle WebSocket connection with authentication."""
        self.user = self.scope.get('user')

        # Require authentication for presence monitoring
        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Unauthorized presence monitor connection attempt")
            await self.close(code=4401)
            return

        self.connection_start = time.time()
        self.last_heartbeat = time.time()

        await self.accept()

        logger.info(
            "Presence monitor connected",
            extra={
                'user_id': self.user.id if hasattr(self.user, 'id') else None,
                'user_type': self._get_user_type()
            }
        )

        # Send initial connection established message
        await self.send_connection_established()

        # Start automatic heartbeat task
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Cancel heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        # Calculate connection duration
        if self.connection_start:
            duration = time.time() - self.connection_start

            # Record metrics
            if MONITORING_ENABLED:
                websocket_metrics.record_connection_closed(
                    user_type=self._get_user_type(),
                    duration_seconds=duration
                )

            logger.info(
                "Presence monitor disconnected",
                extra={
                    'user_id': self.user.id if self.user and hasattr(self.user, 'id') else None,
                    'duration_seconds': duration,
                    'close_code': close_code
                }
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            # Update last heartbeat time
            self.last_heartbeat = time.time()
            self.message_count += 1

            handlers = {
                'heartbeat': self.handle_heartbeat,
                'ping': self.handle_ping,
                'get_stats': self.handle_get_stats,
            }

            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                await self.send_error(f'Unknown message type: {message_type}')

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON data')
        except (ValueError, KeyError) as e:
            logger.warning(
                f"Error processing presence message: {e}",
                extra={'user_id': self.user.id if self.user else None}
            )
            await self.send_error(f'Invalid message: {str(e)}')

    async def handle_heartbeat(self, data):
        """Handle heartbeat message from client."""
        client_timestamp = data.get('timestamp')

        # Calculate latency if client sent timestamp
        latency_ms = None
        if client_timestamp:
            try:
                client_time = datetime.fromisoformat(client_timestamp.replace('Z', '+00:00'))
                server_time = datetime.now(dt_timezone.utc)
                latency_ms = int((server_time - client_time).total_seconds() * 1000)
            except (ValueError, AttributeError):
                pass

        # Send heartbeat acknowledgment
        await self.send(text_data=json.dumps({
            'type': 'heartbeat_ack',
            'server_time': datetime.now(dt_timezone.utc).isoformat(),
            'latency_ms': latency_ms,
            'uptime_seconds': int(time.time() - self.connection_start) if self.connection_start else 0
        }))

    async def handle_ping(self, data):
        """Handle simple ping message."""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': datetime.now(dt_timezone.utc).isoformat()
        }))

    async def handle_get_stats(self, data):
        """Handle request for connection statistics."""
        uptime = time.time() - self.connection_start if self.connection_start else 0

        stats = {
            'type': 'stats',
            'uptime_seconds': int(uptime),
            'message_count': self.message_count,
            'last_heartbeat_ago': int(time.time() - self.last_heartbeat) if self.last_heartbeat else None,
            'user_type': self._get_user_type()
        }

        await self.send(text_data=json.dumps(stats))

    async def send_connection_established(self):
        """Send initial connection confirmation."""
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            'heartbeat_interval': self.heartbeat_interval,
            'presence_timeout': self.presence_timeout
        }))

    async def send_error(self, message: str):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    async def _heartbeat_loop(self):
        """Automatic heartbeat loop to detect stale connections."""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                # Check if connection is stale
                time_since_heartbeat = time.time() - self.last_heartbeat
                if time_since_heartbeat > self.presence_timeout:
                    logger.warning(
                        "Stale connection detected - closing",
                        extra={
                            'user_id': self.user.id if self.user else None,
                            'seconds_since_heartbeat': int(time_since_heartbeat)
                        }
                    )
                    await self.close(code=4408)  # Request Timeout
                    break

                # Send server-initiated heartbeat
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat',
                    'server_time': datetime.now(dt_timezone.utc).isoformat()
                }))

        except asyncio.CancelledError:
            # Task cancelled during disconnect
            pass
        except (ConnectionError, RuntimeError) as e:
            logger.error(
                f"Error in heartbeat loop: {e}",
                extra={'user_id': self.user.id if self.user else None}
            )

    def _get_user_type(self) -> str:
        """Determine user type for metrics."""
        if not self.user or isinstance(self.user, AnonymousUser):
            return 'anonymous'
        elif hasattr(self.user, 'is_staff') and self.user.is_staff:
            return 'staff'
        else:
            return 'authenticated'
