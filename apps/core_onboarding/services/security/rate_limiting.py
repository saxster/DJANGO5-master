"""
Rate Limiting Service with Budget Controls
Enhanced with circuit breaker pattern and graceful degradation
"""
import logging
import uuid
from typing import Dict, Any, Tuple
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from .circuit_breaker import CircuitBreaker
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    pass


class RateLimiter:
    """
    Rate limiting service with circuit breaker and fallback support
    Supports per-user, per-resource limits with hourly/daily windows
    """

    def __init__(self):
        self.cache = cache
        self.circuit_breaker = CircuitBreaker(
            threshold=getattr(settings, 'RATE_LIMITER_CIRCUIT_BREAKER_THRESHOLD', 5),
            reset_minutes=5
        )
        self.critical_resources = getattr(
            settings,
            'RATE_LIMITER_CRITICAL_RESOURCES',
            ['llm_calls', 'translations', 'knowledge_ingestion']
        )

    def check_rate_limit(
        self,
        user_identifier: str,
        resource_type: str,
        limit_type: str = 'requests'
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if user is within rate limits with graceful degradation
        """
        # Check circuit breaker
        if self.circuit_breaker.is_open():
            return self.circuit_breaker.handle_open_circuit(
                resource_type, self.critical_resources
            )

        limits = self._get_limits(resource_type, limit_type)
        limit_info = {
            'allowed': True,
            'current_usage': 0,
            'limit': limits.get('daily', 1000),
            'window': 'daily',
            'reset_time': None,
            'retry_after': None
        }

        try:
            # Check daily limit
            daily_key = self._build_key(resource_type, limit_type, user_identifier, 'daily')
            current_daily = self.cache.get(daily_key, 0)
            daily_limit = limits.get('daily', 1000)

            if current_daily >= daily_limit:
                reset_time = self._get_next_reset_time('daily')
                retry_after = self._calculate_retry_after(reset_time)
                limit_info.update({
                    'allowed': False,
                    'current_usage': current_daily,
                    'limit': daily_limit,
                    'window': 'daily',
                    'reset_time': reset_time,
                    'retry_after': retry_after
                })
                logger.warning(
                    f"Rate limit exceeded for user {user_identifier}",
                    extra={'resource_type': resource_type, 'window': 'daily'}
                )
                return False, limit_info

            # Check hourly limit if configured
            if 'hourly' in limits:
                hourly_key = self._build_key(resource_type, limit_type, user_identifier, 'hourly')
                current_hourly = self.cache.get(hourly_key, 0)
                hourly_limit = limits['hourly']

                if current_hourly >= hourly_limit:
                    reset_time = self._get_next_reset_time('hourly')
                    retry_after = self._calculate_retry_after(reset_time)
                    limit_info.update({
                        'allowed': False,
                        'current_usage': current_hourly,
                        'limit': hourly_limit,
                        'window': 'hourly',
                        'reset_time': reset_time,
                        'retry_after': retry_after
                    })
                    logger.warning(
                        f"Hourly rate limit exceeded for user {user_identifier}",
                        extra={'resource_type': resource_type, 'window': 'hourly'}
                    )
                    return False, limit_info

            # Success - reset circuit breaker failure count
            self.circuit_breaker.record_success()
            limit_info['current_usage'] = current_daily
            return True, limit_info

        except (ValueError, TypeError, AttributeError) as e:
            # Record failure and use fallback
            correlation_id = self.circuit_breaker.record_failure()
            logger.error(
                f"Cache failure in rate limiter",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'correlation_id': correlation_id
                },
                exc_info=True
            )
            return self.circuit_breaker.check_fallback_limit(
                user_identifier, resource_type, self.critical_resources, correlation_id
            )

    def increment_usage(
        self,
        user_identifier: str,
        resource_type: str,
        amount: int = 1,
        limit_type: str = 'requests'
    ) -> bool:
        """Increment usage counters with fallback on cache failure"""
        try:
            daily_key = self._build_key(resource_type, limit_type, user_identifier, 'daily')
            self.cache.set(daily_key, self.cache.get(daily_key, 0) + amount, 86400)

            limits = self._get_limits(resource_type, limit_type)
            if 'hourly' in limits:
                hourly_key = self._build_key(resource_type, limit_type, user_identifier, 'hourly')
                self.cache.set(hourly_key, self.cache.get(hourly_key, 0) + amount, 3600)

            return True

        except CACHE_EXCEPTIONS as e:
            correlation_id = str(uuid.uuid4())
            logger.warning(
                f"Failed to increment usage counter - using fallback",
                extra={'resource_type': resource_type, 'error': str(e), 'correlation_id': correlation_id}
            )
            self.circuit_breaker.increment_fallback(resource_type, user_identifier, amount)
            return True

    def get_usage_stats(self, user_identifier: str, resource_type: str) -> Dict[str, Any]:
        """Get current usage statistics with fallback support"""
        try:
            daily_key = self._build_key(resource_type, 'requests', user_identifier, 'daily')
            hourly_key = self._build_key(resource_type, 'requests', user_identifier, 'hourly')

            return {
                'daily_usage': self.cache.get(daily_key, 0),
                'hourly_usage': self.cache.get(hourly_key, 0),
                'resource_type': resource_type,
                'timestamp': datetime.now().isoformat(),
                'source': 'primary_cache'
            }

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Failed to get usage stats: {str(e)}")
            return {
                'resource_type': resource_type,
                'timestamp': datetime.now().isoformat(),
                'source': 'fallback_cache',
                'warning': 'Primary cache unavailable'
            }

    def _get_limits(self, resource_type: str, limit_type: str) -> Dict[str, int]:
        """Get rate limits for resource type"""
        default_limits = {
            'llm_calls': {'requests': {'daily': 100, 'hourly': 20}},
            'translations': {'requests': {'daily': 500, 'hourly': 100}},
            'knowledge_queries': {'requests': {'daily': 200, 'hourly': 50}}
        }

        custom_limits = getattr(settings, 'ONBOARDING_RATE_LIMITS', {})
        limits = default_limits.get(resource_type, {}).get(limit_type, {'daily': 100})
        custom_resource_limits = custom_limits.get(resource_type, {}).get(limit_type, {})
        limits.update(custom_resource_limits)
        return limits

    def _build_key(self, resource_type: str, limit_type: str, user_id: str, window: str) -> str:
        """Build cache key for rate limit"""
        now = datetime.now()
        if window == 'hourly':
            time_suffix = now.strftime('%Y-%m-%d-%H')
        else:
            time_suffix = now.strftime('%Y-%m-%d')
        return f"rate_limit:{resource_type}:{limit_type}:{user_id}:{time_suffix}"

    def _get_next_reset_time(self, window: str) -> str:
        """Get next reset time for window"""
        now = datetime.now()
        if window == 'hourly':
            next_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return next_time.isoformat()

    def _calculate_retry_after(self, reset_time: str) -> int:
        """Calculate Retry-After value in seconds"""
        try:
            reset_dt = datetime.fromisoformat(reset_time)
            delta = (reset_dt - datetime.now()).total_seconds()
            return max(int(delta), 60)
        except (ValueError, TypeError):
            return 3600


def get_rate_limiter() -> RateLimiter:
    """Factory function to get rate limiter"""
    return RateLimiter()
