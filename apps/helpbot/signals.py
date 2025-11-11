"""
HelpBot Django Signals

Handles automatic knowledge indexing, analytics recording, and other automated tasks
when HelpBot models are created or updated.
"""

import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.helpbot.models import (
    HelpBotSession, HelpBotMessage, HelpBotFeedback, HelpBotKnowledge
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=HelpBotSession)
def handle_session_save(sender, instance, created, **kwargs):
    """Handle session creation and updates."""
    try:
        if created:
            logger.debug(f"New HelpBot session created: {instance.session_id}")

        # Record analytics when session is completed
        if (instance.current_state == HelpBotSession.StateChoices.COMPLETED and
            hasattr(instance, '_state_changed')):

            from apps.helpbot.services import HelpBotAnalyticsService
            analytics_service = HelpBotAnalyticsService()
            analytics_service.record_session_metrics(instance)
            logger.debug(f"Recorded analytics for completed session: {instance.session_id}")

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error in session save signal: {e}", exc_info=True)


@receiver(pre_save, sender=HelpBotSession)
def handle_session_pre_save(sender, instance, **kwargs):
    """Track state changes before saving."""
    try:
        if instance.pk:
            # Get old instance to compare states
            try:
                old_instance = HelpBotSession.objects.get(pk=instance.pk)
                if old_instance.current_state != instance.current_state:
                    instance._state_changed = True
                    logger.debug(
                        f"Session {instance.session_id} state changed: "
                        f"{old_instance.current_state} -> {instance.current_state}"
                    )
            except HelpBotSession.DoesNotExist:
                pass

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error in session pre_save signal: {e}", exc_info=True)


@receiver(post_save, sender=HelpBotMessage)
def handle_message_save(sender, instance, created, **kwargs):
    """Handle message creation."""
    try:
        if created:
            logger.debug(f"New message created: {instance.message_id}")

            # Update session message count
            instance.session.total_messages = instance.session.messages.count()
            instance.session.save(update_fields=['total_messages'])

            # Record response time analytics for bot messages
            if (instance.message_type == HelpBotMessage.MessageTypeChoices.BOT_RESPONSE and
                instance.processing_time_ms):

                from apps.helpbot.services import HelpBotAnalyticsService
                analytics_service = HelpBotAnalyticsService()
                analytics_service.record_response_time(instance)

            # Record knowledge usage
            if instance.knowledge_sources:
                from apps.helpbot.services import HelpBotAnalyticsService
                analytics_service = HelpBotAnalyticsService()
                for source in instance.knowledge_sources:
                    if 'id' in source:
                        analytics_service.record_knowledge_usage(
                            source['id'],
                            {
                                'session_type': instance.session.session_type,
                                'message_type': instance.message_type
                            }
                        )

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error in message save signal: {e}", exc_info=True)


@receiver(post_save, sender=HelpBotFeedback)
def handle_feedback_save(sender, instance, created, **kwargs):
    """Handle feedback submission."""
    try:
        if created:
            logger.debug(f"New feedback created: {instance.feedback_id}")

            # Update knowledge effectiveness if feedback is for a specific message
            if instance.message and instance.rating and instance.message.knowledge_sources:
                from apps.helpbot.services import HelpBotKnowledgeService
                knowledge_service = HelpBotKnowledgeService()

                # Convert 1-5 rating to 0-1 effectiveness score
                effectiveness_score = (instance.rating - 1) / 4.0

                for source in instance.message.knowledge_sources:
                    if 'id' in source:
                        knowledge_service.update_knowledge_effectiveness(
                            source['id'], effectiveness_score
                        )
                        logger.debug(
                            f"Updated knowledge effectiveness for {source['id']}: {effectiveness_score}"
                        )

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error in feedback save signal: {e}", exc_info=True)


@receiver(post_save, sender=HelpBotKnowledge)
def handle_knowledge_save(sender, instance, created, **kwargs):
    """Handle knowledge base updates."""
    try:
        if created:
            logger.debug(f"New knowledge article created: {instance.knowledge_id}")

            # Trigger async txtai index update (Nov 2025 implementation)
            try:
                from apps.helpbot.tasks import update_txtai_index_task

                # Queue background task with 5-second delay for batching
                update_txtai_index_task.apply_async(
                    args=[str(instance.knowledge_id), 'add'],
                    countdown=5  # 5-second delay allows aggregation
                )

                logger.debug(
                    f"Queued txtai index update for knowledge: {instance.knowledge_id}"
                )

            except ImportError as e:
                logger.debug(f"txtai task not available: {e}")

        else:
            # Existing knowledge updated - trigger index refresh
            logger.debug(f"Knowledge article updated: {instance.knowledge_id}")

            try:
                from apps.helpbot.tasks import update_txtai_index_task

                update_txtai_index_task.apply_async(
                    args=[str(instance.knowledge_id), 'update'],
                    countdown=5
                )

            except ImportError as e:
                logger.debug(f"txtai task not available: {e}")

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error in knowledge save signal: {e}", exc_info=True)


@receiver(post_delete, sender=HelpBotKnowledge)
def handle_knowledge_delete(sender, instance, **kwargs):
    """Handle knowledge deletion."""
    try:
        logger.debug(f"Knowledge article deleted: {instance.knowledge_id}")

        # Trigger async txtai index cleanup (Nov 2025 implementation)
        try:
            from apps.helpbot.tasks import update_txtai_index_task

            # Queue background task to remove from index
            update_txtai_index_task.apply_async(
                args=[str(instance.knowledge_id), 'delete'],
                countdown=5  # 5-second delay for batching
            )

            logger.debug(
                f"Queued txtai index removal for knowledge: {instance.knowledge_id}"
            )

        except ImportError as e:
            logger.debug(f"txtai task not available: {e}")

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error in knowledge delete signal: {e}", exc_info=True)


# Optional: Handle other model signals for comprehensive tracking
@receiver(post_save, sender='peoples.People')
def handle_user_activity(sender, instance, created, **kwargs):
    """Track user activity for context awareness."""
    try:
        if not created:  # Only track updates, not creation
            # Update user context if they have active HelpBot sessions
            active_sessions = HelpBotSession.objects.filter(
                user=instance,
                current_state__in=[
                    HelpBotSession.StateChoices.ACTIVE,
                    HelpBotSession.StateChoices.WAITING
                ]
            )

            if active_sessions.exists():
                logger.debug(f"User {instance.email} has active HelpBot sessions during profile update")
                # Could trigger context refresh here

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error in user activity signal: {e}", exc_info=True)


# Error handling for signal failures
def handle_signal_error(sender, **kwargs):
    """Generic error handler for signal failures."""
    exception = kwargs.get('exception')
    logger.error(f"Signal error in {sender}: {exception}", exc_info=True)


# Optional: Connect to Django's got_request_exception for error tracking
from django.core.signals import got_request_exception
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS


@receiver(got_request_exception)
def handle_request_exception(sender, request, **kwargs):
    """Handle request exceptions for HelpBot error context."""
    try:
        # Only handle if this is a HelpBot-related request
        if hasattr(request, 'path') and '/helpbot/' in request.path:
            logger.debug("HelpBot request exception occurred")

            # Store error context in session for potential HelpBot assistance
            if hasattr(request, 'session') and hasattr(request, 'user') and request.user.is_authenticated:
                request.session['helpbot_last_error'] = {
                    'path': request.path,
                    'method': request.method,
                    'timestamp': timezone.now().isoformat(),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                }

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error handling request exception signal: {e}", exc_info=True)