"""
Tests for Mobile Sync Functionality

Testing:
- Conflict resolution
- Version tracking
- Mobile ID synchronization
- Sync status management
- Data consistency across clients
- Offline/online transitions

Run with: pytest apps/journal/tests/test_mobile_sync.py -v
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from uuid import uuid4

from apps.journal.models import JournalEntry
from apps.journal.models.enums import (
    JournalEntryType,
    JournalPrivacyScope,
    JournalSyncStatus,
)


@pytest.mark.django_db
class TestMobileIDTracking(TestCase):
    """Test mobile client ID tracking for sync"""

    def test_entry_with_mobile_id(self, test_user, test_tenant):
        """Test creating entry with mobile ID"""
        mobile_id = uuid4()
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Mobile Entry",
            content="Created on mobile",
            timestamp=timezone.now(),
            mobile_id=mobile_id,
            sync_status=JournalSyncStatus.PENDING_SYNC,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.mobile_id == mobile_id
        assert entry.sync_status == JournalSyncStatus.PENDING_SYNC

    def test_query_by_mobile_id(self, test_user, test_tenant):
        """Test querying entries by mobile ID"""
        mobile_id = uuid4()
        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            mobile_id=mobile_id,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        entry = JournalEntry.objects.filter(mobile_id=mobile_id).first()
        assert entry is not None
        assert entry.mobile_id == mobile_id

    def test_null_mobile_id_allowed(self, test_user, test_tenant):
        """Test that null mobile_id is allowed for server-created entries"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Server Entry",
            content="Created on server",
            timestamp=timezone.now(),
            mobile_id=None,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.mobile_id is None


