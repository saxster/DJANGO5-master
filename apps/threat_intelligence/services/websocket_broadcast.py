"""
WebSocket Broadcast Service for Threat Alerts.

Broadcasts threat intelligence alerts to NOC dashboard via WebSocket.
Follows .claude/rules.md standards (no global state, specific exceptions).
"""

import logging
from typing import Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.threat_intelligence.models import IntelligenceAlert
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

logger = logging.getLogger('threat_intelligence.websocket')

__all__ = ['ThreatAlertWebSocketBroadcaster']


class ThreatAlertWebSocketBroadcaster:
    """Service for broadcasting threat alerts via WebSocket."""

    @classmethod
    def broadcast_new_alert(cls, alert: IntelligenceAlert) -> bool:
        """
        Broadcast new threat alert to NOC dashboard.
        
        Args:
            alert: IntelligenceAlert instance to broadcast
            
        Returns:
            True if broadcast succeeded, False otherwise
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured - WebSocket broadcast disabled")
                return False

            tenant_group = f'threat_alerts_tenant_{alert.tenant_id}'
            
            alert_data = cls._serialize_alert(alert)
            
            async_to_sync(channel_layer.group_send)(
                tenant_group,
                {
                    'type': 'new_threat_alert',
                    'alert': alert_data
                }
            )

            logger.info(
                f"Broadcast new threat alert to tenant {alert.tenant_id}",
                extra={
                    'alert_id': alert.id,
                    'severity': alert.severity,
                    'tenant_id': alert.tenant_id
                }
            )
            return True

        except NETWORK_EXCEPTIONS as e:
            logger.error(
                f"Failed to broadcast threat alert: {e}",
                extra={'alert_id': alert.id},
                exc_info=True
            )
            return False

    @classmethod
    def broadcast_alert_acknowledged(cls, alert_id: int, tenant_id: int, acknowledged_by: Optional[str] = None) -> bool:
        """
        Notify clients that alert was acknowledged.
        
        Args:
            alert_id: ID of acknowledged alert
            tenant_id: Tenant ID for group routing
            acknowledged_by: Username of acknowledging user
            
        Returns:
            True if broadcast succeeded, False otherwise
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return False

            tenant_group = f'threat_alerts_tenant_{tenant_id}'
            
            async_to_sync(channel_layer.group_send)(
                tenant_group,
                {
                    'type': 'alert_acknowledged',
                    'alert_id': alert_id,
                    'acknowledged_by': acknowledged_by
                }
            )

            logger.info(
                f"Broadcast alert acknowledgment to tenant {tenant_id}",
                extra={'alert_id': alert_id}
            )
            return True

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Failed to broadcast acknowledgment: {e}", exc_info=True)
            return False

    @classmethod
    def _serialize_alert(cls, alert: IntelligenceAlert) -> dict:
        """
        Serialize alert for WebSocket transmission.
        
        Args:
            alert: IntelligenceAlert instance
            
        Returns:
            Dictionary with alert data
        """
        return {
            'id': alert.id,
            'severity': alert.severity,
            'urgency_level': alert.urgency_level,
            'distance_km': alert.distance_km,
            'created_at': alert.created_at.isoformat(),
            'threat_event': {
                'id': alert.threat_event.id,
                'title': alert.threat_event.title,
                'description': alert.threat_event.description,
                'incident_type': getattr(alert.threat_event, 'incident_type', None),
                'location': getattr(alert.threat_event, 'location', None),
            }
        }
