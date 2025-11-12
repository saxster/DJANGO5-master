"""
Tests for Consolidated NOC Event Feed.

TASK 11: Gap #14 - Unified event broadcast and routing system.
Tests unified broadcast_event(), event logging, type dispatch, and backward compatibility.

Follows .claude/rules.md Rule #7 (< 150 lines per class), Rule #11 (specific exceptions).
"""

import pytest
import json
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer

from apps.noc.services.websocket_service import NOCWebSocketService
from apps.noc.models import NOCEventLog, NOCAlertEvent
from apps.noc.consumers.noc_dashboard_consumer import NOCDashboardConsumer


@pytest.mark.django_db
class TestUnifiedEventBroadcast:
    """Test unified broadcast_event() method."""

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_broadcast_event_creates_unified_structure(self, mock_channel_layer, tenant):
        """Test that broadcast_event creates unified event structure with type discriminator."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        event_data = {
            'alert_id': 123,
            'severity': 'HIGH',
            'message': 'Test alert'
        }

        NOCWebSocketService.broadcast_event(
            event_type='alert_created',
            event_data=event_data,
            tenant_id=tenant.id,
            site_id=None
        )

        # Verify group_send was called with unified structure
        assert mock_layer.group_send.called
        call_args = mock_layer.group_send.call_args[0]

        # Check group name
        assert call_args[0] == f"noc_tenant_{tenant.id}"

        # Check unified event structure
        unified_event = call_args[1]
        assert unified_event['type'] == 'alert_created'
        assert 'timestamp' in unified_event
        assert unified_event['tenant_id'] == tenant.id
        assert unified_event['alert_id'] == 123
        assert unified_event['severity'] == 'HIGH'

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_broadcast_event_broadcasts_to_tenant_and_site_groups(self, mock_channel_layer, tenant):
        """Test that broadcast_event sends to both tenant and site groups when site_id provided."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        NOCWebSocketService.broadcast_event(
            event_type='finding_created',
            event_data={'finding_id': 456},
            tenant_id=tenant.id,
            site_id=789
        )

        # Should be called twice: once for tenant group, once for site group
        assert mock_layer.group_send.call_count == 2

        # Verify tenant group call
        tenant_call = mock_layer.group_send.call_args_list[0][0]
        assert tenant_call[0] == f"noc_tenant_{tenant.id}"

        # Verify site group call
        site_call = mock_layer.group_send.call_args_list[1][0]
        assert site_call[0] == "noc_site_789"

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_broadcast_event_handles_missing_channel_layer(self, mock_channel_layer, tenant):
        """Test graceful handling when channel layer is not configured."""
        mock_channel_layer.return_value = None

        # Should not raise exception
        NOCWebSocketService.broadcast_event(
            event_type='alert_created',
            event_data={'alert_id': 1},
            tenant_id=tenant.id
        )

        # No event log should be created if channel layer is missing
        assert NOCEventLog.objects.count() == 0


@pytest.mark.django_db
class TestEventLogging:
    """Test NOCEventLog audit trail creation."""

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_successful_broadcast_creates_event_log(self, mock_channel_layer, tenant):
        """Test that successful broadcasts create NOCEventLog entries."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        NOCWebSocketService.broadcast_event(
            event_type='anomaly_detected',
            event_data={
                'anomaly_id': '123e4567-e89b-12d3-a456-426614174000',
                'severity': 'HIGH'
            },
            tenant_id=tenant.id
        )

        # Verify event log created
        event_log = NOCEventLog.objects.get(tenant=tenant)
        assert event_log.event_type == 'anomaly_detected'
        assert event_log.broadcast_success is True
        assert event_log.broadcast_latency_ms is not None
        assert event_log.broadcast_latency_ms > 0
        assert event_log.payload['anomaly_id'] == '123e4567-e89b-12d3-a456-426614174000'

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_failed_broadcast_logs_error(self, mock_channel_layer, tenant):
        """Test that failed broadcasts log error messages."""
        mock_layer = MagicMock()
        mock_layer.group_send.side_effect = ValueError("Broadcast failed")
        mock_channel_layer.return_value = mock_layer

        NOCWebSocketService.broadcast_event(
            event_type='ticket_updated',
            event_data={'ticket_id': 999},
            tenant_id=tenant.id
        )

        # Verify failure logged
        event_log = NOCEventLog.objects.get(tenant=tenant)
        assert event_log.event_type == 'ticket_updated'
        assert event_log.broadcast_success is False
        assert 'Broadcast failed' in event_log.error_message

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_event_log_tracks_latency(self, mock_channel_layer, tenant):
        """Test that event log tracks broadcast latency in milliseconds."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        NOCWebSocketService.broadcast_event(
            event_type='alert_created',
            event_data={'alert_id': 1},
            tenant_id=tenant.id
        )

        event_log = NOCEventLog.objects.get(tenant=tenant)
        assert event_log.broadcast_latency_ms is not None
        assert isinstance(event_log.broadcast_latency_ms, int)
        assert event_log.broadcast_latency_ms >= 0


