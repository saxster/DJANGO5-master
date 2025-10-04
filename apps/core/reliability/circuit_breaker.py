"""
Generalized Circuit Breaker Pattern

Prevents cascade failures by failing fast when service is unhealthy.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).

Moved from apps/noc/middleware/circuit_breaker.py for general use.
"""

import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

from django.core.cache import cache
from django.conf import settings

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS, DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation
    - OPEN: Service failing, reject requests
    - HALF_OPEN: Testing if service recovered

    Usage:
        cb = CircuitBreaker('external_api')

        @cb.protected
        def call_external_api():
            return requests.get('https://api.example.com')
    """

    FAILURE_THRESHOLD = 5
    TIMEOUT_SECONDS = 60
    HALF_OPEN_ATTEMPTS = 3

    def __init__(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        timeout_seconds: Optional[int] = None
    ):
        self.name = name
        self.failure_threshold = failure_threshold or self.FAILURE_THRESHOLD
        self.timeout_seconds = timeout_seconds or self.TIMEOUT_SECONDS

        self.cache_prefix = f"circuit_breaker:{name}"

    def is_open(self) -> bool:
        """Check if circuit is open."""
        state = cache.get(f"{self.cache_prefix}:state")

        if state == 'OPEN':
            opened_at = cache.get(f"{self.cache_prefix}:opened_at")

            if opened_at and (time.time() - opened_at) >= self.timeout_seconds:
                self._transition_to_half_open()
                return False

            return True

        return False

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        if self.is_open():
            raise CircuitBreakerOpen(f"Circuit breaker open for {self.name}")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result

        except (NETWORK_EXCEPTIONS, DATABASE_EXCEPTIONS) as e:
            self.record_failure()
            raise

    def protected(self, func: Callable) -> Callable:
        """
        Decorator to protect function with circuit breaker.

        Usage:
            @circuit_breaker.protected
            def risky_operation():
                ...
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.execute(func, *args, **kwargs)

        return wrapper

    def record_success(self):
        """Reset circuit on success."""
        cache.delete_many([
            f"{self.cache_prefix}:failures",
            f"{self.cache_prefix}:opened_at",
            f"{self.cache_prefix}:state",
            f"{self.cache_prefix}:half_open_attempts"
        ])

        logger.info(f"Circuit breaker success: {self.name}")

    def record_failure(self):
        """Record failure and open circuit if threshold reached."""
        failures = cache.get(f"{self.cache_prefix}:failures", 0)
        failures += 1
        cache.set(f"{self.cache_prefix}:failures", failures, 3600)

        state = cache.get(f"{self.cache_prefix}:state", 'CLOSED')

        if state == 'HALF_OPEN':
            self._transition_to_open()
        elif failures >= self.failure_threshold:
            self._transition_to_open()

        logger.warning(
            f"Circuit breaker failure recorded: {self.name} ({failures}/{self.failure_threshold})"
        )

    def _transition_to_open(self):
        """Transition circuit to OPEN state."""
        cache.set(f"{self.cache_prefix}:state", 'OPEN', self.timeout_seconds)
        cache.set(f"{self.cache_prefix}:opened_at", time.time(), self.timeout_seconds)

        logger.error(f"Circuit breaker opened: {self.name}")

    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        cache.set(f"{self.cache_prefix}:state", 'HALF_OPEN', self.timeout_seconds)
        cache.set(f"{self.cache_prefix}:half_open_attempts", 0, self.timeout_seconds)

        logger.info(f"Circuit breaker half-open: {self.name}")


# Global circuit breakers for common services
database_circuit_breaker = CircuitBreaker('database')
redis_circuit_breaker = CircuitBreaker('redis')
external_api_circuit_breaker = CircuitBreaker('external_api')
