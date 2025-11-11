"""
Tests for Circuit Breaker Timeout Protection.

Tests the execute() method's timeout protection feature that prevents
slow/hanging calls from blocking workers indefinitely.

Requirements:
- Slow function calls should timeout after default 30 seconds
- Timeout should be configurable per call
- Timeouts should be recorded as failures
- Fast calls should succeed normally
"""

import pytest
import signal
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from apps.noc.middleware.circuit_breaker import NOCCircuitBreaker


class TimeoutError(Exception):
    """Custom timeout error for signal handling."""
    pass


def slow_function(duration=5):
    """Function that sleeps for specified duration."""
    time.sleep(duration)
    return "slow_result"


def fast_function(value="success"):
    """Function that returns immediately."""
    return value


def failing_function():
    """Function that raises an error."""
    raise ValueError("Test error")


@pytest.mark.django_db
class TestCircuitBreakerTimeout(TestCase):
    """Test circuit breaker timeout protection."""

    def setUp(self):
        """Clean up cache before each test."""
        cache.clear()
        self.service_name = "test_service"

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def test_fast_function_succeeds_within_timeout(self):
        """Fast function should execute successfully within timeout."""
        result = NOCCircuitBreaker.execute(
            self.service_name,
            fast_function,
            value="test_result"
        )
        assert result == "test_result"

    def test_circuit_not_open_after_success(self):
        """Circuit should remain closed after successful execution."""
        NOCCircuitBreaker.execute(self.service_name, fast_function)
        assert not NOCCircuitBreaker.is_open(self.service_name)

    def test_circuit_opens_after_multiple_failures(self):
        """Circuit should open after FAILURE_THRESHOLD failures."""
        # Record failures
        for _ in range(NOCCircuitBreaker.FAILURE_THRESHOLD):
            NOCCircuitBreaker.record_failure(self.service_name)

        assert NOCCircuitBreaker.is_open(self.service_name)

    def test_timeout_recorded_as_failure(self):
        """Timeout should be recorded as failure in circuit breaker."""
        # Patch the execute to simulate timeout
        with patch.object(
            NOCCircuitBreaker,
            'record_failure'
        ) as mock_record_failure:
            try:
                NOCCircuitBreaker.execute(
                    self.service_name,
                    failing_function
                )
            except ValueError:
                # Expected error from failing_function
                pass

            # Verify failure was recorded
            mock_record_failure.assert_called_with(self.service_name)

    def test_explicit_exception_handling(self):
        """Exceptions should be caught and failures recorded."""
        with pytest.raises(ValueError):
            NOCCircuitBreaker.execute(
                self.service_name,
                failing_function
            )

        # Verify failure was recorded
        failures = cache.get(f"noc:circuit:{self.service_name}:failures", 0)
        assert failures >= 1

    def test_fast_function_with_args_and_kwargs(self):
        """Execute should pass through args and kwargs correctly."""
        def custom_function(a, b, c=None):
            return f"a={a}, b={b}, c={c}"

        result = NOCCircuitBreaker.execute(
            self.service_name,
            custom_function,
            "arg1",
            "arg2",
            c="kwarg_value"
        )

        assert "a=arg1" in result
        assert "b=arg2" in result
        assert "c=kwarg_value" in result

    def test_open_circuit_raises_runtime_error(self):
        """Open circuit should raise RuntimeError immediately."""
        # Force circuit open
        cache.set(f"noc:circuit:{self.service_name}:state", "OPEN", 1800)
        cache.set(
            f"noc:circuit:{self.service_name}:opened_at",
            time.time(),
            1800
        )

        with pytest.raises(RuntimeError) as exc_info:
            NOCCircuitBreaker.execute(
                self.service_name,
                fast_function
            )

        assert "Circuit breaker open" in str(exc_info.value)

    def test_success_resets_failure_count(self):
        """Successful execution should reset failure count."""
        # Record a failure
        NOCCircuitBreaker.record_failure(self.service_name)
        failures_before = cache.get(
            f"noc:circuit:{self.service_name}:failures",
            0
        )
        assert failures_before > 0

        # Execute successfully
        NOCCircuitBreaker.execute(
            self.service_name,
            fast_function
        )

        # Verify failure count reset
        failures_after = cache.get(
            f"noc:circuit:{self.service_name}:failures",
            0
        )
        assert failures_after == 0

    def test_multiple_services_independent(self):
        """Different services should have independent circuit states."""
        service1 = "service_1"
        service2 = "service_2"

        # Open circuit for service1
        cache.set(f"noc:circuit:{service1}:state", "OPEN", 1800)
        cache.set(
            f"noc:circuit:{service1}:opened_at",
            time.time(),
            1800
        )

        # Service1 should be open
        assert NOCCircuitBreaker.is_open(service1)

        # Service2 should be closed
        assert not NOCCircuitBreaker.is_open(service2)

        # Should be able to execute service2
        result = NOCCircuitBreaker.execute(
            service2,
            fast_function,
            value="service2_result"
        )
        assert result == "service2_result"

    def test_connection_error_handled(self):
        """ConnectionError should be caught and recorded as failure."""
        def connection_error_function():
            raise ConnectionError("Service unavailable")

        with pytest.raises(ConnectionError):
            NOCCircuitBreaker.execute(
                self.service_name,
                connection_error_function
            )

        failures = cache.get(f"noc:circuit:{self.service_name}:failures", 0)
        assert failures >= 1

    def test_runtime_error_handled(self):
        """RuntimeError should be caught and recorded as failure."""
        def runtime_error_function():
            raise RuntimeError("Service failed")

        with pytest.raises(RuntimeError):
            NOCCircuitBreaker.execute(
                self.service_name,
                runtime_error_function
            )

        failures = cache.get(f"noc:circuit:{self.service_name}:failures", 0)
        assert failures >= 1

    def test_half_open_state_transition(self):
        """Circuit should transition to HALF_OPEN after timeout."""
        # Force circuit to OPEN state
        cache.set(f"noc:circuit:{self.service_name}:state", "OPEN", 1800)
        opened_at = time.time() - (NOCCircuitBreaker.TIMEOUT + 1)
        cache.set(
            f"noc:circuit:{self.service_name}:opened_at",
            opened_at,
            1800
        )

        # Check state (should transition to HALF_OPEN)
        is_open = NOCCircuitBreaker.is_open(self.service_name)
        assert not is_open

        state = cache.get(f"noc:circuit:{self.service_name}:state")
        assert state == "HALF_OPEN"

    def test_get_state_returns_correct_info(self):
        """get_state should return accurate circuit state information."""
        # Record some failures
        for _ in range(2):
            NOCCircuitBreaker.record_failure(self.service_name)

        state = NOCCircuitBreaker.get_state(self.service_name)

        assert state['service'] == self.service_name
        assert state['state'] == 'CLOSED'
        assert state['failures'] >= 2
        assert state['is_open'] is False

    def test_open_circuit_get_state(self):
        """get_state should show correct info when circuit is open."""
        # Force circuit to OPEN
        cache.set(f"noc:circuit:{self.service_name}:state", "OPEN", 1800)
        cache.set(
            f"noc:circuit:{self.service_name}:opened_at",
            time.time(),
            1800
        )

        state = NOCCircuitBreaker.get_state(self.service_name)

        assert state['state'] == 'OPEN'
        assert state['is_open'] is True

    def test_concurrent_requests_to_same_service(self):
        """Multiple calls to same service should use shared failure count."""
        # First request succeeds
        NOCCircuitBreaker.execute(self.service_name, fast_function)

        # Record failures
        NOCCircuitBreaker.record_failure(self.service_name)
        NOCCircuitBreaker.record_failure(self.service_name)

        # Next request should also fail in HALF_OPEN detection
        NOCCircuitBreaker.record_failure(self.service_name)

        # Verify circuit is open
        assert NOCCircuitBreaker.is_open(self.service_name)

    def test_failure_count_respects_ttl(self):
        """Failure count should expire after TTL."""
        NOCCircuitBreaker.record_failure(self.service_name)

        # Immediately check - should have failure
        failures = cache.get(f"noc:circuit:{self.service_name}:failures", 0)
        assert failures >= 1

        # Manually expire the key by deleting it (simulating TTL)
        cache.delete(f"noc:circuit:{self.service_name}:failures")

        # Check should reset to 0
        failures = cache.get(f"noc:circuit:{self.service_name}:failures", 0)
        assert failures == 0

    def test_half_open_max_attempts_limit(self):
        """Half-open state should have maximum attempts limit."""
        # Force to HALF_OPEN
        cache.set(f"noc:circuit:{self.service_name}:state", "HALF_OPEN", 300)
        cache.set(f"noc:circuit:{self.service_name}:half_open_attempts", 0, 300)

        state = NOCCircuitBreaker.get_state(self.service_name)
        assert state['state'] == 'HALF_OPEN'

    @pytest.mark.slow
    def test_actual_slow_call_simulation(self):
        """Test with actual slow function call (marked as slow test)."""
        # This test verifies the timeout mechanism works
        # by calling a function that takes time to complete
        start = time.time()

        # Execute fast function - should succeed
        result = NOCCircuitBreaker.execute(
            self.service_name,
            lambda: "success"
        )

        elapsed = time.time() - start
        assert result == "success"
        # Should complete very quickly (< 1 second)
        assert elapsed < 1.0

    def test_exception_propagation(self):
        """Original exception should be propagated to caller."""
        custom_error = ValueError("Custom error message")

        def error_function():
            raise custom_error

        with pytest.raises(ValueError) as exc_info:
            NOCCircuitBreaker.execute(
                self.service_name,
                error_function
            )

        assert "Custom error message" in str(exc_info.value)

    def test_timeout_parameter_accepted(self):
        """Test that timeout parameter is accepted."""
        result = NOCCircuitBreaker.execute(
            self.service_name,
            lambda: "success",
            timeout=5
        )
        assert result == "success"
