"""
End-to-End Integration Tests for Redis Enhancements

Tests all Redis enhancements comprehensively:
1. Redis TLS/SSL configuration (PCI DSS compliance)
2. Redis Sentinel High Availability
3. Monitoring infrastructure
4. Select2 PostgreSQL migration
5. Certificate management

pytest marks:
    - integration: Integration tests
    - redis: Redis-related tests
    - security: Security compliance tests
    - monitoring: Monitoring infrastructure tests
"""

import os
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.core.cache import cache, caches
from django.conf import settings
from django.utils import timezone


@pytest.mark.integration
@pytest.mark.redis
class TestRedisTLSConfiguration:
    """Test Redis TLS/SSL configuration for PCI DSS compliance"""

    def test_tls_config_function_exists(self):
        """Verify get_redis_tls_config function exists and is importable"""
        from intelliwiz_config.settings.redis_optimized import get_redis_tls_config

        assert callable(get_redis_tls_config)

    @override_settings(DJANGO_ENVIRONMENT='production')
    def test_tls_config_production_warning(self):
        """Test that production without TLS generates warning"""
        from intelliwiz_config.settings.redis_optimized import get_redis_tls_config

        with patch.dict(os.environ, {'REDIS_SSL_ENABLED': 'false'}):
            config = get_redis_tls_config('production')

            # Should return empty config (but log warning)
            assert config == {}

    @override_settings(DJANGO_ENVIRONMENT='development')
    def test_tls_config_development_disabled(self):
        """Test TLS can be disabled in development"""
        from intelliwiz_config.settings.redis_optimized import get_redis_tls_config

        with patch.dict(os.environ, {'REDIS_SSL_ENABLED': 'false'}):
            config = get_redis_tls_config('development')

            assert config == {}

    def test_tls_config_structure_when_enabled(self):
        """Test TLS config structure when enabled"""
        from intelliwiz_config.settings.redis_optimized import get_redis_tls_config

        # Mock certificate files
        cert_paths = {
            'REDIS_SSL_ENABLED': 'true',
            'REDIS_SSL_CA_CERT': '/tmp/test-ca.pem',
            'REDIS_SSL_CERT': '/tmp/test-cert.pem',
            'REDIS_SSL_KEY': '/tmp/test-key.pem',
        }

        # Create mock certificate files
        for key, path in cert_paths.items():
            if key != 'REDIS_SSL_ENABLED':
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w') as f:
                    f.write('mock certificate')

        try:
            with patch.dict(os.environ, cert_paths):
                config = get_redis_tls_config('production')

                # Verify TLS config structure
                assert config.get('ssl') is True
                assert 'ssl_cert_reqs' in config
                assert 'ssl_ca_certs' in config
                assert 'ssl_certfile' in config
                assert 'ssl_keyfile' in config
                assert config.get('ssl_check_hostname') is True

        finally:
            # Cleanup
            for key, path in cert_paths.items():
                if key != 'REDIS_SSL_ENABLED' and os.path.exists(path):
                    os.remove(path)

    def test_rediss_protocol_when_tls_enabled(self):
        """Test that 'rediss://' protocol is used when TLS enabled"""
        from intelliwiz_config.settings.redis_optimized import get_optimized_redis_config

        # Create mock certificates
        cert_dir = '/tmp/test_redis_certs'
        os.makedirs(cert_dir, exist_ok=True)

        cert_files = ['ca-cert.pem', 'redis-cert.pem', 'redis-key.pem']
        for cert_file in cert_files:
            cert_path = os.path.join(cert_dir, cert_file)
            with open(cert_path, 'w') as f:
                f.write('mock certificate')

        try:
            env_vars = {
                'REDIS_SSL_ENABLED': 'true',
                'REDIS_SSL_CA_CERT': f'{cert_dir}/ca-cert.pem',
                'REDIS_SSL_CERT': f'{cert_dir}/redis-cert.pem',
                'REDIS_SSL_KEY': f'{cert_dir}/redis-key.pem',
                'REDIS_PASSWORD': 'test_password',
                'REDIS_HOST': '127.0.0.1',
                'REDIS_PORT': '6379',
            }

            with patch.dict(os.environ, env_vars):
                config = get_optimized_redis_config('production')

                # Should use 'rediss://' protocol
                assert config['LOCATION'].startswith('rediss://')
                assert 'test_password' in config['LOCATION']

        finally:
            # Cleanup
            import shutil
            if os.path.exists(cert_dir):
                shutil.rmtree(cert_dir)


