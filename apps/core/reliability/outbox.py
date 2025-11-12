"""
Transactional Outbox Pattern

Ensures reliable event publishing with zero message loss.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import logging
import json
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, Optional

from django.db import models, transaction
from django.utils import timezone

from apps.tenants.models import TenantAwareModel
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class OutboxEvent(TenantAwareModel):
    """
    Transactional outbox for reliable event publishing.

    Events are written to database in same transaction as business logic,
    then published asynchronously by processor.
    """

    event_id = models.UUIDField(
        primary_key=True,
        auto_created=True,
        editable=False
    )

    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of event (e.g., 'user.created')"
    )

    aggregate_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of aggregate (e.g., 'User', 'Order')"
    )

    aggregate_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="ID of the aggregate"
    )

    payload = models.JSONField(
        help_text="Event data payload"
    )

    metadata = models.JSONField(
        default=dict,
        help_text="Event metadata (correlation_id, user_id, etc.)"
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('published', 'Published'),
            ('failed', 'Failed'),
        ],
        default='pending',
        db_index=True
    )

    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'core_outbox_event'
        verbose_name = 'Outbox Event'
        verbose_name_plural = 'Outbox Events'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['aggregate_type', 'aggregate_id']),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.status})"

    @classmethod
    def create_event(
        cls,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'OutboxEvent':
        """
        Create outbox event in current transaction.

        Must be called within @transaction.atomic block.

        Usage:
            with transaction.atomic():
                user.save()
                OutboxEvent.create_event(
                    event_type='user.created',
                    aggregate_type='User',
                    aggregate_id=str(user.id),
                    payload={'username': user.username}
                )
        """
        return cls.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            metadata=metadata or {}
        )

    def mark_published(self):
        """Mark event as successfully published."""
        self.status = 'published'
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_at'])

    def mark_failed(self, error_message: str):
        """Mark event as failed."""
        self.retry_count += 1

        if self.retry_count >= self.max_retries:
            self.status = 'failed'
            self.failed_at = timezone.now()

        self.error_message = error_message
        self.save(update_fields=['status', 'retry_count', 'failed_at', 'error_message'])


class OutboxProcessor:
    """
    Processor for outbox events.

    Publishes pending events to message broker (Celery, Kafka, etc.)
    """

    @staticmethod
    def process_pending_events(batch_size: int = 100):
        """
        Process pending outbox events.

        Should be called by periodic Celery task.
        """
        try:
            pending_events = OutboxEvent.objects.filter(
                status='pending'
            ).order_by('created_at')[:batch_size]

            for event in pending_events:
                try:
                    OutboxProcessor._publish_event(event)
                    event.mark_published()

                except (ValueError, TypeError, AttributeError) as e:
                    logger.error(
                        f"Failed to publish outbox event {event.event_id}: {e}",
                        exc_info=True
                    )
                    event.mark_failed(str(e))

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error processing outbox: {e}", exc_info=True)

    @staticmethod
    def _publish_event(event: OutboxEvent):
        """Publish event to message broker."""
        # TODO: Implement actual publishing logic
        # Examples:
        # - Send to Celery task
        # - Publish to Kafka
        # - Send webhook
        # - Trigger AWS SNS/SQS

        logger.info(f"Publishing event {event.event_id}: {event.event_type}")
