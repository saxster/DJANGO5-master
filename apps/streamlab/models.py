"""
Stream Testbench Models
Core models for test scenarios, runs, and event capture with PII protection
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class TestScenario(models.Model):
    """
    Test scenario configuration for stream testing
    """
    PROTOCOL_CHOICES = [
        ('websocket', 'WebSocket'),
        ('mqtt', 'MQTT'),
        ('http', 'HTTP/REST'),
        ('mixed', 'Mixed Protocols')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES)
    endpoint = models.CharField(max_length=200)

    # Configuration JSON for rates, jitter, failure injection
    config = models.JSONField(default=dict, help_text="Scenario configuration (rates, jitter, failures)")

    # PII redaction rules - define which fields to keep
    pii_redaction_rules = models.JSONField(
        default=dict,
        help_text="PII protection rules - allowlisted fields only"
    )

    # Scenario metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Performance expectations
    expected_p95_latency_ms = models.FloatField(
        validators=[MinValueValidator(0)],
        help_text="Expected 95th percentile latency in milliseconds"
    )
    expected_error_rate = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Expected error rate (0.0 to 1.0)"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['protocol', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.protocol})"

    @property
    def default_pii_rules(self):
        """Default PII redaction rules based on protocol"""
        return {
            'websocket': {
                'allowlisted_fields': [
                    'timestamp', 'event_type', 'quality_score',
                    'duration_ms', 'confidence_score', 'processing_time_ms'
                ],
                'hash_fields': ['user_id', 'device_id', 'session_id'],
                'remove_fields': [
                    'voice_sample', 'audio_data', 'image_data',
                    'free_text', 'location', 'precise_gps'
                ]
            },
            'mqtt': {
                'allowlisted_fields': [
                    'timestamp', 'topic', 'qos', 'message_size'
                ],
                'hash_fields': ['client_id', 'user_id'],
                'remove_fields': ['payload_content', 'credentials']
            }
        }


class TestRun(models.Model):
    """
    Individual test run execution tracking
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(TestScenario, on_delete=models.CASCADE, related_name='runs')

    # Run metadata
    started_by = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Runtime configuration (can override scenario config)
    runtime_config = models.JSONField(default=dict)

    # Performance metrics (updated during/after run)
    metrics = models.JSONField(default=dict, help_text="Runtime metrics and results")

    # Summary statistics
    total_events = models.IntegerField(default=0)
    successful_events = models.IntegerField(default=0)
    failed_events = models.IntegerField(default=0)
    anomalies_detected = models.IntegerField(default=0)

    # Performance results
    p50_latency_ms = models.FloatField(null=True, blank=True)
    p95_latency_ms = models.FloatField(null=True, blank=True)
    p99_latency_ms = models.FloatField(null=True, blank=True)
    error_rate = models.FloatField(null=True, blank=True)
    throughput_qps = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['scenario', 'status']),
            models.Index(fields=['started_at']),
            models.Index(fields=['status', 'started_at']),
        ]

    def __str__(self):
        return f"{self.scenario.name} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_seconds(self):
        """Calculate run duration in seconds"""
        if not self.ended_at:
            if self.status == 'running':
                return (timezone.now() - self.started_at).total_seconds()
            return None
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def is_within_slo(self):
        """Check if run meets SLO expectations"""
        if not self.p95_latency_ms or not self.error_rate:
            return None

        latency_ok = self.p95_latency_ms <= self.scenario.expected_p95_latency_ms
        error_ok = self.error_rate <= self.scenario.expected_error_rate

        return latency_ok and error_ok

    def mark_completed(self):
        """Mark run as completed and set end time"""
        self.status = 'completed'
        self.ended_at = timezone.now()
        self.save()

    def mark_failed(self, error_message: str = None):
        """Mark run as failed"""
        self.status = 'failed'
        self.ended_at = timezone.now()
        if error_message:
            metrics = self.metrics or {}
            metrics['error_message'] = error_message
            self.metrics = metrics
        self.save()


