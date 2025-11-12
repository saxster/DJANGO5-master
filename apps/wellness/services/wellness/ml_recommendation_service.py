"""
ML Recommendation Service - Generate ML-based content recommendations

Responsible for:
- Generating ML-based content recommendations
- Content-based filtering using user profiles
- Collaborative filtering patterns
- Coordinating with RecommendationScoringService for scoring
"""

from datetime import timedelta
from django.utils import timezone

from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.wellness.logging import get_wellness_logger
from .recommendation_scoring_service import RecommendationScoringService

logger = get_wellness_logger(__name__)


class MLRecommendationService:
    """Service for ML-based content recommendations"""

    @staticmethod
    def generate_ml_recommendations(user, user_profile, params):
        """
        Generate ML-based content recommendations

        Args:
            user: User object
            user_profile: dict from UserProfileService
            params: dict with limit, categories, exclude_viewed, diversity_enabled

        Returns:
            list: Recommendation dicts with content, score, effectiveness, reason
        """
        limit = params['limit']
        categories = params.get('categories', [])
        exclude_viewed = params.get('exclude_viewed', True)
        diversity_enabled = params.get('diversity_enabled', True)

        # Get filtered content
        queryset = MLRecommendationService._build_queryset(
            user, categories, exclude_viewed, user_profile
        )

        # Get content and generate scores
        content_items = list(queryset.order_by('-priority_score')[:limit * 2])
        recommendations = MLRecommendationService._score_recommendations(
            content_items, user_profile
        )

        # Sort by combined score
        recommendations.sort(key=lambda x: x['value_score'], reverse=True)

        # Apply diversity constraints if enabled
        if diversity_enabled:
            recommendations = RecommendationScoringService.apply_diversity_constraints(
                recommendations, limit
            )
        else:
            recommendations = recommendations[:limit]

        return recommendations

    @staticmethod
    def _build_queryset(user, categories, exclude_viewed, user_profile):
        """Build filtered queryset for content recommendations"""
        # Base queryset
        queryset = WellnessContent.objects.filter(
            tenant=getattr(user, 'tenant', None),
            is_active=True
        )

        # Apply category filter
        if categories:
            queryset = queryset.filter(category__in=categories)

        # Exclude recently viewed content
        if exclude_viewed:
            recent_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                interaction_date__gte=timezone.now() - timedelta(days=14)
            ).values_list('content_id', flat=True)

            queryset = queryset.exclude(id__in=recent_interactions)

        # Content-based filtering boost
        preferred_categories = user_profile.get('preferred_categories', [])
        if preferred_categories:
            queryset = queryset.extra(
                select={
                    'category_boost': f"CASE WHEN category IN {tuple(preferred_categories)} THEN 10 ELSE 0 END"
                }
            )

        return queryset

    @staticmethod
    def _score_recommendations(content_items, user_profile):
        """Score content items for recommendations"""
        recommendations = []

        for content in content_items:
            score = RecommendationScoringService.calculate_personalization_score(
                content, user_profile
            )
            effectiveness = RecommendationScoringService.predict_effectiveness(
                content, user_profile
            )
            reason = RecommendationScoringService.generate_recommendation_reason(
                content, user_profile
            )

            recommendations.append({
                'content': content,
                'score': score,
                'effectiveness': effectiveness,
                'value_score': (score + effectiveness) / 2,
                'reason': reason
            })

        return recommendations

    @staticmethod
    def calculate_diversity_score(recommendations):
        """Calculate diversity score of recommendations"""
        return RecommendationScoringService.calculate_diversity_score(recommendations)
