"""
Integration tests for comprehensive health check system.
Tests degraded state handling, service orchestration, and end-to-end flows.
"""

import pytest
import json
from unittest.mock import patch, Mock
from django.test import Client, TestCase
from django.utils import timezone
from apps.core.services.health_check_service import HealthCheckService
from apps.core.health_checks.manager import HealthCheckManager
from apps.core.models.health_monitoring import HealthCheckLog, ServiceAvailability


@pytest.mark.django_db
class TestHealthCheckIntegration:
    """Integration tests for health check system."""

    def test_health_check_service_initialization(self):
        """Test health check service initialization."""
        service = HealthCheckService()

        assert service.manager is not None
        assert len(service.manager.checks) > 0

    def test_run_all_checks_with_logging(self):
        """Test running all checks with result logging."""
        service = HealthCheckService()

        with patch.object(service.manager, 'run_all_checks') as mock_run:
            mock_run.return_value = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'checks': {
                    'test_check': {
                        'status': 'healthy',
                        'message': 'OK',
                        'duration_ms': 10.0,
                    }
                },
                'summary': {'total_checks': 1, 'healthy': 1},
            }

            result = service.run_all_checks(log_results=True, update_availability=True)

            assert result['status'] == 'healthy'
            mock_run.assert_called_once()

    def test_run_critical_checks_only(self):
        """Test running only critical health checks."""
        service = HealthCheckService()

        result = service.run_critical_checks_only()

        assert 'status' in result
        assert 'checks' in result
        assert all(
            name in service.manager.checks
            for name in result['checks'].keys()
        )

    @patch('apps.core.health_checks.database.check_database_connectivity')
    def test_degraded_state_handling(self, mock_db_check):
        """Test system handles degraded state correctly."""
        manager = HealthCheckManager()

        def critical_check():
            return {'status': 'healthy', 'message': 'OK'}

        def degraded_check():
            return {'status': 'degraded', 'message': 'High latency'}

        manager.register_check('critical', critical_check, critical=True)
        manager.register_check('non_critical', degraded_check, critical=False)

        result = manager.run_all_checks()

        assert result['status'] == 'degraded'
        assert result['checks']['critical']['status'] == 'healthy'
        assert result['checks']['non_critical']['status'] == 'degraded'

    def test_unhealthy_state_with_critical_failure(self):
        """Test system reports unhealthy when critical check fails."""
        manager = HealthCheckManager()

        def critical_failing_check():
            return {'status': 'error', 'message': 'Database down'}

        def healthy_check():
            return {'status': 'healthy', 'message': 'OK'}

        manager.register_check('critical_fail', critical_failing_check, critical=True)
        manager.register_check('healthy', healthy_check, critical=False)

        result = manager.run_all_checks()

        assert result['status'] == 'unhealthy'


@pytest.mark.django_db
class TestHealthCheckEndpoints:
    """Integration tests for health check HTTP endpoints."""

    def test_health_check_endpoint_healthy(self, client):
        """Test /health/ endpoint with healthy status."""
        with patch('apps.core.health_checks.health_service.run_all_checks') as mock_run:
            mock_run.return_value = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'uptime_seconds': 3600,
                'checks': {},
                'summary': {'total_checks': 5, 'healthy': 5},
            }

            response = client.get('/health/')

            assert response.status_code == 200
            data = json.loads(response.content)
            assert data['status'] == 'healthy'

    def test_health_check_endpoint_unhealthy(self, client):
        """Test /health/ endpoint with unhealthy status."""
        with patch('apps.core.health_checks.health_service.run_all_checks') as mock_run:
            mock_run.return_value = {
                'status': 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'uptime_seconds': 3600,
                'checks': {},
                'summary': {'total_checks': 5, 'healthy': 3, 'errors': 2},
            }

            response = client.get('/health/')

            assert response.status_code == 503
            data = json.loads(response.content)
            assert data['status'] == 'unhealthy'

    def test_readiness_check_endpoint_ready(self, client):
        """Test /ready/ endpoint when application is ready."""
        with patch('apps.core.health_checks.health_service.run_critical_checks_only') as mock_run:
            mock_run.return_value = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'checks': {},
            }

            response = client.get('/ready/')

            assert response.status_code == 200
            data = json.loads(response.content)
            assert data['status'] == 'ready'

    def test_readiness_check_endpoint_not_ready(self, client):
        """Test /ready/ endpoint when application is not ready."""
        with patch('apps.core.health_checks.health_service.run_critical_checks_only') as mock_run:
            mock_run.return_value = {
                'status': 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'checks': {},
            }

            response = client.get('/ready/')

            assert response.status_code == 503
            data = json.loads(response.content)
            assert data['status'] == 'not_ready'

    def test_liveness_check_endpoint(self, client):
        """Test /alive/ endpoint for process liveness."""
        response = client.get('/alive/')

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['status'] == 'alive'
        assert 'uptime_seconds' in data

    def test_detailed_health_check_endpoint(self, client):
        """Test /health/detailed/ endpoint with system info."""
        with patch('apps.core.health_checks.health_service.run_all_checks') as mock_run:
            with patch('apps.core.health_checks.health_service.get_service_health_summary') as mock_summary:
                mock_run.return_value = {
                    'status': 'healthy',
                    'timestamp': timezone.now().isoformat(),
                    'uptime_seconds': 3600,
                    'checks': {},
                    'summary': {'total_checks': 20, 'healthy': 20},
                }
                mock_summary.return_value = {
                    'total_services': 5,
                    'services': [],
                }

                response = client.get('/health/detailed/')

                assert response.status_code == 200
                data = json.loads(response.content)
                assert 'system_info' in data
                assert 'service_availability' in data