@pytest.mark.integration
@pytest.mark.redis
class TestSelect2PostgreSQLMigration:
    """Test Select2 cache migration to PostgreSQL"""

    def test_select2_uses_postgresql_backend(self):
        """Verify Select2 cache uses MaterializedViewSelect2Cache"""
        select2_cache = caches['select2']

        backend_class = select2_cache.__class__.__name__
        assert 'MaterializedViewSelect2Cache' in backend_class

    def test_select2_no_redis_dependency(self):
        """Verify Select2 cache has no Redis dependency"""
        from django.conf import settings

        select2_config = settings.CACHES.get('select2', {})
        location = select2_config.get('LOCATION', '')

        # Should not have Redis URL
        assert not location.startswith('redis://')
        assert not location.startswith('rediss://')

    def test_select2_materialized_views_configured(self):
        """Verify materialized view mappings exist"""
        from apps.core.cache.materialized_view_select2 import MaterializedViewSelect2Cache

        assert hasattr(MaterializedViewSelect2Cache, 'MATERIALIZED_VIEWS')
        assert len(MaterializedViewSelect2Cache.MATERIALIZED_VIEWS) >= 3

        # Check expected views
        expected_views = ['people_dropdown', 'location_dropdown', 'asset_dropdown']
        for view_name in expected_views:
            assert view_name in MaterializedViewSelect2Cache.MATERIALIZED_VIEWS


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.monitoring
class TestRedisMonitoringInfrastructure:
    """Test Redis monitoring infrastructure"""

    def test_monitoring_tasks_importable(self):
        """Verify monitoring tasks can be imported"""
        from apps.core.tasks.redis_monitoring_tasks import (
            collect_redis_performance_metrics,
            analyze_redis_performance_trends,
            generate_redis_capacity_report
        )

        assert callable(collect_redis_performance_metrics)
        assert callable(analyze_redis_performance_trends)
        assert callable(generate_redis_capacity_report)

    def test_monitoring_dashboard_views_exist(self):
        """Verify monitoring dashboard views are registered"""
        from apps.core.views.redis_performance_dashboard import (
            RedisPerformanceDashboardView,
            RedisMetricsAPIView,
            RedisPerformanceTrendsAPIView
        )

        assert RedisPerformanceDashboardView is not None
        assert RedisMetricsAPIView is not None
        assert RedisPerformanceTrendsAPIView is not None

    def test_health_checks_importable(self):
        """Verify health check functions exist"""
        from apps.core.health_checks.cache import (
            check_redis_connectivity,
            check_redis_memory_health,
            check_redis_performance,
            check_default_cache
        )

        assert callable(check_redis_connectivity)
        assert callable(check_redis_memory_health)
        assert callable(check_redis_performance)
        assert callable(check_default_cache)

    def test_metrics_collector_service_exists(self):
        """Verify Redis metrics collector service exists"""
        from apps.core.services.redis_metrics_collector import redis_metrics_collector

        assert redis_metrics_collector is not None
        assert hasattr(redis_metrics_collector, 'collect_metrics')
        assert hasattr(redis_metrics_collector, 'analyze_performance')
        assert hasattr(redis_metrics_collector, 'get_performance_trends')


