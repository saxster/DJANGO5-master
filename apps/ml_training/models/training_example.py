"""
ML Training Data Platform - Training Example Model.

Individual training examples with images and ground truth labels.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (focused single responsibility)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
import hashlib
from typing import Dict, Any

from django.db import models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel
from .dataset import TrainingDataset
from .enums import ExampleType, LabelingStatus


class TrainingExample(BaseModel, TenantAwareModel):
    """
    Individual training example with image and ground truth labels.

    Stores training data with rich metadata for active learning
    and quality assurance workflows.
    """

    # Core identification
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        TrainingDataset,
        on_delete=models.CASCADE,
        related_name='training_examples',
        verbose_name=_("Dataset"),
        db_index=True
    )

    # Image data
    image_path = models.CharField(
        _("Image Path"),
        max_length=500,
        help_text="Path to the training image file"
    )
    image_hash = models.CharField(
        _("Image Hash"),
        max_length=64,
        unique=True,
        help_text="SHA256 hash for deduplication"
    )
    image_width = models.PositiveIntegerField(
        _("Image Width"),
        null=True,
        blank=True
    )
    image_height = models.PositiveIntegerField(
        _("Image Height"),
        null=True,
        blank=True
    )
    file_size = models.PositiveIntegerField(
        _("File Size"),
        null=True,
        blank=True,
        help_text="File size in bytes"
    )

    # Ground truth labels
    ground_truth_text = models.TextField(
        _("Ground Truth Text"),
        blank=True,
        help_text="Correct text/label for this example"
    )
    ground_truth_data = JSONField(
        _("Ground Truth Data"),
        default=dict,
        help_text="Structured ground truth (bounding boxes, classifications, etc.)"
    )

    # Labeling metadata
    example_type = models.CharField(
        _("Example Type"),
        max_length=20,
        choices=ExampleType.choices,
        default=ExampleType.PRODUCTION.value
    )
    labeling_status = models.CharField(
        _("Labeling Status"),
        max_length=20,
        choices=LabelingStatus.choices,
        default=LabelingStatus.UNLABELED.value,
        db_index=True
    )
    is_labeled = models.BooleanField(
        _("Is Labeled"),
        default=False,
        db_index=True,
        help_text="Whether this example has valid ground truth"
    )

    # Quality and difficulty metrics
    quality_score = models.FloatField(
        _("Quality Score"),
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text="Label quality score (0-1)"
    )
    difficulty_score = models.FloatField(
        _("Difficulty Score"),
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text="Example difficulty for learning (0-1)"
    )
    uncertainty_score = models.FloatField(
        _("Uncertainty Score"),
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text="Model uncertainty on this example (0-1)"
    )

    # Source tracking
    source_system = models.CharField(
        _("Source System"),
        max_length=100,
        blank=True,
        help_text="System that generated this example"
    )
    source_id = models.CharField(
        _("Source ID"),
        max_length=100,
        blank=True,
        help_text="Original record ID in source system"
    )
    capture_metadata = JSONField(
        _("Capture Metadata"),
        default=dict,
        help_text="Original capture conditions and metadata"
    )

    # Active learning
    selected_for_labeling = models.BooleanField(
        _("Selected for Labeling"),
        default=False,
        db_index=True,
        help_text="Selected by active learning algorithm"
    )
    labeling_priority = models.PositiveIntegerField(
        _("Labeling Priority"),
        default=0,
        help_text="Priority for labeling (higher = more important)"
    )

    class Meta:
        db_table = 'ml_training_example'
        ordering = ['-labeling_priority', '-cdtz']
        indexes = [
            models.Index(fields=['dataset', 'labeling_status']),
            models.Index(fields=['is_labeled', 'quality_score']),
            models.Index(fields=['selected_for_labeling', 'labeling_priority']),
            models.Index(fields=['uncertainty_score', 'difficulty_score']),
            models.Index(fields=['source_system', 'source_id']),
        ]

    def __str__(self):
        return f"{self.dataset.name} - Example {self.uuid.hex[:8]}"

    def calculate_image_hash(self) -> str:
        """Calculate SHA256 hash of image file."""
        if not self.image_path:
            return ""

        try:
            with open(self.image_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except (IOError, OSError):
            return ""

    @property
    def needs_review(self) -> bool:
        """Check if example needs quality review."""
        return (
            self.is_labeled and
            (self.quality_score is None or self.quality_score < 0.8)
        )

    @property
    def is_high_value(self) -> bool:
        """Check if example is high value for training."""
        return (
            self.uncertainty_score and self.uncertainty_score > 0.7 or
            self.difficulty_score and self.difficulty_score > 0.7
        )


__all__ = ['TrainingExample']
