"""
Standardized Error Response Factory

Addresses Issue #19: Inconsistent Error Message Sanitization
Provides centralized, secure error response creation with mandatory correlation IDs.

Features:
- Consistent error response format across all endpoints
- Mandatory correlation ID tracking
- No internal details exposed regardless of DEBUG setting
- Integration with LogSanitizationService
- Support for web and API responses

Complies with: .claude/rules.md Rule #5 (No Debug Information in Production)
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from http import HTTPStatus

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, DatabaseError

from apps.core.middleware.logging_sanitization import LogSanitizationService

logger = logging.getLogger(__name__)


class ErrorResponseFactory:
    """
    Factory for creating standardized, secure error responses.

    All error responses:
    - Include correlation ID for tracking
    - Use generic user-facing messages
    - Never expose internal details or stack traces
    - Follow consistent format across API and web
    - Are logged with full details server-side
    """

    ERROR_MESSAGES = {
        'VALIDATION_ERROR': 'Invalid input data provided',
        'PERMISSION_DENIED': 'You do not have permission to perform this action',
        'AUTHENTICATION_REQUIRED': 'Authentication required to access this resource',
        'DATABASE_ERROR': 'Unable to process request at this time',
        'RESOURCE_NOT_FOUND': 'Requested resource not found',
        'RATE_LIMIT_EXCEEDED': 'Too many requests - please try again later',
        'FILE_UPLOAD_ERROR': 'File upload failed - please check file format and size',
        'INTERNAL_ERROR': 'An unexpected error occurred',
        'SERVICE_UNAVAILABLE': 'Service temporarily unavailable',
        'BUSINESS_RULE_VIOLATION': 'Operation violates business rules',
    }

    @classmethod
    def create_api_error_response(
        cls,
        error_code: str,
        message: Optional[str] = None,
        status_code: int = 400,
        correlation_id: Optional[str] = None,
        field_errors: Optional[Dict[str, List[str]]] = None,
    ) -> JsonResponse:
        """
        Create standardized JSON error response for API endpoints.

        Args:
            error_code: Application error code (e.g., 'VALIDATION_ERROR')
            message: Optional custom message (defaults to standard message)
            status_code: HTTP status code
            correlation_id: Request correlation ID
            field_errors: Field-specific validation errors

        Returns:
            JsonResponse with standardized error structure
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        if message is None:
            message = cls.ERROR_MESSAGES.get(error_code, cls.ERROR_MESSAGES['INTERNAL_ERROR'])

        sanitized_message = LogSanitizationService.sanitize_message(message)

        response_data = {
            'success': False,
            'error': {
                'code': error_code,
                'message': sanitized_message,
                'correlation_id': correlation_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
            }
        }

        if field_errors:
            sanitized_errors = {}
            for field, errors in field_errors.items():
                sanitized_errors[field] = [
                    LogSanitizationService.sanitize_message(str(err))
                    for err in errors
                ]
            response_data['error']['field_errors'] = sanitized_errors

        logger.warning(
            f"API error response generated: {error_code}",
            extra={
                'correlation_id': correlation_id,
                'error_code': error_code,
                'status_code': status_code,
            }
        )

        return JsonResponse(response_data, status=status_code)

    @classmethod
    def create_web_error_response(
        cls,
        request,
        error_code: str,
        message: Optional[str] = None,
        status_code: int = 400,
        correlation_id: Optional[str] = None,
        template: Optional[str] = None,
    ) -> HttpResponse:
        """
        Create standardized HTML error response for web requests.

        Args:
            request: Django HttpRequest
            error_code: Application error code
            message: Optional custom message
            status_code: HTTP status code
            correlation_id: Request correlation ID
            template: Custom error template path

        Returns:
            Rendered error page or simple HttpResponse
        """
        if correlation_id is None:
            correlation_id = getattr(request, 'correlation_id', str(uuid.uuid4()))

        if message is None:
            message = cls.ERROR_MESSAGES.get(error_code, cls.ERROR_MESSAGES['INTERNAL_ERROR'])

        if template is None:
            template = cls._get_default_template(status_code)

        sanitized_message = LogSanitizationService.sanitize_message(message)

        context = {
            'correlation_id': correlation_id,
            'error_message': sanitized_message,
            'error_code': error_code,
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@youtility.com'),
        }

        logger.warning(
            f"Web error response generated: {error_code}",
            extra={
                'correlation_id': correlation_id,
                'error_code': error_code,
                'status_code': status_code,
                'path': request.path,
            }
        )

        try:
            return render(request, template, context, status=status_code)
        except (TypeError, ValidationError, ValueError) as e:
            logger.error(
                f"Template rendering failed: {type(e).__name__}",
                extra={
                    'correlation_id': correlation_id,
                    'template': template,
                }
            )
            return HttpResponse(
                f"Error {status_code}: {sanitized_message}. Reference: {correlation_id}",
                status=status_code,
            )

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        request_type: str = 'api',
        request=None,
        correlation_id: Optional[str] = None,
    ):
        """
        Create error response from exception with automatic classification.

        Args:
            exception: The exception to convert
            request_type: 'api' or 'web'
            request: Django HttpRequest (required for web responses)
            correlation_id: Optional correlation ID

        Returns:
            JsonResponse or HttpResponse based on request_type
        """
        error_code, status_code = cls._classify_exception(exception)

        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        logger.error(
            f"Exception converted to error response: {type(exception).__name__}",
            extra={
                'correlation_id': correlation_id,
                'exception_type': type(exception).__name__,
                'exception_message': LogSanitizationService.sanitize_message(str(exception)),
            }
        )

        if request_type == 'api':
            return cls.create_api_error_response(
                error_code=error_code,
                status_code=status_code,
                correlation_id=correlation_id,
            )
        else:
            if request is None:
                raise ValueError("request parameter required for web error responses")
            return cls.create_web_error_response(
                request=request,
                error_code=error_code,
                status_code=status_code,
                correlation_id=correlation_id,
            )

    @staticmethod
    def _classify_exception(exception: Exception) -> tuple:
        """
        Classify exception and return appropriate error code and status.

        Returns:
            tuple: (error_code, http_status_code)
        """
        if isinstance(exception, ValidationError):
            return ('VALIDATION_ERROR', HTTPStatus.BAD_REQUEST)
        elif isinstance(exception, PermissionDenied):
            return ('PERMISSION_DENIED', HTTPStatus.FORBIDDEN)
        elif isinstance(exception, IntegrityError):
            return ('DATABASE_ERROR', HTTPStatus.CONFLICT)
        elif isinstance(exception, DatabaseError):
            return ('DATABASE_ERROR', HTTPStatus.INTERNAL_SERVER_ERROR)
        elif hasattr(exception, '__class__') and 'NotFound' in exception.__class__.__name__:
            return ('RESOURCE_NOT_FOUND', HTTPStatus.NOT_FOUND)
        elif hasattr(exception, 'error_code'):
            return (exception.error_code, getattr(exception, 'http_status', HTTPStatus.BAD_REQUEST))
        else:
            return ('INTERNAL_ERROR', HTTPStatus.INTERNAL_SERVER_ERROR)

    @staticmethod
    def _get_default_template(status_code: int) -> str:
        """Get default error template for status code."""
        template_map = {
            400: 'errors/400.html',
            403: 'errors/403.html',
            404: 'errors/404.html',
            429: 'errors/429.html',
            500: 'errors/500.html',
        }
        return template_map.get(status_code, 'errors/500.html')

    @classmethod
    def create_validation_error_response(
        cls,
        field_errors: Dict[str, List[str]],
        correlation_id: Optional[str] = None,
        request_type: str = 'api',
        request=None,
    ):
        """
        Create error response specifically for validation errors.

        Args:
            field_errors: Dictionary of field names to error messages
            correlation_id: Optional correlation ID
            request_type: 'api' or 'web'
            request: Django HttpRequest (required for web)

        Returns:
            Appropriate error response based on request type
        """
        if request_type == 'api':
            return cls.create_api_error_response(
                error_code='VALIDATION_ERROR',
                status_code=HTTPStatus.BAD_REQUEST,
                correlation_id=correlation_id,
                field_errors=field_errors,
            )
        else:
            if request is None:
                raise ValueError("request parameter required for web error responses")

            error_message = "Please correct the errors below"
            if field_errors:
                first_field_errors = next(iter(field_errors.values()))
                if first_field_errors:
                    error_message = first_field_errors[0]

            return cls.create_web_error_response(
                request=request,
                error_code='VALIDATION_ERROR',
                message=error_message,
                status_code=HTTPStatus.BAD_REQUEST,
                correlation_id=correlation_id,
            )

    @classmethod
    def create_success_response(
        cls,
        data: Optional[Dict[str, Any]] = None,
        message: str = "Operation completed successfully",
        status_code: int = 200,
        correlation_id: Optional[str] = None,
    ) -> JsonResponse:
        """
        Create standardized success response for API endpoints.

        Args:
            data: Response data payload
            message: Success message
            status_code: HTTP status code
            correlation_id: Request correlation ID

        Returns:
            JsonResponse with standardized success format
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        response_data = {
            'success': True,
            'message': message,
            'correlation_id': correlation_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }

        if data is not None:
            response_data['data'] = data

        return JsonResponse(response_data, status=status_code)


__all__ = ['ErrorResponseFactory']