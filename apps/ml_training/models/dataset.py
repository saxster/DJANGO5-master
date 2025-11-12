"""
ML Training Data Platform - Dataset Model.

Container for related training samples with versioning and metadata.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (focused single responsibility)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
from typing import Dict, Any

from django.db import models
from django.db.models import JSONField
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.peoples.models import People
from apps.tenants.models import TenantAwareModel
from .enums import DatasetType, DatasetStatus


class TrainingDataset(BaseModel, TenantAwareModel):
    """
    Container for related training samples with versioning and metadata.

    Groups training examples by domain (OCR, face recognition, etc.)
    with comprehensive versioning and quality tracking.
    """

    # Core identification
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        _("Dataset Name"),
        max_length=200,
        help_text="Descriptive name for the training dataset"
    )
    description = models.TextField(
        _("Description"),
        help_text="Detailed description of dataset purpose and content"
    )

    # Dataset configuration
    dataset_type = models.CharField(
        _("Dataset Type"),
        max_length=30,
        choices=DatasetType.choices,
        db_index=True
    )
    version = models.CharField(
        _("Version"),
        max_length=50,
        default="1.0",
        help_text="Dataset version (semantic versioning recommended)"
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=DatasetStatus.choices,
        default=DatasetStatus.DRAFT.value,
        db_index=True
    )

    # Content metadata
    total_examples = models.PositiveIntegerField(
        _("Total Examples"),
        default=0,
        help_text="Total number of training examples"
    )
    labeled_examples = models.PositiveIntegerField(
        _("Labeled Examples"),
        default=0,
        help_text="Number of fully labeled examples"
    )
    quality_score = models.FloatField(
        _("Quality Score"),
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text="Overall dataset quality score (0-1)"
    )

    # Configuration and metadata
    labeling_guidelines = models.TextField(
        _("Labeling Guidelines"),
        blank=True,
        help_text="Instructions for labelers"
    )
    metadata = JSONField(
        _("Metadata"),
        default=dict,
        help_text="Additional dataset configuration and metrics"
    )
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Tags for organization and search"
    )

    # Management
    created_by = models.ForeignKey(
        People,
        on_delete=models.PROTECT,
        related_name='created_datasets',
        verbose_name=_("Created By")
    )
    last_modified_by = models.ForeignKey(
        People,
        on_delete=models.PROTECT,
        related_name='modified_datasets',
        verbose_name=_("Last Modified By"),
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'ml_training_dataset'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['dataset_type', 'status']),
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['total_examples', 'labeled_examples']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(labeled_examples__lte=models.F('total_examples')),
                name='labeled_examples_not_exceed_total'
            ),
        ]

    def __str__(self):
        return f"{self.name} v{self.version} ({self.get_dataset_type_display()})"

    @property
    def completion_percentage(self) -> float:
        """Calculate percentage of labeled examples."""
        if self.total_examples == 0:
            return 0.0
        return (self.labeled_examples / self.total_examples) * 100

    @property
    def is_ready_for_training(self) -> bool:
        """Check if dataset has sufficient labeled examples for training."""
        min_examples = self.metadata.get('min_training_examples', 100)
        return (
            self.labeled_examples >= min_examples and
            self.status == DatasetStatus.ACTIVE.value
        )

    def update_stats(self):
        """Update example counts and quality metrics."""
        examples = self.training_examples.all()
        self.total_examples = examples.count()
        self.labeled_examples = examples.filter(is_labeled=True).count()

        if self.labeled_examples > 0:
            avg_quality = examples.filter(is_labeled=True).aggregate(
                avg_quality=models.Avg('quality_score')
            )['avg_quality']
            self.quality_score = avg_quality

        self.save(update_fields=['total_examples', 'labeled_examples', 'quality_score'])


__all__ = ['TrainingDataset']
