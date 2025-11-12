"""
Analytics Views - Wellness system analytics and insights

Provides:
- Wellness engagement analytics
- Content effectiveness metrics
- User preference trends
- Recommendation insights
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

from apps.wellness.services.wellness import AnalyticsService
from apps.wellness.logging import get_wellness_logger
from .permissions import WellnessPermission

logger = get_wellness_logger(__name__)


class WellnessAnalyticsView(APIView):
    """Wellness system analytics and insights"""

    permission_classes = [WellnessPermission]

    def get(self, request):
        """Get wellness engagement analytics"""
        user = request.user
        days = int(request.query_params.get('days', 30))

        try:
            analytics = AnalyticsService.generate_wellness_analytics(user, days)
            return Response(analytics)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Wellness analytics generation failed for user {user.id}: {e}")
            return Response(
                {'error': 'Analytics generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
