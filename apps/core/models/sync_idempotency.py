"""
Sync Idempotency Model

Tracks idempotency keys for mobile sync operations to prevent duplicates on retry.
Implements both batch-level and item-level idempotency.

Following .claude/rules.md patterns:
- Rule #7: Model <150 lines
- Rule #11: Specific exception handling
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta


class SyncIdempotencyRecord(models.Model):
    """
    Stores idempotency keys and responses for sync operations.

    Prevents duplicate processing when mobile clients retry sync requests.
    TTL of 24 hours ensures stale records are cleaned up.
    """

    class IdempotencyScope(models.TextChoices):
        BATCH = 'batch', 'Batch Level'
        ITEM = 'item', 'Item Level'

    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text='SHA256 hash of request for idempotency'
    )

    scope = models.CharField(
        max_length=10,
        choices=IdempotencyScope.choices,
        default=IdempotencyScope.BATCH,
        help_text='Scope of idempotency (batch or item)'
    )

    request_hash = models.CharField(
        max_length=64,
        help_text='Hash of full request payload for verification'
    )

    response_data = models.JSONField(
        help_text='Cached response to return on duplicate request'
    )

    user_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='User who initiated the sync operation'
    )

    device_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Device identifier for tracking'
    )

    endpoint = models.CharField(
        max_length=255,
        help_text='Sync endpoint that was called'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this idempotency record was created'
    )

    expires_at = models.DateTimeField(
        db_index=True,
        help_text='When this record expires (24-hour TTL)'
    )

    hit_count = models.IntegerField(
        default=0,
        help_text='Number of times this idempotency key was used'
    )

    last_hit_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last time this key was used'
    )

    class Meta:
        db_table = 'sync_idempotency_record'
        verbose_name = 'Sync Idempotency Record'
        verbose_name_plural = 'Sync Idempotency Records'
        indexes = [
            models.Index(fields=['user_id', 'created_at'], name='sync_idemp_user_created_idx'),
            models.Index(fields=['device_id', 'created_at'], name='sync_idemp_device_created_idx'),
            models.Index(fields=['expires_at'], name='sync_idemp_expires_idx'),
        ]

    def __str__(self):
        return f"Idempotency {self.idempotency_key[:16]}... ({self.scope})"

    def save(self, *args, **kwargs):
        # Set expiration if not provided
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @classmethod
    def cleanup_expired(cls):
        """Remove expired idempotency records."""
        expired_count = cls.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        return expired_count