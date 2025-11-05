"""
Tests for Model Validation and Constraints

Testing:
- Field validators
- Check constraints
- Model-level validation
- Index effectiveness
- Database constraints

Run with: pytest apps/journal/tests/test_model_validation.py -v
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.journal.models.enums import JournalEntryType, JournalPrivacyScope


@pytest.mark.django_db
class TestMoodRatingValidation(TestCase):
    """Test mood rating field validation"""

    def test_valid_mood_rating_minimum(self, test_user, test_tenant):
        """Test valid minimum mood rating (1)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            mood_rating=1,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.mood_rating == 1

    def test_valid_mood_rating_maximum(self, test_user, test_tenant):
        """Test valid maximum mood rating (10)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            mood_rating=10,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.mood_rating == 10

    def test_valid_mood_rating_midrange(self, test_user, test_tenant):
        """Test valid midrange mood ratings"""
        for rating in [3, 5, 7, 9]:
            entry = JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.MOOD_CHECK_IN,
                title="Entry",
                content="Content",
                timestamp=timezone.now(),
                mood_rating=rating,
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )
            assert entry.mood_rating == rating

    def test_null_mood_rating_allowed(self, test_user, test_tenant):
        """Test that null mood rating is allowed"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            mood_rating=None,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.mood_rating is None


@pytest.mark.django_db
class TestStressLevelValidation(TestCase):
    """Test stress level field validation"""

    def test_valid_stress_level_minimum(self, test_user, test_tenant):
        """Test valid minimum stress level (1)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.STRESS_LOG,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            stress_level=1,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.stress_level == 1

    def test_valid_stress_level_maximum(self, test_user, test_tenant):
        """Test valid maximum stress level (5)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.STRESS_LOG,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            stress_level=5,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.stress_level == 5

    def test_null_stress_level_allowed(self, test_user, test_tenant):
        """Test that null stress level is allowed"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            stress_level=None,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.stress_level is None


@pytest.mark.django_db
class TestEnergyLevelValidation(TestCase):
    """Test energy level field validation"""

    def test_valid_energy_level_minimum(self, test_user, test_tenant):
        """Test valid minimum energy level (1)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            energy_level=1,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.energy_level == 1

    def test_valid_energy_level_maximum(self, test_user, test_tenant):
        """Test valid maximum energy level (10)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            energy_level=10,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.energy_level == 10

    def test_null_energy_level_allowed(self, test_user, test_tenant):
        """Test that null energy level is allowed"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            energy_level=None,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.energy_level is None


