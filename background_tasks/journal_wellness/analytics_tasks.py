"""
Analytics Tasks for Journal & Wellness System

Handles comprehensive analytics computation and updates including:
- Real-time wellbeing analytics computation
- Content effectiveness tracking
- User pattern analysis
- Analytics cache management

All tasks use existing PostgreSQL Task Queue infrastructure with reports priority queue.
"""

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.contrib.auth import get_user_model
from django.db.models import Avg
from datetime import timedelta
import logging

from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.wellness.constants import (
    MINIMUM_ANALYTICS_ENTRIES,
    LOW_WELLBEING_THRESHOLD,
)
from apps.journal.ml.analytics_engine import WellbeingAnalyticsEngine
from apps.core.exceptions import IntegrationException

# Import enhanced base classes and utilities
from apps.core.tasks.base import (
    BaseTask, TaskMetrics, log_task_context
)

User = get_user_model()
logger = logging.getLogger('background_tasks')


@shared_task(
    base=BaseTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, DatabaseError, IntegrityError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    queue='reports',
    priority=6,
    soft_time_limit=600,  # 10 minutes - analytics computation
    time_limit=900         # 15 minutes hard limit
)
def update_user_analytics(self, user_id, trigger_entry_id=None):
    """
    Update user's wellbeing analytics in background

    Args:
        user_id: User to update analytics for
        trigger_entry_id: Journal entry that triggered the update (optional)

    Returns:
        dict: Analytics update results
    """

    with self.task_context(user_id=user_id, trigger_entry_id=trigger_entry_id):
        log_task_context('update_user_analytics', user_id=user_id, trigger_entry_id=trigger_entry_id)

        # Record task metrics
        TaskMetrics.increment_counter('user_analytics_started', {'domain': 'journal'})

    try:
        user = User.objects.get(id=user_id)

        # Check user consent for analytics processing
        try:
            privacy_settings = user.journal_privacy_settings
            if not privacy_settings.analytics_consent:
                logger.info(f"Skipping analytics update - user {user_id} has not consented")
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'no_analytics_consent'
                }
        except JournalPrivacySettings.DoesNotExist:
            logger.warning(f"No privacy settings for user {user_id} - skipping analytics")
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_privacy_settings'
            }

        # Get user's journal entries for analysis (last 90 days)
        journal_entries = list(JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=90),
            is_deleted=False
        ).order_by('timestamp'))

        if len(journal_entries) < MINIMUM_ANALYTICS_ENTRIES:
            logger.debug(f"Insufficient data for analytics - user {user_id} has {len(journal_entries)} entries (minimum: {MINIMUM_ANALYTICS_ENTRIES})")
            return {
                'success': True,
                'skipped': True,
                'reason': 'insufficient_data',
                'entry_count': len(journal_entries)
            }

        # Generate comprehensive analytics
        analytics_engine = WellbeingAnalyticsEngine()

        # Calculate all analytics components
        mood_trends = analytics_engine.calculate_mood_trends(journal_entries)
        stress_analysis = analytics_engine.calculate_stress_trends(journal_entries)
        energy_trends = analytics_engine.calculate_energy_trends(journal_entries)
        gratitude_insights = analytics_engine.calculate_gratitude_insights(journal_entries)
        achievement_insights = analytics_engine.calculate_achievement_insights(journal_entries)
        pattern_insights = analytics_engine.calculate_pattern_insights(journal_entries)

        # Generate recommendations
        recommendations = analytics_engine.generate_recommendations(
            mood_trends, stress_analysis, energy_trends, journal_entries
        )

        # Calculate overall wellbeing score
        wellbeing_score = analytics_engine.calculate_overall_wellbeing_score(
            mood_trends, stress_analysis, energy_trends, journal_entries
        )

        # Cache analytics results for quick API access
        analytics_cache_key = f"user_analytics_{user_id}"
        analytics_data = {
            'wellbeing_trends': {
                'mood_analysis': mood_trends,
                'stress_analysis': stress_analysis,
                'energy_analysis': energy_trends,
                'gratitude_insights': gratitude_insights,
                'achievement_insights': achievement_insights
            },
            'behavioral_patterns': pattern_insights,
            'recommendations': recommendations,
            'overall_wellbeing_score': wellbeing_score,
            'analysis_metadata': {
                'analysis_date': timezone.now().isoformat(),
                'data_points_analyzed': len(journal_entries),
                'algorithm_version': '2.1.0',
                'trigger_entry_id': trigger_entry_id
            }
        }

        # TODO: Cache analytics data using Django cache framework
        # cache.set(analytics_cache_key, analytics_data, timeout=3600)  # 1 hour cache

        logger.info(f"Analytics updated for user {user_id}: wellbeing_score={wellbeing_score['overall_score']}")

        # Schedule wellness content delivery if patterns indicate need
        if wellbeing_score['overall_score'] < LOW_WELLBEING_THRESHOLD:
            from background_tasks.journal_wellness_tasks import schedule_wellness_content_delivery
            schedule_wellness_content_delivery.delay(user_id, 'low_wellbeing_score')

        return {
            'success': True,
            'user_id': user_id,
            'wellbeing_score': wellbeing_score['overall_score'],
            'entry_count': len(journal_entries),
            'recommendations_count': len(recommendations),
            'updated_at': timezone.now().isoformat()
        }

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for analytics update")
        return {
            'success': False,
            'error': 'user_not_found',
            'user_id': user_id
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Analytics update failed for user {user_id}: {e}")
        # Let autoretry handle these exceptions
        raise
    except (ValueError, TypeError) as e:
        logger.error(f"Analytics update failed for user {user_id} (non-retryable): {e}")
        return {
            'success': False,
            'error': 'validation_error',
            'user_id': user_id,
            'details': str(e)
        }


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=180,  # 3 minutes - effectiveness metrics
    time_limit=360         # 6 minutes hard limit
)
def update_content_effectiveness_metrics(self, content_id):
    """
    Update effectiveness metrics for wellness content

    Args:
        content_id: Wellness content to update metrics for

    Returns:
        dict: Effectiveness update results
    """

    logger.debug(f"Updating effectiveness metrics for content {content_id}")

    try:
        content = WellnessContent.objects.get(id=content_id)

        # Get all interactions for this content
        interactions = WellnessContentInteraction.objects.filter(content=content)

        if not interactions.exists():
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_interactions'
            }

        # Calculate effectiveness metrics
        total_interactions = interactions.count()
        completed_interactions = interactions.filter(interaction_type='completed').count()
        positive_interactions = interactions.filter(
            interaction_type__in=['completed', 'bookmarked', 'acted_upon', 'requested_more']
        ).count()
        dismissed_interactions = interactions.filter(interaction_type='dismissed').count()

        # Calculate rates
        completion_rate = completed_interactions / total_interactions if total_interactions > 0 else 0
        effectiveness_rate = positive_interactions / total_interactions if total_interactions > 0 else 0
        dismissal_rate = dismissed_interactions / total_interactions if total_interactions > 0 else 0

        # Calculate average engagement score
        avg_engagement = interactions.aggregate(avg=Avg('engagement_score'))['avg'] or 0

        # Calculate average rating
        rated_interactions = interactions.exclude(user_rating__isnull=True)
        avg_rating = rated_interactions.aggregate(avg=Avg('user_rating'))['avg'] if rated_interactions.exists() else None

        # Update content priority based on effectiveness
        effectiveness_score = (effectiveness_rate + completion_rate) / 2

        # Adjust priority score based on effectiveness
        if effectiveness_score > 0.8:
            # High effectiveness - boost priority
            new_priority = min(100, content.priority_score + 5)
        elif effectiveness_score < 0.4:
            # Low effectiveness - reduce priority
            new_priority = max(1, content.priority_score - 5)
        else:
            new_priority = content.priority_score

        content.priority_score = new_priority
        content.save()

        logger.debug(f"Updated content {content_id} effectiveness: {effectiveness_score:.2f}, priority: {new_priority}")

        return {
            'success': True,
            'content_id': content_id,
            'content_title': content.title,
            'metrics': {
                'total_interactions': total_interactions,
                'completion_rate': round(completion_rate, 3),
                'effectiveness_rate': round(effectiveness_rate, 3),
                'dismissal_rate': round(dismissal_rate, 3),
                'avg_engagement_score': round(avg_engagement, 2),
                'avg_rating': round(avg_rating, 2) if avg_rating else None
            },
            'priority_updated': {
                'old_priority': content.priority_score,
                'new_priority': new_priority
            },
            'updated_at': timezone.now().isoformat()
        }

    except WellnessContent.DoesNotExist:
        logger.error(f"Wellness content {content_id} not found")
        return {
            'success': False,
            'error': 'content_not_found'
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Content effectiveness update failed for {content_id}: {e}")
        raise self.retry(exc=e, countdown=300)
