"""
Unit tests for OntologyQueryService with Redis caching and circuit breaker.

Tests:
- Cached results returned without querying registry
- Registry queried on cache miss
- Circuit breaker opens after 3 consecutive failures
"""

import pytest
from unittest.mock import patch, MagicMock
from apps.core.services.ontology_query_service import OntologyQueryService, CircuitBreaker


@pytest.fixture
def service():
    """Create fresh OntologyQueryService instance."""
    return OntologyQueryService()


class TestOntologyQueryService:
    """Test suite for OntologyQueryService."""

    def test_query_returns_cached_result_if_available(self, service):
        """Cached results should be returned without querying registry."""
        query = "authentication"

        # Mock cache hit
        with patch.object(service, '_get_from_cache') as mock_cache:
            mock_cache.return_value = [{'name': 'AuthService'}]

            results = service.query(query)

            assert len(results) == 1
            assert results[0]['name'] == 'AuthService'
            mock_cache.assert_called_once_with(f"ontology_query:{query}:5")

    def test_query_uses_registry_on_cache_miss(self, service):
        """Registry should be queried on cache miss."""
        query = "authentication"

        with patch.object(service, '_get_from_cache') as mock_cache, \
             patch('apps.ontology.registry.OntologyRegistry.search') as mock_search:

            mock_cache.return_value = None
            mock_search.return_value = [{'name': 'AuthService'}]

            results = service.query(query)

            assert len(results) == 1
            mock_search.assert_called_once_with(query)

    def test_query_respects_circuit_breaker(self, service):
        """Circuit breaker should open after consecutive failures."""
        query = "authentication"

        # Ensure cache is empty for all calls
        with patch.object(service, '_get_from_cache', return_value=None):
            # Simulate 3 consecutive failures
            for i in range(3):
                with patch('apps.ontology.registry.OntologyRegistry.search', side_effect=Exception("Registry down")):
                    results = service.query(query)
                    assert results == []

            # 4th call should short-circuit (no registry call)
            with patch('apps.ontology.registry.OntologyRegistry.search') as mock_search:
                results = service.query(query)
                assert results == []
                mock_search.assert_not_called()  # Circuit breaker open

    def test_query_caches_successful_result(self, service):
        """Successful registry query should be cached."""
        query = "authentication"
        expected_result = [{'name': 'AuthService'}]

        with patch.object(service, '_get_from_cache') as mock_get, \
             patch.object(service, '_set_in_cache') as mock_set, \
             patch('apps.ontology.registry.OntologyRegistry.search') as mock_search:

            mock_get.return_value = None
            mock_search.return_value = expected_result

            results = service.query(query)

            # Should cache the result
            mock_set.assert_called_once_with(f"ontology_query:{query}:5", expected_result)
            assert results == expected_result

    def test_query_respects_limit_parameter(self, service):
        """Query should respect limit parameter."""
        query = "test"
        limit = 3
        registry_results = [{'id': i} for i in range(10)]

        with patch.object(service, '_get_from_cache') as mock_cache, \
             patch('apps.ontology.registry.OntologyRegistry.search') as mock_search:

            mock_cache.return_value = None
            mock_search.return_value = registry_results

            results = service.query(query, limit=limit)

            # Should slice results to limit
            assert len(results) == limit


class TestCircuitBreaker:
    """Test suite for CircuitBreaker."""

    def test_circuit_breaker_starts_closed(self):
        """Circuit breaker should start in closed state."""
        breaker = CircuitBreaker()
        assert breaker.state == 'closed'
        assert breaker.failure_count == 0

    def test_circuit_breaker_opens_after_threshold_failures(self):
        """Circuit breaker should open after reaching failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        def failing_func():
            raise Exception("Simulated failure")

        # Trigger 3 failures
        for _ in range(3):
            result = breaker.call(failing_func)
            assert result is None

        # Circuit should now be open
        assert breaker.state == 'open'
        assert breaker.failure_count == 3

    def test_circuit_breaker_resets_on_success(self):
        """Circuit breaker should reset failure count on success."""
        breaker = CircuitBreaker(failure_threshold=3)

        def failing_func():
            raise Exception("Simulated failure")

        def success_func():
            return "success"

        # Trigger 2 failures
        for _ in range(2):
            breaker.call(failing_func)

        assert breaker.failure_count == 2

        # Success should reset
        result = breaker.call(success_func)
        assert result == "success"
        assert breaker.failure_count == 0
        assert breaker.state == 'closed'

    def test_circuit_breaker_half_open_on_recovery_timeout(self):
        """Circuit breaker should enter half-open state after recovery timeout."""
        import time

        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

        def failing_func():
            raise Exception("Simulated failure")

        # Open the circuit
        for _ in range(3):
            breaker.call(failing_func)

        assert breaker.state == 'open'

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should enter half-open state
        def success_func():
            return "recovered"

        result = breaker.call(success_func)
        assert result == "recovered"
        assert breaker.state == 'closed'

    def test_circuit_breaker_passes_function_args(self):
        """Circuit breaker should pass arguments to wrapped function."""
        breaker = CircuitBreaker()

        def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = breaker.call(func_with_args, "x", "y", c="z")
        assert result == "x-y-z"
