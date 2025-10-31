"""
Data Retention Policy Model

Configurable retention periods per data type for GDPR/compliance.

Retention Categories:
- sanitized_metadata: 14 days
- llm_interaction_logs: 30 days
- usage_analytics: 90 days
- aggregated_metrics: 90 days
- knowledge_documents: 365 days

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #12: Query optimization

Sprint 10.2: Data Retention Controls
"""

import logging
from django.db import models
from django.core.exceptions import ValidationError
from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class RetentionPolicy(models.Model):
    """
    Tenant-specific data retention policies.

    Defines how long different data types should be retained.
    """

    DATA_TYPE_CHOICES = [
        ('sanitized_metadata', 'Sanitized Metadata'),
        ('llm_interaction_logs', 'LLM Interaction Logs'),
        ('llm_usage_log', 'LLM Usage Analytics'),
        ('usage_analytics', 'Usage Analytics'),
        ('aggregated_metrics', 'Aggregated Metrics'),
        ('knowledge_documents', 'Knowledge Documents'),
        ('ingestion_jobs', 'Ingestion Jobs'),
        ('rejected_documents', 'Rejected Documents'),
        ('old_document_versions', 'Old Document Versions'),
        ('voice_embeddings', 'Voice Biometric Embeddings'),
        ('recommendation_traces', 'Recommendation Traces'),
        ('saga_state', 'Saga Transaction State'),
    ]

    # Identification
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='retention_policies',
        help_text="Tenant this policy applies to"
    )

    data_type = models.CharField(
        max_length=50,
        choices=DATA_TYPE_CHOICES,
        help_text="Type of data this policy covers"
    )

    # Retention period
    retention_days = models.IntegerField(
        help_text="Number of days to retain data (0 = forever)"
    )

    # Legal hold
    legal_hold = models.BooleanField(
        default=False,
        help_text="Legal hold prevents automatic purging"
    )

    legal_hold_reason = models.TextField(
        blank=True,
        help_text="Reason for legal hold"
    )

    legal_hold_until = models.DateField(
        null=True,
        blank=True,
        help_text="Date when legal hold expires"
    )

    # Status
    enabled = models.BooleanField(
        default=True,
        help_text="Policy is active"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'retention_policy'
        unique_together = [['tenant', 'data_type']]
        indexes = [
            models.Index(fields=['tenant', 'data_type']),
            models.Index(fields=['enabled']),
            models.Index(fields=['legal_hold']),
        ]
        verbose_name = "Retention Policy"
        verbose_name_plural = "Retention Policies"

    def __str__(self):
        return f"{self.tenant.name} - {self.data_type} ({self.retention_days} days)"

    def clean(self):
        """Validate retention policy."""
        super().clean()

        if self.retention_days < 0:
            raise ValidationError({'retention_days': 'Must be non-negative'})

        if self.legal_hold and not self.legal_hold_reason:
            raise ValidationError({
                'legal_hold_reason': 'Reason required when legal hold enabled'
            })

    def is_purgeable(self, record_age_days: int) -> bool:
        """
        Check if a record can be purged.

        Args:
            record_age_days: Age of record in days

        Returns:
            bool: True if can be purged
        """
        if self.legal_hold:
            return False  # Legal hold prevents purging

        if self.retention_days == 0:
            return False  # Retain forever

        return record_age_days > self.retention_days


# Default retention periods (used when no policy exists)
DEFAULT_RETENTION_DAYS = {
    'sanitized_metadata': 14,
    'llm_interaction_logs': 30,
    'llm_usage_log': 90,
    'usage_analytics': 90,
    'aggregated_metrics': 90,
    'knowledge_documents': 365,
    'ingestion_jobs': 90,
    'rejected_documents': 30,
    'old_document_versions': 365,
    'voice_embeddings': 730,  # 2 years
    'recommendation_traces': 30,
    'saga_state': 7,
}