class StreamEvent(models.Model):
    """
    Individual stream event capture with PII protection
    Stores sanitized event data for analysis and replay
    """
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]

    OUTCOME_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('anomaly', 'Anomaly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name='events')

    # Event identification
    correlation_id = models.UUIDField(db_index=True)
    message_correlation_id = models.UUIDField(null=True, blank=True)

    # Event metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    endpoint = models.CharField(max_length=200)
    channel_topic = models.CharField(max_length=100, blank=True)  # For MQTT topic or WS channel

    # Performance metrics
    latency_ms = models.FloatField(validators=[MinValueValidator(0)])
    message_size_bytes = models.IntegerField(validators=[MinValueValidator(0)])

    # Event outcome
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default='success')
    http_status_code = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)

    # PII-protected payload (sanitized)
    payload_sanitized = models.JSONField(
        help_text="Sanitized payload with PII removed/hashed"
    )
    payload_schema_hash = models.CharField(
        max_length=64,
        help_text="Hash of payload schema for anomaly detection"
    )

    # Stack trace hash for error correlation (if error occurred)
    stack_trace_hash = models.CharField(max_length=64, blank=True)

    # Phase 2: Visual regression testing fields
    visual_baseline_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hash of visual baseline for regression detection"
    )
    visual_diff_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Visual difference score (0.0 = identical, 1.0 = completely different)"
    )
    visual_diff_metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Visual diff analysis metadata (regions changed, severity, etc.)"
    )

    # Phase 2: Mobile performance metrics
    performance_metrics = models.JSONField(
        null=True,
        blank=True,
        help_text="Extended performance metrics (frame times, memory usage, battery impact)"
    )
    jank_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
        help_text="UI jank score - higher values indicate more jank"
    )
    composition_time_ms = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
        help_text="Compose composition time in milliseconds"
    )

    # Mobile app context (aligns with AnomalyOccurrence client tracking)
    client_app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Mobile app version (e.g., 1.2.3)"
    )
    client_os_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Mobile OS version (e.g., Android 13, iOS 16.1)"
    )
    client_device_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Mobile device model (e.g., iPhone 14, Samsung Galaxy S23)"
    )
    device_context = models.JSONField(
        null=True,
        blank=True,
        help_text="Extended device context (battery, memory, network state)"
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['run', 'timestamp']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['outcome', 'timestamp']),
            models.Index(fields=['latency_ms']),
            models.Index(fields=['payload_schema_hash']),
            # Phase 2: Visual regression indexes
            models.Index(fields=['visual_baseline_hash']),
            models.Index(fields=['visual_diff_score']),
            models.Index(fields=['visual_diff_score', 'timestamp']),
            # Phase 2: Mobile performance indexes
            models.Index(fields=['jank_score']),
            models.Index(fields=['composition_time_ms']),
            models.Index(fields=['client_app_version', 'timestamp']),
            models.Index(fields=['client_os_version', 'timestamp']),
            models.Index(fields=['client_device_model', 'timestamp']),
            # Combined indexes for trend analysis
            models.Index(fields=['outcome', 'visual_diff_score', 'timestamp']),
            models.Index(fields=['client_app_version', 'outcome', 'timestamp']),
        ]

    def __str__(self):
        return f"Event {self.correlation_id} - {self.outcome}"

    @property
    def is_anomaly(self):
        """Check if this event represents an anomaly"""
        # Original anomaly conditions
        latency_anomaly = self.latency_ms > 1000  # >1s is anomalous
        outcome_anomaly = self.outcome == 'anomaly'

        # Phase 2: Visual regression anomaly
        visual_anomaly = self.visual_diff_score is not None and self.visual_diff_score > 0.1  # >10% change

        # Phase 2: Performance anomaly
        jank_anomaly = self.jank_score is not None and self.jank_score > 10.0  # High jank score
        composition_anomaly = self.composition_time_ms is not None and self.composition_time_ms > 200.0  # >200ms composition

        return any([outcome_anomaly, latency_anomaly, visual_anomaly, jank_anomaly, composition_anomaly])

    @property
    def is_visual_regression(self):
        """Check if this event represents a visual regression"""
        return (self.visual_diff_score is not None and
                self.visual_diff_score > 0.05 and  # >5% visual change
                self.outcome != 'error')  # Not a functional error

    @property
    def is_performance_regression(self):
        """Check if this event represents a performance regression"""
        return (self.jank_score is not None and self.jank_score > 5.0) or \
               (self.composition_time_ms is not None and self.composition_time_ms > 100.0) or \
               (self.latency_ms > 500.0)  # Network latency threshold

    @property
    def mobile_context_summary(self):
        """Get structured mobile context information"""
        return {
            'app_version': self.client_app_version or 'unknown',
            'os_version': self.client_os_version or 'unknown',
            'device_model': self.client_device_model or 'unknown',
            'has_device_context': self.device_context is not None
        }


class EventRetention(models.Model):
    """
    Data retention policy tracking for Stream Events
    """
    RETENTION_TYPES = [
        ('raw_payloads', 'Raw Payloads (Never Stored)'),
        ('sanitized_metadata', 'Sanitized Metadata (14 days)'),
        ('stack_traces', 'Stack Traces (30 days)'),
        ('aggregated_metrics', 'Aggregated Metrics (90 days)')
    ]

    retention_type = models.CharField(max_length=30, choices=RETENTION_TYPES, unique=True)
    days_to_keep = models.IntegerField(validators=[MinValueValidator(0)])
    last_cleanup_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Event Retention Policy"
        verbose_name_plural = "Event Retention Policies"
        ordering = ['retention_type']
        indexes = [
            models.Index(fields=['retention_type']),
        ]

    def __str__(self):
        return f"{self.retention_type} - {self.days_to_keep} days"


class StreamEventArchive(models.Model):
    """
    Compressed archive of old stream events for compliance/audit
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    archive_date = models.DateField()
    run_ids = models.JSONField(help_text="List of archived run IDs")
    event_count = models.IntegerField()
    compressed_size_bytes = models.IntegerField()

    # Archive location (S3, local file, etc.)
    storage_location = models.CharField(max_length=500)
    checksum_sha256 = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="When this archive will be deleted")

    class Meta:
        verbose_name = "Stream Event Archive"
        verbose_name_plural = "Stream Event Archives"
        ordering = ['-archive_date']
        indexes = [
            models.Index(fields=['archive_date']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Archive {self.archive_date} - {self.event_count} events"