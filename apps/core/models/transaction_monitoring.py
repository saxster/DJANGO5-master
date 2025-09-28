"""
Transaction Monitoring Models

Tracks transaction health, failures, and provides monitoring capabilities.

Complies with: .claude/rules.md - Transaction Management Requirements
"""

from django.db import models
from django.utils import timezone
from apps.tenants.models import TenantAwareModel


class TransactionFailureLog(TenantAwareModel):
    """
    Log of transaction failures for monitoring and debugging.

    Tracks all transaction rollbacks to help identify:
    - Problematic operations
    - Data integrity issues
    - Performance bottlenecks
    """

    operation_name = models.CharField(max_length=255, db_index=True)
    view_name = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    error_type = models.CharField(max_length=100, db_index=True)
    error_message = models.TextField()
    error_traceback = models.TextField(null=True, blank=True)

    correlation_id = models.CharField(max_length=36, null=True, blank=True, db_index=True)
    user_id = models.IntegerField(null=True, blank=True, db_index=True)

    request_path = models.CharField(max_length=500, null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)

    database_alias = models.CharField(max_length=50, default='default')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False, db_index=True)

    resolution_notes = models.TextField(null=True, blank=True)

    additional_context = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'transaction_failure_log'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['operation_name', 'occurred_at']),
            models.Index(fields=['error_type', 'is_resolved']),
            models.Index(fields=['user_id', 'occurred_at']),
        ]

    def __str__(self):
        return f"{self.operation_name} failed at {self.occurred_at}"

    def mark_resolved(self, notes=""):
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save(update_fields=['is_resolved', 'resolved_at', 'resolution_notes'])


class TransactionMetrics(TenantAwareModel):
    """
    Aggregated transaction metrics for performance monitoring.

    Tracks:
    - Success/failure rates
    - Average transaction duration
    - Peak load times
    """

    operation_name = models.CharField(max_length=255, db_index=True)
    metric_date = models.DateField(default=timezone.now, db_index=True)
    hour_of_day = models.IntegerField(null=True, blank=True)

    total_attempts = models.IntegerField(default=0)
    successful_commits = models.IntegerField(default=0)
    failed_commits = models.IntegerField(default=0)
    rollbacks = models.IntegerField(default=0)

    avg_duration_ms = models.FloatField(null=True, blank=True)
    max_duration_ms = models.FloatField(null=True, blank=True)
    min_duration_ms = models.FloatField(null=True, blank=True)

    integrity_errors = models.IntegerField(default=0)
    validation_errors = models.IntegerField(default=0)
    deadlocks = models.IntegerField(default=0)
    timeouts = models.IntegerField(default=0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transaction_metrics'
        unique_together = [['operation_name', 'metric_date', 'hour_of_day', 'tenant', 'client']]
        ordering = ['-metric_date', '-hour_of_day']
        indexes = [
            models.Index(fields=['operation_name', 'metric_date']),
            models.Index(fields=['metric_date', 'hour_of_day']),
        ]

    def __str__(self):
        return f"{self.operation_name} metrics for {self.metric_date}"

    @property
    def success_rate(self):
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_commits / self.total_attempts) * 100

    @property
    def failure_rate(self):
        return 100.0 - self.success_rate


class SagaExecutionLog(TenantAwareModel):
    """
    Log of saga pattern executions for distributed transactions.
    """

    saga_id = models.CharField(max_length=100, unique=True, db_index=True)
    saga_name = models.CharField(max_length=255)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('executing', 'Executing'),
            ('committed', 'Committed'),
            ('failed', 'Failed'),
            ('compensating', 'Compensating'),
            ('compensated', 'Compensated'),
        ],
        default='pending',
        db_index=True
    )

    total_steps = models.IntegerField(default=0)
    executed_steps = models.IntegerField(default=0)
    compensated_steps = models.IntegerField(default=0)

    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.FloatField(null=True, blank=True)

    error_message = models.TextField(null=True, blank=True)
    execution_details = models.JSONField(default=dict)

    user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'saga_execution_log'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['saga_name', 'status']),
        ]

    def __str__(self):
        return f"Saga {self.saga_name} ({self.saga_id}) - {self.status}"


class TransactionHealthCheck(models.Model):
    """
    Periodic health check results for transaction subsystem.
    """

    check_timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    total_transactions_last_hour = models.IntegerField(default=0)
    failed_transactions_last_hour = models.IntegerField(default=0)
    avg_transaction_duration_ms = models.FloatField(null=True, blank=True)

    deadlock_count_last_hour = models.IntegerField(default=0)
    timeout_count_last_hour = models.IntegerField(default=0)

    health_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('critical', 'Critical'),
        ],
        default='healthy'
    )

    alerts_triggered = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)

    class Meta:
        db_table = 'transaction_health_check'
        ordering = ['-check_timestamp']

    def __str__(self):
        return f"Health Check {self.check_timestamp}: {self.health_status}"

    @classmethod
    def calculate_health_status(cls, failure_rate):
        """
        Calculate health status based on failure rate.

        Args:
            failure_rate: Percentage of failed transactions

        Returns:
            str: health status ('healthy', 'degraded', 'critical')
        """
        if failure_rate < 1.0:
            return 'healthy'
        elif failure_rate < 5.0:
            return 'degraded'
        else:
            return 'critical'