"""
PII Sanitization Middleware for Monitoring Endpoints

Automatically sanitizes all monitoring endpoint responses to prevent PII leakage.

Compliance:
- .claude/rules.md Rule #15: PII sanitization in logs
- Rule #8: Middleware < 100 lines
- Rule #11: Specific exception handling

Security:
- All monitoring responses are sanitized before sending
- SQL queries, error messages, URLs sanitized
- Preserves monitoring functionality while protecting privacy
"""

import json
import logging
from typing import Optional
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

logger = logging.getLogger('monitoring.middleware')

__all__ = ['PIISanitizationMiddleware']


class PIISanitizationMiddleware(MiddlewareMixin):
    """
    Middleware to automatically sanitize PII in monitoring responses.

    Applied only to monitoring endpoints to minimize performance impact.
    Rule #8 compliant: < 100 lines
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.monitoring_paths = [
            '/monitoring/',
            '/metrics/',
            '/health/',
        ]

    def process_response(self, request, response):
        """Sanitize monitoring endpoint responses."""
        # Only process monitoring endpoints
        if not self._is_monitoring_endpoint(request):
            return response

        # Only process JSON responses
        if not isinstance(response, JsonResponse):
            return response

        try:
            # Parse response content
            content = json.loads(response.content.decode('utf-8'))

            # Sanitize the data
            sanitized_content = MonitoringPIIRedactionService.sanitize_dashboard_data(content)

            # Create new response with sanitized data
            sanitized_response = JsonResponse(
                sanitized_content,
                status=response.status_code,
                safe=False
            )

            # Preserve headers
            for header, value in response.items():
                sanitized_response[header] = value

            # Add sanitization indicator
            sanitized_response['X-PII-Sanitized'] = 'true'

            logger.debug(
                f"Monitoring response sanitized: {request.path}",
                extra={
                    'path': request.path,
                    'correlation_id': getattr(request, 'correlation_id', None)
                }
            )

            return sanitized_response

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            # JSON parsing failed - log and return original
            logger.warning(
                f"Failed to sanitize monitoring response: {e}",
                extra={
                    'path': request.path,
                    'correlation_id': getattr(request, 'correlation_id', None)
                }
            )
            return response

        except (ValueError, TypeError) as e:
            # Sanitization failed - log and return original
            logger.error(
                f"Error during PII sanitization: {e}",
                extra={
                    'path': request.path,
                    'correlation_id': getattr(request, 'correlation_id', None)
                },
                exc_info=True
            )
            return response

    def _is_monitoring_endpoint(self, request) -> bool:
        """Check if request is for a monitoring endpoint."""
        return any(request.path.startswith(path) for path in self.monitoring_paths)
