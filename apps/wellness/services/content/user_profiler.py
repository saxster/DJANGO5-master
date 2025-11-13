"""
Wellness User Profile Builder

Comprehensive user profile builder for ML-powered wellness recommendations.

Features:
- Multi-source data integration (journal + wellness interactions)
- Pattern recognition and preference extraction
- Behavioral analysis and trend identification
- Profile updating and versioning
- Privacy-compliant data aggregation
"""

from datetime import timedelta
from collections import Counter
from django.utils import timezone
from django.db.models import Avg, Count, Q
import logging

from apps.journal.models import JournalEntry
from apps.wellness.models import WellnessUserProgress, WellnessContentInteraction
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


class UserProfileBuilder:
    """
    Comprehensive user profile builder for ML recommendations

    Features:
    - Multi-source data integration (journal + wellness interactions)
    - Pattern recognition and preference extraction
    - Behavioral analysis and trend identification
    - Profile updating and versioning
    - Privacy-compliant data aggregation
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def build_comprehensive_profile(self, user):
        """
        Build comprehensive user profile for ML recommendations

        Profile Components:
        1. Journal patterns and trends
        2. Wellness content engagement history
        3. Preference indicators and explicit settings
        4. Behavioral patterns and temporal preferences
        5. Progress metrics and achievement patterns
        """

        self.logger.debug(f"Building comprehensive profile for user {user.id}")

        try:
            profile = {
                'user': user,
                'profile_timestamp': timezone.now(),
                'data_sources': []
            }

            # Get wellness progress data
            try:
                progress = user.wellness_progress
                profile.update({
                    'wellness_progress': progress,
                    'current_streak': progress.current_streak,
                    'total_content_viewed': progress.total_content_viewed,
                    'completion_rate': progress.completion_rate,
                    'preferred_content_level': progress.preferred_content_level,
                    'enabled_categories': progress.enabled_categories,
                    'achievements_earned': progress.achievements_earned
                })
                profile['data_sources'].append('wellness_progress')
            except WellnessUserProgress.DoesNotExist:
                self.logger.info(f"No wellness progress found for user {user.id} - using defaults")

            # Analyze journal patterns
            journal_profile = self._build_journal_profile(user)
            profile.update(journal_profile)
            if journal_profile:
                profile['data_sources'].append('journal_analysis')

            # Analyze wellness interaction patterns
            interaction_profile = self._build_interaction_profile(user)
            profile.update(interaction_profile)
            if interaction_profile:
                profile['data_sources'].append('wellness_interactions')

            # Calculate profile completeness and quality
            profile.update(self._assess_profile_quality(profile))

            self.logger.info(f"Profile built for user {user.id}: {len(profile['data_sources'])} data sources")

            return profile

        except DATABASE_EXCEPTIONS as e:
            self.logger.error(f"Database error building profile for user {user.id}: {e}", exc_info=True)
            return {'user': user, 'error': str(e)}
        except ObjectDoesNotExist as e:
            self.logger.warning(f"Profile data not found for user {user.id}: {e}")
            return {'user': user, 'error': str(e)}

    def _build_journal_profile(self, user):
        """Build profile component from journal data"""
        try:
            # Get recent journal entries (last 60 days)
            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=60),
                is_deleted=False
            ).order_by('-timestamp')

            if not recent_entries.exists():
                return {}

            profile = {
                'entry_count': recent_entries.count(),
                'journal_date_range': {
                    'start': recent_entries.last().timestamp.isoformat(),
                    'end': recent_entries.first().timestamp.isoformat()
                }
            }

            # Wellbeing metrics analysis
            wellbeing_entries = recent_entries.filter(
                Q(mood_rating__isnull=False) |
                Q(stress_level__isnull=False) |
                Q(energy_level__isnull=False)
            )

            if wellbeing_entries.exists():
                mood_data = wellbeing_entries.exclude(mood_rating__isnull=True)
                stress_data = wellbeing_entries.exclude(stress_level__isnull=True)
                energy_data = wellbeing_entries.exclude(energy_level__isnull=True)

                if mood_data.exists():
                    profile['avg_mood'] = mood_data.aggregate(avg=Avg('mood_rating'))['avg']
                    profile['mood_variability'] = self._calculate_variability(
                        [e.mood_rating for e in mood_data]
                    )

                if stress_data.exists():
                    profile['avg_stress'] = stress_data.aggregate(avg=Avg('stress_level'))['avg']

                if energy_data.exists():
                    profile['avg_energy'] = energy_data.aggregate(avg=Avg('energy_level'))['avg']

            # Entry type preferences
            entry_types = [e.entry_type for e in recent_entries]
            type_frequency = Counter(entry_types)
            profile['preferred_entry_types'] = [t for t, c in type_frequency.most_common(3)]

            # Temporal patterns
            hours = [e.timestamp.hour for e in recent_entries]
            profile['preferred_hours'] = [h for h, c in Counter(hours).most_common(2)]

            # Positive psychology engagement
            positive_entries = recent_entries.filter(
                entry_type__in=['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS']
            )
            profile['positive_psychology_ratio'] = positive_entries.count() / recent_entries.count()

            return profile

        except DATABASE_EXCEPTIONS as e:
            self.logger.error(f"Database error building journal profile for user {user.id}: {e}", exc_info=True)
            return {}
        except ObjectDoesNotExist as e:
            self.logger.warning(f"Journal profile data not found for user {user.id}: {e}")
            return {}

    def _build_interaction_profile(self, user):
        """Build profile component from wellness interaction data"""
        try:
            # Get recent interactions (last 90 days)
            recent_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                interaction_date__gte=timezone.now() - timedelta(days=90)
            ).select_related('content')

            if not recent_interactions.exists():
                return {}

            profile = {
                'interaction_count': recent_interactions.count()
            }

            # Engagement analysis
            avg_engagement = recent_interactions.aggregate(avg=Avg('engagement_score'))['avg']
            profile['avg_engagement_score'] = avg_engagement

            # Category preferences from interactions
            category_interactions = recent_interactions.values('content__category').annotate(
                count=Count('id'),
                avg_engagement=Avg('engagement_score')
            ).order_by('-count')

            profile['preferred_categories'] = [
                item['content__category'] for item in category_interactions[:3]
            ]

            # Content level preferences
            level_interactions = recent_interactions.values('content__content_level').annotate(
                count=Count('id'),
                avg_engagement=Avg('engagement_score')
            ).order_by('-avg_engagement')

            if level_interactions.exists():
                profile['optimal_content_level'] = level_interactions.first()['content__content_level']

            # Effectiveness patterns
            completed_interactions = recent_interactions.filter(interaction_type='completed')
            profile['completion_rate'] = completed_interactions.count() / recent_interactions.count()

            # Rating patterns
            rated_interactions = recent_interactions.exclude(user_rating__isnull=True)
            if rated_interactions.exists():
                profile['avg_rating_given'] = rated_interactions.aggregate(avg=Avg('user_rating'))['avg']

            return profile

        except DATABASE_EXCEPTIONS as e:
            self.logger.error(f"Database error building interaction profile for user {user.id}: {e}", exc_info=True)
            return {}
        except ObjectDoesNotExist as e:
            self.logger.warning(f"Interaction profile data not found for user {user.id}: {e}")
            return {}

    def _assess_profile_quality(self, profile):
        """Assess quality and completeness of user profile"""
        quality_metrics = {
            'data_richness': 0.0,
            'temporal_coverage': 0.0,
            'engagement_depth': 0.0,
            'overall_quality': 0.0
        }

        # Data richness
        data_points = 0
        if profile.get('entry_count', 0) > 0:
            data_points += 1
        if profile.get('interaction_count', 0) > 0:
            data_points += 1
        if profile.get('avg_mood') is not None:
            data_points += 1
        if profile.get('avg_stress') is not None:
            data_points += 1

        quality_metrics['data_richness'] = data_points / 4

        # Temporal coverage
        entry_count = profile.get('entry_count', 0)
        if entry_count >= 60:
            quality_metrics['temporal_coverage'] = 1.0
        elif entry_count >= 30:
            quality_metrics['temporal_coverage'] = 0.8
        elif entry_count >= 14:
            quality_metrics['temporal_coverage'] = 0.6
        else:
            quality_metrics['temporal_coverage'] = entry_count / 14

        # Engagement depth
        completion_rate = profile.get('completion_rate', 0)
        avg_engagement = profile.get('avg_engagement_score', 0)
        quality_metrics['engagement_depth'] = (completion_rate + avg_engagement / 5) / 2

        # Overall quality
        quality_metrics['overall_quality'] = sum(quality_metrics.values()) / 3

        return quality_metrics

    def _calculate_variability(self, values):
        """Calculate variability (standard deviation) of values"""
        if len(values) < 2:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def get_feature_summary(self, profile):
        """Get feature summary for API response"""
        return {
            'data_sources': profile.get('data_sources', []),
            'entry_count': profile.get('entry_count', 0),
            'interaction_count': profile.get('interaction_count', 0),
            'preferred_categories': profile.get('preferred_categories', []),
            'overall_quality': profile.get('overall_quality', 0.0)
        }
