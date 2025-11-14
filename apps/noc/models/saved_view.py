"""
NOC Saved View Model.

User-specific dashboard view configurations for personalized NOC dashboards.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['NOCSavedView']


class NOCSavedView(TenantAwareModel, BaseModel):
    """
    User-specific NOC dashboard view configurations.

    Stores personalized dashboard layouts, filters, and preferences.
    Supports view sharing for team collaboration.
    """

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        verbose_name=_("Owner"),
        related_name='noc_saved_views'
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_("View Name"),
        help_text=_("Descriptive name for this saved view")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of this view's purpose")
    )

    filters = models.JSONField(
        default=dict,
        verbose_name=_("Filters"),
        help_text=_(
            "Filter settings: client_ids, severities, statuses, time_range"
        )
    )

    widget_layout = models.JSONField(
        default=list,
        verbose_name=_("Widget Layout"),
        help_text=_(
            "Dashboard widget configuration: positions, sizes, visibility"
        )
    )

    time_range_hours = models.IntegerField(
        default=24,
        verbose_name=_("Default Time Range (hours)"),
        help_text=_("Default time window for metrics")
    )

    refresh_interval_seconds = models.IntegerField(
        default=30,
        verbose_name=_("Refresh Interval (seconds)"),
        help_text=_("Auto-refresh interval for real-time updates")
    )

    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Default View"),
        help_text=_("Whether this is the user's default dashboard view")
    )

    is_shared = models.BooleanField(
        default=False,
        verbose_name=_("Shared View"),
        help_text=_("Whether this view is shared with other users")
    )

    shared_with = models.ManyToManyField(
        'peoples.People',
        blank=True,
        related_name='shared_noc_views',
        verbose_name=_("Shared With"),
        help_text=_("Users who have access to this shared view")
    )

    version = models.IntegerField(
        default=1,
        verbose_name=_("Version"),
        help_text=_("View version for tracking changes")
    )

    usage_count = models.IntegerField(
        default=0,
        verbose_name=_("Usage Count"),
        help_text=_("Number of times this view has been loaded")
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Used At")
    )

    class Meta:
        db_table = 'noc_saved_views'
        ordering = ['-is_default', '-last_used_at', 'name']
        unique_together = [['tenant', 'user', 'name']]
        indexes = [
            models.Index(fields=['tenant', 'user', 'is_default']),
            models.Index(fields=['is_shared']),
            models.Index(fields=['last_used_at']),
        ]
        verbose_name = _("NOC Saved View")
        verbose_name_plural = _("NOC Saved Views")

    def __str__(self) -> str:
        default_marker = " (Default)" if self.is_default else ""
        return f"{self.name}{default_marker}"

    def increment_usage(self):
        """Record view usage."""
        from django.utils import timezone
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])

    def increment_version(self):
        """Increment version number."""
        self.version += 1
        self.save(update_fields=['version'])