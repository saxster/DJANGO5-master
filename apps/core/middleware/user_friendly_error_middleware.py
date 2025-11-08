"""
User-Friendly Error Handling Middleware
Transforms technical errors into user-friendly messages with context and recovery suggestions
"""

import json
import logging
import traceback
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import (
    HttpResponseServerError,
    HttpResponseNotFound,
    HttpResponseForbidden,
    JsonResponse
)
from django.shortcuts import render
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse
from apps.core.exceptions.patterns import TEMPLATE_EXCEPTIONS

logger = logging.getLogger(__name__)


class UserFriendlyErrorMiddleware(MiddlewareMixin):
    """
    Middleware to catch exceptions and transform them into user-friendly responses
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_templates = {
            400: 'errors/400.html',
            403: 'errors/403.html',
            404: 'errors/404.html',
            500: 'errors/500.html',
        }

    def process_exception(self, request, exception):
        """
        Process exceptions and return user-friendly error responses
        """
        try:
            # Log the original error for debugging
            self.log_error(request, exception)

            # Get error context
            error_context = self.get_error_context(request, exception)

            # Determine response type
            if self.is_api_request(request):
                return self.create_api_error_response(request, exception, error_context)
            else:
                return self.create_html_error_response(request, exception, error_context)

        except (ValueError, TypeError, AttributeError) as middleware_error:
            # Fallback if middleware itself fails
            logger.critical(
                f"Error middleware failed: {middleware_error}",
                exc_info=True,
                extra={'path': getattr(request, 'path', 'unknown')}
            )
            return self.create_fallback_response(request)

    def log_error(self, request, exception):
        """
        Log error with user and request context
        """
        user_info = 'Anonymous'
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_info = f"{request.user.id}:{getattr(request.user, 'loginid', 'unknown')}"

        error_context = {
            'user': user_info,
            'path': request.path,
            'method': request.method,
            'ip': self.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'session_key': request.session.session_key if hasattr(request, 'session') else None,
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
        }

        logger.error(
            f"User-facing error: {type(exception).__name__} at {request.path}",
            extra=error_context,
            exc_info=True
        )

    def get_error_context(self, request, exception) -> Dict[str, Any]:
        """
        Generate user-friendly error context
        """
        error_type = type(exception).__name__
        status_code = self.get_status_code(exception)

        # Base error context
        context = {
            'error_id': self.generate_error_id(),
            'status_code': status_code,
            'error_type': error_type,
            'user_message': self.get_user_friendly_message(exception),
            'recovery_suggestions': self.get_recovery_suggestions(exception, request),
            'support_context': self.get_support_context(request),
            'technical_details': self.get_technical_details(exception) if settings.DEBUG else None,
            'timestamp': timezone.now().isoformat(),
        }

        # Add specific context based on error type
        if isinstance(exception, ValidationError):
            context.update(self.get_validation_error_context(exception))
        elif isinstance(exception, PermissionDenied):
            context.update(self.get_permission_error_context(exception, request))
        elif status_code == 404:
            context.update(self.get_not_found_context(request))

        return context

    def get_user_friendly_message(self, exception) -> str:
        """
        Convert technical exceptions to user-friendly messages
        """
        error_messages = {
            'ValidationError': 'The information you provided is not valid. Please check your input and try again.',
            'PermissionDenied': 'You don\'t have permission to access this resource.',
            'Http404': 'The page or resource you\'re looking for cannot be found.',
            'ConnectionError': 'We\'re having trouble connecting to our servers. Please try again in a moment.',
            'TimeoutError': 'The request took too long to complete. Please try again.',
            'IntegrityError': 'This action conflicts with existing data. Please check for duplicates.',
            'ObjectDoesNotExist': 'The requested item no longer exists or has been removed.',
            'ImproperlyConfigured': 'The system is not configured properly. Please contact support.',
        }

        exception_name = type(exception).__name__
        return error_messages.get(exception_name, 'An unexpected error occurred. Please try again or contact support.')

    def get_recovery_suggestions(self, exception, request) -> List[str]:
        """
        Get contextual recovery suggestions
        """
        suggestions = []
        error_type = type(exception).__name__

        if error_type == 'ValidationError':
            suggestions.extend([
                'Double-check all required fields are filled out',
                'Verify that email addresses and phone numbers are in the correct format',
                'Make sure passwords meet the security requirements',
                'Clear your browser cache and try again'
            ])

        elif error_type == 'PermissionDenied':
            suggestions.extend([
                'Contact your administrator to request access',
                'Try logging out and logging back in',
                'Check if you\'re accessing the correct site or business unit'
            ])

        elif error_type in ['Http404', 'ObjectDoesNotExist']:
            suggestions.extend([
                'Check the URL for typos',
                'Go back to the previous page and try again',
                'Use the search function to find what you\'re looking for',
                'Visit the home page to start over'
            ])

        elif error_type in ['ConnectionError', 'TimeoutError']:
            suggestions.extend([
                'Check your internet connection',
                'Try refreshing the page',
                'Wait a few minutes and try again',
                'Try accessing from a different device or network'
            ])

        else:
            # Generic suggestions
            suggestions.extend([
                'Try refreshing the page',
                'Clear your browser cache and cookies',
                'Try again in a few minutes',
                'Contact support if the problem persists'
            ])

        return suggestions

    def get_support_context(self, request) -> Dict[str, str]:
        """
        Get support context for error reporting
        """
        from django.core.exceptions import DisallowedHost

        # Safely get page URL (may fail if HTTP_HOST not in ALLOWED_HOSTS)
        try:
            page_url = request.build_absolute_uri()
        except DisallowedHost:
            # Fallback to relative path
            page_url = request.path

        return {
            'error_id': self.generate_error_id(),
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'page_url': page_url,
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown')[:100],
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@youtility.com'),
            'support_phone': getattr(settings, 'SUPPORT_PHONE', '+1-800-YOUTILITY'),
        }

    def get_validation_error_context(self, exception) -> Dict[str, Any]:
        """
        Get specific context for validation errors
        """
        field_errors = {}

        if hasattr(exception, 'error_dict'):
            for field, errors in exception.error_dict.items():
                field_errors[field] = [str(error) for error in errors]
        elif hasattr(exception, 'error_list'):
            field_errors['non_field_errors'] = [str(error) for error in exception.error_list]

        return {
            'field_errors': field_errors,
            'error_category': 'validation',
            'can_retry': True,
        }

    def get_permission_error_context(self, exception, request) -> Dict[str, Any]:
        """
        Get specific context for permission errors
        """
        user = getattr(request, 'user', AnonymousUser())

        return {
            'error_category': 'permission',
            'is_authenticated': user.is_authenticated,
            'login_url': reverse('login') if not user.is_authenticated else None,
            'can_retry': False,
            'required_permission': str(exception) if str(exception) else None,
        }

    def get_not_found_context(self, request) -> Dict[str, Any]:
        """
        Get specific context for 404 errors
        """
        return {
            'error_category': 'not_found',
            'requested_path': request.path,
            'can_retry': True,
            'suggested_pages': self.get_suggested_pages(request),
        }

    def get_suggested_pages(self, request) -> List[Dict[str, str]]:
        """
        Get suggested pages based on the requested path
        """
        suggestions = [
            {'title': 'Dashboard', 'url': reverse('dashboard'), 'icon': 'dashboard'},
            {'title': 'People Directory', 'url': '/people/directory/', 'icon': 'people'},
            {'title': 'Tasks', 'url': '/operations/tasks/', 'icon': 'task'},
            {'title': 'Help Center', 'url': '/help/', 'icon': 'help'},
        ]

        # Add context-specific suggestions based on path
        if '/people/' in request.path:
            suggestions.insert(0, {'title': 'People Management', 'url': '/people/', 'icon': 'person'})
        elif '/admin/' in request.path:
            suggestions.insert(0, {'title': 'Admin Dashboard', 'url': '/admin/', 'icon': 'admin_panel_settings'})

        return suggestions

    def get_technical_details(self, exception) -> Dict[str, str]:
        """
        Get technical details for debugging (only in DEBUG mode)
        """
        return {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'traceback': traceback.format_exc() if settings.DEBUG else None,
        }

    def create_api_error_response(self, request, exception, context):
        """
        Create JSON error response for API requests
        """
        response_data = {
            'success': False,
            'status_code': context['status_code'],
            'message': context['user_message'],
            'error_code': context['error_type'],
            'error_id': context['error_id'],
            'meta': {
                'can_retry': context.get('can_retry', False),
                'support_context': context['support_context'],
                'recovery_suggestions': context['recovery_suggestions'],
            },
            'timestamp': context['timestamp'],
        }

        # Add technical details in debug mode
        if settings.DEBUG and context.get('technical_details'):
            response_data['debug'] = context['technical_details']

        return JsonResponse(response_data, status=context['status_code'])

    def create_html_error_response(self, request, exception, context):
        """
        Create HTML error page for regular requests
        """
        template = self.error_templates.get(context['status_code'], 'errors/500.html')

        try:
            return render(
                request,
                template,
                context=context,
                status=context['status_code']
            )
        except TEMPLATE_EXCEPTIONS as template_error:
            logger.error(
                f"Error template rendering failed: {template_error}",
                exc_info=True,
                extra={'template': template, 'status_code': context.get('status_code')}
            )
            return self.create_fallback_response(request)

    def create_fallback_response(self, request):
        """
        Create minimal fallback response when everything else fails
        """
        fallback_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Service Unavailable - YOUTILITY</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                    text-align: center;
                    padding: 2rem;
                    background: #f8fafd;
                    color: #374151;
                }
                .container {
                    max-width: 600px;
                    margin: 4rem auto;
                    background: white;
                    padding: 3rem;
                    border-radius: 1rem;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                h1 { color: #dc2626; margin-bottom: 1rem; }
                p { margin-bottom: 1.5rem; line-height: 1.6; }
                a {
                    color: #377dff;
                    text-decoration: none;
                    font-weight: 500;
                    padding: 0.5rem 1rem;
                    border: 1px solid #377dff;
                    border-radius: 0.5rem;
                    display: inline-block;
                    margin-top: 1rem;
                }
                a:hover { background: #377dff; color: white; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Service Temporarily Unavailable</h1>
                <p>We're experiencing technical difficulties. Our team has been notified and is working to resolve the issue.</p>
                <p>Please try again in a few minutes.</p>
                <a href="/">Return to Home</a>
            </div>
        </body>
        </html>
        """

        return HttpResponseServerError(fallback_html, content_type='text/html')

    # Utility methods
    def is_api_request(self, request) -> bool:
        """
        Determine if request is an API request
        """
        return (
            request.path.startswith('/api/') or
            request.META.get('HTTP_ACCEPT', '').startswith('application/json') or
            request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
        )

    def get_status_code(self, exception) -> int:
        """
        Get appropriate HTTP status code for exception
        """
        status_mapping = {
            'ValidationError': 400,
            'PermissionDenied': 403,
            'Http404': 404,
            'ObjectDoesNotExist': 404,
            'DoesNotExist': 404,
            'ImproperlyConfigured': 500,
            'ProgrammingError': 500,
            'OperationalError': 503,
            'ConnectionError': 503,
            'TimeoutError': 504,
        }

        exception_name = type(exception).__name__
        return status_mapping.get(exception_name, 500)

    def get_client_ip(self, request) -> str:
        """
        Get client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')

    def generate_error_id(self) -> str:
        """
        Generate unique error ID for tracking
        """
        import uuid
        return str(uuid.uuid4())[:8]

    def _safe_build_absolute_uri(self, request) -> str:
        """
        Safely build absolute URI, falling back to relative path on error.

        Handles DisallowedHost exception when HTTP_HOST is not in ALLOWED_HOSTS.
        """
        from django.core.exceptions import DisallowedHost

        try:
            return request.build_absolute_uri()
        except DisallowedHost:
            return request.path


class ErrorReportingService:
    """
    Service for handling user error reports
    """

    @staticmethod
    def create_error_report(error_context: Dict[str, Any], user_feedback: Optional[str] = None):
        """
        Create error report with user feedback
        """
        report = {
            'error_id': error_context.get('error_id'),
            'timestamp': error_context.get('timestamp'),
            'user_message': user_feedback,
            'error_context': {
                'status_code': error_context.get('status_code'),
                'error_type': error_context.get('error_type'),
                'user_message': error_context.get('user_message'),
            },
            'support_context': error_context.get('support_context'),
        }

        # Save to database or send to monitoring service
        logger.info(f"User error report created: {report['error_id']}", extra=report)

        return report


# Error page views
def custom_404_view(request, exception=None):
    """
    Custom 404 error page with helpful suggestions
    """
    context = {
        'error_id': ErrorReportingService.generate_error_id() if hasattr(ErrorReportingService, 'generate_error_id') else 'unknown',
        'user_message': 'The page you\'re looking for cannot be found.',
        'recovery_suggestions': [
            'Check the URL for typos',
            'Go back to the previous page',
            'Use the search function',
            'Visit the home page'
        ],
        'suggested_pages': [
            {'title': 'Dashboard', 'url': reverse('dashboard'), 'icon': 'dashboard'},
            {'title': 'People Directory', 'url': '/people/', 'icon': 'people'},
            {'title': 'Help Center', 'url': '/help/', 'icon': 'help'},
        ],
        'support_context': {
            'page_url': self._safe_build_absolute_uri(request),
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    }

    return render(request, 'errors/404.html', context, status=404)


def custom_500_view(request):
    """
    Custom 500 error page with support information
    """
    context = {
        'error_id': f"ERR-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        'user_message': 'We\'re experiencing technical difficulties. Our team has been notified and is working to resolve the issue.',
        'recovery_suggestions': [
            'Try refreshing the page',
            'Wait a few minutes and try again',
            'Clear your browser cache',
            'Contact support if the problem persists'
        ],
        'support_context': {
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@youtility.com'),
            'support_phone': getattr(settings, 'SUPPORT_PHONE', '+1-800-YOUTILITY'),
        }
    }

    return render(request, 'errors/500.html', context, status=500)


# Error component utilities
class ErrorMessageBuilder:
    """
    Utility class to build contextual error messages
    """

    @staticmethod
    def build_form_error_message(form_errors: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Build user-friendly form error message
        """
        error_count = sum(len(errors) for errors in form_errors.values())

        return {
            'title': 'Form Validation Error',
            'message': f'Please correct {error_count} error{"s" if error_count != 1 else ""} below:',
            'field_errors': form_errors,
            'suggestions': [
                'Check all required fields are filled out',
                'Verify that data is in the correct format',
                'Make sure there are no duplicate values where not allowed'
            ]
        }

    @staticmethod
    def build_permission_error_message(user, required_permission: str = None) -> Dict[str, Any]:
        """
        Build permission error message with context
        """
        if not user.is_authenticated:
            return {
                'title': 'Authentication Required',
                'message': 'You need to log in to access this page.',
                'suggestions': [
                    'Click the login button to sign in',
                    'Check if you have the correct username and password',
                    'Contact your administrator if you don\'t have an account'
                ],
                'action': {
                    'text': 'Go to Login',
                    'url': reverse('login'),
                    'icon': 'login'
                }
            }
        else:
            return {
                'title': 'Access Denied',
                'message': f'You don\'t have permission to access this resource.' +
                          (f' Required permission: {required_permission}' if required_permission else ''),
                'suggestions': [
                    'Contact your administrator to request access',
                    'Check if you\'re accessing the correct site',
                    'Try logging out and logging back in'
                ],
                'action': {
                    'text': 'Contact Support',
                    'url': '/help/contact/',
                    'icon': 'support'
                }
            }

    @staticmethod
    def build_network_error_message(error_type: str) -> Dict[str, Any]:
        """
        Build network error message
        """
        messages = {
            'timeout': {
                'title': 'Request Timeout',
                'message': 'The request took too long to complete.',
                'suggestions': [
                    'Check your internet connection',
                    'Try again with a simpler request',
                    'Contact support if this happens frequently'
                ]
            },
            'connection': {
                'title': 'Connection Error',
                'message': 'Unable to connect to the server.',
                'suggestions': [
                    'Check your internet connection',
                    'Verify the server is accessible',
                    'Try again in a few minutes'
                ]
            },
            'server': {
                'title': 'Server Error',
                'message': 'The server encountered an unexpected error.',
                'suggestions': [
                    'Try again in a few minutes',
                    'Contact support if the problem persists',
                    'Check the status page for known issues'
                ]
            }
        }

        return messages.get(error_type, messages['server'])