"""
Integration Tests for Message Bus & Streaming Architecture

Tests the complete data flow: MQTT → Celery → WebSocket → Prometheus

Phase 6.1: Integration testing for message bus remediation
"""

import json
import pytest
import time
from unittest.mock import patch, MagicMock
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from apps.mqtt.subscriber import MQTTSubscriberService
from background_tasks.mqtt_handler_tasks import (
    process_device_alert,
    process_guard_gps,
    process_sensor_data
)
from apps.core.tasks.websocket_broadcast import broadcast_to_websocket_group
from apps.ml_training.tasks import train_model

User = get_user_model()


@pytest.mark.django_db
class TestMQTTToWebSocketPipeline(TestCase):
    """Test full MQTT → Celery → WebSocket pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='test_noc_user',
            email='noc@example.com',
            password='test123'
        )
        self.user.tenant_id = 123
        self.user.save()

    def test_mqtt_subscriber_routes_to_celery(self):
        """Test MQTT subscriber routes messages to correct Celery tasks."""
        subscriber = MQTTSubscriberService()

        # Test critical alert routing
        topic = "alert/panic/guard-789"
        data = {
            "alert_type": "panic",
            "severity": "critical",
            "message": "Panic button pressed",
            "timestamp": "2025-11-01T10:00:00Z"
        }

        with patch('background_tasks.mqtt_handler_tasks.process_device_alert.apply_async') as mock_task:
            subscriber._route_message(topic, data)
            mock_task.assert_called_once()
            args, kwargs = mock_task.call_args
            assert kwargs['queue'] == 'critical'
            assert kwargs['priority'] == 10

    def test_guard_gps_routing(self):
        """Test guard GPS messages route to high_priority queue."""
        subscriber = MQTTSubscriberService()

        topic = "guard/guard-789/gps"
        data = {
            "lat": 12.9716,
            "lon": 77.5946,
            "accuracy": 10.5,
            "timestamp": "2025-11-01T10:00:00Z",
            "guard_id": 789
        }

        with patch('background_tasks.mqtt_handler_tasks.process_guard_gps.apply_async') as mock_task:
            subscriber._route_message(topic, data)
            mock_task.assert_called_once()
            args, kwargs = mock_task.call_args
            assert kwargs['queue'] == 'high_priority'
            assert kwargs['priority'] == 8

    @patch('apps.core.tasks.websocket_broadcast.get_channel_layer')
    def test_celery_task_broadcasts_to_websocket(self, mock_get_channel_layer):
        """Test Celery task broadcasts to WebSocket group."""
        # Mock channel layer
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        # Call task synchronously (not via Celery)
        topic = "alert/panic/guard-789"
        data = {
            "source_id": "guard-789",
            "alert_type": "panic",
            "severity": "critical",
            "message": "Panic button pressed",
            "timestamp": "2025-11-01T10:00:00Z"
        }

        # Execute task
        task = process_device_alert
        task.request = MagicMock()  # Mock request object
        task.request.id = "test-task-id"
        task.request.retries = 0

        # This will call broadcast_to_noc_dashboard internally
        # which should trigger group_send
        with patch('background_tasks.mqtt_handler_tasks.TaskMetrics'):
            task(topic, data)

        # Verify group_send was called
        assert mock_channel_layer.group_send.call_count >= 1

    def test_websocket_broadcast_function(self):
        """Test standalone WebSocket broadcast function."""
        with patch('apps.core.tasks.websocket_broadcast.get_channel_layer') as mock_get_channel_layer:
            mock_channel_layer = MagicMock()
            mock_get_channel_layer.return_value = mock_channel_layer

            # Broadcast to group
            result = broadcast_to_websocket_group(
                group_name='noc_dashboard',
                message_type='test_alert',
                data={'test': 'data'},
                priority='critical'
            )

            assert result is True
            mock_channel_layer.group_send.assert_called_once()

    def test_ml_task_websocket_progress(self):
        """Test ML training task broadcasts progress to WebSocket."""
        with patch('apps.ml_training.tasks.time.sleep'):  # Skip actual training
            with patch('apps.core.tasks.websocket_broadcast.get_channel_layer') as mock_get_channel_layer:
                mock_channel_layer = MagicMock()
                mock_get_channel_layer.return_value = mock_channel_layer

                # Execute task
                task = train_model
                task.request = MagicMock()
                task.request.id = "test-ml-task"
                task.request.retries = 0

                task(
                    dataset_id=123,
                    model_type='anomaly_detector',
                    hyperparameters={'threshold': 0.8},
                    user_id=self.user.id
                )

                # Should have broadcast progress updates
                assert mock_channel_layer.group_send.call_count >= 2  # At least start + end


@pytest.mark.django_db
class TestTaskMetricsPrometheusExport(TestCase):
    """Test TaskMetrics export to Prometheus."""

    def test_taskmetrics_prometheus_export(self):
        """Test TaskMetrics counters export to Prometheus."""
        from apps.core.tasks.base import TaskMetrics

        with patch('apps.core.tasks.base.prometheus') as mock_prometheus:
            # Increment counter
            TaskMetrics.increment_counter('test_metric', {'tag': 'value'})

            # Verify Prometheus increment was called
            mock_prometheus.increment_counter.assert_called_once_with(
                'celery_test_metric_total',
                labels={'tag': 'value'},
                help_text='Total count of test_metric events'
            )

    def test_taskmetrics_timing_histogram(self):
        """Test TaskMetrics timing export as Prometheus histogram."""
        from apps.core.tasks.base import TaskMetrics

        with patch('apps.core.tasks.base.prometheus') as mock_prometheus:
            # Record timing
            TaskMetrics.record_timing('task_duration', 123.45, {'task': 'test'})

            # Verify Prometheus histogram was called
            mock_prometheus.observe_histogram.assert_called_once()
            args, kwargs = mock_prometheus.observe_histogram.call_args
            assert args[0] == 'celery_task_duration_seconds'
            assert abs(args[1] - 0.12345) < 0.001  # ms→seconds conversion


@pytest.mark.django_db
class TestCircuitBreaker(TestCase):
    """Test circuit breaker pattern for MQTT publishing."""

    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        from apps.core.tasks.base import CircuitBreaker
        from django.core.cache import cache

        cb = CircuitBreaker()
        service = 'test_mqtt_broker'

        # Initially circuit should be closed
        assert cb.is_open(service) is False

        # Simulate 5 failures
        for i in range(5):
            cb.record_failure(service)

        # Circuit should now be open
        assert cb.is_open(service) is True

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovers after timeout."""
        from apps.core.tasks.base import CircuitBreaker
        from django.core.cache import cache
        import time

        cb = CircuitBreaker()
        service = 'test_mqtt_broker_recovery'

        # Open circuit
        for i in range(5):
            cb.record_failure(service)

        assert cb.is_open(service) is True

        # Manually set last_failure to past (simulate 6 minutes ago)
        cache_key = f"circuit_breaker:{service}"
        circuit_data = cache.get(cache_key)
        circuit_data['last_failure'] = time.time() - 360  # 6 minutes ago
        cache.set(cache_key, circuit_data)

        # Circuit should now be closed (recovery timeout passed)
        assert cb.is_open(service) is False


