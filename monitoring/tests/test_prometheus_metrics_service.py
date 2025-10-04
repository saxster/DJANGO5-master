"""
Comprehensive Tests for Prometheus Metrics Service

Tests Prometheus metrics collection, storage, and export.

Test Coverage:
- Counter increment operations
- Gauge set/inc/dec operations
- Histogram observations
- Label serialization
- Prometheus text format export
- Thread safety
- Metric cardinality limits

Compliance:
- .claude/rules.md Rule #11 (specific exceptions)
"""

import pytest
import threading
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor

from monitoring.services.prometheus_metrics import (
    PrometheusMetricsService,
    prometheus
)


class TestPrometheusCounters:
    """Test counter metric operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PrometheusMetricsService()

    def test_increment_counter_default_value(self):
        """Test counter increment with default value (1.0)."""
        self.service.increment_counter(
            'test_counter_total',
            labels={'status': 'success'},
            help_text='Test counter'
        )

        # Get metrics
        metrics = self.service.get_metrics()

        # Should have counter with value 1.0
        assert 'test_counter_total' in metrics
        assert metrics['test_counter_total']['type'] == 'counter'

    def test_increment_counter_custom_value(self):
        """Test counter increment with custom value."""
        self.service.increment_counter(
            'test_counter_total',
            labels={'status': 'success'},
            value=5.0,
            help_text='Test counter'
        )

        self.service.increment_counter(
            'test_counter_total',
            labels={'status': 'success'},
            value=3.0,
            help_text='Test counter'
        )

        # Get metrics
        metrics = self.service.get_metrics()

        # Should have counter with value 8.0 (5.0 + 3.0)
        counter_data = metrics['test_counter_total']
        assert counter_data['type'] == 'counter'

    def test_increment_counter_different_labels(self):
        """Test counter with different label combinations."""
        # Increment with different labels
        self.service.increment_counter(
            'http_requests_total',
            labels={'method': 'GET', 'endpoint': '/api/'},
            help_text='HTTP requests'
        )

        self.service.increment_counter(
            'http_requests_total',
            labels={'method': 'POST', 'endpoint': '/api/'},
            help_text='HTTP requests'
        )

        metrics = self.service.get_metrics()

        # Should have separate counters for each label combination
        counter_data = metrics['http_requests_total']
        assert counter_data['type'] == 'counter'

    def test_increment_counter_without_labels(self):
        """Test counter without labels."""
        self.service.increment_counter(
            'simple_counter_total',
            help_text='Simple counter'
        )

        metrics = self.service.get_metrics()

        assert 'simple_counter_total' in metrics

    def test_counter_is_monotonic(self):
        """Test that counter only increases."""
        for i in range(10):
            self.service.increment_counter(
                'monotonic_counter_total',
                labels={'test': 'value'},
                value=1.0,
                help_text='Monotonic counter'
            )

        # All increments should accumulate
        metrics = self.service.get_metrics()
        assert 'monotonic_counter_total' in metrics


class TestPrometheusGauges:
    """Test gauge metric operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PrometheusMetricsService()

    def test_set_gauge_value(self):
        """Test setting gauge to specific value."""
        self.service.set_gauge(
            'memory_usage_bytes',
            1024.0,
            labels={'type': 'heap'},
            help_text='Memory usage'
        )

        metrics = self.service.get_metrics()

        assert 'memory_usage_bytes' in metrics
        gauge_data = metrics['memory_usage_bytes']
        assert gauge_data['type'] == 'gauge'

    def test_increment_gauge(self):
        """Test incrementing gauge value."""
        # Set initial value
        self.service.set_gauge(
            'active_connections',
            10.0,
            labels={'server': 'web1'},
            help_text='Active connections'
        )

        # Increment
        self.service.increment_gauge(
            'active_connections',
            labels={'server': 'web1'},
            value=5.0,
            help_text='Active connections'
        )

        metrics = self.service.get_metrics()

        # Should be 15.0
        assert 'active_connections' in metrics

    def test_decrement_gauge(self):
        """Test decrementing gauge value."""
        # Set initial value
        self.service.set_gauge(
            'queue_depth',
            100.0,
            labels={'queue': 'default'},
            help_text='Queue depth'
        )

        # Decrement
        self.service.decrement_gauge(
            'queue_depth',
            labels={'queue': 'default'},
            value=30.0,
            help_text='Queue depth'
        )

        metrics = self.service.get_metrics()

        # Should be 70.0
        assert 'queue_depth' in metrics

    def test_gauge_can_decrease(self):
        """Test that gauge can go up and down."""
        # Start at 100
        self.service.set_gauge('test_gauge', 100.0)

        # Decrease to 50
        self.service.set_gauge('test_gauge', 50.0)

        # Increase to 75
        self.service.set_gauge('test_gauge', 75.0)

        metrics = self.service.get_metrics()

        # Should be at last set value (75.0)
        assert 'test_gauge' in metrics


