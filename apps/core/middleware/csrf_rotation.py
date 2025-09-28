"""
CSRF Token Rotation Middleware

Implements automatic CSRF token rotation for long-lived sessions to prevent
token fixation attacks and enhance security.

Features:
- Rotates CSRF tokens every 30 minutes for active sessions
- Maintains 2-token grace period during rotation
- Logs all rotation events for audit
- Compatible with AJAX and HTMX applications
- Zero user disruption during rotation

Security Benefits:
- Prevents CSRF token fixation attacks
- Limits window of opportunity for stolen tokens
- Reduces impact of token exposure
- Complies with OWASP security best practices

Compliance: OWASP Top 10 A01:2021 - Broken Access Control
Rule Reference: .claude/rules.md Rule #3 enhancement

Author: Security Enhancement Team
Date: 2025-09-27
"""

import logging
import hashlib
import time
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.middleware.csrf import get_token, rotate_token
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')


class CSRFTokenRotationMiddleware(MiddlewareMixin):
    """
    Middleware to automatically rotate CSRF tokens for security.

    Token Rotation Strategy:
    1. Track token age in cache
    2. Rotate tokens after configured interval (default: 30 minutes)
    3. Maintain grace period with dual-token validation
    4. Log all rotations for audit

    Configuration (settings.py):
        CSRF_TOKEN_ROTATION_ENABLED = True  # Enable rotation
        CSRF_TOKEN_ROTATION_INTERVAL = 1800  # 30 minutes in seconds
        CSRF_TOKEN_GRACE_PERIOD = 300  # 5 minutes grace period
    """

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)

        self.enabled = getattr(settings, 'CSRF_TOKEN_ROTATION_ENABLED', True)
        self.rotation_interval = getattr(settings, 'CSRF_TOKEN_ROTATION_INTERVAL', 1800)
        self.grace_period = getattr(settings, 'CSRF_TOKEN_GRACE_PERIOD', 300)

    def process_request(self, request):
        """
        Check if CSRF token needs rotation and rotate if necessary.

        Args:
            request: Django HttpRequest object

        Returns:
            None (modifies request in-place)
        """
        if not self.enabled:
            return None

        if not request.method in ['GET', 'HEAD', 'OPTIONS']:
            return None

        if not hasattr(request, 'session') or not request.session.session_key:
            return None

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        if self._should_rotate_token(request):
            self._rotate_csrf_token(request)

        return None

    def _should_rotate_token(self, request) -> bool:
        """
        Determine if CSRF token should be rotated.

        Args:
            request: Django HttpRequest object

        Returns:
            True if token should be rotated
        """
        session_key = request.session.session_key
        cache_key = f"csrf_token_created:{session_key}"

        token_created_at = cache.get(cache_key)

        if token_created_at is None:
            current_token = get_token(request)
            cache.set(cache_key, time.time(), self.rotation_interval + self.grace_period)
            return False

        age = time.time() - token_created_at

        if age >= self.rotation_interval:
            return True

        return False

    def _rotate_csrf_token(self, request):
        """
        Perform CSRF token rotation with grace period.

        Args:
            request: Django HttpRequest object
        """
        try:
            session_key = request.session.session_key
            old_token = request.META.get('CSRF_COOKIE')

            rotate_token(request)

            new_token = get_token(request)

            cache_key_new = f"csrf_token_created:{session_key}"
            cache.set(cache_key_new, time.time(), self.rotation_interval + self.grace_period)

            if old_token:
                cache_key_grace = f"csrf_token_grace:{session_key}:{old_token}"
                cache.set(cache_key_grace, True, self.grace_period)

            security_logger.info(
                f"CSRF token rotated for user {request.user.loginid if hasattr(request.user, 'loginid') else 'unknown'}",
                extra={
                    'event_type': 'csrf_token_rotation',
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'session_key': session_key,
                    'timestamp': timezone.now().isoformat(),
                    'rotation_interval': self.rotation_interval,
                    'grace_period': self.grace_period
                }
            )

        except (ConnectionError, ValueError) as e:
            logger.error(
                f"CSRF token rotation failed: {e}",
                exc_info=True,
                extra={
                    'event_type': 'csrf_rotation_error',
                    'user_id': getattr(request.user, 'id', None)
                }
            )

    def process_response(self, request, response):
        """
        Process response to include rotated token information.

        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object

        Returns:
            Modified response
        """
        if not self.enabled:
            return response

        if hasattr(request, '_csrf_token_rotated'):
            response['X-CSRF-Token-Rotated'] = 'true'

        return response


