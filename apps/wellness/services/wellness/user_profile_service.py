"""
User Profile Service - Build comprehensive user profiles for ML recommendations

Responsible for:
- Building user profile from wellness progress and journal history
- Analyzing content interaction patterns
- Calculating user preferences and engagement metrics
- Providing profile features for recommendation algorithms
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

from apps.wellness.models import WellnessUserProgress, WellnessContentInteraction
from apps.wellness.logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class UserProfileService:
    """Service for building comprehensive user profiles"""

    @staticmethod
    def build_user_profile(user):
        """
        Build comprehensive user profile for ML recommendations

        Args:
            user: User object

        Returns:
            dict: User profile with wellness progress, journal patterns, interaction history
        """
        profile = {}

        try:
            # Wellness progress data
            progress = user.wellness_progress
            profile.update({
                'current_streak': progress.current_streak,
                'total_content_viewed': progress.total_content_viewed,
                'completion_rate': progress.completion_rate,
                'preferred_content_level': progress.preferred_content_level,
                'enabled_categories': progress.enabled_categories
            })
        except WellnessUserProgress.DoesNotExist:
            profile.update({
                'current_streak': 0,
                'total_content_viewed': 0,
                'completion_rate': 0.0,
                'preferred_content_level': 'short_read',
                'enabled_categories': []
            })

        # Journal patterns analysis
        profile = UserProfileService._add_journal_patterns(user, profile)

        # Content interaction patterns
        profile = UserProfileService._add_interaction_patterns(user, profile)

        return profile

    @staticmethod
    def _add_journal_patterns(user, profile):
        """Add journal pattern analysis to user profile"""
        try:
            from apps.journal.models import JournalEntry

            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=30)
            )

            mood_entries = recent_entries.exclude(mood_rating__isnull=True)
            if mood_entries.exists():
                profile['avg_mood'] = mood_entries.aggregate(avg=Avg('mood_rating'))['avg']

            stress_entries = recent_entries.exclude(stress_level__isnull=True)
            if stress_entries.exists():
                profile['avg_stress'] = stress_entries.aggregate(avg=Avg('stress_level'))['avg']

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to analyze journal patterns: {e}")

        return profile

    @staticmethod
    def _add_interaction_patterns(user, profile):
        """Add content interaction patterns to user profile"""
        interactions = WellnessContentInteraction.objects.filter(
            user=user,
            interaction_date__gte=timezone.now() - timedelta(days=30)
        )

        if interactions.exists():
            profile.update({
                'interaction_count': interactions.count(),
                'avg_engagement_score': interactions.aggregate(avg=Avg('engagement_score'))['avg'],
                'preferred_categories': list(interactions.values('content__category').annotate(
                    count=Count('id')
                ).order_by('-count')[:3].values_list('content__category', flat=True))
            })

        return profile
