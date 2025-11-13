"""
Wellness Content Selector

Contextual content selection and delivery for wellness interventions.

Features:
- Real-time pattern-based content selection
- Crisis intervention content delivery
- Urgency-based content prioritization
- User preference integration
- Evidence-based content curation
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
import logging

from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from apps.journal.models import JournalEntry
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


class WellnessContentDeliveryService:
    """
    Intelligent wellness content delivery with ML-powered personalization

    Features:
    - Real-time pattern analysis integration
    - Crisis intervention content delivery
    - Personalized content selection with effectiveness prediction
    - Evidence-based content curation
    - Multi-tenant content management
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_contextual_content(self, user, journal_entry, analysis_result):
        """
        Get contextual wellness content based on journal entry analysis

        Implements the algorithm from the specification:
        1. Analyze journal entry urgency and patterns
        2. Select appropriate content based on intervention categories
        3. Apply user preferences and personalization
        4. Return ranked content with delivery metadata
        """

        self.logger.info(f"Getting contextual content for user {user.id} based on journal entry analysis")

        urgency_score = analysis_result.get('urgency_score', 0)
        intervention_categories = analysis_result.get('intervention_categories', [])
        crisis_detected = analysis_result.get('crisis_detected', False)

        try:
            # Get user's wellness progress for personalization
            progress, created = WellnessUserProgress.objects.get_or_create(
                user=user,
                defaults={'tenant': getattr(user, 'tenant', None)}
            )

            # Get base content queryset
            content_queryset = WellnessContent.objects.filter(
                tenant=getattr(user, 'tenant', None),
                is_active=True
            )

            # Crisis intervention content
            if crisis_detected:
                crisis_content = self._get_crisis_intervention_content(
                    content_queryset, user, journal_entry, analysis_result
                )
                if crisis_content:
                    self.logger.warning(f"Crisis intervention content delivered to user {user.id}")
                    return crisis_content

            # High urgency content
            if urgency_score >= 5:
                urgent_content = self._get_urgent_support_content(
                    content_queryset, user, intervention_categories, analysis_result
                )
                if urgent_content:
                    return urgent_content

            # Moderate urgency content
            if urgency_score >= 2:
                contextual_content = self._get_contextual_support_content(
                    content_queryset, user, intervention_categories, analysis_result
                )
                return contextual_content

            # Low urgency - general wellness content
            return self._get_general_wellness_content(content_queryset, user, progress)

        except DATABASE_EXCEPTIONS as e:
            self.logger.error(f"Database error getting contextual content for user {user.id}: {e}", exc_info=True)
            return []
        except ObjectDoesNotExist as e:
            self.logger.warning(f"Content not found for user {user.id}: {e}")
            return []

    def _get_crisis_intervention_content(self, content_queryset, user, journal_entry, analysis_result):
        """Get immediate crisis intervention content"""

        crisis_content = content_queryset.filter(
            Q(delivery_context='mood_support') |
            Q(category='mental_health') |
            Q(tags__contains=['crisis', 'emergency', 'immediate'])
        ).filter(
            evidence_level__in=['who_cdc', 'peer_reviewed']  # Only high-evidence content for crisis
        ).order_by('-priority_score')[:2]

        # Log crisis content delivery for monitoring
        for content in crisis_content:
            WellnessContentInteraction.objects.create(
                user=user,
                content=content,
                interaction_type='viewed',
                delivery_context='mood_support',
                trigger_journal_entry=journal_entry,
                user_mood_at_delivery=journal_entry.mood_rating,
                user_stress_at_delivery=journal_entry.stress_level,
                metadata={
                    'crisis_intervention': True,
                    'urgency_score': analysis_result.get('urgency_score'),
                    'crisis_indicators': analysis_result.get('crisis_indicators', [])
                }
            )

        self.logger.critical(f"Crisis intervention content delivered: {[c.title for c in crisis_content]}")
        return list(crisis_content)

    def _get_urgent_support_content(self, content_queryset, user, intervention_categories, analysis_result):
        """Get urgent support content for high-stress situations"""

        # Map intervention categories to content filters
        category_filters = {
            'stress_management': Q(category='stress_management') | Q(delivery_context='stress_response'),
            'mood_crisis_support': Q(category='mental_health') | Q(delivery_context='mood_support'),
            'energy_management': Q(category='physical_wellness') | Q(delivery_context='energy_boost'),
            'equipment_stress_management': Q(category='workplace_health') | Q(tags__contains=['equipment']),
            'workplace_safety': Q(category='workplace_health') | Q(tags__contains=['safety'])
        }

        # Build filter based on intervention categories
        content_filter = Q()
        for category in intervention_categories:
            if category in category_filters:
                content_filter |= category_filters[category]

        if not content_filter:
            # Fallback to general stress management
            content_filter = Q(category='stress_management')

        urgent_content = content_queryset.filter(content_filter).filter(
            delivery_context__in=['stress_response', 'mood_support', 'energy_boost']
        ).order_by('-priority_score')[:3]

        self.logger.info(f"Urgent content selected for user {user.id}: {[c.title for c in urgent_content]}")
        return list(urgent_content)

    def _get_contextual_support_content(self, content_queryset, user, intervention_categories, analysis_result):
        """Get contextual support content for moderate urgency situations"""

        # Get user's content preferences
        try:
            progress = user.wellness_progress
            enabled_categories = progress.enabled_categories or []
            preferred_level = progress.preferred_content_level
        except WellnessUserProgress.DoesNotExist:
            enabled_categories = ['mental_health', 'stress_management', 'workplace_health']
            preferred_level = 'short_read'

        # Filter by user preferences and intervention needs
        content_filter = Q(category__in=enabled_categories)

        # Add intervention category filters
        if 'stress_management' in intervention_categories:
            content_filter |= Q(category='stress_management')
        if 'mood_crisis_support' in intervention_categories:
            content_filter |= Q(category='mental_health')

        contextual_content = content_queryset.filter(content_filter).filter(
            content_level=preferred_level,
            delivery_context='pattern_triggered'
        ).exclude(
            # Exclude recently viewed content
            id__in=self._get_recently_viewed_content_ids(user, days=7)
        ).order_by('-priority_score', '?')[:3]

        return list(contextual_content)

    def _get_general_wellness_content(self, content_queryset, user, progress):
        """Get general wellness content for routine delivery"""

        enabled_categories = progress.enabled_categories or ['mental_health', 'workplace_health']

        general_content = content_queryset.filter(
            category__in=enabled_categories,
            content_level=progress.preferred_content_level,
            delivery_context__in=['daily_tip', 'pattern_triggered']
        ).exclude(
            id__in=self._get_recently_viewed_content_ids(user, days=14)
        ).order_by('?')[:2]  # Random selection for variety

        return list(general_content)

    def _get_recently_viewed_content_ids(self, user, days=7):
        """Get IDs of content recently viewed by user"""
        recent_interactions = WellnessContentInteraction.objects.filter(
            user=user,
            interaction_date__gte=timezone.now() - timedelta(days=days)
        ).values_list('content_id', flat=True)

        return list(recent_interactions)


