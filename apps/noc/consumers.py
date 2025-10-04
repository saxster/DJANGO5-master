"""
NOC WebSocket Consumer for Real-Time Dashboard Updates.

Provides real-time alert notifications and metrics updates to NOC dashboard.
Follows Django Channels best practices with authentication, rate limiting, and error handling.
"""

import json
import logging
from datetime import timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger('noc.websocket')

__all__ = ['NOCDashboardConsumer']


class NOCDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for NOC dashboard real-time updates.

    Supports:
    - Client-specific alert subscriptions
    - Tenant-wide broadcasts
    - Rate limiting (100 msg/min per connection)
    - RBAC scope enforcement
    - Heartbeat for keep-alive
    """

    RATE_LIMIT_WINDOW = 60
    RATE_LIMIT_MAX = 100

    async def connect(self):
        """Handle WebSocket connection with authentication and RBAC."""
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=403)
            return

        if not await self._has_noc_capability(user):
            await self.close(code=403)
            return

        self.user = user
        self.tenant_id = user.tenant_id
        self.message_count = 0
        self.window_start = timezone.now()

        self.tenant_group = f'noc_tenant_{self.tenant_id}'
        await self.channel_layer.group_add(
            self.tenant_group,
            self.channel_name
        )

        await self.accept()
        logger.info(
            f"NOC WebSocket connected",
            extra={'user_id': user.id, 'tenant_id': self.tenant_id}
        )

        await self.send_initial_status()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'tenant_group'):
            await self.channel_layer.group_discard(
                self.tenant_group,
                self.channel_name
            )

        if hasattr(self, 'client_groups'):
            for group in self.client_groups:
                await self.channel_layer.group_discard(
                    group,
                    self.channel_name
                )

        logger.info(
            f"NOC WebSocket disconnected",
            extra={'close_code': close_code}
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        if not await self._check_rate_limit():
            await self.send_error('Rate limit exceeded')
            return

        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            handlers = {
                'subscribe_client': self.handle_subscribe_client,
                'acknowledge_alert': self.handle_acknowledge_alert,
                'request_metrics': self.handle_request_metrics,
                'heartbeat': self.handle_heartbeat,
            }

            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                await self.send_error(f'Unknown message type: {message_type}')

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON data')
        except (ValueError, KeyError) as e:
            await self.send_error(f'Invalid message: {str(e)}')

    async def handle_subscribe_client(self, data):
        """Subscribe to specific client alerts."""
        client_id = data.get('client_id')

        if not client_id:
            await self.send_error('client_id required')
            return

        if not await self._can_view_client(self.user, client_id):
            await self.send_error('Insufficient permissions')
            return

        client_group = f'noc_client_{client_id}'

        if not hasattr(self, 'client_groups'):
            self.client_groups = []

        self.client_groups.append(client_group)

        await self.channel_layer.group_add(
            client_group,
            self.channel_name
        )

        await self.send(text_data=json.dumps({
            'type': 'subscribed',
            'client_id': client_id,
            'message': 'Subscribed to client alerts'
        }))

    async def handle_acknowledge_alert(self, data):
        """Acknowledge an alert via WebSocket."""
        alert_id = data.get('alert_id')

        if not alert_id:
            await self.send_error('alert_id required')
            return

        if not await self._can_acknowledge_alerts(self.user):
            await self.send_error('Cannot acknowledge alerts')
            return

        try:
            await self._acknowledge_alert_db(alert_id, self.user.id)
            await self.send(text_data=json.dumps({
                'type': 'alert_acknowledged',
                'alert_id': alert_id
            }))
        except (ValueError, AttributeError) as e:
            await self.send_error(f'Failed to acknowledge: {str(e)}')

    async def handle_request_metrics(self, data):
        """Request latest metrics for client."""
        client_id = data.get('client_id')

        if not await self._can_view_client(self.user, client_id):
            await self.send_error('Insufficient permissions')
            return

        metrics = await self._get_cached_metrics(client_id)

        await self.send(text_data=json.dumps({
            'type': 'metrics_update',
            'client_id': client_id,
            'metrics': metrics
        }))

    async def handle_heartbeat(self, data):
        """Respond to heartbeat."""
        await self.send(text_data=json.dumps({
            'type': 'heartbeat_ack',
            'timestamp': timezone.now().isoformat()
        }))

    async def alert_notification(self, event):
        """Handle alert broadcast from channel layer."""
        await self.send(text_data=json.dumps({
            'type': 'alert_new',
            'alert_id': event['alert_id'],
            'alert_type': event['alert_type'],
            'severity': event['severity'],
            'message': event['message'],
        }))

    async def send_initial_status(self):
        """Send initial connection status."""
        await self.send(text_data=json.dumps({
            'type': 'connected',
            'tenant_id': self.tenant_id,
            'timestamp': timezone.now().isoformat()
        }))

    async def send_error(self, message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    async def _check_rate_limit(self):
        """Check if message rate limit is exceeded."""
        now = timezone.now()

        if (now - self.window_start).total_seconds() > self.RATE_LIMIT_WINDOW:
            self.message_count = 0
            self.window_start = now

        self.message_count += 1

        return self.message_count <= self.RATE_LIMIT_MAX

    @database_sync_to_async
    def _has_noc_capability(self, user):
        """Check if user has NOC access."""
        return user.has_capability('noc:view')

    @database_sync_to_async
    def _can_view_client(self, user, client_id):
        """Check if user can view specific client."""
        from apps.noc.services import NOCRBACService
        clients = NOCRBACService.get_visible_clients(user)
        return clients.filter(id=client_id).exists()

    @database_sync_to_async
    def _can_acknowledge_alerts(self, user):
        """Check if user can acknowledge alerts."""
        from apps.noc.services import NOCRBACService
        return NOCRBACService.can_acknowledge_alerts(user)

    @database_sync_to_async
    def _acknowledge_alert_db(self, alert_id, user_id):
        """Acknowledge alert in database."""
        from apps.noc.models import NOCAlertEvent
        from apps.peoples.models import People

        alert = NOCAlertEvent.objects.get(id=alert_id)
        alert.status = 'ACKNOWLEDGED'
        alert.acknowledged_at = timezone.now()
        alert.acknowledged_by = People.objects.get(id=user_id)
        alert.save()

    @database_sync_to_async
    def _get_cached_metrics(self, client_id):
        """Get cached metrics for client."""
        from apps.noc.services.cache_service import NOCCacheService
        return NOCCacheService.get_metrics_cached(client_id) or {}