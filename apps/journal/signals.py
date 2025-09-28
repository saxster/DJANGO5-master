"""
Journal App Signals

Handles automatic creation of privacy settings, wellness content triggering,
analytics updates, and other background processing when journal entries are created/updated.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import JournalEntry, JournalPrivacySettings
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_journal_privacy_settings(sender, instance, created, **kwargs):
    """Automatically create journal privacy settings for new users"""
    if created:
        try:
            JournalPrivacySettings.objects.get_or_create(
                user=instance,
                defaults={
                    'consent_timestamp': timezone.now(),
                    'default_privacy_scope': 'private',
                    'wellbeing_sharing_consent': False,
                    'manager_access_consent': False,
                    'analytics_consent': False,
                    'crisis_intervention_consent': False,
                    'data_retention_days': 365,
                    'auto_delete_enabled': False,
                }
            )
            logger.info(f"Created journal privacy settings for user {instance.peoplename}")
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to create journal privacy settings for user {instance.id}: {e}")


@receiver(post_save, sender=JournalEntry)
def handle_journal_entry_created_or_updated(sender, instance, created, **kwargs):
    """Handle journal entry creation/update events"""

    if created:
        logger.info(f"New journal entry created: {instance.title} by {instance.user.peoplename}")

        # Trigger pattern analysis for wellness content (will be implemented later)
        try:
            # Import here to avoid circular imports
            from .services.pattern_analyzer import trigger_pattern_analysis
            trigger_pattern_analysis(instance)
        except ImportError:
            # Service not implemented yet
            pass
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to trigger pattern analysis for entry {instance.id}: {e}")

        # Check for crisis indicators
        try:
            check_crisis_indicators(instance)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to check crisis indicators for entry {instance.id}: {e}")

    else:
        logger.debug(f"Journal entry updated: {instance.title} by {instance.user.peoplename}")


@receiver(post_delete, sender=JournalEntry)
def handle_journal_entry_deleted(sender, instance, **kwargs):
    """Handle journal entry deletion"""
    logger.info(f"Journal entry deleted: {instance.title} by {instance.user.peoplename}")


def check_crisis_indicators(journal_entry):
    """Check for crisis indicators and trigger appropriate responses"""

    # Get user's privacy settings
    try:
        privacy_settings = journal_entry.user.journal_privacy_settings
    except JournalPrivacySettings.DoesNotExist:
        logger.warning(f"No privacy settings found for user {journal_entry.user.id}")
        return

    # Only proceed if user has given crisis intervention consent
    if not privacy_settings.crisis_intervention_consent:
        return

    crisis_detected = False
    crisis_indicators = []

    # Check mood crisis indicators
    if journal_entry.mood_rating and journal_entry.mood_rating <= 2:
        crisis_detected = True
        crisis_indicators.append(f"Very low mood rating: {journal_entry.mood_rating}/10")

    # Check stress crisis indicators
    if journal_entry.stress_level and journal_entry.stress_level >= 5:
        crisis_detected = True
        crisis_indicators.append(f"Maximum stress level: {journal_entry.stress_level}/5")

    # Check content for crisis keywords
    if journal_entry.content:
        crisis_keywords = [
            'hopeless', 'overwhelmed', "can't cope", 'breaking point',
            'giving up', 'no point', 'worthless', 'suicidal'
        ]
        content_lower = journal_entry.content.lower()

        found_keywords = [keyword for keyword in crisis_keywords if keyword in content_lower]
        if found_keywords:
            crisis_detected = True
            crisis_indicators.append(f"Crisis keywords detected: {', '.join(found_keywords)}")

    if crisis_detected:
        logger.warning(
            f"CRISIS INDICATORS DETECTED for user {journal_entry.user.peoplename} "
            f"(ID: {journal_entry.user.id}) in entry {journal_entry.id}. "
            f"Indicators: {'; '.join(crisis_indicators)}"
        )

        # TODO: Implement crisis intervention workflow
        # This could include:
        # - Immediate notification to designated crisis responders
        # - Triggering immediate wellness content delivery
        # - Creating urgent tasks for managers/HR
        # - Sending appropriate resources to the user

        try:
            # Import here to avoid circular imports
            from .services.crisis_intervention import handle_crisis_detected
            handle_crisis_detected(journal_entry, crisis_indicators)
        except ImportError:
            # Crisis intervention service not implemented yet
            logger.info("Crisis intervention service not yet implemented")
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to handle crisis intervention: {e}")


@receiver(post_save, sender=JournalEntry)
def update_user_analytics_async(sender, instance, created, **kwargs):
    """Queue user analytics update in background"""

    # Only update analytics if user has consented
    try:
        privacy_settings = instance.user.journal_privacy_settings
        if not privacy_settings.analytics_consent:
            return
    except JournalPrivacySettings.DoesNotExist:
        logger.warning(f"No privacy settings found for user {instance.user.id}")
        return

    try:
        # TODO: Queue background task for analytics update
        # This will be implemented with the analytics engine
        logger.debug(f"Queuing analytics update for user {instance.user.id}")

        # Example of how this might work:
        # from background_tasks import queue_analytics_update
        # queue_analytics_update(instance.user.id, instance.id)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to queue analytics update for user {instance.user.id}: {e}")


def trigger_wellness_content_delivery(journal_entry):
    """Trigger contextual wellness content delivery based on entry patterns"""

    try:
        # This will be implemented with the wellness content system
        logger.debug(f"Triggering wellness content delivery for entry {journal_entry.id}")

        # Example of how this might work:
        # from apps.wellness.services import WellnessContentDeliveryService
        # delivery_service = WellnessContentDeliveryService()
        # delivery_service.deliver_contextual_content(journal_entry)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to trigger wellness content delivery: {e}")


# Signal for handling privacy settings changes
@receiver(post_save, sender=JournalPrivacySettings)
def handle_privacy_settings_updated(sender, instance, created, **kwargs):
    """Handle privacy settings updates"""

    if created:
        logger.info(f"Privacy settings created for user {instance.user.peoplename}")
    else:
        logger.info(f"Privacy settings updated for user {instance.user.peoplename}")

        # If user revoked consents, we might need to clean up data
        if not instance.analytics_consent:
            logger.info(f"Analytics consent revoked for user {instance.user.id} - may need data cleanup")

        if not instance.wellbeing_sharing_consent:
            logger.info(f"Wellbeing sharing consent revoked for user {instance.user.id}")

        if not instance.crisis_intervention_consent:
            logger.info(f"Crisis intervention consent revoked for user {instance.user.id}")