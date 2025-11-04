"""
Security and operational assets within zones.

Tracks cameras, sensors, access control, alarms, and other equipment.
"""

import uuid
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class Asset(BaseModel, TenantAwareModel):
    """
    Security and operational assets within zones.

    Tracks cameras, sensors, access control, alarms, and other equipment.

    NOTE: Override inherited ForeignKeys to avoid clashes with activity.Asset
    """

    class AssetTypeChoices(models.TextChoices):
        CAMERA = "camera", _("CCTV Camera")
        DVR_NVR = "dvr_nvr", _("DVR/NVR")
        LIGHTING = "lighting", _("Security Lighting")
        METAL_DETECTOR = "metal_detector", _("Metal Detector")
        XRAY_MACHINE = "xray_machine", _("X-Ray Machine")
        ALARM_SYSTEM = "alarm_system", _("Alarm System")
        ACCESS_READER = "access_reader", _("Access Control Reader")
        BIOMETRIC = "biometric", _("Biometric Device")
        INTERCOM = "intercom", _("Intercom System")
        BARRIER_GATE = "barrier_gate", _("Barrier Gate")
        SAFE_VAULT = "safe_vault", _("Safe/Vault")
        FIRE_EXTINGUISHER = "fire_extinguisher", _("Fire Extinguisher")
        FIRE_ALARM = "fire_alarm", _("Fire Alarm")
        EMERGENCY_LIGHT = "emergency_light", _("Emergency Lighting")
        OTHER = "other", _("Other Asset")

    class StatusChoices(models.TextChoices):
        OPERATIONAL = "operational", _("Operational")
        NEEDS_REPAIR = "needs_repair", _("Needs Repair")
        NOT_INSTALLED = "not_installed", _("Not Installed")
        PLANNED = "planned", _("Planned")
        DECOMMISSIONED = "decommissioned", _("Decommissioned")

    # Override inherited ForeignKeys with custom related_name to avoid clashes
    cuser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created By"),
        on_delete=models.RESTRICT,
        related_name="onboarding_asset_cusers",
        null=True,
        blank=True
    )
    muser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Modified By"),
        on_delete=models.RESTRICT,
        related_name="onboarding_asset_musers",
        null=True,
        blank=True
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="onboarding_asset_set",
        null=True,
        blank=True
    )

    asset_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        "site_onboarding.OnboardingZone",
        on_delete=models.CASCADE,
        related_name="assets",
        verbose_name=_("Zone")
    )
    asset_type = models.CharField(
        _("Asset Type"),
        max_length=50,
        choices=AssetTypeChoices.choices
    )
    asset_name = models.CharField(
        _("Asset Name"),
        max_length=200
    )
    status = models.CharField(
        _("Status"),
        max_length=30,
        choices=StatusChoices.choices,
        default=StatusChoices.OPERATIONAL
    )
    specifications = models.JSONField(
        _("Specifications"),
        default=dict,
        blank=True,
        help_text="Technical specs: {model, serial, resolution, coverage_area}"
    )
    linked_photos = ArrayField(
        models.UUIDField(),
        verbose_name=_("Linked Photos"),
        default=list,
        blank=True,
        help_text="Photo IDs documenting this asset"
    )

    class Meta(BaseModel.Meta):
        db_table = "site_onboarding_asset"
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        indexes = [
            models.Index(fields=['zone', 'asset_type'], name='asset_zone_type_idx'),
            models.Index(fields=['status'], name='asset_status_idx'),
        ]

    def __str__(self):
        return f"{self.asset_name} ({self.asset_type})"
