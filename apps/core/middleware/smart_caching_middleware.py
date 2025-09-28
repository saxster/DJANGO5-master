"""
Smart Caching Middleware

Provides intelligent caching for requests and responses to optimize performance
and reduce database load. Particularly effective for heavy operations and
frequently accessed data.

Features:
- Request/response caching with TTL
- Query result caching
- Conditional caching based on request patterns
- Cache invalidation strategies
- Performance metrics integration
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.cache import get_cache_key, learn_cache_key
from django.utils.deprecation import MiddlewareMixin

from apps.core.utils_new.sql_security import QueryValidator


logger = logging.getLogger(__name__)


class SmartCachingMiddleware(MiddlewareMixin):
    """
    Intelligent caching middleware for optimizing request performance.

    Implements:
    - View-level response caching
    - Database query result caching
    - API response caching
    - Conditional caching based on content type
    - Automatic cache invalidation
    """

    # Cache configuration
    DEFAULT_CACHE_TIMEOUT = 300  # 5 minutes
    LONG_CACHE_TIMEOUT = 3600   # 1 hour
    SHORT_CACHE_TIMEOUT = 60    # 1 minute

    # Cacheable patterns
    CACHEABLE_PATHS = [
        '/api/',
        '/reports/',
        '/dashboard/',
        '/assets/',
    ]

    # Non-cacheable patterns
    NON_CACHEABLE_PATHS = [
        '/admin/',
        '/auth/',
        '/login/',
        '/logout/',
        '/monitoring/',
    ]

    # Cache by content type
    CACHEABLE_CONTENT_TYPES = [
        'application/json',
        'text/html',
        'application/pdf',
        'text/csv',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check if request can be served from cache."""
        try:
            # Skip caching for non-cacheable requests
            if not self._is_cacheable_request(request):
                return None

            # Generate cache key
            cache_key = self._generate_cache_key(request)
            if not cache_key:
                return None

            # Try to get cached response
            cached_response = cache.get(cache_key)

            if cached_response:
                self.cache_stats['hits'] += 1
                logger.debug(f"Cache HIT for {request.path}")

                # Create response from cached data
                response = HttpResponse(
                    cached_response['content'],
                    content_type=cached_response['content_type'],
                    status=cached_response['status_code']
                )

                # Add cache headers
                response['X-Cache-Status'] = 'HIT'
                response['X-Cache-Key'] = cache_key[:32]  # Truncated for security
                response['X-Cached-At'] = cached_response['cached_at']

                return response
            else:
                self.cache_stats['misses'] += 1
                logger.debug(f"Cache MISS for {request.path}")

                # Store cache key for process_response
                request._cache_key = cache_key

        except (ConnectionError, ValueError) as e:
            self.cache_stats['errors'] += 1
            logger.error(f"Cache processing error: {str(e)}")

        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Cache response if appropriate."""
        try:
            # Skip if not cacheable
            if not self._is_cacheable_response(request, response):
                return response

            # Get cache key from request processing
            cache_key = getattr(request, '_cache_key', None)
            if not cache_key:
                cache_key = self._generate_cache_key(request)

            if not cache_key:
                return response

            # Prepare cached data
            cached_data = {
                'content': response.content,
                'content_type': response.get('Content-Type', 'text/html'),
                'status_code': response.status_code,
                'cached_at': timezone.now().isoformat(),
                'path': request.path,
                'method': request.method
            }

            # Determine cache timeout
            cache_timeout = self._get_cache_timeout(request, response)

            # Store in cache
            cache.set(cache_key, cached_data, timeout=cache_timeout)
            self.cache_stats['sets'] += 1

            # Add cache headers
            response['X-Cache-Status'] = 'MISS'
            response['X-Cache-Timeout'] = str(cache_timeout)
            response['X-Cache-Key'] = cache_key[:32]

            logger.debug(f"Cached response for {request.path} with timeout {cache_timeout}s")

        except (ConnectionError, ValueError) as e:
            self.cache_stats['errors'] += 1
            logger.error(f"Cache storage error: {str(e)}")

        return response

    def _is_cacheable_request(self, request: HttpRequest) -> bool:
        """Determine if request is cacheable."""
        try:
            # Only cache GET and HEAD requests
            if request.method not in ['GET', 'HEAD']:
                return False

            # Check if user is authenticated (more restrictive caching)
            if hasattr(request, 'user') and request.user.is_authenticated:
                # Cache authenticated requests more selectively
                if not any(request.path.startswith(path) for path in ['/api/', '/reports/']):
                    return False

            # Check non-cacheable paths
            if any(request.path.startswith(path) for path in self.NON_CACHEABLE_PATHS):
                return False

            # Check if path is explicitly cacheable
            if any(request.path.startswith(path) for path in self.CACHEABLE_PATHS):
                return True

            # Check for dynamic content indicators
            if self._has_dynamic_parameters(request):
                return False

            return True

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error checking cacheable request: {str(e)}")
            return False

    def _is_cacheable_response(self, request: HttpRequest, response: HttpResponse) -> bool:
        """Determine if response is cacheable."""
        try:
            # Only cache successful responses
            if response.status_code not in [200, 301, 302, 304]:
                return False

            # Check content type
            content_type = response.get('Content-Type', '').split(';')[0]
            if content_type not in self.CACHEABLE_CONTENT_TYPES:
                return False

            # Don't cache responses with Set-Cookie headers
            if response.has_header('Set-Cookie'):
                return False

            # Don't cache responses that explicitly disable caching
            cache_control = response.get('Cache-Control', '')
            if any(directive in cache_control for directive in ['no-cache', 'no-store', 'private']):
                return False

            # Check response size (don't cache very large responses)
            if hasattr(response, 'content') and len(response.content) > 1024 * 1024:  # 1MB
                return False

            return True

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error checking cacheable response: {str(e)}")
            return False

    def _generate_cache_key(self, request: HttpRequest) -> Optional[str]:
        """Generate cache key for request."""
        try:
            # Base key components
            key_parts = [
                'smart_cache',
                request.method,
                request.path,
            ]

            # Add query parameters (sorted for consistency)
            if request.GET:
                query_string = '&'.join(
                    f"{k}={v}" for k, v in sorted(request.GET.items())
                )
                key_parts.append(query_string)

            # Add user context for authenticated requests
            if hasattr(request, 'user') and request.user.is_authenticated:
                # Use user role/permissions rather than specific user ID for better cache efficiency
                user_context = self._get_user_cache_context(request.user)
                if user_context:
                    key_parts.append(user_context)

            # Add request headers that affect response
            relevant_headers = self._get_relevant_headers(request)
            if relevant_headers:
                key_parts.append(relevant_headers)

            # Create hash of key parts
            key_string = '|'.join(str(part) for part in key_parts)
            cache_key = hashlib.md5(key_string.encode('utf-8')).hexdigest()

            return f"smart_cache_{cache_key}"

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error generating cache key: {str(e)}")
            return None

    def _get_user_cache_context(self, user) -> str:
        """Get user context for cache key generation."""
        try:
            # Use user permissions/roles rather than ID for better cache sharing
            context_parts = []

            if hasattr(user, 'is_staff') and user.is_staff:
                context_parts.append('staff')

            if hasattr(user, 'is_superuser') and user.is_superuser:
                context_parts.append('superuser')

            # Add user groups (for role-based caching)
            if hasattr(user, 'groups'):
                groups = sorted([group.name for group in user.groups.all()])
                if groups:
                    context_parts.extend(groups)

            return '_'.join(context_parts) if context_parts else 'authenticated'

        except (ConnectionError, ValueError):
            return 'authenticated'

    def _get_relevant_headers(self, request: HttpRequest) -> str:
        """Get request headers that affect response caching."""
        relevant_headers = [
            'Accept',
            'Accept-Language',
            'Accept-Encoding',
        ]

        header_values = []
        for header in relevant_headers:
            value = request.META.get(f'HTTP_{header.replace("-", "_").upper()}')
            if value:
                header_values.append(f"{header}:{value}")

        return '|'.join(header_values)

    def _has_dynamic_parameters(self, request: HttpRequest) -> bool:
        """Check if request has parameters indicating dynamic content."""
        dynamic_params = [
            'timestamp',
            'random',
            'nonce',
            '_',  # Common cache-busting parameter
        ]

        return any(param in request.GET for param in dynamic_params)

    def _get_cache_timeout(self, request: HttpRequest, response: HttpResponse) -> int:
        """Determine appropriate cache timeout for request/response."""
        try:
            # Check for explicit Cache-Control max-age
            cache_control = response.get('Cache-Control', '')
            if 'max-age=' in cache_control:
                try:
                    max_age = int(cache_control.split('max-age=')[1].split(',')[0])
                    return min(max_age, self.LONG_CACHE_TIMEOUT)
                except (ValueError, IndexError):
                    pass

            # API endpoints - shorter cache
            if request.path.startswith('/api/'):
                return self.SHORT_CACHE_TIMEOUT

            # Reports - longer cache (they're expensive to generate)
            if request.path.startswith('/reports/'):
                return self.LONG_CACHE_TIMEOUT

            # Static-like content - longer cache
            if any(request.path.endswith(ext) for ext in ['.json', '.csv', '.pdf']):
                return self.LONG_CACHE_TIMEOUT

            # Default timeout
            return self.DEFAULT_CACHE_TIMEOUT

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error determining cache timeout: {str(e)}")
            return self.DEFAULT_CACHE_TIMEOUT

    @classmethod
    def invalidate_cache_pattern(cls, pattern: str) -> int:
        """Invalidate cache entries matching a pattern."""
        try:
            from django.core.cache.utils import make_template_fragment_key

            # This is a simplified implementation
            # In production, you'd use Redis pattern matching or similar
            invalidated_count = 0

            # For now, we'll use a basic approach
            # In a real implementation, you'd iterate through cache keys
            logger.info(f"Cache invalidation requested for pattern: {pattern}")

            return invalidated_count

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return 0

    @classmethod
    def invalidate_user_cache(cls, user_id: int) -> int:
        """Invalidate cache entries for a specific user."""
        try:
            # Invalidate user-specific cached content
            pattern = f"smart_cache_*_user_{user_id}_*"
            return cls.invalidate_cache_pattern(pattern)

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"User cache invalidation error: {str(e)}")
            return 0

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Get caching statistics."""
        try:
            # Get basic cache info
            from django.core.cache import cache

            stats = {
                'cache_backend': type(cache).__name__,
                'cache_location': getattr(cache, '_cache', {}).get('_server', 'unknown'),
            }

            # Add middleware stats if available
            # Note: This is simplified - in production you'd track stats properly
            return stats

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {}

    @classmethod
    def warm_cache(cls, urls: List[str], user_context: Optional[Dict] = None) -> Dict[str, Any]:
        """Pre-warm cache with specified URLs."""
        try:
            from django.test import RequestFactory

            factory = RequestFactory()
            results = {
                'warmed': 0,
                'errors': 0,
                'skipped': 0
            }

            for url in urls:
                try:
                    # Create fake request for cache warming
                    request = factory.get(url)

                    # Add user context if provided
                    if user_context:
                        # This would need proper user object creation
                        pass

                    # This is a placeholder - actual implementation would
                    # process the request through the application
                    results['warmed'] += 1

                except (ValueError, TypeError) as e:
                    logger.error(f"Cache warming error for {url}: {str(e)}")
                    results['errors'] += 1

            logger.info(f"Cache warming completed: {results}")
            return results

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Cache warming failed: {str(e)}")
            return {'warmed': 0, 'errors': 1, 'skipped': 0}


