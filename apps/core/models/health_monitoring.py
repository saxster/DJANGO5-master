"""
Health monitoring models for historical tracking and alerting.
Follows Rule 7: Model complexity < 150 lines.
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

__all__ = [
    'HealthCheckLog',
    'ServiceAvailability',
    'AlertThreshold',
]


class HealthCheckLog(models.Model):
    """Historical log of health check results for trend analysis."""

    CHECK_STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('error', 'Error'),
    ]

    check_name = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=CHECK_STATUS_CHOICES, db_index=True)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    duration_ms = models.FloatField(validators=[MinValueValidator(0)])
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    correlation_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'core_health_check_log'
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['check_name', '-checked_at']),
            models.Index(fields=['status', '-checked_at']),
        ]
        verbose_name = 'Health Check Log'
        verbose_name_plural = 'Health Check Logs'

    def __str__(self):
        return f"{self.check_name} - {self.status} at {self.checked_at}"

    @classmethod
    def log_check(cls, check_name: str, result: dict):
        """
        Log a health check result.

        Args:
            check_name: Name of the health check
            result: Health check result dictionary
        """
        return cls.objects.create(
            check_name=check_name,
            status=result.get('status', 'error'),
            message=result.get('message', ''),
            details=result.get('details', {}),
            duration_ms=result.get('duration_ms', 0),
        )


class ServiceAvailability(models.Model):
    """Track service uptime and availability metrics."""

    service_name = models.CharField(max_length=100, unique=True, db_index=True)
    total_checks = models.IntegerField(default=0)
    successful_checks = models.IntegerField(default=0)
    failed_checks = models.IntegerField(default=0)
    degraded_checks = models.IntegerField(default=0)
    last_check_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    uptime_percentage = models.FloatField(
        default=100.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_service_availability'
        ordering = ['-uptime_percentage']
        verbose_name = 'Service Availability'
        verbose_name_plural = 'Service Availabilities'

    def __str__(self):
        return f"{self.service_name} - {self.uptime_percentage:.2f}% uptime"

    def record_check(self, status: str):
        """
        Record a health check result and update metrics.

        Args:
            status: Check status ('healthy', 'degraded', 'error')
        """
        self.total_checks += 1
        self.last_check_at = timezone.now()

        if status == 'healthy':
            self.successful_checks += 1
            self.last_success_at = timezone.now()
        elif status == 'degraded':
            self.degraded_checks += 1
        elif status == 'error':
            self.failed_checks += 1
            self.last_failure_at = timezone.now()

        if self.total_checks > 0:
            self.uptime_percentage = (
                self.successful_checks / self.total_checks * 100
            )

        self.save()


class AlertThreshold(models.Model):
    """Configurable alert thresholds for health check metrics."""

    METRIC_TYPE_CHOICES = [
        ('disk_usage', 'Disk Usage %'),
        ('memory_usage', 'Memory Usage %'),
        ('cpu_load', 'CPU Load'),
        ('response_time', 'Response Time (ms)'),
        ('error_rate', 'Error Rate %'),
        ('queue_depth', 'Queue Depth'),
    ]

    ALERT_LEVEL_CHOICES = [
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    metric_type = models.CharField(max_length=50, choices=METRIC_TYPE_CHOICES, db_index=True)
    alert_level = models.CharField(max_length=20, choices=ALERT_LEVEL_CHOICES)
    threshold_value = models.FloatField()
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_alert_threshold'
        unique_together = [['metric_type', 'alert_level']]
        ordering = ['metric_type', 'alert_level']
        verbose_name = 'Alert Threshold'
        verbose_name_plural = 'Alert Thresholds'

    def __str__(self):
        return f"{self.get_metric_type_display()} - {self.get_alert_level_display()}: {self.threshold_value}"

    @classmethod
    def get_threshold(cls, metric_type: str, alert_level: str = 'warning') -> float:
        """Get threshold value for a metric type and alert level."""
        try:
            threshold = cls.objects.get(
                metric_type=metric_type,
                alert_level=alert_level,
                enabled=True
            )
            return threshold.threshold_value
        except cls.DoesNotExist:
            defaults = {
                ('disk_usage', 'warning'): 80.0,
                ('disk_usage', 'critical'): 90.0,
                ('memory_usage', 'warning'): 80.0,
                ('memory_usage', 'critical'): 90.0,
                ('cpu_load', 'warning'): 0.7,
                ('cpu_load', 'critical'): 0.9,
                ('response_time', 'warning'): 1000.0,
                ('response_time', 'critical'): 3000.0,
                ('error_rate', 'warning'): 5.0,
                ('error_rate', 'critical'): 10.0,
                ('queue_depth', 'warning'): 100.0,
                ('queue_depth', 'critical'): 500.0,
            }
            return defaults.get((metric_type, alert_level), 100.0)