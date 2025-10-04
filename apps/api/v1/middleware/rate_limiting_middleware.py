"""
Rate Limiting Middleware for Mobile Sync Endpoints

Implements rate limiting to prevent abuse and ensure fair resource usage.

Following .claude/rules.md:
- Rule #12: Comprehensive rate limiting
"""

import logging
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class SyncRateLimitMiddleware:
    """
    Rate limiting middleware for sync endpoints.

    Limits:
    - 100 requests/hour per user
    - 50 requests/hour per device
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/v1/sync/'):
            rate_limit_result = self.check_rate_limit(request)
            if rate_limit_result:
                return rate_limit_result

        response = self.get_response(request)
        return response

    def check_rate_limit(self, request):
        """Check rate limits for user and device."""
        user_id = str(request.user.id) if request.user.is_authenticated else None
        device_id = request.headers.get('Device-Id') or request.META.get('HTTP_DEVICE_ID')

        if user_id:
            if self.is_rate_limited(f'sync_user_{user_id}', limit=100):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': 'Maximum 100 requests per hour per user',
                    'retry_after': 3600
                }, status=429)

        if device_id:
            if self.is_rate_limited(f'sync_device_{device_id}', limit=50):
                logger.warning(f"Rate limit exceeded for device {device_id}")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': 'Maximum 50 requests per hour per device',
                    'retry_after': 3600
                }, status=429)

        return None

    def is_rate_limited(self, key, limit=100):
        """Check if rate limit is exceeded."""
        cache_key = f'rate_limit_{key}'
        current_count = cache.get(cache_key, 0)

        if current_count >= limit:
            return True

        cache.set(cache_key, current_count + 1, 3600)
        return False