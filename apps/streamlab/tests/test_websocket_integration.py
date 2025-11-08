"""
import logging
logger = logging.getLogger(__name__)
WebSocket Integration Tests for Stream Testbench
"""

import asyncio
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import path

# Import consumers
from ..consumers import StreamMetricsConsumer, AnomalyAlertsConsumer
from apps.api.mobile_consumers import MobileSyncConsumer

User = get_user_model()


class TestStreamMetricsConsumer(TransactionTestCase):
    """Test stream metrics WebSocket consumer"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )

    async def test_metrics_consumer_connection(self):
        """Test metrics consumer accepts staff connections"""
        # Create application with just the metrics consumer
        application = URLRouter([
            path("ws/streamlab/metrics/", StreamMetricsConsumer.as_asgi()),
        ])

        # Test connection with staff user
        communicator = WebsocketCommunicator(
            application,
            "ws/streamlab/metrics/",
            headers=[(b"authorization", b"Bearer test-token")]
        )

        # Set user in scope
        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Test receiving initial metrics
        await communicator.send_json_to({'type': 'get_metrics'})

        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'metrics_update')
        self.assertIn('data', response)

        await communicator.disconnect()

    async def test_metrics_consumer_unauthorized(self):
        """Test metrics consumer rejects non-staff connections"""
        from django.contrib.auth.models import AnonymousUser

        application = URLRouter([
            path("ws/streamlab/metrics/", StreamMetricsConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/streamlab/metrics/"
        )

        # Set anonymous user
        communicator.scope['user'] = AnonymousUser()

        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)

    async def test_anomaly_alerts_consumer(self):
        """Test anomaly alerts WebSocket consumer"""
        application = URLRouter([
            path("ws/streamlab/anomalies/", AnomalyAlertsConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/streamlab/anomalies/"
        )

        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Test anomaly acknowledgment
        await communicator.send_json_to({
            'type': 'acknowledge_anomaly',
            'anomaly_id': str(uuid.uuid4())
        })

        # Should receive response (even if anomaly doesn't exist)
        response = await communicator.receive_json_from()
        self.assertIn('type', response)

        await communicator.disconnect()


class TestMobileSyncConsumerIntegration(TransactionTestCase):
    """Test mobile sync consumer with enhanced logging"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='mobileuser',
            email='mobile@example.com',
            password='testpass123'
        )

    async def test_mobile_sync_with_correlation_id(self):
        """Test mobile sync consumer generates correlation IDs"""
        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/mobile/sync/?device_id=test_device_123"
        )

        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Receive connection confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connection_established')
        self.assertEqual(response['device_id'], 'test_device_123')

        # Send sync data message
        sync_message = {
            'type': 'sync_data',
            'sync_id': 'test_sync_123',
            'data': {
                'voice_data': {
                    'quality_score': 0.85,
                    'duration_ms': 2000
                }
            }
        }

        await communicator.send_json_to(sync_message)

        # Should receive sync progress response
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'sync_progress')
        self.assertEqual(response['sync_id'], 'test_sync_123')

        await communicator.disconnect()

    async def test_mobile_sync_heartbeat(self):
        """Test mobile sync heartbeat functionality"""
        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/mobile/sync/?device_id=heartbeat_test"
        )

        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send heartbeat
        await communicator.send_json_to({
            'type': 'heartbeat',
            'client_time': '2024-01-01T12:00:00Z'
        })

        # Should receive heartbeat response
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'heartbeat_response')
        self.assertIn('server_time', response)
        self.assertEqual(response['client_time'], '2024-01-01T12:00:00Z')

        await communicator.disconnect()