@pytest.mark.django_db
class TestTypeDispatch:
    """Test event type routing in consumer."""

    @pytest.mark.asyncio
    async def test_handle_noc_event_routes_to_correct_handler(self):
        """Test that handle_noc_event routes events to correct handlers based on type."""
        consumer = NOCDashboardConsumer()
        consumer.send = Mock()

        # Mock handlers
        consumer.alert_created = Mock()
        consumer.finding_created = Mock()
        consumer.anomaly_detected = Mock()
        consumer.ticket_updated = Mock()

        # Test alert routing
        await consumer.handle_noc_event({'type': 'alert_created', 'alert_id': 1})
        consumer.alert_created.assert_called_once()

        # Test finding routing
        await consumer.handle_noc_event({'type': 'finding_created', 'finding_id': 2})
        consumer.finding_created.assert_called_once()

        # Test anomaly routing
        await consumer.handle_noc_event({'type': 'anomaly_detected', 'anomaly_id': 3})
        consumer.anomaly_detected.assert_called_once()

        # Test ticket routing
        await consumer.handle_noc_event({'type': 'ticket_updated', 'ticket_id': 4})
        consumer.ticket_updated.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_noc_event_fallback_for_unknown_types(self):
        """Test fallback handling for unknown event types."""
        consumer = NOCDashboardConsumer()
        consumer.send = Mock()

        # Unknown event type should use fallback
        unknown_event = {'type': 'unknown_event_type', 'data': 'test'}
        await consumer.handle_noc_event(unknown_event)

        # Verify fallback sends raw event
        consumer.send.assert_called_once()
        call_args = consumer.send.call_args[1]
        sent_data = json.loads(call_args['text_data'])
        assert sent_data['type'] == 'unknown_event_type'

    @pytest.mark.asyncio
    async def test_ticket_updated_handler_sends_correct_format(self):
        """Test that ticket_updated handler sends correct event format to client."""
        consumer = NOCDashboardConsumer()
        consumer.send = Mock()

        event = {
            'type': 'ticket_updated',
            'ticket_id': 123,
            'ticket_no': 'TKT-001',
            'old_status': 'NEW',
            'new_status': 'IN_PROGRESS',
            'priority': 'HIGH',
            'assigned_to': 'John Doe',
            'site_id': 456,
            'site_name': 'Site A',
            'description': 'Test ticket',
            'updated_at': '2025-11-02T10:00:00Z',
            'timestamp': '2025-11-02T10:00:00Z'
        }

        await consumer.ticket_updated(event)

        consumer.send.assert_called_once()
        call_args = consumer.send.call_args[1]
        sent_data = json.loads(call_args['text_data'])

        assert sent_data['type'] == 'ticket_updated'
        assert sent_data['ticket_id'] == 123
        assert sent_data['old_status'] == 'NEW'
        assert sent_data['new_status'] == 'IN_PROGRESS'


@pytest.mark.django_db
class TestBackwardCompatibility:
    """Test backward compatibility with legacy broadcast methods."""

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_broadcast_alert_uses_unified_event(self, mock_channel_layer, noc_alert_event):
        """Test that broadcast_alert refactored to use broadcast_event."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        NOCWebSocketService.broadcast_alert(noc_alert_event)

        # Verify unified broadcast was called
        assert mock_layer.group_send.called
        call_args = mock_layer.group_send.call_args[0]
        unified_event = call_args[1]

        assert unified_event['type'] == 'alert_created'
        assert unified_event['alert_id'] == noc_alert_event.id
        assert 'timestamp' in unified_event

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_legacy_methods_create_event_logs(self, mock_channel_layer, noc_alert_event, tenant):
        """Test that legacy broadcast methods still create event logs via unified system."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        noc_alert_event.tenant = tenant
        noc_alert_event.save()

        NOCWebSocketService.broadcast_alert(noc_alert_event)

        # Verify event log created
        event_log = NOCEventLog.objects.filter(tenant=tenant).first()
        assert event_log is not None
        assert event_log.event_type == 'alert_created'
        assert event_log.alert_id == noc_alert_event.id

    @pytest.mark.asyncio
    async def test_alert_notification_backward_compatibility(self):
        """Test that legacy alert_notification handler routes to unified system."""
        consumer = NOCDashboardConsumer()
        consumer.handle_noc_event = Mock()

        legacy_event = {
            'type': 'alert_notification',
            'alert_id': 123,
            'message': 'Test'
        }

        await consumer.alert_notification(legacy_event)

        # Should route to handle_noc_event
        consumer.handle_noc_event.assert_called_once()


@pytest.mark.django_db
class TestRateLimiting:
    """Test event broadcast rate limiting and performance."""

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_multiple_events_maintain_performance(self, mock_channel_layer, tenant):
        """Test that broadcasting multiple events maintains acceptable latency."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        # Broadcast 10 events
        for i in range(10):
            NOCWebSocketService.broadcast_event(
                event_type='alert_created',
                event_data={'alert_id': i},
                tenant_id=tenant.id
            )

        # All should have acceptable latency (< 100ms)
        event_logs = NOCEventLog.objects.filter(tenant=tenant)
        assert event_logs.count() == 10

        for log in event_logs:
            assert log.broadcast_latency_ms < 100  # Reasonable threshold

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_event_log_stats_aggregation(self, mock_channel_layer, tenant):
        """Test NOCEventLog.get_broadcast_stats() for monitoring."""
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        # Create mix of event types
        for event_type in ['alert_created', 'finding_created', 'anomaly_detected']:
            NOCWebSocketService.broadcast_event(
                event_type=event_type,
                event_data={'id': 1},
                tenant_id=tenant.id
            )

        stats = NOCEventLog.get_broadcast_stats(tenant, hours=24)

        assert stats['total_events'] == 3
        assert stats['avg_latency_ms'] is not None
        assert len(stats['by_type']) == 3
        assert stats['failed_broadcasts'] == 0
