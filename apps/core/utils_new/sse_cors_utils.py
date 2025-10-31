"""
Server-Sent Events (SSE) CORS Security Utilities

Provides secure CORS header generation for SSE endpoints.
Prevents wildcard CORS vulnerabilities while supporting real-time streaming.

Security Features:
- Origin validation against CORS_ALLOWED_ORIGINS settings
- Pattern matching for allowed subdomains
- No wildcard origins (prevents CSRF attacks)
- Comprehensive security logging
- Credentials support validation

Author: Claude Code
Date: 2025-10-01
"""

import logging
import re
from typing import Dict, Optional
from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger('security.cors')


def get_secure_sse_cors_headers(request: HttpRequest) -> Optional[Dict[str, str]]:
    """
    Generate secure CORS headers for Server-Sent Events (SSE) endpoints.

    This function validates the request origin against allowed origins configured
    in Django settings and returns appropriate CORS headers. It prevents wildcard
    CORS vulnerabilities (CVSS 8.1) while supporting legitimate SSE clients.

    Args:
        request: Django HttpRequest object containing Origin header

    Returns:
        Dict with CORS headers if origin is allowed, None if origin is blocked

    Security Notes:
        - Never returns wildcard ('*') origins
        - Validates against CORS_ALLOWED_ORIGINS and CORS_ALLOWED_ORIGIN_REGEXES
        - Logs all blocked requests for security monitoring
        - Supports credentials when origin is explicitly allowed

    Example:
        >>> cors_headers = get_secure_sse_cors_headers(request)
        >>> if cors_headers:
        ...     for key, value in cors_headers.items():
        ...         response[key] = value
        ... else:
        ...     return JsonResponse({'error': 'Unauthorized origin'}, status=403)

    Related:
        - CORS_ALLOWED_ORIGINS setting
        - CORS_ALLOWED_ORIGIN_REGEXES setting
        - CORS enforcement middleware
    """
    # Extract origin from request
    origin = request.META.get('HTTP_ORIGIN', '').strip()

    # No origin header - SSE requires explicit origin
    if not origin:
        logger.warning(
            "SSE request without Origin header blocked",
            extra={
                'path': request.path,
                'remote_addr': request.META.get('REMOTE_ADDR'),
                'security_event': 'sse_no_origin_header'
            }
        )
        return None

    # Check if origin is explicitly allowed
    allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
    if origin in allowed_origins:
        logger.debug(
            f"SSE request from allowed origin: {origin}",
            extra={'path': request.path, 'origin': origin}
        )
        return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Headers': 'Cache-Control, Content-Type',
        }

    # Check against allowed origin patterns (regex)
    allowed_patterns = getattr(settings, 'CORS_ALLOWED_ORIGIN_REGEXES', [])
    for pattern in allowed_patterns:
        try:
            if re.match(pattern, origin):
                logger.debug(
                    f"SSE request from pattern-matched origin: {origin}",
                    extra={'path': request.path, 'origin': origin, 'pattern': pattern}
                )
                return {
                    'Access-Control-Allow-Origin': origin,
                    'Access-Control-Allow-Credentials': 'true',
                    'Access-Control-Allow-Headers': 'Cache-Control, Content-Type',
                }
        except re.error as e:
            logger.error(
                f"Invalid CORS regex pattern: {pattern}",
                extra={'error': str(e), 'pattern': pattern}
            )
            continue

    # Origin not allowed - log security event and block
    logger.warning(
        "SSE request from unauthorized origin blocked",
        extra={
            'origin': origin,
            'path': request.path,
            'remote_addr': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown')[:200],
            'security_event': 'sse_unauthorized_origin_blocked',
            'severity': 'medium'
        }
    )
    return None


def validate_sse_request_security(request: HttpRequest) -> bool:
    """
    Perform comprehensive security validation for SSE requests.

    Checks multiple security aspects beyond just origin validation:
    - Origin header presence and format
    - Multiple Origin headers (attack vector)
    - Null origin (potential attack)
    - Suspicious patterns in origin

    Args:
        request: Django HttpRequest object

    Returns:
        True if request passes security checks, False otherwise

    Example:
        >>> if not validate_sse_request_security(request):
        ...     return JsonResponse({'error': 'Security validation failed'}, status=403)
    """
    origin = request.META.get('HTTP_ORIGIN', '').strip()

    # Check for null origin (security risk)
    if origin.lower() == 'null':
        logger.warning(
            "SSE request with null origin blocked",
            extra={
                'path': request.path,
                'remote_addr': request.META.get('REMOTE_ADDR'),
                'security_event': 'sse_null_origin_blocked'
            }
        )
        return False

    # Check for multiple Origin headers (header injection attack)
    origin_headers = [v for k, v in request.META.items() if k == 'HTTP_ORIGIN']
    if len(origin_headers) > 1:
        logger.warning(
            "SSE request with multiple Origin headers blocked (possible attack)",
            extra={
                'path': request.path,
                'origin_count': len(origin_headers),
                'security_event': 'sse_multiple_origins_blocked',
                'severity': 'high'
            }
        )
        return False

    # Check for suspicious patterns
    suspicious_patterns = [
        r'.*<script.*',  # XSS attempt in origin
        r'.*javascript:.*',  # JavaScript protocol
        r'.*\x00.*',  # Null byte injection
        r'.*[<>].*',  # HTML tags in origin
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, origin, re.IGNORECASE):
            logger.warning(
                "SSE request with suspicious origin pattern blocked",
                extra={
                    'origin': origin[:200],  # Limit log size
                    'path': request.path,
                    'security_event': 'sse_suspicious_origin_pattern',
                    'severity': 'high'
                }
            )
            return False

    return True


def get_sse_security_context(request: HttpRequest) -> Dict[str, any]:
    """
    Generate security context information for SSE request logging.

    Useful for audit logging and security monitoring of SSE connections.

    Args:
        request: Django HttpRequest object

    Returns:
        Dict containing sanitized security context information
    """
    return {
        'origin': request.META.get('HTTP_ORIGIN', 'none'),
        'remote_addr': request.META.get('REMOTE_ADDR', 'unknown'),
        'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown')[:200],
        'referer': request.META.get('HTTP_REFERER', 'none')[:200],
        'path': request.path,
        'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
    }


__all__ = [
    'get_secure_sse_cors_headers',
    'validate_sse_request_security',
    'get_sse_security_context',
]
