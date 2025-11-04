"""
Standard Operating Procedure with multilingual support.

Generated from observations and domain expertise, with compliance citations.
"""

import uuid
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class SOP(BaseModel, TenantAwareModel):
    """
    Standard Operating Procedure with multilingual support.

    Generated from observations and domain expertise, with compliance citations.
    """

    sop_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        "site_onboarding.OnboardingSite",
        on_delete=models.CASCADE,
        related_name="sops",
        verbose_name=_("Site")
    )
    zone = models.ForeignKey(
        "site_onboarding.OnboardingZone",
        on_delete=models.CASCADE,
        related_name="sops",
        verbose_name=_("Zone"),
        null=True,
        blank=True
    )
    asset = models.ForeignKey(
        "site_onboarding.Asset",
        on_delete=models.CASCADE,
        related_name="sops",
        verbose_name=_("Asset"),
        null=True,
        blank=True,
        help_text="Asset-specific SOP"
    )
    sop_title = models.CharField(
        _("SOP Title"),
        max_length=300
    )
    purpose = models.TextField(
        _("Purpose"),
        help_text="Why this SOP is needed"
    )
    steps = models.JSONField(
        _("Steps"),
        default=list,
        help_text="Ordered steps: [{step_number, description, responsible_role}]"
    )
    staffing_required = models.JSONField(
        _("Staffing Required"),
        default=dict,
        help_text="Non-cost staffing: {roles, count, schedule} - no pricing"
    )
    compliance_references = ArrayField(
        models.CharField(max_length=200),
        verbose_name=_("Compliance References"),
        default=list,
        blank=True,
        help_text="RBI/ASIS/ISO citations: ['RBI Master Direction 2021', ...]"
    )
    frequency = models.CharField(
        _("Frequency"),
        max_length=50,
        help_text="hourly/shift/daily/weekly/monthly/as_needed"
    )
    translated_texts = models.JSONField(
        _("Translated Texts"),
        default=dict,
        blank=True,
        help_text="Translations: {lang_code: {title, purpose, steps}}"
    )
    escalation_triggers = models.JSONField(
        _("Escalation Triggers"),
        default=list,
        blank=True,
        help_text="Conditions requiring escalation"
    )
    llm_generated = models.BooleanField(
        _("LLM Generated"),
        default=True,
        help_text="Whether this SOP was AI-generated"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_sops",
        verbose_name=_("Reviewed By")
    )
    approved_at = models.DateTimeField(
        _("Approved At"),
        null=True,
        blank=True
    )

    class Meta(BaseModel.Meta):
        db_table = "site_onboarding_sop"
        verbose_name = "Standard Operating Procedure"
        verbose_name_plural = "Standard Operating Procedures"
        indexes = [
            models.Index(fields=['site', 'zone'], name='sop_site_zone_idx'),
            models.Index(fields=['asset'], name='sop_asset_idx'),
            models.Index(fields=['llm_generated', 'approved_at'], name='sop_gen_approved_idx'),
        ]

    def __str__(self):
        return self.sop_title
