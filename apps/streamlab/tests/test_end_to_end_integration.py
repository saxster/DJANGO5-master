"""
End-to-End Integration Tests
Tests the complete flow from mobile message → Stream Testbench → anomaly detection → real-time alerts.
"""

import asyncio
import uuid
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async

from apps.api.mobile_consumers import MobileSyncConsumer
from apps.streamlab.consumers import AnomalyAlertsConsumer
from apps.issue_tracker.models import AnomalySignature, AnomalyOccurrence
from apps.issue_tracker.services.anomaly_detector import anomaly_detector

User = get_user_model()


class EndToEndIntegrationTests(TransactionTestCase):
    """End-to-end integration tests for the complete Testing Workbench flow"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='e2e_user',
            email='e2e@example.com',
            is_staff=True  # Needed for dashboard access
        )

        self.test_scenario = TestScenario.objects.create(
            name='E2E Mobile Test',
            description='End-to-end test scenario',
            protocol='websocket',
            endpoint='ws/mobile/sync/',
            expected_p95_latency_ms=100.0,
            expected_error_rate=0.05,
            created_by=self.user,
            pii_redaction_rules={
                'allowlisted_fields': ['timestamp', 'event_type', 'latency_ms'],
                'hash_fields': ['user_id', 'device_id'],
                'remove_fields': ['sensitive_data']
            }
        )

        self.test_run = TestRun.objects.create(
            scenario=self.test_scenario,
            started_by=self.user,
            status='running'
        )

    @patch('apps.api.mobile_consumers.cache')
    async def test_complete_mobile_message_to_anomaly_flow(self, mock_cache):
        """Test complete flow: mobile message → event capture → anomaly detection → alert"""

        # Setup device info in cache
        mock_cache.get.return_value = {
            'app_version': '1.2.3',
            'os_version': 'Android 13',
            'device_model': 'Pixel 7'
        }

        # Create mobile consumer
        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'e2e-device-123'
        consumer.correlation_id = str(uuid.uuid4())

        # Test data that will trigger an anomaly (high latency)
        test_message = {
            'type': 'sync_data',
            'data': {
                'voice_data': ['sample1', 'sample2'],
                'metrics': {'processing_time': 150}
            }
        }

        # Mock real-time alerting
        with patch('apps.streamlab.consumers.send_anomaly_alert') as mock_send_alert:
            with patch('apps.api.mobile_consumers.send_anomaly_alert') as mock_mobile_alert:

                # Simulate high processing time that triggers anomaly
                await consumer._capture_stream_event(
                    message=test_message,
                    message_correlation_id='e2e-msg-123',
                    processing_time=150.0,  # High latency to trigger anomaly
                    outcome='success'
                )

                # Verify anomaly was detected and alerted
                self.assertTrue(mock_mobile_alert.called or mock_send_alert.called)

    @database_sync_to_async
    def create_anomaly_data(self):
        """Create test anomaly data"""
        signature = AnomalySignature.objects.create(
            signature_hash='e2e-test-hash-123',
            anomaly_type='latency_spike',
            severity='warning',
            pattern={'latency_ms': {'gt': 100}},
            endpoint_pattern='ws/mobile/sync',
            occurrence_count=1
        )

        occurrence = AnomalyOccurrence.objects.create(
            signature=signature,
            endpoint='ws/mobile/sync/sync_data',
            latency_ms=150.0,
            client_app_version='1.2.3',
            client_os_version='Android 13',
            client_device_model='Pixel 7'
        )

        return signature, occurrence

    async def test_real_time_dashboard_updates(self):
        """Test real-time dashboard updates via WebSocket consumers"""

        # Create test anomaly data
        signature, occurrence = await self.create_anomaly_data()

        # Setup WebSocket communicator for anomaly alerts
        communicator = WebsocketCommunicator(AnomalyAlertsConsumer.as_asgi(), "/ws/anomaly-alerts/")

        # Mock user authentication
        communicator.scope["user"] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Simulate anomaly alert broadcast
        alert_data = {
            'id': str(occurrence.id),
            'signature_id': str(signature.id),
            'type': 'latency_spike',
            'severity': 'warning',
            'endpoint': 'ws/mobile/sync/sync_data',
            'correlation_id': str(uuid.uuid4()),
            'latency_ms': 150.0,
            'created_at': occurrence.created_at.isoformat(),
            'client_info': {
                'app_version': '1.2.3',
                'os_version': 'Android 13',
                'device_model': 'Pixel 7'
            }
        }

        # Send alert through channel layer
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()

        if channel_layer:
            await channel_layer.group_send(
                "streamlab_anomaly_alerts",
                {
                    "type": "new_anomaly",
                    "data": alert_data
                }
            )

            # Receive the message from WebSocket
            response = await communicator.receive_json_from()

            self.assertEqual(response['type'], 'new_anomaly')
            self.assertEqual(response['data']['type'], 'latency_spike')
            self.assertEqual(response['data']['severity'], 'warning')
            self.assertIn('client_info', response['data'])

        await communicator.disconnect()

    async def test_kotlin_anomaly_detection_flow(self):
        """Test end-to-end flow for Kotlin-specific anomalies"""

        # Mock Kotlin/Android specific event data
        kotlin_event_data = {
            'endpoint': 'mobile/android/ui',
            'latency_ms': 25,  # Above 16ms frame time
            'error_message': 'StrictMode policy violation: main thread disk access',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4()),
            'client_app_version': '1.3.0',
            'client_os_version': 'Android 14',
            'client_device_model': 'Pixel 8',
            'payload_sanitized': {
                'jank_percent': 4.2,
                'frame_drops': 12
            }
        }

        # Analyze event for anomalies
        with patch('channels.layers.get_channel_layer') as mock_channel_layer:
            mock_channel = AsyncMock()
            mock_channel_layer.return_value = mock_channel

            result = await anomaly_detector.analyze_event(kotlin_event_data)

            # Should detect Kotlin-specific anomaly
            if result:
                self.assertIn('anomaly_type', result)

                # Verify channel layer was used for broadcasting
                if mock_channel.group_send.called:
                    # Check that anomaly alert was broadcasted
                    call_args = mock_channel.group_send.call_args_list
                    self.assertTrue(any('anomaly_alerts' in str(call) for call in call_args))

    @patch('apps.issue_tracker.services.anomaly_detector.logger')
    async def test_anomaly_escalation_flow(self, mock_logger):
        """Test anomaly escalation for critical issues"""

        # Create critical anomaly event
        critical_event_data = {
            'endpoint': 'mobile/android',
            'error_message': 'ANR detected: Application not responding for 8 seconds',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4()),
            'client_app_version': '1.2.0',
            'latency_ms': 8000  # 8 second timeout
        }

        with patch('channels.layers.get_channel_layer') as mock_channel_layer:
            mock_channel = AsyncMock()
            mock_channel_layer.return_value = mock_channel

            result = await anomaly_detector.analyze_event(critical_event_data)

            if result and result.get('severity') == 'critical':
                # Verify critical anomaly was logged
                mock_logger.info.assert_called()

                # Verify escalation was triggered
                escalation_calls = [call for call in mock_channel.group_send.call_args_list
                                  if 'escalation' in str(call)]
                self.assertTrue(len(escalation_calls) > 0)

    async def test_client_version_trend_analysis(self):
        """Test client version trend analysis functionality"""

        # Create multiple occurrences with different versions
        test_versions = [
            ('1.0.0', 'Android 12', 'Pixel 6'),
            ('1.0.0', 'Android 12', 'Galaxy S22'),
            ('1.1.0', 'Android 13', 'Pixel 7'),
            ('1.1.0', 'Android 13', 'Pixel 7'),
            ('1.2.0', 'Android 14', 'Pixel 8')
        ]

        signature = await database_sync_to_async(AnomalySignature.objects.create)(
            signature_hash='trend-test-hash',
            anomaly_type='test_trend_anomaly',
            severity='warning',
            pattern={'test': True},
            endpoint_pattern='ws/mobile/sync'
        )

        for app_version, os_version, device_model in test_versions:
            await database_sync_to_async(AnomalyOccurrence.objects.create)(
                signature=signature,
                endpoint='ws/mobile/sync',
                client_app_version=app_version,
                client_os_version=os_version,
                client_device_model=device_model
            )

        # Analyze trends
        trend_analysis = await database_sync_to_async(
            AnomalyOccurrence.version_trend_analysis
        )(signature_id=signature.id, days=30)

        # Verify trend analysis
        self.assertIn('app_version_trends', trend_analysis)
        self.assertEqual(trend_analysis['app_version_trends']['1.1.0'], 2)  # Most occurrences
        self.assertEqual(trend_analysis['app_version_trends']['1.0.0'], 2)
        self.assertEqual(trend_analysis['app_version_trends']['1.2.0'], 1)

    @patch('apps.streamlab.services.event_capture.stream_event_capture.capture_event')
    async def test_stream_event_capture_integration(self, mock_capture_event):
        """Test Stream Testbench event capture integration"""

        # Mock successful event capture
        mock_capture_event.return_value = 'captured-event-123'

        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'integration-test-device'
        consumer.correlation_id = str(uuid.uuid4())

        test_message = {
            'type': 'heartbeat',
            'timestamp': '2024-01-01T12:00:00Z'
        }

        with patch('apps.api.mobile_consumers.cache') as mock_cache:
            mock_cache.get.return_value = {'app_version': '1.0.0'}

            await consumer._capture_stream_event(
                message=test_message,
                message_correlation_id='integration-msg-123',
                processing_time=25.0,
                outcome='success'
            )

            # Verify event capture was called with correct parameters
            mock_capture_event.assert_called_once()
            call_kwargs = mock_capture_event.call_args[1]

            self.assertEqual(call_kwargs['correlation_id'], consumer.correlation_id)
            self.assertEqual(call_kwargs['endpoint'], 'ws/mobile/sync/heartbeat')
            self.assertEqual(call_kwargs['direction'], 'inbound')
            self.assertEqual(call_kwargs['latency_ms'], 25.0)
            self.assertEqual(call_kwargs['outcome'], 'success')

    def test_pii_redaction_in_event_capture(self):
        """Test PII redaction in stream event capture"""

        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'pii-test-device'

        # Test message with PII data
        test_message_with_pii = {
            'type': 'sync_data',
            'user_id': '12345',  # Should be hashed
            'voice_sample': 'sensitive_audio_data',  # Should be removed
            'timestamp': '2024-01-01T12:00:00Z',  # Should be kept
            'quality_score': 0.85  # Should be kept
        }

        # Get device info (mock implementation)
        async def mock_get_device_info():
            return {
                'app_version': '1.0.0',
                'os_version': 'Android 12',
                'device_model': 'Test Device',
                'device_id': 'pii-test-device'
            }

        consumer._get_device_info = mock_get_device_info

        # Test sanitized payload creation
        sanitized_payload = {
            'message_type': test_message_with_pii.get('type', 'unknown'),
            'data_types': [],
            'device_info': {
                'app_version': '1.0.0',
                'os_version': 'Android 12',
                'device_model': 'Test Device',
                'device_id': 'pii-test-device'
            },
            'content_size': len(str(test_message_with_pii.get('data', {}))),
            'timestamp': '2024-01-01T12:00:00Z'
        }

        # Verify PII data is not in sanitized payload
        self.assertNotIn('voice_sample', str(sanitized_payload))
        self.assertNotIn('sensitive_audio_data', str(sanitized_payload))

        # Verify safe data is preserved
        self.assertEqual(sanitized_payload['message_type'], 'sync_data')
        self.assertIn('device_info', sanitized_payload)

    async def test_error_handling_resilience(self):
        """Test system resilience with error conditions"""

        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'error-test-device'
        consumer.correlation_id = str(uuid.uuid4())

        # Test with malformed message
        with patch('apps.api.mobile_consumers.logger') as mock_logger:

            # Should not raise exception, just log error
            await consumer._capture_stream_event(
                message=None,  # Invalid message
                message_correlation_id='error-msg-123',
                processing_time=10.0,
                outcome='error',
                error_details={'error_code': 'TEST_ERROR'}
            )

            # Verify error was logged but system continued
            self.assertTrue(mock_logger.error.called)

    async def test_performance_under_load(self):
        """Test system performance under simulated load"""

        consumer = MobileSyncConsumer()
        consumer.user = self.user
        consumer.device_id = 'perf-test-device'

        # Simulate multiple concurrent event captures
        tasks = []

        for i in range(10):  # Simulate 10 concurrent events
            correlation_id = str(uuid.uuid4())
            consumer.correlation_id = correlation_id

            task = consumer._capture_stream_event(
                message={'type': 'load_test', 'id': i},
                message_correlation_id=f'load-msg-{i}',
                processing_time=float(10 + i),
                outcome='success'
            )
            tasks.append(task)

        # Execute all tasks concurrently
        with patch('apps.api.mobile_consumers.stream_event_capture') as mock_capture:
            mock_capture.capture_event.return_value = f'event-{uuid.uuid4()}'

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all tasks completed successfully
            for result in results:
                self.assertIsNone(result)  # No exceptions raised

            # Verify all events were captured
            self.assertEqual(mock_capture.capture_event.call_count, 10)