"""
Attendance Photo Model

Captures timestamped photos during clock-in/out for buddy punching prevention.

Features:
- S3 storage with automatic cleanup
- Face detection validation
- Photo quality scoring
- Integration with face recognition
- 90-day retention policy

Security:
- Photos stored in S3 (not database)
- Compressed to <200KB for mobile bandwidth
- Access controlled via signed URLs
- Automatic deletion after retention period
"""

from django.db import models
from django.contrib.gis.db import models as gis_models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel
from typing import Optional, Dict, Any
import uuid
import logging
from apps.core.exceptions.patterns import BUSINESS_LOGIC_EXCEPTIONS


logger = logging.getLogger(__name__)


class AttendancePhoto(BaseModel, TenantAwareModel):
    """
    Photo captured during clock-in or clock-out.

    Prevents buddy punching by requiring photo verification.
    """

    class PhotoType(models.TextChoices):
        CLOCK_IN = 'CLOCK_IN', 'Clock In Photo'
        CLOCK_OUT = 'CLOCK_OUT', 'Clock Out Photo'
        VERIFICATION = 'VERIFICATION', 'Additional Verification'

    class PhotoQuality(models.TextChoices):
        EXCELLENT = 'EXCELLENT', 'Excellent'
        GOOD = 'GOOD', 'Good'
        ACCEPTABLE = 'ACCEPTABLE', 'Acceptable'
        POOR = 'POOR', 'Poor'
        REJECTED = 'REJECTED', 'Rejected'

    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )

    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.CASCADE,
        related_name='photos',
        help_text="Attendance record this photo belongs to"
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_photos',
        help_text="Employee in the photo"
    )

    photo_type = models.CharField(
        max_length=20,
        choices=PhotoType.choices,
        help_text="When photo was captured"
    )

    # S3 storage
    image = models.ImageField(
        upload_to='attendance_photos/%Y/%m/%d/',
        max_length=500,
        help_text="Photo image stored in S3"
    )

    thumbnail = models.ImageField(
        upload_to='attendance_photos/thumbnails/%Y/%m/%d/',
        max_length=500,
        null=True,
        blank=True,
        help_text="Thumbnail version (150x150)"
    )

    # Photo metadata
    captured_at = models.DateTimeField(
        default=timezone.now,
        help_text="When photo was captured"
    )

    file_size_bytes = models.IntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )

    width = models.IntegerField(
        null=True,
        blank=True,
        help_text="Image width in pixels"
    )

    height = models.IntegerField(
        null=True,
        blank=True,
        help_text="Image height in pixels"
    )

    # Face detection results
    face_detected = models.BooleanField(
        default=False,
        help_text="Whether a face was detected in the photo"
    )

    face_count = models.IntegerField(
        default=0,
        help_text="Number of faces detected"
    )

    face_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Face detection confidence score (0-1)"
    )

    # Photo quality assessment
    quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall photo quality score (0-1)"
    )

    quality_rating = models.CharField(
        max_length=20,
        choices=PhotoQuality.choices,
        null=True,
        blank=True,
        help_text="Photo quality rating"
    )

    is_blurry = models.BooleanField(
        default=False,
        help_text="Whether photo is too blurry"
    )

    is_dark = models.BooleanField(
        default=False,
        help_text="Whether photo is too dark"
    )

    brightness = models.FloatField(
        null=True,
        blank=True,
        help_text="Brightness level (0-255)"
    )

    # Face recognition matching
    matches_enrolled_template = models.BooleanField(
        default=False,
        help_text="Whether photo matches enrolled face template"
    )

    match_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Face match confidence score (0-1)"
    )

    face_recognition_model = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Face recognition model used (Facenet512, VGGFace, etc.)"
    )

    # Validation results
    validation_passed = models.BooleanField(
        default=False,
        help_text="Whether photo passed all quality checks"
    )

    validation_errors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of validation errors (if any)"
    )

    # Metadata
    device_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Device information (model, OS, camera specs)"
    )

    gps_location = gis_models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text="GPS coordinates where photo was captured"
    )

    # Retention
    delete_after = models.DateTimeField(
        help_text="Auto-delete photo after this date (90-day retention)"
    )

    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag"
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When photo was deleted"
    )

    class Meta:
        db_table = 'attendance_photo'
        verbose_name = 'Attendance Photo'
        verbose_name_plural = 'Attendance Photos'
        indexes = [
            models.Index(fields=['tenant', 'employee', 'captured_at'], name='ap_tenant_emp_time_idx'),
            models.Index(fields=['tenant', 'attendance_record'], name='ap_tenant_record_idx'),
            models.Index(fields=['delete_after'], name='ap_delete_after_idx'),
            models.Index(fields=['is_deleted'], name='ap_is_deleted_idx'),
            models.Index(fields=['validation_passed'], name='ap_validation_idx'),
        ]
        ordering = ['-captured_at']

    def __str__(self):
        return f"{self.employee.username} - {self.photo_type} at {self.captured_at}"

    def save(self, *args, **kwargs):
        """Override save to set delete_after date"""
        if not self.delete_after:
            # Set to 90 days from now (configurable retention policy)
            from datetime import timedelta
            retention_days = getattr(settings, 'ATTENDANCE_PHOTO_RETENTION_DAYS', 90)
            self.delete_after = timezone.now() + timedelta(days=retention_days)

        super().save(*args, **kwargs)

    def clean(self):
        """Validate photo data"""
        # Must have at least one face detected
        if self.validation_passed and not self.face_detected:
            raise ValidationError("Photo must contain at least one detectable face")

        # Quality score must be sufficient
        if self.quality_score is not None and self.quality_score < 0.5:
            raise ValidationError(f"Photo quality too low: {self.quality_score}")

        # Resolution must meet minimum
        if self.width and self.height:
            if self.width < 480 or self.height < 480:
                raise ValidationError(f"Photo resolution too low: {self.width}x{self.height} (minimum: 480x480)")

    def get_signed_url(self, expiration: int = 3600) -> str:
        """
        Generate a signed URL for secure photo access.

        Args:
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Signed URL for photo access
        """
        try:
            from django.core.signing import TimestampSigner
            signer = TimestampSigner()

            # Generate signed URL
            # In production, this should use S3 presigned URLs
            if hasattr(self.image, 'url'):
                url = self.image.url
                signature = signer.sign(f"{self.uuid}:{expiration}")
                return f"{url}?signature={signature}"

            return ""

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to generate signed URL for photo {self.id}: {e}", exc_info=True)
            return ""

    def soft_delete(self) -> None:
        """
        Soft delete the photo (mark as deleted but don't remove file yet).

        Actual file deletion happens via cleanup task.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
        logger.info(f"Soft deleted attendance photo {self.id}")

    def hard_delete(self) -> None:
        """
        Permanently delete photo file from S3 and database record.
        """
        # Delete S3 file
        if self.image:
            self.image.delete(save=False)
        if self.thumbnail:
            self.thumbnail.delete(save=False)

        # Delete database record
        self.delete()
        logger.info(f"Hard deleted attendance photo {self.id}")

    @property
    def is_expired(self) -> bool:
        """Check if photo retention period has expired"""
        return timezone.now() > self.delete_after

    @property
    def days_until_deletion(self) -> int:
        """Get days remaining until automatic deletion"""
        delta = self.delete_after - timezone.now()
        return max(delta.days, 0)

    @property
    def quality_summary(self) -> Dict[str, Any]:
        """Get summary of photo quality metrics"""
        return {
            'quality_rating': self.quality_rating,
            'quality_score': self.quality_score,
            'face_detected': self.face_detected,
            'face_count': self.face_count,
            'is_blurry': self.is_blurry,
            'is_dark': self.is_dark,
            'resolution': f"{self.width}x{self.height}" if self.width and self.height else None,
            'file_size_kb': round(self.file_size_bytes / 1024, 2) if self.file_size_bytes else None,
        }


class PhotoQualityThreshold(models.Model):
    """
    Configuration for photo quality thresholds.

    Allows per-client/BU customization of photo requirements.
    """

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='photo_quality_thresholds',
        help_text="Client this threshold applies to"
    )

    # Quality thresholds
    min_quality_score = models.FloatField(
        default=0.5,
        help_text="Minimum quality score (0-1)"
    )

    min_width = models.IntegerField(
        default=480,
        help_text="Minimum image width in pixels"
    )

    min_height = models.IntegerField(
        default=480,
        help_text="Minimum image height in pixels"
    )

    max_file_size_kb = models.IntegerField(
        default=200,
        help_text="Maximum file size in kilobytes"
    )

    require_face_detection = models.BooleanField(
        default=True,
        help_text="Whether face must be detected in photo"
    )

    min_face_confidence = models.FloatField(
        default=0.8,
        help_text="Minimum face detection confidence (0-1)"
    )

    max_blur_threshold = models.FloatField(
        default=100.0,
        help_text="Maximum acceptable blur (Laplacian variance)"
    )

    min_brightness = models.IntegerField(
        default=50,
        help_text="Minimum brightness level (0-255)"
    )

    max_brightness = models.IntegerField(
        default=220,
        help_text="Maximum brightness level (0-255)"
    )

    # Feature flags
    photo_required_clock_in = models.BooleanField(
        default=True,
        help_text="Whether photo is required for clock-in"
    )

    photo_required_clock_out = models.BooleanField(
        default=False,
        help_text="Whether photo is required for clock-out"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this threshold configuration is active"
    )

    class Meta:
        db_table = 'photo_quality_threshold'
        verbose_name = 'Photo Quality Threshold'
        verbose_name_plural = 'Photo Quality Thresholds'

    def __str__(self):
        return f"{self.client.name} - Photo Quality Thresholds"
