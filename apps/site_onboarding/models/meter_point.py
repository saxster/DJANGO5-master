"""
Meter and register reading points requiring OCR extraction.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class MeterPoint(BaseModel, TenantAwareModel):
    """
    Meter and register reading points requiring OCR extraction.
    """

    class MeterTypeChoices(models.TextChoices):
        ELECTRICITY = "electricity", _("Electricity Meter")
        WATER = "water", _("Water Meter")
        DIESEL = "diesel", _("Diesel/Fuel Meter")
        FIRE_PRESSURE = "fire_pressure", _("Fire Hydrant Pressure")
        LOGBOOK = "logbook", _("Manual Logbook")
        TEMPERATURE = "temperature", _("Temperature Gauge")
        GENERATOR_HOURS = "generator_hours", _("Generator Hour Meter")
        UPS_STATUS = "ups_status", _("UPS Status Panel")
        OTHER = "other", _("Other Meter")

    meter_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(
        "site_onboarding.OnboardingZone",
        on_delete=models.CASCADE,
        related_name="meter_points",
        verbose_name=_("Zone")
    )
    meter_type = models.CharField(
        _("Meter Type"),
        max_length=50,
        choices=MeterTypeChoices.choices
    )
    meter_name = models.CharField(
        _("Meter Name"),
        max_length=200
    )
    reading_frequency = models.CharField(
        _("Reading Frequency"),
        max_length=50,
        help_text="daily/weekly/monthly"
    )
    reading_template = models.JSONField(
        _("Reading Template"),
        default=dict,
        help_text="Expected format: {unit, range, validation_rules}"
    )
    requires_photo_ocr = models.BooleanField(
        _("Requires Photo OCR"),
        default=True
    )
    photo_example = models.ImageField(
        _("Example Photo"),
        upload_to="onboarding/meter_examples/",
        null=True,
        blank=True
    )
    sop_instructions = models.TextField(
        _("SOP Instructions"),
        blank=True,
        help_text="How to read and record this meter"
    )

    class Meta(BaseModel.Meta):
        db_table = "site_onboarding_meter_point"
        verbose_name = "Meter Point"
        verbose_name_plural = "Meter Points"
        indexes = [
            models.Index(fields=['zone', 'meter_type'], name='meter_zone_type_idx'),
        ]

    def __str__(self):
        return f"{self.meter_name} ({self.meter_type})"
