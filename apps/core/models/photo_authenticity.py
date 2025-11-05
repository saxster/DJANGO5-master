"""
Photo Authenticity Logging Model

Audit log for photo authenticity validations and fraud detection.

Complies with .claude/rules.md Rule #7: Model classes < 150 lines
"""

from django.db import models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.tenants.models import TenantAwareModel


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
        'core.ImageMetadata',
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
