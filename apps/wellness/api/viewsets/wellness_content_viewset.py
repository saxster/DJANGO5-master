"""
Wellness Content ViewSet for Mobile API

Provides wellness content endpoints:
- GET /wellness/content/daily-tip/ → daily_wellness_tip query
- GET /wellness/content/personalized/ → personalized_wellness_content query
- POST /wellness/content/track-interaction/ → TrackWellnessInteraction mutation

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError
import logging

from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.api.permissions import TenantIsolationPermission

logger = logging.getLogger('wellness_log')


class WellnessContentViewSet(viewsets.GenericViewSet):
    """
    Mobile API for wellness content delivery.

    Endpoints:
    - GET  /api/v1/wellness/content/daily-tip/        Daily wellness tip
    - GET  /api/v1/wellness/content/personalized/     Personalized content
    - POST /api/v1/wellness/content/track-interaction/ Track interaction
    """

    permission_classes = [IsAuthenticated]
    queryset = WellnessContent.objects.filter(is_active=True)

    @action(detail=False, methods=['get'], url_path='daily-tip')
    def daily_tip(self, request):
        """
        Get daily wellness tip.

        Replaces legacy query: daily_wellness_tip

        Query Params:
            preferred_category (str, optional): Preferred category

        Returns:
            Single wellness content item
        """
        try:
            preferred_category = request.query_params.get('preferred_category')

            # Get user's progress to avoid repeats
            from apps.wellness.models import WellnessUserProgress
            try:
                user_progress = WellnessUserProgress.objects.get(user=request.user)
                viewed_ids = WellnessContentInteraction.objects.filter(
                    user=request.user
                ).values_list('content_id', flat=True)
            except ObjectDoesNotExist:
                viewed_ids = []

            # Filter content
            queryset = WellnessContent.objects.filter(
                is_active=True,
                field_worker_relevant=True
            ).exclude(id__in=viewed_ids)

            if preferred_category:
                queryset = queryset.filter(category=preferred_category)

            # Get highest priority tip
            tip = queryset.order_by('-priority_score', '?').first()

            if not tip:
                # Fallback: get any active tip
                tip = WellnessContent.objects.filter(is_active=True).order_by('?').first()

            if tip:
                from apps.wellness.api.serializers import WellnessContentSerializer
                serializer = WellnessContentSerializer(tip)
                logger.info(f"Delivered daily tip {tip.id} to user {request.user.id}")
                return Response(serializer.data)

            return Response(
                {'message': 'No wellness tips available'},
                status=status.HTTP_404_NOT_FOUND
            )

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='personalized')
    def personalized(self, request):
        """
        Get personalized wellness content.

        Replaces legacy query: personalized_wellness_content

        Query Params:
            limit (int): Result limit (default: 5)
            categories (list): Categories to include
            exclude_viewed (bool): Exclude viewed content (default: true)

        Returns:
            List of personalized content recommendations
        """
        try:
            limit = int(request.query_params.get('limit', 5))
            categories = request.query_params.getlist('categories')
            exclude_viewed = request.query_params.get('exclude_viewed', 'true').lower() == 'true'

            # Get viewed content
            viewed_ids = []
            if exclude_viewed:
                viewed_ids = WellnessContentInteraction.objects.filter(
                    user=request.user
                ).values_list('content_id', flat=True)

            # Build queryset
            queryset = WellnessContent.objects.filter(
                is_active=True,
                field_worker_relevant=True
            ).exclude(id__in=viewed_ids)

            if categories:
                queryset = queryset.filter(category__in=categories)

            # Order by relevance score
            queryset = queryset.order_by('-priority_score')[:limit]

            from apps.wellness.api.serializers import WellnessContentSerializer
            serializer = WellnessContentSerializer(queryset, many=True)

            logger.info(f"Returned {len(serializer.data)} personalized content items")

            return Response(serializer.data)

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

    @action(detail=False, methods=['post'], url_path='track-interaction')
    def track_interaction(self, request):
        """
        Track user interaction with wellness content.

        Replaces legacy mutation handler: TrackWellnessInteraction

        Request:
            {
                "content_id": 123,
                "interaction_type": "viewed",
                "time_spent_seconds": 60,
                "user_rating": 4
            }

        Returns:
            {
                "success": true,
                "message": "Interaction tracked"
            }
        """
        try:
            content_id = request.data.get('content_id')
            interaction_type = request.data.get('interaction_type')

            # Validate required fields
            if not content_id or not interaction_type:
                return Response(
                    {'error': 'content_id and interaction_type are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get content
            content = WellnessContent.objects.get(id=content_id)

            # Create interaction record
            interaction = WellnessContentInteraction.objects.create(
                user=request.user,
                content=content,
                interaction_type=interaction_type,
                time_spent_seconds=request.data.get('time_spent_seconds', 0),
                user_rating=request.data.get('user_rating'),
                user_feedback=request.data.get('user_feedback', ''),
                action_taken=request.data.get('action_taken', False)
            )

            logger.info(
                f"Interaction tracked: user {request.user.id}, "
                f"content {content_id}, type {interaction_type}"
            )

            return Response({
                'success': True,
                'message': 'Interaction tracked successfully'
            })

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Content not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to track interaction'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


__all__ = ['WellnessContentViewSet']
