"""
Wellness App Signals

Handles automatic creation of user progress tracking, content delivery scheduling,
achievement notifications, and analytics updates for the wellness education system.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import WellnessUserProgress, WellnessContentInteraction, WellnessContent
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_wellness_user_progress(sender, instance, created, **kwargs):
    """Automatically create wellness progress tracking for new users"""
    if created:
        try:
            # Set default enabled categories based on workplace context
            default_categories = [
                'mental_health',
                'workplace_health',
                'stress_management',
                'preventive_care'
            ]

            WellnessUserProgress.objects.get_or_create(
                user=instance,
                defaults={
                    'tenant': getattr(instance, 'tenant', None),
                    'preferred_content_level': 'short_read',
                    'enabled_categories': default_categories,
                    'daily_tip_enabled': True,
                    'contextual_delivery_enabled': True,
                    'milestone_alerts_enabled': True,
                }
            )
            logger.info(f"Created wellness progress tracking for user {instance.peoplename}")
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to create wellness progress for user {instance.id}: {e}")


@receiver(post_save, sender=WellnessContentInteraction)
def handle_wellness_interaction_created(sender, instance, created, **kwargs):
    """Handle wellness content interaction events"""

    if created:
        logger.debug(f"New wellness interaction: {instance.user.peoplename} {instance.interaction_type} '{instance.content.title}'")

        # Check for milestone achievements
        try:
            check_wellness_milestones(instance.user)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to check wellness milestones for user {instance.user.id}: {e}")

        # Schedule follow-up content if user showed high engagement
        try:
            if instance.engagement_score >= 4:
                schedule_follow_up_content(instance)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to schedule follow-up content: {e}")


def check_wellness_milestones(user):
    """Check and award wellness milestones and achievements"""

    try:
        progress = user.wellness_progress
    except WellnessUserProgress.DoesNotExist:
        logger.warning(f"No wellness progress found for user {user.id}")
        return

    # Check for new achievements
    new_achievements = progress.check_and_award_achievements()

    if new_achievements and progress.milestone_alerts_enabled:
        # Queue milestone notification
        logger.info(f"Queuing milestone notifications for {user.peoplename}: {new_achievements}")

        try:
            # TODO: Implement milestone notification system
            # This could integrate with MQTT for real-time notifications
            from .services.milestone_notifications import queue_achievement_notification
            queue_achievement_notification(user, new_achievements)
        except ImportError:
            # Milestone notification service not implemented yet
            pass
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to queue milestone notification: {e}")


def schedule_follow_up_content(interaction):
    """Schedule follow-up wellness content based on user engagement"""

    if interaction.content.related_topics:
        try:
            # TODO: Implement follow-up content scheduling
            logger.debug(f"Scheduling follow-up content for user {interaction.user.id}")

            # Example of how this might work:
            # from .services.content_scheduler import schedule_related_content
            # schedule_related_content(interaction.user, interaction.content.related_topics)

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to schedule follow-up content: {e}")


@receiver(post_save, sender=WellnessContent)
def handle_wellness_content_updated(sender, instance, created, **kwargs):
    """Handle wellness content creation/update events"""

    if created:
        logger.info(f"New wellness content created: '{instance.title}' in category {instance.category}")

        # Check if content needs immediate verification
        if instance.needs_verification:
            logger.warning(f"New content '{instance.title}' needs evidence verification")

        # Queue content for personalization engine training
        try:
            # TODO: Update ML models with new content
            logger.debug("Queuing ML model update for new wellness content")
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to update ML models: {e}")

    else:
        logger.debug(f"Wellness content updated: '{instance.title}'")


@receiver(post_delete, sender=WellnessContent)
def handle_wellness_content_deleted(sender, instance, **kwargs):
    """Handle wellness content deletion"""
    logger.info(f"Wellness content deleted: '{instance.title}' (Category: {instance.category})")


# Daily wellness tip scheduling signal
@receiver(post_save, sender=WellnessUserProgress)
def handle_wellness_preferences_updated(sender, instance, created, **kwargs):
    """Handle changes to user wellness preferences"""

    if created:
        logger.info(f"Wellness preferences created for user {instance.user.peoplename}")

        # Schedule first daily tip if enabled
        if instance.daily_tip_enabled:
            try:
                schedule_daily_wellness_tip(instance.user)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to schedule initial daily tip: {e}")

    else:
        logger.debug(f"Wellness preferences updated for user {instance.user.peoplename}")

        # Update scheduled content based on preference changes
        if instance.daily_tip_enabled:
            try:
                reschedule_daily_wellness_content(instance.user)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to reschedule wellness content: {e}")


def schedule_daily_wellness_tip(user):
    """Schedule daily wellness tip delivery for user"""
    try:
        progress = user.wellness_progress

        if not progress.daily_tip_enabled:
            return

        # TODO: Implement daily tip scheduling
        logger.debug(f"Scheduling daily wellness tips for user {user.peoplename}")

        # Example of how this might work:
        # from .services.daily_scheduler import schedule_daily_tips
        # schedule_daily_tips(user, progress.preferred_delivery_time)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to schedule daily wellness tip for user {user.id}: {e}")


def reschedule_daily_wellness_content(user):
    """Reschedule daily wellness content based on updated preferences"""
    try:
        # TODO: Update scheduled content delivery
        logger.debug(f"Rescheduling wellness content for user {user.peoplename}")

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to reschedule wellness content: {e}")


# Analytics and effectiveness tracking
@receiver(post_save, sender=WellnessContentInteraction)
def update_content_effectiveness_metrics(sender, instance, created, **kwargs):
    """Update content effectiveness metrics for analytics"""

    if created and instance.is_positive_interaction:
        try:
            # TODO: Update content effectiveness analytics
            logger.debug(f"Updating effectiveness metrics for content {instance.content.id}")

            # This could involve:
            # - Updating content popularity scores
            # - Training personalization models
            # - Adjusting content priority scores based on engagement

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to update effectiveness metrics: {e}")


# Crisis intervention integration
@receiver(post_save, sender='journal.JournalEntry')
def trigger_crisis_wellness_content(sender, instance, created, **kwargs):
    """Trigger immediate wellness content for crisis situations"""

    if not created:
        return

    try:
        # Check if this journal entry indicates crisis

        # Get user's wellness preferences
        if hasattr(instance.user, 'wellness_progress'):
            progress = instance.user.wellness_progress

            if progress.contextual_delivery_enabled:
                # Queue immediate crisis support content
                logger.info(f"Checking for crisis wellness content delivery for user {instance.user.id}")

                # TODO: Implement crisis wellness content delivery
                # from .services.crisis_content import deliver_crisis_support_content
                # deliver_crisis_support_content(instance.user, instance)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to trigger crisis wellness content: {e}")


# Streak maintenance and engagement
def maintain_user_streaks():
    """Daily task to maintain user engagement streaks"""
    try:
        # This would be called by a daily cron job or celery task
        from django.utils import timezone

        # Reset streaks for users who haven't been active
        inactive_users = WellnessUserProgress.objects.filter(
            last_activity_date__lt=timezone.now() - timezone.timedelta(days=2),
            current_streak__gt=0
        )

        for progress in inactive_users:
            old_streak = progress.current_streak
            progress.current_streak = 0
            progress.save()

            logger.info(f"Reset streak for {progress.user.peoplename} (was {old_streak} days)")

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Failed to maintain user streaks: {e}")