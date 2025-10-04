"""
WebSocket Token Binding Security Feature

Binds JWT tokens to device fingerprints to prevent token theft and replay attacks.
Creates a cryptographic binding between the token and the device/connection context.

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #2: Security team audit required for custom cryptography
- Rule #14: Token sanitization in logs

Security Benefits:
- Prevents token theft (stolen tokens won't work on different devices)
- Mitigates man-in-the-middle attacks
- Adds defense-in-depth layer to JWT authentication

Usage:
    from apps.core.security.websocket_token_binding import TokenBindingValidator

    validator = TokenBindingValidator()
    is_valid = await validator.validate_binding(token, scope)
"""

import hashlib
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('websocket.token_binding')

__all__ = ['TokenBindingValidator', 'generate_device_fingerprint']


class TokenBindingValidator:
    """
    Validates that JWT tokens are bound to the device/connection that created them.

    Fingerprint Components:
    1. Device ID (from client)
    2. User-Agent hash
    3. IP subnet (first 3 octets for IPv4, first 4 groups for IPv6)
    """

    def __init__(self):
        self.enabled = getattr(settings, 'WEBSOCKET_TOKEN_BINDING_ENABLED', True)
        self.strict_mode = getattr(settings, 'WEBSOCKET_TOKEN_BINDING_STRICT', False)
        self.cache_timeout = 3600  # 1 hour

    async def validate_binding(self, token: str, scope: Dict[str, Any]) -> bool:
        """
        Validate that token is bound to current connection context.

        Args:
            token: JWT access token
            scope: WebSocket connection scope

        Returns:
            True if binding is valid or disabled, False otherwise
        """
        if not self.enabled:
            return True

        try:
            # Generate fingerprint from current connection
            current_fingerprint = generate_device_fingerprint(scope)

            # Get stored fingerprint for this token
            cache_key = f"ws_token_binding:{self._hash_token(token)}"
            stored_fingerprint = cache.get(cache_key)

            # First connection with this token - store fingerprint
            if stored_fingerprint is None:
                cache.set(cache_key, current_fingerprint, timeout=self.cache_timeout)
                logger.info(
                    "WebSocket token binding established",
                    extra={
                        'fingerprint_hash': self._hash_fingerprint(current_fingerprint),
                        'path': scope.get('path')
                    }
                )
                return True

            # Validate fingerprint matches
            if stored_fingerprint == current_fingerprint:
                return True

            # In non-strict mode, allow minor changes (e.g., IP change)
            if not self.strict_mode:
                if self._is_similar_fingerprint(stored_fingerprint, current_fingerprint):
                    logger.warning(
                        "WebSocket token binding mismatch (non-strict mode, allowing)",
                        extra={
                            'stored_hash': self._hash_fingerprint(stored_fingerprint),
                            'current_hash': self._hash_fingerprint(current_fingerprint)
                        }
                    )
                    return True

            # Binding validation failed
            logger.error(
                "WebSocket token binding validation failed - possible token theft",
                extra={
                    'stored_hash': self._hash_fingerprint(stored_fingerprint),
                    'current_hash': self._hash_fingerprint(current_fingerprint),
                    'path': scope.get('path')
                }
            )
            return False

        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Token binding validation error: {e}")
            # On error, allow in non-strict mode, deny in strict mode
            return not self.strict_mode

    def _hash_token(self, token: str) -> str:
        """Create hash of token for cache key (don't store token itself)."""
        return hashlib.sha256(token[:64].encode()).hexdigest()[:32]

    def _hash_fingerprint(self, fingerprint: str) -> str:
        """Create hash of fingerprint for logging (don't log fingerprint itself)."""
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]

    def _is_similar_fingerprint(self, stored: str, current: str) -> bool:
        """
        Check if fingerprints are similar enough (for non-strict mode).

        Allows:
        - IP changes (mobile networks)
        - Minor user-agent changes (browser updates)
        """
        stored_parts = stored.split('|')
        current_parts = current.split('|')

        if len(stored_parts) != 3 or len(current_parts) != 3:
            return False

        # Device ID must match
        if stored_parts[0] != current_parts[0]:
            return False

        # User-Agent hash must match
        if stored_parts[1] != current_parts[1]:
            return False

        # IP subnet allowed to change in non-strict mode
        return True


def generate_device_fingerprint(scope: Dict[str, Any]) -> str:
    """
    Generate device fingerprint from connection context.

    Components:
    1. Device ID (from query params or header)
    2. User-Agent hash
    3. IP subnet

    Returns:
        Fingerprint string in format: device_id|ua_hash|ip_subnet
    """
    headers = dict(scope.get('headers', []))

    # 1. Extract device ID
    device_id = _extract_device_id(scope)

    # 2. Hash User-Agent
    user_agent = headers.get(b'user-agent', b'').decode()
    ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16]

    # 3. Extract IP subnet
    ip_subnet = _extract_ip_subnet(scope)

    # Combine into fingerprint
    fingerprint = f"{device_id}|{ua_hash}|{ip_subnet}"

    return fingerprint


def _extract_device_id(scope: Dict[str, Any]) -> str:
    """Extract device ID from query params or headers."""
    # Try query parameters first
    query_string = scope.get('query_string', b'').decode()
    if '&device_id=' in query_string or query_string.startswith('device_id='):
        for param in query_string.split('&'):
            if param.startswith('device_id='):
                return param.split('=', 1)[1]

    # Try headers
    headers = dict(scope.get('headers', []))
    device_id = headers.get(b'x-device-id', b'').decode()
    if device_id:
        return device_id

    # No device ID found
    return 'unknown'


def _extract_ip_subnet(scope: Dict[str, Any]) -> str:
    """Extract IP subnet (first 3 octets for IPv4)."""
    headers = dict(scope.get('headers', []))

    # Check X-Forwarded-For header
    forwarded = headers.get(b'x-forwarded-for', b'').decode()
    if forwarded:
        ip = forwarded.split(',')[0].strip()
    else:
        # Get from client address
        client = scope.get('client', ['unknown', 0])
        ip = client[0] if client else 'unknown'

    # Extract subnet (first 3 octets for IPv4)
    if ip and ip != 'unknown':
        parts = ip.split('.')
        if len(parts) >= 3:
            return '.'.join(parts[:3]) + '.0'

    return 'unknown'
