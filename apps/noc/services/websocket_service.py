"""
NOC WebSocket Broadcast Service.

Service for broadcasting real-time updates to WebSocket clients via Django Channels.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import logging
from typing import Dict, Any
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.noc.models import NOCAlertEvent, NOCIncident

__all__ = ['NOCWebSocketService']

logger = logging.getLogger('noc.websocket.service')


class NOCWebSocketService:
    """Service for broadcasting NOC events to WebSocket clients."""

    @staticmethod
    def broadcast_alert(alert: NOCAlertEvent):
        """
        Broadcast new alert to relevant WebSocket channels.

        Args:
            alert: NOCAlertEvent instance
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured")
                return

            alert_data = {
                'alert_id': alert.id,
                'type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'entity_type': alert.entity_type,
                'entity_id': alert.entity_id,
                'client': alert.client.buname,
                'site': alert.bu.buname if alert.bu else None,
                'timestamp': alert.cdtz.isoformat()
            }

            async_to_sync(channel_layer.group_send)(
                f"noc_tenant_{alert.tenant_id}",
                {
                    "type": "alert_notification",
                    "alert_id": alert.id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                }
            )

            async_to_sync(channel_layer.group_send)(
                f"noc_client_{alert.client_id}",
                {
                    "type": "alert_notification",
                    "alert_id": alert.id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                }
            )

            logger.info(f"Alert broadcast sent", extra={'alert_id': alert.id, 'severity': alert.severity})

        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to broadcast alert", extra={'alert_id': alert.id, 'error': str(e)})

    @staticmethod
    def broadcast_alert_update(alert: NOCAlertEvent):
        """
        Broadcast alert status update to relevant channels.

        Args:
            alert: NOCAlertEvent instance
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            async_to_sync(channel_layer.group_send)(
                f"noc_tenant_{alert.tenant_id}",
                {
                    "type": "alert_notification",
                    "alert_id": alert.id,
                    "status": alert.status,
                    "message": f"Alert {alert.id} updated to {alert.status}"
                }
            )

            logger.info(f"Alert update broadcast", extra={'alert_id': alert.id, 'status': alert.status})

        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to broadcast alert update", extra={'alert_id': alert.id, 'error': str(e)})

    @staticmethod
    def broadcast_metrics_refresh(client_id: int):
        """
        Trigger dashboard metrics refresh for a client.

        Args:
            client_id: Client business unit ID
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            async_to_sync(channel_layer.group_send)(
                f"noc_client_{client_id}",
                {
                    "type": "alert_notification",
                    "message": "metrics_refresh",
                    "client_id": client_id
                }
            )

            logger.info(f"Metrics refresh broadcast", extra={'client_id': client_id})

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to broadcast metrics refresh", extra={'client_id': client_id, 'error': str(e)})

    @staticmethod
    def broadcast_incident_update(incident: NOCIncident):
        """
        Broadcast incident update to relevant channels.

        Args:
            incident: NOCIncident instance
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            async_to_sync(channel_layer.group_send)(
                f"noc_tenant_{incident.tenant_id}",
                {
                    "type": "alert_notification",
                    "incident_id": incident.id,
                    "state": incident.state,
                    "severity": incident.severity,
                    "title": incident.title
                }
            )

            logger.info(f"Incident update broadcast", extra={'incident_id': incident.id, 'state': incident.state})

        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to broadcast incident update", extra={'incident_id': incident.id, 'error': str(e)})

    @staticmethod
    def broadcast_maintenance_window(window):
        """
        Broadcast maintenance window notification.

        Args:
            window: MaintenanceWindow instance
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            target_group = f"noc_tenant_{window.tenant_id}"
            if window.client_id:
                target_group = f"noc_client_{window.client_id}"

            async_to_sync(channel_layer.group_send)(
                target_group,
                {
                    "type": "alert_notification",
                    "message": "maintenance_window_created",
                    "window_id": window.id,
                    "start_time": window.start_time.isoformat(),
                    "end_time": window.end_time.isoformat()
                }
            )

            logger.info(f"Maintenance window broadcast", extra={'window_id': window.id})

        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to broadcast maintenance window", extra={'error': str(e)})