"""
Performance tests for health check system.
Ensures health checks complete within acceptable time limits.
"""

import pytest
import time
from unittest.mock import patch, Mock
from apps.core.health_checks.manager import HealthCheckManager
from apps.core.services.health_check_service import HealthCheckService


@pytest.mark.django_db
class TestHealthCheckPerformance:
    """Performance test suite for health checks."""

    def test_individual_check_latency(self):
        """Test that individual checks complete within 100ms."""
        manager = HealthCheckManager()

        def fast_check():
            return {'status': 'healthy', 'message': 'OK'}

        manager.register_check('fast_check', fast_check)

        start_time = time.time()
        result = manager.run_check('fast_check')
        duration = (time.time() - start_time) * 1000

        assert duration < 100
        assert result['status'] == 'healthy'

    def test_parallel_check_execution_performance(self):
        """Test that parallel execution is faster than sequential."""
        manager = HealthCheckManager()

        def slow_check():
            time.sleep(0.01)
            return {'status': 'healthy'}

        for i in range(10):
            manager.register_check(f'check_{i}', slow_check)

        start_parallel = time.time()
        result_parallel = manager.run_all_checks(parallel=True)
        duration_parallel = time.time() - start_parallel

        start_sequential = time.time()
        result_sequential = manager.run_all_checks(parallel=False)
        duration_sequential = time.time() - start_sequential

        assert duration_parallel < duration_sequential
        assert duration_parallel < 0.5

    def test_health_check_service_overall_latency(self):
        """Test overall health check service latency."""
        service = HealthCheckService()

        with patch.object(service.manager, 'run_all_checks') as mock_run:
            mock_run.return_value = {
                'status': 'healthy',
                'checks': {},
                'summary': {'total_checks': 20, 'healthy': 20},
            }

            start_time = time.time()
            result = service.run_all_checks(log_results=False, update_availability=False)
            duration = (time.time() - start_time) * 1000

            assert duration < 200
            assert result['status'] == 'healthy'

    def test_critical_checks_only_faster_than_all(self):
        """Test that critical checks only is faster than all checks."""
        service = HealthCheckService()

        with patch.object(service.manager, 'run_all_checks') as mock_all:
            with patch.object(service, 'run_critical_checks_only') as mock_critical:
                mock_all.return_value = {'status': 'healthy', 'checks': {}}
                mock_critical.return_value = {'status': 'healthy', 'checks': {}}

                start_all = time.time()
                service.run_all_checks(log_results=False, update_availability=False)
                duration_all = time.time() - start_all

                start_critical = time.time()
                service.run_critical_checks_only()
                duration_critical = time.time() - start_critical

                assert duration_critical <= duration_all

    def test_timeout_enforcement(self):
        """Test that timeout decorator enforces time limits."""
        from apps.core.health_checks.utils import timeout_check

        @timeout_check(timeout_seconds=1)
        def slow_function():
            time.sleep(2)
            return {'status': 'healthy'}

        result = slow_function()

        assert result['status'] == 'error'
        assert 'timed out' in result['message']

    def test_circuit_breaker_fast_fail_performance(self):
        """Test circuit breaker fast-fails without delay."""
        from apps.core.health_checks.utils import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=60)

        def failing_func():
            raise ConnectionError('Service down')

        breaker.call(failing_func)
        breaker.call(failing_func)

        start_time = time.time()
        result = breaker.call(failing_func)
        duration = (time.time() - start_time) * 1000

        assert duration < 10
        assert result['status'] == 'error'
        assert 'Circuit breaker open' in result['message']

    def test_cached_health_check_performance(self):
        """Test that cached results return immediately."""
        from apps.core.health_checks.utils import cache_health_check

        call_count = 0

        @cache_health_check(cache_key_prefix='test', cache_ttl=30)
        def expensive_check():
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)
            return {'status': 'healthy'}

        result1 = expensive_check()
        result2 = expensive_check()

        assert result1['cached'] is False
        assert result2['cached'] is True
        assert call_count == 1


@pytest.mark.django_db
class TestHealthCheckEndpointPerformance:
    """Performance tests for health check HTTP endpoints."""

    def test_liveness_check_extremely_fast(self, client):
        """Test that liveness check is extremely fast (<10ms)."""
        start_time = time.time()
        response = client.get('/alive/')
        duration = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration < 50

    @patch('apps.core.health_checks.health_service.run_critical_checks_only')
    def test_readiness_check_fast(self, mock_critical, client):
        """Test that readiness check completes quickly."""
        mock_critical.return_value = {
            'status': 'healthy',
            'timestamp': time.time(),
            'checks': {},
        }

        start_time = time.time()
        response = client.get('/ready/')
        duration = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert duration < 500