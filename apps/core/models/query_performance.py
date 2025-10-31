"""
Query Performance Monitoring Models

Models for tracking PostgreSQL query performance metrics using pg_stat_statements.
Enables historical analysis, alerting, and performance trend monitoring.

Features:
- Historical query performance tracking
- Slow query detection and alerting
- Query pattern analysis
- Performance trend monitoring
- Automatic cleanup of old data

Compliance:
- Rule #7: Model < 150 lines (each model under limit)
- Rule #12: Query optimization with indexes
- Enterprise monitoring standards
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import hashlib
import re


class QueryPerformanceSnapshot(models.Model):
    """
    Historical snapshots of query performance from pg_stat_statements.

    Captures periodic snapshots to track performance trends over time.
    Used for detecting performance degradation and optimization opportunities.
    """

    # Snapshot identification
    snapshot_time = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When this snapshot was taken"
    )

    # Query identification (from pg_stat_statements)
    query_hash = models.BigIntegerField(
        db_index=True,
        help_text="PostgreSQL query hash (queryid from pg_stat_statements)"
    )

    query_text = models.TextField(
        help_text="Full query text (truncated if necessary)"
    )

    query_preview = models.CharField(
        max_length=200,
        help_text="First 200 characters of query for quick identification"
    )

    # Performance metrics
    calls = models.BigIntegerField(
        default=0,
        help_text="Number of times this query was executed"
    )

    total_exec_time = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total execution time in milliseconds"
    )

    mean_exec_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Average execution time in milliseconds"
    )

    max_exec_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Maximum execution time in milliseconds"
    )

    # Resource usage metrics
    rows_returned = models.BigIntegerField(
        default=0,
        help_text="Total number of rows returned/affected"
    )

    shared_blks_hit = models.BigIntegerField(
        default=0,
        help_text="Shared blocks hit (cache hits)"
    )

    shared_blks_read = models.BigIntegerField(
        default=0,
        help_text="Shared blocks read from disk"
    )

    temp_blks_written = models.BigIntegerField(
        default=0,
        help_text="Temporary blocks written to disk"
    )

    class Meta:
        db_table = 'query_performance_snapshots'
        ordering = ['-snapshot_time']
        indexes = [
            models.Index(fields=['query_hash', 'snapshot_time']),
            models.Index(fields=['snapshot_time']),
            models.Index(fields=['mean_exec_time']),
            models.Index(fields=['calls']),
            models.Index(fields=['total_exec_time']),
        ]
        verbose_name = 'Query Performance Snapshot'
        verbose_name_plural = 'Query Performance Snapshots'

    def __str__(self):
        return f"Query {self.query_hash} at {self.snapshot_time}"

    @property
    def avg_rows_per_call(self):
        """Calculate average rows per query execution."""
        return self.rows_returned / self.calls if self.calls > 0 else 0

    @property
    def cache_hit_ratio(self):
        """Calculate cache hit ratio percentage."""
        total_blocks = self.shared_blks_hit + self.shared_blks_read
        if total_blocks > 0:
            return (self.shared_blks_hit / total_blocks) * 100
        return 0

    @classmethod
    def cleanup_old_snapshots(cls, days=30):
        """Remove old performance snapshots to manage storage."""
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(snapshot_time__lt=cutoff).delete()
        return deleted


class SlowQueryAlert(models.Model):
    """
    Alerts for queries that exceed performance thresholds.

    Automatically created when queries are detected as slow or problematic.
    Used for proactive performance monitoring and alerting.
    """

    SEVERITY_CHOICES = [
        ('info', 'Informational'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('emergency', 'Emergency'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]

    # Alert identification
    alert_time = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When this alert was created"
    )

    query_hash = models.BigIntegerField(
        db_index=True,
        help_text="PostgreSQL query hash that triggered the alert"
    )

    # Alert details
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='warning',
        db_index=True,
        help_text="Alert severity level"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        db_index=True,
        help_text="Current alert status"
    )

    alert_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of performance issue detected"
    )

    # Performance metrics that triggered alert
    execution_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Execution time that triggered alert (ms)"
    )

    threshold_exceeded = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Threshold value that was exceeded"
    )

    query_text = models.TextField(
        help_text="Query that triggered the alert"
    )

    # Alert management
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_query_alerts',
        help_text="User who acknowledged this alert"
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this alert was acknowledged"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this alert was resolved"
    )

    notes = models.TextField(
        blank=True,
        help_text="Investigation notes and resolution details"
    )

    class Meta:
        db_table = 'slow_query_alerts'
        ordering = ['-alert_time']
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['alert_time', 'severity']),
            models.Index(fields=['query_hash', 'alert_time']),
            models.Index(fields=['alert_type', 'status']),
        ]
        verbose_name = 'Slow Query Alert'
        verbose_name_plural = 'Slow Query Alerts'

    def __str__(self):
        return f"{self.severity.upper()} - Query {self.query_hash} ({self.execution_time}ms)"

    def acknowledge(self, user, notes=""):
        """Mark alert as acknowledged by a user."""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        if notes:
            self.notes = f"{self.notes}\n[{timezone.now()}] Acknowledged: {notes}"
        self.save()

    def resolve(self, notes=""):
        """Mark alert as resolved."""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        if notes:
            self.notes = f"{self.notes}\n[{timezone.now()}] Resolved: {notes}"
        self.save()

    @classmethod
    def cleanup_old_alerts(cls, days=90):
        """Remove old resolved alerts."""
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(
            status__in=['resolved', 'false_positive'],
            alert_time__lt=cutoff
        ).delete()
        return deleted


class QueryPattern(models.Model):
    """
    Normalized query patterns for analysis and grouping.

    Groups similar queries together by removing literals and parameters
    to identify common query patterns and optimization opportunities.
    """

    pattern_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Hash of normalized query pattern"
    )

    pattern_text = models.TextField(
        help_text="Normalized query pattern with placeholders"
    )

    query_type = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Type of query (SELECT, INSERT, UPDATE, DELETE, etc.)"
    )

    # Pattern statistics
    first_seen = models.DateTimeField(
        default=timezone.now,
        help_text="When this pattern was first observed"
    )

    last_seen = models.DateTimeField(
        default=timezone.now,
        help_text="When this pattern was last observed"
    )

    total_queries = models.BigIntegerField(
        default=0,
        help_text="Total number of queries matching this pattern"
    )

    avg_execution_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Average execution time for this pattern"
    )

    class Meta:
        db_table = 'query_patterns'
        ordering = ['-total_queries']
        indexes = [
            models.Index(fields=['pattern_hash']),
            models.Index(fields=['query_type', 'avg_execution_time']),
            models.Index(fields=['last_seen']),
        ]
        verbose_name = 'Query Pattern'
        verbose_name_plural = 'Query Patterns'

    def __str__(self):
        return f"{self.query_type} pattern ({self.total_queries} queries)"

    @staticmethod
    def normalize_query(query_text):
        """
        Normalize query by replacing literals with placeholders.

        Args:
            query_text: Raw SQL query text

        Returns:
            tuple: (normalized_pattern, pattern_hash)
        """
        # Basic normalization - replace numeric literals and strings
        normalized = re.sub(r'\b\d+\b', '?', query_text)
        normalized = re.sub(r"'[^']*'", '?', normalized)
        normalized = re.sub(r'"[^"]*"', '?', normalized)
        normalized = re.sub(r'\s+', ' ', normalized.strip())

        # Generate hash for the pattern
        pattern_hash = hashlib.sha256(normalized.encode()).hexdigest()

        return normalized, pattern_hash

    @classmethod
    def update_pattern_stats(cls, query_text, execution_time):
        """Update statistics for a query pattern."""
        normalized, pattern_hash = cls.normalize_query(query_text)

        # Extract query type
        query_type = 'UNKNOWN'
        for qtype in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH']:
            if normalized.upper().strip().startswith(qtype):
                query_type = qtype
                break

        # Update or create pattern
        pattern, created = cls.objects.get_or_create(
            pattern_hash=pattern_hash,
            defaults={
                'pattern_text': normalized,
                'query_type': query_type,
                'total_queries': 1,
                'avg_execution_time': execution_time,
            }
        )

        if not created:
            # Update statistics
            pattern.last_seen = timezone.now()
            pattern.total_queries += 1
            # Calculate rolling average
            pattern.avg_execution_time = (
                (pattern.avg_execution_time * (pattern.total_queries - 1)) +
                execution_time
            ) / pattern.total_queries
            pattern.save()

        return pattern