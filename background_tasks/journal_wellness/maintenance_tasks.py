"""
Maintenance Tasks for Journal & Wellness System

Handles periodic maintenance and cleanup operations including:
- Daily wellness content scheduling
- User engagement streak updates
- Old data cleanup
- Data retention policy enforcement

All tasks use existing PostgreSQL Task Queue infrastructure.
"""

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db import DatabaseError, IntegrityError, ConnectionError
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from datetime import timedelta
import logging

from apps.wellness.models import WellnessUserProgress, WellnessContentInteraction
from apps.journal.privacy import JournalPrivacyManager

User = get_user_model()
logger = logging.getLogger('background_tasks')


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(ConnectionError, DatabaseError, IntegrityError),
    retry_backoff=True,
    soft_time_limit=1800,  # 30 minutes - daily batch processing
    time_limit=2400         # 40 minutes hard limit
)
def daily_wellness_content_scheduling(self):
    """
    Daily task to schedule wellness content for all active users

    Runs daily to:
    - Send daily wellness tips to users who have them enabled
    - Check for users who need wellness interventions
    - Update user engagement streaks
    - Clean up expired content interactions
    """

    logger.info("Running daily wellness content scheduling")

    try:
        # Get all users with daily tips enabled
        # OPTIMIZATION: Prefetch today's tips to eliminate N+1 query (PERF-001)
        from django.db.models import Prefetch

        today = timezone.now().date()
        users_with_daily_tips = WellnessUserProgress.objects.filter(
            daily_tip_enabled=True,
            user__isverified=True  # Only verified/active users
        ).select_related('user').prefetch_related(
            Prefetch(
                'user__wellnesscontentinteraction_set',
                queryset=WellnessContentInteraction.objects.filter(
                    delivery_context='daily_tip',
                    interaction_date__date=today
                ),
                to_attr='todays_tips'
            )
        )

        scheduled_count = 0
        skipped_count = 0

        for progress in users_with_daily_tips:
            try:
                # Check if user already received content today (no extra query!)
                if not progress.user.todays_tips:
                    # Schedule daily tip
                    from background_tasks.journal_wellness_tasks import schedule_wellness_content_delivery
                    schedule_wellness_content_delivery.delay(
                        progress.user.id, 'daily_schedule'
                    )
                    scheduled_count += 1
                else:
                    skipped_count += 1

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Failed to schedule daily tip for user {progress.user.id}: {e}")

        # Update user streaks
        from background_tasks.journal_wellness_tasks import update_all_user_streaks
        update_result = update_all_user_streaks.delay()

        # Clean up old interactions
        from background_tasks.journal_wellness_tasks import cleanup_old_wellness_interactions
        cleanup_result = cleanup_old_wellness_interactions.delay()

        logger.info(f"Daily scheduling complete: {scheduled_count} scheduled, {skipped_count} skipped")

        return {
            'success': True,
            'users_scheduled': scheduled_count,
            'users_skipped': skipped_count,
            'total_users_checked': users_with_daily_tips.count(),
            'streak_update_task': update_result.id,
            'cleanup_task': cleanup_result.id,
            'scheduled_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Daily wellness scheduling failed: {e}")
        raise  # Let autoretry handle
    except (ValueError, TypeError) as e:
        logger.error(f"Daily wellness scheduling failed (non-retryable): {e}")
        return {
            'success': False,
            'error': 'processing_error',
            'details': str(e)
        }


@shared_task(
    soft_time_limit=600,  # 10 minutes - streak updates
    time_limit=900         # 15 minutes hard limit
)
def update_all_user_streaks():
    """Update wellness engagement streaks for all users"""

    logger.info("Updating wellness engagement streaks for all users")

    try:
        # Get all users with wellness progress
        all_progress = WellnessUserProgress.objects.select_related('user')

        updated_count = 0
        broken_streaks = 0

        for progress in all_progress:
            try:
                old_streak = progress.current_streak

                # Update streak based on recent activity
                progress.update_streak()

                if progress.current_streak != old_streak:
                    progress.save()
                    updated_count += 1

                    if progress.current_streak == 0 and old_streak > 0:
                        broken_streaks += 1
                        logger.debug(f"Streak broken for user {progress.user.id} (was {old_streak} days)")

            except (DatabaseError, IntegrityError) as e:
                logger.error(f"Failed to update streak for user {progress.user.id}: {e}")

        logger.info(f"Streak update complete: {updated_count} updated, {broken_streaks} broken")

        return {
            'success': True,
            'users_updated': updated_count,
            'streaks_broken': broken_streaks,
            'total_users': all_progress.count(),
            'updated_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Streak update failed: {e}")
        raise


@shared_task(
    soft_time_limit=300,  # 5 minutes - cleanup
    time_limit=600         # 10 minutes hard limit
)
def cleanup_old_wellness_interactions():
    """Clean up old wellness interaction records for performance"""

    logger.info("Cleaning up old wellness interactions")

    try:
        # Keep interactions for 1 year, delete older ones
        cutoff_date = timezone.now() - timedelta(days=365)

        old_interactions = WellnessContentInteraction.objects.filter(
            interaction_date__lt=cutoff_date
        )

        deleted_count = old_interactions.count()
        old_interactions.delete()

        logger.info(f"Cleaned up {deleted_count} old wellness interactions")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Wellness interaction cleanup failed: {e}")
        raise


@shared_task(
    soft_time_limit=1800,  # 30 minutes - retention enforcement
    time_limit=2400         # 40 minutes hard limit
)
def enforce_data_retention_policies():
    """
    Enforce data retention policies for all users

    Runs daily to:
    - Apply user-specific retention policies
    - Auto-delete expired entries
    - Anonymize data per retention settings
    - Generate retention compliance reports
    """

    logger.info("Enforcing data retention policies")

    try:
        privacy_manager = JournalPrivacyManager()

        # Get users with auto-delete enabled
        # OPTIMIZATION: Use iterator() for memory-efficient streaming (PERF-003)
        users_with_retention = User.objects.filter(
            journal_privacy_settings__auto_delete_enabled=True
        ).select_related('journal_privacy_settings').iterator(chunk_size=100)

        total_deleted = 0
        total_anonymized = 0

        for user in users_with_retention:
            try:
                retention_result = privacy_manager.enforce_data_retention_policy(user)
                total_deleted += retention_result.get('entries_deleted', 0)
                total_anonymized += retention_result.get('entries_anonymized', 0)

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Retention enforcement failed for user {user.id}: {e}")

        logger.info(f"Data retention enforcement complete: {total_deleted} deleted, {total_anonymized} anonymized")

        return {
            'success': True,
            'users_processed': users_with_retention.count(),
            'entries_deleted': total_deleted,
            'entries_anonymized': total_anonymized,
            'processed_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Data retention enforcement failed: {e}")
        raise
