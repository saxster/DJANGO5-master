"""
Content Delivery Tasks for Journal & Wellness System

Handles personalized wellness content delivery and scheduling including:
- Daily wellness content scheduling
- Pattern-triggered content delivery
- Milestone notifications
- User preference-based delivery

All tasks use existing PostgreSQL Task Queue infrastructure.
"""

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db import DatabaseError, IntegrityError, ConnectionError
from django.contrib.auth import get_user_model
from django.db.models import Avg
from datetime import timedelta
import logging

from apps.journal.models import JournalEntry
from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from apps.wellness.services.content_delivery import WelnessTipSelector
from apps.core.exceptions import IntegrationException

User = get_user_model()
logger = logging.getLogger('background_tasks')


@shared_task(
    bind=True,
    max_retries=2,
    autoretry_for=(ConnectionError, DatabaseError, IntegrityError),
    retry_backoff=True,
    retry_backoff_max=300,
    soft_time_limit=180,  # 3 minutes - content scheduling
    time_limit=360         # 6 minutes hard limit
)
def schedule_wellness_content_delivery(self, user_id, trigger_reason='daily_schedule'):
    """
    Schedule personalized wellness content delivery

    Args:
        user_id: User to schedule content for
        trigger_reason: Reason for scheduling ('daily_schedule', 'low_wellbeing_score', 'crisis_detected')

    Returns:
        dict: Scheduling results
    """

    logger.info(f"Scheduling wellness content for user {user_id} (reason: {trigger_reason})")

    try:
        user = User.objects.get(id=user_id)

        # Get or create user progress
        progress, created = WellnessUserProgress.objects.get_or_create(
            user=user,
            defaults={'tenant': user.tenant}
        )

        # Check if user has enabled contextual delivery
        if not progress.contextual_delivery_enabled and trigger_reason != 'crisis_detected':
            logger.debug(f"Contextual delivery disabled for user {user_id}")
            return {
                'success': True,
                'skipped': True,
                'reason': 'contextual_delivery_disabled'
            }

        # Check daily tip delivery timing
        if trigger_reason == 'daily_schedule':
            # Check if user already received daily tip today
            today_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                delivery_context='daily_tip',
                interaction_date__date=timezone.now().date()
            )

            if today_interactions.exists():
                logger.debug(f"Daily tip already delivered to user {user_id} today")
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'daily_tip_already_delivered'
                }

        # Analyze user patterns for personalization
        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=7),
            is_deleted=False
        ).order_by('-timestamp')

        user_patterns = {}
        if recent_entries.exists():
            # Calculate recent patterns
            mood_entries = recent_entries.exclude(mood_rating__isnull=True)
            stress_entries = recent_entries.exclude(stress_level__isnull=True)
            energy_entries = recent_entries.exclude(energy_level__isnull=True)

            if mood_entries.exists():
                user_patterns['current_mood'] = mood_entries.first().mood_rating
                user_patterns['avg_mood'] = mood_entries.aggregate(avg=Avg('mood_rating'))['avg']

            if stress_entries.exists():
                user_patterns['current_stress'] = stress_entries.first().stress_level
                user_patterns['avg_stress'] = stress_entries.aggregate(avg=Avg('stress_level'))['avg']

            if energy_entries.exists():
                user_patterns['current_energy'] = energy_entries.first().energy_level

        # Select appropriate content
        tip_selector = WelnessTipSelector()
        selected_content = tip_selector.select_personalized_tip(
            user, user_patterns, []  # No previously seen content for scheduled delivery
        )

        if selected_content:
            # Create interaction record for scheduled delivery
            interaction = WellnessContentInteraction.objects.create(
                user=user,
                content=selected_content,
                interaction_type='viewed',
                delivery_context='daily_tip' if trigger_reason == 'daily_schedule' else 'pattern_triggered',
                user_mood_at_delivery=user_patterns.get('current_mood'),
                user_stress_at_delivery=user_patterns.get('current_stress'),
                metadata={
                    'scheduled_delivery': True,
                    'trigger_reason': trigger_reason,
                    'selection_reason': tip_selector.last_selection_reason,
                    'predicted_effectiveness': tip_selector.predicted_effectiveness
                }
            )

            logger.info(f"Scheduled wellness content '{selected_content.title}' for user {user_id}")

            # TODO: Send push notification or MQTT message for content delivery
            # notify_user_wellness_content.delay(user_id, selected_content.id, interaction.id)

            return {
                'success': True,
                'user_id': user_id,
                'content_scheduled': {
                    'content_id': str(selected_content.id),
                    'content_title': selected_content.title,
                    'delivery_context': interaction.delivery_context,
                    'predicted_effectiveness': tip_selector.predicted_effectiveness
                },
                'interaction_id': str(interaction.id),
                'scheduled_at': timezone.now().isoformat()
            }

        else:
            logger.warning(f"No suitable wellness content found for user {user_id}")
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_suitable_content',
                'user_patterns': user_patterns
            }

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for wellness content scheduling")
        return {
            'success': False,
            'error': 'user_not_found',
            'user_id': user_id
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Wellness content scheduling failed for user {user_id}: {e}")
        # Let autoretry handle these exceptions
        raise
    except (ValueError, TypeError) as e:
        logger.error(f"Wellness content scheduling failed for user {user_id} (non-retryable): {e}")
        return {
            'success': False,
            'error': 'validation_error',
            'user_id': user_id,
            'details': str(e)
        }


@shared_task(
    bind=True,
    soft_time_limit=120,  # 2 minutes - milestone check
    time_limit=240         # 4 minutes hard limit
)
def check_wellness_milestones(self, user_id):
    """
    Check and award wellness milestones and achievements

    Args:
        user_id: User to check milestones for

    Returns:
        dict: Milestone check results
    """

    logger.debug(f"Checking wellness milestones for user {user_id}")

    try:
        user = User.objects.get(id=user_id)

        # Get user's wellness progress
        try:
            progress = user.wellness_progress
        except WellnessUserProgress.DoesNotExist:
            logger.info(f"No wellness progress found for user {user_id}")
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_wellness_progress'
            }

        # Check for new achievements
        old_achievements = set(progress.achievements_earned)
        new_achievements = progress.check_and_award_achievements()

        if new_achievements:
            # Update progress with new achievements
            progress.save()

            logger.info(f"New achievements for user {user_id}: {new_achievements}")

            # Send achievement notifications if enabled
            if progress.milestone_alerts_enabled:
                from background_tasks.journal_wellness_tasks import send_milestone_notification
                send_milestone_notification.delay(user_id, new_achievements)

            # Schedule celebratory wellness content
            from background_tasks.journal_wellness_tasks import schedule_wellness_content_delivery
            schedule_wellness_content_delivery.delay(user_id, 'milestone_achievement')

            return {
                'success': True,
                'user_id': user_id,
                'new_achievements': new_achievements,
                'total_achievements': len(progress.achievements_earned),
                'notification_sent': progress.milestone_alerts_enabled
            }

        else:
            return {
                'success': True,
                'user_id': user_id,
                'new_achievements': [],
                'message': 'No new achievements'
            }

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for milestone check")
        return {
            'success': False,
            'error': 'user_not_found'
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Milestone check failed for user {user_id}: {e}")
        raise


@shared_task(
    bind=True,
    soft_time_limit=60,  # 1 minute - content delivery
    time_limit=120        # 2 minutes hard limit
)
def schedule_specific_content_delivery(self, user_id, content_id, delivery_context):
    """Deliver specific wellness content to user"""

    try:
        user = User.objects.get(id=user_id)
        content = WellnessContent.objects.get(id=content_id)

        # Create interaction for scheduled delivery
        interaction = WellnessContentInteraction.objects.create(
            user=user,
            content=content,
            interaction_type='viewed',
            delivery_context=delivery_context,
            metadata={
                'scheduled_delivery': True,
                'delivery_timestamp': timezone.now().isoformat()
            }
        )

        logger.info(f"Delivered scheduled content '{content.title}' to user {user_id}")

        return {
            'success': True,
            'content_delivered': content.title,
            'interaction_id': str(interaction.id)
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Scheduled content delivery failed: {e}")
        raise


@shared_task(
    bind=True,
    soft_time_limit=60,  # 1 minute - notification
    time_limit=120        # 2 minutes hard limit
)
def send_milestone_notification(self, user_id, achievements):
    """Send notification for wellness milestones"""

    logger.info(f"Sending milestone notification to user {user_id}: {achievements}")

    try:
        user = User.objects.get(id=user_id)

        # TODO: Integrate with MQTT notification system
        # notification_data = {
        #     'type': 'wellness_milestone',
        #     'user_id': user_id,
        #     'achievements': achievements,
        #     'message': f'Congratulations! You earned: {", ".join(achievements)}'
        # }
        # send_mqtt_notification.delay(user_id, notification_data)

        # For now, log the notification
        logger.info(f"MILESTONE NOTIFICATION: User {user.peoplename} earned {achievements}")

        return {
            'success': True,
            'user_id': user_id,
            'achievements': achievements,
            'notification_sent': True
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Milestone notification failed: {e}")
        raise
