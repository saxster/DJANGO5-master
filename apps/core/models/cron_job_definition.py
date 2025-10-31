"""
CronJobDefinition Model for Centralized Cron Management

Stores cron job definitions with validation, scheduling, and metadata.
Supports management commands, background tasks, and custom jobs.

Compliance:
- Rule #7: Model < 150 lines
- Rule #11: Specific exception handling
- Rule #15: No PII in logs
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import JSONField

from apps.tenants.models import TenantAwareModel
from apps.core.utils_new.cron_utilities import validate_cron_for_form

logger = logging.getLogger(__name__)


class CronJobDefinition(TenantAwareModel):
    """
    Centralized cron job definition model.

    Stores all cron job configurations with validation and metadata.
    Supports various job types: management commands, background tasks, custom jobs.
    """

    JOB_TYPES = [
        ('management_command', 'Management Command'),
        ('background_task', 'Background Task'),
        ('celery_task', 'Celery Task'),
        ('custom_function', 'Custom Function'),
        ('api_call', 'API Call'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('paused', 'Paused'),
        ('error', 'Error'),
        ('deprecated', 'Deprecated'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    # Core fields
    name = models.CharField(
        max_length=200,
        help_text="Unique name for this cron job"
    )

    description = models.TextField(
        blank=True,
        help_text="Detailed description of what this job does"
    )

    cron_expression = models.CharField(
        max_length=100,
        help_text="Standard cron expression (e.g., '0 0 * * *' for daily at midnight)",
        validators=[validate_cron_for_form]
    )

    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPES,
        default='management_command'
    )

    # Job configuration
    command_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Management command name (for management_command type)"
    )

    command_args = JSONField(
        default=list,
        blank=True,
        help_text="Command arguments as JSON array"
    )

    command_kwargs = JSONField(
        default=dict,
        blank=True,
        help_text="Command keyword arguments as JSON object"
    )

    task_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Background/Celery task name"
    )

    task_args = JSONField(
        default=list,
        blank=True,
        help_text="Task arguments as JSON array"
    )

    task_kwargs = JSONField(
        default=dict,
        blank=True,
        help_text="Task keyword arguments as JSON object"
    )

    # Execution settings
    timeout_seconds = models.PositiveIntegerField(
        default=3600,
        help_text="Maximum execution time in seconds"
    )

    max_retries = models.PositiveSmallIntegerField(
        default=3,
        help_text="Maximum number of retry attempts"
    )

    retry_delay_seconds = models.PositiveIntegerField(
        default=60,
        help_text="Delay between retries in seconds"
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal'
    )

    # Status and metadata
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='active'
    )

    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether this job is currently enabled"
    )

    environment = models.CharField(
        max_length=20,
        default='all',
        help_text="Target environment (dev, staging, prod, all)"
    )

    tags = JSONField(
        default=list,
        blank=True,
        help_text="Tags for categorization and filtering"
    )

    # Execution tracking
    last_execution_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this job was last executed"
    )

    next_execution_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this job is scheduled to run next"
    )

    execution_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of times this job has been executed"
    )

    success_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of successful executions"
    )

    failure_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed executions"
    )

    average_duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Average execution duration in seconds"
    )

    # Metadata
    created_by = models.CharField(
        max_length=100,
        help_text="User or system that created this job"
    )

    modified_by = models.CharField(
        max_length=100,
        blank=True,
        help_text="User or system that last modified this job"
    )

    version = models.PositiveSmallIntegerField(
        default=1,
        help_text="Version number for change tracking"
    )

    class Meta:
        db_table = 'core_cron_job_definition'
        unique_together = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'status', 'is_enabled']),
            models.Index(fields=['next_execution_time']),
            models.Index(fields=['job_type']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f"{self.name} ({self.cron_expression})"

    def clean(self):
        """Validate job configuration."""
        super().clean()

        if self.job_type == 'management_command' and not self.command_name:
            raise ValidationError({
                'command_name': 'Command name is required for management_command type'
            })

        if self.job_type in ['background_task', 'celery_task'] and not self.task_name:
            raise ValidationError({
                'task_name': 'Task name is required for background_task/celery_task type'
            })

    def get_success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.execution_count == 0:
            return 0.0
        return (self.success_count / self.execution_count) * 100

    def is_overdue(self) -> bool:
        """Check if job is overdue for execution."""
        if not self.next_execution_time:
            return False
        return timezone.now() > self.next_execution_time + timedelta(minutes=5)

    def should_run_now(self) -> bool:
        """Check if job should be executed now."""
        if not self.is_enabled or self.status != 'active':
            return False

        if not self.next_execution_time:
            return False

        return timezone.now() >= self.next_execution_time

    def update_execution_stats(self, success: bool, duration_seconds: float):
        """Update execution statistics."""
        self.execution_count += 1

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        # Update average duration
        if self.average_duration_seconds is None:
            self.average_duration_seconds = duration_seconds
        else:
            # Weighted average with more weight on recent executions
            weight = 0.2  # 20% weight for new execution
            self.average_duration_seconds = (
                (1 - weight) * self.average_duration_seconds +
                weight * duration_seconds
            )

        self.last_execution_time = timezone.now()
        self.save(update_fields=[
            'execution_count', 'success_count', 'failure_count',
            'average_duration_seconds', 'last_execution_time'
        ])