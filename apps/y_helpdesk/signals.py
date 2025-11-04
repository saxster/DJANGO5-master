"""
Y-Helpdesk Signal Handlers.

Handles:
- Ticket numbering on creation
- Ticket state change WebSocket broadcasts (TASK 10)

Following CLAUDE.md Rule #11 (specific exceptions) and Rule #7 (<150 lines).
"""

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from apps.y_helpdesk.models import Ticket
from django.db.models import Q
import logging

logger = logging.getLogger('y_helpdesk.signals')


@receiver(pre_save, sender=Ticket)
def set_serial_no_for_ticket(sender, instance, **kwargs):
    """Generate unique ticket number on creation."""
    if instance.id is None and instance.ticketdesc != "NONE":  # if seqno is not set yet
        # Check if bu exists
        if not instance.bu:
            # If no business unit, generate a unique ticket number
            import uuid
            instance.ticketno = f"TKT#{uuid.uuid4().hex[:8].upper()}"
            return

        latest_record = (
            sender.objects.filter(
                ~Q(ticketdesc="NONE") & ~Q(ticketno__isnull=True),
                client=instance.client,
                bu=instance.bu,
            )
            .order_by("-id")
            .first()
        )
        if latest_record is None:
            # This is the first record for the client
            instance.ticketno = f"{instance.bu.bucode}#1"
        else:
            next_no = int(latest_record.ticketno.split("#")[1]) + 1
            instance.ticketno = f"{instance.bu.bucode}#{next_no}"


# =============================================================================
# TASK 10: TICKET STATE CHANGE BROADCASTS
# =============================================================================

@receiver(pre_save, sender=Ticket)
def track_ticket_status_change(sender, instance, **kwargs):
    """
    Track original status before save for state change detection.

    Stores original status in instance._original_status for use by post_save signal.
    TASK 10: Gap #13 - Ticket State Change Broadcasts
    """
    if instance.pk:
        try:
            original = Ticket.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Ticket.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None


@receiver(post_save, sender=Ticket)
def broadcast_ticket_state_change(sender, instance, created, **kwargs):
    """
    Broadcast ticket state changes via WebSocket.

    Triggers on status change (not on creation) and broadcasts to:
    - Tenant group: noc_tenant_{tenant_id}
    - Site group (if site exists): noc_site_{site_id}

    TASK 10: Gap #13 - Ticket State Change Broadcasts
    """
    if not created and hasattr(instance, '_original_status'):
        old_status = instance._original_status
        if old_status and old_status != instance.status:
            logger.info(
                f"Ticket {instance.id} status changed: {old_status} → {instance.status}",
                extra={
                    'ticket_id': instance.id,
                    'old_status': old_status,
                    'new_status': instance.status,
                    'tenant_id': instance.tenant_id
                }
            )

            # Lazy import to avoid circular dependency
            try:
                from apps.noc.services.websocket_service import NOCWebSocketService
                NOCWebSocketService.broadcast_ticket_update(instance, old_status)
            except (ImportError, AttributeError) as e:
                logger.warning(
                    f"Failed to import NOCWebSocketService: {e}",
                    extra={'ticket_id': instance.id}
                )


# =============================================================================
# SENTIMENT ANALYSIS SIGNALS (Feature 2: NL/AI Platform Quick Win)
# =============================================================================

@receiver(post_save, sender=Ticket)
def analyze_ticket_sentiment_on_creation(sender, instance, created, **kwargs):
    """
    Trigger sentiment analysis when ticket is created.

    Runs asynchronously via Celery task to avoid blocking ticket creation.

    Feature 2: NL/AI Platform Quick Win - Sentiment Analysis
    """
    if created and instance.ticketdesc and instance.ticketdesc != "NONE":
        logger.info(
            f"Triggering sentiment analysis for new ticket {instance.id}",
            extra={
                'ticket_id': instance.id,
                'ticket_no': instance.ticketno
            }
        )

        # Import task lazily to avoid circular imports
        try:
            from apps.y_helpdesk.tasks.sentiment_analysis_tasks import AnalyzeTicketSentimentTask
            AnalyzeTicketSentimentTask.delay(instance.id)
        except ImportError as e:
            logger.warning(
                f"Failed to import sentiment analysis task: {e}",
                extra={'ticket_id': instance.id}
            )
