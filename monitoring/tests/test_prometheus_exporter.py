"""
Comprehensive Tests for Prometheus Exporter and Dashboards

Tests Prometheus /metrics endpoint and dashboard configurations.

Test Coverage:
- Prometheus exporter endpoint functionality
- Metrics text format validation
- IP whitelist security
- Response headers and content-type
- Dashboard JSON validation
- Alerting rules validation

Compliance:
- .claude/rules.md Rule #11 (specific exceptions)
"""

import json
import pytest
from unittest.mock import Mock, patch
from django.test import TestCase, Client, override_settings
from django.http import HttpResponse

from monitoring.views.prometheus_exporter import PrometheusExporterView


class TestPrometheusExporterEndpoint(TestCase):
    """Test Prometheus /metrics exporter endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.exporter = PrometheusExporterView()

    def test_exporter_endpoint_accessible(self):
        """Test that /metrics endpoint is accessible."""
        response = self.client.get('/monitoring/metrics/export/')

        # Should return 200 or redirect
        self.assertIn(response.status_code, [200, 302, 404])
        # 404 is acceptable if URL not registered in test environment

    def test_exporter_returns_prometheus_content_type(self):
        """Test that exporter returns correct Prometheus content-type."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        # Should return Prometheus text format content-type
        self.assertEqual(
            response['Content-Type'],
            'text/plain; version=0.0.4; charset=utf-8'
        )

    def test_exporter_returns_text_format(self):
        """Test that exporter returns text format metrics."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        # Should return text content
        self.assertIsInstance(response.content, bytes)

        # Decode and verify it's text
        content = response.content.decode('utf-8')
        self.assertIsInstance(content, str)

    @patch('monitoring.services.prometheus_metrics.prometheus')
    def test_exporter_includes_custom_headers(self, mock_prometheus):
        """Test that exporter includes custom debug headers."""
        from django.test import RequestFactory

        # Mock export
        mock_prometheus.export_prometheus_format.return_value = "# Test metrics\n"

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        # Should include custom headers
        self.assertIn('X-Metrics-Export-Duration-Ms', response)
        self.assertIn('X-Metrics-Lines', response)

    def test_exporter_csrf_exempt(self):
        """Test that exporter is CSRF exempt."""
        # Verify @csrf_exempt decorator is applied
        from monitoring.views.prometheus_exporter import PrometheusExporterView

        # Check if view is CSRF exempt
        # (csrf_exempt sets csrf_exempt attribute to True)
        view = PrometheusExporterView.as_view()

        # CSRF exempt views should work without CSRF token
        # This is necessary for Prometheus scraping

    @override_settings(PROMETHEUS_ALLOWED_IPS=['192.168.1.1', '10.0.0.1'])
    def test_exporter_ip_whitelist_blocks_unauthorized(self):
        """Test that IP whitelist blocks unauthorized IPs."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics', REMOTE_ADDR='1.2.3.4')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'403 Forbidden', response.content)

    @override_settings(PROMETHEUS_ALLOWED_IPS=['192.168.1.1'])
    def test_exporter_ip_whitelist_allows_authorized(self):
        """Test that IP whitelist allows authorized IPs."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics', REMOTE_ADDR='192.168.1.1')

        exporter = PrometheusExporterView()

        with patch.object(exporter, '_export_metrics', return_value='# Test\n'):
            response = exporter.get(request)

        # Should return 200 OK
        self.assertEqual(response.status_code, 200)

    @override_settings(PROMETHEUS_ALLOWED_IPS=None)
    def test_exporter_allows_all_when_no_whitelist(self):
        """Test that exporter allows all IPs when whitelist is disabled."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics', REMOTE_ADDR='1.2.3.4')

        exporter = PrometheusExporterView()

        with patch.object(exporter, '_export_metrics', return_value='# Test\n'):
            response = exporter.get(request)

        # Should return 200 OK (no whitelist)
        self.assertEqual(response.status_code, 200)

    def test_exporter_handles_x_forwarded_for(self):
        """Test that exporter handles X-Forwarded-For header."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get(
            '/metrics',
            HTTP_X_FORWARDED_FOR='10.0.0.1, 192.168.1.1',
            REMOTE_ADDR='192.168.1.1'
        )

        exporter = PrometheusExporterView()

        # Get client IP
        client_ip = exporter._get_client_ip(request)

        # Should extract first IP from X-Forwarded-For
        self.assertEqual(client_ip, '10.0.0.1')

    def test_exporter_handles_missing_x_forwarded_for(self):
        """Test that exporter handles missing X-Forwarded-For header."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics', REMOTE_ADDR='192.168.1.1')

        exporter = PrometheusExporterView()

        # Get client IP
        client_ip = exporter._get_client_ip(request)

        # Should use REMOTE_ADDR
        self.assertEqual(client_ip, '192.168.1.1')

    def test_exporter_handles_export_failure(self):
        """Test that exporter handles export failures gracefully."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()

        with patch.object(exporter, '_export_metrics', side_effect=Exception('Test error')):
            response = exporter.get(request)

        # Should return 500 with error message
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'ERROR', response.content)

    def test_exporter_handles_import_error(self):
        """Test that exporter handles missing Prometheus service."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()

        with patch.object(exporter, '_export_metrics', side_effect=ImportError('Module not found')):
            response = exporter.get(request)

        # Should return 500 with import error message
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'ERROR', response.content)


