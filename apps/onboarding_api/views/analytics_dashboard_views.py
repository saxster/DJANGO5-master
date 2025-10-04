"""
Analytics Dashboard API Views

REST API endpoints for advanced analytics dashboard.

Following .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling

Author: Claude Code
Date: 2025-10-01
"""

import logging
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from apps.onboarding_api.services.analytics_dashboard import get_analytics_dashboard_service

logger = logging.getLogger(__name__)


class DashboardOverviewView(APIView):
    """
    GET /api/v1/onboarding/dashboard/overview/

    Comprehensive dashboard overview with all key metrics.

    Query Parameters:
        - client_id: Optional client filter
        - time_range_hours: Time range (default: 24)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get dashboard overview"""
        try:
            client_id = request.query_params.get('client_id')
            time_range_hours = int(request.query_params.get('time_range_hours', 24))

            dashboard_service = get_analytics_dashboard_service()
            overview = dashboard_service.get_dashboard_overview(
                client_id=int(client_id) if client_id else None,
                time_range_hours=time_range_hours
            )

            return Response(overview)

        except (ValueError, TypeError) as e:
            return Response(
                {'error': 'Invalid parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class DropOffHeatmapView(APIView):
    """
    GET /api/v1/onboarding/dashboard/heatmap/

    Drop-off heatmap visualization data.

    Query Parameters:
        - start_date: ISO datetime (default: 7 days ago)
        - end_date: ISO datetime (default: now)
        - granularity: 'hourly', 'daily', 'weekly' (default: 'daily')
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get heatmap data"""
        try:
            end_date = self._parse_date(
                request.query_params.get('end_date'),
                default=timezone.now()
            )
            start_date = self._parse_date(
                request.query_params.get('start_date'),
                default=end_date - timedelta(days=7)
            )
            granularity = request.query_params.get('granularity', 'daily')

            if granularity not in ['hourly', 'daily', 'weekly']:
                return Response(
                    {'error': 'Invalid granularity. Must be: hourly, daily, or weekly'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            dashboard_service = get_analytics_dashboard_service()
            heatmap_data = dashboard_service.get_drop_off_heatmap_data(
                start_date=start_date,
                end_date=end_date,
                granularity=granularity
            )

            return Response(heatmap_data)

        except ValidationError as e:
            return Response(
                {'error': 'Invalid date format', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _parse_date(self, date_string, default):
        """Parse date string"""
        if not date_string:
            return default
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))


class SessionReplayView(APIView):
    """
    GET /api/v1/onboarding/dashboard/session-replay/{session_id}/

    Session replay timeline for analysis.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Get session replay data"""
        try:
            dashboard_service = get_analytics_dashboard_service()
            replay_data = dashboard_service.get_session_replay_data(session_id)

            if 'error' in replay_data:
                return Response(
                    replay_data,
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(replay_data)

        except Exception as e:
            logger.error(f"Error getting session replay: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to load session replay'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CohortTrendsView(APIView):
    """
    GET /api/v1/onboarding/dashboard/cohort-trends/

    Cohort trend analysis over time.

    Query Parameters:
        - start_date: ISO datetime (default: 30 days ago)
        - end_date: ISO datetime (default: now)
        - cohort_type: 'daily', 'weekly', 'monthly' (default: 'weekly')
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get cohort trends"""
        try:
            end_date = self._parse_date(
                request.query_params.get('end_date'),
                default=timezone.now()
            )
            start_date = self._parse_date(
                request.query_params.get('start_date'),
                default=end_date - timedelta(days=30)
            )
            cohort_type = request.query_params.get('cohort_type', 'weekly')

            if cohort_type not in ['daily', 'weekly', 'monthly']:
                return Response(
                    {'error': 'Invalid cohort_type. Must be: daily, weekly, or monthly'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            dashboard_service = get_analytics_dashboard_service()
            trends = dashboard_service.get_cohort_trends(
                start_date=start_date,
                end_date=end_date,
                cohort_type=cohort_type
            )

            return Response(trends)

        except ValidationError as e:
            return Response(
                {'error': 'Invalid date format', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _parse_date(self, date_string, default):
        """Parse date string"""
        if not date_string:
            return default
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))


__all__ = [
    'DashboardOverviewView',
    'DropOffHeatmapView',
    'SessionReplayView',
    'CohortTrendsView',
]
