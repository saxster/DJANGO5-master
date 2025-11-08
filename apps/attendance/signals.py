"""
Attendance Module Django Signals

Automatic workflows for:
- Post order version updates → Invalidate acknowledgements
- Assignment status changes → Notifications
- Attendance records → Update assignments
- MQTT notifications for real-time monitoring

Author: Original + Claude Code enhancements
Created: 2025-11-03
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction

from apps.attendance.models import PeopleEventlog
from apps.attendance.serializers import PeopleEventlogSerializer
import json
from background_tasks.tasks import publish_mqtt

import logging
from apps.core.exceptions.patterns import BUSINESS_LOGIC_EXCEPTIONS


logger = logging.getLogger(__name__)

TOPIC = "redmine_to_noc"


def build_payload(instance, model_name, created):
    """Build MQTT payload for NOC notifications"""
    serializer_cls = {"PeopleEventlog": PeopleEventlogSerializer}[model_name]
    serializer = serializer_cls(instance)
    return json.dumps(
        {
            "operation": "CREATE" if created else "UPDATE",
            "app": "Attendance",
            "models": model_name,
            "payload": serializer.data,
        }
    )


@receiver(post_save, sender=PeopleEventlog)
def peopleeventlog_post_save(sender, instance, created, **kwargs):
    """Publish attendance events to MQTT for real-time NOC monitoring"""
    payload = build_payload(instance, "PeopleEventlog", created)
    publish_mqtt.delay(TOPIC, payload)


# ==================== PHASE 2-3: POST ASSIGNMENT SIGNALS ====================

# Import Phase 2-3 models (lazy import to avoid circular dependencies)
def get_post_models():
    """Lazy import to avoid circular dependencies"""
    from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement
    return Post, PostAssignment, PostOrderAcknowledgement


@receiver(pre_save)
def auto_increment_post_orders_version(sender, instance, **kwargs):
    """Auto-increment post_orders_version when post_orders content changes"""
    Post, _, _ = get_post_models()

    if sender == Post and instance.pk:
        try:
            old_instance = Post.objects.get(pk=instance.pk)
            if old_instance.post_orders != instance.post_orders:
                instance.post_orders_version = old_instance.post_orders_version + 1
                logger.info(
                    f"Post {instance.post_code} orders updated: "
                    f"v{old_instance.post_orders_version} → v{instance.post_orders_version}"
                )
        except Post.DoesNotExist:
            pass


@receiver(post_save)
def invalidate_acknowledgements_on_post_update(sender, instance, created, **kwargs):
    """Invalidate acknowledgements when post orders updated"""
    Post, _, PostOrderAcknowledgement = get_post_models()

    if sender == Post and not created and instance.post_orders_version > 1:
        PostOrderAcknowledgement.bulk_invalidate_for_post(
            post=instance,
            reason=f"Post orders updated to v{instance.post_orders_version}"
        )
        logger.info(f"Invalidated acknowledgements for post {instance.post_code}")


@receiver(post_save)
def notify_worker_of_assignment(sender, instance, created, **kwargs):
    """Notify worker when assigned to a post"""
    _, PostAssignment, _ = get_post_models()

    if sender == PostAssignment and created and instance.status == 'SCHEDULED':
        try:
            instance.worker_notified = True
            instance.worker_notified_at = timezone.now()
            instance.save(update_fields=['worker_notified', 'worker_notified_at'])

            logger.info(
                f"Notification queued for worker {instance.worker.id} "
                f"for assignment {instance.id}"
            )
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to notify worker: {e}", exc_info=True)


@receiver(post_save, sender=PeopleEventlog)
def update_assignment_on_attendance(sender, instance, created, **kwargs):
    """Update PostAssignment when attendance record created"""
    if instance.post_assignment:
        try:
            assignment = instance.post_assignment

            if instance.punchintime and not assignment.checked_in_at:
                assignment.checked_in_at = instance.punchintime
                assignment.status = 'IN_PROGRESS'
                assignment.save(update_fields=['checked_in_at', 'status'])

            if instance.punchouttime and not assignment.checked_out_at:
                assignment.checked_out_at = instance.punchouttime
                assignment.status = 'COMPLETED'

                if assignment.checked_in_at:
                    duration = assignment.checked_out_at - assignment.checked_in_at
                    assignment.hours_worked = round(duration.total_seconds() / 3600, 2)

                assignment.save(update_fields=['checked_out_at', 'status', 'hours_worked'])

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to update assignment: {e}", exc_info=True)


@receiver(post_delete)
def log_post_deletion(sender, instance, **kwargs):
    """Log post deletions for audit trail"""
    Post, _, _ = get_post_models()

    if sender == Post:
        logger.warning(
            f"Post {instance.post_code} deleted (ID: {instance.id})",
            extra={'post_id': instance.id, 'post_code': instance.post_code}
        )