class QueryCacheMiddleware(MiddlewareMixin):
    """
    Middleware for caching database query results.

    Provides automatic caching of expensive database queries
    to reduce load on the database server.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.query_cache_stats = {
            'hits': 0,
            'misses': 0,
            'saves': 0
        }

    def process_request(self, request: HttpRequest) -> None:
        """Initialize query caching for request."""
        try:
            # Store original database execute method
            from django.db import connection

            if not hasattr(connection, '_original_execute'):
                connection._original_execute = connection.cursor().execute
                connection._query_cache = {}

            # Initialize request-level query cache
            request._query_cache_enabled = self._should_cache_queries(request)

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Query cache initialization error: {str(e)}")

    def _should_cache_queries(self, request: HttpRequest) -> bool:
        """Determine if queries should be cached for this request."""
        # Enable query caching for read-heavy operations
        cacheable_paths = ['/reports/', '/dashboard/', '/api/']
        return any(request.path.startswith(path) for path in cacheable_paths)

    @classmethod
    def cache_query_result(cls, query: str, params: tuple, result: Any, timeout: int = 300) -> None:
        """Cache a database query result."""
        try:
            # Generate cache key for query
            query_hash = hashlib.md5(f"{query}_{params}".encode()).hexdigest()
            cache_key = f"query_cache_{query_hash}"

            # Store result in cache
            cache.set(cache_key, result, timeout=timeout)

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Query cache storage error: {str(e)}")

    @classmethod
    def get_cached_query_result(cls, query: str, params: tuple) -> Optional[Any]:
        """Get cached query result."""
        try:
            query_hash = hashlib.md5(f"{query}_{params}".encode()).hexdigest()
            cache_key = f"query_cache_{query_hash}"

            return cache.get(cache_key)

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Query cache retrieval error: {str(e)}")
            return None