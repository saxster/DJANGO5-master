"""
Zone-centric model for site security auditing.

Everything anchors to zones: observations, photos, assets, checkpoints.
"""

import uuid
from django.contrib.gis.db.models import PointField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class OnboardingZone(BaseModel, TenantAwareModel):
    """
    Zone-centric model for site security auditing.

    Everything anchors to zones: observations, photos, assets, checkpoints.
    """

    class ZoneTypeChoices(models.TextChoices):
        GATE = "gate", _("Gate / Main Entrance")
        PERIMETER = "perimeter", _("Perimeter / Boundary")
        ENTRY_EXIT = "entry_exit", _("Entry/Exit Point")
        VAULT = "vault", _("Vault / Strong Room")
        ATM = "atm", _("ATM Location")
        CONTROL_ROOM = "control_room", _("Control Room / Security Office")
        PARKING = "parking", _("Parking Area")
        LOADING_DOCK = "loading_dock", _("Loading Dock")
        EMERGENCY_EXIT = "emergency_exit", _("Emergency Exit")
        ASSET_STORAGE = "asset_storage", _("Asset Storage Area")
        CASH_COUNTER = "cash_counter", _("Cash Counter")
        SERVER_ROOM = "server_room", _("Server Room")
        RECEPTION = "reception", _("Reception Area")
        OTHER = "other", _("Other")

    class ImportanceLevelChoices(models.TextChoices):
        CRITICAL = "critical", _("Critical")
        HIGH = "high", _("High")
        MEDIUM = "medium", _("Medium")
        LOW = "low", _("Low")

    class RiskLevelChoices(models.TextChoices):
        SEVERE = "severe", _("Severe")
        HIGH = "high", _("High")
        MODERATE = "moderate", _("Moderate")
        LOW = "low", _("Low")
        MINIMAL = "minimal", _("Minimal")

    zone_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        "site_onboarding.OnboardingSite",
        on_delete=models.CASCADE,
        related_name="zones",
        verbose_name=_("Zone")
    )
    zone_type = models.CharField(
        _("Zone Type"),
        max_length=50,
        choices=ZoneTypeChoices.choices
    )
    zone_name = models.CharField(
        _("Zone Name"),
        max_length=200,
        help_text="Descriptive name for the zone"
    )
    importance_level = models.CharField(
        _("Importance Level"),
        max_length=20,
        choices=ImportanceLevelChoices.choices,
        default=ImportanceLevelChoices.MEDIUM
    )
    risk_level = models.CharField(
        _("Risk Level"),
        max_length=20,
        choices=RiskLevelChoices.choices,
        default=RiskLevelChoices.MODERATE
    )
    gps_coordinates = PointField(
        _("GPS Coordinates"),
        null=True,
        blank=True,
        geography=True
    )
    coverage_required = models.BooleanField(
        _("Coverage Required"),
        default=True,
        help_text="Whether this zone requires guard coverage"
    )
    compliance_notes = models.TextField(
        _("Compliance Notes"),
        blank=True,
        help_text="RBI/ASIS/ISO compliance requirements"
    )

    class Meta(BaseModel.Meta):
        db_table = "site_onboarding_zone"
        verbose_name = "Onboarding Zone"
        verbose_name_plural = "Onboarding Zones"
        indexes = [
            models.Index(fields=['site', 'zone_type'], name='zone_site_type_idx'),
            models.Index(fields=['importance_level'], name='zone_importance_idx'),
            models.Index(fields=['risk_level'], name='zone_risk_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'zone_name'],
                name='unique_zone_name_per_site'
            )
        ]

    def __str__(self):
        return f"{self.zone_name} ({self.zone_type})"
