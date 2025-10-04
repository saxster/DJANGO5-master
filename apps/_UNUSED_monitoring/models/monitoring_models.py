"""
Core Monitoring Models

Device health, performance metrics, and user activity pattern tracking.
Follows .claude/rules.md Rule #7: Model < 150 lines per class.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
import uuid


class MonitoringMetric(BaseModel, TenantAwareModel):
    """
    Time-series metric storage for device monitoring.

    Optimized for high-frequency data ingestion and querying.
    """

    METRIC_TYPES = [
        # Battery metrics
        ('BATTERY_LEVEL', 'Battery Level'),
        ('BATTERY_DRAIN_RATE', 'Battery Drain Rate'),
        ('BATTERY_TEMPERATURE', 'Battery Temperature'),

        # Network metrics
        ('SIGNAL_STRENGTH', 'Signal Strength'),
        ('NETWORK_LATENCY', 'Network Latency'),
        ('DATA_USAGE', 'Data Usage'),

        # Performance metrics
        ('MEMORY_USAGE', 'Memory Usage'),
        ('CPU_USAGE', 'CPU Usage'),
        ('STORAGE_USAGE', 'Storage Usage'),

        # Activity metrics
        ('STEP_COUNT', 'Step Count'),
        ('MOVEMENT_DISTANCE', 'Movement Distance'),
        ('LOCATION_ACCURACY', 'Location Accuracy'),

        # System metrics
        ('APP_CRASHES', 'App Crashes'),
        ('SYNC_SUCCESS_RATE', 'Sync Success Rate'),
        ('RESPONSE_TIME', 'Response Time'),
    ]

    metric_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this metric"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        help_text="User this metric belongs to"
    )

    device_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Device identifier"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Site where metric was recorded"
    )

    metric_type = models.CharField(
        max_length=30,
        choices=METRIC_TYPES,
        db_index=True,
        help_text="Type of metric"
    )

    value = models.FloatField(
        help_text="Metric value"
    )

    unit = models.CharField(
        max_length=20,
        help_text="Unit of measurement"
    )

    recorded_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When metric was recorded"
    )

    # Context data
    context = models.JSONField(
        default=dict,
        help_text="Additional context about the metric"
    )

    # Quality indicators
    accuracy = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Accuracy of the measurement (0-1)"
    )

    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence in the measurement (0-1)"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_metric'
        verbose_name = 'Monitoring Metric'
        verbose_name_plural = 'Monitoring Metrics'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['tenant', 'metric_type', 'recorded_at']),
            models.Index(fields=['user', 'metric_type', 'recorded_at']),
            models.Index(fields=['device_id', 'metric_type', 'recorded_at']),
            models.Index(fields=['site', 'recorded_at']),
        ]

    def __str__(self):
        return f"{self.metric_type}: {self.value} {self.unit} - {self.user.peoplename}"


class DeviceHealthSnapshot(BaseModel, TenantAwareModel):
    """
    Comprehensive device health snapshot taken at regular intervals.

    Aggregates multiple metrics for holistic device health assessment.
    """

    HEALTH_STATUS = [
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
        ('CRITICAL', 'Critical'),
    ]

    snapshot_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this snapshot"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        help_text="User this snapshot belongs to"
    )

    device_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Device identifier"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Current site location"
    )

    # Overall health assessment
    overall_health = models.CharField(
        max_length=20,
        choices=HEALTH_STATUS,
        db_index=True,
        help_text="Overall device health assessment"
    )

    health_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Numerical health score (0-100)"
    )

    # Battery metrics
    battery_level = models.PositiveIntegerField(
        validators=[MaxValueValidator(100)],
        help_text="Battery level percentage"
    )

    battery_health = models.CharField(
        max_length=20,
        choices=HEALTH_STATUS,
        help_text="Battery health assessment"
    )

    is_charging = models.BooleanField(
        help_text="Whether device is currently charging"
    )

    battery_temperature = models.FloatField(
        null=True,
        blank=True,
        help_text="Battery temperature in Celsius"
    )

    # Network metrics
    signal_strength = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-120), MaxValueValidator(0)],
        help_text="Signal strength in dBm"
    )

    network_type = models.CharField(
        max_length=20,
        blank=True,
        help_text="Network connection type"
    )

    is_online = models.BooleanField(
        help_text="Whether device has network connectivity"
    )

    # Performance metrics
    memory_usage_percent = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Memory usage percentage"
    )

    storage_usage_percent = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Storage usage percentage"
    )

    cpu_usage_percent = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="CPU usage percentage"
    )

    # Thermal status
    thermal_state = models.CharField(
        max_length=20,
        blank=True,
        help_text="Device thermal state"
    )

    # Activity metrics
    steps_last_hour = models.PositiveIntegerField(
        default=0,
        help_text="Steps taken in the last hour"
    )

    last_movement_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last detected movement timestamp"
    )

    current_location = models.JSONField(
        null=True,
        blank=True,
        help_text="Current GPS coordinates"
    )

    location_accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS accuracy in meters"
    )

    # App performance
    app_crashes_last_hour = models.PositiveIntegerField(
        default=0,
        help_text="App crashes in the last hour"
    )

    sync_failures_last_hour = models.PositiveIntegerField(
        default=0,
        help_text="Sync failures in the last hour"
    )

    avg_response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Average response time in milliseconds"
    )

    # Predictive indicators
    predicted_battery_hours = models.FloatField(
        null=True,
        blank=True,
        help_text="Predicted hours until battery depleted"
    )

    risk_score = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Overall risk score (0-1)"
    )

    anomaly_indicators = models.JSONField(
        default=list,
        help_text="List of detected anomaly indicators"
    )

    snapshot_taken_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When snapshot was taken"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_device_health_snapshot'
        verbose_name = 'Device Health Snapshot'
        verbose_name_plural = 'Device Health Snapshots'
        ordering = ['-snapshot_taken_at']
        indexes = [
            models.Index(fields=['tenant', 'user', 'snapshot_taken_at']),
            models.Index(fields=['device_id', 'snapshot_taken_at']),
            models.Index(fields=['overall_health', 'snapshot_taken_at']),
            models.Index(fields=['risk_score']),
        ]

    def __str__(self):
        return f"Health: {self.overall_health} - {self.user.peoplename} ({self.health_score}%)"

    @property
    def is_at_risk(self):
        """Check if device is at risk based on multiple factors"""
        return (
            self.risk_score > 0.7 or
            self.battery_level < 20 or
            self.overall_health in ['POOR', 'CRITICAL'] or
            len(self.anomaly_indicators) > 0
        )


class PerformanceSnapshot(BaseModel):
    """
    System-wide performance metrics snapshot.

    Tracks overall system health and performance indicators.
    """

    snapshot_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this snapshot"
    )

    # System metrics
    total_active_devices = models.PositiveIntegerField(
        help_text="Total number of active devices"
    )

    total_alerts_active = models.PositiveIntegerField(
        help_text="Total number of active alerts"
    )

    total_alerts_last_hour = models.PositiveIntegerField(
        help_text="Alerts triggered in last hour"
    )

    # Performance indicators
    avg_response_time_ms = models.FloatField(
        help_text="Average system response time"
    )

    avg_battery_level = models.FloatField(
        help_text="Average battery level across all devices"
    )

    devices_low_battery = models.PositiveIntegerField(
        help_text="Number of devices with low battery"
    )

    devices_offline = models.PositiveIntegerField(
        help_text="Number of offline devices"
    )

    # Network health
    avg_signal_strength = models.FloatField(
        null=True,
        blank=True,
        help_text="Average signal strength across devices"
    )

    network_incidents = models.PositiveIntegerField(
        default=0,
        help_text="Network-related incidents in last hour"
    )

    # Security metrics
    security_alerts_active = models.PositiveIntegerField(
        default=0,
        help_text="Active security alerts"
    )

    failed_authentications_last_hour = models.PositiveIntegerField(
        default=0,
        help_text="Failed authentication attempts in last hour"
    )

    # Operational metrics
    coverage_percentage = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Site coverage percentage"
    )

    operational_efficiency = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall operational efficiency score"
    )

    snapshot_taken_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When snapshot was taken"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_performance_snapshot'
        verbose_name = 'Performance Snapshot'
        verbose_name_plural = 'Performance Snapshots'
        ordering = ['-snapshot_taken_at']
        indexes = [
            models.Index(fields=['snapshot_taken_at']),
        ]

    def __str__(self):
        return f"Performance Snapshot - {self.snapshot_taken_at.strftime('%Y-%m-%d %H:%M')}"


class UserActivityPattern(BaseModel, TenantAwareModel):
    """
    Learned user activity patterns for anomaly detection.

    Tracks normal behavior patterns to identify anomalies.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity_pattern',
        help_text="User whose patterns are tracked"
    )

    # Temporal patterns
    typical_work_hours = models.JSONField(
        default=list,
        help_text="Typical working hours (list of hour integers)"
    )

    typical_work_days = models.JSONField(
        default=list,
        help_text="Typical working days (0-6, Monday-Sunday)"
    )

    avg_shift_duration_hours = models.FloatField(
        default=8.0,
        help_text="Average shift duration in hours"
    )

    # Movement patterns
    avg_steps_per_hour = models.FloatField(
        default=0,
        help_text="Average steps per hour during work"
    )

    typical_movement_variance = models.FloatField(
        default=0,
        help_text="Typical variance in movement patterns"
    )

    primary_work_sites = models.JSONField(
        default=list,
        help_text="Primary work sites with frequency"
    )

    # Device usage patterns
    avg_battery_usage_per_hour = models.FloatField(
        default=0,
        help_text="Average battery usage percentage per hour"
    )

    typical_app_usage = models.JSONField(
        default=dict,
        help_text="Typical app usage patterns"
    )

    normal_network_usage = models.FloatField(
        default=0,
        help_text="Normal network data usage per shift"
    )

    # Performance baselines
    normal_response_times = models.JSONField(
        default=dict,
        help_text="Normal response time ranges for different actions"
    )

    typical_sync_frequency = models.FloatField(
        default=0,
        help_text="Typical data sync frequency per hour"
    )

    # Anomaly thresholds
    movement_anomaly_threshold = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Threshold for movement anomaly detection"
    )

    battery_anomaly_threshold = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Threshold for battery usage anomaly detection"
    )

    behavior_anomaly_threshold = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Threshold for behavioral anomaly detection"
    )

    # Learning metadata
    total_observations = models.PositiveIntegerField(
        default=0,
        help_text="Total number of observations used for learning"
    )

    last_pattern_update = models.DateTimeField(
        auto_now=True,
        help_text="Last time patterns were updated"
    )

    pattern_confidence = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence in learned patterns (0-1)"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_user_activity_pattern'
        verbose_name = 'User Activity Pattern'
        verbose_name_plural = 'User Activity Patterns'
        indexes = [
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['last_pattern_update']),
            models.Index(fields=['pattern_confidence']),
        ]

    def __str__(self):
        return f"Activity Pattern - {self.user.peoplename} (confidence: {self.pattern_confidence:.2f})"

    @property
    def is_well_established(self):
        """Check if pattern has enough data to be reliable"""
        return self.total_observations >= 50 and self.pattern_confidence >= 0.7

    def detect_anomaly(self, current_data):
        """Detect if current data represents an anomaly"""
        anomalies = []

        # Check movement anomaly
        if 'steps_per_hour' in current_data:
            if abs(current_data['steps_per_hour'] - self.avg_steps_per_hour) > (
                self.avg_steps_per_hour * self.movement_anomaly_threshold
            ):
                anomalies.append('movement_anomaly')

        # Check battery usage anomaly
        if 'battery_usage_per_hour' in current_data:
            if abs(current_data['battery_usage_per_hour'] - self.avg_battery_usage_per_hour) > (
                self.avg_battery_usage_per_hour * self.battery_anomaly_threshold
            ):
                anomalies.append('battery_anomaly')

        return anomalies


