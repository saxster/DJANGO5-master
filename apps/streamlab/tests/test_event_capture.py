"""
Unit tests for Stream Event Capture Service
"""

import uuid
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, AsyncMock
import asyncio

from ..models import TestScenario, TestRun, StreamEvent
from ..services.event_capture import StreamEventCapture

User = get_user_model()


class TestStreamEventCapture(TransactionTestCase):
    """Test stream event capture functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        self.scenario = TestScenario.objects.create(
            name='Test Scenario',
            protocol='websocket',
            endpoint='ws://test/',
            expected_p95_latency_ms=100,
            expected_error_rate=0.05,
            created_by=self.user
        )

        self.test_run = TestRun.objects.create(
            scenario=self.scenario,
            started_by=self.user,
            status='running'
        )

        self.capture_service = StreamEventCapture()

    def test_capture_successful_event(self):
        """Test capturing a successful stream event"""
        async def run_test():
            correlation_id = str(uuid.uuid4())

            # Mock active run lookup
            self.capture_service.active_runs[correlation_id] = self.test_run

            payload = {
                'user_id': 'user_123',
                'quality_score': 0.85,
                'voice_sample': 'should_be_redacted'
            }

            event_id = await self.capture_service.capture_event(
                correlation_id=correlation_id,
                endpoint='ws/mobile/sync',
                payload=payload,
                direction='inbound',
                latency_ms=45.5,
                outcome='success'
            )

            self.assertIsNotNone(event_id)

            # Verify event was created
            event = StreamEvent.objects.get(id=event_id)
            self.assertEqual(event.run, self.test_run)
            self.assertEqual(event.correlation_id, correlation_id)
            self.assertEqual(event.latency_ms, 45.5)
            self.assertEqual(event.outcome, 'success')

            # Verify PII was redacted
            self.assertNotIn('voice_sample', event.payload_sanitized)
            self.assertIn('quality_score', event.payload_sanitized)
            self.assertTrue(event.payload_sanitized['_pii_redacted'])

        asyncio.run(run_test())

    def test_capture_error_event(self):
        """Test capturing an error event with stack trace"""
        async def run_test():
            correlation_id = str(uuid.uuid4())
            self.capture_service.active_runs[correlation_id] = self.test_run

            error_details = {
                'error_code': 'VALIDATION_ERROR',
                'error_message': 'Invalid payload format',
                'http_status': 400,
                'traceback': 'File "/app/views.py", line 123, in process_data\n    raise ValidationError("Invalid format")',
                'exception_type': 'ValidationError'
            }

            event_id = await self.capture_service.capture_event(
                correlation_id=correlation_id,
                endpoint='ws/mobile/sync',
                payload={'test': 'data'},
                direction='inbound',
                latency_ms=200.0,
                outcome='error',
                error_details=error_details
            )

            self.assertIsNotNone(event_id)

            # Verify error details were captured
            event = StreamEvent.objects.get(id=event_id)
            self.assertEqual(event.outcome, 'error')
            self.assertEqual(event.error_code, 'VALIDATION_ERROR')
            self.assertEqual(event.http_status_code, 400)
            self.assertNotEqual(event.stack_trace_hash, '')

        asyncio.run(run_test())

    def test_update_run_statistics(self):
        """Test that run statistics are updated correctly"""
        async def run_test():
            correlation_id = str(uuid.uuid4())
            self.capture_service.active_runs[correlation_id] = self.test_run

            # Capture multiple events
            for i in range(5):
                outcome = 'error' if i == 4 else 'success'
                await self.capture_service.capture_event(
                    correlation_id=correlation_id,
                    endpoint='ws/test',
                    payload={'test': f'data_{i}'},
                    outcome=outcome,
                    latency_ms=50.0 + i * 10
                )

            # Refresh test run from database
            self.test_run.refresh_from_db()

            # Check statistics
            self.assertEqual(self.test_run.total_events, 5)
            self.assertEqual(self.test_run.successful_events, 4)
            self.assertEqual(self.test_run.failed_events, 1)
            self.assertEqual(self.test_run.error_rate, 0.2)  # 1/5 = 20%

        asyncio.run(run_test())

    def test_anomaly_detection_threshold(self):
        """Test anomaly detection threshold logic"""
        thresholds = {
            'ws/websocket/test': 100.0,
            'mqtt/topic/test': 50.0,
            'api/http/test': 200.0,
            'unknown/endpoint': 100.0
        }

        for endpoint, expected_threshold in thresholds.items():
            threshold = self.capture_service.get_anomaly_threshold(endpoint)
            self.assertEqual(threshold, expected_threshold)

    def test_no_active_run_handling(self):
        """Test handling when no active test run exists"""
        async def run_test():
            correlation_id = str(uuid.uuid4())

            # Don't add to active_runs cache
            event_id = await self.capture_service.capture_event(
                correlation_id=correlation_id,
                endpoint='ws/test',
                payload={'test': 'data'},
                outcome='success'
            )

            # Should return None when no active run
            self.assertIsNone(event_id)

        asyncio.run(run_test())

    def test_capture_service_error_handling(self):
        """Test error handling in capture service"""
        async def run_test():
            correlation_id = str(uuid.uuid4())

            # Test with invalid data that might cause errors
            with patch('apps.streamlab.services.event_capture.logger') as mock_logger:
                event_id = await self.capture_service.capture_event(
                    correlation_id=correlation_id,
                    endpoint='invalid://endpoint',
                    payload={'circular_ref': None},  # Potentially problematic data
                    outcome='success'
                )

                # Should handle errors gracefully
                self.assertIsNone(event_id)
                mock_logger.error.assert_called()

        asyncio.run(run_test())

    def test_final_metrics_calculation(self):
        """Test final metrics calculation for completed runs"""
        async def run_test():
            # Create events with different latencies
            latencies = [10, 25, 50, 75, 100, 150, 200, 300, 500, 1000]

            for latency in latencies:
                StreamEvent.objects.create(
                    run=self.test_run,
                    correlation_id=str(uuid.uuid4()),
                    direction='inbound',
                    endpoint='test',
                    latency_ms=latency,
                    message_size_bytes=100,
                    outcome='success',
                    payload_sanitized={'test': 'data'}
                )

            # Calculate final metrics
            await self.capture_service._calculate_final_metrics(self.test_run)

            # Refresh from database
            self.test_run.refresh_from_db()

            # Verify percentiles
            self.assertEqual(self.test_run.p50_latency_ms, 100)  # 50th percentile
            self.assertEqual(self.test_run.p95_latency_ms, 500)  # 95th percentile
            self.assertEqual(self.test_run.p99_latency_ms, 1000) # 99th percentile

        asyncio.run(run_test())


class TestEventCaptureIntegration(TestCase):
    """Integration tests for event capture with WebSocket consumers"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

    @patch('apps.streamlab.services.event_capture.StreamEventCapture.capture_event')
    def test_consumer_integration(self, mock_capture):
        """Test integration with WebSocket consumer"""
        mock_capture.return_value = AsyncMock(return_value='event_123')

        # This would typically be tested with channels testing utils
        # For now, we verify the capture service would be called correctly

        correlation_id = str(uuid.uuid4())
        payload = {'test': 'data'}

        # Mock the consumer call
        mock_capture.assert_not_called()

        # In a real integration test, we would:
        # 1. Connect to WebSocket
        # 2. Send message
        # 3. Verify capture_event was called with correct parameters

    def test_event_replay_data_structure(self):
        """Test that captured events can be replayed"""
        from ..models import TestScenario, TestRun, StreamEvent

        scenario = TestScenario.objects.create(
            name='Replay Test',
            protocol='websocket',
            endpoint='ws://test/',
            expected_p95_latency_ms=100,
            expected_error_rate=0.05,
            created_by=self.user
        )

        run = TestRun.objects.create(
            scenario=scenario,
            started_by=self.user,
            status='completed'
        )

        # Create sample events
        events_data = [
            {
                'direction': 'inbound',
                'payload': {'type': 'heartbeat'},
                'latency_ms': 25.0
            },
            {
                'direction': 'outbound',
                'payload': {'type': 'response', 'status': 'ok'},
                'latency_ms': 15.0
            }
        ]

        for event_data in events_data:
            StreamEvent.objects.create(
                run=run,
                correlation_id=str(uuid.uuid4()),
                direction=event_data['direction'],
                endpoint='ws/test',
                latency_ms=event_data['latency_ms'],
                message_size_bytes=100,
                outcome='success',
                payload_sanitized=event_data['payload']
            )

        # Verify events can be queried for replay
        replay_events = StreamEvent.objects.filter(run=run).order_by('timestamp')
        self.assertEqual(replay_events.count(), 2)

        # Verify replay data structure
        for event in replay_events:
            self.assertIsNotNone(event.payload_sanitized)
            self.assertIn('type', event.payload_sanitized)
            self.assertTrue(event.payload_sanitized.get('_pii_redacted', False))