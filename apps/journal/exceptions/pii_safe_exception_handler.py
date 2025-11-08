"""
PII-Safe Exception Handler

Global exception handler that sanitizes all error messages before
sending to clients. Prevents accidental PII exposure in exceptions.

Features:
- Automatic exception message sanitization
- Stack trace PII redaction
- Detailed server-side logging
- Client-safe error responses
- DRF integration

Usage:
    # In settings.py
    REST_FRAMEWORK = {
        'EXCEPTION_HANDLER': 'apps.journal.exceptions.pii_safe_exception_handler'
    }

Author: Claude Code
Date: 2025-10-01
"""

import sys
import traceback
from typing import Optional, Dict, Any
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status
from apps.core.security.pii_redaction import PIIRedactionService
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)


def sanitize_exception_message(message: str) -> str:
    """
    Sanitize exception message to remove PII.

    Args:
        message: Exception message

    Returns:
        str: Sanitized message

    Example:
        >>> sanitize_exception_message("User John Doe not found")
        "User [USER] not found"
    """
    pii_service = PIIRedactionService()
    return pii_service.redact_text(message)


def sanitize_stack_trace(tb: str) -> str:
    """
    Sanitize stack trace to remove variable values that may contain PII.

    Args:
        tb: Stack trace string

    Returns:
        str: Sanitized stack trace

    Example:
        Stack trace with values like:
        "title = 'I am feeling anxious'"
        becomes:
        "title = '[REDACTED]'"
    """
    pii_service = PIIRedactionService()

    # Redact variable assignments in stack trace
    lines = tb.split('\n')
    sanitized_lines = []

    for line in lines:
        # Detect variable assignment lines (e.g., "    title = 'value'")
        if '=' in line and not line.strip().startswith('#'):
            # Redact the value part after '='
            parts = line.split('=', 1)
            if len(parts) == 2:
                sanitized_line = f"{parts[0]}= [REDACTED]"
            else:
                sanitized_line = line
        else:
            # Apply general PII redaction
            sanitized_line = pii_service.redact_text(line)

        sanitized_lines.append(sanitized_line)

    return '\n'.join(sanitized_lines)


def pii_safe_exception_handler(exc, context):
    """
    Custom exception handler that sanitizes all error messages.

    This handler:
    1. Calls DRF's default exception handler
    2. Sanitizes all error messages to remove PII
    3. Logs full details server-side
    4. Returns client-safe error response

    Args:
        exc: Exception instance
        context: Request context

    Returns:
        Response: DRF Response with sanitized error message
    """
    # Get request from context
    request = context.get('view').request if context.get('view') else None
    request_path = request.path if request else 'unknown'
    request_method = request.method if request else 'unknown'
    user = request.user if request and hasattr(request, 'user') else None
    user_id = str(user.id) if user and user.is_authenticated else 'anonymous'

    # Call REST framework's default exception handler first
    response = drf_exception_handler(exc, context)

    # If DRF didn't handle it, create a generic response
    if response is None:
        response = _create_generic_error_response(exc)

    # Sanitize response data
    if response is not None:
        response.data = _sanitize_response_data(response.data)

    # Get full exception details for server-side logging
    exc_type = type(exc).__name__
    exc_message = str(exc)

    # Get stack trace
    exc_traceback = ''.join(traceback.format_exception(*sys.exc_info()))
    sanitized_traceback = sanitize_stack_trace(exc_traceback)

    # Log full details server-side (will be sanitized by logger)
    logger.error(
        f"Exception in journal/wellness API: {exc_type}",
        extra={
            'exception_type': exc_type,
            'exception_message': exc_message,  # Will be sanitized by logger
            'request_path': request_path,
            'request_method': request_method,
            'user_id': user_id,
            'status_code': response.status_code if response else 500,
            'stack_trace': sanitized_traceback  # Pre-sanitized
        },
        exc_info=False  # Don't include exc_info since we have sanitized traceback
    )

    return response


def _create_generic_error_response(exc) -> Response:
    """
    Create a generic error response for unhandled exceptions.

    Args:
        exc: Exception instance

    Returns:
        Response: Generic error response
    """
    # Determine status code based on exception type
    if isinstance(exc, Http404):
        status_code = status.HTTP_404_NOT_FOUND
        message = "Resource not found"

    elif isinstance(exc, PermissionDenied):
        status_code = status.HTTP_403_FORBIDDEN
        message = "Permission denied"

    elif isinstance(exc, ValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
        message = "Validation error occurred"

    else:
        # Unknown exception - be very generic
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        message = "An error occurred processing your request"

    return Response(
        {'detail': message},
        status=status_code
    )


def _sanitize_response_data(data: Any) -> Any:
    """
    Recursively sanitize response data to remove PII.

    Args:
        data: Response data (dict, list, or primitive)

    Returns:
        Any: Sanitized response data
    """
    pii_service = PIIRedactionService()

    if isinstance(data, dict):
        return {
            key: _sanitize_response_data(value)
            for key, value in data.items()
        }

    elif isinstance(data, list):
        return [_sanitize_response_data(item) for item in data]

    elif isinstance(data, str):
        return pii_service.redact_text(data)

    else:
        # Primitive types (int, float, bool, None) - pass through
        return data


class PIISafeExceptionMiddleware:
    """
    Middleware to catch and sanitize exceptions at the middleware level.

    This provides a safety net for exceptions that bypass the DRF exception handler.
    """

    def __init__(self, get_response):
        """Initialize middleware."""
        self.get_response = get_response
        self.pii_service = PIIRedactionService()

    def __call__(self, request):
        """Process request."""
        try:
            response = self.get_response(request)
            return response
        except (ValueError, TypeError, AttributeError) as exc:
            # Log sanitized exception
            sanitized_message = self.pii_service.redact_text(str(exc))
            logger.error(
                f"Unhandled exception: {sanitized_message}",
                extra={
                    'path': request.path,
                    'method': request.method,
                    'exception_type': type(exc).__name__
                }
            )

            # Re-raise - let Django's exception handler deal with it
            raise

    def process_exception(self, request, exception):
        """
        Process exceptions to ensure PII is not leaked.

        Args:
            request: HTTP request
            exception: Exception that occurred

        Returns:
            None (allows normal exception handling to proceed)
        """
        # Sanitize and log
        sanitized_message = self.pii_service.redact_text(str(exception))
        logger.error(
            f"Exception in middleware: {sanitized_message}",
            extra={
                'path': request.path,
                'method': request.method
            }
        )

        # Return None to allow normal exception handling
        return None
