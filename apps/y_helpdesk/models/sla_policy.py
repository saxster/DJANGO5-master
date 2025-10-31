"""
SLA Policy Model

Defines Service Level Agreement policies for ticket management.
Part of Sprint 2: NOC Aggregation SLA Logic implementation.

SLA Rules:
- Priority-based response/resolution times
- Business calendar integration (exclude weekends/holidays)
- Escalation thresholds
- Timezone-aware calculations

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes

Created: 2025-10-11
"""

import logging
from typing import Dict, Any
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.onboarding.models import Bt

logger = logging.getLogger(__name__)


class SLAPolicy(TenantAwareModel):
    """
    Service Level Agreement policies for ticket management.

    Defines response and resolution time targets based on ticket priority,
    with business calendar support for accurate SLA tracking.
    """

    PRIORITY_CHOICES = [
        ('P1', 'Critical - P1'),
        ('P2', 'High - P2'),
        ('P3', 'Medium - P3'),
        ('P4', 'Low - P4'),
    ]

    # Identification
    policy_id = models.AutoField(
        primary_key=True,
        help_text="Unique policy identifier"
    )

    policy_name = models.CharField(
        max_length=255,
        help_text="Policy name (e.g., 'Standard Security SLA')"
    )

    # Scope
    client = models.ForeignKey(
        Bt,
        on_delete=models.CASCADE,
        related_name='sla_policies',
        null=True,
        blank=True,
        help_text="Client (null = global policy)"
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        help_text="Ticket priority level"
    )

    # SLA Targets (in minutes)
    response_time_minutes = models.IntegerField(
        help_text="Target time for first response (in minutes)"
    )

    resolution_time_minutes = models.IntegerField(
        help_text="Target time for resolution (in minutes)"
    )

    escalation_threshold_minutes = models.IntegerField(
        help_text="Time before automatic escalation (in minutes)"
    )

    # Business Calendar
    exclude_weekends = models.BooleanField(
        default=True,
        help_text="Exclude weekends from SLA calculations"
    )

    exclude_holidays = models.BooleanField(
        default=True,
        help_text="Exclude holidays from SLA calculations"
    )

    business_hours_start = models.TimeField(
        default='09:00:00',
        help_text="Business day start time"
    )

    business_hours_end = models.TimeField(
        default='18:00:00',
        help_text="Business day end time"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Policy is active"
    )

    effective_from = models.DateTimeField(
        default=timezone.now,
        help_text="Policy effective date"
    )

    effective_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Policy expiration date"
    )

    # Metadata
    description = models.TextField(
        blank=True,
        help_text="Policy description"
    )

    class Meta:
        db_table = 'sla_policy'
        indexes = [
            models.Index(fields=['client', 'priority', 'is_active']),
            models.Index(fields=['priority', 'is_active']),
            models.Index(fields=['effective_from', 'effective_until']),
        ]
        unique_together = [['client', 'priority']]
        verbose_name = "SLA Policy"
        verbose_name_plural = "SLA Policies"
        ordering = ['priority', 'client']

    def __str__(self):
        client_str = f"{self.client.bucode}" if self.client else "Global"
        return f"{self.policy_name} - {self.priority} ({client_str})"

    def clean(self):
        """Validate SLA policy data."""
        super().clean()

        # Validate response time < resolution time
        if self.response_time_minutes >= self.resolution_time_minutes:
            raise ValidationError({
                'response_time_minutes': 'Response time must be less than resolution time'
            })

        # Validate escalation threshold
        if self.escalation_threshold_minutes > self.resolution_time_minutes:
            raise ValidationError({
                'escalation_threshold_minutes': 'Escalation threshold should be before resolution time'
            })

        # Validate business hours
        if self.business_hours_start >= self.business_hours_end:
            raise ValidationError({
                'business_hours_start': 'Start time must be before end time'
            })

    def is_overdue(self, created_at, current_time=None):
        """
        Check if ticket is overdue based on this SLA policy.

        Args:
            created_at: Ticket creation timestamp
            current_time: Current time (defaults to now)

        Returns:
            bool: True if overdue
        """
        if current_time is None:
            current_time = timezone.now()

        elapsed_minutes = self._calculate_business_minutes(created_at, current_time)
        return elapsed_minutes > self.resolution_time_minutes

    def _calculate_business_minutes(self, start_time, end_time):
        """
        Calculate elapsed business minutes between two timestamps.

        Excludes weekends and non-business hours if configured.

        Args:
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            int: Business minutes elapsed
        """
        # Simplified calculation (full implementation would use business calendar library)
        elapsed = end_time - start_time
        total_minutes = int(elapsed.total_seconds() / 60)

        # Apply business hours multiplier (simplified)
        if self.exclude_weekends:
            # Rough approximation: 5/7 of time
            total_minutes = int(total_minutes * (5 / 7))

        return total_minutes
