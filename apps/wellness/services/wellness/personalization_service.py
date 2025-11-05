"""
Personalization Service - Select personalized wellness content based on user patterns

Responsible for:
- Selecting personalized wellness tips based on user patterns
- Applying user preferences and category filters
- Excluding recently viewed content
- Personalizing based on mood/stress/energy patterns
- Applying seasonal relevance filters
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Q

from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.wellness.logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class PersonalizationService:
    """Service for personalizing wellness content selection"""

    @staticmethod
    def select_personalized_tip(user, progress, patterns, params):
        """
        Select personalized wellness tip based on user patterns

        Args:
            user: User object
            progress: WellnessUserProgress object
            patterns: dict of user patterns from PatternAnalysisService
            params: dict with preferred_category, content_level, exclude_recent

        Returns:
            WellnessContent: Selected wellness content or None
        """
        # Base queryset
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            delivery_context__in=['daily_tip', 'pattern_triggered']
        )

        # Apply user preferences
        if progress.enabled_categories:
            queryset = queryset.filter(category__in=progress.enabled_categories)

        if params.get('preferred_category'):
            queryset = queryset.filter(category=params['preferred_category'])

        if params.get('content_level'):
            queryset = queryset.filter(content_level=params['content_level'])
        else:
            # Use user's preferred content level
            queryset = queryset.filter(content_level=progress.preferred_content_level)

        # Exclude recently viewed content
        if params.get('exclude_recent', True):
            recent_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                interaction_date__gte=timezone.now() - timedelta(days=7)
            ).values_list('content_id', flat=True)

            queryset = queryset.exclude(id__in=recent_interactions)

        # Personalize based on patterns
        queryset = PersonalizationService._apply_pattern_filters(queryset, patterns)

        # Check seasonal relevance
        current_month = timezone.now().month
        queryset = queryset.filter(
            Q(seasonal_relevance__contains=[current_month]) |
            Q(seasonal_relevance=[])  # No seasonal restrictions
        )

        # Order by priority and randomize within same priority
        queryset = queryset.order_by('-priority_score', '?')

        return queryset.first()

    @staticmethod
    def _apply_pattern_filters(queryset, patterns):
        """Apply pattern-based filters to content queryset"""
        if patterns.get('current_stress', 0) >= 4:
            # High stress - prioritize stress management
            queryset = queryset.filter(
                Q(category='stress_management') |
                Q(tags__contains=['stress', 'anxiety', 'pressure'])
            )
        elif patterns.get('current_mood', 10) <= 3:
            # Low mood - prioritize mood support
            queryset = queryset.filter(
                Q(category='mental_health') |
                Q(tags__contains=['mood', 'depression', 'wellbeing'])
            )
        elif patterns.get('current_energy', 10) <= 4:
            # Low energy - prioritize energy boosting
            queryset = queryset.filter(
                Q(category='physical_wellness') |
                Q(tags__contains=['energy', 'fatigue', 'vitality'])
            )

        return queryset
