"""
Tests for WebSocket Message Delivery Service

Tests message acknowledgments, retries, DLQ, and delivery guarantees.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from django.core.cache import cache

from apps.core.services.websocket_delivery_service import (
    WebSocketDeliveryService,
    Message,
    DeliveryStatus,
    delivery_service
)


@pytest.mark.asyncio
class TestMessageDeliveryService:
    """Test message delivery guarantees."""

    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()

    async def test_successful_delivery_with_ack(self):
        """Test successful message delivery with acknowledgment."""
        service = WebSocketDeliveryService()

        message = Message({'type': 'test', 'data': 'hello'})
        send_mock = AsyncMock()

        # Simulate ack in background
        async def simulate_ack():
            await asyncio.sleep(0.1)
            service.acknowledge_message(message.message_id)

        ack_task = asyncio.create_task(simulate_ack())

        # Send message
        result = await service.send_with_guarantee(send_mock, message, timeout=2)

        await ack_task

        assert result is True
        assert message.status == DeliveryStatus.ACKNOWLEDGED
        send_mock.assert_called_once()

    async def test_delivery_without_ack_retries(self):
        """Test that unacknowledged messages are scheduled for retry."""
        service = WebSocketDeliveryService()

        message = Message({'type': 'test'}, max_retries=3)
        send_mock = AsyncMock()

        # Don't send ack - message should timeout
        result = await service.send_with_guarantee(send_mock, message, timeout=1)

        assert result is False
        assert message.status == DeliveryStatus.RETRY
        assert message.retry_count == 1

    async def test_message_moved_to_dlq_after_max_retries(self):
        """Test that failed messages move to DLQ."""
        service = WebSocketDeliveryService()

        message = Message({'type': 'test'}, max_retries=2)
        message.retry_count = 2  # Already retried twice

        service._schedule_retry(message)

        assert message.status == DeliveryStatus.DLQ
        assert message.retry_count == 2

    def test_retry_dlq_message(self):
        """Test retrying messages from DLQ."""
        service = WebSocketDeliveryService()

        message = Message({'type': 'dlq_test'})
        message.status = DeliveryStatus.DLQ

        # Manually add to DLQ
        dlq_key = f"{service.dlq_prefix}{message.message_id}"
        cache.set(dlq_key, message.to_dict())

        # Retry from DLQ
        result = service.retry_dlq_message(message.message_id)

        assert result is True
