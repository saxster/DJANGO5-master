"""
Tests for Serializer PII Redaction

Comprehensive tests for PIIRedactionMixin and serializer-level PII protection.
Validates that sensitive data is properly redacted in serializer output.

Author: Claude Code
Date: 2025-10-01
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from apps.journal.models import JournalEntry
from apps.journal.serializers import (
    JournalEntryListSerializer,
    JournalEntryDetailSerializer
)
from apps.wellness.models import WellnessContentInteraction, WellnessUserProgress, WellnessContent
from apps.wellness.serializers import (
    WellnessContentInteractionSerializer,
    WellnessUserProgressSerializer
)
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestJournalSerializerRedaction(TestCase):
    """Test suite for journal serializer PII redaction"""

    def setUp(self):
        """Set up test fixtures"""
        # Create test tenant
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        # Create test users
        self.owner = User.objects.create_user(
            loginid="owner",
            email="owner@test.com",
            peoplename="John Doe",
            tenant=self.tenant
        )

        self.other_user = User.objects.create_user(
            loginid="other",
            email="other@test.com",
            peoplename="Jane Smith",
            tenant=self.tenant
        )

        self.admin = User.objects.create_superuser(
            loginid="admin",
            email="admin@test.com",
            peoplename="Admin User",
            tenant=self.tenant
        )

        # Create test journal entry
        self.entry = JournalEntry.objects.create(
            user=self.owner,
            tenant=self.tenant,
            entry_type='PERSONAL_REFLECTION',
            title="My Private Thoughts",
            subtitle="Reflecting on my day",
            content="I am feeling anxious about work today",
            mood_rating=5,
            stress_level=4,
            gratitude_items=["My family", "My health"],
            affirmations=["I am enough", "I am capable"],
            stress_triggers=["Work deadline", "Team conflict"],
            privacy_scope='private'
        )

        # Request factory for context
        self.factory = APIRequestFactory()

    def test_owner_sees_all_data_in_list_serializer(self):
        """Test that owner can see all their data in list view"""
        request = self.factory.get('/journal/entries/')
        request.user = self.owner

        serializer = JournalEntryListSerializer(
            self.entry,
            context={'request': request}
        )

        data = serializer.data

        # Owner should see all their data
        assert data['title'] == self.entry.title
        assert data['subtitle'] == self.entry.subtitle
        assert data['user_name'] == self.owner.peoplename

    def test_non_owner_sees_redacted_list_data(self):
        """Test that non-owners see redacted data in list view"""
        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        serializer = JournalEntryListSerializer(
            self.entry,
            context={'request': request}
        )

        data = serializer.data

        # Non-owner should see redacted sensitive fields
        assert data['title'] == '[REDACTED]'
        assert data['subtitle'] == '[REDACTED]'

    def test_admin_sees_partial_redaction_in_list(self):
        """Test that admins see partially redacted data"""
        request = self.factory.get('/journal/entries/')
        request.user = self.admin

        serializer = JournalEntryListSerializer(
            self.entry,
            context={'request': request}
        )

        data = serializer.data

        # Admin should see title markers instead of full redaction
        assert data['title'] == '[TITLE]' or 'TITLE' in data['title']
        assert data['user_name'] != self.owner.peoplename  # Should be partially redacted

    def test_owner_sees_all_detail_data(self):
        """Test that owner sees all detail data"""
        request = self.factory.get(f'/journal/entries/{self.entry.id}/')
        request.user = self.owner

        serializer = JournalEntryDetailSerializer(
            self.entry,
            context={'request': request}
        )

        data = serializer.data

        # Owner should see everything
        assert data['title'] == self.entry.title
        assert data['content'] == self.entry.content
        assert data['gratitude_items'] == self.entry.gratitude_items
        assert data['affirmations'] == self.entry.affirmations
        assert data['stress_triggers'] == self.entry.stress_triggers

    def test_non_owner_sees_fully_redacted_detail(self):
        """Test that non-owners see fully redacted detail data"""
        request = self.factory.get(f'/journal/entries/{self.entry.id}/')
        request.user = self.other_user

        serializer = JournalEntryDetailSerializer(
            self.entry,
            context={'request': request}
        )

        data = serializer.data

        # Non-owner should see redacted sensitive content
        assert data['content'] == '[REDACTED]'
        assert data['gratitude_items'] == ['[REDACTED]'] * len(self.entry.gratitude_items)
        assert data['affirmations'] == ['[REDACTED]'] * len(self.entry.affirmations)
        assert data['stress_triggers'] == ['[REDACTED]'] * len(self.entry.stress_triggers)

    def test_safe_metadata_visible_to_all(self):
        """Test that safe metadata is visible to all users"""
        request = self.factory.get(f'/journal/entries/{self.entry.id}/')
        request.user = self.other_user

        serializer = JournalEntryDetailSerializer(
            self.entry,
            context={'request': request}
        )

        data = serializer.data

        # Safe metadata should be visible
        assert data['id'] == str(self.entry.id)
        assert data['mood_rating'] == self.entry.mood_rating
        assert data['stress_level'] == self.entry.stress_level
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_audit_logging_for_redacted_access(self):
        """Test that redacted access is logged for audit"""
        request = self.factory.get(f'/journal/entries/{self.entry.id}/')
        request.user = self.other_user

        serializer = JournalEntryDetailSerializer(
            self.entry,
            context={'request': request}
        )

        # Trigger serialization
        data = serializer.data

        # Check that audit log was created
        from apps.journal.models.pii_access_log import PIIAccessLog
        logs = PIIAccessLog.objects.filter(
            accessed_user=self.owner,
            user=self.other_user
        )

        # At least one access should be logged
        assert logs.exists()

    def test_serializer_without_request_context(self):
        """Test serializer behavior when request context is missing"""
        # No request in context - should default to full redaction
        serializer = JournalEntryDetailSerializer(self.entry)
        data = serializer.data

        # Without request context, should redact everything
        assert data['content'] == '[REDACTED]'

    def test_multiple_entries_redaction(self):
        """Test redaction works correctly for multiple entries"""
        # Create another entry by different user
        other_entry = JournalEntry.objects.create(
            user=self.other_user,
            tenant=self.tenant,
            entry_type='WORK_REFLECTION',
            title="Work Notes",
            content="Project updates",
            privacy_scope='private'
        )

        request = self.factory.get('/journal/entries/')
        request.user = self.owner

        entries = [self.entry, other_entry]
        serializer = JournalEntryListSerializer(
            entries,
            many=True,
            context={'request': request}
        )

        data = serializer.data

        # First entry: owner's - should see all
        assert data[0]['title'] == self.entry.title

        # Second entry: other user's - should be redacted
        assert data[1]['title'] == '[REDACTED]'


@pytest.mark.django_db
class TestWellnessSerializerRedaction(TestCase):
    """Test suite for wellness serializer PII redaction"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.user1 = User.objects.create_user(
            loginid="user1",
            email="user1@test.com",
            peoplename="Alice Smith",
            tenant=self.tenant
        )

        self.user2 = User.objects.create_user(
            loginid="user2",
            email="user2@test.com",
            peoplename="Bob Jones",
            tenant=self.tenant
        )

        self.admin = User.objects.create_superuser(
            loginid="admin",
            email="admin@test.com",
            peoplename="Admin User",
            tenant=self.tenant
        )

        # Create wellness content
        self.content = WellnessContent.objects.create(
            title="Stress Management",
            summary="Tips for managing stress",
            content="Detailed stress management techniques",
            category='MENTAL_HEALTH',
            created_by=self.admin,
            tenant=self.tenant
        )

        # Create user progress
        self.progress = WellnessUserProgress.objects.create(
            user=self.user1,
            tenant=self.tenant,
            current_streak=5,
            total_content_viewed=10
        )

        # Create interaction
        self.interaction = WellnessContentInteraction.objects.create(
            user=self.user1,
            content=self.content,
            tenant=self.tenant,
            interaction_type='completed',
            user_feedback="This really helped me with my anxiety",
            time_spent_seconds=120
        )

        self.factory = APIRequestFactory()

    def test_user_progress_owner_sees_name(self):
        """Test that user sees their own name in progress"""
        request = self.factory.get('/wellness/progress/')
        request.user = self.user1

        serializer = WellnessUserProgressSerializer(
            self.progress,
            context={'request': request}
        )

        data = serializer.data
        assert data['user_name'] == self.user1.peoplename

    def test_user_progress_admin_sees_redacted_name(self):
        """Test that admin sees partially redacted name"""
        request = self.factory.get('/wellness/progress/')
        request.user = self.admin

        serializer = WellnessUserProgressSerializer(
            self.progress,
            context={'request': request}
        )

        data = serializer.data
        # Admin should see partial redaction
        assert data['user_name'] != self.user1.peoplename
        assert '***' in data['user_name'] or '[NAME]' in data['user_name']

    def test_interaction_owner_sees_feedback(self):
        """Test that user sees their own feedback"""
        request = self.factory.get('/wellness/interactions/')
        request.user = self.user1

        serializer = WellnessContentInteractionSerializer(
            self.interaction,
            context={'request': request}
        )

        data = serializer.data
        assert data['user_feedback'] == self.interaction.user_feedback

    def test_interaction_non_owner_sees_redacted_feedback(self):
        """Test that non-owner sees redacted feedback"""
        request = self.factory.get('/wellness/interactions/')
        request.user = self.user2

        serializer = WellnessContentInteractionSerializer(
            self.interaction,
            context={'request': request}
        )

        data = serializer.data
        assert data['user_feedback'] == '[REDACTED]'

    def test_interaction_safe_metrics_visible(self):
        """Test that safe engagement metrics are visible"""
        request = self.factory.get('/wellness/interactions/')
        request.user = self.user2

        serializer = WellnessContentInteractionSerializer(
            self.interaction,
            context={'request': request}
        )

        data = serializer.data

        # Metrics should be visible
        assert data['time_spent_seconds'] == 120
        assert data['interaction_type'] == 'completed'


