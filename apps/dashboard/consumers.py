"""
Command Center WebSocket Consumer.

Provides real-time updates to command center dashboard via WebSocket.

Events pushed to clients:
- alert.created
- device.health_change
- sla.risk_change
- sos.triggered
- attendance.anomaly
- tour.overdue

Following CLAUDE.md:
- Rule #11: Specific exception handling
- Rule #19: Idempotent message handling
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from apps.core.exceptions.patterns import SERIALIZATION_EXCEPTIONS


logger = logging.getLogger(__name__)


class CommandCenterConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time command center updates.

    Groups:
    - command_center_{tenant_id} - Tenant-specific updates
    """

    async def connect(self):
        """
        Handle WebSocket connection.

        Authenticates user and joins tenant group.
        """
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            logger.warning(
                "command_center_connection_rejected_unauthenticated",
                extra={'ip': self.scope.get('client', ['unknown'])[0]}
            )
            await self.close()
            return

        # Get tenant_id from user
        self.tenant_id = await self.get_user_tenant()
        
        if not self.tenant_id:
            logger.warning(
                "command_center_connection_rejected_no_tenant",
                extra={'user': self.user.username}
            )
            await self.close()
            return

        # Join tenant group
        self.group_name = f"command_center_{self.tenant_id}"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        logger.info(
            "command_center_connected",
            extra={
                'user': self.user.username,
                'tenant_id': self.tenant_id,
                'channel': self.channel_name
            }
        )

        # Send initial data
        await self.send_initial_data()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnect."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

            logger.info(
                "command_center_disconnected",
                extra={
                    'user': self.user.username if hasattr(self, 'user') else 'unknown',
                    'tenant_id': getattr(self, 'tenant_id', None),
                    'close_code': close_code
                }
            )

    async def receive(self, text_data):
        """
        Handle messages from WebSocket.

        Supported commands:
        - refresh: Force refresh of all data
        - subscribe: Subscribe to specific event types
        """
        try:
            data = json.loads(text_data)
            command = data.get('command')

            if command == 'refresh':
                await self.send_initial_data()
            
            elif command == 'subscribe':
                event_types = data.get('event_types', [])
                await self.update_subscription(event_types)

            elif command == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat()
                }))

        except json.JSONDecodeError:
            logger.warning(
                "command_center_invalid_json",
                extra={'user': self.user.username, 'data': text_data}
            )
        except SERIALIZATION_EXCEPTIONS as e:
            logger.error(
                "command_center_receive_error",
                extra={'user': self.user.username, 'error': str(e)},
                exc_info=True
            )

    async def send_initial_data(self):
        """Send initial command center data on connection."""
        from apps.dashboard.services.command_center_service import CommandCenterService
        
        try:
            # Get summary data (will use cache if available)
            summary = await database_sync_to_async(
                CommandCenterService.get_live_summary
            )(self.tenant_id)

            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': summary
            }))

        except SERIALIZATION_EXCEPTIONS as e:
            logger.error(
                "command_center_initial_data_error",
                extra={'tenant_id': self.tenant_id, 'error': str(e)},
                exc_info=True
            )

    async def update_subscription(self, event_types: list):
        """Update event type subscriptions."""
        # Store subscription preferences in channel state
        self.subscribed_events = event_types

        logger.info(
            "command_center_subscription_updated",
            extra={
                'user': self.user.username,
                'event_types': event_types
            }
        )

    # Event handlers for different event types

    async def alert_created(self, event):
        """Handle alert.created event."""
        if self.should_send_event('alert.created'):
            await self.send(text_data=json.dumps({
                'type': 'alert.created',
                'data': event['data']
            }))

    async def device_health_change(self, event):
        """Handle device.health_change event."""
        if self.should_send_event('device.health_change'):
            await self.send(text_data=json.dumps({
                'type': 'device.health_change',
                'data': event['data']
            }))

    async def sla_risk_change(self, event):
        """Handle sla.risk_change event."""
        if self.should_send_event('sla.risk_change'):
            await self.send(text_data=json.dumps({
                'type': 'sla.risk_change',
                'data': event['data']
            }))

    async def sos_triggered(self, event):
        """Handle sos.triggered event (always sent, critical)."""
        await self.send(text_data=json.dumps({
            'type': 'sos.triggered',
            'data': event['data']
        }))

    async def attendance_anomaly(self, event):
        """Handle attendance.anomaly event."""
        if self.should_send_event('attendance.anomaly'):
            await self.send(text_data=json.dumps({
                'type': 'attendance.anomaly',
                'data': event['data']
            }))

    async def tour_overdue(self, event):
        """Handle tour.overdue event."""
        if self.should_send_event('tour.overdue'):
            await self.send(text_data=json.dumps({
                'type': 'tour.overdue',
                'data': event['data']
            }))

    async def summary_update(self, event):
        """Handle summary statistics update."""
        await self.send(text_data=json.dumps({
            'type': 'summary.update',
            'data': event['data']
        }))

    def should_send_event(self, event_type: str) -> bool:
        """Check if event should be sent based on subscription."""
        if not hasattr(self, 'subscribed_events'):
            return True  # Send all events if no subscription set
        
        return event_type in self.subscribed_events

    @database_sync_to_async
    def get_user_tenant(self):
        """Get tenant ID from user."""
        if hasattr(self.user, 'tenant_id'):
            return self.user.tenant_id
        elif hasattr(self.user, 'peopleorganizational'):
            return self.user.peopleorganizational.bu_id
        return None


# Helper function to send events to command center
def send_command_center_event(tenant_id: int, event_type: str, data: dict):
    """
    Send event to all connected command center clients for a tenant.

    Args:
        tenant_id: Tenant identifier
        event_type: Event type (e.g., 'alert.created')
        data: Event data dictionary

    Usage:
        from apps.dashboard.consumers import send_command_center_event
        
        send_command_center_event(
            tenant_id=1,
            event_type='alert.created',
            data={'alert_id': 123, 'severity': 'HIGH', ...}
        )
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    
    if not channel_layer:
        logger.warning(
            "command_center_no_channel_layer",
            extra={'tenant_id': tenant_id, 'event_type': event_type}
        )
        return

    group_name = f"command_center_{tenant_id}"
    
    # Convert event_type to method name (e.g., alert.created -> alert_created)
    method_name = event_type.replace('.', '_')

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': method_name,
            'data': data
        }
    )

    logger.info(
        "command_center_event_sent",
        extra={
            'tenant_id': tenant_id,
            'event_type': event_type,
            'group_name': group_name
        }
    )
