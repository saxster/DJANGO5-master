"""
Tests for PII Redaction Middleware

Comprehensive tests for journal and wellness PII redaction middleware.
Validates that sensitive data is properly sanitized in API responses.

Author: Claude Code
Date: 2025-10-01
"""

import json
import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from apps.journal.middleware.pii_redaction_middleware import JournalPIIRedactionMiddleware
from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestJournalPIIRedactionMiddleware(TestCase):
    """Test suite for Journal PII redaction middleware."""

    def setUp(self):
        """Set up test fixtures."""
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
            content="I am feeling anxious about work today",
            mood_rating=5,
            stress_level=4,
            gratitude_items=["My family", "My health"],
            affirmations=["I am enough", "I am capable"],
            stress_triggers=["Work deadline", "Team conflict"],
            privacy_scope='private'
        )

        # Initialize middleware
        self.factory = RequestFactory()
        self.get_response = lambda request: None  # Dummy response getter
        self.middleware = JournalPIIRedactionMiddleware(self.get_response)

    def test_middleware_should_process_journal_endpoints(self):
        """Test that middleware identifies journal endpoints."""
        request = self.factory.get('/journal/entries/')
        self.assertTrue(self.middleware._should_process_request(request))

        request = self.factory.get('/api/journal/entries/')
        self.assertTrue(self.middleware._should_process_request(request))

        request = self.factory.get('/other/endpoint/')
        self.assertFalse(self.middleware._should_process_request(request))

    def test_middleware_processes_json_responses_only(self):
        """Test that middleware only processes JSON responses."""
        # JSON response
        json_response = JsonResponse({'data': 'test'})
        self.assertTrue(self.middleware._is_json_response(json_response))

        # HTML response
        from django.http import HttpResponse
        html_response = HttpResponse('<html></html>', content_type='text/html')
        self.assertFalse(self.middleware._is_json_response(html_response))

    def test_owner_sees_all_data(self):
        """Test that owner can see all their own data without redaction."""
        # Create request as owner
        request = self.factory.get('/journal/entries/')
        request.user = self.owner

        # Create response with entry data
        data = {
            'id': str(self.entry.id),
            'user_id': str(self.owner.id),
            'title': self.entry.title,
            'content': self.entry.content,
            'gratitude_items': self.entry.gratitude_items,
            'stress_triggers': self.entry.stress_triggers,
            'mood_rating': self.entry.mood_rating,
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        # Parse redacted response
        redacted_data = json.loads(redacted_response.content)

        # Owner should see everything
        self.assertEqual(redacted_data['title'], self.entry.title)
        self.assertEqual(redacted_data['content'], self.entry.content)
        self.assertEqual(redacted_data['gratitude_items'], self.entry.gratitude_items)
        self.assertEqual(redacted_data['mood_rating'], self.entry.mood_rating)

    def test_non_owner_sees_redacted_sensitive_fields(self):
        """Test that non-owners see redacted sensitive fields."""
        # Create request as other user
        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        # Create response with entry data
        data = {
            'id': str(self.entry.id),
            'user_id': str(self.owner.id),  # Different user
            'title': self.entry.title,
            'content': self.entry.content,
            'gratitude_items': self.entry.gratitude_items,
            'stress_triggers': self.entry.stress_triggers,
            'mood_rating': self.entry.mood_rating,  # Safe field
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        # Parse redacted response
        redacted_data = json.loads(redacted_response.content)

        # Sensitive fields should be redacted
        self.assertEqual(redacted_data['content'], '[REDACTED]')
        self.assertEqual(redacted_data['gratitude_items'], ['[REDACTED]'] * len(self.entry.gratitude_items))
        self.assertEqual(redacted_data['stress_triggers'], ['[REDACTED]'] * len(self.entry.stress_triggers))

        # Safe metadata should still be visible
        self.assertEqual(redacted_data['mood_rating'], self.entry.mood_rating)
        self.assertEqual(redacted_data['id'], str(self.entry.id))

    def test_admin_sees_partial_redaction(self):
        """Test that admins see partially redacted data."""
        # Create request as admin
        request = self.factory.get('/journal/entries/')
        request.user = self.admin

        # Create response with entry data
        data = {
            'id': str(self.entry.id),
            'user_id': str(self.owner.id),
            'title': self.entry.title,
            'content': self.entry.content,
            'mood_rating': self.entry.mood_rating,
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        # Parse redacted response
        redacted_data = json.loads(redacted_response.content)

        # Content should still be redacted (sensitive field)
        self.assertEqual(redacted_data['content'], '[REDACTED]')

        # Admin-visible fields show redacted marker
        self.assertEqual(redacted_data['title'], '[TITLE]')

        # Safe fields visible
        self.assertEqual(redacted_data['mood_rating'], self.entry.mood_rating)

    def test_list_response_redaction(self):
        """Test that list responses are properly redacted."""
        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        # Create list response
        data = [
            {
                'id': str(self.entry.id),
                'user_id': str(self.owner.id),
                'content': self.entry.content,
                'mood_rating': self.entry.mood_rating,
            }
        ]

        response = JsonResponse(data, safe=False)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        # Parse redacted response
        redacted_data = json.loads(redacted_response.content)

        # Should be list
        self.assertIsInstance(redacted_data, list)
        self.assertEqual(len(redacted_data), 1)

        # First item should be redacted
        self.assertEqual(redacted_data[0]['content'], '[REDACTED]')
        self.assertEqual(redacted_data[0]['mood_rating'], self.entry.mood_rating)

    def test_transparency_headers_added(self):
        """Test that transparency headers are added to redacted responses."""
        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        data = {
            'id': str(self.entry.id),
            'user_id': str(self.owner.id),
            'content': self.entry.content,
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        # Check headers
        self.assertEqual(redacted_response['X-PII-Redacted'], 'true')
        self.assertEqual(redacted_response['X-Redaction-Role'], 'authenticated')

    def test_user_name_partial_redaction_for_admin(self):
        """Test that user names are partially redacted for admins."""
        request = self.factory.get('/journal/entries/')
        request.user = self.admin

        data = {
            'id': str(self.entry.id),
            'user_id': str(self.owner.id),
            'user_name': 'John Doe',
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        redacted_data = json.loads(redacted_response.content)

        # Should be partially redacted
        self.assertIn('***', redacted_data['user_name'])
        self.assertIn('J', redacted_data['user_name'])  # First letter preserved

    def test_nested_data_redaction(self):
        """Test that nested data structures are properly redacted."""
        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        data = {
            'entry': {
                'id': str(self.entry.id),
                'user_id': str(self.owner.id),
                'content': self.entry.content,
                'metadata': {
                    'gratitude_items': self.entry.gratitude_items
                }
            }
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        redacted_data = json.loads(redacted_response.content)

        # Nested content should be redacted
        self.assertEqual(redacted_data['entry']['content'], '[REDACTED]')
        self.assertEqual(
            redacted_data['entry']['metadata']['gratitude_items'],
            ['[REDACTED]'] * len(self.entry.gratitude_items)
        )

    def test_anonymous_user_sees_maximum_redaction(self):
        """Test that anonymous users see maximum redaction."""
        request = self.factory.get('/journal/entries/')
        request.user = None  # Anonymous

        data = {
            'id': str(self.entry.id),
            'title': self.entry.title,
            'content': self.entry.content,
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)

        redacted_data = json.loads(redacted_response.content)

        # Everything should be redacted
        self.assertEqual(redacted_data['title'], '[REDACTED]')
        self.assertEqual(redacted_data['content'], '[REDACTED]')

    def test_performance_overhead_acceptable(self):
        """Test that redaction performance overhead is < 10ms."""
        import time

        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        data = {
            'id': str(self.entry.id),
            'user_id': str(self.owner.id),
            'content': self.entry.content,
            'gratitude_items': self.entry.gratitude_items,
            'mood_rating': self.entry.mood_rating,
        }

        response = JsonResponse(data)

        # Measure redaction time
        start_time = time.time()
        redacted_response = self.middleware._apply_pii_redaction(request, response)
        elapsed_ms = (time.time() - start_time) * 1000

        # Should be < 10ms
        self.assertLess(elapsed_ms, 10.0,
                       f"Redaction took {elapsed_ms:.2f}ms (target: <10ms)")

    def test_exception_handling_graceful(self):
        """Test that middleware handles exceptions gracefully."""
        request = self.factory.get('/journal/entries/')
        request.user = self.other_user

        # Invalid JSON response
        from django.http import HttpResponse
        invalid_response = HttpResponse('{invalid json}', content_type='application/json')

        # Should not raise exception
        result = self.middleware._apply_pii_redaction(request, invalid_response)

        # Should return original response
        self.assertEqual(result, invalid_response)


@pytest.mark.django_db
class TestPIIRedactionEdgeCases(TestCase):
    """Test edge cases for PII redaction."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = JournalPIIRedactionMiddleware(lambda r: None)

    def test_empty_data_structures(self):
        """Test handling of empty data structures."""
        request = self.factory.get('/journal/entries/')
        request.user = None

        data = {
            'content': '',
            'gratitude_items': [],
            'tags': None,
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)
        redacted_data = json.loads(redacted_response.content)

        # Empty structures should be preserved
        self.assertEqual(redacted_data['content'], '')
        self.assertEqual(redacted_data['gratitude_items'], [])
        self.assertIsNone(redacted_data['tags'])

    def test_unicode_content_redaction(self):
        """Test redaction of Unicode content."""
        request = self.factory.get('/journal/entries/')
        request.user = None

        data = {
            'content': '感謝しています',  # Japanese
            'title': 'Título en español',  # Spanish
        }

        response = JsonResponse(data)
        redacted_response = self.middleware._apply_pii_redaction(request, response)
        redacted_data = json.loads(redacted_response.content)

        # Should be redacted regardless of language
        self.assertEqual(redacted_data['content'], '[REDACTED]')
        self.assertEqual(redacted_data['title'], '[REDACTED]')
