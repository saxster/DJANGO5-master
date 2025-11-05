"""
Journal Privacy Settings Views

Manage user privacy settings for journal data.
Refactored from views.py - simple CRUD operations.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from apps.journal.models import JournalPrivacySettings
from apps.journal.serializers import JournalPrivacySettingsSerializer
from apps.journal.logging import get_journal_logger
from .permissions import JournalPermission

logger = get_journal_logger(__name__)


class JournalPrivacySettingsView(APIView):
    """Manage user privacy settings for journal data"""

    permission_classes = [JournalPermission]

    def get(self, request):
        """Get user's privacy settings"""
        try:
            settings = request.user.journal_privacy_settings
            serializer = JournalPrivacySettingsSerializer(settings)
            return Response(serializer.data)
        except JournalPrivacySettings.DoesNotExist:
            return Response(
                {'error': 'Privacy settings not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request):
        """Update user's privacy settings"""
        settings = self._get_or_create_settings(request.user)
        serializer = JournalPrivacySettingsSerializer(settings, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _get_or_create_settings(self, user):
        """Get existing settings or create new ones"""
        try:
            return user.journal_privacy_settings
        except JournalPrivacySettings.DoesNotExist:
            return JournalPrivacySettings.objects.create(
                user=user,
                consent_timestamp=timezone.now()
            )