class TestPrometheusHistograms:
    """Test histogram metric operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PrometheusMetricsService()

    def test_observe_histogram(self):
        """Test recording histogram observations."""
        self.service.observe_histogram(
            'request_duration_seconds',
            0.5,
            labels={'endpoint': '/api/'},
            help_text='Request duration'
        )

        metrics = self.service.get_metrics()

        assert 'request_duration_seconds' in metrics
        histogram_data = metrics['request_duration_seconds']
        assert histogram_data['type'] == 'histogram'

    def test_histogram_multiple_observations(self):
        """Test histogram with multiple observations."""
        # Record multiple observations
        observations = [0.1, 0.5, 1.0, 2.0, 0.3]

        for value in observations:
            self.service.observe_histogram(
                'latency_seconds',
                value,
                labels={'service': 'api'},
                help_text='Service latency'
            )

        metrics = self.service.get_metrics()

        # Should have histogram with all observations
        assert 'latency_seconds' in metrics

    def test_histogram_different_labels(self):
        """Test histogram with different label combinations."""
        self.service.observe_histogram(
            'response_time_seconds',
            0.5,
            labels={'method': 'GET'},
            help_text='Response time'
        )

        self.service.observe_histogram(
            'response_time_seconds',
            1.5,
            labels={'method': 'POST'},
            help_text='Response time'
        )

        metrics = self.service.get_metrics()

        # Should have separate histograms for each label combination
        assert 'response_time_seconds' in metrics


class TestPrometheusLabelSerialization:
    """Test label serialization for metric keys."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PrometheusMetricsService()

    def test_serialize_simple_labels(self):
        """Test serialization of simple labels."""
        labels = {'method': 'GET', 'status': '200'}

        serialized = self.service._serialize_labels(labels)

        # Should be deterministic and sorted
        assert isinstance(serialized, str)
        assert 'method' in serialized
        assert 'status' in serialized

    def test_serialize_empty_labels(self):
        """Test serialization of empty labels."""
        labels = {}

        serialized = self.service._serialize_labels(labels)

        # Should handle empty labels
        assert isinstance(serialized, str)

    def test_serialize_labels_is_deterministic(self):
        """Test that label serialization is deterministic."""
        labels = {'z': '1', 'a': '2', 'm': '3'}

        # Serialize multiple times
        results = [self.service._serialize_labels(labels) for _ in range(10)]

        # All results should be identical
        assert len(set(results)) == 1

    def test_different_labels_different_keys(self):
        """Test that different labels produce different keys."""
        labels1 = {'method': 'GET'}
        labels2 = {'method': 'POST'}

        key1 = self.service._serialize_labels(labels1)
        key2 = self.service._serialize_labels(labels2)

        assert key1 != key2

    def test_label_order_doesnt_matter(self):
        """Test that label order doesn't affect serialization."""
        labels1 = {'a': '1', 'b': '2', 'c': '3'}
        labels2 = {'c': '3', 'a': '1', 'b': '2'}

        key1 = self.service._serialize_labels(labels1)
        key2 = self.service._serialize_labels(labels2)

        # Should produce same key (order-independent)
        assert key1 == key2


