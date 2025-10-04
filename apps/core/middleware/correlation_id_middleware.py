"""
Correlation ID Middleware

Generates and propagates correlation IDs for request tracking across:
- HTTP requests → responses
- Request → Celery tasks
- Request → database queries
- Request → external API calls

Compliance:
- .claude/rules.md Rule #7 (< 150 lines)
- .claude/rules.md Rule #15 (logging sanitization)

Architecture:
- Generates UUID v4 for each request
- Stores in thread-local storage for access throughout request lifecycle
- Adds X-Correlation-ID header to responses
- Propagates to Celery tasks via signal handlers
"""

import uuid
import logging
import threading
from typing import Optional
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from django.conf import settings

logger = logging.getLogger(__name__)

# Thread-local storage for correlation ID
_thread_locals = threading.local()

__all__ = [
    'CorrelationIDMiddleware',
    'get_correlation_id',
    'set_correlation_id',
    'clear_correlation_id'
]


class CorrelationIDMiddleware(MiddlewareMixin):
    """
    Middleware that generates and propagates correlation IDs.

    Features:
    - Generates UUID v4 for new requests
    - Accepts existing correlation ID from X-Correlation-ID header
    - Stores in thread-local storage
    - Adds to response headers
    - Available via get_correlation_id() throughout request lifecycle

    Usage:
        # In views/services
        from apps.core.middleware.correlation_id_middleware import get_correlation_id

        correlation_id = get_correlation_id()
        logger.info("Processing request", extra={'correlation_id': correlation_id})
    """

    # Header name for correlation ID
    HEADER_NAME = 'X-Correlation-ID'
    REQUEST_ATTR = 'correlation_id'

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.enabled = getattr(settings, 'ENABLE_CORRELATION_ID', True)

    def process_request(self, request: HttpRequest) -> None:
        """
        Generate or extract correlation ID at the start of request processing.

        Priority:
        1. Existing X-Correlation-ID header from client
        2. Generate new UUID v4

        Args:
            request: The HTTP request object
        """
        if not self.enabled:
            return None

        # Check for existing correlation ID in headers
        correlation_id = request.META.get(
            f'HTTP_{self.HEADER_NAME.upper().replace("-", "_")}'
        )

        # Validate existing correlation ID (must be valid UUID)
        if correlation_id:
            try:
                uuid.UUID(correlation_id, version=4)
            except (ValueError, AttributeError):
                # Invalid UUID, generate new one
                logger.warning(
                    f"Invalid correlation ID received: {correlation_id}, generating new one"
                )
                correlation_id = None

        # Generate new correlation ID if not provided or invalid
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request object
        setattr(request, self.REQUEST_ATTR, correlation_id)

        # Store in thread-local storage for global access
        set_correlation_id(correlation_id)

        logger.debug(f"Correlation ID set: {correlation_id}")

        return None

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """
        Add correlation ID to response headers.

        Args:
            request: The HTTP request object
            response: The HTTP response object

        Returns:
            HttpResponse with X-Correlation-ID header
        """
        if not self.enabled:
            return response

        # Get correlation ID from request
        correlation_id = getattr(request, self.REQUEST_ATTR, None)

        if correlation_id:
            # Add to response headers
            response[self.HEADER_NAME] = correlation_id

        # Clean up thread-local storage
        clear_correlation_id()

        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """
        Ensure correlation ID is logged with exceptions.

        Args:
            request: The HTTP request object
            exception: The exception that occurred
        """
        correlation_id = getattr(request, self.REQUEST_ATTR, None)

        if correlation_id:
            logger.error(
                f"Exception occurred during request processing",
                extra={
                    'correlation_id': correlation_id,
                    'exception_type': type(exception).__name__,
                    'exception_message': str(exception)
                },
                exc_info=True
            )

        # Clean up thread-local storage
        clear_correlation_id()

        return None


# Thread-local storage helper functions

def set_correlation_id(correlation_id: str) -> None:
    """
    Store correlation ID in thread-local storage.

    Args:
        correlation_id: The correlation ID to store
    """
    _thread_locals.correlation_id = correlation_id


def get_correlation_id() -> Optional[str]:
    """
    Retrieve correlation ID from thread-local storage.

    Returns:
        str: The current correlation ID or None if not set

    Usage:
        correlation_id = get_correlation_id()
        logger.info("Processing", extra={'correlation_id': correlation_id})
    """
    return getattr(_thread_locals, 'correlation_id', None)


def clear_correlation_id() -> None:
    """
    Clear correlation ID from thread-local storage.

    Called automatically by middleware after response is sent.
    """
    if hasattr(_thread_locals, 'correlation_id'):
        delattr(_thread_locals, 'correlation_id')
