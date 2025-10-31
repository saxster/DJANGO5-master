"""
Failure Recovery Tests - Retry Logic and Rollbacks

Tests ingestion pipeline failure recovery, retry mechanisms,
and proper cleanup on errors.

Following CLAUDE.md:
- Rule #13: Comprehensive test coverage
- Rule #17: Transaction rollback testing
- Error handling validation

Sprint 1-2: Knowledge Management Testing
"""

import pytest
from datetime import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from apps.onboarding.models import (
    KnowledgeSource,
    KnowledgeIngestionJob,
    AuthoritativeKnowledge,
    AuthoritativeKnowledgeChunk
)
from background_tasks.onboarding_tasks_phase2 import (
    ingest_document,
    reembed_document
)

People = get_user_model()


@pytest.mark.django_db
class TestFailureRecovery(TestCase):
    """Test failure recovery and retry logic."""

    def setUp(self):
        """Setup test data."""
        self.user = People.objects.create_user(
            peoplename='Test User',
            loginid='testuser',
            email='test@example.com'
        )

        self.source = KnowledgeSource.objects.create(
            name='Test Source',
            source_type='iso',
            base_url='https://www.iso.org',
            is_active=True
        )

    def test_fetch_failure_updates_job_status(self):
        """Test fetch failure updates job to failed status."""
        job = KnowledgeIngestionJob.objects.create(
            source=self.source,
            source_url='https://www.iso.org/nonexistent.pdf',
            created_by=self.user,
            status='queued'
        )

        # Mock fetch failure
        with patch('background_tasks.onboarding_tasks_phase2.get_document_fetcher') as mock_fetcher:
            mock_fetcher.return_value.fetch_document.side_effect = Exception("404 Not Found")

            result = ingest_document(str(job.job_id))

            assert result['status'] == 'failed'
            assert '404' in result['error']

        # Verify job status
        job.refresh_from_db()
        assert job.status == 'failed'
        assert job.retry_count > 0
        assert 'Not Found' in job.error_log

    def test_sanitization_failure_stops_pipeline(self):
        """Test content sanitization failure prevents ingestion."""
        job = KnowledgeIngestionJob.objects.create(
            source=self.source,
            source_url='https://www.iso.org/malicious.pdf',
            created_by=self.user,
            status='queued'
        )

        # Mock fetch success but sanitization detects malicious content
        with patch('background_tasks.onboarding_tasks_phase2.get_document_fetcher') as mock_fetcher, \
             patch('background_tasks.onboarding_tasks_phase2.ContentSanitizationService') as mock_sanitizer:

            mock_fetcher.return_value.fetch_document.return_value = {
                'content': '<script>alert("xss")</script>',
                'content_type': 'text/html',
                'content_hash': 'malicious_hash',
                'metadata': {}
            }

            from apps.onboarding_api.services.knowledge.exceptions import SecurityError
            mock_sanitizer.return_value.sanitize_document_content.side_effect = SecurityError(
                "Malicious patterns detected"
            )

            result = ingest_document(str(job.job_id))

            assert result['status'] == 'failed'
            assert 'malicious' in result['error'].lower() or 'security' in result['error'].lower()

        # Verify job failed and no document created
        job.refresh_from_db()
        assert job.status == 'failed'
        assert job.document is None

    def test_embedding_failure_does_not_create_document(self):
        """Test embedding failure prevents document creation."""
        job = KnowledgeIngestionJob.objects.create(
            source=self.source,
            source_url='https://www.iso.org/test.pdf',
            created_by=self.user,
            status='queued'
        )

        # Mock successful fetch/parse but failed embedding
        with patch('background_tasks.onboarding_tasks_phase2.get_document_fetcher') as mock_fetcher, \
             patch('background_tasks.onboarding_tasks_phase2.get_document_parser') as mock_parser, \
             patch('background_tasks.onboarding_tasks_phase2.get_embedding_generator') as mock_embedder, \
             patch('background_tasks.onboarding_tasks_phase2.ContentSanitizationService') as mock_sanitizer:

            mock_fetcher.return_value.fetch_document.return_value = {
                'content': 'Test content',
                'content_type': 'text/plain',
                'content_hash': 'test_hash',
                'metadata': {}
            }

            mock_sanitizer.return_value.sanitize_document_content.return_value = (
                'Test content', {'sanitized': True}
            )

            mock_parser.return_value.parse_document.return_value = {
                'full_text': 'Test content',
                'document_info': {'title': 'Test'},
                'parser_metadata': {}
            }

            mock_embedder.return_value.generate_embedding.side_effect = Exception("Embedding API failure")

            result = ingest_document(str(job.job_id))

            assert result['status'] == 'failed'

        # Verify cleanup occurred
        job.refresh_from_db()
        assert job.status == 'failed'

    def test_reembedding_preserves_document_on_failure(self):
        """Test re-embedding failure doesn't delete original embeddings."""
        # Create document with existing embeddings
        document = AuthoritativeKnowledge.objects.create(
            source_organization='ISO',
            document_title='Existing Document',
            document_version='1.0',
            authority_level='high',
            content_summary='Test document',
            ingestion_version=1
        )

        # Create chunks
        for i in range(5):
            AuthoritativeKnowledgeChunk.objects.create(
                knowledge=document,
                chunk_index=i,
                chunk_text='Test chunk',
                is_current=True
            )

        initial_version = document.ingestion_version

        # Mock re-embedding failure
        with patch('background_tasks.onboarding_tasks_phase2.get_embedding_generator') as mock_embedder:
            mock_embedder.return_value.generate_embedding.side_effect = Exception("Re-embedding failed")

            result = reembed_document(str(document.knowledge_id), {})

            assert result['status'] == 'failed'

        # Verify document and chunks still exist
        document.refresh_from_db()
        assert document.ingestion_version == initial_version  # Not incremented
        assert AuthoritativeKnowledgeChunk.objects.filter(knowledge=document).count() == 5
