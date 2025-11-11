"""
NOC WebSocket Broadcast Service.

Service for broadcasting real-time updates to WebSocket clients via Django Channels.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import logging
import time
from typing import Dict, Any, Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from apps.noc.models import NOCAlertEvent, NOCIncident, WebSocketConnection
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

__all__ = ['NOCWebSocketService']

logger = logging.getLogger('noc.websocket.service')


class NOCWebSocketService:
    """Service for broadcasting NOC events to WebSocket clients."""

    @staticmethod
    def broadcast_event(event_type: str, event_data: Dict[str, Any], tenant_id: int, site_id: Optional[int] = None):
        """
        Unified event broadcast with audit logging.

        All NOC events route through this method for consistent handling,
        logging, and performance tracking.

        Args:
            event_type: Type discriminator (alert_created, finding_created, etc.)
            event_data: Event payload data
            tenant_id: Tenant ID for tenant-scoped broadcast
            site_id: Optional site ID for site-scoped broadcast

        TASK 11: Gap #14 - Consolidated NOC Event Feed
        """
        try:
            start_time = time.time()

            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured")
                return

            # Create unified event structure with type discriminator
            unified_event = {
                "type": event_type,
                "timestamp": timezone.now().isoformat(),
                "tenant_id": tenant_id,
                **event_data
            }

            # Broadcast to tenant group
            async_to_sync(channel_layer.group_send)(
                f"noc_tenant_{tenant_id}",
                unified_event
            )

            # Broadcast to site group if applicable
            if site_id:
                async_to_sync(channel_layer.group_send)(
                    f"noc_site_{site_id}",
                    unified_event
                )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Count actual recipients from WebSocket connections
            recipient_count = WebSocketConnection.get_group_member_count(
                group_name=f"noc_tenant_{tenant_id}",
                tenant_id=tenant_id
            )

            # Log event to NOCEventLog for audit trail
            from apps.noc.models import NOCEventLog
            NOCEventLog.objects.create(
                event_type=event_type,
                tenant_id=tenant_id,
                payload=event_data,
                broadcast_latency_ms=latency_ms,
                broadcast_success=True,
                alert_id=event_data.get('alert_id'),
                finding_id=event_data.get('finding_id'),
                ticket_id=event_data.get('ticket_id'),
                recipient_count=recipient_count  # Actual WebSocket connection count
            )

            logger.info(
                f"Event broadcast: {event_type} ({latency_ms}ms)",
                extra={'event_type': event_type, 'latency_ms': latency_ms, 'tenant_id': tenant_id}
            )

        except (ValueError, AttributeError, TypeError) as e:
            logger.error(
                f"Failed to broadcast event {event_type}: {e}",
                extra={'event_type': event_type, 'tenant_id': tenant_id, 'error': str(e)}
            )
            # Log failure for forensic analysis
            try:
                from apps.noc.models import NOCEventLog
                NOCEventLog.objects.create(
                    event_type=event_type,
                    tenant_id=tenant_id,
                    payload=event_data,
                    broadcast_success=False,
                    error_message=str(e)
                )
            except DATABASE_EXCEPTIONS:
                pass  # Best effort logging

    @staticmethod
    def broadcast_alert(alert: NOCAlertEvent):
        """
        Broadcast new alert to relevant WebSocket channels.

        Args:
            alert: NOCAlertEvent instance

        Refactored to use unified broadcast_event().
        """
        NOCWebSocketService.broadcast_event(
            event_type='alert_created',
            event_data={
                'alert_id': alert.id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'entity_type': alert.entity_type,
                'entity_id': alert.entity_id,
                'client_name': alert.client.buname if alert.client else None,
                'site_name': alert.bu.buname if alert.bu else None,
            },
            tenant_id=alert.tenant_id,
            site_id=alert.bu_id if alert.bu else None
        )

    @staticmethod
    def broadcast_alert_update(alert: NOCAlertEvent):
        """
        Broadcast alert status update to relevant channels.

        Args:
            alert: NOCAlertEvent instance

        Refactored to use unified broadcast_event().
        """
        NOCWebSocketService.broadcast_event(
            event_type='alert_updated',
            event_data={
                'alert_id': alert.id,
                'status': alert.status,
                'message': f"Alert {alert.id} updated to {alert.status}"
            },
            tenant_id=alert.tenant_id,
            site_id=alert.bu_id if alert.bu else None
        )

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

    @staticmethod
    def broadcast_finding(finding):
        """
        Broadcast audit finding creation to relevant channels.

        Args:
            finding: AuditFinding instance

        Refactored to use unified broadcast_event().
        """
        NOCWebSocketService.broadcast_event(
            event_type='finding_created',
            event_data={
                'finding_id': finding.id,
                'finding_type': finding.finding_type,
                'severity': finding.severity,
                'category': finding.category,
                'site_id': finding.site.id if finding.site else None,
                'site_name': finding.site.buname if finding.site else None,
                'title': finding.title,
                'evidence_summary': finding.evidence_summary[:200] if finding.evidence_summary else "",
                'detected_at': finding.cdtz.isoformat()
            },
            tenant_id=finding.tenant_id,
            site_id=finding.site.id if finding.site else None
        )

    @staticmethod
    def broadcast_anomaly(anomaly):
        """
        Broadcast attendance anomaly detection to relevant channels.

        Args:
            anomaly: AttendanceAnomalyLog instance

        Refactored to use unified broadcast_event().
        """
        NOCWebSocketService.broadcast_event(
            event_type='anomaly_detected',
            event_data={
                'anomaly_id': str(anomaly.id),
                'person_id': anomaly.person.id,
                'person_name': anomaly.person.peoplename,
                'site_id': anomaly.site.id,
                'site_name': anomaly.site.buname,
                'anomaly_type': anomaly.anomaly_type,
                'fraud_score': getattr(anomaly, 'fraud_score', 0.0),
                'severity': anomaly.severity,
                'timestamp': anomaly.detected_at.isoformat()
            },
            tenant_id=anomaly.tenant_id,
            site_id=anomaly.site.id if anomaly.site else None
        )

    @staticmethod
    def broadcast_ticket_update(ticket, old_status):
        """
        Broadcast ticket state change to relevant channels.

        Args:
            ticket: Ticket instance
            old_status: Previous ticket status

        TASK 10: Gap #13 - Ticket State Change Broadcasts
        Refactored to use unified broadcast_event().
        """
        NOCWebSocketService.broadcast_event(
            event_type='ticket_updated',
            event_data={
                'ticket_id': ticket.id,
                'ticket_no': ticket.ticketno,
                'old_status': old_status,
                'new_status': ticket.status,
                'priority': ticket.priority,
                'assigned_to': ticket.assignedtopeople.peoplename if ticket.assignedtopeople else None,
                'site_id': ticket.bu.id if ticket.bu else None,
                'site_name': ticket.bu.buname if ticket.bu else None,
                'description': ticket.ticketdesc[:200] if ticket.ticketdesc else "",
                'updated_at': ticket.mdtz.isoformat()
            },
            tenant_id=ticket.tenant_id,
            site_id=ticket.bu.id if ticket.bu else None
        )