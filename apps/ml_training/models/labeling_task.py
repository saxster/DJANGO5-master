"""
ML Training Data Platform - Labeling Task Model.

Human labeling task management with quality assurance workflows.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (focused single responsibility)
- Rule #9: Specific exception handling
- Rule #12: Query optimization with indexes
"""

import uuid

from django.db import models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.models import BaseModel, People
from apps.tenants.models import TenantAwareModel
from .dataset import TrainingDataset
from .training_example import TrainingExample
from .enums import TaskType, TaskStatus


class LabelingTask(BaseModel, TenantAwareModel):
    """
    Human labeling task with quality assurance workflows.

    Manages the assignment and tracking of labeling work
    with quality control and inter-annotator agreement.
    """

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
            self.task_status not in [TaskStatus.COMPLETED.value, TaskStatus.REVIEWED.value]
        )

    @property
    def completion_percentage(self) -> float:
        """Calculate task completion percentage."""
        if self.total_examples == 0:
            return 0.0
        return (self.examples_completed / self.total_examples) * 100

    def start_task(self):
        """Mark task as started."""
        if self.task_status == TaskStatus.ASSIGNED.value:
            self.task_status = TaskStatus.IN_PROGRESS.value
            self.started_at = timezone.now()
            self.save(update_fields=['task_status', 'started_at'])

    def complete_task(self):
        """Mark task as completed."""
        self.task_status = TaskStatus.COMPLETED.value
        self.completed_at = timezone.now()
        self.examples_completed = self.total_examples
        self.save(update_fields=['task_status', 'completed_at', 'examples_completed'])


__all__ = ['LabelingTask']
