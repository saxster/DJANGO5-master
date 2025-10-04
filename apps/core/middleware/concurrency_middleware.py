"""
Concurrency Middleware - Optimistic Locking Handler

Handles RecordModifiedError exceptions from django-concurrency
and provides user-friendly conflict resolution.

Features:
- Detects optimistic locking conflicts
- Returns structured error responses
- Logs conflicts for monitoring
- Provides conflict resolution guidance

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from typing import Dict, Any
from django.http import JsonResponse, HttpRequest
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')


class ConcurrencyMiddleware:
    """
    Middleware to handle optimistic locking conflicts gracefully.

    When multiple users edit the same record simultaneously,
    django-concurrency raises RecordModifiedError. This middleware
    catches it and returns a user-friendly response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        return response

    def process_exception(self, request: HttpRequest, exception: Exception):
        """
        Handle RecordModifiedError from django-concurrency.

        Args:
            request: HTTP request
            exception: Exception raised

        Returns:
            JsonResponse with conflict details or None to continue
        """
        # Check if this is a concurrency conflict
        if self._is_concurrency_error(exception):
            return self._handle_concurrency_conflict(request, exception)

        # Let other exceptions pass through
        return None

    def _is_concurrency_error(self, exception: Exception) -> bool:
        """Check if exception is a concurrency conflict"""
        exception_name = exception.__class__.__name__
        return exception_name in [
            'RecordModifiedError',
            'RecordDeletedError',
        ]

    def _handle_concurrency_conflict(
        self,
        request: HttpRequest,
        exception: Exception
    ) -> JsonResponse:
        """
        Create user-friendly response for concurrency conflicts.

        Returns:
            409 Conflict response with resolution guidance
        """
        # Log the conflict
        self._log_conflict(request, exception)

        # Extract conflict details
        conflict_details = self._extract_conflict_details(exception)

        # Create response
        response_data = {
            'error': 'concurrency_conflict',
            'message': (
                'This record was modified by another user. '
                'Please refresh and try again with the latest version.'
            ),
            'details': conflict_details,
            'resolution': {
                'action': 'refresh_and_retry',
                'steps': [
                    'Refresh the page to get the latest version',
                    'Review the changes made by the other user',
                    'Make your changes again if still necessary',
                ],
            },
        }

        return JsonResponse(response_data, status=409)

    def _extract_conflict_details(self, exception: Exception) -> Dict[str, Any]:
        """
        Extract details from RecordModifiedError.

        Args:
            exception: RecordModifiedError instance

        Returns:
            Dict with conflict details
        """
        details = {
            'error_type': exception.__class__.__name__,
        }

        # Try to extract model and version info
        if hasattr(exception, 'target'):
            target = exception.target
            details['model'] = target.__class__.__name__
            details['record_id'] = getattr(target, 'id', None)

            # Get version info if available
            if hasattr(target, 'version'):
                details['expected_version'] = getattr(exception, 'expected_version', None)
                details['actual_version'] = getattr(target, 'version', None)

        return details

    def _log_conflict(self, request: HttpRequest, exception: Exception):
        """Log concurrency conflict for monitoring"""
        conflict_details = self._extract_conflict_details(exception)

        logger.warning(
            "Concurrency conflict detected",
            extra={
                'path': request.path,
                'method': request.method,
                'user_id': request.user.id if request.user.is_authenticated else None,
                'conflict_type': conflict_details.get('error_type'),
                'model': conflict_details.get('model'),
                'record_id': conflict_details.get('record_id'),
            }
        )