class SystemHealthMetric(BaseModel):
    """
    System-wide health metrics for monitoring infrastructure health.

    Tracks the health of the monitoring system itself.
    """

    METRIC_NAMES = [
        ('ALERT_PROCESSING_TIME', 'Alert Processing Time'),
        ('DEVICE_DATA_INGESTION_RATE', 'Device Data Ingestion Rate'),
        ('SYSTEM_RESPONSE_TIME', 'System Response Time'),
        ('DATABASE_PERFORMANCE', 'Database Performance'),
        ('CACHE_HIT_RATE', 'Cache Hit Rate'),
        ('BACKGROUND_TASK_SUCCESS_RATE', 'Background Task Success Rate'),
        ('NOTIFICATION_DELIVERY_RATE', 'Notification Delivery Rate'),
        ('ML_MODEL_ACCURACY', 'ML Model Accuracy'),
    ]

    metric_name = models.CharField(
        max_length=50,
        choices=METRIC_NAMES,
        db_index=True,
        help_text="Name of the system metric"
    )

    value = models.FloatField(
        help_text="Metric value"
    )

    unit = models.CharField(
        max_length=20,
        help_text="Unit of measurement"
    )

    threshold_warning = models.FloatField(
        null=True,
        blank=True,
        help_text="Warning threshold value"
    )

    threshold_critical = models.FloatField(
        null=True,
        blank=True,
        help_text="Critical threshold value"
    )

    metadata = models.JSONField(
        default=dict,
        help_text="Additional metric metadata"
    )

    recorded_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When metric was recorded"
    )

    class Meta(BaseModel.Meta):
        db_table = 'monitoring_system_health_metric'
        verbose_name = 'System Health Metric'
        verbose_name_plural = 'System Health Metrics'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['metric_name', 'recorded_at']),
        ]

    def __str__(self):
        return f"{self.metric_name}: {self.value} {self.unit}"

    @property
    def status(self):
        """Get metric status based on thresholds"""
        if self.threshold_critical and self.value >= self.threshold_critical:
            return 'CRITICAL'
        elif self.threshold_warning and self.value >= self.threshold_warning:
            return 'WARNING'
        else:
            return 'OK'