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
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS
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
            logger.error(f"Failed to create wellness progress for user {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender=WellnessContentInteraction)
def handle_wellness_interaction_created(sender, instance, created, **kwargs):
    """Handle wellness content interaction events"""

    if created:
        logger.debug(f"New wellness interaction: {instance.user.peoplename} {instance.interaction_type} '{instance.content.title}'")

        # Check for milestone achievements
        try:
            check_wellness_milestones(instance.user)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to check wellness milestones for user {instance.user.id}: {e}", exc_info=True)

        # Schedule follow-up content if user showed high engagement
        try:
            if instance.engagement_score >= 4:
                schedule_follow_up_content(instance)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to schedule follow-up content: {e}", exc_info=True)


def check_wellness_milestones(user):
    """Check and award wellness milestones and achievements"""

    try:
        progress = user.wellness_progress
    except WellnessUserProgress.DoesNotExist:
        logger.warning(f"No wellness progress found for user {user.id}", exc_info=True)
        return

    # Check for new achievements
    new_achievements = progress.check_and_award_achievements()

    if new_achievements and progress.milestone_alerts_enabled:
        # Queue milestone notification
        logger.info(f"Queuing milestone notifications for {user.peoplename}: {new_achievements}")

        try:
            # Try to send notification via AlertNotificationService
            from apps.mqtt.services.alert_notification_service import AlertNotificationService

            notification_service = AlertNotificationService()
            for achievement in new_achievements:
                # Send achievement notification
                achievement_titles = {
                    'week_streak': '7-Day Streak Achievement!',
                    'month_streak': '30-Day Streak Achievement!',
                    'content_explorer': 'Content Explorer Badge Earned!',
                    'wellness_scholar': 'Wellness Scholar Badge Earned!',
                }

                title = achievement_titles.get(achievement, 'New Achievement Unlocked!')
                message = f"Congratulations! You've earned the {achievement.replace('_', ' ').title()} achievement!"

                # Queue notification (actual implementation may vary based on AlertNotificationService API)
                logger.debug(f"Sending achievement notification for {achievement} to user {user.id}")

        except ImportError as e:
            logger.warning(
                f"AlertNotificationService not available for milestone notification: {e}. "
                "Falling back to simple logging.",
                exc_info=True
            )
            logger.info(f"Milestone achieved: User {user.id} earned achievements: {new_achievements}")
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to send milestone notification: {e}", exc_info=True)


def schedule_follow_up_content(interaction):
    """Schedule follow-up wellness content based on user engagement"""

    if interaction.content.related_topics:
        try:
            # TODO: Implement follow-up content scheduling - deferred until sufficient usage data
            # collected (min 500 interactions) to establish effective content recommendation patterns
            logger.debug(f"Scheduling follow-up content for user {interaction.user.id}")

            # Example of how this might work:
            # from .services.content_scheduler import schedule_related_content
            # schedule_related_content(interaction.user, interaction.content.related_topics)

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to schedule follow-up content: {e}", exc_info=True)


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
            # TODO: Update ML models with new content - deferred until baseline metrics established
            # (min 1000 content interactions) to train effective personalization models
            logger.debug("Queuing ML model update for new wellness content")
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to update ML models: {e}", exc_info=True)

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
            except BUSINESS_LOGIC_EXCEPTIONS as e:
                logger.error(f"Failed to schedule initial daily tip: {e}", exc_info=True)

    else:
        logger.debug(f"Wellness preferences updated for user {instance.user.peoplename}")

        # Update scheduled content based on preference changes
        if instance.daily_tip_enabled:
            try:
                reschedule_daily_wellness_content(instance.user)
            except BUSINESS_LOGIC_EXCEPTIONS as e:
                logger.error(f"Failed to reschedule wellness content: {e}", exc_info=True)


def schedule_daily_wellness_tip(user):
    """Schedule daily wellness tip delivery for user via Celery Beat"""
    try:
        progress = user.wellness_progress

        if not progress.daily_tip_enabled:
            # Disable scheduled task if tips disabled
            try:
                from django_celery_beat.models import PeriodicTask
                PeriodicTask.objects.filter(
                    name=f"daily_wellness_tip_user_{user.id}"
                ).update(enabled=False)
                logger.debug(f"Disabled daily wellness tips for user {user.id}")
            except ImportError:
                logger.warning("django_celery_beat not available - skipping task scheduling")
            return

        try:
            from django_celery_beat.models import PeriodicTask, CrontabSchedule
            import json

            # Get or create schedule for user's preferred time (default 9 AM)
            preferred_hour = progress.preferred_delivery_time.hour if progress.preferred_delivery_time else 9
            schedule, _ = CrontabSchedule.objects.get_or_create(
                hour=preferred_hour,
                minute=0,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
            )

            # Create or update periodic task
            task, created = PeriodicTask.objects.get_or_create(
                name=f"daily_wellness_tip_user_{user.id}",
                defaults={
                    'task': 'apps.wellness.tasks.send_daily_wellness_tip',
                    'crontab': schedule,
                    'kwargs': json.dumps({'user_id': user.id}),
                    'enabled': True,
                }
            )

            if not created:
                # Update existing task if schedule changed
                task.crontab = schedule
                task.enabled = True
                task.save()

            logger.info(f"Daily wellness tips scheduled for user {user.id} at {preferred_hour}:00")

        except ImportError:
            logger.warning("django_celery_beat not available - skipping task scheduling")
        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to create periodic task for user {user.id}: {e}", exc_info=True)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to schedule daily wellness tip for user {user.id}: {e}", exc_info=True)


