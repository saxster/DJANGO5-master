"""
Versioned Exception Handler for DRF
Provides consistent error responses across API versions.

Compliance with .claude/rules.md:
- Rule #5: No debug information in responses
- Rule #11: Specific exception handling
- Rule #15: No sensitive data logging
"""

import logging
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger('api.exceptions')


def versioned_exception_handler(exc, context):
    """
    Custom exception handler that provides versioned, secure error responses.

    Returns:
    - Sanitized error messages (no stack traces)
    - Correlation IDs for tracking
    - Version-specific response format
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        response = _handle_django_exceptions(exc, context)

    if response is not None:
        _enhance_error_response(response, exc, context)

    return response


def _handle_django_exceptions(exc, context):
    """Handle Django-specific exceptions not covered by DRF."""
    if isinstance(exc, PermissionDenied):
        return Response(
            {'error': 'Permission Denied', 'message': str(exc)},
            status=status.HTTP_403_FORBIDDEN
        )

    if isinstance(exc, ValidationError):
        return Response(
            {'error': 'Validation Error', 'message': exc.messages if hasattr(exc, 'messages') else str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )

    if isinstance(exc, (ObjectDoesNotExist, Http404)):
        return Response(
            {'error': 'Not Found', 'message': 'The requested resource was not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    return None


def _enhance_error_response(response, exc, context):
    """Add correlation ID and version info to error responses."""
    request = context.get('request')

    correlation_id = ErrorHandler.handle_exception(
        exc,
        context={'view': context.get('view').__class__.__name__ if context.get('view') else 'Unknown'},
        level='warning'
    )

    response.data = {
        'error': response.data.get('detail') or _get_error_type(exc),
        'message': _get_safe_error_message(exc),
        'correlation_id': correlation_id,
        'timestamp': timezone.now().isoformat(),
        'status_code': response.status_code,
    }

    if request:
        api_version = _extract_api_version(request)
        response['X-API-Version'] = api_version
        response.data['api_version'] = api_version


def _get_error_type(exc):
    """Get user-friendly error type from exception."""
    if isinstance(exc, PermissionDenied):
        return 'Permission Denied'
    if isinstance(exc, ValidationError):
        return 'Validation Error'
    if isinstance(exc, (ObjectDoesNotExist, Http404)):
        return 'Not Found'
    return 'Internal Server Error'


def _get_safe_error_message(exc):
    """Get safe error message without exposing sensitive details."""
    if hasattr(exc, 'detail'):
        return str(exc.detail)
    if isinstance(exc, ValidationError) and hasattr(exc, 'messages'):
        return '; '.join(exc.messages)
    if str(exc):
        return str(exc)
    return 'An error occurred processing your request'


def _extract_api_version(request):
    """Extract API version from request path or headers."""
    import re

    match = re.search(r'/api/(v\d+)/', request.path)
    if match:
        return match.group(1)

    accept_version = request.META.get('HTTP_ACCEPT_VERSION')
    if accept_version:
        return accept_version

    return 'v1'


__all__ = ['versioned_exception_handler']