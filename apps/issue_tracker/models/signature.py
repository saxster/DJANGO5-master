"""
AnomalySignature Model
Unique fingerprint of an anomaly pattern for tracking recurrences
"""

import uuid
from django.db import models
from django.utils import timezone

from .enums import SEVERITY_CHOICES, SIGNATURE_STATUS_CHOICES


class AnomalySignature(models.Model):
    """
    Unique fingerprint of an anomaly pattern for tracking recurrences
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Unique signature hash
    signature_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hash of anomaly signature"
    )

    # Anomaly classification
    anomaly_type = models.CharField(
        max_length=50,
        help_text="Type of anomaly (latency, error, schema, etc.)"
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=SIGNATURE_STATUS_CHOICES,
        default='active'
    )

    # Pattern definition
    pattern = models.JSONField(
        help_text="Pattern definition for anomaly detection"
    )

    # Signature metadata
    endpoint_pattern = models.CharField(max_length=200)
    error_class = models.CharField(max_length=100, blank=True)
    schema_signature = models.TextField(blank=True)

    # Tracking metrics
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    occurrence_count = models.IntegerField(default=1)

    # Resolution tracking
    mttr_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Mean Time To Resolution in seconds"
    )
    mtbf_hours = models.FloatField(
        null=True,
        blank=True,
        help_text="Mean Time Between Failures in hours"
    )

    # Tags for categorization
    tags = models.JSONField(
        default=list,
        help_text="Tags for categorization and search"
    )

    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['signature_hash']),
            models.Index(fields=['anomaly_type', 'severity']),
            models.Index(fields=['status', 'last_seen']),
            models.Index(fields=['endpoint_pattern']),
        ]

    def __str__(self):
        return f"{self.anomaly_type} - {self.endpoint_pattern}"

    @property
    def is_recurring(self):
        """Check if this is a recurring issue"""
        return self.occurrence_count > 3

    @property
    def severity_score(self):
        """Get numeric severity score for prioritization"""
        scores = {'info': 1, 'warning': 2, 'error': 3, 'critical': 4}
        return scores.get(self.severity, 1)

    def update_occurrence(self):
        """Update occurrence tracking"""
        self.occurrence_count += 1
        self.last_seen = timezone.now()
        self.save()

    def calculate_mttr(self):
        """Calculate MTTR from resolved occurrences"""
        resolved_occurrences = self.occurrences.filter(
            status='resolved',
            resolved_at__isnull=False
        )

        if not resolved_occurrences.exists():
            return None

        total_resolution_time = 0
        count = 0

        for occurrence in resolved_occurrences:
            if occurrence.created_at and occurrence.resolved_at:
                resolution_time = (
                    occurrence.resolved_at - occurrence.created_at
                ).total_seconds()
                total_resolution_time += resolution_time
                count += 1

        if count > 0:
            self.mttr_seconds = int(total_resolution_time / count)
            self.save()

        return self.mttr_seconds
