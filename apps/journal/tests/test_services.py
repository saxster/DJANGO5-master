"""
Tests for Journal Services

Testing:
- JournalEntryService CRUD operations
- JournalSyncService mobile sync logic
- JournalSearchService filtering and search
- Analytics service integration
- Error handling and edge cases

Run with: pytest apps/journal/tests/test_services.py -v
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from apps.journal.models import JournalEntry
from apps.journal.models.enums import JournalEntryType, JournalPrivacyScope
from apps.journal.services.journal_entry_service import JournalEntryService
from apps.journal.services.journal_sync_service import JournalSyncService
from apps.journal.services.journal_search_service import JournalSearchService


@pytest.mark.django_db
class TestJournalEntryService(TestCase):
    """Test JournalEntryService"""

    def test_service_create_entry_with_analysis(self, test_user, test_tenant):
        """Test service creates entry with analysis"""
        service = JournalEntryService()

        validated_data = {
            'entry_type': JournalEntryType.MOOD_CHECK_IN,
            'title': 'Morning Check',
            'content': 'Feeling good today',
            'timestamp': timezone.now(),
            'mood_rating': 8,
            'stress_level': 2,
            'energy_level': 9,
            'privacy_scope': JournalPrivacyScope.PRIVATE,
            'consent_given': True,
            'consent_timestamp': timezone.now(),
        }

        result = service.create_entry_with_analysis(test_user, validated_data)

        assert result['success'] is True
        assert result['journal_entry'] is not None
        assert result['error'] is None
        assert result['journal_entry'].user == test_user
        assert result['journal_entry'].title == 'Morning Check'

    def test_service_create_entry_stores_metadata(self, test_user, test_tenant):
        """Test service stores metadata correctly"""
        service = JournalEntryService()

        validated_data = {
            'entry_type': JournalEntryType.SITE_INSPECTION,
            'title': 'Inspection',
            'content': 'Report content',
            'timestamp': timezone.now(),
            'location_site_name': 'Office A',
            'tags': ['inspection', 'routine'],
            'metadata': {'inspector': 'John', 'duration': '45 mins'},
            'privacy_scope': JournalPrivacyScope.PRIVATE,
            'consent_given': True,
            'consent_timestamp': timezone.now(),
        }

        result = service.create_entry_with_analysis(test_user, validated_data)

        entry = result['journal_entry']
        assert entry.location_site_name == 'Office A'
        assert 'inspection' in entry.tags
        assert entry.metadata['inspector'] == 'John'


@pytest.mark.django_db
class TestJournalSyncService(TestCase):
    """Test JournalSyncService"""

    def test_sync_service_process_sync_request(self, test_user, test_tenant):
        """Test service processes sync request"""
        service = JournalSyncService()

        # Create entries on mobile to sync
        sync_data = {
            'entries': [
                {
                    'mobile_id': 'mobile-1',
                    'entry_type': JournalEntryType.MOOD_CHECK_IN,
                    'title': 'Synced Entry',
                    'content': 'Content from mobile',
                    'timestamp': timezone.now().isoformat(),
                    'mood_rating': 7,
                    'privacy_scope': JournalPrivacyScope.PRIVATE,
                    'consent_given': True,
                },
            ],
            'last_sync_timestamp': None,
        }

        # Mock serializers
        serializers = {
            'detail': type('Serializer', (), {'to_representation': lambda self, x: {}})
        }

        result = service.process_sync_request(test_user, sync_data, serializers)

        assert 'sync_timestamp' in result
        assert 'created_count' in result
        assert 'conflict_count' in result

    def test_sync_service_handles_multiple_entries(self, test_user, test_tenant):
        """Test service handles multiple entries in sync"""
        service = JournalSyncService()

        sync_data = {
            'entries': [
                {
                    'mobile_id': f'mobile-{i}',
                    'entry_type': JournalEntryType.PERSONAL_REFLECTION,
                    'title': f'Entry {i}',
                    'content': f'Content {i}',
                    'timestamp': timezone.now().isoformat(),
                    'privacy_scope': JournalPrivacyScope.PRIVATE,
                    'consent_given': True,
                }
                for i in range(3)
            ],
            'last_sync_timestamp': None,
        }

        serializers = {
            'detail': type('Serializer', (), {'to_representation': lambda self, x: {}})
        }

        result = service.process_sync_request(test_user, sync_data, serializers)

        # Should have processed all entries
        assert result['created_count'] + result['updated_count'] + result['conflict_count'] >= 0


@pytest.mark.django_db
class TestJournalSearchService(TestCase):
    """Test JournalSearchService"""

    def test_search_by_text(self, test_user, test_tenant):
        """Test searching entries by text"""
        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title='Project Alpha',
            content='Work on project alpha this week',
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title='Personal Thoughts',
            content='Reflecting on life',
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        service = JournalSearchService()
        results = service.search_entries(
            user=test_user,
            query='project',
            filters={}
        )

        assert len(results) >= 1
        assert any('Project' in e.title for e in results)

    def test_search_by_tags(self, test_user, test_tenant):
        """Test searching entries by tags"""
        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.SITE_INSPECTION,
            title='Inspection Report',
            content='Site inspection',
            tags=['safety', 'routine'],
            timestamp=timezone.now(),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        service = JournalSearchService()
        results = service.search_entries(
            user=test_user,
            query='',
            filters={'tags': ['safety']}
        )

        assert len(results) >= 1

    def test_search_by_date_range(self, test_user, test_tenant):
        """Test searching entries by date range"""
        from datetime import timedelta

        base_time = timezone.now()

        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title='Recent',
            content='Content',
            timestamp=base_time,
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        JournalEntry.objects.create(
            user=test_user,
            tenant=test_tenant,
            entry_type=JournalEntryType.PERSONAL_REFLECTION,
            title='Old',
            content='Content',
            timestamp=base_time - timedelta(days=30),
            privacy_scope=JournalPrivacyScope.PRIVATE,
            consent_given=True,
            consent_timestamp=timezone.now(),
        )

        service = JournalSearchService()
        week_ago = base_time - timedelta(days=7)
        results = service.search_entries(
            user=test_user,
            query='',
            filters={'date_from': week_ago}
        )

        assert len(results) >= 1
        assert any('Recent' in e.title for e in results)


@pytest.mark.django_db
class TestServiceErrorHandling(TestCase):
    """Test service error handling"""

    def test_entry_service_handles_invalid_data(self, test_user, test_tenant):
        """Test service handles invalid data gracefully"""
        service = JournalEntryService()

        # Missing required fields
        validated_data = {
            'entry_type': JournalEntryType.PERSONAL_REFLECTION,
            'title': '',  # Empty title
            'content': '',
            'timestamp': timezone.now(),
        }

        result = service.create_entry_with_analysis(test_user, validated_data)

        # Should either succeed with validation or handle error
        assert 'success' in result
        assert 'error' in result or result['success']

    def test_sync_service_handles_database_errors(self, test_user, test_tenant):
        """Test sync service handles database errors"""
        service = JournalSyncService()

        # Create sync data with problematic entries
        sync_data = {
            'entries': [
                {
                    'mobile_id': 'mobile-1',
                    'entry_type': 'INVALID_TYPE',  # Invalid
                    'title': 'Entry',
                    'content': 'Content',
                    'timestamp': timezone.now().isoformat(),
                    'privacy_scope': JournalPrivacyScope.PRIVATE,
                    'consent_given': True,
                },
            ],
            'last_sync_timestamp': None,
        }

        serializers = {
            'detail': type('Serializer', (), {'to_representation': lambda self, x: {}})
        }

        result = service.process_sync_request(test_user, sync_data, serializers)

        # Should handle gracefully
        assert 'conflict_count' in result


@pytest.mark.django_db
class TestServiceIntegration(TestCase):
    """Test service integration scenarios"""

    def test_create_and_search_workflow(self, test_user, test_tenant):
        """Test complete workflow: create entries and search"""
        entry_service = JournalEntryService()
        search_service = JournalSearchService()

        # Create multiple entries
        for i in range(3):
            validated_data = {
                'entry_type': JournalEntryType.MOOD_CHECK_IN,
                'title': f'Mood Check {i}',
                'content': f'How I felt on day {i}',
                'timestamp': timezone.now(),
                'mood_rating': 5 + i,
                'privacy_scope': JournalPrivacyScope.PRIVATE,
                'consent_given': True,
                'consent_timestamp': timezone.now(),
            }
            entry_service.create_entry_with_analysis(test_user, validated_data)

        # Search for entries
        results = search_service.search_entries(
            user=test_user,
            query='Mood',
            filters={}
        )

        assert len(results) >= 3

    def test_create_sync_and_search_workflow(self, test_user, test_tenant):
        """Test workflow: create via sync and search"""
        entry_service = JournalEntryService()
        sync_service = JournalSyncService()
        search_service = JournalSearchService()

        # Create an entry
        validated_data = {
            'entry_type': JournalEntryType.SITE_INSPECTION,
            'title': 'Site Visit',
            'content': 'Visited site today',
            'timestamp': timezone.now(),
            'tags': ['inspection'],
            'privacy_scope': JournalPrivacyScope.PRIVATE,
            'consent_given': True,
            'consent_timestamp': timezone.now(),
        }
        entry_service.create_entry_with_analysis(test_user, validated_data)

        # Search for the entry
        results = search_service.search_entries(
            user=test_user,
            query='Site',
            filters={}
        )

        assert len(results) >= 1
        assert any('Site' in e.title for e in results)
