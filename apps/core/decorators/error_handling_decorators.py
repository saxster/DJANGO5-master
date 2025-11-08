"""
Error Handling Decorators

Provides zero-friction error handling for view functions with:
- Automatic correlation ID extraction
- Standardized error responses
- Comprehensive logging
- Exception classification

Usage:
    from apps.core.decorators import safe_api_view
from apps.core.exceptions.patterns import TEMPLATE_EXCEPTIONS


    @safe_api_view()
    def my_api_view(request):
        # Automatic error handling with correlation IDs
        user.save()
        return JsonResponse({'status': 'ok'})

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: Correlation ID tracking
"""

from functools import wraps
import logging

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

from apps.core.error_handling import ErrorHandler
from apps.core.middleware.correlation_id_middleware import get_correlation_id
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    VALIDATION_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    FILE_EXCEPTIONS
)

logger = logging.getLogger(__name__)


def safe_api_view(
    error_code='INTERNAL_ERROR',
    status_code=500,
    log_exceptions=True
):
    """
    Decorator for API views with automatic error handling and correlation IDs.

    Features:
    - Catches specific exception types
    - Logs with correlation IDs
    - Returns standardized JSON error responses
    - Preserves original response on success

    Usage:
        @safe_api_view(error_code='VALIDATION_ERROR', status_code=400)
        def my_view(request):
            return JsonResponse({'data': 'success'})

    Args:
        error_code: Error code for client (default: INTERNAL_ERROR)
        status_code: HTTP status code (default: 500)
        log_exceptions: Whether to log exceptions (default: True)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            correlation_id = get_correlation_id() or getattr(request, 'correlation_id', None)

            try:
                return view_func(request, *args, **kwargs)

            except VALIDATION_EXCEPTIONS as e:
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={
                            'view': view_func.__name__,
                            'path': request.path,
                            'method': request.method
                        },
                        correlation_id=correlation_id,
                        level='warning'
                    )
                return JsonResponse(
                    {
                        'success': False,
                        'error': {
                            'code': 'VALIDATION_ERROR',
                            'message': 'Invalid input data',
                            'correlation_id': correlation_id
                        }
                    },
                    status=400
                )

            except DATABASE_EXCEPTIONS as e:
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={
                            'view': view_func.__name__,
                            'path': request.path
                        },
                        correlation_id=correlation_id,
                        level='error'
                    )
                return JsonResponse(
                    {
                        'success': False,
                        'error': {
                            'code': 'DATABASE_ERROR',
                            'message': 'Database operation failed',
                            'correlation_id': correlation_id
                        }
                    },
                    status=500
                )

            except NETWORK_EXCEPTIONS as e:
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={
                            'view': view_func.__name__,
                            'path': request.path
                        },
                        correlation_id=correlation_id,
                        level='error'
                    )
                return JsonResponse(
                    {
                        'success': False,
                        'error': {
                            'code': 'NETWORK_ERROR',
                            'message': 'External service unavailable',
                            'correlation_id': correlation_id
                        }
                    },
                    status=503
                )

            except FILE_EXCEPTIONS as e:
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={
                            'view': view_func.__name__,
                            'path': request.path
                        },
                        correlation_id=correlation_id,
                        level='error'
                    )
                return JsonResponse(
                    {
                        'success': False,
                        'error': {
                            'code': 'FILE_ERROR',
                            'message': 'File operation failed',
                            'correlation_id': correlation_id
                        }
                    },
                    status=500
                )

            except (ValueError, TypeError, AttributeError) as e:
                # Last resort - unexpected exception
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={
                            'view': view_func.__name__,
                            'path': request.path,
                            'unexpected': True
                        },
                        correlation_id=correlation_id,
                        level='critical'
                    )
                return JsonResponse(
                    {
                        'success': False,
                        'error': {
                            'code': error_code,
                            'message': 'An error occurred',
                            'correlation_id': correlation_id
                        }
                    },
                    status=status_code
                )

        return wrapper
    return decorator


def safe_view(template_name='errors/500.html', log_exceptions=True):
    """
    Decorator for Django views (non-API) with automatic error handling.

    Features:
    - Catches specific exception types
    - Logs with correlation IDs
    - Renders error templates
    - Falls back to simple HTTP response

    Usage:
        @safe_view(template_name='errors/custom_error.html')
        def my_view(request):
            return render(request, 'my_template.html', context)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            correlation_id = get_correlation_id() or getattr(request, 'correlation_id', None)

            try:
                return view_func(request, *args, **kwargs)

            except (ValidationError, ValueError, TypeError) as e:
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={'view': view_func.__name__, 'path': request.path},
                        correlation_id=correlation_id,
                        level='warning'
                    )
                context = {
                    'correlation_id': correlation_id,
                    'error_message': 'Invalid request data'
                }
                try:
                    return render(request, 'errors/400.html', context, status=400)
                except TEMPLATE_EXCEPTIONS as e:
                    return HttpResponse(
                        f'Bad Request. Correlation ID: {correlation_id}',
                        status=400
                    )

            except DATABASE_EXCEPTIONS as e:
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={'view': view_func.__name__, 'path': request.path},
                        correlation_id=correlation_id,
                        level='error'
                    )
                context = {
                    'correlation_id': correlation_id,
                    'error_message': 'A database error occurred'
                }
                try:
                    return render(request, template_name, context, status=500)
                except TEMPLATE_EXCEPTIONS as e:
                    return HttpResponse(
                        f'Server Error. Correlation ID: {correlation_id}',
                        status=500
                    )

            except TEMPLATE_EXCEPTIONS as e:
                if log_exceptions:
                    ErrorHandler.handle_exception(
                        e,
                        context={'view': view_func.__name__, 'path': request.path, 'unexpected': True},
                        correlation_id=correlation_id,
                        level='critical'
                    )
                context = {
                    'correlation_id': correlation_id,
                    'error_message': 'An unexpected error occurred'
                }
                try:
                    return render(request, template_name, context, status=500)
                except TEMPLATE_EXCEPTIONS as e:
                    return HttpResponse(
                        f'Server Error. Correlation ID: {correlation_id}',
                        status=500
                    )

        return wrapper
    return decorator


__all__ = [
    'safe_api_view',
    'safe_view'
]
