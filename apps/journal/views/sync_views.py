"""
Journal Sync Views

Mobile client sync with conflict resolution.
Refactored from views.py - business logic delegated to JournalSyncService.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.journal.serializers import (
    JournalSyncSerializer,
    JournalEntryDetailSerializer,
    JournalEntryCreateSerializer,
    JournalEntryUpdateSerializer
)
from apps.journal.services.journal_sync_service import JournalSyncService
from apps.journal.logging import get_journal_logger
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from .permissions import JournalPermission

logger = get_journal_logger(__name__)


class JournalSyncView(APIView):
    """
    Mobile client sync with conflict resolution

    Handles:
    - Bulk upload from mobile clients
    - Conflict resolution using version numbers
    - Differential sync based on timestamps
    - Media attachment sync coordination
    """

    permission_classes = [JournalPermission]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync_service = JournalSyncService()

    def post(self, request):
        """Sync journal entries from mobile client"""
        serializer = JournalSyncSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        sync_data = serializer.validated_data
        user = request.user

        try:
            sync_result = self._process_sync(user, sync_data)
            return Response(sync_result)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Sync failed for user {user.id}: {e}")
            return Response(
                {'error': 'Sync failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_sync(self, user, sync_data):
        """Process sync request using service"""
        serializers = {
            'detail': JournalEntryDetailSerializer,
            'create': JournalEntryCreateSerializer,
            'update': JournalEntryUpdateSerializer
        }

        return self.sync_service.process_sync_request(user, sync_data, serializers)
