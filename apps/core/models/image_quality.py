"""
Image Quality Assessment Model

Image quality scoring and recommendations for photo uploads.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

from django.db import models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.tenants.models import TenantAwareModel


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
        'core.ImageMetadata',
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
