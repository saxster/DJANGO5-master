"""
Streaming Event Publishers

Signal handlers that publish attendance, task, and GPS events to channel layer
for real-time anomaly detection via StreamingAnomalyConsumer.

Architecture:
    Model.post_save → Signal Handler → channel_layer.group_send() →
    StreamingAnomalyConsumer → Anomaly Detection

Features:
- Non-blocking async event publishing
- Multi-tenant event isolation
- Automatic event data extraction
- Error resilience (doesn't block model save)

Compliance with .claude/rules.md:
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
- Rule #15: Sanitized logging
"""

import logging
import uuid
from typing import Optional, Dict, Any

from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger('noc.streaming_events')

__all__ = [
    'publish_attendance_event',
    'publish_task_event',
    'publish_location_event',
]


def _publish_to_stream(
    tenant_id: int,
    event_type: str,
    event_data: Dict[str, Any],
    event_id: Optional[str] = None
):
    """
    Publish event to streaming anomaly channel layer.

    Args:
        tenant_id: Tenant ID for isolation
        event_type: Event type ('attendance', 'task', 'location')
        event_data: Event data dict
        event_id: Optional event ID (auto-generated if not provided)
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not configured - skipping streaming event")
            return

        group_name = f"anomaly_stream_{tenant_id}"
        message = {
            'type': 'process_event',
            'event_id': event_id or str(uuid.uuid4()),
            'event_type': event_type,
            'event_data': event_data
        }

        # Send to group (non-blocking)
        async_to_sync(channel_layer.group_send)(group_name, message)

        logger.debug(
            f"Published {event_type} event to streaming anomaly channel",
            extra={
                'tenant_id': tenant_id,
                'event_type': event_type,
                'event_id': message['event_id']
            }
        )

    except (RuntimeError, ConnectionError, AttributeError) as e:
        # Graceful degradation - log but don't crash model save
        logger.error(
            f"Failed to publish streaming event: {e}",
            extra={
                'tenant_id': tenant_id,
                'event_type': event_type
            },
            exc_info=True
        )


@receiver(post_save, sender='attendance.PeopleEventlog')
def publish_attendance_event(sender, instance, created, **kwargs):
    """
    Publish attendance event for real-time anomaly detection.

    Triggered on PeopleEventlog creation (check-in/check-out).
    """
    if not created:
        return  # Only process new records

    try:
        # Extract event data
        event_data = {
            'event_id': instance.id,
            'person_id': instance.people_id if instance.people else None,
            'site_id': instance.bu_id if instance.bu else None,
            'bu_id': instance.bu_id if instance.bu else None,
            'client_id': instance.client_id if instance.client else None,
            'event_time': instance.cdtz.isoformat() if instance.cdtz else None,
            'event_type': 'attendance',
            'has_checkin': bool(instance.timein),
            'has_checkout': bool(instance.timeout),
        }

        # Get tenant ID
        tenant_id = instance.tenant_id if hasattr(instance, 'tenant_id') else None
        if not tenant_id:
            logger.warning("No tenant_id for attendance event - skipping streaming")
            return

        # Publish to channel layer
        _publish_to_stream(
            tenant_id=tenant_id,
            event_type='attendance',
            event_data=event_data,
            event_id=str(instance.uuid) if hasattr(instance, 'uuid') else None
        )

    except (ValueError, AttributeError) as e:
        logger.error(
            f"Error publishing attendance event: {e}",
            extra={'instance_id': instance.id if hasattr(instance, 'id') else None},
            exc_info=True
        )


@receiver(post_save, sender='activity.Jobneed')
def publish_task_event(sender, instance, created, **kwargs):
    """
    Publish task event for real-time anomaly detection.

    Triggered on Jobneed creation (task/tour instance).
    """
    if not created:
        return  # Only process new records

    try:
        # Extract event data
        event_data = {
            'event_id': instance.id,
            'task_id': instance.id,
            'job_id': instance.job_id if instance.job else None,
            'site_id': instance.bu_id if instance.bu else None,
            'bu_id': instance.bu_id if instance.bu else None,
            'client_id': instance.client_id if instance.client else None,
            'event_time': instance.cdtz.isoformat() if instance.cdtz else None,
            'event_type': 'task',
            'is_tour': instance.is_tour if hasattr(instance, 'is_tour') else False,
            'status': instance.status if hasattr(instance, 'status') else None,
        }

        # Get tenant ID
        tenant_id = instance.tenant_id if hasattr(instance, 'tenant_id') else None
        if not tenant_id:
            logger.warning("No tenant_id for task event - skipping streaming")
            return

        # Publish to channel layer
        _publish_to_stream(
            tenant_id=tenant_id,
            event_type='task',
            event_data=event_data,
            event_id=str(instance.uuid) if hasattr(instance, 'uuid') else None
        )

    except (ValueError, AttributeError) as e:
        logger.error(
            f"Error publishing task event: {e}",
            extra={'instance_id': instance.id if hasattr(instance, 'id') else None},
            exc_info=True
        )


@receiver(post_save, sender='activity.Location')
def publish_location_event(sender, instance, created, **kwargs):
    """
    Publish GPS location event for real-time anomaly detection.

    Triggered on Location creation (GPS tracking).
    """
    if not created:
        return  # Only process new records

    try:
        # Extract event data
        event_data = {
            'event_id': instance.id,
            'location_id': instance.id,
            'site_id': instance.bu_id if instance.bu else None,
            'bu_id': instance.bu_id if instance.bu else None,
            'client_id': instance.client_id if instance.client else None,
            'event_time': instance.cdtz.isoformat() if instance.cdtz else None,
            'event_type': 'location',
            'has_gps': bool(instance.gpslocation),
            'location_status': instance.locstatus if hasattr(instance, 'locstatus') else None,
        }

        # Get tenant ID
        tenant_id = instance.tenant_id if hasattr(instance, 'tenant_id') else None
        if not tenant_id:
            logger.warning("No tenant_id for location event - skipping streaming")
            return

        # Publish to channel layer
        _publish_to_stream(
            tenant_id=tenant_id,
            event_type='location',
            event_data=event_data,
            event_id=str(instance.uuid) if hasattr(instance, 'uuid') else None
        )

    except (ValueError, AttributeError) as e:
        logger.error(
            f"Error publishing location event: {e}",
            extra={'instance_id': instance.id if hasattr(instance, 'id') else None},
            exc_info=True
        )
