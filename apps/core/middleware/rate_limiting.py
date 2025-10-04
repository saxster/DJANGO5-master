"""
Rate Limiting Middleware and Decorators for Spatial Operations

Prevents API abuse, quota exhaustion, and DoS attacks on geocoding
and spatial query endpoints.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Security best practices for rate limiting

Features:
- Per-user, per-session, and per-IP rate limiting
- Configurable limits per operation type
- Sliding window algorithm
- Automatic cache cleanup
- Detailed logging of rate limit violations
"""

import logging
import time
from functools import wraps
from typing import Optional, Callable, Union
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpRequest
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


# ===========================================
# RATE LIMIT CONFIGURATION
# ===========================================

class RateLimitConfig:
    """Centralized rate limit configuration."""

    # Geocoding operations (Google Maps API)
    GEOCODING_RATE_LIMIT = getattr(settings, 'GEOCODING_RATE_LIMIT', {
        'anonymous': {'calls': 10, 'period': 3600},  # 10 calls per hour
        'authenticated': {'calls': 100, 'period': 3600},  # 100 calls per hour
        'staff': {'calls': 1000, 'period': 3600},  # 1000 calls per hour
    })

    # Reverse geocoding operations
    REVERSE_GEOCODING_RATE_LIMIT = getattr(settings, 'REVERSE_GEOCODING_RATE_LIMIT', {
        'anonymous': {'calls': 10, 'period': 3600},
        'authenticated': {'calls': 100, 'period': 3600},
        'staff': {'calls': 1000, 'period': 3600},
    })

    # Route optimization operations
    ROUTE_OPTIMIZATION_RATE_LIMIT = getattr(settings, 'ROUTE_OPTIMIZATION_RATE_LIMIT', {
        'anonymous': {'calls': 5, 'period': 3600},
        'authenticated': {'calls': 50, 'period': 3600},
        'staff': {'calls': 500, 'period': 3600},
    })

    # Spatial query operations
    SPATIAL_QUERY_RATE_LIMIT = getattr(settings, 'SPATIAL_QUERY_RATE_LIMIT', {
        'anonymous': {'calls': 100, 'period': 3600},
        'authenticated': {'calls': 1000, 'period': 3600},
        'staff': {'calls': 10000, 'period': 3600},
    })

    # GPS submission operations
    GPS_SUBMISSION_RATE_LIMIT = getattr(settings, 'GPS_SUBMISSION_RATE_LIMIT', {
        'anonymous': {'calls': 0, 'period': 3600},  # Not allowed for anonymous
        'authenticated': {'calls': 500, 'period': 3600},
        'staff': {'calls': 5000, 'period': 3600},
    })


# ===========================================
# RATE LIMITER CLASS
# ===========================================