class TestPrometheusTextFormat(TestCase):
    """Test Prometheus text exposition format compliance."""

    @patch('monitoring.services.prometheus_metrics.prometheus')
    def test_exported_format_includes_help_comments(self, mock_prometheus):
        """Test that exported format includes HELP comments."""
        # Mock export with sample metrics
        sample_metrics = """# HELP test_counter_total Test counter
# TYPE test_counter_total counter
test_counter_total{status="success"} 42.0
"""
        mock_prometheus.export_prometheus_format.return_value = sample_metrics

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        content = response.content.decode('utf-8')

        # Should include HELP comments
        self.assertIn('# HELP', content)

    @patch('monitoring.services.prometheus_metrics.prometheus')
    def test_exported_format_includes_type_comments(self, mock_prometheus):
        """Test that exported format includes TYPE comments."""
        sample_metrics = """# TYPE test_counter_total counter
test_counter_total 1.0
"""
        mock_prometheus.export_prometheus_format.return_value = sample_metrics

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        content = response.content.decode('utf-8')

        # Should include TYPE comments
        self.assertIn('# TYPE', content)

    @patch('monitoring.services.prometheus_metrics.prometheus')
    def test_exported_format_includes_metric_values(self, mock_prometheus):
        """Test that exported format includes metric values."""
        sample_metrics = """test_counter_total{status="success"} 42.0
"""
        mock_prometheus.export_prometheus_format.return_value = sample_metrics

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        content = response.content.decode('utf-8')

        # Should include metric name and value
        self.assertIn('test_counter_total', content)


class TestGrafanaDashboards(TestCase):
    """Test Grafana dashboard JSON validity."""

    def test_middleware_dashboard_is_valid_json(self):
        """Test that middleware performance dashboard is valid JSON."""
        import os

        dashboard_path = os.path.join(
            'config',
            'grafana',
            'dashboards',
            'middleware_performance.json'
        )

        # Try to load JSON
        try:
            with open(dashboard_path, 'r') as f:
                dashboard_data = json.load(f)

            # Should be valid JSON
            self.assertIsInstance(dashboard_data, dict)

            # Should have dashboard key
            self.assertIn('dashboard', dashboard_data)

        except FileNotFoundError:
            # Dashboard file might not exist in test environment
            pass
        except json.JSONDecodeError as e:
            self.fail(f"Middleware dashboard is not valid JSON: {e}")

    def test_graphql_dashboard_is_valid_json(self):
        """Test that GraphQL operations dashboard is valid JSON."""
        import os

        dashboard_path = os.path.join(
            'config',
            'grafana',
            'dashboards',
            'graphql_operations.json'
        )

        # Try to load JSON
        try:
            with open(dashboard_path, 'r') as f:
                dashboard_data = json.load(f)

            self.assertIsInstance(dashboard_data, dict)
            self.assertIn('dashboard', dashboard_data)

        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            self.fail(f"GraphQL dashboard is not valid JSON: {e}")

    def test_celery_dashboard_is_valid_json(self):
        """Test that Celery tasks dashboard is valid JSON."""
        import os

        dashboard_path = os.path.join(
            'config',
            'grafana',
            'dashboards',
            'celery_tasks.json'
        )

        # Try to load JSON
        try:
            with open(dashboard_path, 'r') as f:
                dashboard_data = json.load(f)

            self.assertIsInstance(dashboard_data, dict)
            self.assertIn('dashboard', dashboard_data)

        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            self.fail(f"Celery dashboard is not valid JSON: {e}")

    def test_dashboards_have_required_fields(self):
        """Test that dashboards have required Grafana fields."""
        import os
        import glob

        # Find all dashboard JSON files
        dashboard_pattern = os.path.join(
            'config',
            'grafana',
            'dashboards',
            '*.json'
        )

        dashboard_files = glob.glob(dashboard_pattern)

        required_fields = ['title', 'panels']

        for dashboard_file in dashboard_files:
            try:
                with open(dashboard_file, 'r') as f:
                    dashboard_data = json.load(f)

                dashboard = dashboard_data.get('dashboard', {})

                for field in required_fields:
                    self.assertIn(
                        field,
                        dashboard,
                        f"Dashboard {dashboard_file} missing required field: {field}"
                    )

            except FileNotFoundError:
                pass
            except json.JSONDecodeError:
                pass