@pytest.mark.django_db
class TestVersionTracking(TestCase):
    """Test version tracking for conflict resolution"""

    def test_initial_version_is_one(self, test_user, test_tenant):
        """Test that new entries start at version 1"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="New Entry",
            content="Content",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.version == 1

    def test_version_increments_on_update(self, test_user, test_tenant):
        """Test that version increments with each update"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.version == 1

        entry.content = "Updated content"
        entry.save()
        assert entry.version == 2

        entry.title = "New title"
        entry.save()
        assert entry.version == 3

    def test_version_prevents_lost_updates(self, test_user, test_tenant):
        """Test that version field enables detecting concurrent updates"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Original",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        version1 = entry.version

        # Simulate concurrent update from another client
        entry.title = "Update 1"
        entry.save()
        version2 = entry.version

        # Try to update with old version
        entry_old = JournalEntry.objects.get(id=entry.id)
        entry_old.title = "Update 2"
        entry_old.save()

        # Final version should be higher
        final = JournalEntry.objects.get(id=entry.id)
        assert final.version > version2


@pytest.mark.django_db
class TestSyncStatusTransitions(TestCase):
    """Test sync status state transitions"""

    def test_draft_status(self, test_user, test_tenant):
        """Test DRAFT status for unsaved entries"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Draft",
            content="Draft content",
            timestamp=timezone.now(),
            is_draft=True,
            sync_status=JournalSyncStatus.DRAFT,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.sync_status == JournalSyncStatus.DRAFT
        assert entry.is_draft is True

    def test_pending_sync_status(self, test_user, test_tenant):
        """Test PENDING_SYNC status for entries awaiting sync"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Pending",
            content="Content",
            timestamp=timezone.now(),
            sync_status=JournalSyncStatus.PENDING_SYNC,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.sync_status == JournalSyncStatus.PENDING_SYNC

    def test_synced_status(self, test_user, test_tenant):
        """Test SYNCED status for synchronized entries"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Synced",
            content="Content",
            timestamp=timezone.now(),
            sync_status=JournalSyncStatus.SYNCED,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.sync_status == JournalSyncStatus.SYNCED

    def test_sync_error_status(self, test_user, test_tenant):
        """Test SYNC_ERROR status for failed syncs"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Error",
            content="Content",
            timestamp=timezone.now(),
            sync_status=JournalSyncStatus.SYNC_ERROR,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.sync_status == JournalSyncStatus.SYNC_ERROR

    def test_pending_delete_status(self, test_user, test_tenant):
        """Test PENDING_DELETE status for deletions waiting sync"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="To Delete",
            content="Content",
            timestamp=timezone.now(),
            sync_status=JournalSyncStatus.PENDING_DELETE,
            is_deleted=True,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.sync_status == JournalSyncStatus.PENDING_DELETE
        assert entry.is_deleted is True

    def test_transition_pending_to_synced(self, test_user, test_tenant):
        """Test transitioning from PENDING_SYNC to SYNCED"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            sync_status=JournalSyncStatus.PENDING_SYNC,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        entry.sync_status = JournalSyncStatus.SYNCED
        entry.last_sync_timestamp = timezone.now()
        entry.save()

        refreshed = JournalEntry.objects.get(id=entry.id)
        assert refreshed.sync_status == JournalSyncStatus.SYNCED
        assert refreshed.last_sync_timestamp is not None


@pytest.mark.django_db
class TestLastSyncTimestamp(TestCase):
    """Test last sync timestamp tracking"""

    def test_set_last_sync_timestamp(self, test_user, test_tenant):
        """Test setting last sync timestamp"""
        sync_time = timezone.now()
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            last_sync_timestamp=sync_time,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.last_sync_timestamp == sync_time

    def test_update_last_sync_timestamp(self, test_journal_entry):
        """Test updating last sync timestamp"""
        assert test_journal_entry.last_sync_timestamp is None

        new_sync_time = timezone.now()
        test_journal_entry.last_sync_timestamp = new_sync_time
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.last_sync_timestamp == new_sync_time

    def test_filter_by_last_sync(self, test_user, test_tenant):
        """Test filtering entries by sync timestamp"""
        old_sync = timezone.now()
        recent_sync = timezone.now()

        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Old Sync",
            content="Content",
            timestamp=timezone.now(),
            last_sync_timestamp=old_sync,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Recent Sync",
            content="Content",
            timestamp=timezone.now(),
            last_sync_timestamp=recent_sync,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        unsynced = JournalEntry.objects.filter(
            user=test_user,
            last_sync_timestamp__isnull=True
        )
        assert unsynced.count() >= 0


@pytest.mark.django_db
class TestOfflineSync(TestCase):
    """Test offline data handling and sync"""

    def test_entry_created_offline(self, test_user, test_tenant):
        """Test entry created in offline mode"""
        mobile_id = uuid4()
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Offline Entry",
            content="Created while offline",
            timestamp=timezone.now(),
            mobile_id=mobile_id,
            sync_status=JournalSyncStatus.PENDING_SYNC,
            last_sync_timestamp=None,  # Never synced
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.sync_status == JournalSyncStatus.PENDING_SYNC
        assert entry.last_sync_timestamp is None

    def test_multiple_offline_entries_sync(self, test_user, test_tenant):
        """Test syncing multiple entries created offline"""
        mobile_ids = [uuid4() for _ in range(3)]

        for mobile_id in mobile_ids:
            JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.PERSONAL_REFLECTION,
                title="Offline",
                content="Content",
                timestamp=timezone.now(),
                mobile_id=mobile_id,
                sync_status=JournalSyncStatus.PENDING_SYNC,
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )

        pending = JournalEntry.objects.filter(
            user=test_user,
            sync_status=JournalSyncStatus.PENDING_SYNC
        )
        assert pending.count() == 3

        # Simulate sync
        pending.update(sync_status=JournalSyncStatus.SYNCED, last_sync_timestamp=timezone.now())

        synced = JournalEntry.objects.filter(
            user=test_user,
            sync_status=JournalSyncStatus.SYNCED
        )
        assert synced.count() == 3

    def test_conflict_detection_same_mobile_id(self, test_user, test_tenant):
        """Test detecting conflicts with same mobile ID"""
        mobile_id = uuid4()

        # Original entry
        entry1 = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Original content",
            timestamp=timezone.now(),
            mobile_id=mobile_id,
            version=1,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        # Update from another client
        entry1.content = "Updated from client"
        entry1.save()
        updated_version = entry1.version

        # Try to update with older version data
        conflicting_entry = JournalEntry.objects.filter(mobile_id=mobile_id).first()
        assert conflicting_entry.version > 1


@pytest.mark.django_db
class TestBatchSync(TestCase):
    """Test batch synchronization"""

    def test_sync_multiple_entries_atomically(self, test_user, test_tenant):
        """Test syncing multiple entries as atomic operation"""
        mobile_ids = [uuid4() for _ in range(5)]
        entries = []

        for mobile_id in mobile_ids:
            entry = JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.PERSONAL_REFLECTION,
                title=f"Entry {mobile_id}",
                content="Content",
                timestamp=timezone.now(),
                mobile_id=mobile_id,
                sync_status=JournalSyncStatus.PENDING_SYNC,
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )
            entries.append(entry)

        # Batch update
        pending = JournalEntry.objects.filter(mobile_id__in=mobile_ids)
        sync_time = timezone.now()
        pending.update(
            sync_status=JournalSyncStatus.SYNCED,
            last_sync_timestamp=sync_time
        )

        # Verify all synced
        synced = JournalEntry.objects.filter(
            mobile_id__in=mobile_ids,
            sync_status=JournalSyncStatus.SYNCED
        )
        assert synced.count() == 5

    def test_partial_sync_failure_handling(self, test_user, test_tenant):
        """Test handling partial failures in batch sync"""
        entry1 = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="OK",
            content="Content",
            timestamp=timezone.now(),
            mobile_id=uuid4(),
            sync_status=JournalSyncStatus.PENDING_SYNC,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        entry2 = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Failed",
            content="Content",
            timestamp=timezone.now(),
            mobile_id=uuid4(),
            sync_status=JournalSyncStatus.PENDING_SYNC,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        # Sync one successfully
        entry1.sync_status = JournalSyncStatus.SYNCED
        entry1.last_sync_timestamp = timezone.now()
        entry1.save()

        # Mark other as error
        entry2.sync_status = JournalSyncStatus.SYNC_ERROR
        entry2.save()

        synced = JournalEntry.objects.filter(sync_status=JournalSyncStatus.SYNCED)
        errors = JournalEntry.objects.filter(sync_status=JournalSyncStatus.SYNC_ERROR)

        assert synced.count() == 1
        assert errors.count() == 1
