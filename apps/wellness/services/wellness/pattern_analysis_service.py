"""
Pattern Analysis Service - Extract user journal pattern analysis business logic

Responsible for:
- Analyzing recent journal entries for mood/stress/energy patterns
- Calculating pattern statistics (averages, current values)
- Providing pattern-based insights for content selection
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

from apps.wellness.logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class PatternAnalysisService:
    """Service for analyzing user journal patterns"""

    @staticmethod
    def analyze_recent_patterns(user, days=7):
        """
        Analyze user's recent journal patterns for personalization

        Args:
            user: User object
            days: Number of days to analyze (default: 7)

        Returns:
            dict: Pattern analysis with mood/stress/energy statistics
        """
        try:
            from apps.journal.models import JournalEntry

            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=days),
                is_deleted=False
            ).order_by('-timestamp')

            patterns = {
                'entry_count': recent_entries.count(),
                'wellbeing_entries': recent_entries.filter(
                    entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']
                ).count()
            }

            # Mood analysis
            mood_entries = recent_entries.exclude(mood_rating__isnull=True)
            if mood_entries.exists():
                patterns['current_mood'] = mood_entries.first().mood_rating
                patterns['avg_mood'] = mood_entries.aggregate(avg=Avg('mood_rating'))['avg']

            # Stress analysis
            stress_entries = recent_entries.exclude(stress_level__isnull=True)
            if stress_entries.exists():
                patterns['current_stress'] = stress_entries.first().stress_level
                patterns['avg_stress'] = stress_entries.aggregate(avg=Avg('stress_level'))['avg']

            # Energy analysis
            energy_entries = recent_entries.exclude(energy_level__isnull=True)
            if energy_entries.exists():
                patterns['current_energy'] = energy_entries.first().energy_level
                patterns['avg_energy'] = energy_entries.aggregate(avg=Avg('energy_level'))['avg']

            return patterns

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to analyze patterns for user {user.id}: {e}")
            return {'entry_count': 0}
