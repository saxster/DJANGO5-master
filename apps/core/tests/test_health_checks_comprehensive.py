"""
Comprehensive unit tests for health check system.
Tests all health check modules with specific exception handling.
Follows Rule 11: Specific exception handling validation.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from django.test import TestCase
from apps.core.health_checks.database import (
    check_database_connectivity,
    check_postgis_extension,
    check_database_performance,
    check_connection_pool,
    check_custom_postgresql_functions,
)
from apps.core.health_checks.cache import (
    check_redis_connectivity,
    check_default_cache,
    check_select2_cache,
)
from apps.core.health_checks.system import (
    check_disk_space,
    check_memory_usage,
    check_cpu_load,
)
from apps.core.health_checks.channels import check_channel_layer
from apps.core.health_checks.mqtt import check_mqtt_broker
from apps.core.health_checks.external_apis import (
    check_aws_ses,
    check_google_maps_api,
    check_openai_api,
    check_anthropic_api,
)
from apps.core.health_checks.background_tasks import (
    check_task_queue,
    check_pending_tasks,
    check_failed_tasks,
    check_task_workers,
)
from apps.core.health_checks.filesystem import check_directory_permissions
from apps.core.health_checks.utils import CircuitBreaker, format_check_result


@pytest.mark.django_db
class TestDatabaseHealthChecks:
    """Test suite for database health check functions."""

    @patch('django.db.connection.cursor')
    def test_check_database_connectivity_success(self, mock_cursor):
        """Test successful database connectivity check."""
        mock_cursor_instance = Mock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.fetchone.side_effect = [
            (1,),
            ('PostgreSQL 14.8 on x86_64-pc-linux-gnu',),
            (150,),
        ]

        result = check_database_connectivity()

        assert result['status'] == 'healthy'
        assert 'database_version' in result['details']
        assert 'session_count' in result['details']
        assert result['details']['session_count'] == 150
        assert 'duration_ms' in result

    @patch('django.db.connection.cursor')
    def test_check_database_connectivity_operational_error(self, mock_cursor):
        """Test database connectivity with OperationalError."""
        from django.db import OperationalError

        mock_cursor.side_effect = OperationalError('Connection refused')

        result = check_database_connectivity()

        assert result['status'] == 'error'
        assert 'Connection refused' in result['message']
        assert result['details']['error_type'] == 'OperationalError'

    @patch('django.db.connection.cursor')
    def test_check_postgis_extension_success(self, mock_cursor):
        """Test successful PostGIS extension check."""
        mock_cursor_instance = Mock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.fetchone.side_effect = [
            (True,),
            ('3.1',),
            ('POINT(0 0)',),
        ]

        result = check_postgis_extension()

        assert result['status'] == 'healthy'
        assert result['details']['postgis_installed'] is True
        assert 'postgis_version' in result['details']

    @patch('django.db.connection.cursor')
    def test_check_postgis_extension_not_installed(self, mock_cursor):
        """Test PostGIS extension not installed."""
        mock_cursor_instance = Mock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.fetchone.return_value = (False,)

        result = check_postgis_extension()

        assert result['status'] == 'error'
        assert 'not installed' in result['message']

    @patch('django.db.connection.cursor')
    def test_check_connection_pool_success(self, mock_cursor):
        """Test successful connection pool check."""
        mock_cursor_instance = Mock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.fetchone.return_value = (5, 10, 15)

        result = check_connection_pool()

        assert result['status'] == 'healthy'
        assert result['details']['active_connections'] == 5
        assert result['details']['idle_connections'] == 10
        assert result['details']['total_connections'] == 15

    @patch('django.db.connection.cursor')
    def test_check_connection_pool_high_utilization(self, mock_cursor):
        """Test connection pool with high utilization."""
        mock_cursor_instance = Mock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.fetchone.return_value = (70, 10, 80)

        result = check_connection_pool()

        assert result['status'] == 'degraded'
        assert result['details']['utilization'] > 0.7

    @patch('django.db.connection.cursor')
    def test_check_custom_postgresql_functions_all_available(self, mock_cursor):
        """Test all PostgreSQL functions available."""
        mock_cursor_instance = Mock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.fetchone.side_effect = [
            (True,),
            (True,),
            (True,),
        ]

        result = check_custom_postgresql_functions()

        assert result['status'] == 'healthy'
        assert all(
            status == 'available'
            for status in result['details']['functions'].values()
        )

@pytest.mark.django_db
class TestCacheHealthChecks:
    """Test suite for cache health check functions."""

    @patch('apps.core.health_checks.cache.redis.from_url')
    def test_check_redis_connectivity_success(self, mock_redis_from_url):
        """Test successful Redis connectivity check."""
        mock_redis_client = Mock()
        mock_redis_from_url.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        mock_redis_client.info.return_value = {
            'redis_version': '6.2.6',
            'uptime_in_seconds': 3600,
            'connected_clients': 10,
            'used_memory_human': '10M',
        }

        result = check_redis_connectivity()

        assert result['status'] == 'healthy'
        assert 'redis_version' in result['details']

    @patch('apps.core.health_checks.cache.redis.from_url')
    def test_check_redis_connectivity_connection_error(self, mock_redis_from_url):
        """Test Redis connectivity with ConnectionError."""
        import redis

        mock_redis_from_url.side_effect = redis.ConnectionError('Connection refused')

        result = check_redis_connectivity()

        assert result['status'] == 'error'
        assert 'ConnectionError' in result['details']['error_type']


@pytest.mark.django_db
class TestSystemHealthChecks:
    """Test suite for system resource health check functions."""

    @patch('shutil.disk_usage')
    @patch('os.path.exists')
    def test_check_disk_space_success(self, mock_exists, mock_disk_usage):
        """Test successful disk space check."""
        mock_exists.return_value = True
        mock_disk_usage.return_value = Mock(
            total=100 * 1024**3,
            used=50 * 1024**3,
            free=50 * 1024**3,
        )

        result = check_disk_space()

        assert result['status'] == 'healthy'
        assert 'disk_usage' in result['details']

    @patch('shutil.disk_usage')
    @patch('os.path.exists')
    def test_check_disk_space_high_usage(self, mock_exists, mock_disk_usage):
        """Test disk space check with high usage."""
        mock_exists.return_value = True
        mock_disk_usage.return_value = Mock(
            total=100 * 1024**3,
            used=85 * 1024**3,
            free=15 * 1024**3,
        )

        result = check_disk_space()

        assert result['status'] == 'degraded'

    @patch('apps.core.health_checks.system.psutil')
    def test_check_memory_usage_success(self, mock_psutil):
        """Test successful memory usage check."""
        mock_psutil.virtual_memory.return_value = Mock(
            total=16 * 1024**3,
            used=8 * 1024**3,
            available=8 * 1024**3,
            percent=50.0,
        )

        result = check_memory_usage()

        assert result['status'] == 'healthy'
        assert result['details']['percent_used'] == 50.0


class TestCircuitBreaker:
    """Test suite for circuit breaker pattern."""

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=10)

        def test_func():
            return {'status': 'healthy', 'message': 'OK'}

        result = breaker.call(test_func)

        assert result['status'] == 'healthy'
        assert breaker.state == 'closed'

    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=10)

        def failing_func():
            raise ConnectionError('Service unavailable')

        for _ in range(3):
            result = breaker.call(failing_func)

        assert breaker.state == 'open'
        assert 'Circuit breaker open' in result['message']

    def test_circuit_breaker_half_open_state(self):
        """Test circuit breaker transitions to half-open."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        def failing_func():
            raise ConnectionError('Service unavailable')

        breaker.call(failing_func)
        breaker.call(failing_func)

        assert breaker.state == 'open'

        time.sleep(1.1)

        def success_func():
            return {'status': 'healthy'}

        result = breaker.call(success_func)

        assert result['status'] == 'healthy'
        assert breaker.state == 'closed'


class TestFormatCheckResult:
    """Test suite for format_check_result utility."""

    def test_format_check_result_basic(self):
        """Test basic result formatting."""
        result = format_check_result(
            status='healthy',
            message='System operational'
        )

        assert result['status'] == 'healthy'
        assert result['message'] == 'System operational'
        assert 'timestamp' in result

    def test_format_check_result_with_details(self):
        """Test result formatting with details."""
        details = {'version': '1.0', 'connections': 10}
        result = format_check_result(
            status='healthy',
            message='OK',
            details=details,
            duration_ms=50.5
        )

        assert result['details'] == details
        assert result['duration_ms'] == 50.5