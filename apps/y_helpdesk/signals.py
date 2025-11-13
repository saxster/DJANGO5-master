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
# REMOVED: Signal handlers moved to Ticket model methods (Django best practice)
# - track_ticket_status_change → Ticket.__init__()
# - broadcast_ticket_state_change → Ticket.save() + Ticket._broadcast_status_change()
#
# Rationale:
# 1. Eliminates N+1 query (Ticket.objects.get() in pre_save signal)
# 2. Moves business logic from signals to model (Django best practice)
# 3. Uses transaction.on_commit() for WebSocket broadcasts (safer)
# 4. Maintains backward compatibility with existing functionality
#
# Date: 2025-11-12
# =============================================================================


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
