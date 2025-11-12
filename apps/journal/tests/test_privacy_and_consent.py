"""
Tests for Privacy and Consent Management

Testing:
- Privacy scope enforcement
- User consent tracking
- Sharing permissions
- Privacy settings
- Data retention policies
- Crisis intervention rules

Run with: pytest apps/journal/tests/test_privacy_and_consent.py -v
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.journal.models.enums import JournalEntryType, JournalPrivacyScope


@pytest.mark.django_db
class TestPrivacyScope(TestCase):
    """Test privacy scope enforcement"""

    def test_private_scope_blocks_access(self, test_user, test_user2, test_tenant):
        """Test that PRIVATE scope prevents access by others"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Private Entry",
            content="Very private",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.can_user_access(test_user) is True
        assert entry.can_user_access(test_user2) is False

    def test_shared_scope_grants_permission(self, test_user, test_user2, test_tenant):
        """Test that SHARED scope allows selected users"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Shared Entry",
            content="Shared with team",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.SHARED,
            sharing_permissions=[str(test_user2.id)],
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.can_user_access(test_user2) is True

    def test_shared_scope_denies_unpermitted_users(self, test_user, test_user2, test_tenant):
        """Test that SHARED scope denies non-listed users"""
        from uuid import uuid4

        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Shared Entry",
            content="Shared with specific users",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.SHARED,
            sharing_permissions=[str(uuid4())],  # Different user
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert entry.can_user_access(test_user2) is False

    def test_aggregate_only_scope_blocks_access(self, test_user, test_user2, test_tenant):
        """Test that AGGREGATE_ONLY scope prevents individual access"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Aggregate Entry",
            content="For analytics only",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.AGGREGATE_ONLY,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        # Even owner can view full entry
        assert entry.can_user_access(test_user) is True
        # But others cannot
        assert entry.can_user_access(test_user2) is False


@pytest.mark.django_db
class TestConsentTracking(TestCase):
    """Test consent management"""

    def test_create_entry_with_consent(self, test_user, test_tenant):
        """Test creating entry with explicit consent"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Consented Entry",
            content="Content",
            timestamp=timezone.now(),
            consent_given=True,
            consent_timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
        )

        assert entry.consent_given is True
        assert entry.consent_timestamp is not None

    def test_create_entry_without_consent(self, test_user, test_tenant):
        """Test creating entry without explicit consent"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="No Consent Entry",
            content="Content",
            timestamp=timezone.now(),
            consent_given=False,
            privacy_scope=JournalPrivacyScope.PRIVATE,
        )

        assert entry.consent_given is False
        assert entry.consent_timestamp is None

    def test_update_consent_status(self, test_journal_entry):
        """Test updating consent status"""
        assert test_journal_entry.consent_given is True

        test_journal_entry.consent_given = False
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert refreshed.consent_given is False


@pytest.mark.django_db
class TestSharingPermissions(TestCase):
    """Test sharing permissions management"""

    def test_add_sharing_permission(self, test_user, test_user2, test_journal_entry):
        """Test adding a sharing permission"""
        assert test_journal_entry.sharing_permissions == []

        test_journal_entry.sharing_permissions.append(str(test_user2.id))
        test_journal_entry.privacy_scope = JournalPrivacyScope.SHARED
        test_journal_entry.save()

        refreshed = JournalEntry.objects.get(id=test_journal_entry.id)
        assert str(test_user2.id) in refreshed.sharing_permissions

    def test_remove_sharing_permission(self, test_user, test_user2, test_tenant):
        """Test removing a sharing permission"""
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

        assert str(test_user2.id) in entry.sharing_permissions
        entry.sharing_permissions = []
        entry.save()

        refreshed = JournalEntry.objects.get(id=entry.id)
        assert refreshed.sharing_permissions == []

    def test_multiple_sharing_permissions(self, test_user, test_user2, test_tenant):
        """Test entry shared with multiple users"""
        from uuid import uuid4

        user3_id = str(uuid4())
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.TEAM_COLLABORATION,
            title="Team Entry",
            content="Content",
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.SHARED,
            sharing_permissions=[str(test_user2.id), user3_id],
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert len(entry.sharing_permissions) == 2
        assert str(test_user2.id) in entry.sharing_permissions
        assert user3_id in entry.sharing_permissions


