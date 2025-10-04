"""
CronJobExecution Model for Tracking Individual Job Runs

Records detailed execution history for cron jobs including performance metrics,
output, errors, and execution context for monitoring and debugging.

Compliance:
- Rule #7: Model < 150 lines
- Rule #11: Specific exception handling
- Rule #15: No PII in logs (sanitized output storage)
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import JSONField

from apps.tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class CronJobExecution(TenantAwareModel):
    """
    Individual cron job execution record.

    Tracks detailed execution history for monitoring, debugging,
    and performance analysis of cron jobs.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('cancelled', 'Cancelled'),
        ('retry', 'Retry'),
    ]

    EXECUTION_CONTEXT_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual'),
        ('retry', 'Retry'),
        ('test', 'Test'),
        ('migration', 'Migration'),
    ]

    # Core fields
    job_definition = models.ForeignKey(
        'core.CronJobDefinition',
        on_delete=models.CASCADE,
        related_name='executions',
        help_text="Associated cron job definition"
    )

    execution_id = models.CharField(
        max_length=36,
        unique=True,
        help_text="Unique execution identifier (UUID)"
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending'
    )

    execution_context = models.CharField(
        max_length=15,
        choices=EXECUTION_CONTEXT_CHOICES,
        default='scheduled'
    )

    # Timing information
    scheduled_time = models.DateTimeField(
        help_text="When this execution was scheduled to run"
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution actually started"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution completed"
    )

    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Execution duration in seconds"
    )

    # Execution details
    hostname = models.CharField(
        max_length=100,
        blank=True,
        help_text="Hostname where job was executed"
    )

    process_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Process ID of the execution"
    )

    worker_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the worker that executed the job"
    )

    # Results and output
    exit_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="Exit code (0 for success, non-zero for failure)"
    )

    stdout_output = models.TextField(
        blank=True,
        max_length=10000,  # Limit to prevent database bloat
        help_text="Standard output (truncated if too long)"
    )

    stderr_output = models.TextField(
        blank=True,
        max_length=10000,  # Limit to prevent database bloat
        help_text="Standard error output (truncated if too long)"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if execution failed"
    )

    # Metadata
    retry_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of retries for this execution"
    )

    parent_execution = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='retries',
        help_text="Parent execution if this is a retry"
    )

    execution_metadata = JSONField(
        default=dict,
        blank=True,
        help_text="Additional execution metadata"
    )

    # Performance metrics
    memory_usage_mb = models.FloatField(
        null=True,
        blank=True,
        help_text="Peak memory usage in MB"
    )

    cpu_usage_percent = models.FloatField(
        null=True,
        blank=True,
        help_text="Average CPU usage percentage"
    )

    class Meta:
        db_table = 'core_cron_job_execution'
        indexes = [
            models.Index(fields=['tenant', 'job_definition', 'status']),
            models.Index(fields=['scheduled_time']),
            models.Index(fields=['started_at']),
            models.Index(fields=['status', 'execution_context']),
            models.Index(fields=['job_definition', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job_definition.name} - {self.execution_id} ({self.status})"

    def save(self, *args, **kwargs):
        """Override save to calculate duration and sanitize output."""
        # Calculate duration if both times are available
        if self.started_at and self.completed_at:
            self.duration_seconds = (
                self.completed_at - self.started_at
            ).total_seconds()

        # Sanitize output to prevent PII leakage (Rule #15)
        self.stdout_output = self._sanitize_output(self.stdout_output)
        self.stderr_output = self._sanitize_output(self.stderr_output)

        super().save(*args, **kwargs)

    def _sanitize_output(self, output: str) -> str:
        """
        Sanitize output to remove potential PII.

        Args:
            output: Raw output string

        Returns:
            Sanitized output string
        """
        if not output:
            return output

        # Truncate if too long
        if len(output) > 10000:
            output = output[:9950] + "\n... [TRUNCATED]"

        # Basic PII sanitization patterns
        import re

        # Remove potential email addresses
        output = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                       '[EMAIL_REDACTED]', output)

        # Remove potential phone numbers
        output = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
                       '[PHONE_REDACTED]', output)

        # Remove potential credit card numbers
        output = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
                       '[CARD_REDACTED]', output)

        return output

    def mark_started(self, hostname: str = None, process_id: int = None):
        """Mark execution as started."""
        self.status = 'running'
        self.started_at = timezone.now()
        if hostname:
            self.hostname = hostname
        if process_id:
            self.process_id = process_id
        self.save(update_fields=['status', 'started_at', 'hostname', 'process_id'])

    def mark_completed(self, success: bool, exit_code: int = None,
                      error_message: str = None):
        """Mark execution as completed."""
        self.status = 'success' if success else 'failed'
        self.completed_at = timezone.now()

        if exit_code is not None:
            self.exit_code = exit_code

        if error_message:
            self.error_message = error_message

        self.save(update_fields=[
            'status', 'completed_at', 'exit_code', 'error_message'
        ])

        # Update job definition statistics
        if self.job_definition:
            self.job_definition.update_execution_stats(
                success=success,
                duration_seconds=self.duration_seconds or 0
            )

    def mark_failed(self, error_message: str, exit_code: int = 1):
        """Mark execution as failed."""
        self.mark_completed(success=False, exit_code=exit_code,
                          error_message=error_message)

    def mark_timeout(self):
        """Mark execution as timed out."""
        self.status = 'timeout'
        self.completed_at = timezone.now()
        self.error_message = f"Execution timed out after {self.job_definition.timeout_seconds} seconds"
        self.save(update_fields=['status', 'completed_at', 'error_message'])

    def should_retry(self) -> bool:
        """Check if this execution should be retried."""
        if self.status != 'failed':
            return False

        return self.retry_count < self.job_definition.max_retries

    def get_execution_delay(self) -> Optional[float]:
        """Get delay between scheduled and actual start time in seconds."""
        if not self.started_at:
            return None
        return (self.started_at - self.scheduled_time).total_seconds()

    def is_long_running(self) -> bool:
        """Check if execution is taking longer than expected."""
        if not self.started_at or self.status not in ['running']:
            return False

        elapsed = (timezone.now() - self.started_at).total_seconds()
        expected_duration = self.job_definition.average_duration_seconds or 300

        # Consider long running if > 3x expected duration
        return elapsed > (expected_duration * 3)