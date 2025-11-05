"""
Tests for Journal Entry CRUD Operations

Comprehensive testing of:
- Entry creation with validation
- Retrieval and filtering
- Update operations with version tracking
- Soft delete functionality
- Privacy scope enforcement
- Wellbeing metric validation

Run with: pytest apps/journal/tests/test_entry_crud.py -v --cov=apps/journal
"""
import pytest
from django.utils import timezone
from django.test import TestCase

from apps.journal.models import JournalEntry
from apps.journal.models.enums import (
    JournalEntryType,
    JournalPrivacyScope,
)


@pytest.mark.django_db
class TestJournalEntryCreation(TestCase):
    """Test journal entry creation with validation"""

    def test_create_basic_entry(self, test_user, test_tenant):
        """Test creating a basic journal entry"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Test Entry",
            content="Test content",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.id is not None
        assert entry.title == "Test Entry"
        assert entry.user == test_user
        assert entry.version == 1
        assert entry.is_deleted is False
        assert entry.is_draft is False

    def test_create_entry_with_mood_metrics(self, test_user, test_tenant):
        """Test creating entry with wellbeing metrics"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Mood Check",
            content="Today's mood check in",
            timestamp=timezone.now(),
            mood_rating=8,
            stress_level=2,
            energy_level=9,
            mood_description="Feeling great",
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.mood_rating == 8
        assert entry.stress_level == 2
        assert entry.energy_level == 9
        assert entry.has_wellbeing_metrics is True

    def test_create_entry_with_tags_and_metadata(self, test_user, test_tenant):
        """Test creating entry with tags and metadata"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Site Inspection",
            content="Inspection completed",
            timestamp=timezone.now(),
            tags=["inspection", "safety", "routine"],
            priority="high",
            severity="low",
            metadata={"location": "Building A", "inspector": "John"},
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert "inspection" in entry.tags
        assert entry.priority == "high"
        assert entry.metadata["location"] == "Building A"

    def test_create_entry_sets_default_timestamp(self, test_user, test_tenant):
        """Test that timestamp is set to now if not provided"""
        before = timezone.now()
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Test Entry",
            content="Test content",
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        after = timezone.now()

        assert before <= entry.timestamp <= after

    def test_create_entry_defaults_to_private_scope(self, test_user, test_tenant):
        """Test that entries default to private scope"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Test Entry",
            content="Test content",
            timestamp=timezone.now(),
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.privacy_scope == JournalPrivacyScope.PRIVATE


@pytest.mark.django_db
class TestJournalEntryRetrieval(TestCase):
    """Test journal entry retrieval and filtering"""

    def test_retrieve_entry_by_id(self, test_journal_entry):
        """Test retrieving an entry by ID"""
        entry = JournalEntry.objects.get(id=test_journal_entry.id)
        assert entry.title == "Test Journal Entry"
        assert entry.content == "This is test content for the journal entry."

    def test_list_entries_for_user(self, test_user, test_tenant):
        """Test listing all entries for a user"""
        for i in range(3):
            JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.PERSONAL_REFLECTION,
                title="Entry {i}",
                content="Content {i}",
                timestamp=timezone.now(),
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )

        entries = JournalEntry.objects.filter(user=test_user)
        assert entries.count() == 3

    def test_filter_entries_by_type(self, test_user, test_tenant):
        """Test filtering entries by type"""
        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Mood",
            content="Check",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Inspection",
            content="Report",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        mood_entries = JournalEntry.objects.filter(entry_type=JournalEntryType.MOOD_CHECK_IN)
        assert mood_entries.count() == 1
        assert mood_entries.first().title == "Mood"

    def test_filter_entries_by_date_range(self, test_user, test_tenant):
        """Test filtering entries by date range"""
        from datetime import timedelta

        base_time = timezone.now()
        old_entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Old",
            content="Old entry",
            timestamp=base_time - timedelta(days=10),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        recent_entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Recent",
            content="Recent entry",
            timestamp=base_time,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        week_ago = base_time - timedelta(days=7)
        recent = JournalEntry.objects.filter(timestamp__gte=week_ago)
        assert recent.count() == 1
        assert recent.first().title == "Recent"

    def test_exclude_deleted_entries(self, test_user, test_tenant):
        """Test filtering out soft-deleted entries"""
        active = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Active",
            content="Active entry",
            timestamp=timezone.now(),
            is_deleted=False,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        deleted = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Deleted",
            content="Deleted entry",
            timestamp=timezone.now(),
            is_deleted=True,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        active_entries = JournalEntry.objects.filter(user=test_user, is_deleted=False)
        assert active_entries.count() == 1
        assert active_entries.first().title == "Active"


