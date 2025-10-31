"""
Base model classes and utilities for the peoples app.

This module contains the foundational model classes that other models inherit from,
ensuring consistency across the application and adhering to DRY principles.
"""

from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def now():
    """
    Return the current datetime with microsecond precision removed.

    Returns:
        datetime: Current timestamp without microseconds
    """
    return timezone.now().replace(microsecond=0)


class BaseModel(models.Model):
    """
    Abstract base model providing common audit fields.

    Provides created/modified user tracking and timestamps that are
    used consistently across all models in the application.

    Attributes:
        cuser (ForeignKey): User who created the record
        muser (ForeignKey): User who last modified the record
        cdtz (DateTimeField): Creation timestamp
        mdtz (DateTimeField): Last modification timestamp
        ctzoffset (IntegerField): Timezone offset for the user
    """

    cuser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="%(class)s_cusers",
        verbose_name=_("Created by"),
        help_text=_("User who created this record")
    )
    muser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="%(class)s_musers",
        verbose_name=_("Modified by"),
        help_text=_("User who last modified this record")
    )
    cdtz = models.DateTimeField(
        _("Created date"),
        default=now,
        help_text=_("When this record was created")
    )
    mdtz = models.DateTimeField(
        _("Modified date"),
        default=now,
        help_text=_("When this record was last modified")
    )
    ctzoffset = models.IntegerField(
        _("Timezone offset"),
        default=-1,
        help_text=_("User's timezone offset in minutes")
    )

    class Meta:
        abstract = True
        ordering = ["mdtz"]
        indexes = [
            models.Index(fields=['mdtz'], name='%(class)s_mdtz_idx'),
            models.Index(fields=['cdtz'], name='%(class)s_cdtz_idx'),
        ]

    def save(self, *args, **kwargs):
        """
        Override save to automatically update modification timestamp.

        Updates mdtz field whenever the record is saved, ensuring
        accurate modification tracking.
        """
        self.mdtz = now()
        super().save(*args, **kwargs)

    @property
    def created_at(self) -> datetime:
        """Backward-compatible alias for creation timestamp."""
        return self.cdtz

    @created_at.setter
    def created_at(self, value: datetime):
        self.cdtz = value

    @property
    def updated_at(self) -> datetime:
        """Backward-compatible alias for modification timestamp."""
        return self.mdtz

    @updated_at.setter
    def updated_at(self, value: datetime):
        self.mdtz = value
