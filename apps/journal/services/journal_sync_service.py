"""
Journal Sync Service

Handles mobile client synchronization logic.
Extracted from views.py to separate sync concerns.
"""

from django.utils import timezone
from django.db.models import ObjectDoesNotExist
from apps.journal.logging import get_journal_logger
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = get_journal_logger(__name__)


class JournalSyncService:
    """Service for mobile client synchronization"""

    def process_sync_request(self, user, sync_data, serializers):
        """
        Process mobile client sync request

        Args:
            user: User object
            sync_data: Validated sync data
            serializers: Dict with serializer classes

        Returns:
            dict: Sync result with created/updated/conflict entries
        """
        entries_data = sync_data['entries']
        last_sync = sync_data.get('last_sync_timestamp')

        created_entries = []
        updated_entries = []
        conflicts = []

        for entry_data in entries_data:
            mobile_id = entry_data.get('mobile_id')

            try:
                result = self._sync_single_entry(user, mobile_id, entry_data, serializers)

                if result['status'] == 'created':
                    created_entries.append(result['entry'])
                elif result['status'] == 'updated':
                    updated_entries.append(result['entry'])
                else:
                    conflicts.append(result)

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Failed to sync entry with mobile_id {mobile_id}: {e}")
                conflicts.append({
                    'mobile_id': mobile_id,
                    'error': str(e),
                    'entry_data': entry_data
                })

        # Get server-side changes since last sync
        server_changes = self._get_server_changes(user, last_sync)

        return {
            'sync_timestamp': timezone.now().isoformat(),
            'created_count': len(created_entries),
            'updated_count': len(updated_entries),
            'conflict_count': len(conflicts),
            'created_entries': self._serialize_entries(created_entries, serializers['detail']),
            'updated_entries': self._serialize_entries(updated_entries, serializers['detail']),
            'conflicts': conflicts,
            'server_changes': server_changes
        }

    def _sync_single_entry(self, user, mobile_id, entry_data, serializers):
        """
        Sync a single entry (create or update)

        Args:
            user: User object
            mobile_id: Mobile client ID
            entry_data: Entry data from mobile
            serializers: Dict with serializer classes

        Returns:
            dict: Result with status and entry
        """
        from apps.journal.models import JournalEntry

        existing_entry = JournalEntry.objects.filter(
            mobile_id=mobile_id,
            user=user
        ).first()

        if existing_entry:
            return self._handle_entry_update(existing_entry, entry_data, serializers)
        else:
            new_entry = self._create_entry_from_sync(user, entry_data, serializers['create'])
            return {
                'status': 'created',
                'entry': new_entry
            }

    def _handle_entry_update(self, existing_entry, entry_data, serializers):
        """
        Handle entry update with conflict resolution

        Args:
            existing_entry: Existing JournalEntry
            entry_data: Data from mobile client
            serializers: Dict with serializer classes

        Returns:
            dict: Update result
        """
        client_version = entry_data.get('version', 1)

        if client_version <= existing_entry.version:
            # Client is behind server, conflict
            return {
                'status': 'conflict',
                'mobile_id': entry_data.get('mobile_id'),
                'client_version': client_version,
                'server_version': existing_entry.version,
                'server_entry': serializers['detail'](existing_entry).data
            }

        # Client is ahead, update server
        serializer = serializers['update'](
            existing_entry,
            data=entry_data,
            partial=True
        )

        if serializer.is_valid():
            updated_entry = serializer.save()
            return {
                'status': 'updated',
                'entry': updated_entry
            }
        else:
            return {
                'status': 'error',
                'mobile_id': entry_data.get('mobile_id'),
                'errors': serializer.errors
            }

    def _create_entry_from_sync(self, user, entry_data, create_serializer):
        """
        Create new journal entry from sync data

        Args:
            user: User object
            entry_data: Entry data from mobile
            create_serializer: CreateSerializer class

        Returns:
            JournalEntry: Created entry
        """
        serializer = create_serializer(
            data=entry_data,
            context={'request': type('MockRequest', (), {'user': user})()}
        )

        if serializer.is_valid():
            entry = serializer.save()
            entry.sync_status = 'synced'
            entry.last_sync_timestamp = timezone.now()
            entry.save()
            return entry
        else:
            raise ValueError(f"Invalid entry data: {serializer.errors}")

    def _get_server_changes(self, user, last_sync):
        """
        Get server-side changes since last sync

        Args:
            user: User object
            last_sync: Last sync timestamp

        Returns:
            list: Server changes
        """
        if not last_sync:
            return []

        from apps.journal.models import JournalEntry

        return list(JournalEntry.objects.filter(
            user=user,
            updated_at__gt=last_sync,
            is_deleted=False
        ).values())

    def _serialize_entries(self, entries, serializer_class):
        """
        Serialize list of entries

        Args:
            entries: List of JournalEntry objects
            serializer_class: Serializer class

        Returns:
            list: Serialized data
        """
        return [serializer_class(e).data for e in entries]
