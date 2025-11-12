"""
Inbox Pattern for Idempotent Event Processing

Ensures exactly-once processing of events.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import logging
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, Optional, Callable

from django.db import models, transaction
from django.utils import timezone

from apps.tenants.models import TenantAwareModel
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class InboxEvent(TenantAwareModel):
    """
    Inbox for idempotent event consumption.

    Tracks processed events to prevent duplicate processing.
    """

    event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique event ID from source"
    )

    event_type = models.CharField(
        max_length=100,
        db_index=True
    )

    payload = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=[
            ('received', 'Received'),
            ('processing', 'Processing'),
            ('processed', 'Processed'),
            ('failed', 'Failed'),
        ],
        default='received',
        db_index=True
    )

    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    retry_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'core_inbox_event'
        verbose_name = 'Inbox Event'
        verbose_name_plural = 'Inbox Events'
        ordering = ['received_at']
        indexes = [
            models.Index(fields=['status', 'received_at']),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} - {self.event_id}"


class InboxProcessor:
    """
    Processor for inbox events with idempotency guarantees.
    """

    @staticmethod
    def process_event(
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """
        Process event idempotently.

        Args:
            event_id: Unique event identifier
            event_type: Type of event
            payload: Event data
            handler: Function to process event

        Returns:
            True if processed, False if duplicate

        Usage:
            def handle_user_created(payload):
                user_id = payload['user_id']
                # Process event...

            InboxProcessor.process_event(
                event_id='evt_123',
                event_type='user.created',
                payload={'user_id': 123},
                handler=handle_user_created
            )
        """
        try:
            with transaction.atomic():
                # Try to create inbox entry (idempotency check)
                inbox_event, created = InboxEvent.objects.get_or_create(
                    event_id=event_id,
                    defaults={
                        'event_type': event_type,
                        'payload': payload,
                        'status': 'processing'
                    }
                )

                if not created:
                    # Event already processed or being processed
                    logger.info(f"Duplicate event: {event_id}")
                    return False

                # Process event
                try:
                    handler(payload)

                    # Mark as processed
                    inbox_event.status = 'processed'
                    inbox_event.processed_at = timezone.now()
                    inbox_event.save(update_fields=['status', 'processed_at'])

                    return True

                except DATABASE_EXCEPTIONS as e:
                    # Mark as failed
                    inbox_event.status = 'failed'
                    inbox_event.error_message = str(e)
                    inbox_event.retry_count += 1
                    inbox_event.save(
                        update_fields=['status', 'error_message', 'retry_count']
                    )

                    logger.error(
                        f"Failed to process inbox event {event_id}: {e}",
                        exc_info=True
                    )

                    raise

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error processing inbox event: {e}", exc_info=True)
            return False
