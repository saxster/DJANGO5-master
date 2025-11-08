"""
Conversation Translation Signal Handlers

Automatic translation system for new wisdom conversations based on user
language preferences. Implements non-blocking background translation
with proper error handling and retry mechanisms.
"""

import logging
from typing import Optional
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from ..models.wisdom_conversations import WisdomConversation
from ..models.conversation_translation import WisdomConversationTranslation
from ..services.conversation_translation_service import ConversationTranslationService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=WisdomConversation)
def auto_translate_new_conversation(sender, instance: WisdomConversation, created, **kwargs):
    """
    Automatically queue translation for new wisdom conversations based on user preferences.

    This signal fires when a new WisdomConversation is created and:
    1. Checks if the conversation is in English (default language)
    2. Identifies all users in the same tenant with non-English preferred languages
    3. Queues background translation tasks for those languages
    4. Implements rate limiting to avoid overwhelming translation services
    """

    # Only process newly created conversations
    if not created:
        return

    # Skip if automatic translation is disabled
    if not getattr(settings, 'WELLNESS_AUTO_TRANSLATE_CONVERSATIONS', True):
        logger.debug(f"Auto-translation disabled, skipping conversation {instance.id}")
        return

    try:
        # Check rate limiting - avoid overwhelming translation services
        rate_limit_key = f"auto_translate_rate_limit:{instance.tenant.id}"
        current_count = cache.get(rate_limit_key, 0)
        max_translations_per_hour = getattr(settings, 'WELLNESS_MAX_AUTO_TRANSLATIONS_PER_HOUR', 50)

        if current_count >= max_translations_per_hour:
            logger.warning(f"Rate limit reached for tenant {instance.tenant.id}, skipping auto-translation", exc_info=True)
            return

        # Get all users in the tenant with non-English language preferences
        from django.contrib.auth import get_user_model
        User = get_user_model()

        users_needing_translation = User.objects.filter(
            tenant=instance.tenant,
            preferred_language__isnull=False
        ).exclude(
            preferred_language='en'
        ).values_list('preferred_language', flat=True).distinct()

        if not users_needing_translation:
            logger.debug(f"No users require translation for conversation {instance.id}")
            return

        # Queue translation tasks for each required language
        translation_service = ConversationTranslationService()
        queued_languages = []

        for target_language in users_needing_translation:
            # Check if translation already exists
            existing_translation = WisdomConversationTranslation.objects.filter(
                original_conversation=instance,
                target_language=target_language,
                status='completed'
            ).first()

            if existing_translation and not existing_translation.is_expired:
                logger.debug(f"Translation to {target_language} already exists for conversation {instance.id}")
                continue

            # Queue async translation task using Celery
            from ..tasks import translate_conversation_async
            translate_conversation_async.delay(
                conversation_id=instance.id,
                target_language=target_language,
                priority='auto',
                retry_count=0
            )

            queued_languages.append(target_language)

        # Update rate limiting counter
        cache.set(rate_limit_key, current_count + len(queued_languages), timeout=3600)

        if queued_languages:
            logger.info(
                f"Queued auto-translation for conversation {instance.id} "
                f"to languages: {', '.join(queued_languages)}"
            )

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Error in auto-translation signal for conversation {instance.id}: {e}", exc_info=True)


@receiver(post_delete, sender=WisdomConversation)
def cleanup_conversation_translations(sender, instance: WisdomConversation, **kwargs):
    """
    Clean up associated translations when a conversation is deleted.

    This signal ensures that all related translation records are properly
    removed to maintain data consistency and prevent orphaned records.
    """
    try:
        # Delete all associated translations
        deleted_count = WisdomConversationTranslation.objects.filter(
            original_conversation=instance
        ).delete()[0]

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} translations for deleted conversation {instance.id}")

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Error cleaning up translations for conversation {instance.id}: {e}", exc_info=True)


# Translation queuing is now handled by Celery tasks in apps.wellness.tasks.translate_conversation_async


