"""
Journal Analytics Views

Comprehensive wellbeing analytics with ML-powered insights.
Refactored from views.py - business logic delegated to JournalAnalyticsService.
"""

from typing import Optional
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.journal.logging import get_journal_logger
from apps.journal.serializers import JournalAnalyticsSerializer
from apps.journal.services import JournalAnalyticsService
from .permissions import JournalPermission

logger = get_journal_logger(__name__)


class JournalAnalyticsView(APIView):
    """
    Comprehensive wellbeing analytics with ML-powered insights

    Implements ALL algorithms moved from Kotlin:
    - Mood trend analysis with variability calculation
    - Stress pattern recognition and trigger analysis
    - Energy correlation with work patterns
    - Positive psychology engagement measurement
    - Predictive modeling for intervention timing
    - Personalized recommendation generation
    """

    permission_classes = [JournalPermission]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.analytics_service = JournalAnalyticsService()
        self.user_model = get_user_model()

    def get(self, request):
        """Generate comprehensive wellbeing analytics"""
        requested_user_id = request.query_params.get('user_id')
        days = int(request.query_params.get('days', 30))

        target_user = self._resolve_target_user(request.user, requested_user_id)

        # Verify user can access analytics
        if target_user != request.user and not request.user.is_superuser:
            raise PermissionDenied("Cannot access analytics for other users")

        try:
            analytics = self.analytics_service.generate_comprehensive_analytics(target_user, days=days)
            return self._validate_and_respond(analytics)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Analytics generation failed for user {target_user.id}: {e}")
            return Response(
                {'error': 'Analytics generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _resolve_target_user(self, requester, requested_user_id: Optional[str]):
        if not requested_user_id or str(requested_user_id) == str(requester.id):
            return requester

        if not requester.is_superuser:
            raise PermissionDenied("Cannot access analytics for other users")

        try:
            return self.user_model.objects.get(pk=requested_user_id)
        except self.user_model.DoesNotExist as exc:
            raise PermissionDenied("Requested user does not exist") from exc

    def _validate_and_respond(self, analytics):
        """Validate analytics and return response"""
        serializer = JournalAnalyticsSerializer(data=analytics)
        if serializer.is_valid():
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Analytics serialization failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
