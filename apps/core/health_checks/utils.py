"""
Health check utilities: circuit breaker, timeout helpers, and caching.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
import functools
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timedelta
from threading import Lock
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

__all__ = [
    'CircuitBreaker',
    'timeout_check',
    'cache_health_check',
    'format_check_result',
]


class CircuitBreaker:
    """
    Circuit breaker pattern for external service health checks.
    Prevents cascading failures from unresponsive services.
    """

    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        self.lock = Lock()

    def call(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """Execute function with circuit breaker protection."""
        with self.lock:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                else:
                    return {
                        "status": "error",
                        "message": f"Circuit breaker open, failing fast. Retry after {self._time_until_reset():.0f}s",
                        "circuit_state": "open",
                    }

        try:
            result = func(*args, **kwargs)

            with self.lock:
                if self.state == "half-open":
                    self._reset()

            return result

        except (ConnectionError, TimeoutError, OSError) as e:
            with self.lock:
                self._record_failure()

            return {
                "status": "error",
                "message": f"Service unavailable: {str(e)}",
                "circuit_state": self.state,
            }

    def _record_failure(self):
        """Record a failure and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        logger.info("Circuit breaker reset to closed state")

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.timeout_seconds

    def _time_until_reset(self) -> float:
        """Calculate time remaining until reset attempt."""
        if self.last_failure_time is None:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, self.timeout_seconds - elapsed)


def timeout_check(timeout_seconds: int = 5):
    """
    Decorator to enforce timeout on health check functions.
    Uses signal-based timeout for sync functions.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"Health check timed out after {timeout_seconds}s")

            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)

                try:
                    result = func(*args, **kwargs)
                    signal.alarm(0)
                    return result
                finally:
                    signal.signal(signal.SIGALRM, old_handler)

            except TimeoutError as e:
                return {
                    "status": "error",
                    "message": str(e),
                    "timeout_seconds": timeout_seconds,
                }
            except (ConnectionError, OSError) as e:
                return {
                    "status": "error",
                    "message": f"Connection failed: {str(e)}",
                }

        return wrapper

    return decorator


def cache_health_check(cache_key_prefix: str, cache_ttl: int = 30):
    """
    Decorator to cache health check results.
    Prevents DoS by limiting check frequency.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            cache_key = f"health_check:{cache_key_prefix}:{func.__name__}"

            cached_result = cache.get(cache_key)
            if cached_result is not None:
                cached_result["cached"] = True
                return cached_result

            result = func(*args, **kwargs)
            result["cached"] = False

            try:
                cache.set(cache_key, result, cache_ttl)
            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"Failed to cache health check result: {e}")

            return result

        return wrapper

    return decorator


def format_check_result(
    status: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Format health check result in standardized structure.

    Args:
        status: One of 'healthy', 'degraded', 'error'
        message: Human-readable status message
        details: Additional check-specific details
        duration_ms: Check execution time in milliseconds

    Returns:
        Standardized health check result dictionary
    """
    result = {
        "status": status,
        "message": message,
        "timestamp": timezone.now().isoformat(),
    }

    if details:
        result["details"] = details

    if duration_ms is not None:
        result["duration_ms"] = round(duration_ms, 2)

    return result