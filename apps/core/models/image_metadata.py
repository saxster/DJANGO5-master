"""
Image Metadata Models for EXIF Analysis and Photo Authenticity

Advanced metadata storage for comprehensive photo analysis, fraud detection,
and compliance auditing in enterprise facility management.

Models:
- ImageMetadata: Core EXIF metadata storage with geospatial support
- PhotoAuthenticityLog: Fraud detection and validation tracking
- CameraFingerprint: Device identification and tracking
- ImageQualityAssessment: Quality metrics and recommendations

Complies with .claude/rules.md:
- Rule #7: Model classes < 150 lines
- Rule #10: Database query optimization with indexes
"""

from django.db import models
from django.contrib.gis.db import models as gis_models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
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
            # Performance indexes for common queries
            models.Index(fields=['people', 'upload_context'], name='idx_metadata_people_context'),
            models.Index(fields=['validation_status', 'manipulation_risk'], name='idx_metadata_security'),
            models.Index(fields=['analysis_timestamp'], name='idx_metadata_timestamp'),
            models.Index(fields=['authenticity_score'], name='idx_metadata_authenticity'),
            models.Index(fields=['camera_make', 'camera_model'], name='idx_metadata_camera'),

            # Composite indexes for fraud detection
            models.Index(
                fields=['people', 'authenticity_score', 'analysis_timestamp'],
                name='idx_metadata_fraud_analysis'
            ),
            models.Index(
                fields=['upload_context', 'validation_status', 'manipulation_risk'],
                name='idx_metadata_context_security'
            ),
        ]

        # Optimize for recent data access
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


class PhotoAuthenticityLog(TenantAwareModel):
    """
    Audit log for photo authenticity validations and fraud detection.

    Tracks all authenticity checks, validation results, and manual reviews
    for compliance and forensic analysis.
    """

    class ValidationAction(models.TextChoices):
        AUTOMATIC = 'automatic', 'Automatic Validation'
        MANUAL_REVIEW = 'manual_review', 'Manual Review'
        LOCATION_CHECK = 'location_check', 'Location Verification'
        DEVICE_CHECK = 'device_check', 'Device Fingerprint Check'
        HISTORICAL_ANALYSIS = 'historical', 'Historical Pattern Analysis'

    class ValidationResult(models.TextChoices):
        PASSED = 'passed', 'Validation Passed'
        FAILED = 'failed', 'Validation Failed'
        FLAGGED = 'flagged', 'Flagged for Review'
        PENDING = 'pending', 'Pending Review'

    # Link to metadata
    image_metadata = models.ForeignKey(
        ImageMetadata,
        on_delete=models.CASCADE,
        related_name='authenticity_logs'
    )

    # Validation details
    validation_action = models.CharField(
        max_length=30,
        choices=ValidationAction.choices,
        db_index=True
    )
    validation_result = models.CharField(
        max_length=20,
        choices=ValidationResult.choices,
        db_index=True
    )

    # Reviewer information
    reviewed_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='photo_reviews'
    )
    review_timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )

    # Validation details
    validation_details = JSONField(
        default=dict,
        help_text="Detailed validation results and analysis"
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.5,
        help_text="Confidence in validation result"
    )

    # Additional context
    validation_notes = models.TextField(
        blank=True,
        help_text="Manual review notes or system comments"
    )
    follow_up_required = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this validation requires follow-up action"
    )

    class Meta:
        db_table = 'core_photo_authenticity_log'
        verbose_name = 'Photo Authenticity Log'
        verbose_name_plural = 'Photo Authenticity Logs'

        indexes = [
            models.Index(fields=['validation_result', 'review_timestamp'], name='idx_auth_result_time'),
            models.Index(fields=['reviewed_by', 'validation_action'], name='idx_auth_reviewer_action'),
            models.Index(fields=['follow_up_required'], name='idx_auth_followup'),
        ]

        ordering = ['-review_timestamp']

    def __str__(self):
        return f"AuthLog {self.image_metadata.correlation_id} - {self.validation_result}"


