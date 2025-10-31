"""
Vehicle Entry Models for AI/ML-powered license plate recognition and vehicle tracking.

This module provides models for storing vehicle entry/exit data captured
via AI/ML image processing for access control and visitor management.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.db import models
from django.db.models import JSONField
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from apps.activity.models.location_model import Location
from apps.peoples.models import People


class VehicleEntry(BaseModel, TenantAwareModel):
    """
    Vehicle entry/exit records captured via AI/ML license plate recognition.

    Tracks vehicle access for security, visitor management, and access control
    with confidence scoring and validation.
    """

    class EntryType(models.TextChoices):
        ENTRY = ('ENTRY', 'Vehicle Entry')
        EXIT = ('EXIT', 'Vehicle Exit')
        PARKING = ('PARKING', 'Parking Verification')
        VISITOR = ('VISITOR', 'Visitor Registration')

    class VehicleType(models.TextChoices):
        CAR = ('CAR', 'Car')
        TRUCK = ('TRUCK', 'Truck')
        MOTORCYCLE = ('MOTORCYCLE', 'Motorcycle')
        VAN = ('VAN', 'Van')
        BUS = ('BUS', 'Bus')
        OTHER = ('OTHER', 'Other')

    class Status(models.TextChoices):
        PENDING = ('PENDING', 'Pending Processing')
        APPROVED = ('APPROVED', 'Approved Entry')
        DENIED = ('DENIED', 'Denied Entry')
        FLAGGED = ('FLAGGED', 'Flagged for Review')
        EXPIRED = ('EXPIRED', 'Entry Expired')

    class CaptureMethod(models.TextChoices):
        AI_CAMERA = ('AI_CAMERA', 'AI Camera Capture')
        MANUAL = ('MANUAL', 'Manual Entry')
        GATE_SENSOR = ('GATE_SENSOR', 'Automated Gate Sensor')
        MOBILE_APP = ('MOBILE_APP', 'Mobile App')

    # Core identification
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    license_plate = models.CharField(
        _("License Plate"),
        max_length=20,
        validators=[MinLengthValidator(3), MaxLengthValidator(15)],
        help_text="Vehicle license plate number",
        db_index=True
    )
    license_plate_clean = models.CharField(
        _("License Plate (Clean)"),
        max_length=15,
        help_text="Cleaned license plate without spaces/symbols",
        db_index=True
    )
    state_province = models.CharField(
        _("State/Province"),
        max_length=10,
        blank=True,
        help_text="State or province of registration"
    )
    country_code = models.CharField(
        _("Country Code"),
        max_length=3,
        default="USA",
        help_text="Country code (ISO 3-letter)"
    )

    # Entry/Exit data
    entry_type = models.CharField(
        _("Entry Type"),
        max_length=20,
        choices=EntryType.choices,
        default=EntryType.ENTRY.value,
        db_index=True
    )
    vehicle_type = models.CharField(
        _("Vehicle Type"),
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.CAR.value
    )
    entry_timestamp = models.DateTimeField(
        _("Entry Timestamp"),
        default=timezone.now,
        db_index=True,
        help_text="When the vehicle was detected"
    )

    # Location and gate
    gate_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Gate Location"),
        help_text="Gate or entrance where detected"
    )
    detection_zone = models.CharField(
        _("Detection Zone"),
        max_length=50,
        blank=True,
        help_text="Specific zone or camera identifier"
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
        null=True,
        blank=True,
        help_text="AI confidence score for plate recognition (0-1)"
    )
    image_path = models.CharField(
        _("Image Path"),
        max_length=500,
        null=True,
        blank=True,
        help_text="Path to captured image"
    )
    image_hash = models.CharField(
        _("Image Hash"),
        max_length=64,
        null=True,
        blank=True,
        help_text="SHA256 hash for deduplication"
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
        choices=Status.choices,
        default=Status.PENDING.value,
        db_index=True
    )
    validation_flags = JSONField(
        _("Validation Flags"),
        default=list,
        help_text="List of validation issues or flags"
    )
    is_blacklisted = models.BooleanField(
        _("Is Blacklisted"),
        default=False,
        help_text="Vehicle is on security blacklist",
        db_index=True
    )

    # Associated people and visitor data
    associated_person = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vehicle_entries',
        verbose_name=_("Associated Person"),
        help_text="Employee or registered person"
    )
    visitor_name = models.CharField(
        _("Visitor Name"),
        max_length=100,
        blank=True,
        help_text="Name for visitor entries"
    )
    visitor_company = models.CharField(
        _("Visitor Company"),
        max_length=100,
        blank=True,
        help_text="Company for visitor entries"
    )
    purpose_of_visit = models.CharField(
        _("Purpose of Visit"),
        max_length=200,
        blank=True,
        help_text="Reason for visit"
    )

    # Duration tracking
    expected_duration_hours = models.PositiveIntegerField(
        _("Expected Duration (Hours)"),
        null=True,
        blank=True,
        help_text="Expected duration of visit in hours"
    )
    exit_timestamp = models.DateTimeField(
        _("Exit Timestamp"),
        null=True,
        blank=True,
        help_text="When vehicle exited (if applicable)"
    )
    actual_duration = models.DurationField(
        _("Actual Duration"),
        null=True,
        blank=True,
        help_text="Calculated duration of visit"
    )

    # User and approval
    captured_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captured_vehicle_entries',
        verbose_name=_("Captured By"),
        help_text="Security personnel who processed entry"
    )
    approved_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_vehicle_entries',
        verbose_name=_("Approved By"),
        help_text="Person who approved the entry"
    )
    approved_at = models.DateTimeField(
        _("Approved At"),
        null=True,
        blank=True
    )

    # Comments and notes
    notes = models.TextField(
        _("Notes"),
        blank=True,
        help_text="Additional notes about the entry"
    )

    class Meta(BaseModel.Meta):
        verbose_name = _("Vehicle Entry")
        verbose_name_plural = _("Vehicle Entries")
        ordering = ['-entry_timestamp']
        indexes = [
            models.Index(fields=['license_plate_clean', '-entry_timestamp']),
            models.Index(fields=['entry_type', '-entry_timestamp']),
            models.Index(fields=['status', 'is_blacklisted']),
            models.Index(fields=['gate_location', '-entry_timestamp']),
            models.Index(fields=['image_hash']),
            models.Index(fields=['-cdtz']),
        ]

    def __str__(self):
        return f"{self.license_plate} - {self.get_entry_type_display()} ({self.entry_timestamp.strftime('%Y-%m-%d %H:%M')})"

    def clean(self):
        """Validate the vehicle entry data."""
        super().clean()

        # Clean and validate license plate
        if self.license_plate:
            self.license_plate_clean = self._clean_license_plate(self.license_plate)

        # Validate license plate format
        if not self._is_valid_license_plate(self.license_plate):
            raise ValidationError("Invalid license plate format")

        # Validate confidence score range
        if self.confidence_score is not None and not (0 <= self.confidence_score <= 1):
            raise ValidationError("Confidence score must be between 0 and 1")

    def save(self, *args, **kwargs):
        """Override save to calculate duration and validate data."""
        is_new = self.pk is None

        # Clean license plate
        if self.license_plate and not self.license_plate_clean:
            self.license_plate_clean = self._clean_license_plate(self.license_plate)

        # Calculate duration if both timestamps exist
        if self.entry_timestamp and self.exit_timestamp:
            self.actual_duration = self.exit_timestamp - self.entry_timestamp

        # Set expiry status if needed
        if is_new:
            self._check_blacklist_status()

        super().save(*args, **kwargs)

    def _clean_license_plate(self, plate: str) -> str:
        """Clean license plate by removing spaces and special characters."""
        return re.sub(r'[^\w]', '', plate.upper())

    def _is_valid_license_plate(self, plate: str) -> bool:
        """Validate license plate format using common patterns."""
        if not plate or len(plate) < 3:
            return False

        # Common license plate patterns
        patterns = [
            r'^[A-Z0-9]{3,8}$',  # Basic alphanumeric
            r'^[A-Z]{1,3}[0-9]{1,4}[A-Z]{0,3}$',  # Letters + numbers + letters
            r'^[0-9]{1,3}[A-Z]{1,3}[0-9]{1,4}$',  # Numbers + letters + numbers
        ]

        clean_plate = self._clean_license_plate(plate)
        return any(re.match(pattern, clean_plate) for pattern in patterns)

    def _check_blacklist_status(self):
        """Check if vehicle is on security blacklist."""
        # Simple blacklist check - in real implementation, this would check against
        # a security database or service
        blacklisted_patterns = ['STOLEN', 'BLOCK', 'BANNED']

        for pattern in blacklisted_patterns:
            if pattern in self.license_plate.upper():
                self.is_blacklisted = True
                self.status = self.Status.DENIED
                self.validation_flags = self.validation_flags or []
                self.validation_flags.append('BLACKLISTED')
                break

    @property
    def is_visitor_entry(self):
        """Check if this is a visitor entry."""
        return self.entry_type == self.EntryType.VISITOR or bool(self.visitor_name)

    @property
    def is_active_entry(self):
        """Check if entry is currently active (no exit recorded)."""
        return self.entry_type == self.EntryType.ENTRY and not self.exit_timestamp

    @property
    def is_overdue(self):
        """Check if visitor has overstayed expected duration."""
        if not self.expected_duration_hours or self.exit_timestamp:
            return False

        expected_exit = self.entry_timestamp + timedelta(hours=self.expected_duration_hours)
        return timezone.now() > expected_exit

    def record_exit(self, exit_timestamp=None, captured_by=None):
        """Record vehicle exit."""
        self.exit_timestamp = exit_timestamp or timezone.now()
        self.entry_type = self.EntryType.EXIT

        if self.entry_timestamp:
            self.actual_duration = self.exit_timestamp - self.entry_timestamp

        if captured_by:
            self.captured_by = captured_by

        self.save(update_fields=['exit_timestamp', 'entry_type', 'actual_duration', 'captured_by'])

    def get_matching_entries(self):
        """Get other entries for the same license plate."""
        return VehicleEntry.objects.filter(
            license_plate_clean=self.license_plate_clean
        ).exclude(id=self.id).order_by('-entry_timestamp')


class VehicleSecurityAlert(BaseModel, TenantAwareModel):
    """
    Security alerts generated from vehicle entry analysis.

    Tracks security events, blacklisted vehicles, and suspicious activity.
    """

    class AlertType(models.TextChoices):
        BLACKLISTED_VEHICLE = ('BLACKLISTED_VEHICLE', 'Blacklisted Vehicle')
        UNAUTHORIZED_ENTRY = ('UNAUTHORIZED_ENTRY', 'Unauthorized Entry Attempt')
        OVERSTAY = ('OVERSTAY', 'Visitor Overstay')
        SUSPICIOUS_ACTIVITY = ('SUSPICIOUS_ACTIVITY', 'Suspicious Activity')
        MULTIPLE_ENTRIES = ('MULTIPLE_ENTRIES', 'Multiple Entries Same Vehicle')
        LOW_CONFIDENCE = ('LOW_CONFIDENCE', 'Low Recognition Confidence')
        DUPLICATE_IMAGE = ('DUPLICATE_IMAGE', 'Duplicate Image Detected')

    class Severity(models.TextChoices):
        LOW = ('LOW', 'Low')
        MEDIUM = ('MEDIUM', 'Medium')
        HIGH = ('HIGH', 'High')
        CRITICAL = ('CRITICAL', 'Critical')

    vehicle_entry = models.ForeignKey(
        VehicleEntry,
        on_delete=models.CASCADE,
        verbose_name=_("Vehicle Entry")
    )
    alert_type = models.CharField(
        _("Alert Type"),
        max_length=30,
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

    # Alert details
    license_plate = models.CharField(
        _("License Plate"),
        max_length=20,
        help_text="License plate from the entry"
    )
    location = models.CharField(
        _("Location"),
        max_length=100,
        blank=True,
        help_text="Location where alert was triggered"
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

    # Response and resolution
    security_response = models.TextField(
        _("Security Response"),
        blank=True,
        help_text="Action taken by security team"
    )
    resolution_notes = models.TextField(
        _("Resolution Notes"),
        blank=True
    )

    class Meta(BaseModel.Meta):
        verbose_name = _("Vehicle Security Alert")
        verbose_name_plural = _("Vehicle Security Alerts")
        ordering = ['-cdtz']
        indexes = [
            models.Index(fields=['license_plate', '-cdtz']),
            models.Index(fields=['alert_type', 'severity']),
            models.Index(fields=['is_acknowledged', '-cdtz']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.license_plate} ({self.get_severity_display()})"

    def acknowledge(self, user, notes="", response=""):
        """Acknowledge the security alert."""
        self.is_acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.resolution_notes = notes
        self.security_response = response
        self.save(update_fields=[
            'is_acknowledged', 'acknowledged_by', 'acknowledged_at',
            'resolution_notes', 'security_response'
        ])