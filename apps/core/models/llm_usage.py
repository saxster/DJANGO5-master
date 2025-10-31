"""
LLM Usage Tracking Models

Tracks API calls, token usage, costs, and quotas for LLM providers.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #12: Query optimization with indexes
- Cost transparency

Sprint 7-8 Phase 1: LLM Provider Foundation
"""

import logging
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class LLMUsageLog(models.Model):
    """
    Log of LLM API calls with token counts and costs.

    Enables cost tracking, quota enforcement, and usage analytics.
    """

    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('gemini', 'Google Gemini'),
    ]

    # Identification
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='llm_usage_logs',
        help_text="Tenant making the request"
    )

    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        help_text="LLM provider used"
    )

    operation = models.CharField(
        max_length=100,
        help_text="Operation type (e.g., 'generate_changeset', 'review_changeset')"
    )

    # Token usage
    input_tokens = models.IntegerField(
        help_text="Number of input tokens"
    )

    output_tokens = models.IntegerField(
        help_text="Number of output tokens"
    )

    # Cost tracking
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="Cost in USD for this API call"
    )

    # Performance
    latency_ms = models.FloatField(
        help_text="API call latency in milliseconds"
    )

    # Additional context
    metadata = models.JSONField(
        default=dict,
        help_text="Additional metadata (model version, user_id, etc.)"
    )

    # Timestamp
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the API call was made"
    )

    class Meta:
        db_table = 'llm_usage_log'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['provider', 'created_at']),
            models.Index(fields=['tenant', 'provider', 'created_at']),
        ]
        verbose_name = "LLM Usage Log"
        verbose_name_plural = "LLM Usage Logs"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider} - {self.operation} ({self.input_tokens}+{self.output_tokens} tokens, ${self.cost_usd})"


class LLMQuota(models.Model):
    """
    Tenant-specific LLM usage quotas.

    Enforces daily/monthly cost and request limits per tenant.
    """

    # Identification
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='llm_quotas',
        help_text="Tenant this quota applies to"
    )

    provider = models.CharField(
        max_length=50,
        choices=LLMUsageLog.PROVIDER_CHOICES,
        help_text="LLM provider"
    )

    # Request limits
    daily_request_limit = models.IntegerField(
        default=1000,
        help_text="Maximum requests per day"
    )

    monthly_request_limit = models.IntegerField(
        default=30000,
        help_text="Maximum requests per month"
    )

    # Cost limits
    daily_cost_limit_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Maximum cost per day in USD"
    )

    monthly_cost_limit_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1000.00'),
        help_text="Maximum cost per month in USD"
    )

    # Status
    enabled = models.BooleanField(
        default=True,
        help_text="Quota enforcement enabled"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'llm_quota'
        unique_together = [['tenant', 'provider']]
        indexes = [
            models.Index(fields=['tenant', 'provider']),
            models.Index(fields=['enabled']),
        ]
        verbose_name = "LLM Quota"
        verbose_name_plural = "LLM Quotas"

    def __str__(self):
        return f"{self.tenant.name} - {self.provider} (${self.daily_cost_limit_usd}/day)"

    def clean(self):
        """Validate quota configuration."""
        super().clean()

        if self.daily_request_limit < 0:
            raise ValidationError({'daily_request_limit': 'Must be non-negative'})

        if self.daily_cost_limit_usd < 0:
            raise ValidationError({'daily_cost_limit_usd': 'Must be non-negative'})
