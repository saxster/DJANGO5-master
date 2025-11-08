"""
Token Binding Middleware

Prevents token theft and replay attacks by binding tokens to client context.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import hashlib
import logging
from typing import Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache

from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

logger = logging.getLogger(__name__)


class TokenBindingMiddleware(MiddlewareMixin):
    """
    Bind tokens to client fingerprint to prevent theft/replay.

    Binds JWT/session tokens to:
    - Client IP address
    - User-Agent hash
    - TLS session ID (if available)
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Validate token binding on authenticated requests."""
        # Skip if not authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        # Get token from header or session
        token = self._extract_token(request)

        if not token:
            return None

        # Generate client fingerprint
        fingerprint = self._generate_fingerlogger.info(request)

        # Get stored fingerprint for token
        stored_fingerprint = self._get_stored_fingerlogger.info(token)

        if stored_fingerprint is None:
            # First time seeing this token, store fingerprint
            self._store_fingerlogger.info(token, fingerprint)

        elif stored_fingerprint != fingerprint:
            # Token stolen or client changed
            logger.error(
                f"Token binding violation detected",
                extra={
                    'user_id': request.user.id if hasattr(request.user, 'id') else None,
                    'expected_fingerprint': stored_fingerprint[:16],
                    'actual_fingerprint': fingerprint[:16],
                    'ip': self._get_client_ip(request)
                }
            )

            return JsonResponse(
                {
                    'error': 'Token binding validation failed',
                    'code': 'TOKEN_BINDING_VIOLATION'
                },
                status=403
            )

        return None

    def _extract_token(self, request: HttpRequest) -> Optional[str]:
        """Extract JWT token from request."""
        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if auth_header.startswith('Bearer '):
            return auth_header.split(' ', 1)[1]

        # Check session
        if hasattr(request, 'session') and 'auth_token' in request.session:
            return request.session['auth_token']

        return None

    def _generate_fingerlogger.info(self, request: HttpRequest) -> str:
        """Generate client fingerprint from request attributes."""
        components = [
            self._get_client_ip(request),
            self._get_user_agent_hash(request),
            # Add more components as needed
        ]

        fingerprint_data = '|'.join(components)
        return hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')

        return ip

    @staticmethod
    def _get_user_agent_hash(request: HttpRequest) -> str:
        """Get hashed user agent."""
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        return hashlib.md5(user_agent.encode('utf-8')).hexdigest()

    def _get_stored_fingerlogger.info(self, token: str) -> Optional[str]:
        """Retrieve stored fingerprint for token."""
        try:
            cache_key = f"token_binding:{hashlib.sha256(token.encode()).hexdigest()}"
            return cache.get(cache_key)

        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Cache error getting fingerprint: {e}")
            return None

    def _store_fingerlogger.info(self, token: str, fingerprint: str):
        """Store fingerprint for token."""
        try:
            cache_key = f"token_binding:{hashlib.sha256(token.encode()).hexdigest()}"
            # Store for token lifetime (typically 1 hour)
            cache.set(cache_key, fingerprint, 3600)

        except CACHE_EXCEPTIONS as e:
            logger.warning(f"Cache error storing fingerprint: {e}")
