"""
Asset Field History Model for Comprehensive Audit Trail (Sprint 4.4)

Provides field-level change tracking for assets beyond simple status changes.
Tracks every field modification with user attribution, timestamps, and change reasons.

This extends the existing AssetLog model which only tracks status changes.

Author: Development Team
Date: October 2025
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel
import uuid


class AssetFieldHistory(BaseModel, TenantAwareModel):
    """
    Comprehensive field-level change history for assets.

    Tracks all field changes (not just status) with full audit trail.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    asset = models.ForeignKey(
        'activity.Asset',
        verbose_name=_("Asset"),
        on_delete=models.CASCADE,
        related_name='field_history'
    )

    field_name = models.CharField(
        _("Field Name"),
        max_length=100,
        help_text="Name of the field that changed"
    )

    old_value = models.TextField(
        _("Old Value"),
        blank=True,
        help_text="Previous value (JSON serialized for complex types)"
    )

    new_value = models.TextField(
        _("New Value"),
        blank=True,
        help_text="New value (JSON serialized for complex types)"
    )

    changed_by = models.ForeignKey(
        'peoples.People',
        verbose_name=_("Changed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_changes'
    )

    change_reason = models.TextField(
        _("Change Reason"),
        blank=True,
        help_text="Optional reason for the change"
    )

    correlation_id = models.UUIDField(
        _("Correlation ID"),
        default=uuid.uuid4,
        help_text="Correlation ID for tracking related changes"
    )

    change_source = models.CharField(
        _("Change Source"),
        max_length=50,
        default='WEB_UI',
        choices=[
            ('WEB_UI', 'Web UI'),
            ('MOBILE_APP', 'Mobile App'),
            ('API', 'REST API'),
            ('BULK_IMPORT', 'Bulk Import'),
            ('SYSTEM', 'System'),
            ('MIGRATION', 'Data Migration')
        ],
        help_text="Source of the change"
    )

    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Additional change metadata (IP address, user agent, etc.)"
    )

    class Meta:
        db_table = 'activity_asset_field_history'
        verbose_name = _("Asset Field History")
        verbose_name_plural = _("Asset Field History")
        indexes = [
            models.Index(fields=['tenant', 'asset', 'cdtz']),
            models.Index(fields=['tenant', 'field_name', 'cdtz']),
            models.Index(fields=['tenant', 'changed_by', 'cdtz']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['cdtz']),
        ]
        ordering = ['-cdtz']

    def __str__(self):
        return f"{self.asset.assetcode}: {self.field_name} changed at {self.cdtz}"


class AssetLifecycleStage(BaseModel, TenantAwareModel):
    """
    Asset lifecycle stage tracking for enhanced lifecycle management.

    Tracks asset progression through lifecycle stages with validation
    and stage-specific metadata.
    """

    class LifecycleStage(models.TextChoices):
        """Lifecycle stages for assets."""
        ACQUISITION = ("ACQUISITION", "Acquisition")
        INSTALLATION = ("INSTALLATION", "Installation")
        OPERATION = ("OPERATION", "Operation")
        MAINTENANCE = ("MAINTENANCE", "Maintenance")
        DECOMMISSIONING = ("DECOMMISSIONING", "Decommissioning")
        DISPOSED = ("DISPOSED", "Disposed")

    asset = models.ForeignKey(
        'activity.Asset',
        verbose_name=_("Asset"),
        on_delete=models.CASCADE,
        related_name='lifecycle_stages'
    )

    stage = models.CharField(
        _("Lifecycle Stage"),
        max_length=20,
        choices=LifecycleStage.choices
    )

    stage_started = models.DateTimeField(
        _("Stage Started"),
        help_text="When this lifecycle stage began"
    )

    stage_ended = models.DateTimeField(
        _("Stage Ended"),
        null=True,
        blank=True,
        help_text="When this lifecycle stage ended"
    )

    is_current = models.BooleanField(
        _("Is Current Stage"),
        default=True,
        help_text="Whether this is the current lifecycle stage"
    )

    stage_metadata = models.JSONField(
        _("Stage Metadata"),
        default=dict,
        blank=True,
        help_text="Stage-specific metadata (installation date, disposal method, etc.)"
    )

    transitioned_by = models.ForeignKey(
        'peoples.People',
        verbose_name=_("Transitioned By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    notes = models.TextField(
        _("Notes"),
        blank=True,
        help_text="Notes about this lifecycle stage"
    )

    class Meta:
        db_table = 'activity_asset_lifecycle_stage'
        verbose_name = _("Asset Lifecycle Stage")
        verbose_name_plural = _("Asset Lifecycle Stages")
        indexes = [
            models.Index(fields=['tenant', 'asset', 'is_current']),
            models.Index(fields=['tenant', 'stage', 'cdtz']),
            models.Index(fields=['stage_started']),
        ]
        ordering = ['-stage_started']

    def __str__(self):
        status = "Current" if self.is_current else "Historical"
        return f"{self.asset.assetcode}: {self.stage} ({status})"
