"""
API Middleware for Monitoring and Optimization

Provides request/response processing for API endpoints.

@ontology(
    domain="api",
    purpose="Combined API middleware stack: monitoring, rate limiting, caching, and security headers",
    middleware_type="both",
    execution_order="after authentication, before views",
    middleware_stack=[
        "APISecurityMiddleware (security headers)",
        "APIRateLimitMiddleware (per-tier rate limits)",
        "APICacheMiddleware (GET request caching)",
        "APIMonitoringMiddleware (metrics and analytics)"
    ],
    rate_limit_tiers={
        "anonymous": "60 req/hour",
        "authenticated": "600 req/hour",
        "premium": "6000 req/hour"
    },
    cache_config={
        "timeout": "300s (5min)",
        "cacheable_paths": ["/api/v1/people/", "/api/v1/groups/", "/api/v1/assets/", "/api/v1/config/"],
        "bypass": "?nocache or Cache-Control: no-cache"
    },
    security_headers=[
        "X-Content-Type-Options: nosniff",
        "X-Frame-Options: DENY",
        "X-XSS-Protection: 1; mode=block",
        "Strict-Transport-Security",
        "removes Server and X-Powered-By"
    ],
    applies_to_paths=["/api/"],
    affects_all_requests=False,
    performance_impact="~2-5ms per request (depending on cache hit)",
    criticality="high",
    metrics_collected=[
        "request count per endpoint",
        "response time distribution",
        "error rates by status code",
        "cache hit/miss ratios"
    ],
    response_headers=["X-Response-Time", "X-API-Version", "X-RateLimit-*", "X-Cache"],
    tags=["middleware", "api", "monitoring", "rate-limiting", "caching", "security"]
)
"""

import time
import json
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.conf import settings

from apps.api.monitoring.analytics import api_analytics
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    SecurityException,
    APIException,
    SystemException,
    DatabaseException,
    CacheException
)

logger = logging.getLogger('api.middleware')


class APIMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor API requests and responses.
    
    Features:
        - Request/response timing
        - Error tracking
        - Usage analytics
        - Performance monitoring
    """
    
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)
        self.excluded_paths = [
            '/api/health/',
            '/api/metrics/',
            '/static/',
            '/media/'
        ]
    
    def process_request(self, request):
        """
        Process incoming API request.
        """
        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return super().process_request(request)

        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.excluded_paths):
            return super().process_request(request)

        # Start timing
        request._api_start_time = time.time()

        # Log request
        logger.debug(
            f"API Request: {request.method} {request.path} "
            f"(User: {request.user.id if request.user.is_authenticated else 'Anonymous'})"
        )

        return super().process_request(request)
    
    def process_response(self, request, response):
        """
        Process API response and record metrics.
        """
        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return super().process_response(request, response)

        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.excluded_paths):
            return super().process_response(request, response)

        response = super().process_response(request, response)

        # Calculate execution time
        if hasattr(request, '_api_start_time'):
            execution_time = time.time() - request._api_start_time

            # Record analytics
            try:
                api_analytics.record_request(request, response, execution_time)
            except (ConnectionError, OSError) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_analytics_connection', 'path': request.path},
                    level='warning'
                )
                logger.warning(f"Analytics service connection failed", extra={'correlation_id': correlation_id})
            except DatabaseException as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_analytics_database', 'path': request.path},
                    level='error'
                )
                logger.error(f"Analytics database error", extra={'correlation_id': correlation_id})
            except (ValueError, TypeError) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_analytics_data', 'path': request.path},
                    level='warning'
                )
                logger.warning(f"Analytics data processing error", extra={'correlation_id': correlation_id})
            except SystemException as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_analytics_system', 'path': request.path},
                    level='critical'
                )
                logger.critical(f"Analytics system error", extra={'correlation_id': correlation_id})

            # Add performance headers
            response['X-Response-Time'] = f"{execution_time:.3f}s"
            response['X-API-Version'] = self._get_api_version(request.path)

            # Log slow requests
            if execution_time > 1.0:
                logger.warning(
                    f"Slow API request: {request.method} {request.path} "
                    f"took {execution_time:.3f}s"
                )
        else:
            response.setdefault('X-API-Version', self._get_api_version(request.path))
            response.setdefault('X-Response-Time', 'N/A')

        return response
    
    def process_exception(self, request, exception):
        """
        Handle exceptions in API requests.
        """
        # Log exception
        logger.error(
            f"API Exception: {request.method} {request.path} - {str(exception)}",
            exc_info=True
        )
        
        # Record error in analytics
        if hasattr(request, '_api_start_time'):
            execution_time = time.time() - request._api_start_time
            
            # Create error response
            error_response = JsonResponse({
                'error': 'Internal Server Error',
                'message': str(exception) if settings.DEBUG else 'An error occurred',
                'status_code': 500,
                'timestamp': timezone.now().isoformat()
            }, status=500)
            
            # Record in analytics
            try:
                api_analytics.record_request(request, error_response, execution_time)
            except (ConnectionError, OSError) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_error_analytics', 'path': request.path},
                    level='warning'
                )
                logger.warning(f"Failed to record error analytics - connection issue", extra={'correlation_id': correlation_id})
            except DatabaseException as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_error_analytics_db', 'path': request.path},
                    level='error'
                )
                logger.error(f"Failed to record error analytics - database issue", extra={'correlation_id': correlation_id})
            except (ValueError, TypeError) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_error_analytics_data', 'path': request.path},
                    level='warning'
                )
                logger.warning(f"Failed to record error analytics - data issue", extra={'correlation_id': correlation_id})
        
        return super().process_exception(request, exception)
    
    def _get_api_version(self, path):
        """
        Extract API version from path.
        """
        import re
        match = re.search(r'/api/(v\d+)/', path)
        return match.group(1) if match else 'v1'


class APIRateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware for API endpoints.
    """
    
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)
        
        # Rate limit configuration
        self.rate_limits = {
            'anonymous': (60, 3600),      # 60 requests per hour
            'authenticated': (600, 3600),  # 600 requests per hour
            'premium': (6000, 3600),       # 6000 requests per hour
        }
    
    def process_request(self, request):
        """
        Check rate limits for API requests.
        """
        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return super().process_request(request)
        
        # Determine user tier
        user_tier = self._get_user_tier(request)
        
        # Get rate limit for tier
        limit, window = self.rate_limits.get(user_tier, (60, 3600))
        
        # Generate cache key
        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}"
        else:
            identifier = f"ip:{self._get_client_ip(request)}"
        
        cache_key = f"rate_limit:{identifier}"
        
        # Check current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            # Rate limit exceeded
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': f'You have exceeded the rate limit of {limit} requests per {window} seconds',
                'retry_after': window,
                'status_code': 429
            }, status=429)
        
        # Increment counter
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, window)
        
        # Add rate limit headers to request for response processing
        request._rate_limit_limit = limit
        request._rate_limit_remaining = limit - current_count - 1
        request._rate_limit_reset = int(time.time()) + window
        
        return super().process_request(request)
    
    def process_response(self, request, response):
        """
        Add rate limit headers to response.
        """
        response = super().process_response(request, response)

        if hasattr(request, '_rate_limit_limit'):
            response['X-RateLimit-Limit'] = request._rate_limit_limit
            response['X-RateLimit-Remaining'] = max(0, request._rate_limit_remaining)
            response['X-RateLimit-Reset'] = request._rate_limit_reset
        return response
    
    def _get_user_tier(self, request):
        """
        Determine user's rate limit tier.
        """
        if not request.user.is_authenticated:
            return 'anonymous'
        
        # Check for premium status
        if hasattr(request.user, 'is_premium') and request.user.is_premium:
            return 'premium'
        
        return 'authenticated'
    
    def _get_client_ip(self, request):
        """
        Get client IP address.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class APICacheMiddleware(MiddlewareMixin):
    """
    Caching middleware for GET requests.
    """
    
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)
        
        self.cache_timeout = 300  # 5 minutes
        self.cacheable_paths = [
            '/api/v1/people/',
            '/api/v1/groups/',
            '/api/v1/assets/',
            '/api/v1/config/'
        ]
    
    def process_request(self, request):
        """
        Check cache for GET requests.
        """
        # Only cache GET requests
        if request.method != 'GET':
            return super().process_request(request)

        # Check if path is cacheable
        if not any(request.path.startswith(path) for path in self.cacheable_paths):
            return super().process_request(request)

        # Skip if no-cache header is present
        if request.GET.get('nocache') or request.META.get('HTTP_CACHE_CONTROL') == 'no-cache':
            return super().process_request(request)
        
        # Generate cache key
        cache_key = self._generate_cache_key(request)
        
        # Try to get from cache
        cached_response = cache.get(cache_key)
        if cached_response:
            # Return cached response
            response = JsonResponse(cached_response)
            response['X-Cache'] = 'HIT'
            return response
        
        # Store cache key for response processing
        request._cache_key = cache_key
        
        return super().process_request(request)
    
    def process_response(self, request, response):
        """
        Cache successful GET responses.
        """
        response = super().process_response(request, response)

        # Check if we should cache this response
        if hasattr(request, '_cache_key') and response.status_code == 200:
            try:
                # Parse response content
                if hasattr(response, 'data'):
                    cache_data = response.data
                else:
                    cache_data = json.loads(response.content)
                
                # Cache the response
                cache.set(request._cache_key, cache_data, self.cache_timeout)

                # Add cache headers
                response['X-Cache'] = 'MISS'
                response['Cache-Control'] = f'max-age={self.cache_timeout}'

            except CacheException as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_cache_set', 'path': request.path},
                    level='warning'
                )
                logger.warning(f"Cache operation failed", extra={'correlation_id': correlation_id})
            except (json.JSONDecodeError, ValueError) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_cache_parse', 'path': request.path},
                    level='warning'
                )
                logger.warning(f"Failed to parse response for caching", extra={'correlation_id': correlation_id})
            except (ConnectionError, OSError) as e:
                correlation_id = ErrorHandler.handle_exception(
                    e,
                    context={'operation': 'api_cache_connection', 'path': request.path},
                    level='warning'
                )
                logger.warning(f"Cache connection failed", extra={'correlation_id': correlation_id})

        return response
    
    def _generate_cache_key(self, request):
        """
        Generate cache key for request.
        """
        import hashlib
        
        # Include path, query params, and user context
        key_parts = [
            request.path,
            request.META.get('QUERY_STRING', ''),
            str(request.user.id) if request.user.is_authenticated else 'anonymous'
        ]
        
        key_string = ':'.join(key_parts)
        return f"api_cache:{hashlib.md5(key_string.encode()).hexdigest()}"


class APISecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for API endpoints.
    """
    
    def process_response(self, request, response):
        """
        Add security headers to API responses.

        SECURITY NOTE: CORS headers are managed by django-cors-headers middleware.
        DO NOT set Access-Control-Allow-Origin here as it conflicts with
        CORS_ALLOW_CREDENTIALS = True and can bypass domain restrictions.
        """
        response = super().process_response(request, response)

        if request.path.startswith('/api/'):
            # Security headers
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

            # CORS headers: Managed by django-cors-headers middleware (corsheaders.middleware.CorsMiddleware)
            # Configuration: intelliwiz_config/settings/security/cors.py
            # DO NOT set wildcard CORS headers here - security vulnerability!

            # Remove sensitive headers
            response.pop('Server', None)
            response.pop('X-Powered-By', None)

        return response


# Combined middleware for optimal ordering
class APIMiddleware(
    APISecurityMiddleware,
    APIRateLimitMiddleware,
    APICacheMiddleware,
    APIMonitoringMiddleware
):
    """
    Combined API middleware for all API-related processing.
    
    Order of execution:
    1. Security checks
    2. Rate limiting
    3. Cache checking
    4. Monitoring
    """
    pass


# Export middleware classes
__all__ = [
    'APIMonitoringMiddleware',
    'APIRateLimitMiddleware',
    'APICacheMiddleware',
    'APISecurityMiddleware',
    'APIMiddleware',
]