@pytest.mark.django_db
class TestJournalPrivacySettings(TestCase):
    """Test privacy settings model"""

    def test_create_privacy_settings(self, test_user):
        """Test creating privacy settings"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            default_privacy_scope=JournalPrivacyScope.PRIVATE,
            wellbeing_sharing_consent=False,
            manager_access_consent=False,
            analytics_consent=False,
            consent_timestamp=timezone.now(),
        )

        assert settings.user == test_user
        assert settings.default_privacy_scope == JournalPrivacyScope.PRIVATE
        assert settings.wellbeing_sharing_consent is False

    def test_privacy_settings_defaults(self, test_user):
        """Test default values for privacy settings"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            consent_timestamp=timezone.now(),
        )

        assert settings.default_privacy_scope == JournalPrivacyScope.PRIVATE
        assert settings.wellbeing_sharing_consent is False
        assert settings.manager_access_consent is False
        assert settings.analytics_consent is False
        assert settings.crisis_intervention_consent is False
        assert settings.data_retention_days == 365
        assert settings.auto_delete_enabled is False

    def test_update_privacy_preferences(self, test_privacy_settings):
        """Test updating privacy preferences"""
        test_privacy_settings.default_privacy_scope = JournalPrivacyScope.SHARED
        test_privacy_settings.analytics_consent = True
        test_privacy_settings.save()

        refreshed = JournalPrivacySettings.objects.get(user=test_privacy_settings.user)
        assert refreshed.default_privacy_scope == JournalPrivacyScope.SHARED
        assert refreshed.analytics_consent is True

    def test_grant_wellbeing_sharing_consent(self, test_user):
        """Test granting wellbeing sharing consent"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            wellbeing_sharing_consent=False,
            analytics_consent=False,
            consent_timestamp=timezone.now(),
        )

        assert settings.can_share_wellbeing_data() is False

        settings.wellbeing_sharing_consent = True
        settings.analytics_consent = True
        settings.save()

        refreshed = JournalPrivacySettings.objects.get(user=test_user)
        assert refreshed.can_share_wellbeing_data() is True

    def test_get_effective_privacy_scope_sensitive_entry(self, test_user):
        """Test effective privacy scope for sensitive entries"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            default_privacy_scope=JournalPrivacyScope.SHARED,
            consent_timestamp=timezone.now(),
        )

        # Sensitive entries should always be private
        scope = settings.get_effective_privacy_scope(JournalEntryType.MOOD_CHECK_IN)
        assert scope == JournalPrivacyScope.PRIVATE

    def test_get_effective_privacy_scope_non_sensitive_entry(self, test_user):
        """Test effective privacy scope for non-sensitive entries"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            default_privacy_scope=JournalPrivacyScope.SHARED,
            consent_timestamp=timezone.now(),
        )

        # Non-sensitive entries use default scope
        scope = settings.get_effective_privacy_scope(JournalEntryType.SITE_INSPECTION)
        assert scope == JournalPrivacyScope.SHARED

    def test_data_retention_preferences(self, test_user):
        """Test data retention preferences"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            data_retention_days=90,  # 3 months
            auto_delete_enabled=True,
            consent_timestamp=timezone.now(),
        )

        assert settings.data_retention_days == 90
        assert settings.auto_delete_enabled is True


@pytest.mark.django_db
class TestCrisisIntervention(TestCase):
    """Test crisis intervention rules"""

    def test_crisis_intervention_triggered_by_low_mood(self, test_user):
        """Test crisis intervention trigger for very low mood"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            crisis_intervention_consent=True,
            consent_timestamp=timezone.now(),
        )

        from apps.journal.models import JournalEntry

        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=getattr(test_user, 'tenant', None),
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Low Mood",
            content="Feeling terrible",
            timestamp=timezone.now(),
            mood_rating=2,  # Very low
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert settings.should_trigger_crisis_intervention(entry) is True

    def test_crisis_intervention_triggered_by_high_stress(self, test_user):
        """Test crisis intervention trigger for high stress"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            crisis_intervention_consent=True,
            consent_timestamp=timezone.now(),
        )

        from apps.journal.models import JournalEntry

        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=getattr(test_user, 'tenant', None),
            entry_type=JournalEntryType.STRESS_LOG,
            title="High Stress",
            content="Very stressful day",
            timestamp=timezone.now(),
            stress_level=5,  # Maximum stress
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert settings.should_trigger_crisis_intervention(entry) is True

    def test_crisis_intervention_not_triggered_without_consent(self, test_user):
        """Test that crisis intervention requires consent"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            crisis_intervention_consent=False,
            consent_timestamp=timezone.now(),
        )

        from apps.journal.models import JournalEntry

        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=getattr(test_user, 'tenant', None),
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Low Mood",
            content="Feeling terrible",
            timestamp=timezone.now(),
            mood_rating=2,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert settings.should_trigger_crisis_intervention(entry) is False

    def test_crisis_intervention_not_triggered_with_normal_metrics(self, test_user):
        """Test that normal metrics don't trigger intervention"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            crisis_intervention_consent=True,
            consent_timestamp=timezone.now(),
        )

        from apps.journal.models import JournalEntry

        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=getattr(test_user, 'tenant', None),
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Normal Mood",
            content="Regular day",
            timestamp=timezone.now(),
            mood_rating=7,
            stress_level=2,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        assert settings.should_trigger_crisis_intervention(entry) is False
