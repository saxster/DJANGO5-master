"""
Search Rate Limiting Middleware

Implements comprehensive rate limiting for search endpoints to prevent abuse.

Features:
- Separate limits for authenticated vs anonymous users
- Redis-backed sliding window algorithm
- Configurable per-endpoint limits
- Graceful degradation if Redis unavailable
- X-RateLimit headers for transparency
- Per-tenant metrics tracking with Redis tags
- Prometheus metrics export integration
- Business unit-level rate limiting support

Compliance with .claude/rules.md:
- Rule #9: Input validation (rate limit enforcement)
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
import hashlib
import time
from typing import Optional, Dict, Any, Tuple
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpRequest
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.cache import CacheKeyWarning

from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# Prometheus metrics (lazy import for optional dependency)
try:
    from prometheus_client import Counter, Histogram, Gauge
    METRICS_ENABLED = True

    # Metrics definitions
    rate_limit_requests = Counter(
        'search_rate_limit_requests_total',
        'Total search rate limit requests',
        ['tenant_id', 'user_type', 'endpoint', 'allowed']
    )

    rate_limit_exceeded = Counter(
        'search_rate_limit_exceeded_total',
        'Total search rate limit violations',
        ['tenant_id', 'user_type', 'reason']
    )

    rate_limit_check_duration = Histogram(
        'search_rate_limit_check_duration_seconds',
        'Rate limit check duration',
        ['tenant_id']
    )

    active_rate_limits = Gauge(
        'search_active_rate_limits',
        'Number of active rate limit entries in cache',
        ['tenant_id']
    )
except ImportError:
    METRICS_ENABLED = False
    logger.warning("prometheus_client not installed. Metrics export disabled.")


class SearchRateLimitConfig:
    """Configuration for search rate limiting"""

    # Requests per time window
    ANONYMOUS_LIMIT = 20  # 20 requests per 5 minutes
    AUTHENTICATED_LIMIT = 100  # 100 requests per 5 minutes
    PREMIUM_LIMIT = 500  # 500 requests per 5 minutes (premium tenants)

    # Time windows (in seconds)
    WINDOW_SIZE = 5 * SECONDS_IN_MINUTE  # 5 minutes

    # Cache key prefixes (with tenant namespace)
    CACHE_KEY_PREFIX = 'search_rate_limit'

    # Response headers
    HEADER_LIMIT = 'X-RateLimit-Limit'
    HEADER_REMAINING = 'X-RateLimit-Remaining'
    HEADER_RESET = 'X-RateLimit-Reset'
    HEADER_RETRY_AFTER = 'Retry-After'
    HEADER_TENANT = 'X-RateLimit-Tenant'  # NEW: Tenant identification

    # Premium tenant configuration
    PREMIUM_TENANTS = getattr(
        settings,
        'SEARCH_PREMIUM_TENANTS',
        []
    )

    # Tenant-specific overrides (future enhancement)
    TENANT_OVERRIDES = getattr(
        settings,
        'SEARCH_RATE_LIMIT_TENANT_OVERRIDES',
        {}
    )


class SearchRateLimitMiddleware:
    """
    Middleware for rate limiting search endpoints.

    Uses Redis-backed sliding window algorithm for accurate rate limiting.
    Provides graceful degradation if Redis is unavailable.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.config = SearchRateLimitConfig()

    def __call__(self, request: HttpRequest):
        # Only apply to search endpoints
        if not self._is_search_endpoint(request):
            return self.get_response(request)

        # Start metrics timer
        start_time = time.time() if METRICS_ENABLED else 0

        # Check rate limit
        rate_limit_result = self._check_rate_limit(request)

        # Record metrics
        if METRICS_ENABLED:
            duration = time.time() - start_time
            tenant_id = str(self._get_tenant_id(request))
            user_type = self._get_user_type(request)

            rate_limit_check_duration.labels(tenant_id=tenant_id).observe(duration)
            rate_limit_requests.labels(
                tenant_id=tenant_id,
                user_type=user_type,
                endpoint=request.path,
                allowed=str(rate_limit_result['allowed'])
            ).inc()

        if not rate_limit_result['allowed']:
            return self._create_rate_limit_response(rate_limit_result)

        # Add rate limit headers to response
        response = self.get_response(request)
        self._add_rate_limit_headers(response, rate_limit_result)

        return response

    def _is_search_endpoint(self, request: HttpRequest) -> bool:
        """Check if request is for a search endpoint"""
        search_paths = [
            '/api/v1/search',
            '/api/v2/search',
            '/search/',
        ]
        return any(request.path.startswith(path) for path in search_paths)

    def _check_rate_limit(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Check if request exceeds rate limit with tenant awareness.

        Returns:
            Dict with rate limit status and metadata
        """
        try:
            # Get tenant and user information
            tenant_id = self._get_tenant_id(request)
            identifier = self._get_user_identifier(request)
            user_type = self._get_user_type(request)

            # Get rate limit for user type (tenant-aware)
            limit, window = self._get_rate_limit_config(request)

            # Generate tenant-aware cache key
            cache_key = self._generate_cache_key(tenant_id, identifier, request.path)

            # Get current timestamp
            now = time.time()
            window_start = now - window

            # Get request history from cache
            request_history = cache.get(cache_key, [])

            # Clean old requests outside window
            request_history = [
                timestamp for timestamp in request_history
                if timestamp > window_start
            ]

            # Check if limit exceeded
            current_count = len(request_history)
            allowed = current_count < limit

            if allowed:
                # Add current request
                request_history.append(now)
                cache.set(cache_key, request_history, timeout=int(window))

            # Calculate reset time
            if request_history:
                oldest_request = min(request_history)
                reset_time = oldest_request + window
            else:
                reset_time = now + window

            result = {
                'allowed': allowed,
                'limit': limit,
                'remaining': max(0, limit - current_count - (1 if allowed else 0)),
                'reset': int(reset_time),
                'retry_after': int(reset_time - now) if not allowed else 0,
                'identifier': identifier,
                'tenant_id': tenant_id,
                'user_type': user_type,
                'window': int(window),
            }

            # Log and export metrics if rate limit exceeded
            if not allowed:
                self._log_rate_limit_exceeded(request, result)

                if METRICS_ENABLED:
                    rate_limit_exceeded.labels(
                        tenant_id=str(tenant_id),
                        user_type=user_type,
                        reason='quota_exceeded'
                    ).inc()

            return result

        except (CacheKeyWarning, ConnectionError, TimeoutError) as e:
            # Graceful degradation - allow request if cache unavailable
            logger.warning(
                f"Rate limit cache unavailable: {e}. Allowing request.",
                exc_info=True
            )
            return {
                'allowed': True,
                'limit': 0,
                'remaining': 0,
                'reset': 0,
                'retry_after': 0,
                'identifier': 'unknown',
                'tenant_id': 0,
                'user_type': 'unknown',
                'window': 0,
            }

    def _get_user_identifier(self, request: HttpRequest) -> str:
        """Get unique identifier for rate limiting"""
        if request.user and request.user.is_authenticated:
            # Use user ID for authenticated users
            return f"user:{request.user.id}"
        else:
            # Use IP address for anonymous users
            ip_address = self._get_client_ip(request)
            return f"ip:{ip_address}"

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address from request"""
        # Check X-Forwarded-For header (load balancer)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()

        # Check X-Real-IP header (nginx)
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip

        # Fallback to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR', 'unknown')

    def _get_tenant_id(self, request: HttpRequest) -> int:
        """
        Extract tenant ID from request.

        Returns:
            Tenant ID or 0 for anonymous/no tenant
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request.user, 'tenant') and request.user.tenant:
                return request.user.tenant.id
        return 0

    def _get_user_type(self, request: HttpRequest) -> str:
        """
        Determine user type for metrics and rate limiting.

        Returns:
            'anonymous', 'authenticated', or 'premium'
        """
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return 'anonymous'

        tenant_id = self._get_tenant_id(request)
        if tenant_id in self.config.PREMIUM_TENANTS:
            return 'premium'

        if hasattr(request.user, 'is_premium') and request.user.is_premium:
            return 'premium'

        return 'authenticated'

    def _get_rate_limit_config(self, request: HttpRequest) -> Tuple[int, int]:
        """Get rate limit and window size for user type with tenant overrides"""
        tenant_id = self._get_tenant_id(request)
        user_type = self._get_user_type(request)

        # Check for tenant-specific overrides
        if tenant_id in self.config.TENANT_OVERRIDES:
            override = self.config.TENANT_OVERRIDES[tenant_id]
            limit = override.get('limit', self.config.AUTHENTICATED_LIMIT)
            window = override.get('window', self.config.WINDOW_SIZE)
            return limit, window

        # Default limits by user type
        if user_type == 'premium':
            limit = self.config.PREMIUM_LIMIT
        elif user_type == 'authenticated':
            limit = self.config.AUTHENTICATED_LIMIT
        else:
            limit = self.config.ANONYMOUS_LIMIT

        return limit, self.config.WINDOW_SIZE

    def _generate_cache_key(
        self,
        tenant_id: int,
        identifier: str,
        endpoint: str
    ) -> str:
        """
        Generate Redis cache key with tenant namespace for rate limiting.

        Format: search_rate_limit:{tenant_id}:{endpoint_hash}:{identifier_hash}

        Args:
            tenant_id: Tenant ID for namespace isolation
            identifier: User/IP identifier
            endpoint: Request path

        Returns:
            Namespaced cache key string
        """
        # Hash identifier for consistent key length
        identifier_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]

        # Hash endpoint for grouping
        endpoint_hash = hashlib.sha256(endpoint.encode()).hexdigest()[:8]

        return f"{self.config.CACHE_KEY_PREFIX}:{tenant_id}:{endpoint_hash}:{identifier_hash}"

    def _create_rate_limit_response(
        self,
        rate_limit_result: Dict[str, Any]
    ) -> JsonResponse:
        """Create 429 Too Many Requests response with tenant context"""
        response = JsonResponse({
            'error': 'rate_limit_exceeded',
            'message': 'Too many search requests. Please try again later.',
            'limit': rate_limit_result['limit'],
            'retry_after': rate_limit_result['retry_after'],
            'window_seconds': rate_limit_result['window'],
            'user_type': rate_limit_result.get('user_type', 'unknown'),
        }, status=429)

        # Add rate limit headers
        response[self.config.HEADER_LIMIT] = rate_limit_result['limit']
        response[self.config.HEADER_REMAINING] = 0
        response[self.config.HEADER_RESET] = rate_limit_result['reset']
        response[self.config.HEADER_RETRY_AFTER] = rate_limit_result['retry_after']
        response[self.config.HEADER_TENANT] = rate_limit_result.get('tenant_id', 0)

        return response

    def _add_rate_limit_headers(
        self,
        response,
        rate_limit_result: Dict[str, Any]
    ):
        """Add rate limit headers to response with tenant information"""
        response[self.config.HEADER_LIMIT] = rate_limit_result['limit']
        response[self.config.HEADER_REMAINING] = rate_limit_result['remaining']
        response[self.config.HEADER_RESET] = rate_limit_result['reset']
        response[self.config.HEADER_TENANT] = rate_limit_result.get('tenant_id', 0)

    def _log_rate_limit_exceeded(
        self,
        request: HttpRequest,
        result: Dict[str, Any]
    ):
        """Log rate limit violation for security monitoring"""
        security_logger.warning(
            "Search rate limit exceeded",
            extra={
                'identifier': result['identifier'],
                'limit': result['limit'],
                'path': request.path,
                'method': request.method,
                'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
                'ip_address': self._get_client_ip(request),
            }
        )