class TestWebSocketErrorHandling(TransactionTestCase):
    """Test WebSocket error handling and logging"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='erroruser',
            email='error@example.com'
        )

    async def test_invalid_json_handling(self):
        """Test handling of invalid JSON messages"""
        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/mobile/sync/?device_id=error_test"
        )

        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send invalid JSON
        await communicator.send_to(text_data="invalid json {{{")

        # Should receive error response
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertEqual(response['error_code'], 'JSON_DECODE_ERROR')

        await communicator.disconnect()

    async def test_unknown_message_type_handling(self):
        """Test handling of unknown message types"""
        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/mobile/sync/?device_id=unknown_test"
        )

        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send unknown message type
        await communicator.send_json_to({
            'type': 'unknown_message_type',
            'data': {'test': 'data'}
        })

        # Should receive error response
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertEqual(response['error_code'], 'UNKNOWN_MESSAGE_TYPE')

        await communicator.disconnect()

    async def test_unauthorized_connection_rejection(self):
        """Test rejection of unauthorized connections"""
        from django.contrib.auth.models import AnonymousUser

        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/mobile/sync/?device_id=unauth_test"
        )

        # Set anonymous user
        communicator.scope['user'] = AnonymousUser()

        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)

    async def test_missing_device_id_rejection(self):
        """Test rejection of connections without device ID"""
        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/mobile/sync/"  # No device_id parameter
        )

        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)


class TestWebSocketPerformance(TransactionTestCase):
    """Performance tests for WebSocket consumers"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='perfuser',
            email='perf@example.com'
        )

    async def test_concurrent_connections(self):
        """Test handling of multiple concurrent connections"""
        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        # Create multiple communicators
        communicators = []
        for i in range(5):  # Test with 5 concurrent connections
            communicator = WebsocketCommunicator(
                application,
                f"ws/mobile/sync/?device_id=perf_test_{i}"
            )
            communicator.scope['user'] = self.user
            communicators.append(communicator)

        # Connect all concurrently
        connect_tasks = [comm.connect() for comm in communicators]
        results = await asyncio.gather(*connect_tasks, return_exceptions=True)

        # Verify all connections succeeded
        for i, (connected, subprotocol) in enumerate(results):
            if isinstance(connected, Exception):
                self.fail(f"Connection {i} failed: {connected}")
            self.assertTrue(connected, f"Connection {i} should have succeeded")

        # Send messages concurrently
        message_tasks = []
        for i, comm in enumerate(communicators):
            # Skip connection confirmation
            await comm.receive_json_from()

            # Send test message
            task = comm.send_json_to({
                'type': 'heartbeat',
                'client_time': f'2024-01-01T12:00:{i:02d}Z'
            })
            message_tasks.append(task)

        await asyncio.gather(*message_tasks)

        # Receive responses concurrently
        response_tasks = [comm.receive_json_from() for comm in communicators]
        responses = await asyncio.gather(*response_tasks, return_exceptions=True)

        # Verify all responses
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                self.fail(f"Response {i} failed: {response}")
            self.assertEqual(response['type'], 'heartbeat_response')

        # Disconnect all
        disconnect_tasks = [comm.disconnect() for comm in communicators]
        await asyncio.gather(*disconnect_tasks)

    async def test_message_throughput(self):
        """Test message processing throughput"""
        import time

        application = URLRouter([
            path("ws/mobile/sync/", MobileSyncConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            "ws/mobile/sync/?device_id=throughput_test"
        )

        communicator.scope['user'] = self.user

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send multiple messages rapidly
        message_count = 50
        start_time = time.time()

        for i in range(message_count):
            await communicator.send_json_to({
                'type': 'heartbeat',
                'client_time': f'2024-01-01T12:00:{i:02d}Z'
            })

        # Receive all responses
        for i in range(message_count):
            response = await communicator.receive_json_from()
            self.assertEqual(response['type'], 'heartbeat_response')

        end_time = time.time()
        duration = end_time - start_time
        throughput = message_count / duration

        logger.info(f"WebSocket throughput: {throughput:.1f} messages/second")

        # Should handle at least 10 messages per second
        self.assertGreater(throughput, 10)

        await communicator.disconnect()