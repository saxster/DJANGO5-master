"""
Integration models - Webhook configuration and external integrations.

Migration Timeline (Nov 2025):
- Phase 3: Create proper webhook models to replace TypeAssist JSON blobs
- Benefits: Schema validation, migrations, queryability, encrypted secrets
- Backward compatibility: TypeAssist webhooks deprecated but still supported

Legacy Structure (TypeAssist.other_data - DEPRECATED):
{
    "webhooks": [
        {
            "id": "uuid",
            "name": "Primary Webhook",
            "url": "https://api.example.com/webhook",
            "events": ["ticket.created", "alert.escalated"],
            "secret": "hmac_secret",
            "enabled": true,
            "retry_count": 3,
            "timeout_seconds": 30
        }
    ]
}
"""

import uuid
from django.db import models
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from encrypted_model_fields.fields import EncryptedCharField

from apps.core.models import TenantAwareModel, BaseModel


class WebhookConfiguration(TenantAwareModel):
    """
    First-class webhook configuration model (Nov 2025).

    Replaces TypeAssist JSON blob storage with proper schema validation,
    encrypted secrets, and queryable fields.

    Migration: apps/integrations/migrations/migrate_typeassist_webhooks.py
    """

    # Identity
    webhook_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=100,
        help_text="Human-readable webhook name"
    )

    # Configuration
    url = models.URLField(
        max_length=500,
        validators=[URLValidator()],
        help_text="Webhook endpoint URL"
    )
    secret = EncryptedCharField(
        max_length=255,
        help_text="HMAC secret for signature verification (encrypted at rest)"
    )

    # Behavior
    enabled = models.BooleanField(
        default=True,
        help_text="Whether webhook is active"
    )
    retry_count = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Max retry attempts for failed deliveries"
    )
    timeout_seconds = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
        help_text="HTTP timeout for webhook delivery"
    )

    # Classification
    webhook_type = models.CharField(
        max_length=50,
        choices=[
            ('generic', 'Generic Webhook'),
            ('slack', 'Slack'),
            ('teams', 'Microsoft Teams'),
            ('discord', 'Discord'),
            ('custom', 'Custom Integration'),
        ],
        default='generic',
        help_text="Webhook platform type"
    )

    # Metadata
    description = models.TextField(
        blank=True,
        help_text="Optional description of webhook purpose"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integrations_webhook_configuration'
        indexes = [
            models.Index(fields=['tenant', 'webhook_type', 'enabled']),
            models.Index(fields=['enabled', 'created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = 'Webhook Configuration'
        verbose_name_plural = 'Webhook Configurations'

    def __str__(self):
        return f"{self.name} ({self.webhook_type})"

    @property
    def is_active(self):
        """Check if webhook is active and configured."""
        return self.enabled and bool(self.url)


class WebhookEvent(BaseModel):
    """
    Many-to-many relationship: webhooks listen to multiple events.

    Allows queryability: "Find all webhooks listening to ticket.created"
    """

    webhook = models.ForeignKey(
        WebhookConfiguration,
        on_delete=models.CASCADE,
        related_name='webhook_events'
    )
    event_type = models.CharField(
        max_length=100,
        help_text="Event type identifier (e.g., 'ticket.created', 'alert.escalated')"
    )

    class Meta:
        db_table = 'integrations_webhook_event'
        unique_together = [('webhook', 'event_type')]
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['webhook', 'event_type']),
        ]
        verbose_name = 'Webhook Event'
        verbose_name_plural = 'Webhook Events'

    def __str__(self):
        return f"{self.webhook.name}: {self.event_type}"


class WebhookDeliveryLog(TenantAwareModel):
    """
    Webhook delivery audit log.

    Tracks all delivery attempts for monitoring and debugging.
    """

    webhook = models.ForeignKey(
        WebhookConfiguration,
        on_delete=models.CASCADE,
        related_name='delivery_logs'
    )
    event_type = models.CharField(max_length=100)

    # Delivery details
    delivered_at = models.DateTimeField(auto_now_add=True)
    http_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)

    # Success/failure
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    # Retry tracking
    attempt_number = models.PositiveIntegerField(default=1)
    retry_after_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'integrations_webhook_delivery_log'
        indexes = [
            models.Index(fields=['webhook', 'delivered_at']),
            models.Index(fields=['tenant', 'delivered_at']),
            models.Index(fields=['success', 'delivered_at']),
        ]
        ordering = ['-delivered_at']
        verbose_name = 'Webhook Delivery Log'
        verbose_name_plural = 'Webhook Delivery Logs'

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.webhook.name}: {self.event_type}"
