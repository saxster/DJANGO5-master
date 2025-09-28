"""
Signal handlers for the AI Mentor system.

These signals help keep the mentor's index up to date when code changes occur.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save)
def handle_model_change(sender, instance, created, **kwargs):
    """
    Handle model changes to trigger index updates if needed.

    This is mainly for tracking when Django models themselves change
    during development, which might affect the mentor's understanding
    of the codebase structure.
    """
    # Only track changes for apps we care about
    if hasattr(sender, '_meta') and sender._meta.app_label != 'mentor':
        logger.debug(
            f"Model change detected: {sender._meta.app_label}.{sender._meta.model_name}"
        )
        # TODO: Queue index update if running in auto-refresh mode


@receiver(post_delete)
def handle_model_deletion(sender, instance, **kwargs):
    """Handle model deletions for index cleanup."""
    if hasattr(sender, '_meta') and sender._meta.app_label != 'mentor':
        logger.debug(
            f"Model deletion detected: {sender._meta.app_label}.{sender._meta.model_name}"
        )