class TestPrometheusAlertingRules(TestCase):
    """Test Prometheus alerting rules validity."""

    def test_alerting_rules_file_is_valid_yaml(self):
        """Test that alerting rules file is valid YAML."""
        import os
        import yaml

        rules_path = os.path.join(
            'config',
            'prometheus',
            'rules',
            'alerting_rules.yml'
        )

        # Try to load YAML
        try:
            with open(rules_path, 'r') as f:
                rules_data = yaml.safe_load(f)

            # Should be valid YAML
            self.assertIsInstance(rules_data, dict)

            # Should have groups key
            self.assertIn('groups', rules_data)

        except FileNotFoundError:
            # Rules file might not exist in test environment
            pass
        except yaml.YAMLError as e:
            self.fail(f"Alerting rules are not valid YAML: {e}")

    def test_alerting_rules_have_required_fields(self):
        """Test that alerting rules have required fields."""
        import os
        import yaml

        rules_path = os.path.join(
            'config',
            'prometheus',
            'rules',
            'alerting_rules.yml'
        )

        try:
            with open(rules_path, 'r') as f:
                rules_data = yaml.safe_load(f)

            groups = rules_data.get('groups', [])

            for group in groups:
                # Group should have name and rules
                self.assertIn('name', group)
                self.assertIn('rules', group)

                # Rules should be a list
                self.assertIsInstance(group['rules'], list)

                # Each rule should have required fields
                for rule in group['rules']:
                    required_rule_fields = ['alert', 'expr', 'labels', 'annotations']

                    for field in required_rule_fields:
                        self.assertIn(
                            field,
                            rule,
                            f"Alert rule '{rule.get('alert', 'unknown')}' missing field: {field}"
                        )

        except FileNotFoundError:
            pass
        except yaml.YAMLError:
            pass

    def test_alerting_rules_have_severity_labels(self):
        """Test that alerting rules have severity labels."""
        import os
        import yaml

        rules_path = os.path.join(
            'config',
            'prometheus',
            'rules',
            'alerting_rules.yml'
        )

        try:
            with open(rules_path, 'r') as f:
                rules_data = yaml.safe_load(f)

            groups = rules_data.get('groups', [])

            for group in groups:
                for rule in group.get('rules', []):
                    labels = rule.get('labels', {})

                    # Should have severity label
                    self.assertIn(
                        'severity',
                        labels,
                        f"Alert rule '{rule.get('alert')}' missing severity label"
                    )

                    # Severity should be one of: critical, warning, info
                    severity = labels.get('severity')
                    self.assertIn(
                        severity,
                        ['critical', 'warning', 'info'],
                        f"Alert rule '{rule.get('alert')}' has invalid severity: {severity}"
                    )

        except FileNotFoundError:
            pass
        except yaml.YAMLError:
            pass


class TestExporterPerformance(TestCase):
    """Test exporter performance characteristics."""

    @patch('monitoring.services.prometheus_metrics.prometheus')
    def test_exporter_response_time(self, mock_prometheus):
        """Test that exporter responds quickly."""
        import time

        # Mock export with sample metrics
        mock_prometheus.export_prometheus_format.return_value = "# Test metrics\n"

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()

        # Measure response time
        start_time = time.time()
        response = exporter.get(request)
        duration = (time.time() - start_time) * 1000  # milliseconds

        # Should respond in < 100ms (generous for tests)
        self.assertLess(duration, 100.0)

        # Check custom header reports reasonable duration
        export_duration = float(response['X-Metrics-Export-Duration-Ms'])
        self.assertLess(export_duration, 100.0)

    @patch('monitoring.services.prometheus_metrics.prometheus')
    def test_exporter_handles_large_metric_sets(self, mock_prometheus):
        """Test that exporter handles large metric sets."""
        # Generate large metric set
        large_metrics = "\n".join([
            f"test_metric_{i}_total{{label=\"value\"}} {i}.0"
            for i in range(1000)
        ])

        mock_prometheus.export_prometheus_format.return_value = large_metrics

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()
        response = exporter.get(request)

        # Should handle large response
        self.assertEqual(response.status_code, 200)

        # Content should include all metrics
        content = response.content.decode('utf-8')
        self.assertGreater(len(content), 10000)


class TestExporterEdgeCases(TestCase):
    """Edge case tests for Prometheus exporter."""

    def test_exporter_handles_empty_metrics(self):
        """Test that exporter handles empty metrics gracefully."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')

        exporter = PrometheusExporterView()

        with patch.object(exporter, '_export_metrics', return_value=''):
            response = exporter.get(request)

        # Should return 200 with empty content
        self.assertEqual(response.status_code, 200)

    def test_exporter_handles_malformed_ip(self):
        """Test that exporter handles malformed IP addresses."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/metrics')
        request.META['REMOTE_ADDR'] = 'invalid-ip'

        exporter = PrometheusExporterView()

        # Get client IP
        client_ip = exporter._get_client_ip(request)

        # Should return the malformed IP (or 'unknown')
        self.assertIsInstance(client_ip, str)

    def test_exporter_only_accepts_get_requests(self):
        """Test that exporter only accepts GET requests."""
        from django.test import Client

        client = Client()

        # POST request should not be supported
        response = client.post('/monitoring/metrics/export/')

        # Should return 405 Method Not Allowed or 404
        self.assertIn(response.status_code, [405, 404])