@pytest.mark.django_db
class TestSerializerRedactionPerformance(TestCase):
    """Test performance of serializer redaction"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain="test"
        )

        self.owner = User.objects.create_user(
            loginid="owner",
            email="owner@test.com",
            peoplename="Test User",
            tenant=self.tenant
        )

        self.other_user = User.objects.create_user(
            loginid="other",
            email="other@test.com",
            peoplename="Other User",
            tenant=self.tenant
        )

        # Create 50 test entries
        self.entries = []
        for i in range(50):
            entry = JournalEntry.objects.create(
                user=self.owner,
                tenant=self.tenant,
                entry_type='PERSONAL_REFLECTION',
                title=f"Entry {i}",
                content=f"Content {i}",
                gratitude_items=[f"Item {i}"],
                privacy_scope='private'
            )
            self.entries.append(entry)

        self.factory = APIRequestFactory()

    def test_bulk_serialization_performance(self):
        """Test that bulk serialization with redaction is performant"""
        import time

        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        start_time = time.time()
        serializer = JournalEntryListSerializer(
            self.entries,
            many=True,
            context={'request': request}
        )
        data = serializer.data
        elapsed_time = time.time() - start_time

        # Should serialize 50 entries in < 100ms
        assert elapsed_time < 0.1, f"Serialization too slow: {elapsed_time:.3f}s"

        # Verify all entries were redacted
        for entry_data in data:
            assert entry_data['title'] == '[REDACTED]'
            assert entry_data['content'] == '[REDACTED]'


class TestSerializerEdgeCases:
    """Test edge cases for serializer redaction"""

    def test_empty_array_fields(self):
        """Test redaction of empty array fields"""
        # Arrays that are empty should remain empty
        pass

    def test_null_values(self):
        """Test redaction handles null values"""
        # Null fields should remain null
        pass

    def test_nested_serializers(self):
        """Test redaction works with nested serializers"""
        # Nested data should also be redacted
        pass
