"""
Verification checkpoints for patrol and compliance validation.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class Checkpoint(BaseModel, TenantAwareModel):
    """
    Verification checkpoints for patrol and compliance validation.
    """

    checkpoint_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        "site_onboarding.OnboardingZone",
        on_delete=models.CASCADE,
        related_name="checkpoints",
        verbose_name=_("Zone")
    )
    checkpoint_name = models.CharField(
        _("Checkpoint Name"),
        max_length=200
    )
    questions = models.JSONField(
        _("Questions"),
        default=list,
        help_text="Checklist questions: [{question, required, type}]"
    )
    frequency = models.CharField(
        _("Check Frequency"),
        max_length=50,
        help_text="hourly/shift/daily/weekly"
    )
    severity = models.CharField(
        _("Severity if Missed"),
        max_length=20,
        default="medium"
    )
    template_id = models.UUIDField(
        _("Template ID"),
        null=True,
        blank=True,
        help_text="Link to compliance template"
    )
    completed = models.BooleanField(
        _("Completed"),
        default=False
    )

    class Meta(BaseModel.Meta):
        db_table = "site_onboarding_checkpoint"
        verbose_name = "Checkpoint"
        verbose_name_plural = "Checkpoints"
        indexes = [
            models.Index(fields=['zone', 'completed'], name='checkpoint_zone_complete_idx'),
        ]

    def __str__(self):
        return f"Checkpoint: {self.checkpoint_name}"
