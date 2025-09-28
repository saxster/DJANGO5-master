"""
Tests for Mobile Consumer - Stream Testbench Integration
Tests the integration between mobile WebSocket consumers and Stream Testbench event capture and anomaly detection.
"""

import json
import uuid
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async

from apps.api.mobile_consumers import MobileSyncConsumer
User = get_user_model()


class MobileConsumerStreamIntegrationTests(TestCase):
    """Test mobile consumer integration with Stream Testbench"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        # Create test scenario and run
        self.test_scenario = TestScenario.objects.create(
            name='Mobile Sync Test',
            description='Test scenario',
            protocol='websocket',
            endpoint='ws/mobile/sync/',
            expected_p95_latency_ms=100.0,
            expected_error_rate=0.05,
            created_by=self.user
        )

        self.test_run = TestRun.objects.create(
            scenario=self.test_scenario,
            started_by=self.user,
            status='running'
        )

    @patch('apps.api.mobile_consumers.stream_event_capture')
    @patch('apps.api.mobile_consumers.anomaly_detector')
    async def test_successful_message_captures_stream_event(self, mock_anomaly_detector, mock_stream_capture):
        """Test that successful message processing captures stream event"""
        # Mock return values
        mock_stream_capture.capture_event.return_value = 'test-event-id'
        mock_anomaly_detector.analyze_event.return_value = None  # No anomaly

        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'test-device-123'
        consumer.correlation_id = str(uuid.uuid4())

        # Mock cache for device info
        with patch('apps.api.mobile_consumers.cache') as mock_cache:
            mock_cache.get.return_value = {
                'app_version': '1.2.3',
                'os_version': 'Android 13',
                'device_model': 'Pixel 7'
            }

            # Simulate message processing
            test_message = {
                'type': 'sync_data',
                'data': {'test': 'payload'}
            }

            await consumer._capture_stream_event(
                message=test_message,
                message_correlation_id='msg-123',
                processing_time=50.0,
                outcome='success'
            )

            # Verify stream event capture was called
            mock_stream_capture.capture_event.assert_called_once()
            call_args = mock_stream_capture.capture_event.call_args[1]

            self.assertEqual(call_args['correlation_id'], consumer.correlation_id)
            self.assertEqual(call_args['endpoint'], 'ws/mobile/sync/sync_data')
            self.assertEqual(call_args['direction'], 'inbound')
            self.assertEqual(call_args['latency_ms'], 50.0)
            self.assertEqual(call_args['outcome'], 'success')

            # Verify anomaly detection was triggered
            mock_anomaly_detector.analyze_event.assert_called_once()

    @patch('apps.api.mobile_consumers.stream_event_capture')
    @patch('apps.api.mobile_consumers.anomaly_detector')
    async def test_error_message_captures_error_event(self, mock_anomaly_detector, mock_stream_capture):
        """Test that error message processing captures error event with details"""
        mock_stream_capture.capture_event.return_value = 'test-error-event-id'
        mock_anomaly_detector.analyze_event.return_value = {
            'occurrence_id': 'test-occurrence-id',
            'anomaly_type': 'json_decode_error',
            'severity': 'error'
        }

        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'test-device-123'
        consumer.correlation_id = str(uuid.uuid4())

        error_details = {
            'error_code': 'JSON_DECODE_ERROR',
            'error_message': 'Invalid JSON format',
            'exception_type': 'JSONDecodeError'
        }

        with patch('apps.api.mobile_consumers.cache') as mock_cache:
            mock_cache.get.return_value = {}

            await consumer._capture_stream_event(
                message={},
                message_correlation_id='msg-error-123',
                processing_time=25.0,
                outcome='error',
                error_details=error_details
            )

            # Verify error event was captured
            call_args = mock_stream_capture.capture_event.call_args[1]
            self.assertEqual(call_args['outcome'], 'error')
            self.assertEqual(call_args['error_details'], error_details)

    @patch('apps.api.mobile_consumers.send_anomaly_alert')
    @patch('apps.api.mobile_consumers.stream_event_capture')
    @patch('apps.api.mobile_consumers.anomaly_detector')
    async def test_anomaly_detection_broadcasts_alert(self, mock_anomaly_detector, mock_stream_capture, mock_send_alert):
        """Test that detected anomalies broadcast real-time alerts"""
        mock_stream_capture.capture_event.return_value = 'test-event-id'
        mock_anomaly_detector.analyze_event.return_value = {
            'occurrence_id': 'test-occurrence-id',
            'anomaly_type': 'latency_spike',
            'severity': 'warning'
        }

        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'test-device-123'
        consumer.correlation_id = str(uuid.uuid4())

        with patch('apps.api.mobile_consumers.cache') as mock_cache:
            mock_cache.get.return_value = {
                'app_version': '1.2.3',
                'os_version': 'Android 13',
                'device_model': 'Pixel 7'
            }

            await consumer._capture_stream_event(
                message={'type': 'sync_data'},
                message_correlation_id='msg-123',
                processing_time=150.0,  # High latency
                outcome='success'
            )

            # Verify anomaly alert was sent
            mock_send_alert.assert_called_once()
            alert_data = mock_send_alert.call_args[0][0]

            self.assertEqual(alert_data['id'], 'test-occurrence-id')
            self.assertEqual(alert_data['type'], 'latency_spike')
            self.assertEqual(alert_data['severity'], 'warning')
            self.assertIn('device_info', alert_data)

    async def test_device_info_extraction(self):
        """Test device information extraction from cache"""
        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'test-device-456'

        with patch('apps.api.mobile_consumers.cache') as mock_cache:
            mock_cache.get.return_value = {
                'app_version': '2.1.0',
                'os_version': 'Android 14',
                'device_model': 'Samsung Galaxy S24'
            }

            device_info = await consumer._get_device_info()

            self.assertEqual(device_info['app_version'], '2.1.0')
            self.assertEqual(device_info['os_version'], 'Android 14')
            self.assertEqual(device_info['device_model'], 'Samsung Galaxy S24')
            self.assertEqual(device_info['device_id'], 'test-device-456')

    async def test_device_info_extraction_fallback(self):
        """Test device info extraction with missing cache data"""
        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'test-device-789'

        with patch('apps.api.mobile_consumers.cache') as mock_cache:
            mock_cache.get.return_value = {}  # Empty cache

            device_info = await consumer._get_device_info()

            self.assertEqual(device_info['app_version'], 'unknown')
            self.assertEqual(device_info['os_version'], 'unknown')
            self.assertEqual(device_info['device_model'], 'unknown')
            self.assertEqual(device_info['device_id'], 'test-device-789')

    @patch('apps.api.mobile_consumers.logger')
    async def test_stream_capture_error_handling(self, mock_logger):
        """Test error handling in stream event capture"""
        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'test-device'
        consumer.correlation_id = str(uuid.uuid4())

        # Mock stream_event_capture to raise exception
        with patch('apps.api.mobile_consumers.stream_event_capture') as mock_capture:
            mock_capture.capture_event.side_effect = Exception('Capture failed')

            # Should not raise exception, just log error
            await consumer._capture_stream_event(
                message={'type': 'test'},
                message_correlation_id='msg-123',
                processing_time=10.0
            )

            # Verify error was logged
            mock_logger.error.assert_called_once()
            self.assertIn('Stream event capture failed', str(mock_logger.error.call_args))


class MobileConsumerIntegrationEndToEndTests(TestCase):
    """End-to-end integration tests"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='e2e_user',
            email='e2e@example.com'
        )

    @database_sync_to_async
    def create_test_run(self):
        """Create test run for E2E test"""
        scenario = TestScenario.objects.create(
            name='E2E Test Scenario',
            protocol='websocket',
            endpoint='ws/mobile/sync/',
            expected_p95_latency_ms=100.0,
            expected_error_rate=0.05,
            created_by=self.user
        )

        return TestRun.objects.create(
            scenario=scenario,
            started_by=self.user,
            status='running'
        )

    @patch('apps.api.mobile_consumers.stream_event_capture.capture_event')
    async def test_end_to_end_message_to_stream_event(self, mock_capture):
        """Test complete flow from WebSocket message to StreamEvent creation"""
        # Create test run
        test_run = await self.create_test_run()

        # Mock successful event capture
        mock_capture.return_value = 'stream-event-123'

        consumer = MobileSyncConsumer()
        consumer.scope = {
            'user': self.user,
            'query_string': b'device_id=test-device-e2e'
        }

        # Simulate connect
        await consumer.connect()

        # Simulate message receive with real message flow
        with patch('apps.api.mobile_consumers.anomaly_detector') as mock_detector:
            mock_detector.analyze_event.return_value = None

            test_message = json.dumps({
                'type': 'sync_data',
                'data': {
                    'voice_data': [],
                    'metrics': {'latency': 45}
                }
            })

            await consumer.receive(test_message)

            # Verify capture was called
            self.assertTrue(mock_capture.called)

            # Verify anomaly detection was triggered
            self.assertTrue(mock_detector.analyze_event.called)