"""
Knowledge Ingestion Job Model

Tracks document ingestion pipeline from fetch to embedding generation.
Part of Sprint 3: Knowledge Management Models implementation.

Pipeline Stages:
1. QUEUED - Job created, waiting to start
2. FETCHING - Downloading document from source
3. PARSING - Extracting text/metadata from document
4. CHUNKING - Splitting document into semantic chunks
5. EMBEDDING - Generating vector embeddings
6. READY - Complete and ready for search
7. FAILED - Error occurred

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes

Created: 2025-10-11
"""

import logging
import uuid
from datetime import timedelta
from typing import Dict, Any
from django.db import models
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.onboarding.models.knowledge_source import KnowledgeSource
from apps.onboarding.models.conversational_ai import AuthoritativeKnowledge
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class KnowledgeIngestionJob(TenantAwareModel):
    """
    Document ingestion pipeline job tracker.

    Tracks progress of document fetch → parse → chunk → embed pipeline
    with comprehensive timing and error logging.
    """

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('fetching', 'Fetching Document'),
        ('parsing', 'Parsing Content'),
        ('chunking', 'Creating Chunks'),
        ('embedding', 'Generating Embeddings'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    # Identification
    job_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique job identifier"
    )

    # Relationships
    source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name='ingestion_jobs',
        help_text="Knowledge source"
    )

    document = models.ForeignKey(
        AuthoritativeKnowledge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ingestion_jobs',
        help_text="Created/updated document (null until created)"
    )

    created_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_ingestion_jobs',
        help_text="User who initiated ingestion"
    )

    # Source information
    source_url = models.URLField(
        max_length=500,
        help_text="Specific document URL to ingest"
    )

    # Pipeline status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='queued',
        help_text="Current pipeline stage"
    )

    # Processing metrics
    chunks_created = models.IntegerField(
        default=0,
        help_text="Number of chunks created"
    )

    embeddings_generated = models.IntegerField(
        default=0,
        help_text="Number of embeddings generated"
    )

    processing_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total processing time in milliseconds"
    )

    # Timing breakdown
    timings = models.JSONField(
        default=dict,
        help_text="Stage-wise timing breakdown (fetch, parse, chunk, embed)"
    )

    # Configuration
    processing_config = models.JSONField(
        default=dict,
        help_text="Processing configuration (chunk size, model, etc.)"
    )

    # Error tracking
    error_log = models.TextField(
        blank=True,
        help_text="Error messages and stack traces"
    )

    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )

    # Timestamps
    cdtz = models.DateTimeField(
        auto_now_add=True,
        help_text="Created datetime"
    )

    mdtz = models.DateTimeField(
        auto_now=True,
        help_text="Modified datetime"
    )

    class Meta:
        db_table = 'knowledge_ingestion_job'
        indexes = [
            models.Index(fields=['status', 'cdtz']),
            models.Index(fields=['source', 'status']),
            models.Index(fields=['created_by', 'cdtz']),
            models.Index(fields=['document']),
        ]
        verbose_name = "Knowledge Ingestion Job"
        verbose_name_plural = "Knowledge Ingestion Jobs"
        ordering = ['-cdtz']

    def __str__(self):
        return f"{self.source.name} - {self.source_url[:50]} ({self.status})"

    def update_status(self, new_status: str, error_message: str = ''):
        """
        Update job status with timestamp.

        Args:
            new_status: New status value
            error_message: Error message (if status=failed)
        """
        self.status = new_status

        if new_status == 'failed' and error_message:
            self.error_log += f"\n[{timezone.now().isoformat()}] {error_message}"
            self.retry_count += 1

        self.save()
        logger.info(f"Ingestion job {self.job_id} status: {new_status}")

    def record_timing(self, stage: str, duration_ms: int):
        """
        Record timing for pipeline stage.

        Args:
            stage: Pipeline stage name (fetch, parse, chunk, embed)
            duration_ms: Duration in milliseconds
        """
        if not self.timings:
            self.timings = {}

        self.timings[stage] = duration_ms
        self.save()

        logger.debug(f"Ingestion job {self.job_id} {stage}: {duration_ms}ms")

    def is_stale(self, threshold_hours: int = 24) -> bool:
        """
        Check if job is stale (stuck in processing).

        Args:
            threshold_hours: Hours before job considered stale

        Returns:
            bool: True if stale
        """
        if self.status in ['ready', 'failed']:
            return False  # Terminal states

        age = timezone.now() - self.cdtz
        return age > timedelta(hours=threshold_hours)