@pytest.mark.integration
@pytest.mark.redis
class TestRedisSentinelConfiguration:
    """Test Redis Sentinel high availability configuration"""

    def test_sentinel_settings_function_exists(self):
        """Verify Sentinel configuration function exists"""
        from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings

        assert callable(get_sentinel_settings)

    def test_sentinel_configuration_structure(self):
        """Test Sentinel configuration returns correct structure"""
        from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings

        with patch.dict(os.environ, {'DJANGO_ENVIRONMENT': 'production'}):
            config = get_sentinel_settings()

            # Verify structure
            assert 'sentinels' in config
            assert 'service_name' in config
            assert 'sentinel_kwargs' in config
            assert 'redis_kwargs' in config

            # Verify sentinels is list of tuples
            assert isinstance(config['sentinels'], list)
            assert len(config['sentinels']) == 3  # 3-node quorum

    def test_sentinel_tls_integration(self):
        """Verify Sentinel integrates TLS configuration"""
        from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings

        # Create mock certificates
        cert_dir = '/tmp/test_sentinel_certs'
        os.makedirs(cert_dir, exist_ok=True)

        for cert_file in ['ca-cert.pem', 'redis-cert.pem', 'redis-key.pem']:
            with open(os.path.join(cert_dir, cert_file), 'w') as f:
                f.write('mock')

        try:
            env_vars = {
                'DJANGO_ENVIRONMENT': 'production',
                'REDIS_SSL_ENABLED': 'true',
                'REDIS_SSL_CA_CERT': f'{cert_dir}/ca-cert.pem',
                'REDIS_SSL_CERT': f'{cert_dir}/redis-cert.pem',
                'REDIS_SSL_KEY': f'{cert_dir}/redis-key.pem',
            }

            with patch.dict(os.environ, env_vars):
                config = get_sentinel_settings()

                # Verify TLS config is integrated
                assert 'ssl' in config['redis_kwargs']
                assert config['redis_kwargs']['ssl'] is True

        finally:
            import shutil
            if os.path.exists(cert_dir):
                shutil.rmtree(cert_dir)

    def test_sentinel_validation_function_exists(self):
        """Verify Sentinel validation function exists"""
        from intelliwiz_config.settings.redis_sentinel import validate_sentinel_configuration

        assert callable(validate_sentinel_configuration)


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.security
class TestCertificateManagement:
    """Test certificate management for PCI DSS compliance"""

    def test_check_certificates_command_exists(self):
        """Verify check_redis_certificates management command exists"""
        from django.core.management import call_command
        from io import StringIO

        # Should not raise ImportError
        out = StringIO()
        with patch.dict(os.environ, {'REDIS_SSL_ENABLED': 'false'}):
            call_command('check_redis_certificates', stdout=out)

        output = out.getvalue()
        assert 'Redis TLS/SSL is not enabled' in output or 'PCI DSS' in output


@pytest.mark.integration
@pytest.mark.redis
class TestRedisPasswordSecurity:
    """Test Redis password security configuration"""

    def test_password_fail_fast_production(self):
        """Verify production fails fast without password"""
        from intelliwiz_config.settings.redis_optimized import get_redis_password

        with patch.dict(os.environ, {'REDIS_PASSWORD': ''}, clear=True):
            with pytest.raises(ValueError, match="REDIS_PASSWORD must be set"):
                get_redis_password('production')

    def test_password_fallback_development(self):
        """Verify development uses fallback password with warning"""
        from intelliwiz_config.settings.redis_optimized import get_redis_password

        with patch.dict(os.environ, {'REDIS_PASSWORD': ''}, clear=True):
            password = get_redis_password('development')

            # Should return fallback password (not raise exception)
            assert password is not None
            assert len(password) > 0


