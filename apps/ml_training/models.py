"""
ML Training Data Platform Models.

Enterprise-grade training data management with active learning,
versioning, and quality assurance capabilities.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (split into focused models)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid
import hashlib
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from django.db import models
from django.db.models import JSONField
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import People


class TrainingDataset(BaseModel, TenantAwareModel):
    """
    Container for related training samples with versioning and metadata.

    Groups training examples by domain (OCR, face recognition, etc.)
    with comprehensive versioning and quality tracking.
    """

    class DatasetType(models.TextChoices):
        OCR_METERS = ('OCR_METERS', 'OCR - Meter Readings')
        OCR_LICENSE_PLATES = ('OCR_LICENSE_PLATES', 'OCR - License Plates')
        OCR_DOCUMENTS = ('OCR_DOCUMENTS', 'OCR - Documents')
        FACE_RECOGNITION = ('FACE_RECOGNITION', 'Face Recognition')
        OBJECT_DETECTION = ('OBJECT_DETECTION', 'Object Detection')
        CLASSIFICATION = ('CLASSIFICATION', 'Image Classification')
        CUSTOM = ('CUSTOM', 'Custom Domain')

    class Status(models.TextChoices):
        DRAFT = ('DRAFT', 'Draft')
        ACTIVE = ('ACTIVE', 'Active')
        TRAINING = ('TRAINING', 'In Training')
        ARCHIVED = ('ARCHIVED', 'Archived')
        DEPRECATED = ('DEPRECATED', 'Deprecated')

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
        choices=Status.choices,
        default=Status.DRAFT.value,
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
        return self.labeled_examples >= min_examples and self.status == self.Status.ACTIVE.value

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


class TrainingExample(BaseModel, TenantAwareModel):
    """
    Individual training example with image and ground truth labels.

    Stores training data with rich metadata for active learning
    and quality assurance workflows.
    """

    class ExampleType(models.TextChoices):
        PRODUCTION = ('PRODUCTION', 'Production Data')
        SYNTHETIC = ('SYNTHETIC', 'Synthetic Data')
        AUGMENTED = ('AUGMENTED', 'Data Augmentation')
        CROWDSOURCED = ('CROWDSOURCED', 'Crowdsourced')
        EXPERT_LABELED = ('EXPERT_LABELED', 'Expert Labeled')

    class LabelingStatus(models.TextChoices):
        UNLABELED = ('UNLABELED', 'Unlabeled')
        IN_PROGRESS = ('IN_PROGRESS', 'In Progress')
        LABELED = ('LABELED', 'Labeled')
        REVIEWED = ('REVIEWED', 'Reviewed')
        DISPUTED = ('DISPUTED', 'Disputed')
        REJECTED = ('REJECTED', 'Rejected')

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
        ordering = ['-labeling_priority', '-created_at']
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


class LabelingTask(BaseModel, TenantAwareModel):
    """
    Human labeling task with quality assurance workflows.

    Manages the assignment and tracking of labeling work
    with quality control and inter-annotator agreement.
    """

    class TaskType(models.TextChoices):
        INITIAL_LABELING = ('INITIAL_LABELING', 'Initial Labeling')
        REVIEW = ('REVIEW', 'Quality Review')
        CORRECTION = ('CORRECTION', 'Correction')
        CONSENSUS = ('CONSENSUS', 'Consensus Resolution')
        VALIDATION = ('VALIDATION', 'Validation')

    class TaskStatus(models.TextChoices):
        ASSIGNED = ('ASSIGNED', 'Assigned')
        IN_PROGRESS = ('IN_PROGRESS', 'In Progress')
        COMPLETED = ('COMPLETED', 'Completed')
        REVIEWED = ('REVIEWED', 'Reviewed')
        REJECTED = ('REJECTED', 'Rejected')

    # Core identification
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        TrainingDataset,
        on_delete=models.CASCADE,
        related_name='labeling_tasks',
        verbose_name=_("Dataset")
    )
    examples = models.ManyToManyField(
        TrainingExample,
        related_name='labeling_tasks',
        verbose_name=_("Examples")
    )

    # Task configuration
    task_type = models.CharField(
        _("Task Type"),
        max_length=20,
        choices=TaskType.choices,
        default=TaskType.INITIAL_LABELING.value
    )
    task_status = models.CharField(
        _("Task Status"),
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.ASSIGNED.value,
        db_index=True
    )
    priority = models.PositiveIntegerField(
        _("Priority"),
        default=5,
        help_text="Task priority (1-10, higher = more urgent)"
    )

    # Assignment
    assigned_to = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='assigned_labeling_tasks',
        verbose_name=_("Assigned To")
    )
    assigned_at = models.DateTimeField(
        _("Assigned At"),
        auto_now_add=True
    )
    due_date = models.DateTimeField(
        _("Due Date"),
        null=True,
        blank=True
    )

    # Progress tracking
    started_at = models.DateTimeField(
        _("Started At"),
        null=True,
        blank=True
    )
    completed_at = models.DateTimeField(
        _("Completed At"),
        null=True,
        blank=True
    )
    examples_completed = models.PositiveIntegerField(
        _("Examples Completed"),
        default=0
    )
    total_examples = models.PositiveIntegerField(
        _("Total Examples"),
        default=0
    )

    # Quality metrics
    quality_score = models.FloatField(
        _("Quality Score"),
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text="Task quality score from review"
    )
    reviewer = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        related_name='reviewed_labeling_tasks',
        null=True,
        blank=True,
        verbose_name=_("Reviewer")
    )
    review_notes = models.TextField(
        _("Review Notes"),
        blank=True
    )

    # Instructions and metadata
    instructions = models.TextField(
        _("Instructions"),
        help_text="Specific instructions for this labeling task"
    )
    metadata = JSONField(
        _("Metadata"),
        default=dict,
        help_text="Task-specific configuration and tracking data"
    )

    class Meta:
        db_table = 'ml_labeling_task'
        ordering = ['-priority', '-assigned_at']
        indexes = [
            models.Index(fields=['assigned_to', 'task_status']),
            models.Index(fields=['dataset', 'task_type']),
            models.Index(fields=['priority', 'due_date']),
            models.Index(fields=['completed_at', 'quality_score']),
        ]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.assigned_to.peoplename}"

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        return (
            self.due_date and
            self.due_date < timezone.now() and
            self.task_status not in [self.TaskStatus.COMPLETED.value, self.TaskStatus.REVIEWED.value]
        )

    @property
    def completion_percentage(self) -> float:
        """Calculate task completion percentage."""
        if self.total_examples == 0:
            return 0.0
        return (self.examples_completed / self.total_examples) * 100

    def start_task(self):
        """Mark task as started."""
        if self.task_status == self.TaskStatus.ASSIGNED.value:
            self.task_status = self.TaskStatus.IN_PROGRESS.value
            self.started_at = timezone.now()
            self.save(update_fields=['task_status', 'started_at'])

    def complete_task(self):
        """Mark task as completed."""
        self.task_status = self.TaskStatus.COMPLETED.value
        self.completed_at = timezone.now()
        self.examples_completed = self.total_examples
        self.save(update_fields=['task_status', 'completed_at', 'examples_completed'])


# Export all models
__all__ = [
    'TrainingDataset',
    'TrainingExample',
    'LabelingTask',
]