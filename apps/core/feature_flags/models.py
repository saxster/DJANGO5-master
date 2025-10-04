"""
Feature Flag Models

Extended feature flag models beyond django-waffle for custom functionality.
Follows .claude/rules.md Rule #7 (< 150 lines per model).
"""

import logging
from datetime import datetime, timezone as dt_timezone
from typing import Optional, Dict, Any

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import JSONField
from django.utils import timezone

from apps.tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class FeatureFlagMetadata(TenantAwareModel):
    """
    Extended metadata for feature flags.

    Complements django-waffle flags with additional tracking:
    - Rollout percentage tracking
    - Deployment metadata
    - Impact metrics
    """

    flag_name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Feature flag name (matches waffle flag)"
    )

    rollout_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of users with access (0-100)"
    )

    target_groups = models.JSONField(
        default=list,
        help_text="List of user groups with access"
    )

    target_users = models.JSONField(
        default=list,
        help_text="List of specific user IDs with access"
    )

    deployment_metadata = models.JSONField(
        default=dict,
        help_text="Deployment context (version, date, engineer)"
    )

    impact_metrics = models.JSONField(
        default=dict,
        help_text="Measured impact (error_rate, latency, usage)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_feature_flag_metadata'
        verbose_name = 'Feature Flag Metadata'
        verbose_name_plural = 'Feature Flag Metadata'
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f"{self.flag_name} ({self.rollout_percentage}%)"

    def increment_rollout(self, percentage: int = 5) -> int:
        """Gradually increase rollout percentage."""
        self.rollout_percentage = min(100, self.rollout_percentage + percentage)
        self.save(update_fields=['rollout_percentage', 'updated_at'])
        return self.rollout_percentage

    def is_enabled_for_user(self, user_id: int) -> bool:
        """Check if flag enabled for specific user."""
        return user_id in self.target_users


class FeatureFlagAuditLog(TenantAwareModel):
    """
    Audit log for feature flag changes.

    Tracks who changed what and when for compliance.
    """

    flag_name = models.CharField(max_length=100, db_index=True)
    action = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Created'),
            ('enabled', 'Enabled'),
            ('disabled', 'Disabled'),
            ('rollout_changed', 'Rollout Changed'),
            ('deleted', 'Deleted'),
        ]
    )

    changed_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        related_name='flag_changes'
    )

    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)

    reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'core_feature_flag_audit'
        verbose_name = 'Feature Flag Audit Log'
        verbose_name_plural = 'Feature Flag Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['flag_name', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.flag_name}: {self.action} at {self.created_at}"
