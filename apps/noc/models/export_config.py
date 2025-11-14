"""
NOC Export Configuration Models.

Models for export templates and export history tracking.
Follows .claude/rules.md Rule #7 (models <150 lines).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['NOCExportTemplate', 'NOCExportHistory']


class NOCExportTemplate(TenantAwareModel, BaseModel):
    """
    Reusable export configurations.

    Allows users to save frequently used export settings for one-click exports.
    Supports team sharing for standardized reporting.
    """

    ENTITY_CHOICES = [
        ('alerts', 'Alerts'),
        ('incidents', 'Incidents'),
        ('snapshots', 'Metric Snapshots'),
        ('audit', 'Audit Logs'),
    ]

    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ]

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        verbose_name=_("Owner"),
        related_name='noc_export_templates'
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_("Template Name"),
        help_text=_("Descriptive name for this export template")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of what this template exports")
    )

    entity_type = models.CharField(
        max_length=20,
        choices=ENTITY_CHOICES,
        default='alerts',
        verbose_name=_("Entity Type"),
        help_text=_("Type of data to export")
    )

    format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default='csv',
        verbose_name=_("Export Format")
    )

    filters = models.JSONField(
        default=dict,
        verbose_name=_("Filters"),
        help_text=_("Filter criteria (client_ids, severities, statuses, date_ranges)")
    )

    columns = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        null=True,
        verbose_name=_("Columns"),
        help_text=_("Specific columns to include (null = all columns)")
    )

    is_public = models.BooleanField(
        default=False,
        verbose_name=_("Public Template"),
        help_text=_("Whether this template is shared with team")
    )

    usage_count = models.IntegerField(
        default=0,
        verbose_name=_("Usage Count"),
        help_text=_("Number of times this template has been used")
    )

    class Meta:
        db_table = 'noc_export_templates'
        ordering = ['-usage_count', 'name']
        unique_together = [['tenant', 'user', 'name']]
        indexes = [
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['entity_type']),
            models.Index(fields=['is_public']),
        ]
        verbose_name = _("NOC Export Template")
        verbose_name_plural = _("NOC Export Templates")

    def __str__(self) -> str:
        return f"{self.name} ({self.entity_type})"

    def increment_usage(self):
        """Increment usage count."""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])


class NOCExportHistory(TenantAwareModel, BaseModel):
    """
    Audit trail for NOC data exports.

    Tracks all export operations for compliance and debugging.
    Provides download links for recently generated exports.
    """

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name='noc_export_history'
    )

    template = models.ForeignKey(
        NOCExportTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Template Used"),
        related_name='executions'
    )

    entity_type = models.CharField(
        max_length=20,
        default='alerts',
        verbose_name=_("Entity Type"),
        help_text=_("Type of data exported")
    )

    format = models.CharField(
        max_length=10,
        default='csv',
        verbose_name=_("Format")
    )

    record_count = models.IntegerField(
        default=0,
        verbose_name=_("Record Count"),
        help_text=_("Number of records exported")
    )

    file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("File Size (Bytes)")
    )

    filters_used = models.JSONField(
        default=dict,
        verbose_name=_("Filters Used"),
        help_text=_("Filter criteria applied to this export")
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP Address")
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expires At"),
        help_text=_("When the export file will be deleted (null = immediate download)")
    )

    class Meta:
        db_table = 'noc_export_history'
        ordering = ['-cdtz']
        indexes = [
            models.Index(fields=['tenant', 'user', '-cdtz']),
            models.Index(fields=['entity_type']),
            models.Index(fields=['expires_at']),
        ]
        verbose_name = _("NOC Export History")
        verbose_name_plural = _("NOC Export History")

    def __str__(self) -> str:
        return f"{self.entity_type} export by {self.user.peoplename} ({self.record_count} records)"