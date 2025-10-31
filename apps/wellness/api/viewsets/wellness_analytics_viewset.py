"""
Wellness Analytics ViewSet for Mobile API

Provides analytics and progress endpoints:
- GET /wellness/analytics/my-progress/ → my_wellness_progress query
- GET /wellness/analytics/wellbeing-analytics/ → my_wellbeing_analytics query

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
- Owner-only access
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
import logging

from apps.wellness.models import WellnessUserProgress

logger = logging.getLogger('wellness_log')


class WellnessAnalyticsViewSet(viewsets.GenericViewSet):
    """
    Mobile API for wellness analytics and progress.

    Endpoints:
    - GET /api/v1/wellness/analytics/my-progress/           User progress
    - GET /api/v1/wellness/analytics/wellbeing-analytics/   Wellbeing analytics
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='my-progress')
    def my_progress(self, request):
        """
        Get user's wellness progress.

        Replaces legacy query: my_wellness_progress

        Returns:
            User progress object
        """
        try:
            # Get or create progress
            progress, created = WellnessUserProgress.objects.get_or_create(
                user=request.user,
                defaults={
                    'current_streak': 0,
                    'longest_streak': 0,
                    'total_content_viewed': 0,
                    'total_content_completed': 0,
                    'total_score': 0
                }
            )

            from apps.wellness.api.serializers import WellnessUserProgressSerializer
            serializer = WellnessUserProgressSerializer(progress)

            logger.info(f"Retrieved progress for user {request.user.id}")

            return Response(serializer.data)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='wellbeing-analytics')
    def wellbeing_analytics(self, request):
        """
        Get wellbeing analytics from journal entries.

        Replaces legacy query: my_wellbeing_analytics

        Query Params:
            days (int): Number of days to analyze (default: 30)

        Returns:
            {
                "overall_score": <float>,
                "mood_trends": {...},
                "stress_analysis": {...},
                "energy_trends": {...},
                "recommendations": [...]
            }
        """
        try:
            days = int(request.query_params.get('days', 30))

            # Import analytics engine
            try:
                from apps.journal.ml.analytics_engine import WellbeingAnalyticsEngine
            except ImportError:
                logger.warning("Analytics engine not available")
                return Response({
                    'overall_score': 0.0,
                    'mood_trends': {},
                    'stress_analysis': {},
                    'energy_trends': {},
                    'recommendations': [],
                    'message': 'Analytics engine not available'
                })

            # Generate analytics
            engine = WellbeingAnalyticsEngine(user=request.user)
            analytics = engine.generate_analytics(days=days)

            logger.info(f"Generated analytics for user {request.user.id} ({days} days)")

            return Response(analytics)

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


__all__ = ['WellnessAnalyticsViewSet']
