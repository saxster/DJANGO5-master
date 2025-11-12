"""
ML Training signals for automatic model updates and relationships.

Handles automatic dataset statistics, quality calculations,
and cross-model updates.
"""

import logging
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from .models import TrainingDataset, TrainingExample, LabelingTask
from apps.core.exceptions.patterns import CELERY_EXCEPTIONS

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import ENCRYPTION_EXCEPTIONS


logger = logging.getLogger(__name__)


@receiver(post_save, sender=TrainingExample)
def update_dataset_stats_on_example_save(sender, instance, created, **kwargs):
    """Update dataset statistics when training example is saved."""
    try:
        instance.dataset.update_stats()
        logger.debug(f"Updated stats for dataset {instance.dataset.id}")
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Failed to update dataset stats: {str(e)}")


@receiver(post_delete, sender=TrainingExample)
def update_dataset_stats_on_example_delete(sender, instance, **kwargs):
    """Update dataset statistics when training example is deleted."""
    try:
        instance.dataset.update_stats()
        logger.debug(f"Updated stats for dataset {instance.dataset.id} after deletion")
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Failed to update dataset stats on deletion: {str(e)}")


@receiver(post_save, sender=TrainingExample)
def calculate_image_hash_on_save(sender, instance, created, **kwargs):
    """Calculate image hash for new training examples."""
    if created and not instance.image_hash and instance.image_path:
        try:
            instance.image_hash = instance.calculate_image_hash()
            if instance.image_hash:
                instance.save(update_fields=['image_hash'])
                logger.debug(f"Calculated image hash for example {instance.id}")
        except ENCRYPTION_EXCEPTIONS as e:
            logger.error(f"Failed to calculate image hash: {str(e)}")


@receiver(m2m_changed, sender=LabelingTask.examples.through)
def update_labeling_task_totals(sender, instance, action, pk_set, **kwargs):
    """Update labeling task totals when examples are added/removed."""
    if action in ['post_add', 'post_remove', 'post_clear']:
        try:
            instance.total_examples = instance.examples.count()
            instance.save(update_fields=['total_examples'])
            logger.debug(f"Updated totals for labeling task {instance.id}")
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to update labeling task totals: {str(e)}")


@receiver(post_save, sender=LabelingTask)
def auto_start_labeling_task(sender, instance, created, **kwargs):
    """Automatically start labeling task if assigned."""
    if (created and
        instance.task_status == LabelingTask.TaskStatus.ASSIGNED.value and
        instance.assigned_to):
        try:
            # Auto-start task after assignment
            instance.start_task()
            logger.info(f"Auto-started labeling task {instance.id}")
        except CELERY_EXCEPTIONS as e:
            logger.error(f"Failed to auto-start labeling task: {str(e)}")


@receiver(post_save, sender=TrainingExample)
def update_labeling_status_flags(sender, instance, **kwargs):
    """Update labeling status flags based on ground truth data."""
    try:
        # Determine if example is labeled based on ground truth
        has_ground_truth = bool(
            instance.ground_truth_text.strip() or
            instance.ground_truth_data
        )

        if has_ground_truth and not instance.is_labeled:
            instance.is_labeled = True
            if instance.labeling_status == TrainingExample.LabelingStatus.UNLABELED.value:
                instance.labeling_status = TrainingExample.LabelingStatus.LABELED.value
            instance.save(update_fields=['is_labeled', 'labeling_status'])
            logger.debug(f"Marked example {instance.id} as labeled")

        elif not has_ground_truth and instance.is_labeled:
            instance.is_labeled = False
            instance.labeling_status = TrainingExample.LabelingStatus.UNLABELED.value
            instance.save(update_fields=['is_labeled', 'labeling_status'])
            logger.debug(f"Marked example {instance.id} as unlabeled")

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Failed to update labeling status flags: {str(e)}")