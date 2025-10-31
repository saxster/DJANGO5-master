"""
SQL Injection Protection Middleware
Provides protection against SQL injection attacks at the middleware level.

Optimizations:
- Early rejection of oversized request bodies (DoS prevention)
- Whitelist bypass for known-safe endpoints
- Reduced false positives on benign content
"""

import logging
import re
from typing import Optional, Set, List
from dataclasses import dataclass

from django.http import HttpResponseBadRequest
from django.http.request import RawPostDataException
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.conf import settings

from .error_handling import ErrorHandler

logger = logging.getLogger(__name__)


@dataclass
class SQLSecurityConfig:
    """Configuration for SQL security middleware"""
    max_body_size_bytes: int = 1048576  # 1MB default
    scan_full_json_body: bool = False  # Disabled by default for performance
    whitelisted_paths: Set[str] = None

    def __post_init__(self):
        if self.whitelisted_paths is None:
            self.whitelisted_paths = set()


class SQLInjectionProtectionMiddleware:
    """
    Middleware to detect and prevent SQL injection attempts.

    This middleware analyzes incoming requests for common SQL injection patterns
    and blocks suspicious requests before they reach the application logic.

    Performance Optimizations:
    - Early rejection of oversized bodies (prevents DoS via large payloads)
    - Whitelisted paths bypass scanning (static assets, health checks)
    - Conditional full-body scanning (disabled by default)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_handler = ErrorHandler()

        # Load configuration from settings with sensible defaults
        self.config = SQLSecurityConfig(
            max_body_size_bytes=getattr(settings, 'SQL_SECURITY_MAX_BODY_SIZE', 1048576),
            scan_full_json_body=getattr(settings, 'SQL_SECURITY_SCAN_FULL_BODY', False),
            whitelisted_paths=set(getattr(settings, 'SQL_SECURITY_WHITELISTED_PATHS', [
                '/static/',
                '/media/',
                '/_health/',
                '/metrics/',
                '/favicon.ico',
            ]))
        )

        # HIGH-RISK SQL injection patterns (focused, reduced false positives)
        self.high_risk_patterns = [
            # Basic SQL injection patterns
            r"('\s*(or|and)\s*'[^']*'|'\s*(or|and)\s*\d+\s*=\s*\d+)",
            r"('\s*;\s*(drop|delete|update|insert|create|alter)\s+)",
            r"('\s*union\s+(all\s+)?select\s+)",
            # Advanced SQL injection patterns
            r"(exec\s*\(|execute\s*\(|sp_executesql)",
            r"(xp_cmdshell|sp_makewebtask|sp_oacreate)",
            r"(waitfor\s+delay|benchmark\s*\(|sleep\s*\()",
            # Union-based injection
            r"(union\s+(all\s+)?select\s+null)",
            r"(union\s+(all\s+)?select\s+\d+)",
            # Schema discovery attempts
            r"(information_schema|sys\.tables|sys\.columns)",
        ]

        # MEDIUM-RISK patterns (used for non-password fields only)
        self.medium_risk_patterns = [
            # Boolean-based blind injection
            r"(\s+and\s+\d+\s*=\s*\d+\s*--)",
            r"(\s+or\s+\d+\s*=\s*\d+\s*--)",
            # Time-based blind injection
            r"(if\s*\(\s*\d+\s*=\s*\d+\s*,\s*sleep\s*\(\s*\d+\s*\))",
            # Comment-based injection (SQL comments only, not fragments in valid text)
            r"(^\s*#|--\s+.*|/\*.*\*/)",
        ]

        # Compile regex patterns for performance
        self.compiled_high_risk = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.high_risk_patterns
        ]
        self.compiled_medium_risk = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.medium_risk_patterns
        ]

    def __call__(self, request):
        # Early bailout: whitelisted paths
        if self._is_whitelisted_path(request.path):
            return self.get_response(request)

        # Early bailout: oversized body (DoS prevention)
        if self._is_oversized_body(request):
            logger.warning(
                f"Rejecting oversized request body: {len(request.body) if hasattr(request, 'body') else 'unknown'} bytes",
                extra={
                    "correlation_id": getattr(request, "correlation_id", "unknown"),
                    "path": request.path,
                    "ip": self._get_client_ip(request),
                }
            )
            return HttpResponseBadRequest(
                "Request body too large for security scanning. Maximum: 1MB"
            )

        # Check for SQL injection attempts
        if self._detect_sql_injection(request):
            return self._handle_sql_injection_attempt(request)

        response = self.get_response(request)
        return response

    def _is_whitelisted_path(self, path: str) -> bool:
        """Check if path is whitelisted (bypasses scanning for performance)."""
        return any(path.startswith(wl_path) for wl_path in self.config.whitelisted_paths)

    def _is_oversized_body(self, request) -> bool:
        """Check if request body exceeds maximum size for scanning."""
        if not hasattr(request, 'body'):
            return False

        try:
            content_length = request.META.get('CONTENT_LENGTH')
            if content_length:
                return int(content_length) > self.config.max_body_size_bytes
        except (ValueError, TypeError):
            pass

        return False

    def _detect_sql_injection(self, request):
        """
        Detect SQL injection attempts in request parameters.

        Args:
            request: Django HttpRequest object

        Returns:
            bool: True if SQL injection pattern detected, False otherwise
        """
        # Check GET parameters
        for param, value in request.GET.items():
            if self._check_value_for_sql_injection(value, param):
                logger.warning(
                    f"SQL injection attempt detected in GET parameter '{param}': {value}",
                    extra={
                        "correlation_id": getattr(request, "correlation_id", "unknown"),
                        "ip": self._get_client_ip(request),
                        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                        "path": request.path,
                        "method": request.method,
                    },
                )
                return True

        # Check POST parameters for form data
        # Note: Accessing request.POST will consume the body stream
        if hasattr(request, "POST") and request.content_type != "application/json":
            for param, value in request.POST.items():
                if self._check_value_for_sql_injection(value, param):
                    logger.warning(
                        f"SQL injection attempt detected in POST parameter '{param}': {value}",
                        extra={
                            "correlation_id": getattr(
                                request, "correlation_id", "unknown"
                            ),
                            "ip": self._get_client_ip(request),
                            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                            "path": request.path,
                            "method": request.method,
                        },
                    )
                    return True

        # Check JSON body for API requests (CONDITIONAL - disabled by default for performance)
        # Full-body scanning has high overhead and false positives
        elif (hasattr(request, "body") and
              request.content_type == "application/json" and
              self.config.scan_full_json_body):  # OPTIMIZATION: Conditional scanning
            try:
                # Try to access body, but handle the case where it's already been read
                body_str = request.body.decode("utf-8")
                if self._check_value_for_sql_injection(body_str, "json_body"):
                    logger.warning(
                        f"SQL injection attempt detected in JSON body",
                        extra={
                            "correlation_id": getattr(
                                request, "correlation_id", "unknown"
                            ),
                            "ip": self._get_client_ip(request),
                            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                            "path": request.path,
                            "method": request.method,
                        },
                    )
                    return True
            except (UnicodeDecodeError, AttributeError, RawPostDataException):
                # If body was already read or can't be decoded, skip JSON body check
                # This happens when request.POST or request.FILES was accessed before
                pass

        return False


    def _check_value_for_sql_injection(self, value, param_name=""):
        """
        Check a single value for SQL injection patterns using two-tier system.

        Args:
            value: String value to check
            param_name: Name of the parameter (for context-aware checking)

        Returns:
            bool: True if SQL injection pattern found, False otherwise
        """
        if not isinstance(value, str):
            return False

        # Context-aware checking: password fields use high-risk patterns only
        password_fields = ["password", "passwd", "pwd", "pass", "secret", "token"]
        is_password_field = any(
            pwd_field in param_name.lower() for pwd_field in password_fields
        )

        # ALWAYS check high-risk patterns (critical SQL injection signatures)
        for pattern in self.compiled_high_risk:
            if pattern.search(value):
                return True

        # For password fields, STOP here (avoid false positives on special chars)
        if is_password_field:
            return False

        # For non-password fields, also check medium-risk patterns
        for pattern in self.compiled_medium_risk:
            if pattern.search(value):
                return True

        return False

    def _handle_sql_injection_attempt(self, request):
        """
        Handle detected SQL injection attempt.

        Args:
            request: Django HttpRequest object

        Returns:
            HttpResponse: Error response
        """
        error_message = (
            "Suspicious input detected. Request blocked for security reasons."
        )

        # Log the attempt
        logger.error(
            f"SQL injection attempt blocked from {self._get_client_ip(request)}",
            extra={
                "correlation_id": getattr(request, "correlation_id", "unknown"),
                "ip": self._get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "path": request.path,
                "method": request.method,
                "referer": request.META.get("HTTP_REFERER", ""),
            },
        )

        # Return appropriate error response
        if request.content_type == "application/json":
            # API request - return JSON error
            return self.error_handler.handle_api_error(
                request, SuspiciousOperation(error_message), status_code=400
            )
        else:
            # Web request - return HTTP 400
            return HttpResponseBadRequest(error_message)

    def _get_client_ip(self, request):
        """
        Get the client IP address from request.

        Args:
            request: Django HttpRequest object

        Returns:
            str: Client IP address
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
