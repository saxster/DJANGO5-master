"""
Performance Analytics REST API Views.

REST API endpoints for worker and team performance analytics:
- GET /api/performance/me/ - Worker performance dashboard
- GET /api/performance/me/trends/ - Worker trends over time
- GET /api/performance/me/achievements/ - Worker achievements
- GET /api/performance/team/<site_id>/ - Team performance dashboard
- GET /api/performance/coaching-queue/<site_id>/ - Coaching opportunities
- GET /api/performance/top-performers/<site_id>/ - Top performers
- POST /api/performance/kudos/ - Create kudos
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from apps.ontology.decorators import ontology
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.performance_analytics.services.worker_analytics_service import WorkerAnalyticsService
from apps.performance_analytics.services.team_analytics_service import TeamAnalyticsService
from apps.performance_analytics.models import (
    WorkerAchievement,
    Kudos,
)
from .serializers import (
    WorkerAchievementSerializer,
    KudosSerializer,
)
from .permissions import IsSupervisorOrAdmin

__all__ = [
    'WorkerPerformanceView',
    'WorkerTrendsView',
    'WorkerAchievementsView',
    'TeamPerformanceView',
    'CoachingQueueView',
    'TopPerformersView',
    'KudosCreateView',
]

logger = logging.getLogger('performance_analytics.api')


@ontology(
    domain="performance_analytics",
    purpose="Worker performance dashboard - Returns worker's personal performance metrics and insights",
    api_endpoint=True,
    http_methods=["GET"],
    authentication_required=True,
    permissions=["IsAuthenticated"],
    rate_limit="60/minute",
    response_schema="WorkerDashboardResponse",
    error_codes=[401, 404, 500],
    criticality="medium",
    tags=["api", "rest", "performance", "analytics", "worker", "dashboard"],
)
class WorkerPerformanceView(APIView):
    """Worker performance dashboard API endpoint."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = int(request.query_params.get('days', 30))
            dashboard_data = WorkerAnalyticsService.get_worker_dashboard(request.user, days)

            return Response({
                'success': True,
                'data': dashboard_data
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist as e:
            logger.warning(f"Worker not found: {e}")
            return Response({
                'success': False,
                'error': 'Worker data not found'
            }, status=status.HTTP_404_NOT_FOUND)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error fetching worker dashboard: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to fetch dashboard data'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ValueError as e:
            logger.warning(f"Invalid days parameter: {e}")
            return Response({
                'success': False,
                'error': 'Invalid days parameter'
            }, status=status.HTTP_400_BAD_REQUEST)


@ontology(
    domain="performance_analytics",
    purpose="Worker trends over time - Returns time-series performance data for visualization",
    api_endpoint=True,
    http_methods=["GET"],
    authentication_required=True,
    permissions=["IsAuthenticated"],
    rate_limit="60/minute",
    response_schema="WorkerTrendsResponse",
    error_codes=[400, 401, 500],
    criticality="medium",
    tags=["api", "rest", "performance", "analytics", "trends", "time-series"],
)
class WorkerTrendsView(APIView):
    """Worker performance trends API endpoint."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = int(request.query_params.get('days', 90))
            trends_data = WorkerAnalyticsService.get_worker_trends(request.user, days)

            return Response({
                'success': True,
                'data': trends_data
            }, status=status.HTTP_200_OK)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error fetching worker trends: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to fetch trends data'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ValueError as e:
            logger.warning(f"Invalid days parameter: {e}")
            return Response({
                'success': False,
                'error': 'Invalid days parameter'
            }, status=status.HTTP_400_BAD_REQUEST)


@ontology(
    domain="performance_analytics",
    purpose="Worker achievements - Returns all achievements earned by worker",
    api_endpoint=True,
    http_methods=["GET"],
    authentication_required=True,
    permissions=["IsAuthenticated"],
    rate_limit="60/minute",
    response_schema="WorkerAchievementSerializer",
    error_codes=[401, 500],
    criticality="low",
    tags=["api", "rest", "performance", "gamification", "achievements"],
)
class WorkerAchievementsView(APIView):
    """Worker achievements API endpoint."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            achievements = WorkerAchievement.objects.filter(
                worker=request.user
            ).select_related('achievement').order_by('-earned_at')

            serializer = WorkerAchievementSerializer(achievements, many=True)

            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error fetching achievements: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to fetch achievements'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@ontology(
    domain="performance_analytics",
    purpose="Team performance dashboard - Returns team-level metrics for supervisors/managers",
    api_endpoint=True,
    http_methods=["GET"],
    authentication_required=True,
    permissions=["IsSupervisorOrAdmin"],
    rate_limit="60/minute",
    response_schema="TeamDashboardResponse",
    error_codes=[401, 403, 404, 500],
    criticality="high",
    tags=["api", "rest", "performance", "analytics", "team", "supervisor"],
)
class TeamPerformanceView(APIView):
    """Team performance dashboard API endpoint."""

    permission_classes = [IsSupervisorOrAdmin]

    def get(self, request, site_id):
        try:
            days = int(request.query_params.get('days', 30))
            dashboard_data = TeamAnalyticsService.get_team_dashboard(site_id, days)

            return Response({
                'success': True,
                'data': dashboard_data
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist as e:
            logger.warning(f"Site not found: {e}")
            return Response({
                'success': False,
                'error': 'Site not found'
            }, status=status.HTTP_404_NOT_FOUND)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error fetching team dashboard: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to fetch team dashboard'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ValueError as e:
            logger.warning(f"Invalid days parameter: {e}")
            return Response({
                'success': False,
                'error': 'Invalid days parameter'
            }, status=status.HTTP_400_BAD_REQUEST)


@ontology(
    domain="performance_analytics",
    purpose="Coaching queue - Returns workers needing coaching intervention based on performance",
    api_endpoint=True,
    http_methods=["GET"],
    authentication_required=True,
    permissions=["IsSupervisorOrAdmin"],
    rate_limit="60/minute",
    response_schema="CoachingQueueResponse",
    error_codes=[401, 403, 500],
    criticality="high",
    tags=["api", "rest", "performance", "coaching", "supervisor"],
)
class CoachingQueueView(APIView):
    """Coaching queue API endpoint."""

    permission_classes = [IsSupervisorOrAdmin]

    def get(self, request, site_id):
        try:
            priority = request.query_params.get('priority', 'high')
            coaching_queue = TeamAnalyticsService.identify_coaching_opportunities(
                site_id, 
                priority=priority
            )

            return Response({
                'success': True,
                'data': coaching_queue
            }, status=status.HTTP_200_OK)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error fetching coaching queue: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to fetch coaching queue'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ValueError as e:
            logger.warning(f"Invalid priority parameter: {e}")
            return Response({
                'success': False,
                'error': 'Invalid priority parameter'
            }, status=status.HTTP_400_BAD_REQUEST)


@ontology(
    domain="performance_analytics",
    purpose="Top performers - Returns top performing workers for a site",
    api_endpoint=True,
    http_methods=["GET"],
    authentication_required=True,
    permissions=["IsSupervisorOrAdmin"],
    rate_limit="60/minute",
    response_schema="TopPerformersResponse",
    error_codes=[401, 403, 500],
    criticality="medium",
    tags=["api", "rest", "performance", "leaderboard", "recognition"],
)
class TopPerformersView(APIView):
    """Top performers API endpoint."""

    permission_classes = [IsSupervisorOrAdmin]

    def get(self, request, site_id):
        try:
            limit = int(request.query_params.get('limit', 5))
            metric = request.query_params.get('metric', 'bpi')

            top_performers = TeamAnalyticsService.get_top_performers(
                site_id, 
                limit=limit,
                metric=metric
            )

            return Response({
                'success': True,
                'data': top_performers
            }, status=status.HTTP_200_OK)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error fetching top performers: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to fetch top performers'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ValueError as e:
            logger.warning(f"Invalid parameters: {e}")
            return Response({
                'success': False,
                'error': 'Invalid parameters'
            }, status=status.HTTP_400_BAD_REQUEST)


@ontology(
    domain="performance_analytics",
    purpose="Create kudos - Post recognition/kudos for worker performance",
    api_endpoint=True,
    http_methods=["POST"],
    authentication_required=True,
    permissions=["IsAuthenticated"],
    rate_limit="30/minute",
    request_schema="KudosSerializer",
    response_schema="KudosSerializer",
    error_codes=[400, 401, 404, 500],
    criticality="low",
    tags=["api", "rest", "performance", "gamification", "kudos", "recognition"],
)
class KudosCreateView(APIView):
    """Create kudos API endpoint."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serializer = KudosSerializer(data=request.data, context={'request': request})

            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            kudos = serializer.save()

            return Response({
                'success': True,
                'data': KudosSerializer(kudos).data,
                'message': 'Kudos sent successfully'
            }, status=status.HTTP_201_CREATED)

        except ObjectDoesNotExist as e:
            logger.warning(f"Recipient not found: {e}")
            return Response({
                'success': False,
                'error': 'Recipient not found'
            }, status=status.HTTP_404_NOT_FOUND)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error creating kudos: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Failed to create kudos'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
