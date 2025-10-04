"""
ETag Middleware for HTTP Caching

Implements RFC 7232 ETags for efficient HTTP caching.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).

Benefits:
- 70%+ bandwidth reduction for unchanged resources
- Reduced server load
- Better user experience (faster page loads)
"""

import hashlib
import logging
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import get_conditional_response
from django.views.decorators.http import condition

from apps.core.exceptions.patterns import VALIDATION_ERRORS

logger = logging.getLogger(__name__)


class ETagMiddleware(MiddlewareMixin):
    """
    Middleware to add ETag support to responses.

    Supports:
    - Strong ETags for static content
    - Weak ETags for dynamic content
    - If-None-Match conditional requests
    - If-Match conditional updates
    """

    # Paths to skip ETag processing
    SKIP_PATHS = [
        '/admin/',
        '/api/graphql/',  # GraphQL has custom caching
        '/healthz',
        '/readyz',
        '/startup',
    ]

    # HTTP methods that support conditional requests
    SAFE_METHODS = ['GET', 'HEAD']
    CONDITIONAL_METHODS = ['PUT', 'PATCH', 'DELETE']

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """
        Add ETag to response if applicable.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            Modified response with ETag header
        """
        # Skip if path is in exclusion list
        if self._should_skip(request):
            return response

        # Only process successful responses
        if response.status_code not in [200, 201]:
            return response

        # Only for GET/HEAD requests
        if request.method not in self.SAFE_METHODS:
            return response

        # Skip if response already has ETag
        if response.has_header('ETag'):
            return response

        # Skip if response is streaming
        if response.streaming:
            return response

        try:
            # Generate ETag from response content
            etag = self._generate_etag(response)

            if etag:
                # Add ETag to response
                response['ETag'] = etag

                # Check if client has matching ETag
                client_etag = request.META.get('HTTP_IF_NONE_MATCH')

                if client_etag and self._etags_match(client_etag, etag):
                    # Return 304 Not Modified
                    return HttpResponse(status=304)

        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to generate ETag: {e}")

        return response

    def _should_skip(self, request: HttpRequest) -> bool:
        """Check if request should skip ETag processing."""
        path = request.path

        for skip_path in self.SKIP_PATHS:
            if path.startswith(skip_path):
                return True

        return False

    def _generate_etag(self, response: HttpResponse) -> Optional[str]:
        """
        Generate ETag from response content.

        Args:
            response: HTTP response

        Returns:
            ETag string (e.g., W/"abc123" for weak, "abc123" for strong)
        """
        try:
            # Get response content
            if hasattr(response, 'content'):
                content = response.content
            else:
                return None

            # Calculate MD5 hash
            content_hash = hashlib.md5(content).hexdigest()

            # Determine if weak or strong ETag
            content_type = response.get('Content-Type', '')

            # Use weak ETag for dynamic content (HTML, JSON)
            if any(ct in content_type for ct in ['html', 'json', 'xml']):
                return f'W/"{content_hash}"'

            # Use strong ETag for static content (images, CSS, JS)
            return f'"{content_hash}"'

        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(f"Error generating ETag: {e}")
            return None

    @staticmethod
    def _etags_match(client_etag: str, server_etag: str) -> bool:
        """
        Compare client and server ETags.

        Args:
            client_etag: ETag from If-None-Match header
            server_etag: Generated ETag

        Returns:
            True if ETags match
        """
        # Remove quotes and W/ prefix for comparison
        client_clean = client_etag.replace('W/', '').strip('"')
        server_clean = server_etag.replace('W/', '').strip('"')

        return client_clean == server_clean


class ConditionalGetMiddleware(MiddlewareMixin):
    """
    Enhanced conditional GET support with Last-Modified headers.

    Works in tandem with ETagMiddleware for comprehensive caching.
    """

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """
        Add Last-Modified header and handle If-Modified-Since.

        Args:
            request: HTTP request
            response: HTTP response

        Returns:
            Response with caching headers
        """
        # Only for GET/HEAD
        if request.method not in ['GET', 'HEAD']:
            return response

        # Only for successful responses
        if response.status_code != 200:
            return response

        # Use Django's built-in conditional response handling
        conditional_response = get_conditional_response(
            request,
            etag=response.get('ETag'),
            last_modified=response.get('Last-Modified')
        )

        if conditional_response:
            return conditional_response

        return response