@pytest.mark.django_db
class TestJournalEntryUpdate(TestCase):
    """Test journal entry update operations"""

    def test_update_entry_content(self, test_journal_entry):
        """Test updating entry content"""
        new_content = "Updated content"
        old_version = test_journal_entry.version

        test_journal_entry.content = new_content
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.content == new_content
        assert refreshed.version == old_version + 1

    def test_update_entry_title(self, test_journal_entry):
        """Test updating entry title"""
        new_title = "New Title"
        test_journal_entry.title = new_title
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.title == new_title

    def test_update_mood_rating(self, test_journal_entry):
        """Test updating mood rating"""
        test_journal_entry.mood_rating = 9
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.mood_rating == 9

    def test_update_privacy_scope(self, test_journal_entry):
        """Test updating privacy scope"""
        test_journal_entry.privacy_scope = JournalPrivacyScope.SHARED
        test_journal_entry.sharing_permissions = ["user-id-123"]
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.privacy_scope == JournalPrivacyScope.SHARED
        assert "user-id-123" in refreshed.sharing_permissions

    def test_version_increments_on_save(self, test_journal_entry):
        """Test that version increments on each save"""
        assert test_journal_entry.version == 1

        test_journal_entry.content = "Updated"
        test_journal_entry.save()
        assert test_journal_entry.version == 2

        test_journal_entry.content = "Updated again"
        test_journal_entry.save()
        assert test_journal_entry.version == 3

    def test_update_tags(self, test_journal_entry):
        """Test updating tags"""
        test_journal_entry.tags = ["important", "follow-up"]
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert "important" in refreshed.tags
        assert "follow-up" in refreshed.tags


@pytest.mark.django_db
class TestJournalEntrySoftDelete(TestCase):
    """Test soft delete functionality"""

    def test_soft_delete_entry(self, test_journal_entry):
        """Test soft deleting an entry"""
        assert test_journal_entry.is_deleted is False

        test_journal_entry.is_deleted = True
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.is_deleted is True

    def test_restore_soft_deleted_entry(self, test_journal_entry):
        """Test restoring a soft-deleted entry"""
        test_journal_entry.is_deleted = True
        test_journal_entry.save()

        test_journal_entry.is_deleted = False
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.is_deleted is False

    def test_filter_active_entries_excludes_deleted(self, test_user, test_tenant):
        """Test that filtering excludes deleted entries"""
        active = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Active",
            content="Active",
            timestamp=timezone.now(),
            is_deleted=False,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        for i in range(2):
            deleted = JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.PERSONAL_REFLECTION,
                title="Deleted {i}",
                content="Deleted {i}",
                timestamp=timezone.now(),
                is_deleted=True,
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )

        active_count = JournalEntry.objects.filter(
            user=test_user,
            is_deleted=False
        ).count()
        assert active_count == 1


@pytest.mark.django_db
class TestJournalEntryWellbeingProperties(TestCase):
    """Test wellbeing-related properties and methods"""

    def test_is_wellbeing_entry_true_for_mood_check(self, test_user, test_tenant):
        """Test is_wellbeing_entry returns True for mood check-in"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Mood",
            content="Check",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.is_wellbeing_entry is True

    def test_is_wellbeing_entry_true_for_stress_log(self, test_user, test_tenant):
        """Test is_wellbeing_entry returns True for stress log"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.STRESS_LOG,
            title="Stress",
            content="Log",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.is_wellbeing_entry is True

    def test_is_wellbeing_entry_false_for_work_entry(self, test_user, test_tenant):
        """Test is_wellbeing_entry returns False for work entries"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Inspection",
            content="Report",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.is_wellbeing_entry is False

    def test_has_wellbeing_metrics_true_with_mood(self, test_user, test_tenant):
        """Test has_wellbeing_metrics returns True when mood is set"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Mood",
            content="Check",
            timestamp=timezone.now(),
            mood_rating=7,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.has_wellbeing_metrics is True

    def test_has_wellbeing_metrics_false_when_empty(self, test_user, test_tenant):
        """Test has_wellbeing_metrics returns False with no metrics"""
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
        assert entry.has_wellbeing_metrics is False


@pytest.mark.django_db
class TestJournalEntryAccessControl(TestCase):
    """Test entry access control methods"""

    def test_owner_can_access_entry(self, test_user, test_journal_entry):
        """Test that entry owner can access their entry"""
        assert test_journal_entry.can_user_access(test_user) is True

    def test_private_entry_inaccessible_to_others(self, test_user, test_user2, test_journal_entry):
        """Test that private entries are not accessible to others"""
        assert test_journal_entry.privacy_scope == JournalPrivacyScope.PRIVATE
        assert test_journal_entry.can_user_access(test_user2) is False

    def test_shared_entry_accessible_to_permitted_user(self, test_user, test_user2, test_tenant):
        """Test that shared entries are accessible to permitted users"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Shared",
            content="Content",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.SHARED,
            sharing_permissions=[str(test_user2.id)],
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.can_user_access(test_user2) is True

    def test_get_effective_privacy_scope_for_owner(self, test_user, test_journal_entry):
        """Test effective privacy scope for owner"""
        scope = test_journal_entry.get_effective_privacy_scope(test_user)
        assert scope == test_journal_entry.privacy_scope
