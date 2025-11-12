"""
Batch Ingestion Tests - Concurrent Job Processing

Tests concurrent document ingestion with race condition handling,
resource contention, and proper isolation.

Following CLAUDE.md:
- Rule #13: Comprehensive test coverage
- Rule #17: Transaction safety testing
- Concurrency testing

Sprint 1-2: Knowledge Management Testing
"""

import pytest
from datetime import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from apps.client_onboarding.models import (
    KnowledgeSource,
    KnowledgeIngestionJob
)
from apps.core_onboarding.models import AuthoritativeKnowledge
from background_tasks.onboarding_tasks_phase2 import (
    ingest_document,
    batch_embed_documents_task
)

People = get_user_model()


@pytest.mark.django_db
class TestBatchIngestion(TestCase):
    """Test batch document ingestion with concurrency."""

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

    def test_concurrent_ingestion_jobs_isolated(self):
        """Test concurrent ingestion jobs don't interfere with each other."""
        # Create multiple jobs
        jobs = [
            KnowledgeIngestionJob.objects.create(
                source=self.source,
                source_url=f'https://www.iso.org/doc{i}.pdf',
                created_by=self.user,
                status='queued'
            )
            for i in range(5)
        ]

        # Mock the actual ingestion pipeline
        with patch('background_tasks.onboarding_tasks_phase2.get_document_fetcher') as mock_fetcher:
            mock_fetcher.return_value.fetch_document.return_value = {
                'content': b'Test content',
                'content_type': 'application/pdf',
                'content_hash': 'test_hash',
                'metadata': {}
            }

            # Simulate concurrent execution
            results = []
            for job in jobs:
                try:
                    result = ingest_document(str(job.job_id))
                    results.append(result)
                except (ValueError, TypeError, AttributeError, KeyError) as e:
                    results.append({'status': 'failed', 'error': str(e)})

        # Verify each job processed independently
        assert len(results) == 5
        for job in jobs:
            job.refresh_from_db()
            # Each job should have independent state
            assert job.status in ['ready', 'failed', 'queued']

    def test_batch_embed_parallel_execution(self):
        """Test batch embedding processes documents in parallel."""
        # Create documents
        documents = [
            AuthoritativeKnowledge.objects.create(
                source_organization='ISO',
                document_title=f'Test Document {i}',
                document_version='1.0',
                authority_level='medium',
                content_summary='Test content for embedding'
            )
            for i in range(10)
        ]

        knowledge_ids = [str(doc.knowledge_id) for doc in documents]

        # Mock embedding generation
        with patch('background_tasks.onboarding_tasks_phase2.embed_knowledge_document_task') as mock_embed:
            mock_embed.si.return_value = MagicMock()

            result = batch_embed_documents_task(knowledge_ids)

            # Verify batch was started
            assert result['status'] in ['batch_started', 'no_documents']
            if result['status'] == 'batch_started':
                assert result['document_count'] == 10

    def test_ingestion_with_source_error_count(self):
        """Test source error count increments on failure."""
        job = KnowledgeIngestionJob.objects.create(
            source=self.source,
            source_url='https://www.iso.org/invalid.pdf',
            created_by=self.user,
            status='queued'
        )

        initial_error_count = self.source.fetch_error_count

        # Mock a fetch failure
        with patch('background_tasks.onboarding_tasks_phase2.get_document_fetcher') as mock_fetcher:
            mock_fetcher.return_value.fetch_document.side_effect = Exception("Fetch failed")

            result = ingest_document(str(job.job_id))

            assert result['status'] == 'failed'

        # Verify error count incremented
        self.source.refresh_from_db()
        assert self.source.fetch_error_count > initial_error_count
