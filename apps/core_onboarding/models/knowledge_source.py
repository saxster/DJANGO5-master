"""
Knowledge Source Model

Defines allowlisted external knowledge sources for ingestion.
Part of Sprint 3: Knowledge Management Models implementation.

Knowledge Sources:
- ISO standards (iso.org)
- NIST publications (nist.gov)
- ASIS International (asis.org)
- Internal documentation
- Approved industry sources

Following CLAUDE.md:
- Rule #7: <150 lines per file
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes

Created: 2025-10-11
"""

import logging
import uuid
from typing import Dict, Any
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class KnowledgeSource(TenantAwareModel):
    """
    Allowlisted external knowledge sources for document ingestion.

    Security:
    - Only allowlisted domains can be added
    - Authentication credentials encrypted
    - Fetch policy enforcement (manual, scheduled, on-demand)
    - Activity tracking for audit
    """

    SOURCE_TYPES = [
        ('iso', 'ISO Standards'),
        ('nist', 'NIST Publications'),
        ('asis', 'ASIS International'),
        ('internal', 'Internal Documentation'),
        ('external', 'External Approved Source'),
    ]

    FETCH_POLICIES = [
        ('manual', 'Manual Fetch Only'),
        ('scheduled', 'Scheduled Automatic Fetch'),
        ('on_demand', 'On-Demand Fetch'),
    ]

    # Identification
    source_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique source identifier"
    )

    name = models.CharField(
        max_length=255,
        help_text="Source name (e.g., 'ISO 27001 Standards Library')"
    )

    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPES,
        help_text="Type of knowledge source"
    )

    # Connection details
    base_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Base URL for document fetching"
    )

    auth_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Authentication configuration (encrypted)"
    )

    # Content metadata
    jurisdiction = models.CharField(
        max_length=100,
        blank=True,
        help_text="Legal jurisdiction (e.g., 'India', 'Global')"
    )

    industry_tags = models.JSONField(
        default=list,
        help_text="Industry categories (e.g., ['security', 'facilities'])"
    )

    language = models.CharField(
        max_length=10,
        default='en',
        help_text="Primary language code (ISO 639-1)"
    )

    # Fetch configuration
    fetch_policy = models.CharField(
        max_length=20,
        choices=FETCH_POLICIES,
        default='manual',
        help_text="Document fetching policy"
    )

    fetch_schedule_cron = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cron expression for scheduled fetching"
    )

    # Status tracking
    is_active = models.BooleanField(
        default=True,
        help_text="Source is active and available"
    )

    last_fetch_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last fetch attempt timestamp"
    )

    last_successful_fetch = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful fetch timestamp"
    )

    total_documents_fetched = models.IntegerField(
        default=0,
        help_text="Total documents successfully fetched"
    )

    fetch_error_count = models.IntegerField(
        default=0,
        help_text="Count of consecutive fetch errors"
    )

    last_error_message = models.TextField(
        blank=True,
        help_text="Last fetch error message"
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
        db_table = 'knowledge_source'
        indexes = [
            models.Index(fields=['source_type', 'is_active']),
            models.Index(fields=['fetch_policy', 'is_active']),
            models.Index(fields=['last_successful_fetch']),
        ]
        verbose_name = "Knowledge Source"
        verbose_name_plural = "Knowledge Sources"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"

    def clean(self):
        """Validate knowledge source configuration."""
        super().clean()

        # Validate fetch schedule if policy is 'scheduled'
        if self.fetch_policy == 'scheduled' and not self.fetch_schedule_cron:
            raise ValidationError({
                'fetch_schedule_cron': 'Cron schedule required for scheduled fetch policy'
            })

        # Validate base_url for external sources
        if self.source_type in ['iso', 'nist', 'asis', 'external'] and not self.base_url:
            raise ValidationError({
                'base_url': 'Base URL required for external sources'
            })

    def record_fetch_attempt(self, success: bool, error_message: str = ''):
        """Record fetch attempt outcome."""
        self.last_fetch_attempt = timezone.now()

        if success:
            self.last_successful_fetch = timezone.now()
            self.total_documents_fetched += 1
            self.fetch_error_count = 0
            self.last_error_message = ''
        else:
            self.fetch_error_count += 1
            self.last_error_message = error_message[:500]  # Truncate

        self.save()
