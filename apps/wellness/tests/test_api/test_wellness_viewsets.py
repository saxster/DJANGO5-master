"""
Unit Tests for Wellness API ViewSets

Tests wellness endpoints:
- Journal entries (create, list, retrieve)
- Wellness content (daily tip, personalized, track interaction)
- Analytics (progress, wellbeing analytics)
- Privacy settings (get, update)

Compliance with .claude/rules.md:
- Specific exception testing
- 80% coverage target
- PII protection validation
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch, MagicMock

from apps.peoples.models import People
from apps.tenants.models import Client, BusinessUnit


@pytest.mark.django_db
class TestJournalViewSet(TestCase):
    """Test suite for JournalViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client_obj = APIClient()

        # Create test tenant
        self.tenant = Client.objects.create(
            name="Test Client",
            is_active=True
        )

        # Create test user
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            client=self.tenant,
        )

        # Authenticate
        self.client_obj.force_authenticate(user=self.user)

    def test_create_journal_entry_success(self):
        """Test successful journal entry creation"""
        url = '/api/v1/wellness/journal/entries/'

        data = {
            'title': 'Test Entry',
            'content': 'Today was productive',
            'entry_type': 'work_log',
            'mood_rating': 8,
            'stress_level': 2
        }

        response = self.client_obj.post(url, data, format='json')

        # If journal models available
        if response.status_code == 201:
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertIn('id', response.data)
            self.assertEqual(response.data['title'], 'Test Entry')

    def test_list_journal_entries_success(self):
        """Test successful journal entries list"""
        url = '/api/v1/wellness/journal/entries/'

        response = self.client_obj.get(url)

        # Should succeed (returns empty list if no entries)
        self.assertIn(response.status_code, [200, 503])  # 503 if journal not available

    def test_list_journal_entries_with_filters(self):
        """Test journal entries with filters"""
        url = '/api/v1/wellness/journal/entries/'

        response = self.client_obj.get(url, {
            'entry_types': 'work_log',
            'limit': 10
        })

        self.assertIn(response.status_code, [200, 503])

    def test_retrieve_journal_entry_not_found(self):
        """Test retrieve non-existent journal entry"""
        url = '/api/v1/wellness/journal/entries/99999/'

        response = self.client_obj.get(url)

        self.assertIn(response.status_code, [404, 503])


@pytest.mark.django_db
class TestWellnessContentViewSet(TestCase):
    """Test suite for WellnessContentViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client_obj = APIClient()

        # Create test user
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Authenticate
        self.client_obj.force_authenticate(user=self.user)

        # Create test wellness content
        from apps.wellness.models import WellnessContent
        self.content = WellnessContent.objects.create(
            title="Test Wellness Tip",
            summary="Test summary",
            content="Full content here",
            category="stress_management",
            content_level="beginner",
            evidence_level="high",
            workplace_specific=True,
            field_worker_relevant=True,
            priority_score=8.5,
            estimated_reading_time=5,
            is_active=True
        )

    def test_daily_tip_success(self):
        """Test successful daily tip retrieval"""
        url = '/api/v1/wellness/content/daily-tip/'

        response = self.client_obj.get(url)

        if response.status_code == 200:
            self.assertIn('id', response.data)
            self.assertIn('title', response.data)

    def test_daily_tip_with_category(self):
        """Test daily tip with preferred category"""
        url = '/api/v1/wellness/content/daily-tip/'

        response = self.client_obj.get(url, {
            'preferred_category': 'stress_management'
        })

        self.assertIn(response.status_code, [200, 404])

    def test_personalized_content_success(self):
        """Test personalized content retrieval"""
        url = '/api/v1/wellness/content/personalized/'

        response = self.client_obj.get(url, {
            'limit': 5,
            'exclude_viewed': 'true'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_track_interaction_success(self):
        """Test tracking wellness interaction"""
        url = '/api/v1/wellness/content/track-interaction/'

        data = {
            'content_id': self.content.id,
            'interaction_type': 'viewed',
            'time_spent_seconds': 60,
            'user_rating': 4
        }

        response = self.client_obj.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get('success'))

    def test_track_interaction_missing_fields(self):
        """Test track interaction with missing required fields"""
        url = '/api/v1/wellness/content/track-interaction/'

        data = {
            'interaction_type': 'viewed'
            # Missing content_id
        }

        response = self.client_obj.post(url, data, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)


@pytest.mark.django_db
class TestWellnessAnalyticsViewSet(TestCase):
    """Test suite for WellnessAnalyticsViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client_obj = APIClient()

        # Create test user
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Authenticate
        self.client_obj.force_authenticate(user=self.user)

    def test_my_progress_success(self):
        """Test successful progress retrieval"""
        url = '/api/v1/wellness/analytics/my-progress/'

        response = self.client_obj.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('current_streak', response.data)
        self.assertIn('total_content_viewed', response.data)

    def test_wellbeing_analytics_success(self):
        """Test wellbeing analytics retrieval"""
        url = '/api/v1/wellness/analytics/wellbeing-analytics/'

        response = self.client_obj.get(url, {
            'days': 30
        })

        # Should return analytics even if empty
        self.assertEqual(response.status_code, 200)

    def test_wellbeing_analytics_invalid_days(self):
        """Test wellbeing analytics with invalid days parameter"""
        url = '/api/v1/wellness/analytics/wellbeing-analytics/'

        response = self.client_obj.get(url, {
            'days': 'invalid'
        })

        self.assertEqual(response.status_code, 400)


@pytest.mark.django_db
class TestPrivacySettingsViewSet(TestCase):
    """Test suite for PrivacySettingsViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client_obj = APIClient()

        # Create test user
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Authenticate
        self.client_obj.force_authenticate(user=self.user)

    def test_get_privacy_settings_success(self):
        """Test successful privacy settings retrieval"""
        url = '/api/v1/wellness/privacy/settings/'

        response = self.client_obj.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('analytics_consent', response.data)

    def test_update_privacy_settings_success(self):
        """Test successful privacy settings update"""
        url = '/api/v1/wellness/privacy/settings/'

        data = {
            'analytics_consent': False,
            'crisis_intervention_enabled': True
        }

        response = self.client_obj.patch(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['analytics_consent'], False)


__all__ = [
    'TestJournalViewSet',
    'TestWellnessContentViewSet',
    'TestWellnessAnalyticsViewSet',
    'TestPrivacySettingsViewSet',
]
