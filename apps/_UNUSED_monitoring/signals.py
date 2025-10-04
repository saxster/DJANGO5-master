"""
Monitoring App Signals

Signal handlers for monitoring system integration.
"""

import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

# Import models after Django is ready
def get_monitoring_models():
    from apps.monitoring.models import Alert, DeviceHealthSnapshot
    from apps.activity.models import DeviceEventlog
    return Alert, DeviceHealthSnapshot, DeviceEventlog

@receiver(post_save, sender='activity.DeviceEventlog')
def trigger_device_monitoring(sender, instance, created, **kwargs):
    """
    Trigger monitoring when new device data is received.

    This signal fires whenever a new DeviceEventlog entry is created,
    which indicates new device telemetry data has arrived.
    """
    if created:
        try:
            # Import here to avoid circular imports
            from apps.monitoring.services.monitoring_service import monitoring_service

            # Extract user and device info
            user_id = instance.people.id if instance.people else None
            device_id = instance.deviceid

            if user_id and device_id:
                # Trigger asynchronous monitoring
                from apps.monitoring.tasks import monitor_device_task
                monitor_device_task.delay(user_id, device_id)

                logger.debug(f"Queued monitoring task for user {user_id}, device {device_id}")

        except Exception as e:
            logger.error(f"Error triggering device monitoring: {str(e)}")

@receiver(post_save, sender='monitoring.Alert')
def handle_new_alert(sender, instance, created, **kwargs):
    """
    Handle new alert creation for additional processing.
    """
    if created:
        try:
            logger.info(f"New alert created: {instance.alert_id} - {instance.title}")

            # Trigger additional alert processing if needed
            # This could include integrations with external systems

        except Exception as e:
            logger.error(f"Error handling new alert: {str(e)}")

@receiver(pre_delete, sender='monitoring.Alert')
def alert_cleanup(sender, instance, **kwargs):
    """
    Clean up when alerts are deleted.
    """
    try:
        logger.info(f"Alert being deleted: {instance.alert_id}")

        # Perform any necessary cleanup
        # Update statistics, notify external systems, etc.

    except Exception as e:
        logger.error(f"Error in alert cleanup: {str(e)}")

# Additional signal handlers can be added here for other monitoring events