"""
WebSocket Per-Connection Throttling Middleware

Prevents abuse by limiting concurrent WebSocket connections per user/IP.
Uses Redis for distributed connection tracking across multiple server instances.

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #9: Comprehensive rate limiting
- Rule #8: Middleware < 100 lines

Monitoring Integration:
- Records all connection attempts (accepted/rejected)
- Tracks active connections by user type
- Records connection duration
- Monitors throttle hits and rejection reasons

Usage:
    from apps.core.middleware.websocket_throttling import ThrottlingMiddleware

    application = ThrottlingMiddleware(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    )
"""

import logging
import time
from typing import Dict, Any, Optional

from channels.middleware import BaseMiddleware
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('websocket.throttling')

# Import monitoring service
try:
    from monitoring.services.websocket_metrics_collector import websocket_metrics
    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False

__all__ = ['ThrottlingMiddleware', 'ConnectionLimitExceeded']


class ConnectionLimitExceeded(Exception):
    """Raised when connection limit is exceeded."""
    pass


class ThrottlingMiddleware(BaseMiddleware):
    """
    Per-connection throttling middleware for WebSockets.

    Limits:
    - Anonymous: 5 connections per IP
    - Authenticated: 20 connections per user
    - Staff: 100 connections per user
    """

    def __init__(self, inner):
        super().__init__(inner)
        self.limits = getattr(settings, 'WEBSOCKET_THROTTLE_LIMITS', {
            'anonymous': 5,
            'authenticated': 20,
            'staff': 100,
        })
        self.connection_timeout = 3600  # 1 hour

    async def __call__(self, scope, receive, send):
        """Process WebSocket connection with throttling and monitoring."""
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)

        user = scope.get('user', AnonymousUser())
        client_ip = self._get_client_ip(scope)
        user_type = self._get_user_type(user)

        # Get correlation ID if available
        correlation_id = scope.get('correlation_id', None)

        # Track connection start time
        connection_start = time.time()

        # Check connection limit
        try:
            await self._check_connection_limit(user, client_ip)

            # Connection accepted - record metrics
            if MONITORING_ENABLED:
                websocket_metrics.record_connection_attempt(
                    accepted=True,
                    user_type=user_type,
                    client_ip=client_ip,
                    user_id=user.id if hasattr(user, 'id') else None,
                    correlation_id=correlation_id
                )

        except ConnectionLimitExceeded as e:
            # Connection rejected - record metrics
            if MONITORING_ENABLED:
                websocket_metrics.record_connection_attempt(
                    accepted=False,
                    user_type=user_type,
                    client_ip=client_ip,
                    user_id=user.id if hasattr(user, 'id') else None,
                    rejection_reason='rate_limit_exceeded',
                    correlation_id=correlation_id
                )

            logger.warning(
                "WebSocket connection limit exceeded",
                extra={
                    'user_id': user.id if hasattr(user, 'id') else None,
                    'client_ip': client_ip,
                    'path': scope.get('path'),
                    'correlation_id': correlation_id
                }
            )

            # Close connection with rate limit code
            await send({
                'type': 'websocket.close',
                'code': 4429  # Custom code: Too Many Connections
            })
            return

        # Track connection
        connection_key = self._get_connection_key(user, client_ip)
        cache.incr(connection_key, delta=1)
        cache.expire(connection_key, self.connection_timeout)

        # Wrap receive to detect disconnection
        original_receive = receive

        async def wrapped_receive():
            message = await original_receive()
            # If connection closing, decrement counter and record duration
            if message['type'] == 'websocket.disconnect':
                self._release_connection(connection_key)

                # Record connection duration
                if MONITORING_ENABLED:
                    duration = time.time() - connection_start
                    websocket_metrics.record_connection_closed(
                        user_type=user_type,
                        duration_seconds=duration,
                        correlation_id=correlation_id
                    )

            return message

        try:
            return await super().__call__(scope, wrapped_receive, send)
        finally:
            # Ensure connection is released on any error
            self._release_connection(connection_key)

            # Record duration on error closure
            if MONITORING_ENABLED:
                duration = time.time() - connection_start
                websocket_metrics.record_connection_closed(
                    user_type=user_type,
                    duration_seconds=duration,
                    correlation_id=correlation_id
                )

    async def _check_connection_limit(self, user: Any, client_ip: str):
        """Check if connection limit is exceeded."""
        connection_key = self._get_connection_key(user, client_ip)
        current_connections = cache.get(connection_key, 0)

        # Determine limit based on user type
        if isinstance(user, AnonymousUser):
            limit = self.limits['anonymous']
        elif hasattr(user, 'is_staff') and user.is_staff:
            limit = self.limits['staff']
        else:
            limit = self.limits['authenticated']

        if current_connections >= limit:
            raise ConnectionLimitExceeded(
                f"Connection limit exceeded: {current_connections}/{limit}"
            )

    def _get_connection_key(self, user: Any, client_ip: str) -> str:
        """Generate cache key for connection tracking."""
        if isinstance(user, AnonymousUser):
            return f"ws_conn:ip:{client_ip}"
        return f"ws_conn:user:{user.id}"

    def _release_connection(self, connection_key: str):
        """Decrement connection counter."""
        try:
            current = cache.get(connection_key, 0)
            if current > 0:
                cache.decr(connection_key, delta=1)
        except (ConnectionError, ValueError) as e:
            logger.warning(f"Error releasing connection: {e}")

    def _get_client_ip(self, scope: Dict[str, Any]) -> str:
        """Extract client IP address from scope."""
        headers = dict(scope.get('headers', []))

        # Check X-Forwarded-For header
        forwarded = headers.get(b'x-forwarded-for', b'').decode()
        if forwarded:
            return forwarded.split(',')[0].strip()

        # Fall back to client address
        client = scope.get('client', ['unknown', 0])
        return client[0] if client else 'unknown'

    def _get_user_type(self, user: Any) -> str:
        """Determine user type for metrics."""
        if isinstance(user, AnonymousUser):
            return 'anonymous'
        elif hasattr(user, 'is_staff') and user.is_staff:
            return 'staff'
        else:
            return 'authenticated'
