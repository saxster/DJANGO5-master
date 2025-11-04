"""
Circuit Breaker for LLM Provider Resilience

Implements circuit breaker pattern to prevent cascading failures.

States:
- CLOSED: Normal operation
- OPEN: Too many failures, reject requests
- HALF_OPEN: Testing if service recovered

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Resilience pattern

Sprint 7-8 Phase 2: Core Services
"""

import logging
import time
from typing import Callable, Any, Dict
from django.core.cache import cache
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE
from apps.core_onboarding.services.llm.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker for LLM provider calls.

    Opens circuit after consecutive failures to prevent cascading errors.
    Auto-resets after cooldown period.
    """

    def __init__(self, provider_name: str, tenant_id: int, config: dict = None):
        """
        Initialize circuit breaker.

        Args:
            provider_name: LLM provider name
            tenant_id: Tenant identifier
            config: Circuit breaker configuration (optional)
        """
        self.provider_name = provider_name
        self.tenant_id = tenant_id
        self.cache_key = f"circuit_breaker:{provider_name}:{tenant_id}"

        # Configuration from settings or defaults
        if config is None:
            from django.conf import settings
            config = getattr(settings, 'LLM_CIRCUIT_BREAKER', {})

        self.failure_threshold = config.get('failure_threshold', 3)
        self.cooldown_seconds = config.get('cooldown_seconds', 60)
        self.half_open_max_calls = config.get('half_open_max_calls', 1)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        # Check circuit state
        if self.is_open():
            logger.warning(f"Circuit breaker OPEN for {self.provider_name}")
            raise CircuitBreakerOpenError(self.provider_name, self.cooldown_seconds)

        try:
            # Execute function
            result = func(*args, **kwargs)

            # Success - record it
            self.record_success()
            return result

        except Exception as e:
            # Failure - record it
            self.record_failure()
            logger.error(f"Circuit breaker recorded failure for {self.provider_name}: {e}")
            raise

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        state = cache.get(self.cache_key)

        if not state:
            return False  # No state = closed

        # Check if cooldown expired
        if state.get('state') == 'OPEN':
            opened_at = state.get('opened_at', 0)
            if time.time() - opened_at > self.cooldown_seconds:
                # Cooldown expired, transition to half-open
                state['state'] = 'HALF_OPEN'
                state['half_open_calls'] = 0
                cache.set(self.cache_key, state, timeout=self.cooldown_seconds)
                return False

            return True  # Still in cooldown

        return False

    def record_failure(self):
        """Record failure and potentially open circuit."""
        state = cache.get(self.cache_key) or {
            'failures': 0,
            'state': 'CLOSED',
            'opened_at': 0
        }

        state['failures'] += 1
        state['last_failure'] = time.time()

        # Check if threshold exceeded
        if state['failures'] >= self.failure_threshold:
            state['state'] = 'OPEN'
            state['opened_at'] = time.time()

            logger.warning(
                f"Circuit breaker OPENED for {self.provider_name} "
                f"after {state['failures']} failures"
            )

        # Store state with TTL
        cache.set(self.cache_key, state, timeout=self.cooldown_seconds + 60)

    def record_success(self):
        """Record success and close circuit if half-open."""
        state = cache.get(self.cache_key)

        if state and state.get('state') == 'HALF_OPEN':
            # Half-open successful call - close circuit
            cache.delete(self.cache_key)
            logger.info(f"Circuit breaker CLOSED for {self.provider_name} after successful recovery")
        elif state:
            # Reset failure count on success
            state['failures'] = 0
            cache.set(self.cache_key, state, timeout=self.cooldown_seconds + 60)

    def get_state(self) -> Dict[str, Any]:
        """
        Get current circuit breaker state.

        Returns:
            Dict with state, failures, timestamps
        """
        state = cache.get(self.cache_key)

        if not state:
            return {
                'state': 'CLOSED',
                'failures': 0,
                'provider': self.provider_name,
                'tenant_id': self.tenant_id
            }

        return {
            'state': state.get('state', 'CLOSED'),
            'failures': state.get('failures', 0),
            'opened_at': state.get('opened_at'),
            'last_failure': state.get('last_failure'),
            'provider': self.provider_name,
            'tenant_id': self.tenant_id
        }
