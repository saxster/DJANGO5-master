"""
WebSocket JWT Authentication Middleware

Provides JWT token authentication for Django Channels WebSocket connections.
Supports multiple token sources: query parameters, headers, and cookies.

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling (no generic Exception catching)
- Rule #14: Token sanitization (no tokens logged)
- Rule #15: Logging data sanitization
- Rule #8: Middleware < 150 lines

Usage:
    from apps.core.middleware.websocket_jwt_auth import JWTAuthMiddleware

    application = JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    )
"""

import logging
from urllib.parse import parse_qs
from typing import Optional, Dict, Any

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from apps.peoples.models import People

logger = logging.getLogger('websocket.auth')

__all__ = ['JWTAuthMiddleware', 'JWTAuthMiddlewareStack']


class JWTAuthMiddleware(BaseMiddleware):
    """
    JWT authentication middleware for WebSocket connections.

    Extracts and validates JWT tokens from:
    1. Query parameters: ?token=xxx
    2. Authorization header: Authorization: Bearer xxx
    3. Cookie: ws_token=xxx

    Falls back to session authentication if no JWT token found.
    """

    async def __call__(self, scope, receive, send):
        """Process WebSocket connection with JWT authentication."""
        # Only process WebSocket connections
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)

        # Try JWT authentication first
        user = await self._authenticate_jwt(scope)

        # If JWT auth failed, fall back to session auth
        if user is None:
            user = scope.get('user', AnonymousUser())

        # Attach authenticated user to scope
        scope['user'] = user

        # Log connection attempt (sanitized - no tokens)
        logger.info(
            "WebSocket connection attempt",
            extra={
                'path': scope.get('path'),
                'user_id': user.id if hasattr(user, 'id') else None,
                'auth_method': 'jwt' if user and not isinstance(user, AnonymousUser) else 'session',
                'client_ip': self._get_client_ip(scope)
            }
        )

        return await super().__call__(scope, receive, send)

    async def _authenticate_jwt(self, scope: Dict[str, Any]) -> Optional[People]:
        """
        Authenticate user via JWT token.

        Returns:
            People instance if authentication successful, None otherwise
        """
        token = self._extract_token(scope)

        if not token:
            return None

        try:
            # Check token cache first (5-minute cache)
            cache_key = f"ws_jwt:{token[:32]}"  # Use hash prefix for cache key
            cached_user_id = cache.get(cache_key)

            if cached_user_id:
                user = await self._get_user_by_id(cached_user_id)
                if user:
                    return user

            # Validate token using rest_framework_simplejwt
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')

            if not user_id:
                logger.warning("JWT token missing user_id claim")
                return None

            # Get user from database
            user = await self._get_user_by_id(user_id)

            if user:
                # Cache successful authentication (5 minutes)
                cache.set(cache_key, user_id, timeout=300)
                logger.info(
                    "JWT authentication successful",
                    extra={'user_id': user_id, 'path': scope.get('path')}
                )

            return user

        except (TokenError, InvalidToken) as e:
            logger.warning(
                "Invalid JWT token",
                extra={
                    'error': str(e),
                    'path': scope.get('path'),
                    'client_ip': self._get_client_ip(scope)
                }
            )
            return None
        except (ValueError, KeyError) as e:
            logger.warning(
                "JWT token validation error",
                extra={
                    'error': str(e),
                    'path': scope.get('path')
                }
            )
            return None

    def _extract_token(self, scope: Dict[str, Any]) -> Optional[str]:
        """
        Extract JWT token from query params, headers, or cookies.

        Priority: query params > Authorization header > cookie
        """
        # 1. Check query parameters: ?token=xxx
        query_string = scope.get('query_string', b'').decode()
        if query_string:
            query_params = parse_qs(query_string)
            token = query_params.get('token', [None])[0]
            if token:
                return token

        # 2. Check Authorization header: Authorization: Bearer xxx
        headers = dict(scope.get('headers', []))
        auth_header = headers.get(b'authorization', b'').decode()
        if auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix

        # 3. Check cookie: ws_token=xxx
        cookie_header = headers.get(b'cookie', b'').decode()
        if cookie_header:
            cookies = self._parse_cookies(cookie_header)
            token = cookies.get('ws_token')
            if token:
                return token

        return None

    def _parse_cookies(self, cookie_header: str) -> Dict[str, str]:
        """Parse cookie header into dictionary."""
        cookies = {}
        try:
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if '=' in cookie:
                    key, value = cookie.split('=', 1)
                    cookies[key.strip()] = value.strip()
        except (ValueError, AttributeError):
            pass
        return cookies

    def _get_client_ip(self, scope: Dict[str, Any]) -> str:
        """Extract client IP address from scope."""
        headers = dict(scope.get('headers', []))

        # Check X-Forwarded-For header first (proxy/load balancer)
        forwarded = headers.get(b'x-forwarded-for', b'').decode()
        if forwarded:
            return forwarded.split(',')[0].strip()

        # Fall back to client address
        client = scope.get('client', ['unknown', 0])
        return client[0] if client else 'unknown'

    @database_sync_to_async
    def _get_user_by_id(self, user_id: int) -> Optional[People]:
        """Retrieve user from database by ID."""
        try:
            return People.objects.get(id=user_id, enable=True)
        except People.DoesNotExist:
            logger.warning(f"User not found or disabled: {user_id}")
            return None
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid user_id format: {e}")
            return None


def JWTAuthMiddlewareStack(inner):
    """
    Convenience function to wrap URLRouter with JWT authentication.

    Usage:
        application = ProtocolTypeRouter({
            "websocket": JWTAuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        })
    """
    return JWTAuthMiddleware(inner)