class RateLimiter:
    """
    Sliding window rate limiter using Django cache.

    Uses a sliding window algorithm to track request counts
    over a rolling time period.
    """

    def __init__(self, identifier: str, max_calls: int, period: int):
        """
        Initialize rate limiter.

        Args:
            identifier: Unique identifier for this rate limit (user ID, IP, etc.)
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
        """
        self.identifier = identifier
        self.max_calls = max_calls
        self.period = period
        self.cache_key = f"rate_limit:{identifier}"

    def is_allowed(self) -> bool:
        """
        Check if request is allowed under rate limit.

        Returns:
            True if allowed, False if rate limit exceeded
        """
        current_time = time.time()

        # Get existing request timestamps from cache
        request_times = cache.get(self.cache_key, [])

        # Remove timestamps outside the sliding window
        cutoff_time = current_time - self.period
        request_times = [t for t in request_times if t > cutoff_time]

        # Check if limit exceeded
        if len(request_times) >= self.max_calls:
            # Calculate time until oldest request expires
            time_until_reset = int(request_times[0] + self.period - current_time)
            logger.warning(
                f"Rate limit exceeded for {self.identifier}. "
                f"Limit: {self.max_calls} calls per {self.period}s. "
                f"Reset in: {time_until_reset}s"
            )
            return False

        # Add current request timestamp
        request_times.append(current_time)

        # Store updated timestamps in cache
        cache.set(self.cache_key, request_times, self.period + 60)  # +60s buffer

        return True

    def get_usage_stats(self) -> dict:
        """
        Get current rate limit usage statistics.

        Returns:
            Dictionary with usage stats
        """
        current_time = time.time()
        request_times = cache.get(self.cache_key, [])

        # Remove expired timestamps
        cutoff_time = current_time - self.period
        active_requests = [t for t in request_times if t > cutoff_time]

        remaining = max(0, self.max_calls - len(active_requests))

        # Calculate reset time
        if active_requests:
            reset_time = int(active_requests[0] + self.period - current_time)
        else:
            reset_time = 0

        return {
            'limit': self.max_calls,
            'remaining': remaining,
            'used': len(active_requests),
            'reset_in_seconds': reset_time,
            'period_seconds': self.period,
        }


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def get_client_identifier(request: HttpRequest, use_ip: bool = False) -> str:
    """
    Get unique identifier for client (user, session, or IP).

    Args:
        request: Django HTTP request
        use_ip: Use IP address instead of user/session

    Returns:
        Unique identifier string
    """
    # Prefer user ID if authenticated
    if not use_ip and request.user.is_authenticated:
        return f"user:{request.user.id}"

    # Use session key if available
    if not use_ip and hasattr(request, 'session') and request.session.session_key:
        return f"session:{request.session.session_key}"

    # Fall back to IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')

    return f"ip:{ip}"


def get_user_tier(request: HttpRequest) -> str:
    """
    Determine user tier for rate limiting.

    Args:
        request: Django HTTP request

    Returns:
        Tier string: 'staff', 'authenticated', or 'anonymous'
    """
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return 'staff'
        return 'authenticated'
    return 'anonymous'


def create_rate_limit_response(
    identifier: str,
    stats: dict,
    operation: str
) -> JsonResponse:
    """
    Create standardized rate limit exceeded response.

    Args:
        identifier: Client identifier
        stats: Rate limit usage statistics
        operation: Operation type

    Returns:
        JsonResponse with 429 status
    """
    response = JsonResponse({
        'error': 'rate_limit_exceeded',
        'message': _(
            f'Rate limit exceeded for {operation}. '
            f'Please try again in {stats["reset_in_seconds"]} seconds.'
        ),
        'limit': stats['limit'],
        'remaining': stats['remaining'],
        'reset_in_seconds': stats['reset_in_seconds'],
        'period_seconds': stats['period_seconds'],
    }, status=429)

    # Add standard rate limit headers
    response['X-RateLimit-Limit'] = str(stats['limit'])
    response['X-RateLimit-Remaining'] = str(stats['remaining'])
    response['X-RateLimit-Reset'] = str(int(time.time() + stats['reset_in_seconds']))
    response['Retry-After'] = str(stats['reset_in_seconds'])

    return response


# ===========================================
# DECORATORS
# ===========================================

