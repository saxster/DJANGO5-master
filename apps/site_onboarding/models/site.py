"""
Site model for Voice-First Security Audits.

Master container for site security audit sessions linking business unit
with conversational session for complete onboarding lifecycle.
"""

import uuid
from decimal import Decimal
from django.contrib.gis.db.models import PointField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import ConversationSession
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class OnboardingSite(BaseModel, TenantAwareModel):
    """
    Master container for site security audit sessions.

    Links business unit with conversational session to manage
    complete site onboarding lifecycle.
    """

    class SiteTypeChoices(models.TextChoices):
        BANK_BRANCH = "bank_branch", _("Bank Branch")
        ATM = "atm", _("ATM")
        RETAIL_STORE = "retail_store", _("Retail Store")
        WAREHOUSE = "warehouse", _("Warehouse")
        OFFICE = "office", _("Office")
        INDUSTRIAL = "industrial", _("Industrial Facility")
        MIXED_USE = "mixed_use", _("Mixed Use")

    site_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business_unit = models.ForeignKey(
        Bt,
        on_delete=models.CASCADE,
        related_name="onboarding_sites",
        verbose_name=_("Business Unit")
    )
    conversation_session = models.OneToOneField(
        ConversationSession,
        on_delete=models.CASCADE,
        related_name="onboarding_site",
        verbose_name=_("Conversation Session")
    )
    site_type = models.CharField(
        _("Site Type"),
        max_length=50,
        choices=SiteTypeChoices.choices,
        default=SiteTypeChoices.OFFICE
    )
    language = models.CharField(
        _("Audit Language"),
        max_length=10,
        default="en",
        help_text=_("Primary language for audit (ISO 639-1 code)")
    )
    operating_hours_start = models.TimeField(
        _("Operating Hours Start"),
        null=True,
        blank=True
    )
    operating_hours_end = models.TimeField(
        _("Operating Hours End"),
        null=True,
        blank=True
    )
    primary_gps = PointField(
        _("Primary GPS Location"),
        null=True,
        blank=True,
        geography=True,
        help_text="Primary site coordinates"
    )
    risk_profile = models.JSONField(
        _("Risk Profile"),
        default=dict,
        blank=True,
        help_text="Risk assessment: {overall_score, critical_zones, threat_vectors}"
    )
    audit_completed_at = models.DateTimeField(
        _("Audit Completed At"),
        null=True,
        blank=True
    )
    report_generated_at = models.DateTimeField(
        _("Report Generated At"),
        null=True,
        blank=True
    )
    knowledge_base_id = models.UUIDField(
        _("Knowledge Base Document ID"),
        null=True,
        blank=True,
        help_text="Reference to ingested KB document"
    )

    class Meta(BaseModel.Meta):
        db_table = "site_onboarding_site"
        verbose_name = "Onboarding Site"
        verbose_name_plural = "Onboarding Sites"
        indexes = [
            models.Index(fields=['business_unit', 'cdtz'], name='site_bu_created_idx'),
            models.Index(fields=['site_type', 'cdtz'], name='site_type_created_idx'),
        ]

    def __str__(self):
        return f"Site Audit: {self.business_unit.buname} ({self.site_type})"

    def get_critical_zones(self):
        """Get all zones with critical or high importance level."""
        return self.zones.filter(
            importance_level__in=['critical', 'high']
        ).select_related('site')

    def calculate_coverage_score(self) -> Decimal:
        """Calculate audit coverage completion score (0.0 to 1.0)."""
        total_zones = self.zones.count()
        if total_zones == 0:
            return Decimal('0.0')

        completed_zones = self.zones.filter(
            observations__isnull=False
        ).distinct().count()

        return Decimal(completed_zones) / Decimal(total_zones)
