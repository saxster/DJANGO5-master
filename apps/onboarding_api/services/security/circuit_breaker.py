"""
Circuit Breaker Pattern for Resilient Rate Limiting
Handles cache failures gracefully with fallback mechanisms
"""
import logging
import uuid
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker for rate limiting resilience
    Implements fail-open/fail-closed strategies based on resource criticality
    """

    def __init__(self, threshold: int = 5, reset_minutes: int = 5):
        self.failure_count = 0
        self.threshold = threshold
        self.reset_minutes = reset_minutes
        self.reset_time = None
        self.fallback_cache: Dict[str, int] = {}

    def is_open(self) -> bool:
        """Check if circuit breaker is currently open"""
        if self.reset_time is None:
            return False

        if datetime.now() >= self.reset_time:
            logger.info("Circuit breaker CLOSED - reset time reached")
            self.reset_time = None
            self.failure_count = 0
            return False

        return True

    def record_failure(self) -> str:
        """Record a failure and potentially open the circuit"""
        self.failure_count += 1
        correlation_id = str(uuid.uuid4())

        if self.failure_count >= self.threshold and self.reset_time is None:
            self.reset_time = datetime.now() + timedelta(minutes=self.reset_minutes)
            logger.critical(
                f"Circuit breaker OPENED after {self.failure_count} failures",
                extra={'correlation_id': correlation_id, 'reset_time': self.reset_time.isoformat()}
            )

        return correlation_id

    def record_success(self):
        """Record a success and reset failure count"""
        if self.failure_count > 0:
            logger.info(f"Cache recovered, resetting failure count from {self.failure_count}")
            self.failure_count = 0

    def handle_open_circuit(
        self,
        resource_type: str,
        critical_resources: list
    ) -> Tuple[bool, Dict[str, Any]]:
        """Handle request when circuit breaker is open"""
        is_critical = resource_type in critical_resources

        if is_critical:
            # Fail-closed for critical resources
            retry_after = int((self.reset_time - datetime.now()).total_seconds())
            logger.warning(
                f"Circuit breaker OPEN - blocking critical resource: {resource_type}",
                extra={'resource_type': resource_type, 'retry_after': retry_after, 'strategy': 'fail_closed'}
            )

            return False, {
                'allowed': False,
                'reason': 'circuit_breaker_open',
                'critical_resource': True,
                'retry_after': retry_after,
                'reset_time': self.reset_time.isoformat()
            }
        else:
            # Fail-open for non-critical resources
            logger.warning(
                f"Circuit breaker OPEN - allowing non-critical resource: {resource_type}",
                extra={'resource_type': resource_type, 'strategy': 'fail_open_with_logging'}
            )

            return True, {
                'allowed': True,
                'reason': 'circuit_breaker_open_fail_open',
                'critical_resource': False,
                'warning': 'Rate limiting unavailable - degraded mode'
            }

    def check_fallback_limit(
        self,
        user_identifier: str,
        resource_type: str,
        critical_resources: list,
        correlation_id: str,
        fallback_limit: int = 50
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit using in-memory fallback cache"""
        is_critical = resource_type in critical_resources

        # Fail-closed for critical resources
        if is_critical:
            logger.warning(
                f"Fallback check for critical resource - BLOCKING: {resource_type}",
                extra={
                    'user_identifier': user_identifier,
                    'resource_type': resource_type,
                    'correlation_id': correlation_id,
                    'strategy': 'fail_closed'
                }
            )

            return False, {
                'allowed': False,
                'reason': 'cache_failure_critical_resource',
                'critical_resource': True,
                'retry_after': 300,
                'correlation_id': correlation_id
            }

        # Use fallback cache for non-critical resources
        fallback_key = f"{resource_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"
        current_count = self.fallback_cache.get(fallback_key, 0)

        if current_count >= fallback_limit:
            logger.warning(
                f"Fallback rate limit exceeded for user {user_identifier}",
                extra={
                    'user_identifier': user_identifier,
                    'resource_type': resource_type,
                    'current_count': current_count,
                    'fallback_limit': fallback_limit,
                    'correlation_id': correlation_id
                }
            )

            return False, {
                'allowed': False,
                'reason': 'fallback_limit_exceeded',
                'current_usage': current_count,
                'limit': fallback_limit,
                'window': 'hourly_fallback',
                'retry_after': 3600,
                'correlation_id': correlation_id
            }

        # Increment and clean old entries
        self.fallback_cache[fallback_key] = current_count + 1
        self._clean_fallback_cache()

        logger.info(
            f"Fallback rate limit check passed for {user_identifier}",
            extra={
                'user_identifier': user_identifier,
                'resource_type': resource_type,
                'current_count': current_count + 1,
                'fallback_limit': fallback_limit,
                'correlation_id': correlation_id
            }
        )

        return True, {
            'allowed': True,
            'reason': 'fallback_cache_passed',
            'current_usage': current_count + 1,
            'limit': fallback_limit,
            'window': 'hourly_fallback',
            'warning': 'Using fallback rate limiting',
            'correlation_id': correlation_id
        }

    def increment_fallback(self, resource_type: str, user_identifier: str, amount: int = 1):
        """Increment fallback cache counter"""
        fallback_key = f"{resource_type}:{user_identifier}:{datetime.now().strftime('%Y-%m-%d-%H')}"
        self.fallback_cache[fallback_key] = self.fallback_cache.get(fallback_key, 0) + amount

    def _clean_fallback_cache(self, max_entries: int = 100):
        """Clean old fallback cache entries"""
        if len(self.fallback_cache) > max_entries:
            keys_to_remove = list(self.fallback_cache.keys())[:20]
            for key in keys_to_remove:
                del self.fallback_cache[key]
