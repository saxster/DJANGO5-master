"""
Journal Search Views

Advanced search with privacy filtering.
Refactored from views.py - business logic delegated to JournalSearchService.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.journal.serializers import JournalSearchSerializer, JournalEntryListSerializer
from apps.journal.services.journal_search_service import JournalSearchService
from apps.journal.logging import get_journal_logger
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from .permissions import JournalPermission

logger = get_journal_logger(__name__)


class JournalSearchView(APIView):
    """
    Advanced search with Elasticsearch integration and privacy filtering

    Implements:
    - Full-text search with highlighting
    - Privacy-compliant result filtering
    - Faceted search with aggregations
    - Search analytics and personalization
    """

    permission_classes = [JournalPermission]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_service = JournalSearchService()

    def post(self, request):
        """Execute advanced journal search with privacy filtering"""
        serializer = JournalSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        search_params = serializer.validated_data
        user = request.user

        try:
            results = self._execute_search(user, search_params)
            self.search_service.track_search_interaction(user, search_params)
            return Response(results)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Search failed for user {user.id}: {e}")
            return Response(
                {'error': 'Search failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _execute_search(self, user, search_params):
        """Execute search using service"""
        # TODO: Replace with Elasticsearch implementation
        return self.search_service.execute_database_search(
            user,
            search_params,
            JournalEntryListSerializer
        )