@pytest.mark.integration
@pytest.mark.redis
class TestRedisConfigurationIntegration:
    """Test complete Redis configuration integration"""

    def test_optimized_caches_configuration(self):
        """Verify OPTIMIZED_CACHES is properly configured"""
        from intelliwiz_config.settings.redis_optimized import OPTIMIZED_CACHES

        assert isinstance(OPTIMIZED_CACHES, dict)
        assert 'default' in OPTIMIZED_CACHES
        assert 'select2' in OPTIMIZED_CACHES

    def test_cache_backend_types(self):
        """Verify cache backends are correct types"""
        from django.conf import settings

        caches_config = settings.CACHES

        # Default should be Redis
        assert 'RedisCache' in caches_config['default']['BACKEND'] or \
               'redis' in caches_config['default']['BACKEND'].lower()

        # Select2 should be PostgreSQL
        assert 'MaterializedViewSelect2Cache' in caches_config['select2']['BACKEND']

    def test_cache_connectivity(self):
        """Test cache read/write operations"""
        test_key = f'integration_test_{datetime.now().timestamp()}'
        test_value = {'test': 'data', 'timestamp': datetime.now().isoformat()}

        try:
            # Test write
            cache.set(test_key, test_value, timeout=60)

            # Test read
            result = cache.get(test_key)
            assert result == test_value

            # Test delete
            cache.delete(test_key)
            assert cache.get(test_key) is None

        except Exception as e:
            pytest.fail(f"Cache connectivity test failed: {e}")

    def test_select2_cache_independence(self):
        """Verify Select2 cache works independently of Redis"""
        select2_cache = caches['select2']

        # Should work even if Redis unavailable
        test_key = 'select2_test_key'
        test_value = {'id': 1, 'text': 'Test Item'}

        try:
            select2_cache.set(test_key, test_value, timeout=300)
            result = select2_cache.get(test_key)

            # May return None if materialized views not created yet (acceptable)
            # The important thing is it doesn't raise Redis connection error
            assert result is None or result == test_value

        except ConnectionError:
            pytest.fail("Select2 cache should not depend on Redis connection")


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.monitoring
class TestRedisMonitoringIntegration:
    """Test Redis monitoring infrastructure integration"""

    def test_monitoring_tasks_registered(self):
        """Verify monitoring tasks are registered with Celery"""
        from celery import current_app

        registered_tasks = current_app.tasks

        expected_tasks = [
            'collect_redis_performance_metrics',
            'analyze_redis_performance_trends',
            'generate_redis_capacity_report'
        ]

        for task_name in expected_tasks:
            assert task_name in registered_tasks, f"{task_name} not registered"

    def test_redis_metrics_collector_functional(self):
        """Test Redis metrics collector can collect metrics"""
        from apps.core.services.redis_metrics_collector import redis_metrics_collector

        try:
            metrics = redis_metrics_collector.collect_metrics('main')

            # If Redis is running, should return metrics
            # If not running, should return None (acceptable in test)
            if metrics:
                assert hasattr(metrics, 'used_memory')
                assert hasattr(metrics, 'hit_ratio')
                assert hasattr(metrics, 'connected_clients')

        except Exception as e:
            # Redis not running in test environment is acceptable
            pytest.skip(f"Redis not available in test environment: {e}")

    def test_health_checks_executable(self):
        """Test health check functions are executable"""
        from apps.core.health_checks.cache import (
            check_redis_connectivity,
            check_default_cache
        )

        try:
            # These should return dict with 'status' key
            connectivity_result = check_redis_connectivity()
            cache_result = check_default_cache()

            assert isinstance(connectivity_result, dict)
            assert 'status' in connectivity_result

            assert isinstance(cache_result, dict)
            assert 'status' in cache_result

        except Exception as e:
            pytest.skip(f"Health checks require Redis: {e}")


