"""
HelpBot Analytics Views

Handles analytics and reporting data.
Fixed deep nesting issues (8 levels → 3 levels max).
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.helpbot.services import HelpBotAnalyticsService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class HelpBotAnalyticsView(APIView):
    """HelpBot analytics and reporting."""

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.analytics_service = HelpBotAnalyticsService()

    def get(self, request):
        """Get HelpBot analytics data."""
        try:
            # Guard clause: Check permissions first
            if not self._has_analytics_permission(request.user):
                return Response(
                    {'error': 'Permission denied. Admin access required.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            analytics_type = request.query_params.get('type', 'dashboard')
            days = min(int(request.query_params.get('days', 30)), 365)

            # Route to appropriate handler (flattened logic)
            if analytics_type == 'dashboard':
                return self._get_dashboard_data(days)
            elif analytics_type == 'insights':
                return self._get_insights(days)
            elif analytics_type == 'user':
                return self._get_user_analytics(request, days)
            else:
                return Response(
                    {'error': 'Invalid analytics type. Use: dashboard, insights, or user'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in HelpBot analytics view: {e}", exc_info=True)
            return Response(
                {'error': 'Could not get analytics data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _has_analytics_permission(self, user):
        """Check if user has permission for analytics."""
        return user.is_staff or getattr(user, 'isadmin', False)

    def _get_dashboard_data(self, days):
        """Get dashboard analytics."""
        data = self.analytics_service.get_dashboard_data(days)
        return Response(data)

    def _get_insights(self, days):
        """Get analytics insights."""
        insights = self.analytics_service.generate_insights(days)
        return Response({'insights': insights})

    def _get_user_analytics(self, request, days):
        """Get user-specific analytics."""
        # Guard clause: Non-superusers can only see their own data
        if not request.user.is_superuser:
            return self._get_own_analytics(request.user, days)

        # Superusers can view any user's analytics
        user_id = request.query_params.get('user_id')

        if not user_id:
            return self._get_own_analytics(request.user, days)

        # Get target user analytics
        target_user = self._get_user_by_id(user_id)

        if not target_user:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        user_analytics = self.analytics_service.get_user_analytics(target_user, days)
        return Response(user_analytics)

    def _get_own_analytics(self, user, days):
        """Get analytics for the requesting user."""
        user_analytics = self.analytics_service.get_user_analytics(user, days)
        return Response(user_analytics)

    def _get_user_by_id(self, user_id):
        """Get user by ID."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
