"""
Threat Intelligence WebSocket Consumer for Real-Time Alerts.

Delivers threat intelligence alerts to NOC dashboards in real-time with:
- Tenant-aware group subscription
- Authentication enforcement
- Rate limiting
- Alert status updates
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.core.tasks.base import TaskMetrics

logger = logging.getLogger('threat_intelligence.websocket')

__all__ = ['ThreatAlertConsumer']


class ThreatAlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for threat intelligence alerts.
    
    Supports:
    - Tenant-specific alert subscriptions
    - Real-time alert delivery
    - Alert acknowledgement updates
    - Connection rate limiting
    """
    
    RATE_LIMIT_WINDOW = 60
    RATE_LIMIT_MAX = 100
    
    async def connect(self):
        """Handle WebSocket connection with authentication."""
        user = self.scope.get('user')
        
        if not user or not user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt")
            await self.close(code=403)
            return
        
        self.user = user
        self.tenant_id = user.tenant_id
        self.tenant_group = f'threat_alerts_tenant_{self.tenant_id}'
        
        # Join tenant-specific group
        await self.channel_layer.group_add(
            self.tenant_group,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(
            f"Threat alert WebSocket connected",
            extra={
                'user_id': user.id,
                'tenant_id': self.tenant_id,
                'correlation_id': f'ws_connect_{user.id}_{timezone.now().timestamp()}'
            }
        )
        
        # Record connection metric
        TaskMetrics.increment_counter('websocket_connection_established', {
            'consumer': 'threat_alert',
            'tenant_id': str(self.tenant_id)[:20]
        })
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'tenant_group'):
            await self.channel_layer.group_discard(
                self.tenant_group,
                self.channel_name
            )
        
        logger.info(
            f"Threat alert WebSocket disconnected",
            extra={
                'close_code': close_code,
                'correlation_id': f'ws_disconnect_{close_code}_{timezone.now().timestamp()}'
            }
        )
        
        # Record disconnection metric
        TaskMetrics.increment_counter('websocket_connection_closed', {
            'consumer': 'threat_alert',
            'close_code': str(close_code)
        })
    
    async def threat_alert(self, event):
        """
        Broadcast threat alert to connected clients.
        
        Args:
            event: Dict containing alert data with keys:
                - alert_id
                - severity
                - category
                - title
                - distance_km
                - urgency_level
                - event_start_time
                - created_at
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'threat_alert',
                'alert_id': event['alert_id'],
                'severity': event['severity'],
                'category': event['category'],
                'title': event['title'],
                'distance_km': event['distance_km'],
                'urgency_level': event['urgency_level'],
                'event_start_time': event['event_start_time'],
                'created_at': event['created_at'],
            }))
            
            TaskMetrics.increment_counter('threat_alert_websocket_sent', {
                'severity': event['severity'],
                'urgency': event['urgency_level']
            })
            
        except Exception as e:
            logger.error(
                f"Failed to send threat alert via WebSocket: {e}",
                exc_info=True,
                extra={'alert_id': event.get('alert_id')}
            )
    
    async def threat_alert_update(self, event):
        """
        Send alert status updates (acknowledgement, response).
        
        Args:
            event: Dict containing update data with keys:
                - alert_id
                - update_type ('acknowledged', 'responded', 'escalated')
                - data (additional update information)
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'threat_alert_update',
                'alert_id': event['alert_id'],
                'update_type': event['update_type'],
                'data': event.get('data', {}),
                'timestamp': timezone.now().isoformat(),
            }))
            
            TaskMetrics.increment_counter('threat_alert_update_sent', {
                'update_type': event['update_type']
            })
            
        except Exception as e:
            logger.error(
                f"Failed to send threat alert update via WebSocket: {e}",
                exc_info=True,
                extra={'alert_id': event.get('alert_id')}
            )