def rate_limit(
    operation: str,
    config: Optional[dict] = None,
    use_ip: bool = False
):
    """
    Decorator for rate limiting function calls.

    Args:
        operation: Operation type (geocoding, spatial_query, etc.)
        config: Rate limit configuration dict (optional)
        use_ip: Use IP-based rate limiting

    Example:
        @rate_limit('geocoding')
        def geocode_address(request, address):
            # Function implementation
            pass

        @rate_limit('spatial_query', config={'calls': 100, 'period': 60})
        def complex_spatial_query(request):
            # Function implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract request from args or kwargs
            request = None
            if args and isinstance(args[0], HttpRequest):
                request = args[0]
            elif 'request' in kwargs:
                request = kwargs['request']

            if not request:
                # No request object, skip rate limiting
                logger.warning(f"Rate limiting skipped for {func.__name__}: No request object")
                return func(*args, **kwargs)

            # Get client identifier
            identifier = get_client_identifier(request, use_ip=use_ip)
            identifier_with_op = f"{identifier}:{operation}"

            # Get rate limit configuration
            if config:
                limit_config = config
            else:
                # Get config based on operation type
                config_map = {
                    'geocoding': RateLimitConfig.GEOCODING_RATE_LIMIT,
                    'reverse_geocoding': RateLimitConfig.REVERSE_GEOCODING_RATE_LIMIT,
                    'route_optimization': RateLimitConfig.ROUTE_OPTIMIZATION_RATE_LIMIT,
                    'spatial_query': RateLimitConfig.SPATIAL_QUERY_RATE_LIMIT,
                    'gps_submission': RateLimitConfig.GPS_SUBMISSION_RATE_LIMIT,
                }

                operation_config = config_map.get(operation, {})
                user_tier = get_user_tier(request)
                limit_config = operation_config.get(user_tier, {'calls': 100, 'period': 3600})

            # Create rate limiter
            rate_limiter = RateLimiter(
                identifier=identifier_with_op,
                max_calls=limit_config['calls'],
                period=limit_config['period']
            )

            # Check rate limit
            if not rate_limiter.is_allowed():
                stats = rate_limiter.get_usage_stats()

                # Log violation
                logger.warning(
                    f"Rate limit exceeded: {identifier} for {operation}. "
                    f"Limit: {stats['limit']}/{stats['period_seconds']}s, "
                    f"Used: {stats['used']}, "
                    f"Reset in: {stats['reset_in_seconds']}s"
                )

                # Return 429 response
                return create_rate_limit_response(identifier, stats, operation)

            # Request allowed, proceed with function call
            return func(*args, **kwargs)

        return wrapper
    return decorator


def rate_limit_view(operation: str, use_ip: bool = False):
    """
    Decorator for rate limiting Django views.

    Specifically designed for view functions that return HttpResponse.

    Args:
        operation: Operation type
        use_ip: Use IP-based rate limiting

    Example:
        @rate_limit_view('geocoding')
        def geocode_view(request):
            address = request.GET.get('address')
            result = geocode(address)
            return JsonResponse(result)
    """
    return rate_limit(operation=operation, use_ip=use_ip)


def rate_limit_api(operation: str, use_ip: bool = False):
    """
    Decorator for rate limiting API endpoints (DRF views).

    Args:
        operation: Operation type
        use_ip: Use IP-based rate limiting

    Example:
        from rest_framework.decorators import api_view

        @api_view(['POST'])
        @rate_limit_api('gps_submission')
        def submit_gps_location(request):
            # API implementation
            pass
    """
    return rate_limit(operation=operation, use_ip=use_ip)


# ===========================================
# MIDDLEWARE
# ===========================================

class GlobalRateLimitMiddleware:
    """
    Global rate limiting middleware for all spatial API endpoints.

    Apply this middleware to protect all geocoding and spatial query endpoints
    from abuse without needing to decorate individual views.
    """

    # Patterns that trigger rate limiting
    RATE_LIMITED_PATHS = [
        '/api/maps/',
        '/api/geocode/',
        '/api/spatial/',
        '/api/location/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if path should be rate limited
        should_limit = any(
            request.path.startswith(path)
            for path in self.RATE_LIMITED_PATHS
        )

        if should_limit:
            # Determine operation type from path
            operation = self._get_operation_from_path(request.path)

            # Get client identifier
            identifier = get_client_identifier(request)
            identifier_with_op = f"{identifier}:{operation}"

            # Get rate limit config
            user_tier = get_user_tier(request)
            limit_config = RateLimitConfig.SPATIAL_QUERY_RATE_LIMIT.get(
                user_tier, {'calls': 100, 'period': 3600}
            )

            # Create rate limiter
            rate_limiter = RateLimiter(
                identifier=identifier_with_op,
                max_calls=limit_config['calls'],
                period=limit_config['period']
            )

            # Check rate limit
            if not rate_limiter.is_allowed():
                stats = rate_limiter.get_usage_stats()
                logger.warning(
                    f"Global rate limit exceeded: {identifier} for {request.path}"
                )
                return create_rate_limit_response(identifier, stats, operation)

        response = self.get_response(request)
        return response

    def _get_operation_from_path(self, path: str) -> str:
        """Determine operation type from request path."""
        if '/geocode/' in path:
            return 'geocoding'
        elif '/maps/' in path:
            return 'maps_api'
        elif '/spatial/' in path:
            return 'spatial_query'
        elif '/location/' in path:
            return 'location_api'
        return 'api_request'


# ===========================================
# UTILITY FUNCTIONS
# ===========================================

def check_rate_limit(
    request: HttpRequest,
    operation: str,
    raise_exception: bool = False
) -> bool:
    """
    Manually check rate limit without decorator.

    Args:
        request: Django HTTP request
        operation: Operation type
        raise_exception: Raise PermissionDenied if exceeded

    Returns:
        True if allowed, False if rate limit exceeded

    Raises:
        PermissionDenied: If raise_exception=True and limit exceeded

    Example:
        def my_view(request):
            if not check_rate_limit(request, 'geocoding'):
                return JsonResponse({'error': 'Rate limit exceeded'}, status=429)

            # Proceed with operation
            ...
    """
    identifier = get_client_identifier(request)
    identifier_with_op = f"{identifier}:{operation}"

    # Get config
    config_map = {
        'geocoding': RateLimitConfig.GEOCODING_RATE_LIMIT,
        'reverse_geocoding': RateLimitConfig.REVERSE_GEOCODING_RATE_LIMIT,
        'route_optimization': RateLimitConfig.ROUTE_OPTIMIZATION_RATE_LIMIT,
        'spatial_query': RateLimitConfig.SPATIAL_QUERY_RATE_LIMIT,
        'gps_submission': RateLimitConfig.GPS_SUBMISSION_RATE_LIMIT,
    }

    operation_config = config_map.get(operation, {})
    user_tier = get_user_tier(request)
    limit_config = operation_config.get(user_tier, {'calls': 100, 'period': 3600})

    # Create rate limiter
    rate_limiter = RateLimiter(
        identifier=identifier_with_op,
        max_calls=limit_config['calls'],
        period=limit_config['period']
    )

    # Check limit
    is_allowed = rate_limiter.is_allowed()

    if not is_allowed and raise_exception:
        raise PermissionDenied(_("Rate limit exceeded"))

    return is_allowed


def get_rate_limit_stats(request: HttpRequest, operation: str) -> dict:
    """
    Get current rate limit statistics for a request.

    Args:
        request: Django HTTP request
        operation: Operation type

    Returns:
        Dictionary with rate limit statistics

    Example:
        stats = get_rate_limit_stats(request, 'geocoding')
        print(f"Remaining calls: {stats['remaining']}")
    """
    identifier = get_client_identifier(request)
    identifier_with_op = f"{identifier}:{operation}"

    # Get config
    user_tier = get_user_tier(request)
    config_map = {
        'geocoding': RateLimitConfig.GEOCODING_RATE_LIMIT,
        'reverse_geocoding': RateLimitConfig.REVERSE_GEOCODING_RATE_LIMIT,
        'route_optimization': RateLimitConfig.ROUTE_OPTIMIZATION_RATE_LIMIT,
        'spatial_query': RateLimitConfig.SPATIAL_QUERY_RATE_LIMIT,
        'gps_submission': RateLimitConfig.GPS_SUBMISSION_RATE_LIMIT,
    }

    operation_config = config_map.get(operation, {})
    limit_config = operation_config.get(user_tier, {'calls': 100, 'period': 3600})

    # Create rate limiter
    rate_limiter = RateLimiter(
        identifier=identifier_with_op,
        max_calls=limit_config['calls'],
        period=limit_config['period']
    )

    return rate_limiter.get_usage_stats()


__all__ = [
    'RateLimiter',
    'RateLimitConfig',
    'rate_limit',
    'rate_limit_view',
    'rate_limit_api',
    'GlobalRateLimitMiddleware',
    'check_rate_limit',
    'get_rate_limit_stats',
]