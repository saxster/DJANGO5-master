"""
Unit Tests for HelpBot ViewSets

Tests helpbot endpoints:
- POST /api/v1/helpbot/sessions/
- POST /api/v1/helpbot/sessions/{id}/messages/
- GET /api/v1/helpbot/sessions/{id}/history/
- POST /api/v1/helpbot/sessions/{id}/feedback/
- GET /api/v1/helpbot/knowledge/search/
- GET /api/v1/helpbot/knowledge/articles/{id}/

Compliance with .claude/rules.md:
- Specific exception testing
- 80% coverage target
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from apps.peoples.models import People
from apps.tenants.models import Client


@pytest.mark.django_db
class TestHelpBotViewSet(TestCase):
    """Test suite for HelpBotViewSet"""

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

        # Create test session ID
        self.session_id = str(uuid.uuid4())

    def test_create_session_success(self):
        """Test successful helpbot session creation"""
        url = '/api/v1/helpbot/sessions/'

        data = {
            'context': 'I need help with tasks',
            'user_role': 'field_worker'
        }

        response = self.client_obj.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('session_id', response.data)
        self.assertIn('message', response.data)

    def test_send_message_success(self):
        """Test sending message to helpbot"""
        url = f'/api/v1/helpbot/sessions/{self.session_id}/messages/'

        data = {
            'message': 'How do I complete a task?'
        }

        response = self.client_obj.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('response', response.data)

    def test_send_message_missing_message(self):
        """Test sending message without message field"""
        url = f'/api/v1/helpbot/sessions/{self.session_id}/messages/'

        response = self.client_obj.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_get_session_history_success(self):
        """Test successful session history retrieval"""
        url = f'/api/v1/helpbot/sessions/{self.session_id}/history/'

        response = self.client_obj.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('session_id', response.data)
        self.assertIn('messages', response.data)

    def test_submit_feedback_success(self):
        """Test successful feedback submission"""
        url = f'/api/v1/helpbot/sessions/{self.session_id}/feedback/'

        data = {
            'rating': 5,
            'feedback': 'Very helpful!'
        }

        response = self.client_obj.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        self.assertTrue(response.data['success'])

    def test_unauthenticated_access(self):
        """Test that unauthenticated requests are rejected"""
        self.client_obj.force_authenticate(user=None)
        url = '/api/v1/helpbot/sessions/'

        response = self.client_obj.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class TestKnowledgeViewSet(TestCase):
    """Test suite for KnowledgeViewSet"""

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

    def test_search_knowledge_success(self):
        """Test successful knowledge base search"""
        url = '/api/v1/helpbot/knowledge/search/'

        response = self.client_obj.get(url, {
            'query': 'task management',
            'limit': 10
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)

    def test_search_knowledge_invalid_limit(self):
        """Test knowledge search with invalid limit"""
        url = '/api/v1/helpbot/knowledge/search/'

        response = self.client_obj.get(url, {
            'query': 'test',
            'limit': 'invalid'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_knowledge_article_success(self):
        """Test successful knowledge article retrieval"""
        url = '/api/v1/helpbot/knowledge/articles/1/'

        response = self.client_obj.get(url)

        # Should return article data or 404
        self.assertIn(response.status_code, [200, 404])

    def test_get_knowledge_article_invalid_id(self):
        """Test knowledge article with invalid ID"""
        url = '/api/v1/helpbot/knowledge/articles/invalid/'

        response = self.client_obj.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


__all__ = [
    'TestBusinessUnitViewSet',
    'TestKnowledgeViewSet',
]
