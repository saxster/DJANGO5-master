"""
Security Intelligence Signal Handlers.

Automatically triggers anomaly detection when attendance events occur.
Non-blocking async processing to avoid performance impact.

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

logger = logging.getLogger('noc.security_intelligence')


@receiver(post_save, sender='attendance.PeopleEventlog')
def process_attendance_for_anomalies(sender, instance, created, **kwargs):
    """
    Process attendance event for security anomalies.

    Args:
        sender: Model class
        instance: PeopleEventlog instance
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    if not created:
        return

    if not instance.punchintime:
        return

    try:
        transaction.on_commit(lambda: _async_process_anomalies(instance))
    except (ValueError, AttributeError) as e:
        logger.error(f"Signal processing error: {e}", exc_info=True)


def _async_process_anomalies(attendance_event):
    """
    Async anomaly processing (runs after transaction commit).

    Args:
        attendance_event: PeopleEventlog instance
    """
    from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator

    try:
        anomalies = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        if anomalies:
            logger.info(f"Detected {len(anomalies)} anomalies for attendance {attendance_event.id}")
        else:
            logger.debug(f"No anomalies detected for attendance {attendance_event.id}")

    except (ValueError, AttributeError) as e:
        logger.error(f"Async anomaly processing error: {e}", exc_info=True)