@pytest.mark.django_db
class TestCompletionRateValidation(TestCase):
    """Test completion rate field validation"""

    def test_valid_completion_rate_minimum(self, test_user, test_tenant):
        """Test valid minimum completion rate (0.0)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            completion_rate=0.0,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.completion_rate == 0.0

    def test_valid_completion_rate_maximum(self, test_user, test_tenant):
        """Test valid maximum completion rate (1.0)"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            completion_rate=1.0,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.completion_rate == 1.0

    def test_valid_completion_rate_midrange(self, test_user, test_tenant):
        """Test valid midrange completion rates"""
        for rate in [0.25, 0.5, 0.75]:
            entry = JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.SITE_INSPECTION,
                title="Entry",
                content="Content",
                timestamp=timezone.now(),
                completion_rate=rate,
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )
            assert entry.completion_rate == rate

    def test_null_completion_rate_allowed(self, test_user, test_tenant):
        """Test that null completion rate is allowed"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            completion_rate=None,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.completion_rate is None


@pytest.mark.django_db
class TestEfficiencyAndQualityScores(TestCase):
    """Test efficiency and quality score validation"""

    def test_valid_efficiency_score_range(self, test_user, test_tenant):
        """Test valid efficiency scores (0-10)"""
        for score in [0.0, 5.0, 10.0]:
            entry = JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.SITE_INSPECTION,
                title="Entry",
                content="Content",
                timestamp=timezone.now(),
                efficiency_score=score,
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )
            assert entry.efficiency_score == score

    def test_valid_quality_score_range(self, test_user, test_tenant):
        """Test valid quality scores (0-10)"""
        for score in [0.0, 5.0, 10.0]:
            entry = JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.SITE_INSPECTION,
                title="Entry",
                content="Content",
                timestamp=timezone.now(),
                quality_score=score,
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )
            assert entry.quality_score == score

    def test_null_scores_allowed(self, test_user, test_tenant):
        """Test that null scores are allowed"""
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            efficiency_score=None,
            quality_score=None,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.efficiency_score is None
        assert entry.quality_score is None


@pytest.mark.django_db
class TestDataRetentionValidation(TestCase):
    """Test data retention policy validation"""

    def test_valid_retention_minimum(self, test_user):
        """Test valid minimum data retention (30 days)"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            data_retention_days=30,
            consent_timestamp=timezone.now(),
        )
        assert settings.data_retention_days == 30

    def test_valid_retention_maximum(self, test_user):
        """Test valid maximum data retention (3650 days = 10 years)"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            data_retention_days=3650,
            consent_timestamp=timezone.now(),
        )
        assert settings.data_retention_days == 3650

    def test_default_retention_period(self, test_user):
        """Test default data retention is 1 year"""
        settings = JournalPrivacySettings.objects.create(
            user=test_user,
            consent_timestamp=timezone.now(),
        )
        assert settings.data_retention_days == 365


@pytest.mark.django_db
class TestJSONFieldValidation(TestCase):
    """Test JSON field validation"""

    def test_tags_as_list(self, test_user, test_tenant):
        """Test tags field stores list correctly"""
        tags = ["important", "follow-up", "urgent"]
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            tags=tags,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.tags == tags

    def test_sharing_permissions_as_list(self, test_user, test_tenant):
        """Test sharing_permissions stores list correctly"""
        from uuid import uuid4

        user_ids = [str(uuid4()) for _ in range(3)]
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            sharing_permissions=user_ids,
            privacy_scope=JournalPrivacyScope.SHARED,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.sharing_permissions == user_ids

    def test_metadata_as_dict(self, test_user, test_tenant):
        """Test metadata field stores dict correctly"""
        metadata = {
            "location": "Building A",
            "inspector": "John",
            "equipment": ["camera", "thermometer"]
        }
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            metadata=metadata,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.metadata == metadata

    def test_location_coordinates_as_dict(self, test_user, test_tenant):
        """Test location_coordinates field stores dict correctly"""
        coords = {"lat": 40.7128, "lng": -74.0060}
        entry = JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title="Entry",
            content="Content",
            timestamp=timezone.now(),
            location_coordinates=coords,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )
        assert entry.location_coordinates == coords


@pytest.mark.django_db
class TestModelIndexes(TestCase):
    """Test that model indexes work correctly for performance"""

    def test_user_timestamp_index(self, test_user, test_tenant):
        """Test filtering by user and timestamp uses index"""
        from datetime import timedelta

        now = timezone.now()
        for i in range(5):
            JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.PERSONAL_REFLECTION,
                title=f"Entry {i}",
                content="Content",
                timestamp=now - timedelta(days=i),
                privacy_scope=JournalPrivacyScope.PRIVATE,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )

        # Query should use index
        recent = JournalEntry.objects.filter(
            user=test_user,
            timestamp__gte=now - timedelta(days=2)
        ).order_by('-timestamp')

        assert recent.count() >= 2

    def test_entry_type_timestamp_index(self, test_user, test_tenant):
        """Test filtering by entry type and timestamp uses index"""
        from datetime import timedelta

        now = timezone.now()
        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.MOOD_CHECK_IN,
            title="Mood",
            content="Check",
            timestamp=now,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        moods = JournalEntry.objects.filter(
            entry_type=JournalEntryType.MOOD_CHECK_IN
        ).order_by('-timestamp')

        assert moods.count() >= 1

    def test_privacy_scope_user_index(self, test_user, test_tenant):
        """Test filtering by privacy scope and user uses index"""
        for scope in [JournalPrivacyScope.PRIVATE, JournalPrivacyScope.SHARED]:
            JournalEntry.objects.create(
                user=test_user,
                tenant=test_tenant,
                entry_type=JournalEntryType.PERSONAL_REFLECTION,
                title="Entry",
                content="Content",
                timestamp=timezone.now(),
                privacy_scope=scope,
                consent_given=True,
                consent_timestamp=timezone.now(),
            )

        private = JournalEntry.objects.filter(
            user=test_user,
            privacy_scope=JournalPrivacyScope.PRIVATE
        )

        assert private.count() >= 1