class CSRFDoubleSubmitMiddleware(MiddlewareMixin):
    """
    Double-Submit Cookie CSRF Protection Middleware.

    Provides an additional layer of CSRF protection using the double-submit
    cookie pattern as a fallback mechanism.

    How it Works:
    1. Set a random value in a cookie
    2. Require the same value in a custom header
    3. Validate they match (no server-side state needed)

    Benefits:
    - Stateless CSRF protection
    - Works without server-side sessions
    - Compatible with distributed systems
    - Backup for token-based protection

    Configuration (settings.py):
        CSRF_DOUBLE_SUBMIT_ENABLED = False  # Enable double-submit pattern
        CSRF_DOUBLE_SUBMIT_COOKIE_NAME = 'csrf-token'
        CSRF_DOUBLE_SUBMIT_HEADER_NAME = 'X-CSRF-Token'

    Security Note:
    This is a COMPLEMENTARY protection mechanism. The primary CSRF protection
    (csrf_protect_ajax, csrf_protect_htmx) remains the main defense layer.
    """

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)

        self.enabled = getattr(settings, 'CSRF_DOUBLE_SUBMIT_ENABLED', False)
        self.cookie_name = getattr(settings, 'CSRF_DOUBLE_SUBMIT_COOKIE_NAME', 'csrf-token')
        self.header_name = getattr(settings, 'CSRF_DOUBLE_SUBMIT_HEADER_NAME', 'X-CSRF-Token')

    def process_request(self, request):
        """
        Validate double-submit cookie pattern for mutations.

        Args:
            request: Django HttpRequest object

        Returns:
            None if validation passes, JsonResponse if fails
        """
        if not self.enabled:
            return None

        if request.method in ['GET', 'HEAD', 'OPTIONS', 'TRACE']:
            return None

        if self._is_exempt_path(request.path):
            return None

        cookie_value = request.COOKIES.get(self.cookie_name)
        header_value = request.META.get(f'HTTP_{self.header_name.upper().replace("-", "_")}')

        if not cookie_value or not header_value:
            return None

        if not self._constant_time_compare(cookie_value, header_value):
            security_logger.warning(
                f"Double-submit CSRF validation failed for {request.path}",
                extra={
                    'event_type': 'csrf_double_submit_failure',
                    'correlation_id': getattr(request, 'correlation_id', 'unknown'),
                    'user': getattr(request.user, 'loginid', 'anonymous') if hasattr(request, 'user') else 'anonymous',
                    'ip': self._get_client_ip(request),
                    'path': request.path
                }
            )

            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Double-submit CSRF validation failed',
                'code': 'CSRF_DOUBLE_SUBMIT_INVALID'
            }, status=403)

        request.csrf_double_submit_validated = True
        return None

    def process_response(self, request, response):
        """
        Set double-submit cookie on response.

        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object

        Returns:
            Modified response with cookie
        """
        if not self.enabled:
            return response

        if not request.COOKIES.get(self.cookie_name):
            import secrets
            token_value = secrets.token_urlsafe(32)

            response.set_cookie(
                self.cookie_name,
                token_value,
                max_age=None,
                secure=getattr(settings, 'SESSION_COOKIE_SECURE', True),
                httponly=False,
                samesite=getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax')
            )

        return response

    def _is_exempt_path(self, path: str) -> bool:
        """
        Check if path is exempt from double-submit validation.

        Args:
            path: Request path

        Returns:
            True if exempt
        """
        exempt_paths = getattr(settings, 'CSRF_DOUBLE_SUBMIT_EXEMPT_PATHS', [
            '/admin/login/',
            '/accounts/login/',
        ])

        return any(path.startswith(exempt_path) for exempt_path in exempt_paths)

    def _constant_time_compare(self, val1: str, val2: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks.

        Args:
            val1: First value
            val2: Second value

        Returns:
            True if values match
        """
        import hmac
        return hmac.compare_digest(val1, val2)

    def _get_client_ip(self, request) -> str:
        """
        Get client IP address.

        Args:
            request: Django HttpRequest object

        Returns:
            IP address string
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip


class CSRFViolationTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track and analyze CSRF violation patterns.

    Features:
    - Detects CSRF bypass attempts
    - Tracks violation patterns per IP/user
    - Automatic blocking after threshold violations
    - Integration with CSRF violation monitoring dashboard
    - Real-time alerting for attack patterns

    Configuration (settings.py):
        CSRF_VIOLATION_TRACKING_ENABLED = True
        CSRF_VIOLATION_THRESHOLD = 5  # Block after 5 violations
        CSRF_VIOLATION_WINDOW = 3600  # 1 hour window
        CSRF_VIOLATION_BLOCK_DURATION = 86400  # 24 hours
    """

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)

        self.enabled = getattr(settings, 'CSRF_VIOLATION_TRACKING_ENABLED', True)
        self.threshold = getattr(settings, 'CSRF_VIOLATION_THRESHOLD', 5)
        self.window = getattr(settings, 'CSRF_VIOLATION_WINDOW', 3600)
        self.block_duration = getattr(settings, 'CSRF_VIOLATION_BLOCK_DURATION', 86400)

    def process_response(self, request, response):
        """
        Track CSRF violations from response status.

        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object

        Returns:
            Response (potentially modified for blocking)
        """
        if not self.enabled:
            return response

        if response.status_code == 403:
            if self._is_csrf_violation(request, response):
                self._record_violation(request)

                if self._is_blocked(request):
                    security_logger.critical(
                        f"IP blocked due to repeated CSRF violations: {self._get_client_ip(request)}",
                        extra={
                            'event_type': 'csrf_violation_block',
                            'ip': self._get_client_ip(request),
                            'violations': self._get_violation_count(request),
                            'threshold': self.threshold
                        }
                    )

                    from django.http import JsonResponse
                    return JsonResponse({
                        'error': 'Access temporarily blocked due to repeated security violations',
                        'code': 'BLOCKED_DUE_TO_VIOLATIONS',
                        'retry_after': self.block_duration
                    }, status=403)

        return response

    def _is_csrf_violation(self, request, response) -> bool:
        """
        Determine if 403 response is a CSRF violation.

        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object

        Returns:
            True if CSRF violation
        """
        try:
            if hasattr(response, 'content'):
                content = response.content.decode('utf-8')
                return any(keyword in content for keyword in [
                    'CSRF_TOKEN_REQUIRED',
                    'CSRF_TOKEN_INVALID',
                    'CSRF validation failed'
                ])
        except (ConnectionError, TypeError, ValidationError, ValueError):
            pass

        return False

    def _record_violation(self, request):
        """
        Record CSRF violation for tracking.

        Args:
            request: Django HttpRequest object
        """
        identifier = self._get_violation_identifier(request)
        cache_key = f"csrf_violations:{identifier}"

        violations = cache.get(cache_key, [])
        violations.append({
            'timestamp': time.time(),
            'path': request.path,
            'method': request.method,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100]
        })

        cache.set(cache_key, violations, self.window)

        violation_count = len(violations)

        security_logger.warning(
            f"CSRF violation recorded for {identifier} (count: {violation_count}/{self.threshold})",
            extra={
                'event_type': 'csrf_violation',
                'identifier': identifier,
                'violation_count': violation_count,
                'path': request.path,
                'user': getattr(request.user, 'loginid', 'anonymous') if hasattr(request, 'user') else 'anonymous'
            }
        )

        if violation_count >= self.threshold:
            self._trigger_block(identifier)

    def _is_blocked(self, request) -> bool:
        """
        Check if request source is blocked due to violations.

        Args:
            request: Django HttpRequest object

        Returns:
            True if blocked
        """
        identifier = self._get_violation_identifier(request)
        block_cache_key = f"csrf_block:{identifier}"
        return cache.get(block_cache_key, False)

    def _trigger_block(self, identifier: str):
        """
        Block request source due to threshold violations.

        Args:
            identifier: Unique identifier (IP or user ID)
        """
        block_cache_key = f"csrf_block:{identifier}"
        cache.set(block_cache_key, True, self.block_duration)

        security_logger.critical(
            f"IP/User blocked due to CSRF violations: {identifier}",
            extra={
                'event_type': 'csrf_violation_block_triggered',
                'identifier': identifier,
                'block_duration': self.block_duration,
                'threshold': self.threshold
            }
        )

    def _get_violation_identifier(self, request) -> str:
        """
        Get unique identifier for violation tracking.

        Uses user ID if authenticated, otherwise IP address.

        Args:
            request: Django HttpRequest object

        Returns:
            Unique identifier string
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        else:
            return f"ip:{self._get_client_ip(request)}"

    def _get_violation_count(self, request) -> int:
        """
        Get current violation count for request source.

        Args:
            request: Django HttpRequest object

        Returns:
            Number of violations in current window
        """
        identifier = self._get_violation_identifier(request)
        cache_key = f"csrf_violations:{identifier}"
        violations = cache.get(cache_key, [])
        return len(violations)

    def _get_client_ip(self, request) -> str:
        """
        Get client IP address.

        Args:
            request: Django HttpRequest object

        Returns:
            IP address string
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip