"""
Task Failure Record Model

Stores information about failed Celery tasks for Dead Letter Queue (DLQ) processing.
Enables manual retry, failure analysis, and automated recovery.

Related Files:
- background_tasks/dead_letter_queue.py - DLQ service implementation
- apps/core/views/task_monitoring_dashboard.py - Admin dashboard
"""

from django.db import models
from django.utils import timezone
from django.conf import settings
from apps.tenants.models import TenantAwareModel
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR


class TaskFailureRecord(TenantAwareModel):
    """
    Records failed task executions for DLQ processing and analysis.

    DLQ Workflow:
    1. Task fails after max retries → Create record
    2. Automatic retry with exponential backoff (if transient)
    3. Manual review and retry via admin dashboard (if permanent)
    4. Failure pattern analysis for alerting

    Indexes:
    - status + next_retry_at: Fast DLQ processing queries
    - task_name + status: Failure rate analysis
    - correlation_id: Request tracing
    """

    # Failure taxonomy
    FAILURE_TYPE_CHOICES = [
        ('TRANSIENT', 'Transient Failure'),        # Network timeout, DB deadlock
        ('PERMANENT', 'Permanent Failure'),        # Validation error, missing data
        ('CONFIGURATION', 'Configuration Error'),  # Missing settings, invalid config
        ('EXTERNAL', 'External Service Failure'),  # 3rd party API down
        ('UNKNOWN', 'Unknown Failure'),            # Unexpected exception
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Retry'),
        ('RETRYING', 'Retrying'),
        ('RESOLVED', 'Resolved'),
        ('ABANDONED', 'Abandoned'),  # Max retries exceeded or manual abandonment
    ]

    # Task identification
    task_id = models.CharField(max_length=255, db_index=True, help_text="Celery task ID")
    task_name = models.CharField(max_length=255, db_index=True, help_text="Task name (e.g., 'auto_close_jobs')")
    correlation_id = models.CharField(max_length=100, db_index=True, null=True, blank=True,
                                     help_text="Request correlation ID for tracing")

    # Task execution context
    task_args = models.JSONField(default=list, help_text="Task positional arguments")
    task_kwargs = models.JSONField(default=dict, help_text="Task keyword arguments")

    # Failure information
    failure_type = models.CharField(max_length=20, choices=FAILURE_TYPE_CHOICES, default='UNKNOWN',
                                   db_index=True, help_text="Failure category for automated handling")
    exception_type = models.CharField(max_length=255, help_text="Exception class name (e.g., 'DatabaseError')")
    exception_message = models.TextField(help_text="Exception message (sanitized, no sensitive data)")
    traceback = models.TextField(help_text="Exception traceback for debugging")

    # Retry management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    retry_count = models.IntegerField(default=0, help_text="Number of DLQ retry attempts")
    max_retries = models.IntegerField(default=3, help_text="Maximum DLQ retry attempts before abandonment")
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True,
                                        help_text="Next automatic retry timestamp")
    last_retry_at = models.DateTimeField(null=True, blank=True, help_text="Last retry attempt timestamp")

    # Timestamps
    first_failed_at = models.DateTimeField(auto_now_add=True, help_text="Initial failure timestamp")
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="Resolution timestamp")
    abandoned_at = models.DateTimeField(null=True, blank=True, help_text="Abandonment timestamp")

    # Metadata
    worker_hostname = models.CharField(max_length=255, null=True, blank=True, help_text="Worker that processed task")
    queue_name = models.CharField(max_length=100, null=True, blank=True, help_text="Queue name (critical, high_priority, etc.)")
    remediation_notes = models.TextField(blank=True, help_text="Manual notes from admin review")

    class Meta:
        db_table = 'core_task_failure_record'
        verbose_name = 'Task Failure Record'
        verbose_name_plural = 'Task Failure Records'
        ordering = ['-first_failed_at']
        indexes = [
            models.Index(fields=['status', 'next_retry_at'], name='task_fail_dlq_idx'),
            models.Index(fields=['task_name', 'status'], name='task_fail_analysis_idx'),
            models.Index(fields=['failure_type', 'status'], name='task_fail_type_idx'),
        ]

    def __str__(self):
        return f"{self.task_name} - {self.task_id[:8]} - {self.status}"

    def schedule_retry(self, delay_seconds=None):
        """
        Schedule next automatic retry with exponential backoff.

        Args:
            delay_seconds: Optional custom delay (default: exponential backoff)
        """
        if delay_seconds is None:
            # Exponential backoff: 5min, 15min, 45min
            delay_seconds = 300 * (3 ** self.retry_count)

        self.next_retry_at = timezone.now() + timezone.timedelta(seconds=delay_seconds)
        self.status = 'PENDING'
        self.save(update_fields=['next_retry_at', 'status'])

    def mark_resolved(self):
        """Mark task failure as resolved after successful retry."""
        self.status = 'RESOLVED'
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])

    def mark_abandoned(self, reason=''):
        """Mark task failure as abandoned (no more retries)."""
        self.status = 'ABANDONED'
        self.abandoned_at = timezone.now()
        if reason:
            self.remediation_notes = f"{self.remediation_notes}\n\nAbandoned: {reason}".strip()
        self.save(update_fields=['status', 'abandoned_at', 'remediation_notes'])

    def increment_retry_count(self):
        """Increment retry counter and check for max retries."""
        self.retry_count += 1
        self.last_retry_at = timezone.now()

        if self.retry_count >= self.max_retries:
            self.mark_abandoned(f"Exceeded max retries ({self.max_retries})")
        else:
            self.schedule_retry()

    @classmethod
    def create_from_exception(cls, task, exc, exc_type, traceback_str, **kwargs):
        """
        Factory method to create DLQ record from task exception.

        Args:
            task: Celery task instance (bound task with self.request)
            exc: Exception instance
            exc_type: Exception class
            traceback_str: Formatted traceback string
            **kwargs: Additional fields (correlation_id, failure_type, etc.)

        Returns:
            TaskFailureRecord instance
        """
        from apps.core.exceptions.patterns import (
            DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS, FILE_EXCEPTIONS
        )

        # Determine failure type from exception
        failure_type = 'UNKNOWN'
        if isinstance(exc, DATABASE_EXCEPTIONS):
            failure_type = 'TRANSIENT'  # Database errors usually transient
        elif isinstance(exc, NETWORK_EXCEPTIONS):
            failure_type = 'EXTERNAL'
        elif isinstance(exc, FILE_EXCEPTIONS):
            failure_type = 'CONFIGURATION'
        elif isinstance(exc, (ValueError, TypeError, KeyError)):
            failure_type = 'PERMANENT'  # Validation errors permanent

        # Extract task context
        task_context = {
            'task_id': task.request.id,
            'task_name': task.name,
            'task_args': list(task.request.args) if hasattr(task.request, 'args') else [],
            'task_kwargs': dict(task.request.kwargs) if hasattr(task.request, 'kwargs') else {},
            'exception_type': exc_type.__name__,
            'exception_message': str(exc)[:1000],  # Truncate long messages
            'traceback': traceback_str[:5000],  # Truncate long tracebacks
            'failure_type': kwargs.get('failure_type', failure_type),
            'worker_hostname': task.request.hostname if hasattr(task.request, 'hostname') else None,
            'queue_name': task.request.delivery_info.get('routing_key') if hasattr(task.request, 'delivery_info') else None,
        }

        # Add optional fields
        if 'correlation_id' in kwargs:
            task_context['correlation_id'] = kwargs['correlation_id']

        # Create record
        record = cls.objects.create(**task_context)

        # Schedule first retry for transient/external failures
        if record.failure_type in ['TRANSIENT', 'EXTERNAL']:
            record.schedule_retry(delay_seconds=SECONDS_IN_HOUR)  # 1 hour for first retry

        return record

    @classmethod
    def get_pending_retries(cls):
        """Get all tasks pending retry (for DLQ processor)."""
        return cls.objects.filter(
            status='PENDING',
            next_retry_at__lte=timezone.now()
        ).select_related('business_unit')

    @classmethod
    def get_failure_rate(cls, task_name, hours=24):
        """Calculate task failure rate for monitoring."""
        from django.db.models import Count
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=hours)
        failures = cls.objects.filter(
            task_name=task_name,
            first_failed_at__gte=cutoff
        ).aggregate(Count('id'))

        return failures['id__count'] or 0
