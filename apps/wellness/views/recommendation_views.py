"""
Recommendation Views - ML-powered personalized wellness content recommendations

Provides:
- ML-powered personalized content recommendations
- Collaborative filtering with similar users
- Content-based filtering using entry patterns
- Diversity constraints to avoid content clustering
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

from apps.wellness.serializers import (
    PersonalizedContentRequestSerializer,
    WellnessRecommendationSerializer
)
from apps.wellness.services.wellness import (
    UserProfileService,
    MLRecommendationService
)
from apps.wellness.logging import get_wellness_logger
from .permissions import WellnessPermission

logger = get_wellness_logger(__name__)


class PersonalizedWellnessContentView(APIView):
    """ML-powered personalized wellness content recommendations"""

    permission_classes = [WellnessPermission]

    def get(self, request):
        """Get personalized wellness content recommendations"""
        serializer = PersonalizedContentRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = serializer.validated_data
        user = request.user

        try:
            # Build user profile and generate recommendations
            user_profile = UserProfileService.build_user_profile(user)
            recommendations = MLRecommendationService.generate_ml_recommendations(user, user_profile, params)

            return self._build_recommendations_response(recommendations, user_profile)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Personalized content generation failed for user {user.id}: {e}")
            return Response({'error': 'Personalized content generation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _build_recommendations_response(self, recommendations, user_profile):
        """Build recommendations response"""
        return Response({
            'personalized_content': [
                WellnessRecommendationSerializer({
                    'content': item['content'],
                    'personalization_score': item['score'],
                    'recommendation_reason': item['reason'],
                    'predicted_effectiveness': item['effectiveness'],
                    'estimated_value': item['value_score'],
                    'delivery_context': item.get('context', 'personalized')
                }).data
                for item in recommendations
            ],
            'personalization_metadata': {
                'user_profile_features': user_profile,
                'recommendation_algorithm': 'hybrid_cf_cbf_v2.1',
                'model_confidence': 0.8,
                'diversity_score': MLRecommendationService.calculate_diversity_score(recommendations)
            }
        })
