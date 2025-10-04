"""
Circuit Breaker service for external API resilience.

Implements circuit breaker pattern to prevent cascading failures
when external services (LLM, Vision, Speech APIs) become unavailable.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service failing, requests fail fast
- HALF_OPEN: Testing if service recovered

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
"""

import logging
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5        # Open after N failures
    recovery_timeout: int = 60        # Seconds before trying half-open
    success_threshold: int = 3        # Half-open -> closed after N successes
    timeout: int = 30                 # Request timeout seconds


class CircuitBreakerException(Exception):
    """Exception raised when circuit is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.

    Tracks failures and automatically opens circuit to fail fast
    when service is unavailable. Provides graceful degradation.
    """

    def __init__(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker for service.

        Args:
            service_name: Name of service (llm_api, vision_api, etc.)
            config: Optional custom configuration
        """
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()

        # Cache keys for state management
        self.state_key = f"circuit_breaker:{service_name}:state"
        self.failures_key = f"circuit_breaker:{service_name}:failures"
        self.successes_key = f"circuit_breaker:{service_name}:successes"
        self.opened_at_key = f"circuit_breaker:{service_name}:opened_at"

    def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            fallback: Optional fallback function if circuit open
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback result

        Raises:
            CircuitBreakerException: If circuit open and no fallback
        """
        current_state = self._get_state()

        # If circuit is OPEN, check if recovery timeout passed
        if current_state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._set_state(CircuitState.HALF_OPEN)
                logger.info(
                    f"Circuit breaker {self.service_name}: OPEN -> HALF_OPEN (testing recovery)"
                )
            else:
                # Circuit still open - fail fast
                logger.warning(
                    f"Circuit breaker {self.service_name}: OPEN - failing fast"
                )
                if fallback:
                    logger.info(f"Using fallback for {self.service_name}")
                    return fallback(*args, **kwargs)
                raise CircuitBreakerException(
                    f"Circuit breaker open for {self.service_name}"
                )

        # Execute function
        try:
            result = func(*args, **kwargs)

            # Success - handle state transition
            self._on_success(current_state)

            return result

        except Exception as exc:
            # Failure - handle state transition
            self._on_failure(current_state, exc)

            # Use fallback if available
            if fallback:
                logger.info(
                    f"Circuit breaker {self.service_name}: using fallback after error"
                )
                return fallback(*args, **kwargs)

            # Re-raise exception
            raise

    def _get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        state_str = cache.get(self.state_key, CircuitState.CLOSED.value)
        return CircuitState(state_str)

    def _set_state(self, state: CircuitState):
        """Set circuit breaker state."""
        cache.set(self.state_key, state.value, timeout=3600)  # 1 hour TTL

        if state == CircuitState.OPEN:
            # Record when circuit opened
            cache.set(
                self.opened_at_key,
                timezone.now().isoformat(),
                timeout=3600
            )

    def _should_attempt_reset(self) -> bool:
        """Check if recovery timeout has passed."""
        opened_at_str = cache.get(self.opened_at_key)
        if not opened_at_str:
            return True

        opened_at = datetime.fromisoformat(opened_at_str)
        elapsed = (timezone.now() - opened_at).total_seconds()

        return elapsed >= self.config.recovery_timeout

    def _on_success(self, current_state: CircuitState):
        """Handle successful call."""
        if current_state == CircuitState.HALF_OPEN:
            # Increment success counter
            successes = cache.get(self.successes_key, 0) + 1
            cache.set(self.successes_key, successes, timeout=300)

            # Check if threshold met
            if successes >= self.config.success_threshold:
                self._set_state(CircuitState.CLOSED)
                self._reset_counters()
                logger.info(
                    f"Circuit breaker {self.service_name}: HALF_OPEN -> CLOSED (recovered)"
                )
        elif current_state == CircuitState.CLOSED:
            # Reset failure counter on success
            cache.delete(self.failures_key)

    def _on_failure(self, current_state: CircuitState, exc: Exception):
        """Handle failed call."""
        # Increment failure counter
        failures = cache.get(self.failures_key, 0) + 1
        cache.set(self.failures_key, failures, timeout=300)  # 5 min window

        logger.warning(
            f"Circuit breaker {self.service_name}: failure #{failures}",
            extra={
                'service': self.service_name,
                'failures': failures,
                'state': current_state.value,
                'exception': type(exc).__name__
            }
        )

        # Check if should open circuit
        if current_state == CircuitState.CLOSED:
            if failures >= self.config.failure_threshold:
                self._set_state(CircuitState.OPEN)
                logger.error(
                    f"Circuit breaker {self.service_name}: CLOSED -> OPEN "
                    f"(threshold {self.config.failure_threshold} reached)"
                )

        elif current_state == CircuitState.HALF_OPEN:
            # Any failure in half-open state reopens circuit
            self._set_state(CircuitState.OPEN)
            logger.error(
                f"Circuit breaker {self.service_name}: HALF_OPEN -> OPEN "
                f"(recovery test failed)"
            )

    def _reset_counters(self):
        """Reset failure and success counters."""
        cache.delete(self.failures_key)
        cache.delete(self.successes_key)
        cache.delete(self.opened_at_key)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.

        Returns:
            Status dict with state and metrics
        """
        state = self._get_state()
        failures = cache.get(self.failures_key, 0)
        successes = cache.get(self.successes_key, 0)

        status = {
            'service': self.service_name,
            'state': state.value,
            'failures': failures,
            'successes': successes,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'success_threshold': self.config.success_threshold
            }
        }

        if state == CircuitState.OPEN:
            opened_at_str = cache.get(self.opened_at_key)
            if opened_at_str:
                opened_at = datetime.fromisoformat(opened_at_str)
                status['opened_at'] = opened_at.isoformat()
                status['open_duration_seconds'] = (
                    timezone.now() - opened_at
                ).total_seconds()

        return status


# Global circuit breakers for common services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """
    Get or create circuit breaker for service.

    Args:
        service_name: Service name (llm_api, vision_api, speech_api)

    Returns:
        CircuitBreaker instance
    """
    if service_name not in _circuit_breakers:
        # Create with service-specific config
        config = _get_service_config(service_name)
        _circuit_breakers[service_name] = CircuitBreaker(
            service_name=service_name,
            config=config
        )

    return _circuit_breakers[service_name]


def _get_service_config(service_name: str) -> CircuitBreakerConfig:
    """Get service-specific circuit breaker configuration."""
    # LLM APIs - more lenient (expensive calls)
    if 'llm' in service_name.lower():
        return CircuitBreakerConfig(
            failure_threshold=3,   # Open after 3 failures
            recovery_timeout=120,  # 2 minutes recovery
            success_threshold=2,   # 2 successes to close
            timeout=60             # 60s timeout
        )

    # Vision/Speech APIs - standard config
    elif 'vision' in service_name.lower() or 'speech' in service_name.lower():
        return CircuitBreakerConfig(
            failure_threshold=5,   # Open after 5 failures
            recovery_timeout=60,   # 1 minute recovery
            success_threshold=3,   # 3 successes to close
            timeout=30             # 30s timeout
        )

    # Default config
    return CircuitBreakerConfig()
