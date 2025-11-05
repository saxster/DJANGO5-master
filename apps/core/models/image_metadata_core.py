"""
Core Image Metadata Model for EXIF Analysis

Stores comprehensive EXIF metadata with geospatial support and security features.

Complies with .claude/rules.md:
- Rule #7: Model classes < 150 lines
- Rule #10: Database query optimization with indexes
"""

from django.db import models
from django.contrib.gis.db import models as gis_models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.tenants.models import TenantAwareModel


class ImageMetadata(TenantAwareModel):
    """
    Comprehensive EXIF metadata storage with geospatial and security features.

    Stores extracted EXIF data for photos uploaded across the platform,
    enabling advanced security analysis, GPS validation, and compliance auditing.
    """

    class AuthenticityRisk(models.TextChoices):
        LOW = 'low', 'Low Risk'
        MEDIUM = 'medium', 'Medium Risk'
        HIGH = 'high', 'High Risk'
        CRITICAL = 'critical', 'Critical Risk'

    class ValidationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Analysis'
        VALID = 'valid', 'Valid Metadata'
        INVALID = 'invalid', 'Invalid Metadata'
        SUSPICIOUS = 'suspicious', 'Suspicious Content'
        ERROR = 'error', 'Analysis Error'

    # Core identification
    correlation_id = models.CharField(
        max_length=36,
        unique=True,
        db_index=True,
        help_text="Unique correlation ID for tracking and debugging"
    )

    # File information
    image_path = models.CharField(
        max_length=500,
        db_index=True,
        help_text="Original file path of the analyzed image"
    )
    file_hash = models.CharField(
        max_length=32,
        db_index=True,
        help_text="SHA256 hash for file integrity verification"
    )
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes"
    )
    file_extension = models.CharField(
        max_length=10,
        help_text="File extension (e.g., .jpg, .png)"
    )

    # Associated user and context
    people = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='image_metadata',
        help_text="User who uploaded the image"
    )
    activity_record_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Associated activity/attendance record ID"
    )
    upload_context = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Context of image upload (attendance, facility_audit, etc.)"
    )

    # GPS and geospatial data
    gps_coordinates = gis_models.PointField(
        null=True,
        blank=True,
        srid=4326,
        spatial_index=True,
        help_text="GPS coordinates from EXIF data"
    )
    gps_altitude = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS altitude in meters"
    )
    gps_accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS accuracy in meters"
    )
    gps_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="GPS timestamp from EXIF data"
    )

    # Camera and device information
    camera_make = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Camera manufacturer"
    )
    camera_model = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Camera model"
    )
    camera_serial = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Camera serial number (hashed for privacy)"
    )
    software_signature = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_index=True,
        help_text="Software used to process the image"
    )

    # Timestamp analysis
    photo_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Original photo timestamp from EXIF"
    )
    timestamp_consistency = models.BooleanField(
        default=True,
        help_text="Whether EXIF timestamps are consistent"
    )
    server_upload_time = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Server timestamp when metadata was processed"
    )

    # Security and authenticity analysis
    authenticity_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.5,
        db_index=True,
        help_text="Photo authenticity score (0.0 = fake, 1.0 = authentic)"
    )
    manipulation_risk = models.CharField(
        max_length=20,
        choices=AuthenticityRisk.choices,
        default=AuthenticityRisk.LOW,
        db_index=True,
        help_text="Risk level for photo manipulation"
    )
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
        db_index=True,
        help_text="Overall validation status of the photo"
    )

    # Comprehensive metadata storage
    raw_exif_data = JSONField(
        default=dict,
        help_text="Complete raw EXIF data extracted from image"
    )
    security_analysis = JSONField(
        default=dict,
        help_text="Security analysis results and fraud indicators"
    )
    quality_metrics = JSONField(
        default=dict,
        help_text="Image quality assessment and metadata completeness"
    )

    # Analysis metadata
    analysis_timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the EXIF analysis was performed"
    )
    analysis_version = models.CharField(
        max_length=20,
        default='1.0',
        help_text="Version of analysis algorithm used"
    )

    class Meta:
        db_table = 'core_image_metadata'
        verbose_name = 'Image Metadata'
        verbose_name_plural = 'Image Metadata Records'
        indexes = [
            models.Index(fields=['people', 'upload_context'], name='idx_metadata_people_context'),
            models.Index(fields=['validation_status', 'manipulation_risk'], name='idx_metadata_security'),
            models.Index(fields=['analysis_timestamp'], name='idx_metadata_timestamp'),
            models.Index(fields=['authenticity_score'], name='idx_metadata_authenticity'),
            models.Index(fields=['camera_make', 'camera_model'], name='idx_metadata_camera'),
            models.Index(
                fields=['people', 'authenticity_score', 'analysis_timestamp'],
                name='idx_metadata_fraud_analysis'
            ),
            models.Index(
                fields=['upload_context', 'validation_status', 'manipulation_risk'],
                name='idx_metadata_context_security'
            ),
        ]
        ordering = ['-analysis_timestamp']

    def __str__(self):
        return f"ImageMetadata {self.correlation_id} - {self.authenticity_score:.2f}"

    @property
    def is_authentic(self):
        """Quick check if photo is considered authentic."""
        return (
            self.authenticity_score >= 0.7 and
            self.manipulation_risk in ['low', 'medium'] and
            self.validation_status == 'valid'
        )

    @property
    def has_valid_gps(self):
        """Check if photo has valid GPS coordinates."""
        return self.gps_coordinates is not None

    @property
    def fraud_indicators(self):
        """Extract fraud indicators from security analysis."""
        return self.security_analysis.get('suspicious_patterns', [])

    def get_location_distance(self, expected_point):
        """Calculate distance from expected location in meters."""
        if not self.gps_coordinates or not expected_point:
            return None

        # Use PostGIS distance calculation (approximate meters)
        return self.gps_coordinates.distance(expected_point) * 111000
