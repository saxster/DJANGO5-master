"""
ML Training Data Platform - Enumeration Types.

Centralized enum definitions for dataset types, statuses, and labeling workflows.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (enums in dedicated module)
- Rule #9: Specific exception handling
"""

from django.db import models


class DatasetType(models.TextChoices):
    """Types of training datasets supported."""
    OCR_METERS = ('OCR_METERS', 'OCR - Meter Readings')
    OCR_LICENSE_PLATES = ('OCR_LICENSE_PLATES', 'OCR - License Plates')
    OCR_DOCUMENTS = ('OCR_DOCUMENTS', 'OCR - Documents')
    FACE_RECOGNITION = ('FACE_RECOGNITION', 'Face Recognition')
    OBJECT_DETECTION = ('OBJECT_DETECTION', 'Object Detection')
    CLASSIFICATION = ('CLASSIFICATION', 'Image Classification')
    CUSTOM = ('CUSTOM', 'Custom Domain')


class DatasetStatus(models.TextChoices):
    """Lifecycle status for datasets."""
    DRAFT = ('DRAFT', 'Draft')
    ACTIVE = ('ACTIVE', 'Active')
    TRAINING = ('TRAINING', 'In Training')
    ARCHIVED = ('ARCHIVED', 'Archived')
    DEPRECATED = ('DEPRECATED', 'Deprecated')


class ExampleType(models.TextChoices):
    """Source types for training examples."""
    PRODUCTION = ('PRODUCTION', 'Production Data')
    SYNTHETIC = ('SYNTHETIC', 'Synthetic Data')
    AUGMENTED = ('AUGMENTED', 'Data Augmentation')
    CROWDSOURCED = ('CROWDSOURCED', 'Crowdsourced')
    EXPERT_LABELED = ('EXPERT_LABELED', 'Expert Labeled')


class LabelingStatus(models.TextChoices):
    """Status of labeling process for examples."""
    UNLABELED = ('UNLABELED', 'Unlabeled')
    IN_PROGRESS = ('IN_PROGRESS', 'In Progress')
    LABELED = ('LABELED', 'Labeled')
    REVIEWED = ('REVIEWED', 'Reviewed')
    DISPUTED = ('DISPUTED', 'Disputed')
    REJECTED = ('REJECTED', 'Rejected')


class TaskType(models.TextChoices):
    """Types of labeling tasks."""
    INITIAL_LABELING = ('INITIAL_LABELING', 'Initial Labeling')
    REVIEW = ('REVIEW', 'Quality Review')
    CORRECTION = ('CORRECTION', 'Correction')
    CONSENSUS = ('CONSENSUS', 'Consensus Resolution')
    VALIDATION = ('VALIDATION', 'Validation')


class TaskStatus(models.TextChoices):
    """Status of labeling tasks."""
    ASSIGNED = ('ASSIGNED', 'Assigned')
    IN_PROGRESS = ('IN_PROGRESS', 'In Progress')
    COMPLETED = ('COMPLETED', 'Completed')
    REVIEWED = ('REVIEWED', 'Reviewed')
    REJECTED = ('REJECTED', 'Rejected')


__all__ = [
    'DatasetType',
    'DatasetStatus',
    'ExampleType',
    'LabelingStatus',
    'TaskType',
    'TaskStatus',
]
