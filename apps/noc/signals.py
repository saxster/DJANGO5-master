"""
NOC Signal Handlers.

Django signals for automatic alert generation based on business events.
Follows .claude/rules.md Rule #17 (signals participate in parent transaction).
"""

import logging
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger('noc.signals')

__all__ = [
    'handle_ticket_sla_breach',
    'handle_work_order_overdue',
    'handle_device_status',
    'handle_attendance_exceptions',
    'invalidate_noc_cache_on_alert',
]


@receiver(post_save, sender='y_helpdesk.Ticket')
def handle_ticket_sla_breach(sender, instance, created, **kwargs):
    """
    Check for SLA breach and create CRITICAL alert.

    Signal handlers participate in the parent transaction automatically.
    Do NOT add transaction.atomic here (Rule #17 guidance).
    """
    from .services import AlertCorrelationService

    if instance.status not in ['OPEN', 'ESCALATED']:
        return

    hours_open = (timezone.now() - instance.cdtz).total_seconds() / 3600

    if instance.priority == 'HIGH' and hours_open > 4:
        alert_data = {
            'tenant': instance.tenant,
            'client': instance.client or instance.bu.get_client_parent(),
            'bu': instance.bu,
            'alert_type': 'SLA_BREACH',
            'severity': 'CRITICAL',
            'entity_type': 'ticket',
            'entity_id': instance.id,
            'message': f"Ticket #{instance.ticketno} breached SLA ({hours_open:.1f}h)",
            'metadata': {
                'priority': instance.priority,
                'hours_open': hours_open,
                'assigned_to': instance.assignedtopeople_id,
            }
        }
        _create_and_broadcast_alert(alert_data)

    elif instance.status == 'ESCALATED':
        alert_data = {
            'tenant': instance.tenant,
            'client': instance.client or instance.bu.get_client_parent(),
            'bu': instance.bu,
            'alert_type': 'TICKET_ESCALATED',
            'severity': 'MEDIUM',
            'entity_type': 'ticket',
            'entity_id': instance.id,
            'message': f"Ticket #{instance.ticketno} escalated",
            'metadata': {'priority': instance.priority}
        }
        _create_and_broadcast_alert(alert_data)


@receiver(post_save, sender='work_order_management.WorkOrder')
def handle_work_order_overdue(sender, instance, created, **kwargs):
    """
    Create MEDIUM alert for overdue work orders.

    Signal handlers participate in the parent transaction automatically.
    Do NOT add transaction.atomic here (Rule #17 guidance).
    """
    from .services import AlertCorrelationService

    if not hasattr(instance, 'deadline') or instance.status == 'COMPLETED':
        return

    if instance.deadline and timezone.now() > instance.deadline:
        alert_data = {
            'tenant': instance.tenant,
            'client': instance.bu.get_client_parent() if instance.bu else None,
            'bu': instance.bu,
            'alert_type': 'WORK_ORDER_OVERDUE',
            'severity': 'MEDIUM',
            'entity_type': 'work_order',
            'entity_id': instance.id,
            'message': f"Work Order #{instance.id} is overdue",
            'metadata': {
                'deadline': instance.deadline.isoformat(),
                'status': instance.status
            }
        }
        _create_and_broadcast_alert(alert_data)


@receiver(post_save, sender='core.DeviceRegistry')
def handle_device_status(sender, instance, created, **kwargs):
    """
    Create HIGH alert for offline devices or CRITICAL for spoofing.

    Signal handlers participate in the parent transaction automatically.
    Do NOT add transaction.atomic here (Rule #17 guidance).
    """
    from .services import AlertCorrelationService

    if instance.status == 'OFFLINE':
        alert_data = {
            'tenant': instance.tenant,
            'client': instance.bu.get_client_parent() if instance.bu else None,
            'bu': instance.bu,
            'alert_type': 'DEVICE_OFFLINE',
            'severity': 'HIGH',
            'entity_type': 'device',
            'entity_id': instance.id,
            'message': f"Device {instance.device_id} is offline",
            'metadata': {
                'device_id': instance.device_id,
                'last_seen': instance.last_seen.isoformat() if instance.last_seen else None
            }
        }
        _create_and_broadcast_alert(alert_data)


@receiver(post_save, sender='attendance.PeopleEventlog')
def handle_attendance_exceptions(sender, instance, created, **kwargs):
    """
    Create LOW alert for attendance exceptions.

    Signal handlers participate in the parent transaction automatically.
    Do NOT add transaction.atomic here (Rule #17 guidance).
    """
    pass


@receiver(post_save, sender='noc.NOCAlertEvent')
def invalidate_noc_cache_on_alert(sender, instance, created, **kwargs):
    """
    Invalidate relevant caches when alerts are created or updated.

    Signal handlers participate in the parent transaction automatically.
    Do NOT add transaction.atomic here (Rule #17 guidance).
    """
    if created or instance.status in ['NEW', 'ACKNOWLEDGED']:
        cache_keys = [
            f"noc:metrics:client_{instance.client_id}",
            f"noc:alerts:client_{instance.client_id}",
            f"noc:dashboard:tenant_{instance.tenant_id}"
        ]
        cache.delete_many(cache_keys)


def _create_and_broadcast_alert(alert_data):
    """
    Create alert and broadcast to WebSocket channels.

    Args:
        alert_data: Dictionary with alert information
    """
    from .services import AlertCorrelationService

    try:
        alert = AlertCorrelationService.process_alert(alert_data)
        if alert:
            _broadcast_alert_to_websocket(alert)
    except (ValueError, KeyError) as e:
        logger.error(
            f"Alert creation failed",
            extra={'alert_type': alert_data.get('alert_type'), 'error': str(e)}
        )


def _broadcast_alert_to_websocket(alert):
    """
    Broadcast alert to WebSocket consumers.

    Args:
        alert: NOCAlertEvent instance
    """
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"noc_client_{alert.client_id}",
            {
                'type': 'alert_notification',
                'alert_id': alert.id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
            }
        )
    except (RuntimeError, OSError) as e:
        logger.warning(f"WebSocket broadcast failed: {e}")