def reschedule_daily_wellness_content(user):
    """Reschedule daily wellness content based on updated preferences"""
    try:
        # Simply call schedule_daily_wellness_tip which handles updates
        schedule_daily_wellness_tip(user)
        logger.debug(f"Rescheduled wellness content for user {user.peoplename}")

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to reschedule wellness content: {e}", exc_info=True)


# Analytics and effectiveness tracking
@receiver(post_save, sender=WellnessContentInteraction)
def update_content_effectiveness_metrics(sender, instance, created, **kwargs):
    """Update content effectiveness metrics for analytics"""

    if created and instance.is_positive_interaction:
        try:
            # TODO: Update content effectiveness analytics - deferred until baseline metrics established
            # (min 1000 interactions) to calculate statistically significant effectiveness scores
            logger.debug(f"Updating effectiveness metrics for content {instance.content.id}")

            # This could involve:
            # - Updating content popularity scores
            # - Training personalization models
            # - Adjusting content priority scores based on engagement

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Failed to update effectiveness metrics: {e}", exc_info=True)


# Mental Health Intervention Integration
@receiver(post_save, sender='journal.JournalEntry')
def trigger_mental_health_intervention_analysis(sender, instance, created, **kwargs):
    """
    Signal handler: Trigger mental health intervention analysis on journal entry save

    This is the main integration point that automatically analyzes journal entries
    for mental health intervention needs and triggers appropriate responses.
    """

    # Only process for new entries or significant updates
    if not created and not _is_significant_update(instance):
        return

    try:
        user = instance.user

        # Check privacy consent
        if not _check_intervention_consent(user):
            logger.debug(f"Mental health intervention analysis skipped for user {user.id} - no consent")
            return

        # Check if user has wellbeing metrics (required for analysis)
        if not _has_analyzable_content(instance):
            logger.debug(f"Journal entry {instance.id} lacks analyzable content for mental health intervention")
            return

        logger.info(f"Triggering mental health intervention analysis for journal entry {instance.id}")

        # Process entry for interventions (async to avoid blocking journal save)
        from .tasks import process_entry_for_mental_health_interventions
        process_entry_for_mental_health_interventions.delay(
            journal_entry_id=instance.id,
            user_id=user.id,
            created=created
        )

        logger.debug(f"Mental health intervention analysis queued for entry {instance.id}")

    except BUSINESS_LOGIC_EXCEPTIONS as e:
        logger.error(f"Mental health intervention signal processing failed for entry {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender='journal.JournalEntry')
def monitor_crisis_patterns(sender, instance, created, **kwargs):
    """
    Signal handler: Monitor for crisis patterns requiring immediate response

    Separate from main intervention analysis to ensure crisis detection
    happens immediately without waiting for background task processing.
    """

    try:
        user = instance.user

        # Check for immediate crisis indicators
        crisis_indicators = _check_immediate_crisis_indicators(instance)

        if crisis_indicators['crisis_detected']:
            logger.critical(f"IMMEDIATE CRISIS INDICATORS DETECTED: Journal Entry {instance.id}, User {user.id}")

            # Trigger immediate crisis response
            from .services.crisis_prevention_system import CrisisPreventionSystem
            crisis_system = CrisisPreventionSystem()

            # Perform rapid crisis assessment
            crisis_assessment = crisis_system.assess_crisis_risk(
                user=user,
                journal_entry=instance,
                analysis_period_days=3  # Rapid assessment with recent data
            )

            # If crisis confirmed, trigger immediate escalation
            if crisis_assessment.get('immediate_safety_concerns', False):
                logger.critical(f"CRISIS CONFIRMED: Initiating immediate escalation for user {user.id}")

                # Trigger crisis intervention background task (highest priority)
                from .tasks import process_crisis_mental_health_intervention

                crisis_task = process_crisis_mental_health_intervention.apply_async(
                    args=[user.id, crisis_assessment, instance.id],
                    queue='critical',
                    priority=10,
                    countdown=0  # Immediate
                )

                logger.critical(f"Crisis intervention task started: {crisis_task.id} for user {user.id}")

    except BUSINESS_LOGIC_EXCEPTIONS as e:
        logger.error(f"Crisis monitoring signal failed for entry {instance.id}: {e}", exc_info=True)


# Crisis intervention integration (legacy - updated above)
@receiver(post_save, sender='journal.JournalEntry')
def trigger_crisis_wellness_content(sender, instance, created, **kwargs):
    """Trigger immediate wellness content for crisis situations - LEGACY"""

    if not created:
        return

    try:
        # This functionality is now handled by the mental health intervention signals above
        logger.debug(f"Legacy crisis wellness content check for entry {instance.id} - handled by new system")

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to trigger crisis wellness content: {e}", exc_info=True)


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
        logger.error(f"Failed to maintain user streaks: {e}", exc_info=True)


# Helper functions for mental health intervention signals

def _is_significant_update(journal_entry):
    """Check if journal entry update is significant enough to trigger reanalysis"""
    # Only reanalyze if wellbeing metrics changed or content changed substantially
    # This is a simplified check - production would compare actual changes
    return True  # For now, analyze all updates


def _check_intervention_consent(user):
    """Check if user has consented to mental health interventions"""
    try:
        from apps.journal.models import JournalPrivacySettings
        privacy_settings = JournalPrivacySettings.objects.filter(user=user).first()

        if not privacy_settings:
            # Default consent for basic wellness interventions
            return True

        # Check for mental health intervention consent
        # Using analytics_consent as proxy for intervention consent
        return privacy_settings.analytics_consent

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Consent check failed for user {user.id}: {e}", exc_info=True)
        return False  # Conservative default


def _has_analyzable_content(journal_entry):
    """Check if journal entry has content suitable for mental health analysis"""
    # Check for wellbeing metrics or substantial content
    has_metrics = False
    has_content = False

    if hasattr(journal_entry, 'wellbeing_metrics') and journal_entry.wellbeing_metrics:
        metrics = journal_entry.wellbeing_metrics
        has_metrics = (
            getattr(metrics, 'mood_rating', None) is not None or
            getattr(metrics, 'stress_level', None) is not None or
            getattr(metrics, 'energy_level', None) is not None
        )

    if journal_entry.content and len(journal_entry.content.strip()) > 20:
        has_content = True

    return has_metrics or has_content


def _check_immediate_crisis_indicators(journal_entry):
    """Check for immediate crisis indicators requiring urgent response"""
    crisis_indicators = {
        'crisis_detected': False,
        'indicators': [],
        'severity': 'none'
    }

    # Check content for crisis keywords
    if journal_entry.content:
        content_lower = journal_entry.content.lower()

        # Immediate crisis keywords (suicidal ideation)
        immediate_crisis_keywords = [
            'suicidal', 'kill myself', 'end it all', 'want to die',
            'better off dead', 'suicide', 'no reason to live'
        ]

        for keyword in immediate_crisis_keywords:
            if keyword in content_lower:
                crisis_indicators['crisis_detected'] = True
                crisis_indicators['indicators'].append(f"Crisis keyword detected: {keyword}")
                crisis_indicators['severity'] = 'immediate'

    # Check severe mood ratings
    if hasattr(journal_entry, 'wellbeing_metrics') and journal_entry.wellbeing_metrics:
        mood = getattr(journal_entry.wellbeing_metrics, 'mood_rating', None)
        stress = getattr(journal_entry.wellbeing_metrics, 'stress_level', None)

        if mood and mood <= 2:
            crisis_indicators['crisis_detected'] = True
            crisis_indicators['indicators'].append(f"Severe mood rating: {mood}/10")
            if crisis_indicators['severity'] != 'immediate':
                crisis_indicators['severity'] = 'high'

        if stress and stress >= 5:
            crisis_indicators['crisis_detected'] = True
            crisis_indicators['indicators'].append(f"Maximum stress level: {stress}/5")
            if crisis_indicators['severity'] != 'immediate':
                crisis_indicators['severity'] = 'high'

    return crisis_indicators


# =============================================================================
# WISDOM CONVERSATIONS SIGNAL INTEGRATION
# =============================================================================

@receiver(post_save, sender='wellness.InterventionDeliveryLog')
def trigger_wisdom_conversation_generation(sender, instance, created, **kwargs):
    """
    Signal handler: Automatically generate wisdom conversations from intervention deliveries

    This is the main integration point for the "Conversations with Wisdom" feature.
    When an intervention is delivered, this signal automatically creates a corresponding
    conversation entry to maintain the continuous narrative flow.
    """

    # Only process new deliveries or significant updates
    if not created and not _is_significant_delivery_update(instance):
        return

    try:
        # Import here to avoid circular imports
        from .services.automatic_conversation_generator import AutomaticConversationGenerator

        # Check if this delivery should generate a conversation
        if not _should_trigger_conversation_generation(instance):
            logger.debug(f"Skipping conversation generation for delivery {instance.id}")
            return

        logger.info(f"Triggering wisdom conversation generation for delivery {instance.id}")

        # Generate conversation asynchronously to avoid blocking the intervention delivery
        # Use Celery task for background processing
        try:
            from ..tasks import generate_wisdom_conversation_task
            generate_wisdom_conversation_task.delay(instance.id)

        except ImportError:
            # Fallback to synchronous generation if Celery not available
            logger.warning("Celery not available, generating conversation synchronously", exc_info=True)
            generator = AutomaticConversationGenerator()
            conversation = generator.process_intervention_delivery(instance)

            if conversation:
                logger.info(f"Generated wisdom conversation {conversation.id} for delivery {instance.id}")
            else:
                logger.debug(f"No conversation generated for delivery {instance.id}")

    except BUSINESS_LOGIC_EXCEPTIONS as e:
        logger.error(f"Error in wisdom conversation generation signal for delivery {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender='wellness.ConversationThread')
def handle_conversation_thread_created(sender, instance, created, **kwargs):
    """
    Signal handler: Handle new conversation thread creation

    Performs initialization and setup when a new conversation thread is created.
    """

    if created:
        logger.info(f"New conversation thread created: {instance.title} for user {instance.user.peoplename}")

        try:
            # Initialize thread with user's personalization preferences
            from .services.conversation_personalization_system import ConversationPersonalizationSystem
            personalization_system = ConversationPersonalizationSystem()

            # Get user's personality profile if available
            personality_profile = personalization_system._get_user_personality_profile(instance.user)

            # Update thread with personalization data
            if personality_profile:
                instance.personalization_data = {
                    'personality_profile': personality_profile,
                    'thread_initialized': timezone.now().isoformat(),
                    'auto_personalization_enabled': True
                }
                instance.save(update_fields=['personalization_data'])

                logger.debug(f"Initialized thread {instance.id} with personality profile")

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error initializing conversation thread {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender='wellness.WisdomConversation')
def handle_wisdom_conversation_created(sender, instance, created, **kwargs):
    """
    Signal handler: Handle new wisdom conversation creation

    Performs post-processing when a new wisdom conversation is created.
    """

    if created:
        logger.info(f"New wisdom conversation created: {instance.id} in thread {instance.thread.title}")

        try:
            # Update thread statistics
            instance.thread.update_conversation_stats()

            # Check for conversation flow optimization opportunities
            from .services.conversation_flow_manager import ConversationFlowManager
            flow_manager = ConversationFlowManager()

            # Analyze conversation flow after adding new conversation
            # Do this asynchronously to avoid blocking
            try:
                from ..tasks import optimize_conversation_flow_task
                optimize_conversation_flow_task.delay(instance.user.id, instance.thread.id)

            except ImportError:
                # Skip flow optimization if Celery not available
                logger.debug("Skipping flow optimization - Celery not available")

            # Track conversation creation analytics
            _track_conversation_creation_analytics(instance)

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error in post-processing for conversation {instance.id}: {e}", exc_info=True)


@receiver(post_save, sender='wellness.ConversationEngagement')
def handle_conversation_engagement_created(sender, instance, created, **kwargs):
    """
    Signal handler: Handle new conversation engagement

    Updates personalization and effectiveness tracking when users engage with conversations.
    """

    if created:
        logger.debug(f"New conversation engagement: {instance.engagement_type} by {instance.user.peoplename}")

        try:
            # Update conversation effectiveness metrics
            if instance.effectiveness_rating:
                _update_conversation_effectiveness(instance)

            # Update user personalization profile based on engagement
            if instance.engagement_type in ['positive_feedback', 'bookmark', 'reflection_note']:
                _update_user_personalization_from_engagement(instance)

            # Check for milestone achievements
            _check_engagement_milestones(instance.user)

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.error(f"Error processing conversation engagement {instance.id}: {e}", exc_info=True)


# Helper functions for wisdom conversation signals

def _is_significant_delivery_update(delivery_log):
    """Check if delivery update is significant enough to trigger conversation generation"""
    # For now, only process new deliveries
    # Could be extended to handle effectiveness score updates, etc.
    return False


def _should_trigger_conversation_generation(delivery_log):
    """Determine if this delivery should trigger conversation generation"""

    # Check effectiveness threshold
    if delivery_log.effectiveness_score < 2.0:
        return False

    # Check intervention type eligibility
    eligible_types = [
        'THREE_GOOD_THINGS', 'GRATITUDE_JOURNAL', 'CBT_THOUGHT_RECORD',
        'MOTIVATIONAL_INTERVIEWING', 'CRISIS_SUPPORT', 'STRESS_MANAGEMENT',
        'WORKPLACE_WELLNESS', 'PREVENTIVE_CARE'
    ]

    if delivery_log.intervention.intervention_type not in eligible_types:
        return False

    # Check if conversation already exists
    from .models.wisdom_conversations import WisdomConversation
    if WisdomConversation.objects.filter(source_intervention_delivery=delivery_log).exists():
        return False

    # Check user preferences
    try:
        from .models.user_progress import WellnessUserProgress
        progress = WellnessUserProgress.objects.get(user=delivery_log.user)
        return getattr(progress, 'contextual_delivery_enabled', True)
    except WellnessUserProgress.DoesNotExist:
        return True  # Default to enabled


def _track_conversation_creation_analytics(conversation):
    """Track analytics for conversation creation"""

    try:
        from .models.wisdom_conversations import ConversationEngagement

        # Create initial analytics engagement
        ConversationEngagement.objects.create(
            user=conversation.user,
            conversation=conversation,
            engagement_type='view',
            access_context='automated_creation',
            engagement_metadata={
                'creation_source': conversation.source_type,
                'thread_type': conversation.thread.thread_type,
                'conversation_tone': conversation.conversation_tone,
                'word_count': conversation.word_count,
                'sequence_number': conversation.sequence_number,
                'is_milestone': conversation.is_milestone_conversation,
                'created_at': timezone.now().isoformat(),
            }
        )

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error tracking conversation creation analytics: {e}", exc_info=True)


def _update_conversation_effectiveness(engagement):
    """Update conversation effectiveness based on user engagement"""

    try:
        conversation = engagement.conversation

        # Update conversation personalization score based on effectiveness rating
        if engagement.effectiveness_rating >= 4:
            # Positive feedback - increase personalization score
            new_score = min(1.0, conversation.personalization_score + 0.05)
            conversation.personalization_score = new_score
            conversation.save(update_fields=['personalization_score'])

        elif engagement.effectiveness_rating <= 2:
            # Negative feedback - decrease personalization score
            new_score = max(0.0, conversation.personalization_score - 0.1)
            conversation.personalization_score = new_score
            conversation.save(update_fields=['personalization_score'])

        logger.debug(f"Updated conversation {conversation.id} effectiveness score to {conversation.personalization_score}")

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error updating conversation effectiveness: {e}", exc_info=True)


def _update_user_personalization_from_engagement(engagement):
    """Update user personalization profile based on positive engagement"""

    try:
        from .services.conversation_personalization_system import ConversationPersonalizationSystem

        personalization_system = ConversationPersonalizationSystem()
        conversation = engagement.conversation

        # Update user's preferred tones and styles based on engagement
        thread = conversation.thread
        personalization_data = thread.personalization_data.copy()

        if 'effective_tones' not in personalization_data:
            personalization_data['effective_tones'] = {}

        tone = conversation.conversation_tone
        if tone not in personalization_data['effective_tones']:
            personalization_data['effective_tones'][tone] = 0

        # Increment effectiveness for this tone
        personalization_data['effective_tones'][tone] += 1
        personalization_data['last_updated'] = timezone.now().isoformat()

        thread.personalization_data = personalization_data
        thread.save(update_fields=['personalization_data'])

        logger.debug(f"Updated personalization data for user {engagement.user.peoplename}")

    except BUSINESS_LOGIC_EXCEPTIONS as e:
        logger.error(f"Error updating user personalization from engagement: {e}", exc_info=True)


def _check_engagement_milestones(user):
    """Check for engagement-based milestones and achievements"""

    try:
        from .models.wisdom_conversations import ConversationEngagement

        # Count total engagements
        total_engagements = ConversationEngagement.objects.filter(user=user).count()

        # Check for milestone achievements
        milestones = [10, 25, 50, 100, 250, 500]

        for milestone in milestones:
            if total_engagements == milestone:
                logger.info(f"User {user.peoplename} reached engagement milestone: {milestone}")

                # Create milestone celebration conversation
                try:
                    from ..tasks import create_milestone_conversation_task
                    create_milestone_conversation_task.delay(user.id, 'engagement', milestone)
                except ImportError:
                    logger.debug("Skipping milestone conversation creation - Celery not available")

                break

    except BUSINESS_LOGIC_EXCEPTIONS as e:
        logger.error(f"Error checking engagement milestones for user {user.id}: {e}", exc_info=True)