"""
Standardized REST API Exception Handling

Provides consistent error responses across all API endpoints with correlation tracking.

Compliance with .claude/rules.md:
- Specific exception types (no bare except)
- Standardized error envelopes
- Correlation ID tracking
"""

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.db import DatabaseError, IntegrityError
from psycopg2.errors import UniqueViolation, ForeignKeyViolation
import logging
import uuid

logger = logging.getLogger(__name__)


def standardized_exception_handler(exc, context):
    """
    Custom exception handler that returns standardized error responses.

    Error Response Format:
    {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": {
                "email": ["Enter a valid email address."],
                "phone": ["This field is required."]
            },
            "correlation_id": "abc-123-def-456",
            "timestamp": "2025-10-27T10:30:00.123Z"
        }
    }

    Args:
        exc: The raised exception
        context: Request context from DRF

    Returns:
        Response with standardized error envelope
    """
    # Get correlation ID from request
    request = context.get('request')
    correlation_id = getattr(request, 'correlation_id', None) if request else None
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)

    # If DRF handled it, wrap in our standard envelope
    if response is not None:
        error_code = _get_error_code(exc)
        error_message = _get_error_message(exc, response)

        standardized_response = {
            "error": {
                "code": error_code,
                "message": error_message,
                "details": response.data if isinstance(response.data, dict) else {"detail": response.data},
                "correlation_id": correlation_id,
            }
        }

        response.data = standardized_response

        # Log error for monitoring
        logger.error(
            f"API Error: {error_code} - {error_message}",
            extra={
                "correlation_id": correlation_id,
                "status_code": response.status_code,
                "path": request.path if request else None,
                "method": request.method if request else None,
            },
            exc_info=exc if response.status_code >= 500 else None
        )

        return response

    # Handle Django exceptions not caught by DRF
    if isinstance(exc, Http404):
        return _create_error_response(
            code="NOT_FOUND",
            message="Resource not found",
            details={"detail": str(exc)},
            status_code=status.HTTP_404_NOT_FOUND,
            correlation_id=correlation_id
        )

    if isinstance(exc, DjangoPermissionDenied):
        return _create_error_response(
            code="PERMISSION_DENIED",
            message="You do not have permission to perform this action",
            details={"detail": str(exc)},
            status_code=status.HTTP_403_FORBIDDEN,
            correlation_id=correlation_id
        )

    if isinstance(exc, ObjectDoesNotExist):
        return _create_error_response(
            code="NOT_FOUND",
            message=f"Object not found: {exc.__class__.__name__}",
            details={"detail": str(exc)},
            status_code=status.HTTP_404_NOT_FOUND,
            correlation_id=correlation_id
        )

    # Handle database exceptions
    if isinstance(exc, IntegrityError):
        if isinstance(exc.__cause__, UniqueViolation):
            return _create_error_response(
                code="DUPLICATE_ENTRY",
                message="A record with this value already exists",
                details={"detail": str(exc)},
                status_code=status.HTTP_409_CONFLICT,
                correlation_id=correlation_id
            )
        if isinstance(exc.__cause__, ForeignKeyViolation):
            return _create_error_response(
                code="INVALID_REFERENCE",
                message="Referenced object does not exist",
                details={"detail": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
                correlation_id=correlation_id
            )

    if isinstance(exc, DatabaseError):
        logger.error(
            f"Database error: {exc}",
            extra={"correlation_id": correlation_id},
            exc_info=exc
        )
        return _create_error_response(
            code="DATABASE_ERROR",
            message="A database error occurred",
            details={"detail": "Please try again later"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            correlation_id=correlation_id
        )

    # Unhandled exception - return 500
    logger.error(
        f"Unhandled exception in API: {exc.__class__.__name__}",
        extra={"correlation_id": correlation_id},
        exc_info=exc
    )
    return _create_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        details={"detail": "Please contact support if this persists"},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        correlation_id=correlation_id
    )


def _get_error_code(exc):
    """
    Determine standardized error code from exception type.
    """
    error_code_mapping = {
        ValidationError: "VALIDATION_ERROR",
        PermissionDenied: "PERMISSION_DENIED",
        AuthenticationFailed: "AUTHENTICATION_FAILED",
        NotAuthenticated: "NOT_AUTHENTICATED",
        NotFound: "NOT_FOUND",
        MethodNotAllowed: "METHOD_NOT_ALLOWED",
        Throttled: "RATE_LIMIT_EXCEEDED",
        ParseError: "PARSE_ERROR",
        UnsupportedMediaType: "UNSUPPORTED_MEDIA_TYPE",
    }

    exc_class = exc.__class__.__name__
    for error_type, code in error_code_mapping.items():
        if isinstance(exc, error_type):
            return code

    # Fallback based on status code if available
    if hasattr(exc, 'status_code'):
        if exc.status_code == 400:
            return "BAD_REQUEST"
        elif exc.status_code == 401:
            return "UNAUTHORIZED"
        elif exc.status_code == 403:
            return "FORBIDDEN"
        elif exc.status_code == 404:
            return "NOT_FOUND"
        elif exc.status_code >= 500:
            return "INTERNAL_ERROR"

    return "API_ERROR"


def _get_error_message(exc, response):
    """
    Extract human-readable error message from exception.
    """
    if hasattr(exc, 'detail'):
        if isinstance(exc.detail, dict):
            # For validation errors, return generic message
            return "Validation failed"
        return str(exc.detail)

    if hasattr(response, 'data'):
        if isinstance(response.data, dict) and 'detail' in response.data:
            return str(response.data['detail'])

    return str(exc)


def _create_error_response(code, message, details, status_code, correlation_id):
    """
    Helper to create standardized error response.
    """
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "correlation_id": correlation_id,
            }
        },
        status=status_code
    )


# Import DRF exceptions for error code mapping
from rest_framework.exceptions import (
    PermissionDenied,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    MethodNotAllowed,
    Throttled,
    ParseError,
    UnsupportedMediaType,
)


__all__ = [
    'standardized_exception_handler',
]
