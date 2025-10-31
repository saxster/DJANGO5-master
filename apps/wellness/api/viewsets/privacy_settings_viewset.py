"""
Privacy Settings ViewSet for Mobile API

Provides privacy settings endpoints:
- GET /wellness/privacy/settings/ → my_privacy_settings query
- PATCH /wellness/privacy/settings/ → UpdatePrivacySettings mutation

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
from django.core.exceptions import ValidationError, ObjectDoesNotExist
import logging

logger = logging.getLogger('wellness_log')


class PrivacySettingsViewSet(viewsets.GenericViewSet):
    """
    Mobile API for journal privacy settings.

    Endpoints:
    - GET   /api/v1/wellness/privacy/settings/   Get privacy settings
    - PATCH /api/v1/wellness/privacy/settings/   Update privacy settings
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='settings')
    def get_settings(self, request):
        """
        Get user's privacy settings.

        Replaces legacy query: my_privacy_settings

        Returns:
            Privacy settings object
        """
        try:
            from apps.journal.models import JournalPrivacySettings

            # Get or create privacy settings
            settings, created = JournalPrivacySettings.objects.get_or_create(
                user=request.user,
                defaults={
                    'analytics_consent': True,
                    'pattern_analysis_consent': True,
                    'crisis_intervention_enabled': True
                }
            )

            from apps.wellness.api.serializers import PrivacySettingsSerializer
            serializer = PrivacySettingsSerializer(settings)

            logger.info(f"Retrieved privacy settings for user {request.user.id}")

            return Response(serializer.data)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['patch'], url_path='settings')
    def update_settings(self, request):
        """
        Update user's privacy settings.

        Replaces legacy mutation handler: UpdatePrivacySettings

        Request:
            {
                "analytics_consent": true,
                "pattern_analysis_consent": false,
                "crisis_intervention_enabled": true
            }

        Returns:
            Updated privacy settings
        """
        try:
            from apps.journal.models import JournalPrivacySettings

            # Get or create settings
            settings, created = JournalPrivacySettings.objects.get_or_create(
                user=request.user
            )

            from apps.wellness.api.serializers import PrivacySettingsSerializer
            serializer = PrivacySettingsSerializer(
                settings,
                data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            logger.info(f"Updated privacy settings for user {request.user.id}")

            return Response(serializer.data)

        except ValidationError as ve:
            logger.error(f"Validation error: {ve}", exc_info=True)
            return Response(
                {'error': str(ve)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Database operation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


__all__ = ['PrivacySettingsViewSet']
