"""
IVR Provider Configuration Model.

Stores provider-specific configuration and credentials.
Supports multiple providers with failover priority.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class IVRProviderConfig(BaseModel, TenantAwareModel):
    """
    IVR provider configuration and credentials.

    Supports multi-provider setup with automatic failover.
    """

    PROVIDER_TYPE_CHOICES = [
        ('TWILIO', 'Twilio Voice'),
        ('GOOGLE_VOICE', 'Google Cloud Voice'),
        ('SMS', 'SMS Fallback'),
        ('MOCK', 'Mock Provider (Testing)'),
    ]

    provider_type = models.CharField(
        max_length=20,
        choices=PROVIDER_TYPE_CHOICES,
        db_index=True,
        help_text="Provider type"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether provider is active"
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary provider"
    )

    priority = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Provider priority (1=highest, for failover)"
    )

    credentials = models.JSONField(
        default=dict,
        help_text="Encrypted provider credentials (API keys, tokens, etc.)"
    )

    # Rate limiting and cost control
    rate_limit_per_hour = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Maximum calls per hour"
    )

    max_daily_calls = models.IntegerField(
        default=500,
        validators=[MinValueValidator(10), MaxValueValidator(10000)],
        help_text="Maximum calls per day"
    )

    monthly_budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('5000.00'),
        help_text="Monthly budget in rupees"
    )

    cost_per_call = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('2.50'),
        help_text="Estimated cost per call (rupees)"
    )

    cost_per_minute = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('2.50'),
        help_text="Cost per minute for voice calls"
    )

    # Performance tracking
    total_calls_made = models.IntegerField(
        default=0,
        help_text="Total calls made via this provider"
    )

    successful_calls = models.IntegerField(
        default=0,
        help_text="Successfully completed calls"
    )

    failed_calls = models.IntegerField(
        default=0,
        help_text="Failed calls"
    )

    success_rate = models.FloatField(
        default=0.0,
        help_text="Call success rate (0-1)"
    )

    avg_response_time_seconds = models.FloatField(
        default=0.0,
        help_text="Average time to answer"
    )

    total_cost_current_month = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total cost this month"
    )

    last_call_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last call timestamp"
    )

    # Health monitoring
    is_healthy = models.BooleanField(
        default=True,
        help_text="Provider health status"
    )

    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Consecutive failed calls (circuit breaker)"
    )

    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last health check timestamp"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_ivr_provider_config'
        verbose_name = 'IVR Provider Config'
        verbose_name_plural = 'IVR Provider Configs'
        ordering = ['priority']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'priority']),
            models.Index(fields=['provider_type', 'is_healthy']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'provider_type'],
                name='unique_provider_per_tenant'
            ),
        ]

    def __str__(self):
        return f"{self.get_provider_type_display()} (Priority: {self.priority})"

    def record_call_outcome(self, success, cost=Decimal('0.00')):
        """Record call outcome and update statistics."""
        self.total_calls_made += 1
        if success:
            self.successful_calls += 1
            self.consecutive_failures = 0
        else:
            self.failed_calls += 1
            self.consecutive_failures += 1

        self.success_rate = self.successful_calls / max(self.total_calls_made, 1)
        self.total_cost_current_month += cost
        self.last_call_at = timezone.now()

        if self.consecutive_failures >= 5:
            self.is_healthy = False

        self.save()

    def reset_monthly_cost(self):
        """Reset monthly cost counter (run monthly)."""
        self.total_cost_current_month = Decimal('0.00')
        self.save(update_fields=['total_cost_current_month'])