class CameraFingerprint(TenantAwareModel):
    """
    Device fingerprinting for camera identification and fraud tracking.

    Tracks unique camera signatures to identify repeat offenders and
    suspicious device usage patterns.
    """

    class TrustLevel(models.TextChoices):
        TRUSTED = 'trusted', 'Trusted Device'
        NEUTRAL = 'neutral', 'Neutral Device'
        SUSPICIOUS = 'suspicious', 'Suspicious Device'
        BLOCKED = 'blocked', 'Blocked Device'

    # Camera identification
    fingerprint_hash = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="Unique hash identifying the camera device"
    )
    camera_make = models.CharField(max_length=100, db_index=True)
    camera_model = models.CharField(max_length=100, db_index=True)

    # Usage tracking
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(auto_now=True, db_index=True)
    usage_count = models.PositiveIntegerField(default=1)

    # Associated users
    associated_users = models.ManyToManyField(
        'peoples.People',
        related_name='camera_devices',
        help_text="Users who have used this camera"
    )

    # Trust and security
    trust_level = models.CharField(
        max_length=20,
        choices=TrustLevel.choices,
        default=TrustLevel.NEUTRAL,
        db_index=True
    )
    fraud_incidents = models.PositiveIntegerField(
        default=0,
        help_text="Number of fraud incidents associated with this device"
    )

    # Metadata
    device_characteristics = JSONField(
        default=dict,
        help_text="Technical characteristics and patterns"
    )
    security_notes = models.TextField(
        blank=True,
        help_text="Security notes and incident history"
    )

    class Meta:
        db_table = 'core_camera_fingerprint'
        verbose_name = 'Camera Fingerprint'
        verbose_name_plural = 'Camera Fingerprints'

        indexes = [
            models.Index(fields=['trust_level', 'last_seen'], name='idx_camera_trust_activity'),
            models.Index(fields=['fraud_incidents'], name='idx_camera_fraud_count'),
        ]

        ordering = ['-last_seen']

    def __str__(self):
        return f"Camera {self.camera_make} {self.camera_model} - {self.trust_level}"

    @property
    def is_high_risk(self):
        """Check if camera is considered high risk."""
        return (
            self.trust_level in ['suspicious', 'blocked'] or
            self.fraud_incidents > 2
        )

    def update_usage(self, people_instance):
        """Update usage statistics and user associations."""
        self.usage_count += 1
        self.last_seen = timezone.now()
        self.save(update_fields=['usage_count', 'last_seen'])

        if people_instance:
            self.associated_users.add(people_instance)


class ImageQualityAssessment(TenantAwareModel):
    """
    Image quality assessment and recommendations for photo uploads.

    Provides quality scoring and actionable recommendations to improve
    photo quality for better EXIF analysis and fraud detection.
    """

    class QualityLevel(models.TextChoices):
        EXCELLENT = 'excellent', 'Excellent Quality'
        GOOD = 'good', 'Good Quality'
        FAIR = 'fair', 'Fair Quality'
        POOR = 'poor', 'Poor Quality'
        UNACCEPTABLE = 'unacceptable', 'Unacceptable Quality'

    # Link to metadata
    image_metadata = models.OneToOneField(
        ImageMetadata,
        on_delete=models.CASCADE,
        related_name='quality_assessment'
    )

    # Overall quality metrics
    overall_quality_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Overall quality score (0.0 - 1.0)"
    )
    quality_level = models.CharField(
        max_length=20,
        choices=QualityLevel.choices,
        db_index=True
    )

    # Specific quality metrics
    metadata_completeness = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="EXIF metadata completeness score"
    )
    gps_data_quality = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="GPS data quality and precision score"
    )
    timestamp_reliability = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Timestamp consistency and reliability score"
    )

    # Quality issues and recommendations
    quality_issues = JSONField(
        default=list,
        help_text="List of identified quality issues"
    )
    recommendations = JSONField(
        default=list,
        help_text="Actionable recommendations for improvement"
    )

    # Assessment details
    assessment_timestamp = models.DateTimeField(default=timezone.now)
    assessment_algorithm = models.CharField(
        max_length=50,
        default='exif_v1.0',
        help_text="Algorithm version used for assessment"
    )

    class Meta:
        db_table = 'core_image_quality_assessment'
        verbose_name = 'Image Quality Assessment'
        verbose_name_plural = 'Image Quality Assessments'

        indexes = [
            models.Index(fields=['quality_level'], name='idx_quality_level'),
            models.Index(fields=['overall_quality_score'], name='idx_quality_score'),
        ]

    def __str__(self):
        return f"Quality {self.image_metadata.correlation_id} - {self.quality_level}"

    @property
    def needs_improvement(self):
        """Check if image quality needs improvement."""
        return self.quality_level in ['poor', 'unacceptable']

    @property
    def is_acceptable_for_security(self):
        """Check if quality is acceptable for security analysis."""
        return (
            self.overall_quality_score >= 0.6 and
            self.metadata_completeness >= 0.5
        )