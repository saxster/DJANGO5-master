"""
Monitoring Models

Models for persistent monitoring data storage.

Models:
- MonitoringEvent: Stores monitoring events with correlation IDs
- PerformanceBaseline: Stores performance baselines for anomaly detection
- SecurityEvent: Stores security-related monitoring events

Compliance: .claude/rules.md Rule #7 (Model < 150 lines)
"""

from django.db import models
from django.utils import timezone
from apps.peoples.models import BaseModel  # BaseModel is in peoples, not core

__all__ = ['MonitoringEvent', 'PerformanceBaseline', 'SecurityEvent']


class MonitoringEvent(BaseModel):
    """
    Stores monitoring events for persistence and analysis.

    Enables long-term trend analysis and correlation tracking.
    Rule #7 compliant: < 150 lines
    """

    # Event categorization
    EVENT_TYPE_CHOICES = [
        ('request', 'HTTP Request'),
        ('query', 'Database Query'),
        ('cache', 'Cache Operation'),
        ('error', 'Error/Exception'),
        ('alert', 'Alert Triggered'),
        ('websocket', 'WebSocket Event'),
        ('security', 'Security Event'),
    ]

    SEVERITY_CHOICES = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]

    # Core fields
    correlation_id = models.UUIDField(
        db_index=True,
        help_text='Correlation ID for request tracking'
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        db_index=True
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='info',
        db_index=True
    )

    # Event details
    message = models.TextField()
    details = models.JSONField(
        default=dict,
        help_text='Additional event details'
    )

    # Performance metrics
    duration_ms = models.FloatField(
        null=True,
        blank=True,
        help_text='Event duration in milliseconds'
    )
    value = models.FloatField(
        null=True,
        blank=True,
        help_text='Numeric metric value'
    )

    # Context
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Timestamps
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'monitoring_events'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['correlation_id', '-occurred_at']),
            models.Index(fields=['event_type', '-occurred_at']),
            models.Index(fields=['severity', '-occurred_at']),
        ]
        verbose_name = 'Monitoring Event'
        verbose_name_plural = 'Monitoring Events'

    def __str__(self):
        return f"{self.event_type} - {self.severity} - {self.correlation_id}"


class PerformanceBaseline(BaseModel):
    """
    Stores performance baselines for anomaly detection.

    Used by anomaly detector to identify performance regressions.
    """

    # Metric identification
    metric_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text='Name of the metric'
    )
    endpoint = models.CharField(
        max_length=500,
        blank=True,
        help_text='API endpoint or path'
    )

    # Baseline statistics
    mean = models.FloatField()
    median = models.FloatField()
    p95 = models.FloatField()
    p99 = models.FloatField()
    std_dev = models.FloatField()

    # Sample information
    sample_size = models.IntegerField(
        help_text='Number of samples used for baseline'
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    # Metadata
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this baseline is actively used'
    )

    class Meta:
        db_table = 'monitoring_performance_baselines'
        ordering = ['-cdtz']  # BaseModel provides cdtz (created datetime), not created_at
        indexes = [
            models.Index(fields=['metric_name', 'endpoint']),
            models.Index(fields=['is_active', '-cdtz']),  # Use cdtz from BaseModel
        ]
        verbose_name = 'Performance Baseline'
        verbose_name_plural = 'Performance Baselines'
        unique_together = [['metric_name', 'endpoint', 'is_active']]

    def __str__(self):
        return f"{self.metric_name} - {self.endpoint or 'global'}"


class SecurityEvent(BaseModel):
    """
    Stores security-related monitoring events.

    Tracks security incidents, attacks, and policy violations.
    """

    # Security event types
    SECURITY_EVENT_TYPES = [
        ('websocket_flood', 'WebSocket Connection Flood'),
        ('rate_limit', 'Rate Limit Exceeded'),
        ('auth_failure', 'Authentication Failure'),
        ('csrf_violation', 'CSRF Violation'),
        ('sql_injection', 'SQL Injection Attempt'),
        ('xss_attempt', 'XSS Attempt'),
        ('path_traversal', 'Path Traversal Attempt'),
    ]

    # Event details
    correlation_id = models.UUIDField(db_index=True)
    event_type = models.CharField(
        max_length=50,
        choices=SECURITY_EVENT_TYPES,
        db_index=True
    )

    # Attack details
    source_ip = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500)
    request_method = models.CharField(max_length=10)

    # Security context
    user_id = models.IntegerField(null=True, blank=True)
    blocked = models.BooleanField(
        default=True,
        help_text='Whether the request was blocked'
    )
    details = models.JSONField(
        default=dict,
        help_text='Attack details and context'
    )

    # Timestamps
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'monitoring_security_events'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['source_ip', '-detected_at']),
            models.Index(fields=['event_type', '-detected_at']),
            models.Index(fields=['blocked', '-detected_at']),
        ]
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'

    def __str__(self):
        status = 'Blocked' if self.blocked else 'Allowed'
        return f"{self.event_type} from {self.source_ip} - {status}"
