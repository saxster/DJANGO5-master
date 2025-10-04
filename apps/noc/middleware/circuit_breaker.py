"""
NOC Circuit Breaker Implementation.

Prevents cascade failures in NOC pipeline by opening circuit after repeated failures.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import time
import logging
from django.core.cache import cache
from typing import Callable, Any

__all__ = ['NOCCircuitBreaker']

logger = logging.getLogger('noc.circuit_breaker')


class NOCCircuitBreaker:
    """
    Circuit breaker pattern implementation for NOC services.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Circuit breaker triggered, requests fail fast
    - HALF_OPEN: Testing if service recovered, limited requests pass

    Configuration:
    - FAILURE_THRESHOLD: 3 failures within window opens circuit
    - TIMEOUT: 1800 seconds (30 minutes) before trying half-open
    - HALF_OPEN_MAX_ATTEMPTS: 5 test requests in half-open state
    """

    FAILURE_THRESHOLD = 3
    TIMEOUT = 1800
    HALF_OPEN_MAX_ATTEMPTS = 5

    @classmethod
    def is_open(cls, service_name: str) -> bool:
        """Check if circuit is open (service failing)."""
        state = cache.get(f"noc:circuit:{service_name}:state")
        if state == 'OPEN':
            opened_at = cache.get(f"noc:circuit:{service_name}:opened_at")
            if opened_at and (time.time() - opened_at) >= cls.TIMEOUT:
                cls._transition_to_half_open(service_name)
                return False
            return True
        return False

    @classmethod
    def execute(cls, service_name: str, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            service_name: Service identifier
            func: Function to execute
            *args, **kwargs: Arguments for function

        Returns:
            Function result or raises exception

        Raises:
            RuntimeError: If circuit is open
        """
        if cls.is_open(service_name):
            raise RuntimeError(f"Circuit breaker open for {service_name}")

        try:
            result = func(*args, **kwargs)
            cls.record_success(service_name)
            return result
        except (ValueError, RuntimeError, ConnectionError) as e:
            cls.record_failure(service_name)
            raise

    @classmethod
    def record_success(cls, service_name: str):
        """Reset circuit on success."""
        cache.delete_many([
            f"noc:circuit:{service_name}:failures",
            f"noc:circuit:{service_name}:opened_at",
            f"noc:circuit:{service_name}:state",
            f"noc:circuit:{service_name}:half_open_attempts"
        ])
        logger.info(f"Circuit breaker success for {service_name}")

    @classmethod
    def record_failure(cls, service_name: str):
        """Record failure and open circuit if threshold reached."""
        failures = cache.get(f"noc:circuit:{service_name}:failures", 0)
        failures += 1
        cache.set(f"noc:circuit:{service_name}:failures", failures, 3600)

        state = cache.get(f"noc:circuit:{service_name}:state", 'CLOSED')

        if state == 'HALF_OPEN':
            cls._transition_to_open(service_name)
        elif failures >= cls.FAILURE_THRESHOLD:
            cls._transition_to_open(service_name)

        logger.warning(
            f"Circuit breaker failure recorded for {service_name}",
            extra={'failures': failures, 'state': state}
        )

    @classmethod
    def _transition_to_open(cls, service_name: str):
        """Transition circuit to OPEN state."""
        cache.set(f"noc:circuit:{service_name}:state", 'OPEN', cls.TIMEOUT)
        cache.set(f"noc:circuit:{service_name}:opened_at", time.time(), cls.TIMEOUT)
        logger.error(f"Circuit breaker opened for {service_name}")

    @classmethod
    def _transition_to_half_open(cls, service_name: str):
        """Transition circuit to HALF_OPEN state for testing."""
        cache.set(f"noc:circuit:{service_name}:state", 'HALF_OPEN', 300)
        cache.set(f"noc:circuit:{service_name}:half_open_attempts", 0, 300)
        logger.info(f"Circuit breaker half-open for {service_name}")

    @classmethod
    def get_state(cls, service_name: str) -> dict:
        """Get circuit breaker state for monitoring."""
        state = cache.get(f"noc:circuit:{service_name}:state", 'CLOSED')
        failures = cache.get(f"noc:circuit:{service_name}:failures", 0)
        opened_at = cache.get(f"noc:circuit:{service_name}:opened_at")

        return {
            'service': service_name,
            'state': state,
            'failures': failures,
            'opened_at': opened_at,
            'is_open': cls.is_open(service_name)
        }