@pytest.mark.django_db
class TestHealthMonitoringModels:
    """Test suite for health monitoring models."""

    def test_health_check_log_creation(self):
        """Test creating health check log entry."""
        log = HealthCheckLog.objects.create(
            check_name='test_check',
            status='healthy',
            message='Test successful',
            duration_ms=50.5,
        )

        assert log.pk is not None
        assert log.check_name == 'test_check'
        assert log.status == 'healthy'

    def test_health_check_log_query_method(self):
        """Test HealthCheckLog.log_check class method."""
        result = {
            'status': 'healthy',
            'message': 'OK',
            'details': {'version': '1.0'},
            'duration_ms': 25.0,
        }

        log = HealthCheckLog.log_check('test_check', result)

        assert log.check_name == 'test_check'
        assert log.status == 'healthy'
        assert log.details == {'version': '1.0'}

    def test_service_availability_creation(self):
        """Test creating service availability record."""
        service = ServiceAvailability.objects.create(
            service_name='database'
        )

        assert service.pk is not None
        assert service.total_checks == 0
        assert service.uptime_percentage == 100.0

    def test_service_availability_record_check(self):
        """Test recording health check results."""
        service = ServiceAvailability.objects.create(
            service_name='database'
        )

        service.record_check('healthy')
        service.record_check('healthy')
        service.record_check('error')

        assert service.total_checks == 3
        assert service.successful_checks == 2
        assert service.failed_checks == 1
        assert service.uptime_percentage == pytest.approx(66.67, rel=0.1)


@pytest.mark.django_db
class TestDegradedStateScenarios:
    """Test various degraded state scenarios."""

    def test_non_critical_service_failure_degraded_state(self):
        """Test non-critical service failure results in degraded state."""
        manager = HealthCheckManager()

        manager.register_check(
            'critical_db', lambda: {'status': 'healthy'}, critical=True
        )
        manager.register_check(
            'optional_cache', lambda: {'status': 'error', 'message': 'Cache down'}, critical=False
        )

        result = manager.run_all_checks()

        assert result['status'] == 'degraded'
        assert result['summary']['healthy'] == 1
        assert result['summary']['errors'] == 1

    def test_all_critical_checks_pass_non_critical_fail(self):
        """Test system is operational when only non-critical checks fail."""
        manager = HealthCheckManager()

        manager.register_check('db', lambda: {'status': 'healthy'}, critical=True)
        manager.register_check('redis', lambda: {'status': 'healthy'}, critical=True)
        manager.register_check('mqtt', lambda: {'status': 'error'}, critical=False)
        manager.register_check('email', lambda: {'status': 'error'}, critical=False)

        result = manager.run_all_checks()

        assert result['status'] == 'degraded'
        assert result['summary']['healthy'] == 2
        assert result['summary']['errors'] == 2

    def test_mixed_statuses_prioritizes_critical(self):
        """Test that critical check failures override degraded state."""
        manager = HealthCheckManager()

        manager.register_check('db', lambda: {'status': 'error'}, critical=True)
        manager.register_check('cache', lambda: {'status': 'degraded'}, critical=False)

        result = manager.run_all_checks()

        assert result['status'] == 'unhealthy'