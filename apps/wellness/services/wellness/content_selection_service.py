"""
Content Selection Service - Select wellness content based on urgency and context

Responsible for:
- Selecting urgent support content based on intervention categories
- Selecting follow-up content for continued support
- Applying delivery context filters
- Prioritizing content by urgency and priority score
"""

from django.db.models import Q

from apps.wellness.models import WellnessContent
from apps.wellness.logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class ContentSelectionService:
    """Service for selecting wellness content based on urgency and context"""

    @staticmethod
    def get_urgent_support_content(user, urgency_analysis, user_context, max_items):
        """
        Get immediate support content for urgent situations

        Args:
            user: User object
            urgency_analysis: dict from UrgencyAnalysisService
            user_context: dict with user context data
            max_items: int maximum number of items to return

        Returns:
            list: WellnessContent objects for urgent support
        """
        categories = urgency_analysis.get('intervention_categories', [])

        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            delivery_context__in=['stress_response', 'mood_support', 'energy_boost']
        )

        # Filter by intervention categories
        if 'stress_management' in categories:
            queryset = queryset.filter(
                Q(category='stress_management') |
                Q(delivery_context='stress_response')
            )
        elif 'mood_crisis_support' in categories:
            queryset = queryset.filter(
                Q(category='mental_health') |
                Q(delivery_context='mood_support')
            )
        elif 'energy_management' in categories:
            queryset = queryset.filter(
                Q(category='physical_wellness') |
                Q(delivery_context='energy_boost')
            )

        return list(queryset.order_by('-priority_score')[:max_items])

    @staticmethod
    def get_follow_up_content(user, urgency_analysis, user_context, max_items):
        """
        Get follow-up content for continued support

        Args:
            user: User object
            urgency_analysis: dict from UrgencyAnalysisService
            user_context: dict with user context data
            max_items: int maximum number of items to return

        Returns:
            list: WellnessContent objects for follow-up support
        """
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            delivery_context='pattern_triggered'
        )

        # Select content based on lower urgency patterns
        categories = ['mental_health', 'stress_management', 'workplace_health']
        queryset = queryset.filter(category__in=categories)

        return list(queryset.order_by('-priority_score', '?')[:max_items])
