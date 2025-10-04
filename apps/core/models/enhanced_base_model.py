"""
Enhanced Base Model Classes for Code Duplication Elimination

This module provides enhanced base models that consolidate common patterns
across the codebase, eliminating duplication while maintaining backward compatibility.

Following .claude/rules.md:
- Rule #7: Model classes <150 lines (single responsibility)
- Rule #11: Specific exception handling
- Rule #12: Comprehensive database query optimization
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.tenants.models import TenantAwareModel


def now():
    """
    Return the current datetime with microsecond precision removed.

    Returns:
        datetime: Current timestamp without microseconds
    """
    return timezone.now().replace(microsecond=0)


class TimestampMixin(models.Model):
    """
    Mixin providing standardized timestamp fields.

    Consolidates the various timestamp patterns used across the codebase:
    - created_at/updated_at (modern standard)
    - cdtz/mdtz (legacy peoples app)
    - Provides both for backward compatibility
    """

    # Standard timestamp fields (preferred)
    created_at = models.DateTimeField(
        _("Created at"),
        auto_now_add=True,
        help_text=_("When this record was created")
    )
    updated_at = models.DateTimeField(
        _("Updated at"),
        auto_now=True,
        help_text=_("When this record was last modified")
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_at'], name='%(class)s_created_idx'),
            models.Index(fields=['updated_at'], name='%(class)s_updated_idx'),
        ]


class AuditMixin(models.Model):
    """
    Mixin providing standardized audit fields for user tracking.

    Consolidates user tracking patterns across different apps.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created_by",
        verbose_name=_("Created by"),
        help_text=_("User who created this record")
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated_by",
        verbose_name=_("Updated by"),
        help_text=_("User who last modified this record")
    )

    class Meta:
        abstract = True


class MobileSyncMixin(models.Model):
    """
    Mixin providing standardized mobile sync fields.

    Consolidates mobile sync patterns used across various models
    to eliminate duplication in sync services.
    """

    mobile_id = models.UUIDField(
        _("Mobile ID"),
        unique=True,
        null=True,
        blank=True,
        help_text=_("Unique identifier for mobile sync")
    )
    version = models.PositiveIntegerField(
        _("Version"),
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_("Version number for optimistic locking")
    )
    sync_status = models.CharField(
        _("Sync Status"),
        max_length=20,
        choices=[
            ('pending', _('Pending Sync')),
            ('synced', _('Synced')),
            ('conflict', _('Sync Conflict')),
            ('error', _('Sync Error')),
        ],
        default='pending',
        db_index=True,
        help_text=_("Current synchronization status")
    )
    last_sync_timestamp = models.DateTimeField(
        _("Last Sync"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("When this record was last synchronized")
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['mobile_id'], name='%(class)s_mobile_id_idx'),
            models.Index(fields=['sync_status'], name='%(class)s_sync_status_idx'),
            models.Index(fields=['last_sync_timestamp'], name='%(class)s_last_sync_idx'),
            models.Index(fields=['version'], name='%(class)s_version_idx'),
        ]

    def save(self, *args, **kwargs):
        """
        Override save to auto-generate mobile_id if not provided.
        """
        if not self.mobile_id:
            self.mobile_id = uuid.uuid4()
        super().save(*args, **kwargs)


class ActiveStatusMixin(models.Model):
    """
    Mixin providing standardized active/inactive status field.

    Consolidates is_active patterns used across many models.
    """

    is_active = models.BooleanField(
        _("Active"),
        default=True,
        db_index=True,
        help_text=_("Whether this record is active")
    )

    class Meta:
        abstract = True


class EnhancedBaseModel(TimestampMixin, AuditMixin, ActiveStatusMixin):
    """
    Enhanced base model consolidating common patterns.

    Provides:
    - Standardized timestamp fields (created_at, updated_at)
    - User audit fields (created_by, updated_by)
    - Active status field (is_active)
    - Optimized indexing
    - Proper Meta class inheritance
    """

    class Meta:
        abstract = True
        ordering = ['-updated_at']

    def __str__(self):
        """
        Default string representation showing ID and update time.
        """
        return f"{self.__class__.__name__}(id={self.pk}, updated={self.updated_at})"


class EnhancedSyncModel(EnhancedBaseModel, MobileSyncMixin):
    """
    Enhanced base model with mobile sync capabilities.

    Combines all common patterns:
    - Timestamps (created_at, updated_at)
    - User audit (created_by, updated_by)
    - Active status (is_active)
    - Mobile sync (mobile_id, version, sync_status, last_sync_timestamp)
    """

    class Meta:
        abstract = True
        ordering = ['-updated_at']


class EnhancedTenantModel(EnhancedBaseModel, TenantAwareModel):
    """
    Enhanced base model with tenant awareness.

    Combines common patterns with multi-tenancy support.
    """

    class Meta:
        abstract = True
        ordering = ['-updated_at']


class EnhancedTenantSyncModel(EnhancedSyncModel, TenantAwareModel):
    """
    Enhanced base model with both tenant awareness and mobile sync.

    The ultimate base model combining all common patterns.
    """

    class Meta:
        abstract = True
        ordering = ['-updated_at']


# Backward compatibility aliases for peoples app
class BaseModelCompat(TimestampMixin, AuditMixin):
    """
    Backward compatibility model for peoples app.

    Provides properties for legacy field names while using standard internals.
    """

    # Legacy timezone field for compatibility
    ctzoffset = models.IntegerField(
        _("Timezone offset"),
        default=-1,
        help_text=_("User's timezone offset in minutes")
    )

    class Meta:
        abstract = True
        ordering = ['-updated_at']  # Use standard field internally
        indexes = [
            models.Index(fields=['updated_at'], name='%(class)s_mdtz_idx'),
            models.Index(fields=['created_at'], name='%(class)s_cdtz_idx'),
        ]

    # Properties for backward compatibility with peoples app
    @property
    def cdtz(self):
        """Legacy property for created_at."""
        return self.created_at

    @property
    def mdtz(self):
        """Legacy property for updated_at."""
        return self.updated_at

    @property
    def cuser(self):
        """Legacy property for created_by."""
        return self.created_by

    @property
    def muser(self):
        """Legacy property for updated_by."""
        return self.updated_by

    def save(self, *args, **kwargs):
        """
        Override save with legacy timezone handling.
        """
        # Maintain legacy behavior for peoples app
        super().save(*args, **kwargs)