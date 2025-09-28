"""
Error Response Validation Middleware

Addresses Issue #19: Inconsistent Error Message Sanitization
Validates all error responses for compliance with sanitization standards.

Features:
- Intercepts all error responses (4xx, 5xx)
- Validates correlation ID presence
- Strips leaked internal details
- Logs compliance violations
- Enforces standardized error format

Complies with: .claude/rules.md Rule #5 (No Debug Information in Production)
"""

import re
import json
import logging
import uuid
from typing import Optional, Dict, Any

from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse, HttpResponse
from django.conf import settings

from apps.core.middleware.logging_sanitization import LogSanitizationService

logger = logging.getLogger('error_validation')


class ErrorResponseValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate and sanitize all error responses.

    Ensures compliance with error sanitization standards by:
    - Validating correlation ID presence
    - Removing leaked stack traces or internal details
    - Enforcing consistent error response format
    - Logging violations for remediation
    """

    FORBIDDEN_PATTERNS = [
        (re.compile(r'traceback', re.IGNORECASE), 'Stack trace leak'),
        (re.compile(r'File ".*?", line \d+', re.IGNORECASE), 'File path in error'),
        (re.compile(r'Exception at /', re.IGNORECASE), 'Exception details leak'),
        (re.compile(r'django\..*?Error', re.IGNORECASE), 'Django internal exception'),
        (re.compile(r'\.py:\d+', re.IGNORECASE), 'Python file reference'),
    ]

    REQUIRED_ERROR_FIELDS = {'correlation_id', 'timestamp', 'message'}

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        self.enable_validation = getattr(settings, 'ENABLE_ERROR_RESPONSE_VALIDATION', True)
        self.strict_mode = getattr(settings, 'ERROR_VALIDATION_STRICT_MODE', False)
        super().__init__(get_response)

    def process_response(self, request, response):
        """Validate error responses for compliance."""
        if not self.enable_validation:
            return response

        if not self._is_error_response(response):
            return response

        correlation_id = getattr(request, 'correlation_id', str(uuid.uuid4()))

        if isinstance(response, JsonResponse):
            return self._validate_json_error(response, correlation_id)
        elif isinstance(response, HttpResponse):
            return self._validate_html_error(response, correlation_id)

        return response

    def _is_error_response(self, response) -> bool:
        """Check if response is an error response."""
        return response.status_code >= 400

    def _validate_json_error(self, response: JsonResponse, correlation_id: str) -> JsonResponse:
        """Validate JSON error response compliance."""
        try:
            content = json.loads(response.content.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
            logger.warning(
                f"Could not parse JSON error response: {type(e).__name__}",
                extra={'correlation_id': correlation_id}
            )
            return response

        violations = []
        sanitized_content = content.copy()

        if 'error' in content:
            error_data = content['error']

            if 'correlation_id' not in error_data:
                violations.append('Missing correlation_id in error object')
                sanitized_content['error']['correlation_id'] = correlation_id

            for pattern, violation_type in self.FORBIDDEN_PATTERNS:
                content_str = json.dumps(content)
                if pattern.search(content_str):
                    violations.append(violation_type)
                    sanitized_content = self._strip_forbidden_content(
                        sanitized_content, pattern
                    )

        elif 'errors' in content or 'detail' in content:
            if 'correlation_id' not in content:
                violations.append('Missing correlation_id in root')
                sanitized_content['correlation_id'] = correlation_id

        if violations:
            self._log_violations(correlation_id, violations, 'JSON')

            if self.strict_mode or violations:
                return JsonResponse(sanitized_content, status=response.status_code)

        return response

    def _validate_html_error(self, response: HttpResponse, correlation_id: str) -> HttpResponse:
        """Validate HTML error response compliance."""
        try:
            content = response.content.decode('utf-8')
        except (UnicodeDecodeError, AttributeError) as e:
            logger.warning(
                f"Could not decode HTML error response: {type(e).__name__}",
                extra={'correlation_id': correlation_id}
            )
            return response

        violations = []

        for pattern, violation_type in self.FORBIDDEN_PATTERNS:
            if pattern.search(content):
                violations.append(violation_type)

        if 'correlation' not in content.lower():
            violations.append('Missing correlation ID in HTML')

        if violations:
            self._log_violations(correlation_id, violations, 'HTML')

        return response

    def _strip_forbidden_content(self, content: Dict, pattern: re.Pattern) -> Dict:
        """Recursively strip forbidden content from response."""
        if isinstance(content, dict):
            return {
                key: self._strip_forbidden_content(value, pattern)
                for key, value in content.items()
            }
        elif isinstance(content, list):
            return [self._strip_forbidden_content(item, pattern) for item in content]
        elif isinstance(content, str):
            return pattern.sub('[SANITIZED]', content)
        else:
            return content

    def _log_violations(self, correlation_id: str, violations: List[str], response_type: str):
        """Log error response validation violations."""
        logger.warning(
            f"Error response validation violations detected",
            extra={
                'correlation_id': correlation_id,
                'response_type': response_type,
                'violations': violations,
                'violation_count': len(violations),
            }
        )

        cache_key = f'error_validation_violations_{response_type}'
        from django.core.cache import cache
        count = cache.get(cache_key, 0)
        cache.set(cache_key, count + len(violations), 3600)


__all__ = ['ErrorResponseValidationMiddleware']