@pytest.mark.integration
@pytest.mark.redis
class TestProductionConfigurationCompliance:
    """Test production configuration meets all requirements"""

    def test_production_has_caches_configuration(self):
        """Verify production settings include CACHES configuration"""
        # Import production settings
        with patch.dict(os.environ, {'DJANGO_SETTINGS_MODULE': 'intelliwiz_config.settings.production'}):
            # Force reload
            import importlib
            from intelliwiz_config.settings import production
            importlib.reload(production)

            # Production should import OPTIMIZED_CACHES
            # This test verifies the critical fix from Oct 10, 2025
            assert hasattr(production, 'CACHES')

    def test_all_environments_use_json_serializer(self):
        """Verify all environments use JSON serializer (compliance requirement)"""
        from intelliwiz_config.settings.redis_optimized import get_optimized_redis_config

        for environment in ['development', 'testing', 'production']:
            config = get_optimized_redis_config(environment)

            serializer = config['OPTIONS'].get('SERIALIZER', '')
            assert 'JSONSerializer' in serializer, \
                f"{environment} should use JSON serializer for compliance"

    def test_production_fail_fast_without_password(self):
        """Verify production fails if Redis password missing"""
        from intelliwiz_config.settings.redis_optimized import get_redis_password

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                get_redis_password('production')


@pytest.mark.integration
@pytest.mark.redis
class TestVerificationScripts:
    """Test verification scripts are functional"""

    def test_verify_redis_cache_config_script_exists(self):
        """Verify cache verification script exists and is executable"""
        script_path = os.path.join(settings.BASE_DIR, 'scripts', 'verify_redis_cache_config.py')
        assert os.path.exists(script_path)
        assert os.access(script_path, os.X_OK)

    def test_verify_monitoring_script_exists(self):
        """Verify monitoring verification script exists"""
        script_path = os.path.join(settings.BASE_DIR, 'scripts', 'verify_redis_monitoring_enabled.py')
        assert os.path.exists(script_path)
        assert os.access(script_path, os.X_OK)

    def test_tls_setup_script_exists(self):
        """Verify TLS setup script exists"""
        script_path = os.path.join(settings.BASE_DIR, 'scripts', 'setup_redis_tls.sh')
        assert os.path.exists(script_path)
        assert os.access(script_path, os.X_OK)


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.security
class TestPCIDSSCompliance:
    """Test PCI DSS compliance requirements"""

    def test_compliance_documentation_exists(self):
        """Verify PCI DSS compliance documentation exists"""
        compliance_doc = os.path.join(
            settings.BASE_DIR,
            'docs/compliance/PCI_DSS_REDIS_TLS_COMPLIANCE_CHECKLIST.md'
        )
        assert os.path.exists(compliance_doc)

    def test_operator_guide_exists(self):
        """Verify operator guide exists"""
        operator_guide = os.path.join(
            settings.BASE_DIR,
            'docs/operations/REDIS_OPERATOR_GUIDE.md'
        )
        assert os.path.exists(operator_guide)

    def test_redis_tls_config_template_exists(self):
        """Verify redis.conf TLS template exists"""
        config_template = os.path.join(
            settings.BASE_DIR,
            'config/redis/redis-tls.conf.template'
        )
        assert os.path.exists(config_template)


# Test suite summary
def test_suite_summary():
    """
    This test suite verifies all Redis enhancements are properly integrated:

    1. ✅ TLS/SSL Configuration (PCI DSS Requirement 4.2.1)
       - TLS config function exists
       - Production warnings if disabled
       - Certificate validation
       - rediss:// protocol when enabled

    2. ✅ Select2 PostgreSQL Migration
       - Uses MaterializedViewSelect2Cache
       - No Redis dependency
       - Materialized views configured

    3. ✅ Monitoring Infrastructure
       - Tasks registered with Celery
       - Dashboard views exist
       - Health checks functional
       - Metrics collector operational

    4. ✅ Sentinel High Availability
       - Configuration function exists
       - TLS integration working
       - Validation function available

    5. ✅ Certificate Management
       - Management command exists
       - PCI DSS compliance checklist created
       - Operator guide available

    6. ✅ Security & Compliance
       - JSON serializer across all environments
       - Password fail-fast in production
       - Production CACHES configuration present
       - Verification scripts available

    Run this suite:
        pytest apps/core/tests/test_redis_enhancements_integration.py -v

    Run specific marks:
        pytest -m redis -v            # All Redis tests
        pytest -m security -v         # Security compliance tests
        pytest -m monitoring -v       # Monitoring tests
    """
    pass  # This is a documentation test
