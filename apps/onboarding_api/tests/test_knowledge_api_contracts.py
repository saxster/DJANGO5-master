"""
Knowledge API Contract Tests - Two-Person Approval Workflow

Comprehensive API contract validation for knowledge management endpoints.
Validates request/response schemas, error handling, and security controls.

Following CLAUDE.md:
- Rule #13: Comprehensive test coverage
- Rule #11: Specific exception testing
- API contract compliance

Sprint 1-2: Knowledge Management Testing
"""

import pytest
import json
from datetime import datetime
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.onboarding.models import (
    KnowledgeSource,
    KnowledgeIngestionJob,
    AuthoritativeKnowledge,
    KnowledgeReview
)

People = get_user_model()


@pytest.mark.django_db
class TestKnowledgeSourceAPI(TestCase):
    """Test knowledge source CRUD endpoints."""

    def setUp(self):
        """Setup test data."""
        self.client = Client()
        self.user = People.objects.create_user(
            peoplename='Test User',
            loginid='testuser',
            email='test@example.com',
            is_staff=True
        )
        self.client.force_login(self.user)

    def test_list_knowledge_sources(self):
        """Test GET /api/knowledge/sources/ lists sources."""
        # Create test source
        source = KnowledgeSource.objects.create(
            name='ISO Standards',
            source_type='iso',
            base_url='https://www.iso.org',
            is_active=True
        )

        response = self.client.get('/api/knowledge/sources/')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert len(data['sources']) >= 1
        assert 'pagination' in data

    def test_create_knowledge_source_allowlisted(self):
        """Test POST /api/knowledge/sources/ with allowlisted domain."""
        payload = {
            'name': 'NIST Publications',
            'source_type': 'nist',
            'base_url': 'https://www.nist.gov',
            'jurisdiction': 'USA',
            'language': 'en'
        }

        response = self.client.post(
            '/api/knowledge/sources/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 201
        data = response.json()
        assert data['status'] == 'created'
        assert 'source' in data

    def test_create_knowledge_source_not_allowlisted(self):
        """Test POST with non-allowlisted domain is rejected."""
        payload = {
            'name': 'Malicious Source',
            'source_type': 'external',
            'base_url': 'https://evil.com',
            'language': 'en'
        }

        response = self.client.post(
            '/api/knowledge/sources/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 403
        data = response.json()
        assert 'not allowlisted' in data['error'].lower()


@pytest.mark.django_db
class TestDocumentReviewWorkflow(TestCase):
    """Test two-person approval review workflow."""

    def setUp(self):
        """Setup test data."""
        self.client = Client()

        # Create first reviewer (Subject Matter Expert)
        self.first_reviewer = People.objects.create_user(
            peoplename='SME Reviewer',
            loginid='sme_reviewer',
            email='sme@example.com',
            is_staff=True
        )

        # Create second reviewer (Quality Assurance)
        self.second_reviewer = People.objects.create_user(
            peoplename='QA Reviewer',
            loginid='qa_reviewer',
            email='qa@example.com',
            is_staff=True
        )

        # Create test document
        self.document = AuthoritativeKnowledge.objects.create(
            source_organization='ISO',
            document_title='ISO 27001 Standard',
            document_version='2022',
            authority_level='high',
            content_summary='Test document',
            is_current=False
        )

        # Create draft review
        self.review = KnowledgeReview.objects.create(
            document=self.document,
            status='draft',
            notes='Initial draft review'
        )

    def test_first_review_approval(self):
        """Test first review approval transitions to second_review."""
        self.client.force_login(self.first_reviewer)

        payload = {
            'document_id': str(self.document.knowledge_id),
            'review_type': 'first',
            'decision': 'approve',
            'notes': 'Content is accurate and complete',
            'accuracy_score': 0.95,
            'completeness_score': 0.90,
            'relevance_score': 0.92
        }

        response = self.client.post(
            '/api/knowledge/reviews/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['result']['status'] == 'second_review'
        assert data['result']['next_step'] == 'Assign second reviewer'

        # Verify database state
        self.review.refresh_from_db()
        assert self.review.status == 'second_review'
        assert self.review.first_reviewer == self.first_reviewer
        assert self.review.first_reviewed_at is not None

    def test_second_review_approval_enables_publication(self):
        """Test second review approval enables publication."""
        # Setup: First review already approved
        self.review.status = 'second_review'
        self.review.first_reviewer = self.first_reviewer
        self.review.first_reviewed_at = datetime.now()
        self.review.accuracy_score = 0.95
        self.review.completeness_score = 0.90
        self.review.relevance_score = 0.92
        self.review.save()

        self.client.force_login(self.second_reviewer)

        payload = {
            'document_id': str(self.document.knowledge_id),
            'review_type': 'second',
            'decision': 'approve',
            'notes': 'Quality validated, approved for publication'
        }

        response = self.client.post(
            '/api/knowledge/reviews/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['result']['status'] == 'approved'
        assert data['result']['next_step'] == 'Publish document'

        # Verify database state
        self.review.refresh_from_db()
        assert self.review.status == 'approved'
        assert self.review.approved_for_publication is True
        assert self.review.second_reviewer == self.second_reviewer
        assert self.review.second_reviewed_at is not None

    def test_publish_requires_two_person_approval(self):
        """Test publish endpoint enforces two-person approval gate."""
        # Case 1: No approval - should fail
        response = self.client.post(
            f'/api/knowledge/documents/{self.document.knowledge_id}/publish'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'two-person approval' in data['message'].lower()

        # Case 2: Only first review - should fail
        self.review.status = 'second_review'
        self.review.first_reviewer = self.first_reviewer
        self.review.first_reviewed_at = datetime.now()
        self.review.save()

        response = self.client.post(
            f'/api/knowledge/documents/{self.document.knowledge_id}/publish'
        )

        assert response.status_code == 400

        # Case 3: Both reviews approved - should succeed
        self.review.status = 'approved'
        self.review.second_reviewer = self.second_reviewer
        self.review.second_reviewed_at = datetime.now()
        self.review.approved_for_publication = True
        self.review.save()

        response = self.client.post(
            f'/api/knowledge/documents/{self.document.knowledge_id}/publish'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'published'
        assert 'first_reviewer' in data['approved_by']
        assert 'second_reviewer' in data['approved_by']

        # Verify document is published
        self.document.refresh_from_db()
        assert self.document.is_current is True

    def test_first_review_rejection_prevents_second_review(self):
        """Test first reviewer rejection prevents second review."""
        self.client.force_login(self.first_reviewer)

        payload = {
            'document_id': str(self.document.knowledge_id),
            'review_type': 'first',
            'decision': 'reject',
            'notes': 'Contains factual errors, needs revision',
            'accuracy_score': 0.4,
            'completeness_score': 0.5,
            'relevance_score': 0.6
        }

        response = self.client.post(
            '/api/knowledge/reviews/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['result']['status'] == 'rejected'

        # Verify document stays unpublished
        self.review.refresh_from_db()
        assert self.review.status == 'rejected'
        assert self.review.approved_for_publication is False
