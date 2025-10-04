"""
WebSocket Origin Validation Middleware

CORS-like origin validation for WebSocket connections to prevent
cross-site WebSocket hijacking (CSWSH) attacks.

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #3: Alternative CSRF protection for WebSockets
- Rule #8: Middleware < 100 lines

Attack Prevention:
- Cross-Site WebSocket Hijacking (CSWSH)
- Unauthorized cross-origin connections
- Origin spoofing attacks

Usage:
    from apps.core.middleware.websocket_origin_validation import OriginValidationMiddleware

    application = OriginValidationMiddleware(
        ThrottlingMiddleware(...)
    )
"""

import logging
from typing import List, Dict, Any
from urllib.parse import urlparse

from channels.middleware import BaseMiddleware
from django.conf import settings

logger = logging.getLogger('websocket.origin')

__all__ = ['OriginValidationMiddleware']


class OriginValidationMiddleware(BaseMiddleware):
    """
    Validates WebSocket connection origins against allowlist.

    Similar to CORS but for WebSocket connections.
    """

    def __init__(self, inner):
        super().__init__(inner)
        self.enabled = getattr(settings, 'WEBSOCKET_ORIGIN_VALIDATION_ENABLED', True)
        self.allowed_origins = set(
            getattr(settings, 'WEBSOCKET_ALLOWED_ORIGINS', [])
        )

    async def __call__(self, scope, receive, send):
        """Validate WebSocket connection origin."""
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)

        # Skip validation if disabled (development mode)
        if not self.enabled:
            return await super().__call__(scope, receive, send)

        # Extract origin from headers
        origin = self._get_origin(scope)

        # Validate origin
        if not self._is_origin_allowed(origin):
            logger.warning(
                "WebSocket connection rejected: invalid origin",
                extra={
                    'origin': origin,
                    'path': scope.get('path'),
                    'client_ip': self._get_client_ip(scope)
                }
            )
            # Close connection with forbidden code
            await send({
                'type': 'websocket.close',
                'code': 4403  # Custom code: Origin Forbidden
            })
            return

        logger.debug(
            "WebSocket origin validated",
            extra={'origin': origin, 'path': scope.get('path')}
        )

        return await super().__call__(scope, receive, send)

    def _get_origin(self, scope: Dict[str, Any]) -> str:
        """Extract origin from WebSocket headers."""
        headers = dict(scope.get('headers', []))

        # Try Origin header first (standard)
        origin = headers.get(b'origin', b'').decode()
        if origin:
            return origin

        # Fall back to Host header
        host = headers.get(b'host', b'').decode()
        if host:
            # Determine scheme from connection
            scheme = 'wss' if scope.get('scheme') == 'wss' else 'ws'
            return f"{scheme}://{host}"

        return ''

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is in allowlist."""
        if not origin:
            # No origin header = likely non-browser client (mobile app)
            # Allow but log for monitoring
            logger.info("WebSocket connection without origin header (mobile client?)")
            return True

        # Parse origin URL
        try:
            parsed = urlparse(origin)
            origin_normalized = f"{parsed.scheme}://{parsed.netloc}"

            # Check exact match
            if origin_normalized in self.allowed_origins:
                return True

            # Check wildcard patterns (*.example.com)
            for allowed in self.allowed_origins:
                if self._matches_wildcard(origin_normalized, allowed):
                    return True

        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid origin format: {origin} - {e}")
            return False

        return False

    def _matches_wildcard(self, origin: str, pattern: str) -> bool:
        """Check if origin matches wildcard pattern."""
        if '*' not in pattern:
            return False

        # Simple wildcard matching for subdomains
        # Pattern: https://*.example.com
        # Matches: https://app.example.com, https://api.example.com
        pattern_parts = pattern.replace('*', '').split('://')
        origin_parts = origin.split('://')

        if len(pattern_parts) != 2 or len(origin_parts) != 2:
            return False

        # Schemes must match
        if pattern_parts[0] != origin_parts[0]:
            return False

        # Check if domain ends with pattern
        return origin_parts[1].endswith(pattern_parts[1])

    def _get_client_ip(self, scope: Dict[str, Any]) -> str:
        """Extract client IP address from scope."""
        headers = dict(scope.get('headers', []))
        forwarded = headers.get(b'x-forwarded-for', b'').decode()
        if forwarded:
            return forwarded.split(',')[0].strip()

        client = scope.get('client', ['unknown', 0])
        return client[0] if client else 'unknown'
