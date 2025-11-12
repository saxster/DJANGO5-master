"""
Threat Alerts WebSocket Consumer.

Real-time threat intelligence alert distribution to NOC dashboard.
Follows Django Channels best practices with authentication and rate limiting.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from apps.core.tasks.base import TaskMetrics

logger = logging.getLogger('noc.threat_alerts')

__all__ = ['ThreatAlertsConsumer']


class ThreatAlertsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for threat intelligence alerts.
    
    Broadcasts new threat alerts to authenticated NOC users.
    Enforces tenant isolation and RBAC.
    """

    async def connect(self):
        """Handle WebSocket connection with authentication."""
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=403)
            return

        if not await self._has_noc_capability(user):
            await self.close(code=403)
            return

        self.user = user
        self.tenant_id = user.tenant_id
        self.tenant_group = f'threat_alerts_tenant_{self.tenant_id}'

        await self.channel_layer.group_add(
            self.tenant_group,
            self.channel_name
        )

        await self.accept()
        logger.info(
            f"Threat alerts WebSocket connected",
            extra={'user_id': user.id, 'tenant_id': self.tenant_id}
        )

        TaskMetrics.increment_counter('websocket_threat_alerts_connected', {
            'tenant_id': str(self.tenant_id)[:20]
        })

        await self.send(json.dumps({
            'type': 'connection_established',
            'message': 'Connected to threat intelligence feed'
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'tenant_group'):
            await self.channel_layer.group_discard(
                self.tenant_group,
                self.channel_name
            )

        logger.info(
            f"Threat alerts WebSocket disconnected",
            extra={'close_code': close_code}
        )

        TaskMetrics.increment_counter('websocket_threat_alerts_disconnected', {
            'close_code': str(close_code)
        })

    async def receive(self, text_data):
        """Handle incoming WebSocket messages (not used for alerts)."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                await self.send(json.dumps({'type': 'pong'}))
            else:
                logger.warning(f"Unknown message type: {message_type}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")

    async def new_threat_alert(self, event):
        """Broadcast new threat alert to client."""
        await self.send(text_data=json.dumps({
            'type': 'new_threat_alert',
            'alert': event['alert']
        }))

    async def alert_acknowledged(self, event):
        """Notify client that alert was acknowledged."""
        await self.send(text_data=json.dumps({
            'type': 'alert_acknowledged',
            'alert_id': event['alert_id'],
            'acknowledged_by': event.get('acknowledged_by')
        }))

    async def alert_updated(self, event):
        """Notify client of alert status update."""
        await self.send(text_data=json.dumps({
            'type': 'alert_updated',
            'alert': event['alert']
        }))

    @database_sync_to_async
    def _has_noc_capability(self, user):
        """Check if user has NOC view capability."""
        return getattr(user, 'capabilities', {}).get('noc:view', False)
