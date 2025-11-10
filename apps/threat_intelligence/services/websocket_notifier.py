"""
WebSocket Notification Service for Threat Intelligence.

Provides helper methods to broadcast alert updates via WebSocket.
"""

import logging
from typing import Dict, Any
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from apps.threat_intelligence.models import IntelligenceAlert

logger = logging.getLogger(__name__)


class WebSocketNotifier:
    """Service for sending WebSocket notifications to threat alert subscribers."""
    
    @classmethod
    def send_alert_acknowledged(cls, alert: IntelligenceAlert, user_id: int):
        """
        Notify all clients that an alert was acknowledged.
        
        Args:
            alert: The acknowledged alert
            user_id: ID of user who acknowledged
        """
        cls._send_update(
            alert=alert,
            update_type='acknowledged',
            data={
                'acknowledged_by': user_id,
                'acknowledged_at': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def send_alert_responded(cls, alert: IntelligenceAlert, response: str, notes: str = ""):
        """
        Notify all clients of alert response.
        
        Args:
            alert: The alert that was responded to
            response: Response type (ACTIONABLE, FALSE_POSITIVE, etc.)
            notes: Optional response notes
        """
        cls._send_update(
            alert=alert,
            update_type='responded',
            data={
                'response': response,
                'notes': notes,
                'response_timestamp': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def send_alert_escalated(cls, alert: IntelligenceAlert, escalated_to: list):
        """
        Notify all clients that an alert was escalated.
        
        Args:
            alert: The escalated alert
            escalated_to: List of people/roles escalated to
        """
        cls._send_update(
            alert=alert,
            update_type='escalated',
            data={
                'escalation_level': alert.escalation_level,
                'escalated_to': escalated_to,
                'escalated_at': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def send_work_order_created(cls, alert: IntelligenceAlert, work_order_id: int):
        """
        Notify all clients that a work order was created for an alert.
        
        Args:
            alert: The alert
            work_order_id: ID of created work order
        """
        cls._send_update(
            alert=alert,
            update_type='work_order_created',
            data={
                'work_order_id': work_order_id,
                'created_at': timezone.now().isoformat()
            }
        )
    
    @classmethod
    def _send_update(cls, alert: IntelligenceAlert, update_type: str, data: Dict[str, Any]):
        """
        Internal method to send alert updates via WebSocket.
        
        Args:
            alert: The alert being updated
            update_type: Type of update
            data: Update data
        """
        try:
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f"threat_alerts_tenant_{alert.tenant.id}",
                {
                    "type": "threat_alert_update",
                    "alert_id": alert.id,
                    "update_type": update_type,
                    "data": data
                }
            )
            
            logger.info(
                f"WebSocket update sent for alert {alert.id}",
                extra={
                    'tenant_id': alert.tenant.id,
                    'update_type': update_type,
                    'correlation_id': f'alert_update_{alert.id}_{timezone.now().timestamp()}'
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to send WebSocket update for alert {alert.id}: {e}",
                exc_info=True,
                extra={'update_type': update_type}
            )