# User preference change signal
@receiver(post_save, sender='peoples.People')
def handle_user_language_preference_change(sender, instance, created, **kwargs):
    """
    Handle user language preference changes by queuing translation of existing conversations.

    When a user changes their language preference, this signal will queue translation
    of their recent conversations to the new preferred language.
    """

    # Skip for new users or if preferred_language field wasn't changed
    if created:
        return

    # Check if preferred_language was actually changed
    if not hasattr(instance, '_old_preferred_language'):
        return

    old_language = getattr(instance, '_old_preferred_language')
    new_language = instance.preferred_language

    if old_language == new_language or new_language == 'en':
        return

    try:
        # Get user's recent conversations (last 30 days)
        recent_conversations = WisdomConversation.objects.filter(
            tenant=instance.tenant,
            conversation_date__gte=timezone.now() - timedelta(days=30)
        )

        queued_count = 0
        for conversation in recent_conversations:
            # Check if translation already exists
            existing = WisdomConversationTranslation.objects.filter(
                original_conversation=conversation,
                target_language=new_language,
                status='completed'
            ).first()

            if not existing or existing.is_expired:
                from ..tasks import translate_conversation_async
                translate_conversation_async.delay(
                    conversation_id=conversation.id,
                    target_language=new_language,
                    priority='user_preference',
                    retry_count=0
                )
                queued_count += 1

        if queued_count > 0:
            logger.info(
                f"Queued {queued_count} conversations for translation to {new_language} "
                f"due to user {instance.id} language preference change"
            )

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Error handling language preference change for user {instance.id}: {e}", exc_info=True)


# Cache invalidation signal
@receiver(post_save, sender=WisdomConversationTranslation)
def invalidate_translation_cache(sender, instance: WisdomConversationTranslation, **kwargs):
    """
    Invalidate Redis cache when translation is updated in database.

    This ensures consistency between database cache and Redis cache.
    """
    try:
        # Clear Redis cache for this specific translation
        cache_key = f"wisdom_translation:{instance.original_conversation.id}:{instance.target_language}"
        cache.delete(cache_key)

        logger.debug(f"Invalidated cache for translation {instance.id}")

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Error invalidating translation cache: {e}", exc_info=True)


# Settings configuration for auto-translation
def get_auto_translation_settings():
    """
    Get auto-translation configuration from Django settings.

    Returns:
        dict: Configuration parameters for auto-translation
    """
    return {
        'enabled': getattr(settings, 'WELLNESS_AUTO_TRANSLATE_CONVERSATIONS', True),
        'max_per_hour': getattr(settings, 'WELLNESS_MAX_AUTO_TRANSLATIONS_PER_HOUR', 50),
        'max_retries': getattr(settings, 'WELLNESS_TRANSLATION_MAX_RETRIES', 3),
        'supported_languages': getattr(settings, 'WELLNESS_SUPPORTED_LANGUAGES', [
            'hi', 'te', 'es', 'fr', 'ar', 'zh'
        ]),
        'batch_size': getattr(settings, 'WELLNESS_TRANSLATION_BATCH_SIZE', 10),
        'retry_delay_base': getattr(settings, 'WELLNESS_TRANSLATION_RETRY_DELAY_BASE', 60),  # seconds
    }


# For tracking model changes (used in user preference change signal)
def track_model_changes(sender, **kwargs):
    """
    Track changes to model fields for use in signal handlers.

    This is called by Django's pre_save signal to track what fields changed.
    """
    if kwargs.get('raw', False):
        return

    instance = kwargs['instance']

    if hasattr(instance, 'pk') and instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_preferred_language = old_instance.preferred_language
        except sender.DoesNotExist:
            instance._old_preferred_language = None
    else:
        instance._old_preferred_language = None


# Connect the tracking signal
from django.db.models.signals import pre_save
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
pre_save.connect(track_model_changes, sender='peoples.People')