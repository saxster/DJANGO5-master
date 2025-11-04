"""
GPS Validation Log Model.

Records GPS location validations and spoofing detection.
Tracks location quality, network validation, and geofence compliance.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class GPSValidationLog(BaseModel, TenantAwareModel):
    """
    GPS location validation and spoofing detection log.

    Validates GPS quality and detects location manipulation.
    """

    VALIDATION_RESULT_CHOICES = [
        ('VALID', 'Valid Location'),
        ('SUSPICIOUS', 'Suspicious Location'),
        ('SPOOFED', 'Likely Spoofed'),
        ('LOW_ACCURACY', 'Low Accuracy'),
        ('NETWORK_MISMATCH', 'Network Location Mismatch'),
        ('IMPOSSIBLE_SPEED', 'Impossible Speed Detected'),
        ('GEOFENCE_VIOLATION', 'Geofence Violation'),
    ]

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='gps_validations',
        help_text="Person whose location was validated"
    )

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='gps_validations',
        help_text="Expected site"
    )

    attendance_event = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gps_validations',
        help_text="Related attendance event"
    )

    validated_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Validation timestamp"
    )

    result = models.CharField(
        max_length=30,
        choices=VALIDATION_RESULT_CHOICES,
        db_index=True,
        help_text="Validation result"
    )

    # GPS location data
    gps_location = PointField(
        geography=True,
        srid=4326,
        help_text="Reported GPS coordinates"
    )

    gps_accuracy_meters = models.FloatField(
        help_text="GPS accuracy in meters"
    )

    # Network location (for cross-validation)
    network_location = PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text="Network-based location (cell tower/WiFi)"
    )

    gps_network_distance_meters = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance between GPS and network location"
    )

    # Geofence validation
    site_geofence_center = PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text="Site geofence center"
    )

    distance_from_geofence_meters = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance from geofence boundary"
    )

    is_within_geofence = models.BooleanField(
        default=True,
        help_text="Whether location is within geofence"
    )

    # Speed validation
    previous_location = PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text="Previous GPS location"
    )

    previous_location_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Previous location timestamp"
    )

    calculated_speed_kmh = models.FloatField(
        null=True,
        blank=True,
        help_text="Calculated travel speed (km/h)"
    )

    is_impossible_speed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Speed exceeds physical limits"
    )

    # Fraud indicators
    fraud_score = models.FloatField(
        default=0.0,
        help_text="GPS fraud probability (0-1)"
    )

    fraud_indicators = models.JSONField(
        default=list,
        help_text="List of detected fraud indicators"
    )

    # Metadata
    device_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Device reporting location"
    )

    validation_metadata = models.JSONField(
        default=dict,
        help_text="Additional validation data"
    )

    # Alert linkage
    noc_alert = models.ForeignKey(
        'noc.NOCAlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gps_validations',
        help_text="Related NOC alert"
    )

    flagged_for_review = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged for manual review"
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_gps_logs',
        help_text="Reviewer"
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Review timestamp"
    )

    review_notes = models.TextField(
        blank=True,
        help_text="Review findings"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_gps_validation_log'
        verbose_name = 'GPS Validation Log'
        verbose_name_plural = 'GPS Validation Logs'
        ordering = ['-validated_at']
        indexes = [
            models.Index(fields=['tenant', 'validated_at']),
            models.Index(fields=['person', 'validated_at']),
            models.Index(fields=['site', 'result', 'validated_at']),
            models.Index(fields=['is_impossible_speed', 'is_within_geofence']),
            models.Index(fields=['fraud_score']),
        ]

    def __str__(self):
        return f"GPS Validation: {self.person.peoplename} @ {self.site.name} ({self.result})"

    def flag_for_review(self, reason=""):
        """Flag for manual review."""
        self.flagged_for_review = True
        if reason:
            self.review_notes = f"Auto-flagged: {reason}"
        self.save()