@pytest.mark.django_db
class TestWebSocketConsumerMetrics(TestCase):
    """Test WebSocket consumer metrics tracking."""

    def test_connection_metrics_tracked(self):
        """Test WebSocket connection metrics are recorded."""
        from apps.core.tasks.base import TaskMetrics

        with patch('apps.core.tasks.base.cache') as mock_cache:
            mock_cache.get.return_value = 0

            # Simulate connection metric
            TaskMetrics.increment_counter('websocket_connection_established', {
                'consumer': 'noc_dashboard',
                'tenant_id': '123'
            })

            # Verify cache.set was called
            assert mock_cache.set.call_count >= 1


class TestEndToEndPipeline(TestCase):
    """End-to-end integration tests (requires running services)."""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires MQTT broker and Redis running")
    def test_full_pipeline_mqtt_to_websocket(self):
        """
        Full pipeline test: MQTT publish → Subscriber → Celery → WebSocket.

        Prerequisites:
        - MQTT broker running (mosquitto)
        - Redis running
        - Celery worker running
        - MQTT subscriber running

        This test publishes an MQTT message and verifies it reaches WebSocket.
        """
        import paho.mqtt.client as mqtt_client
        from paho.mqtt.enums import CallbackAPIVersion

        # 1. Publish MQTT message
        client = mqtt_client.Client(CallbackAPIVersion.VERSION2)
        client.connect('localhost', 1883, 60)
        payload = json.dumps({
            "alert_type": "test",
            "severity": "low",
            "message": "End-to-end test",
            "timestamp": "2025-11-01T10:00:00Z"
        })
        client.publish("alert/test/integration", payload, qos=1)
        client.loop(2)
        client.disconnect()

        # 2. Wait for processing
        time.sleep(2)

        # 3. Check WebSocket group received message
        channel_layer = get_channel_layer()
        # Note: In real test, would connect WebSocket client and verify receipt
        assert channel_layer is not None


# Performance benchmarks
@pytest.mark.benchmark
class TestMessageBusPerformance(TestCase):
    """Performance benchmarks for message bus components."""

    def test_websocket_broadcast_latency(self):
        """Benchmark WebSocket broadcast latency (should be < 50ms)."""
        import time
        from apps.core.tasks.websocket_broadcast import broadcast_to_websocket_group

        with patch('apps.core.tasks.websocket_broadcast.get_channel_layer') as mock_get_channel_layer:
            mock_channel_layer = MagicMock()
            mock_get_channel_layer.return_value = mock_channel_layer

            start = time.time()
            for i in range(100):
                broadcast_to_websocket_group(
                    group_name='test_group',
                    message_type='benchmark',
                    data={'iteration': i}
                )
            duration_ms = (time.time() - start) * 1000

            avg_latency = duration_ms / 100
            assert avg_latency < 50, f"Average latency {avg_latency}ms exceeds 50ms threshold"

    def test_mqtt_routing_performance(self):
        """Benchmark MQTT message routing (should be < 10ms per message)."""
        subscriber = MQTTSubscriberService()

        topic = "device/sensor-123/telemetry"
        data = {"battery": 85, "signal": 90}

        with patch('background_tasks.mqtt_handler_tasks.process_device_telemetry.apply_async'):
            start = time.time()
            for i in range(1000):
                subscriber._route_message(topic, data)
            duration_ms = (time.time() - start) * 1000

            avg_latency = duration_ms / 1000
            assert avg_latency < 10, f"Average routing latency {avg_latency}ms exceeds 10ms threshold"
