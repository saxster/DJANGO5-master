"""
Progress Views - User wellness progress and gamification management

Provides:
- User wellness progress tracking
- Gamification metrics (streaks, points, achievements)
- User preference management
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.wellness.models import WellnessUserProgress
from apps.wellness.serializers import WellnessUserProgressSerializer
from apps.wellness.logging import get_wellness_logger
from .permissions import WellnessPermission

logger = get_wellness_logger(__name__)


class WellnessProgressView(APIView):
    """User wellness progress and gamification management"""

    permission_classes = [WellnessPermission]

    def get(self, request):
        """Get user's wellness progress"""
        try:
            progress = request.user.wellness_progress
            serializer = WellnessUserProgressSerializer(progress)
            return Response(serializer.data)
        except WellnessUserProgress.DoesNotExist:
            return Response(
                {'error': 'Wellness progress not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request):
        """Update user's wellness preferences"""
        try:
            progress = request.user.wellness_progress
        except WellnessUserProgress.DoesNotExist:
            progress = WellnessUserProgress.objects.create(
                user=request.user,
                tenant=getattr(request.user, 'tenant', None)
            )

        serializer = WellnessUserProgressSerializer(
            progress,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
