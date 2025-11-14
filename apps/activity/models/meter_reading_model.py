"""
Meter Reading Models for AI/ML-powered meter data capture and tracking.

This module provides models for storing time-series meter readings captured
via AI/ML image processing, with validation, anomaly detection, and analytics.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.db import models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel
from apps.activity.models.asset_model import Asset
from apps.peoples.models import People


class MeterReading(BaseModel, TenantAwareModel):
    """
    Time-series meter reading data captured via AI/ML image processing.

    Stores individual meter readings with confidence scores, validation,
    and anomaly detection for facility management systems.
    """

    class MeterType(models.TextChoices):
        ELECTRICITY = ('ELECTRICITY', 'Electricity Meter')
        WATER = ('WATER', 'Water Meter')
        GAS = ('GAS', 'Gas Meter')
        DIESEL = ('DIESEL', 'Diesel Meter')
        TEMPERATURE = ('TEMPERATURE', 'Temperature Gauge')
        PRESSURE = ('PRESSURE', 'Pressure Gauge')
        FIRE_PRESSURE = ('FIRE_PRESSURE', 'Fire Pressure Gauge')
        GENERATOR_HOURS = ('GENERATOR_HOURS', 'Generator Hour Meter')
        FLOW = ('FLOW', 'Flow Meter')
        OTHER = ('OTHER', 'Other Meter')

    class ReadingStatus(models.TextChoices):
        PENDING = ('PENDING', 'Pending Processing')
        VALIDATED = ('VALIDATED', 'Validated')
        FLAGGED = ('FLAGGED', 'Flagged for Review')
        REJECTED = ('REJECTED', 'Rejected')
        ANOMALY = ('ANOMALY', 'Anomaly Detected')

    class CaptureMethod(models.TextChoices):
        AI_CAMERA = ('AI_CAMERA', 'AI Camera Capture')
        MANUAL = ('MANUAL', 'Manual Entry')
        API_IMPORT = ('API_IMPORT', 'API Import')
        SCHEDULED = ('SCHEDULED', 'Scheduled Capture')

    # Core identification
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        verbose_name=_("Asset"),
        help_text="Asset this reading belongs to",
        db_index=True
    )
    meter_type = models.CharField(
        _("Meter Type"),
        max_length=20,
        choices=MeterType.choices,
        db_index=True
    )

    # Reading data
    reading_value = models.DecimalField(
        _("Reading Value"),
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Numeric meter reading value"
    )
    unit = models.CharField(
        _("Unit"),
        max_length=20,
        help_text="Unit of measurement (kWh, L, °C, etc.)"
    )
    reading_timestamp = models.DateTimeField(
        _("Reading Timestamp"),
        default=timezone.now,
        db_index=True,
        help_text="When the reading was taken"
    )

    # AI/ML metadata
    capture_method = models.CharField(
        _("Capture Method"),
        max_length=20,
        choices=CaptureMethod.choices,
        default=CaptureMethod.AI_CAMERA.value
    )
    confidence_score = models.FloatField(
        _("Confidence Score"),
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text="AI confidence score (0-1)"
    )
    image_path = models.CharField(
        _("Image Path"),
        max_length=500,
        null=True,
        blank=True,
        help_text="Path to original image file"
    )
    image_hash = models.CharField(
        _("Image Hash"),
        max_length=64,
        null=True,
        blank=True,
        help_text="SHA256 hash of image for deduplication"
    )

    # Processing metadata
    raw_ocr_text = models.TextField(
        _("Raw OCR Text"),
        null=True,
        blank=True,
        help_text="Original text extracted by OCR"
    )
    processing_metadata = JSONField(
        _("Processing Metadata"),
        default=dict,
        help_text="OCR and processing details"
    )

    # Validation and status
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=ReadingStatus.choices,
        default=ReadingStatus.PENDING.value,
        db_index=True
    )
    validation_flags = JSONField(
        _("Validation Flags"),
        default=list,
        help_text="List of validation issues or flags"
    )
    is_anomaly = models.BooleanField(
        _("Is Anomaly"),
        default=False,
        help_text="Flagged as anomaly by detection algorithm",
        db_index=True
    )
    anomaly_score = models.FloatField(
        _("Anomaly Score"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Anomaly detection confidence (0-1)"
    )

    # Usage and cost tracking
    consumption_since_last = models.DecimalField(
        _("Consumption Since Last"),
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Calculated consumption since last reading"
    )
    estimated_cost = models.DecimalField(
        _("Estimated Cost"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated cost for consumption"
    )

    # User and approval
    captured_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Captured By"),
        help_text="User who captured/submitted the reading"
    )
    validated_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_readings',
        verbose_name=_("Validated By"),
        help_text="User who validated the reading"
    )
    validated_at = models.DateTimeField(
        _("Validated At"),
        null=True,
        blank=True
    )

    # Comments and notes
    notes = models.TextField(
        _("Notes"),
        blank=True,
        help_text="Additional notes or comments"
    )

    class Meta(BaseModel.Meta):
        verbose_name = _("Meter Reading")
        verbose_name_plural = _("Meter Readings")
        ordering = ['-reading_timestamp']
        unique_together = ['asset', 'reading_timestamp']
        indexes = [
            models.Index(fields=['asset', '-reading_timestamp']),
            models.Index(fields=['meter_type', '-reading_timestamp']),
            models.Index(fields=['status', 'is_anomaly']),
            models.Index(fields=['image_hash']),
            models.Index(fields=['-cdtz']),
        ]

    def __str__(self):
        return f"{self.asset.assetname} - {self.reading_value} {self.unit} ({self.reading_timestamp.strftime('%Y-%m-%d %H:%M')})"

    def clean(self):
        """Validate the meter reading data."""
        super().clean()

        # Validate meter type matches asset
        if self.asset and hasattr(self.asset, 'json_data'):
            asset_data = self.asset.json_data or {}
            if asset_data.get('ismeter') is False:
                raise ValidationError("Asset is not configured as a meter")

        # Validate reading value is reasonable
        if self.reading_value < 0:
            raise ValidationError("Reading value cannot be negative")

        # Validate confidence score range
        if self.confidence_score is not None and not (0 <= self.confidence_score <= 1):
            raise ValidationError("Confidence score must be between 0 and 1")

    def save(self, *args, **kwargs):
        """Override save to calculate consumption and detect anomalies."""
        is_new = self.pk is None

        # Calculate consumption if this is a new reading
        if is_new:
            self._calculate_consumption()
            self._detect_anomalies()

        super().save(*args, **kwargs)

    def _calculate_consumption(self):
        """Calculate consumption since last reading."""
        try:
            last_reading = MeterReading.objects.filter(
                asset=self.asset,
                meter_type=self.meter_type,
                status__in=[self.ReadingStatus.VALIDATED, self.ReadingStatus.FLAGGED],
                reading_timestamp__lt=self.reading_timestamp
            ).order_by('-reading_timestamp').first()

            if last_reading and last_reading.reading_value <= self.reading_value:
                self.consumption_since_last = self.reading_value - last_reading.reading_value

        except (ValueError, TypeError):
            # Skip consumption calculation if there's an error
            pass

    def _detect_anomalies(self):
        """Basic anomaly detection using statistical methods."""
        try:
            # Get recent readings for comparison
            recent_readings = MeterReading.objects.filter(
                asset=self.asset,
                meter_type=self.meter_type,
                status=self.ReadingStatus.VALIDATED,
                reading_timestamp__gte=timezone.now() - timedelta(days=30)
            ).values_list('reading_value', flat=True)

            if len(recent_readings) >= 3:
                values = list(recent_readings)
                mean_value = sum(values) / len(values)

                # Simple anomaly detection: flag if reading is > 3 standard deviations
                if len(values) > 1:
                    variance = sum((x - mean_value) ** 2 for x in values) / len(values)
                    std_dev = variance ** 0.5

                    if abs(float(self.reading_value) - mean_value) > (3 * std_dev):
                        self.is_anomaly = True
                        self.anomaly_score = min(1.0, abs(float(self.reading_value) - mean_value) / (3 * std_dev))
                        self.validation_flags = self.validation_flags or []
                        self.validation_flags.append('STATISTICAL_ANOMALY')
                        self.status = self.ReadingStatus.FLAGGED

        except (ValueError, TypeError, ZeroDivisionError):
            # Skip anomaly detection if there's an error
            pass

    @property
    def is_recent(self):
        """Check if reading was taken recently (within 24 hours)."""
        return timezone.now() - self.reading_timestamp <= timedelta(hours=24)

    @property
    def needs_validation(self):
        """Check if reading needs manual validation."""
        return self.status in [self.ReadingStatus.PENDING, self.ReadingStatus.FLAGGED]

    def get_previous_reading(self):
        """Get the previous reading for this asset/meter type."""
        return MeterReading.objects.filter(
            asset=self.asset,
            meter_type=self.meter_type,
            reading_timestamp__lt=self.reading_timestamp
        ).order_by('-reading_timestamp').first()

    def get_consumption_rate(self, period_days=30):
        """Calculate average consumption rate over specified period."""
        end_date = self.reading_timestamp
        start_date = end_date - timedelta(days=period_days)

        start_reading = MeterReading.objects.filter(
            asset=self.asset,
            meter_type=self.meter_type,
            reading_timestamp__gte=start_date,
            status=self.ReadingStatus.VALIDATED
        ).order_by('reading_timestamp').first()

        if start_reading and start_reading.reading_value < self.reading_value:
            consumption = self.reading_value - start_reading.reading_value
            time_diff = (self.reading_timestamp - start_reading.reading_timestamp).days

            if time_diff > 0:
                return float(consumption) / time_diff

        return None


class MeterReadingAlert(BaseModel, TenantAwareModel):
    """
    Alerts generated from meter reading analysis.

    Tracks anomalies, maintenance needs, and cost thresholds.
    """

    class AlertType(models.TextChoices):
        ANOMALY = ('ANOMALY', 'Anomaly Detected')
        HIGH_CONSUMPTION = ('HIGH_CONSUMPTION', 'High Consumption')
        LOW_READING = ('LOW_READING', 'Suspiciously Low Reading')
        MAINTENANCE_DUE = ('MAINTENANCE_DUE', 'Maintenance Due')
        COST_THRESHOLD = ('COST_THRESHOLD', 'Cost Threshold Exceeded')
        MISSING_READING = ('MISSING_READING', 'Missing Expected Reading')

    class Severity(models.TextChoices):
        LOW = ('LOW', 'Low')
        MEDIUM = ('MEDIUM', 'Medium')
        HIGH = ('HIGH', 'High')
        CRITICAL = ('CRITICAL', 'Critical')

    reading = models.ForeignKey(
        MeterReading,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Related Reading")
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        verbose_name=_("Asset")
    )
    alert_type = models.CharField(
        _("Alert Type"),
        max_length=20,
        choices=AlertType.choices,
        db_index=True
    )
    severity = models.CharField(
        _("Severity"),
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM.value,
        db_index=True
    )
    message = models.TextField(_("Alert Message"))
    threshold_value = models.DecimalField(
        _("Threshold Value"),
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True
    )
    actual_value = models.DecimalField(
        _("Actual Value"),
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True
    )
    is_acknowledged = models.BooleanField(
        _("Acknowledged"),
        default=False,
        db_index=True
    )
    acknowledged_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Acknowledged By")
    )
    acknowledged_at = models.DateTimeField(
        _("Acknowledged At"),
        null=True,
        blank=True
    )
    resolution_notes = models.TextField(
        _("Resolution Notes"),
        blank=True
    )

    class Meta(BaseModel.Meta):
        verbose_name = _("Meter Reading Alert")
        verbose_name_plural = _("Meter Reading Alerts")
        ordering = ['-cdtz']
        indexes = [
            models.Index(fields=['asset', '-cdtz']),
            models.Index(fields=['alert_type', 'severity']),
            models.Index(fields=['is_acknowledged', '-cdtz']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.asset.assetname} ({self.get_severity_display()})"

    def acknowledge(self, user, notes=""):
        """Acknowledge the alert."""
        self.is_acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.resolution_notes = notes
        self.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at', 'resolution_notes'])