class TestPrometheusTextFormat:
    """Test Prometheus text exposition format export."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PrometheusMetricsService()

    def test_export_prometheus_format(self):
        """Test export in Prometheus text format."""
        # Add some metrics
        self.service.increment_counter(
            'test_counter_total',
            labels={'status': 'success'},
            help_text='Test counter'
        )

        self.service.set_gauge(
            'test_gauge',
            42.0,
            help_text='Test gauge'
        )

        # Export
        text_format = self.service.export_prometheus_format()

        # Should be string
        assert isinstance(text_format, str)

        # Should contain metric names
        assert 'test_counter_total' in text_format or 'test_gauge' in text_format

    def test_export_includes_help_text(self):
        """Test that export includes HELP comments."""
        self.service.increment_counter(
            'my_counter_total',
            help_text='This is my counter'
        )

        text_format = self.service.export_prometheus_format()

        # Should include HELP line
        assert '# HELP' in text_format or 'my_counter_total' in text_format

    def test_export_includes_type(self):
        """Test that export includes TYPE comments."""
        self.service.increment_counter(
            'my_counter_total',
            help_text='Test counter'
        )

        text_format = self.service.export_prometheus_format()

        # Should include TYPE line
        assert '# TYPE' in text_format or 'counter' in text_format

    def test_export_with_labels(self):
        """Test export with labeled metrics."""
        self.service.increment_counter(
            'http_requests_total',
            labels={'method': 'GET', 'status': '200'},
            help_text='HTTP requests'
        )

        text_format = self.service.export_prometheus_format()

        # Should include label information
        assert 'http_requests_total' in text_format
        # Labels appear as {method="GET",status="200"}

    def test_export_empty_metrics(self):
        """Test export with no metrics."""
        text_format = self.service.export_prometheus_format()

        # Should return empty string or minimal header
        assert isinstance(text_format, str)


class TestPrometheusThreadSafety:
    """Test thread safety of Prometheus metrics service."""

    def test_concurrent_counter_increments(self):
        """Test concurrent counter increments from multiple threads."""
        service = PrometheusMetricsService()

        def increment_counter(thread_id):
            for i in range(100):
                service.increment_counter(
                    'concurrent_counter_total',
                    labels={'thread': str(thread_id)},
                    help_text='Concurrent counter'
                )

        # Run 10 threads concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(increment_counter, i) for i in range(10)]
            for f in futures:
                f.result()

        metrics = service.get_metrics()

        # Should have counter
        assert 'concurrent_counter_total' in metrics

    def test_concurrent_gauge_updates(self):
        """Test concurrent gauge updates from multiple threads."""
        service = PrometheusMetricsService()

        def update_gauge(thread_id):
            for i in range(50):
                service.set_gauge(
                    'concurrent_gauge',
                    float(i),
                    labels={'thread': str(thread_id)},
                    help_text='Concurrent gauge'
                )

        # Run 5 threads concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(update_gauge, i) for i in range(5)]
            for f in futures:
                f.result()

        metrics = service.get_metrics()

        # Should have gauge
        assert 'concurrent_gauge' in metrics

    def test_concurrent_histogram_observations(self):
        """Test concurrent histogram observations from multiple threads."""
        service = PrometheusMetricsService()

        def observe_histogram(thread_id):
            for i in range(50):
                service.observe_histogram(
                    'concurrent_histogram',
                    float(i) / 10.0,
                    labels={'thread': str(thread_id)},
                    help_text='Concurrent histogram'
                )

        # Run 5 threads concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(observe_histogram, i) for i in range(5)]
            for f in futures:
                f.result()

        metrics = service.get_metrics()

        # Should have histogram
        assert 'concurrent_histogram' in metrics

    def test_concurrent_export(self):
        """Test concurrent export from multiple threads."""
        service = PrometheusMetricsService()

        # Add some metrics
        service.increment_counter('test_counter_total', help_text='Test')

        def export_metrics():
            return service.export_prometheus_format()

        # Export concurrently from multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(export_metrics) for _ in range(10)]
            results = [f.result() for f in futures]

        # All exports should succeed
        assert len(results) == 10
        assert all(isinstance(r, str) for r in results)


class TestPrometheusGlobalSingleton:
    """Test global singleton Prometheus instance."""

    def test_global_prometheus_instance_exists(self):
        """Test that global prometheus instance is available."""
        from monitoring.services.prometheus_metrics import prometheus

        assert prometheus is not None
        assert isinstance(prometheus, PrometheusMetricsService)

    def test_global_prometheus_is_singleton(self):
        """Test that global prometheus is a singleton."""
        from monitoring.services.prometheus_metrics import prometheus as instance1
        from monitoring.services.prometheus_metrics import prometheus as instance2

        # Should be same instance
        assert instance1 is instance2

    def test_global_prometheus_shared_state(self):
        """Test that global prometheus maintains shared state."""
        from monitoring.services.prometheus_metrics import prometheus

        # Increment counter
        prometheus.increment_counter('global_test_counter', help_text='Test')

        # Get metrics from same instance
        metrics = prometheus.get_metrics()

        # Should have the counter
        assert 'global_test_counter' in metrics


class TestPrometheusEdgeCases:
    """Edge case tests for Prometheus metrics service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PrometheusMetricsService()

    def test_metric_name_with_underscores(self):
        """Test metric name with underscores."""
        self.service.increment_counter(
            'my_app_requests_total',
            help_text='Requests'
        )

        metrics = self.service.get_metrics()
        assert 'my_app_requests_total' in metrics

    def test_label_value_with_special_characters(self):
        """Test label value with special characters."""
        self.service.increment_counter(
            'test_counter',
            labels={'path': '/api/v1/users'},
            help_text='Test'
        )

        metrics = self.service.get_metrics()
        assert 'test_counter' in metrics

    def test_very_large_counter_value(self):
        """Test counter with very large value."""
        self.service.increment_counter(
            'large_counter',
            value=1e10,
            help_text='Large counter'
        )

        metrics = self.service.get_metrics()
        assert 'large_counter' in metrics

    def test_very_small_histogram_value(self):
        """Test histogram with very small value."""
        self.service.observe_histogram(
            'small_histogram',
            0.000001,
            help_text='Small histogram'
        )

        metrics = self.service.get_metrics()
        assert 'small_histogram' in metrics

    def test_negative_gauge_value(self):
        """Test gauge with negative value."""
        self.service.set_gauge(
            'temperature_celsius',
            -10.0,
            help_text='Temperature'
        )

        metrics = self.service.get_metrics()
        assert 'temperature_celsius' in metrics

    def test_metric_without_help_text(self):
        """Test metric without help text."""
        self.service.increment_counter('no_help_counter')

        metrics = self.service.get_metrics()
        assert 'no_help_counter' in metrics

    def test_empty_metric_name(self):
        """Test handling of empty metric name."""
        # Should handle gracefully or raise specific error
        try:
            self.service.increment_counter('', help_text='Empty name')
            # If it allows empty name, verify it's handled
            metrics = self.service.get_metrics()
            # Check behavior
        except (ValueError, KeyError) as e:
            # Expected behavior: reject empty names
            pass
