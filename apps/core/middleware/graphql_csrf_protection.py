"""
GraphQL-specific CSRF Protection Middleware

This middleware provides comprehensive CSRF protection for GraphQL endpoints while
maintaining support for file uploads and backward compatibility.

Security Features:
- Validates CSRF tokens for all GraphQL mutations
- Allows queries without CSRF tokens (read-only operations)
- Supports both header and form-based CSRF token submission
- Maintains file upload functionality
- Provides detailed security logging
- Implements rate limiting for GraphQL operations

Compliance: Addresses CVSS 8.1 vulnerability - CSRF Protection Bypass on GraphQL

IMPORTANT: Middleware Ordering
This middleware MUST be placed BEFORE Django's CsrfViewMiddleware in settings.MIDDLEWARE:

    MIDDLEWARE = [
        ...
        "apps.core.middleware.graphql_csrf_protection.GraphQLCSRFProtectionMiddleware",  # FIRST
        ...
        "django.middleware.csrf.CsrfViewMiddleware",  # SECOND (global CSRF)
        ...
    ]

Architecture:
- This middleware identifies GraphQL mutations and prepares the request
- Django's global CsrfViewMiddleware performs the actual validation
- No duplicate CSRF instances (performance optimization)
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Union

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.views.decorators.csrf import csrf_exempt
from django.utils.cache import get_cache_key
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import PermissionDenied
from django.core.cache import cache

from apps.core.error_handling import CorrelationIDMiddleware


# Security logging
security_logger = logging.getLogger('security')
graphql_logger = logging.getLogger('graphql_security')


class GraphQLCSRFProtectionMiddleware(MiddlewareMixin):
    """
    GraphQL-specific CSRF protection middleware that enforces CSRF validation
    for mutations while allowing queries to pass through.

    This middleware addresses the critical CSRF vulnerability (CVSS 8.1) in
    GraphQL endpoints by removing the blanket csrf_exempt and implementing
    smart CSRF protection based on operation type.

    Design Pattern:
    - This middleware identifies GraphQL operations (query/mutation/subscription)
    - For mutations, it ensures CSRF token is present and accessible
    - Django's global CsrfViewMiddleware (later in the stack) performs validation
    - This avoids duplicate CSRF middleware instances
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        # NOTE: We do NOT create a duplicate CsrfViewMiddleware instance
        # The global CsrfViewMiddleware in settings.MIDDLEWARE handles validation
        self.graphql_paths = getattr(settings, 'GRAPHQL_PATHS', [
            '/api/graphql/',
            '/graphql/',
            '/graphql'
        ])
        self.rate_limit_cache_prefix = 'graphql_rate_limit'
        self.rate_limit_window = getattr(settings, 'GRAPHQL_RATE_LIMIT_WINDOW', 300)  # 5 minutes
        self.rate_limit_max_requests = getattr(settings, 'GRAPHQL_RATE_LIMIT_MAX', 100)

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming GraphQL requests and apply appropriate CSRF protection.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse if request should be blocked, None to continue processing
        """
        if not self._is_graphql_request(request):
            return None

        # Add correlation ID for security tracking
        correlation_id = getattr(request, 'correlation_id', None)
        if not correlation_id:
            correlation_id = CorrelationIDMiddleware.generate_correlation_id()
            request.correlation_id = correlation_id

        # Log GraphQL request for security monitoring
        self._log_graphql_request(request, correlation_id)

        # Apply rate limiting
        rate_limit_response = self._check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response

        # Skip CSRF validation for introspection queries in development
        if settings.DEBUG and self._is_introspection_query(request):
            graphql_logger.info(
                f"Introspection query allowed in development mode. "
                f"Correlation ID: {correlation_id}"
            )
            return None

        # Parse GraphQL operation to determine if CSRF protection is needed
        operation_type = self._get_graphql_operation_type(request)

        if operation_type == 'query':
            # Queries are read-only, no CSRF protection needed
            graphql_logger.debug(
                f"GraphQL query operation - CSRF validation skipped. "
                f"Correlation ID: {correlation_id}"
            )
            return None

        elif operation_type == 'mutation':
            # Mutations modify state, require CSRF protection
            return self._validate_csrf_for_mutation(request, correlation_id)

        elif operation_type == 'subscription':
            # Subscriptions generally don't modify state, but validate anyway for security
            graphql_logger.info(
                f"GraphQL subscription operation - applying CSRF validation. "
                f"Correlation ID: {correlation_id}"
            )
            return self._validate_csrf_for_mutation(request, correlation_id)

        else:
            # Unknown operation type, apply CSRF protection by default
            security_logger.warning(
                f"Unknown GraphQL operation type '{operation_type}' - "
                f"applying CSRF protection by default. Correlation ID: {correlation_id}"
            )
            return self._validate_csrf_for_mutation(request, correlation_id)

    def _is_graphql_request(self, request: HttpRequest) -> bool:
        """Check if the request is for a GraphQL endpoint."""
        return any(request.path.startswith(path) for path in self.graphql_paths)

    def _is_introspection_query(self, request: HttpRequest) -> bool:
        """
        Check if the request is a GraphQL introspection query.
        Introspection queries are typically allowed without CSRF in development.
        """
        try:
            if request.method == 'GET' and 'query' in request.GET:
                query = request.GET.get('query', '')
            elif request.method == 'POST':
                if request.content_type == 'application/json':
                    data = json.loads(request.body.decode('utf-8'))
                    query = data.get('query', '')
                else:
                    query = request.POST.get('query', '')
            else:
                return False

            # Check for introspection patterns
            introspection_patterns = [
                '__schema',
                '__type',
                'IntrospectionQuery',
                'query IntrospectionQuery'
            ]

            return any(pattern in query for pattern in introspection_patterns)

        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            return False

    def _get_graphql_operation_type(self, request: HttpRequest) -> str:
        """
        Determine the GraphQL operation type (query, mutation, subscription).

        Returns:
            str: The operation type, or 'unknown' if it cannot be determined
        """
        try:
            query = None

            if request.method == 'GET' and 'query' in request.GET:
                query = request.GET.get('query', '')
            elif request.method == 'POST':
                if request.content_type == 'application/json':
                    data = json.loads(request.body.decode('utf-8'))
                    query = data.get('query', '')
                else:
                    query = request.POST.get('query', '')

            if not query:
                return 'unknown'

            # Simple parsing to detect operation type
            query = query.strip()

            if query.startswith('query') or query.startswith('{'):
                return 'query'
            elif query.startswith('mutation'):
                return 'mutation'
            elif query.startswith('subscription'):
                return 'subscription'
            else:
                # Try to detect based on keywords
                if 'mutation' in query.lower():
                    return 'mutation'
                elif 'subscription' in query.lower():
                    return 'subscription'
                else:
                    return 'query'  # Default to query for safety

        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            graphql_logger.warning(
                f"Failed to parse GraphQL operation type from request. "
                f"Path: {request.path}, Method: {request.method}"
            )
            return 'unknown'

    def _validate_csrf_for_mutation(self, request: HttpRequest, correlation_id: str) -> Optional[HttpResponse]:
        """
        Prepare GraphQL mutation for CSRF validation by global CsrfViewMiddleware.

        This method ensures the CSRF token is present and accessible, then delegates
        actual validation to Django's global CsrfViewMiddleware (later in the stack).

        Args:
            request: The HTTP request
            correlation_id: Request correlation ID for tracking

        Returns:
            HttpResponse if token is missing, None to continue (validation happens later)
        """
        # Check for CSRF token in various places
        csrf_token = self._get_csrf_token_from_request(request)

        if not csrf_token:
            security_logger.error(
                f"GraphQL mutation attempted without CSRF token. "
                f"Path: {request.path}, User: {getattr(request, 'user', 'anonymous')}, "
                f"IP: {self._get_client_ip(request)}, Correlation ID: {correlation_id}"
            )
            return self._create_csrf_error_response(
                "CSRF token missing. GraphQL mutations require CSRF protection.",
                correlation_id
            )

        # Ensure token is in request.POST or request.META for global middleware
        # This makes the token accessible to Django's CsrfViewMiddleware
        if csrf_token:
            # Store in META for CsrfViewMiddleware to validate
            request.META['HTTP_X_CSRFTOKEN'] = csrf_token

        graphql_logger.info(
            f"GraphQL mutation prepared for CSRF validation. "
            f"Path: {request.path}, User: {getattr(request, 'user', 'anonymous')}, "
            f"Correlation ID: {correlation_id}"
        )

        # Return None - global CsrfViewMiddleware will validate
        # If validation fails, it will return 403 response
        return None

    def _get_csrf_token_from_request(self, request: HttpRequest) -> Optional[str]:
        """
        Extract CSRF token from request headers or form data.

        Args:
            request: The HTTP request

        Returns:
            str: The CSRF token if found, None otherwise
        """
        # Check X-CSRFToken header (for AJAX requests)
        csrf_token = request.META.get('HTTP_X_CSRFTOKEN')
        if csrf_token:
            return csrf_token

        # Check X-CSRF-Token header (alternative header name)
        csrf_token = request.META.get('HTTP_X_CSRF_TOKEN')
        if csrf_token:
            return csrf_token

        # Check form data (for regular form submissions)
        if request.method == 'POST':
            csrf_token = request.POST.get('csrfmiddlewaretoken')
            if csrf_token:
                return csrf_token

            # For JSON requests, check if token is in the JSON body
            try:
                if request.content_type == 'application/json':
                    data = json.loads(request.body.decode('utf-8'))
                    csrf_token = data.get('csrfmiddlewaretoken')
                    if csrf_token:
                        return csrf_token
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return None

    def _check_rate_limit(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Apply rate limiting to GraphQL requests.

        Args:
            request: The HTTP request

        Returns:
            HttpResponse if rate limit exceeded, None otherwise
        """
        if not getattr(settings, 'ENABLE_GRAPHQL_RATE_LIMITING', True):
            return None

        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None

        # Create rate limit key (use user ID if authenticated, otherwise IP)
        if user_id:
            rate_limit_key = f"{self.rate_limit_cache_prefix}:user:{user_id}"
        else:
            rate_limit_key = f"{self.rate_limit_cache_prefix}:ip:{client_ip}"

        # Check current rate limit
        current_requests = cache.get(rate_limit_key, 0)

        if current_requests >= self.rate_limit_max_requests:
            security_logger.warning(
                f"GraphQL rate limit exceeded. "
                f"Key: {rate_limit_key}, Requests: {current_requests}, "
                f"Limit: {self.rate_limit_max_requests}"
            )

            return JsonResponse({
                'errors': [{
                    'message': 'Rate limit exceeded. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'timestamp': time.time()
                }]
            }, status=429)

        # Increment rate limit counter
        cache.set(rate_limit_key, current_requests + 1, self.rate_limit_window)

        return None

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip

    def _log_graphql_request(self, request: HttpRequest, correlation_id: str):
        """Log GraphQL request for security monitoring."""
        graphql_logger.info(
            f"GraphQL request: {request.method} {request.path} - "
            f"User: {getattr(request, 'user', 'anonymous')}, "
            f"IP: {self._get_client_ip(request)}, "
            f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'unknown')}, "
            f"Correlation ID: {correlation_id}"
        )

    def _create_csrf_error_response(self, message: str, correlation_id: str) -> JsonResponse:
        """
        Create a standardized CSRF error response.

        Args:
            message: Error message to include
            correlation_id: Request correlation ID

        Returns:
            JsonResponse with error details
        """
        return JsonResponse({
            'errors': [{
                'message': message,
                'code': 'CSRF_TOKEN_REQUIRED',
                'timestamp': time.time(),
                'correlation_id': correlation_id,
                'help': {
                    'csrf_token_header': 'Include CSRF token in X-CSRFToken header',
                    'csrf_token_form': 'Include csrfmiddlewaretoken in form data',
                    'csrf_token_json': 'Include csrfmiddlewaretoken in JSON body'
                }
            }]
        }, status=403)


class GraphQLSecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers specifically for GraphQL responses.
    """

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add security headers to GraphQL responses."""
        if hasattr(request, 'path') and any(request.path.startswith(path) for path in ['/api/graphql/', '/graphql/', '/graphql']):
            # Add GraphQL-specific security headers
            response['X-GraphQL-CSRF-Protected'] = 'true'
            response['X-GraphQL-Rate-Limited'] = 'true'
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'

            # Add CSP header for GraphQL responses
            if not response.get('Content-Security-Policy'):
                response['Content-Security-Policy'] = "default-src 'self'; script-src 'none'"

        return response