class ContextualContentEngine:
    """
    Context-aware content delivery engine

    Features:
    - Real-time context analysis
    - Emergency content delivery
    - Pattern-based content selection
    - User context integration
    - Effectiveness optimization
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_urgent_support_content(self, user, entry_analysis, user_context):
        """Get urgent support content for crisis situations"""
        intervention_categories = entry_analysis.get('intervention_categories', [])

        # Map to wellness content categories
        content_categories = []
        if 'mood_crisis_support' in intervention_categories:
            content_categories.extend(['mental_health'])
        if 'stress_management' in intervention_categories:
            content_categories.extend(['stress_management'])
        if 'crisis_intervention' in intervention_categories:
            content_categories.extend(['mental_health'])

        urgent_content = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            category__in=content_categories,
            delivery_context__in=['stress_response', 'mood_support'],
            evidence_level__in=['who_cdc', 'peer_reviewed']  # Only high-evidence for crisis
        ).order_by('-priority_score')[:2]

        return list(urgent_content)

    def get_follow_up_content(self, user, entry_analysis, user_context):
        """Get follow-up content for continued support"""
        urgency_level = entry_analysis.get('urgency_level', 'low')

        # Select appropriate categories based on urgency
        if urgency_level == 'high':
            categories = ['stress_management', 'mental_health']
        elif urgency_level == 'medium':
            categories = ['stress_management', 'workplace_health', 'mindfulness']
        else:
            categories = ['workplace_health', 'physical_wellness', 'mindfulness']

        follow_up_content = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True,
            category__in=categories,
            delivery_context='pattern_triggered'
        ).order_by('-priority_score', '?')[:3]

        return list(follow_up_content)


# Convenience functions for integration with other services

def trigger_pattern_analysis(journal_entry):
    """Trigger pattern analysis and content delivery"""
    try:
        from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer

        analyzer = JournalPatternAnalyzer()
        analysis = analyzer.analyze_entry_for_immediate_action(journal_entry)

        # Get contextual content if urgency warrants it
        if analysis['urgency_score'] >= 2:
            delivery_service = WellnessContentDeliveryService()
            contextual_content = delivery_service.get_contextual_content(
                journal_entry.user, journal_entry, analysis
            )

            logger.info(f"Delivered {len(contextual_content)} contextual content items to user {journal_entry.user.id}")

        return analysis

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error triggering pattern analysis: {e}", exc_info=True)
        return None
    except ObjectDoesNotExist as e:
        logger.warning(f"Pattern analysis data not found: {e}")
        return None
