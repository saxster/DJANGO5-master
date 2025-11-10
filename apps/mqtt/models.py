"""
MQTT Telemetry Data Models

@ontology(
    domain="integration",
    purpose="Persistent storage for MQTT telemetry data from IoT devices, guards, and facility sensors",
    models=[
        "DeviceTelemetry - Battery, signal, temperature, connectivity metrics",
        "GuardLocation - GPS tracking history with geofence validation",
        "SensorReading - Facility sensor data (motion, door, smoke, etc.)",
        "DeviceAlert - Critical alerts (panic, SOS, intrusion)"
    ],
    data_sources=["MQTT broker via apps/mqtt/subscriber.py"],
    integration_points=[
        "background_tasks/mqtt_handler_tasks.py (Celery persistence)",
        "apps/onboarding/models/approved_location.py (geofence validation)",
        "monitoring/services/prometheus_metrics.py (metrics export)"
    ],
    geospatial_features=["PostGIS Point for GPS coordinates", "Geofence boundary validation"],
    compliance=[".claude/rules.md Rule #7 (< 150 lines per model)"],
    criticality="high",
    dependencies=["Django", "PostGIS", "TenantAwareModel"],
    tags=["mqtt", "telemetry", "iot", "gps", "sensors", "alerts"]
)
"""

import logging
import uuid
from typing import Dict, Any
from datetime import datetime, timezone as dt_timezone

from django.db import models
from django.contrib.gis.db.models import PointField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.peoples.models import BaseModel, People
from apps.tenants.models import TenantAwareModel

logger = logging.getLogger(__name__)


class DeviceTelemetry(BaseModel, TenantAwareModel):
    """
    Device telemetry data from IoT sensors.

    Stores periodic health metrics (battery, signal, temperature)
    from field devices. Used for predictive maintenance and device monitoring.

    Compliance: Rule #7 (< 150 lines)
    """

    # Device identification
    device_id = models.CharField(
        _("Device ID"),
        max_length=100,
        db_index=True,
        help_text="Unique device identifier from MQTT topic"
    )

    # Telemetry metrics
    battery_level = models.IntegerField(
        _("Battery Level"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Battery percentage (0-100)"
    )

    signal_strength = models.IntegerField(
        _("Signal Strength"),
        validators=[MinValueValidator(-120), MaxValueValidator(0)],
        null=True,
        blank=True,
        help_text="Signal strength in dBm (-120 to 0)"
    )

    temperature = models.FloatField(
        _("Temperature"),
        null=True,
        blank=True,
        help_text="Device temperature in Celsius"
    )

    connectivity_status = models.CharField(
        _("Connectivity Status"),
        max_length=20,
        null=True,
        blank=True,
        help_text="Network connectivity state (ONLINE, OFFLINE, POOR)"
    )

    # Metadata
    timestamp = models.DateTimeField(
        _("Timestamp"),
        db_index=True,
        help_text="Device-reported timestamp"
    )

    received_at = models.DateTimeField(
        _("Received At"),
        auto_now_add=True,
        help_text="Server received timestamp"
    )

    raw_data = models.JSONField(
        _("Raw MQTT Payload"),
        help_text="Complete MQTT message payload"
    )

    class Meta:
        db_table = 'mqtt_device_telemetry'
        verbose_name = _("Device Telemetry")
        verbose_name_plural = _("Device Telemetry")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device_id', '-timestamp'], name='mqtt_device_ts_idx'),
            models.Index(fields=['received_at'], name='mqtt_device_received_idx'),
        ]

    def __str__(self):
        return f"{self.device_id} @ {self.timestamp} (Battery: {self.battery_level}%)"


class GuardLocation(BaseModel, TenantAwareModel):
    """
    Guard GPS location tracking history.

    Stores real-time GPS coordinates from guard devices with geofence
    validation. Used for attendance verification and safety monitoring.

    Compliance: Rule #7 (< 150 lines)
    """

    # Guard identification
    guard = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='gps_locations',
        help_text="Guard person record"
    )

    # Geographic data (PostGIS)
    location = PointField(
        _("GPS Coordinates"),
        srid=4326,  # WGS84
        geography=True,
        help_text="GPS coordinates (lon, lat)"
    )

    accuracy = models.FloatField(
        _("GPS Accuracy"),
        validators=[MinValueValidator(0)],
        help_text="GPS accuracy in meters"
    )

    # Geofence validation
    in_geofence = models.BooleanField(
        _("Within Geofence"),
        default=False,
        db_index=True,
        help_text="Whether location is within assigned geofence(s)"
    )

    geofence_violation = models.BooleanField(
        _("Geofence Violation"),
        default=False,
        db_index=True,
        help_text="True if guard is outside permitted areas"
    )

    # Metadata
    timestamp = models.DateTimeField(
        _("Timestamp"),
        db_index=True,
        help_text="Device-reported timestamp"
    )

    received_at = models.DateTimeField(
        _("Received At"),
        auto_now_add=True,
        help_text="Server received timestamp"
    )

    raw_data = models.JSONField(
        _("Raw MQTT Payload"),
        help_text="Complete MQTT message payload"
    )

    class Meta:
        db_table = 'mqtt_guard_location'
        verbose_name = _("Guard Location")
        verbose_name_plural = _("Guard Locations")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['guard', '-timestamp'], name='mqtt_guard_ts_idx'),
            models.Index(fields=['geofence_violation', '-timestamp'], name='mqtt_guard_violation_idx'),
        ]

    def __str__(self):
        status = "IN" if self.in_geofence else "OUT"
        return f"Guard {self.guard_id} @ {self.timestamp} ({status} geofence)"


class SensorReading(BaseModel, TenantAwareModel):
    """
    Facility sensor data readings.

    Stores data from motion sensors, door sensors, smoke detectors,
    temperature sensors, etc. Used for facility monitoring and security.

    Compliance: Rule #7 (< 150 lines)
    """

    SENSOR_TYPES = [
        ('MOTION', 'Motion Detector'),
        ('DOOR', 'Door/Window Sensor'),
        ('SMOKE', 'Smoke Detector'),
        ('TEMPERATURE', 'Temperature Sensor'),
        ('HUMIDITY', 'Humidity Sensor'),
        ('WATER_LEAK', 'Water Leak Detector'),
        ('INTRUSION', 'Intrusion Sensor'),
        ('GLASS_BREAK', 'Glass Break Detector'),
    ]

    STATE_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('DETECTED', 'Detected'),
        ('CLEAR', 'Clear'),
        ('ALARM', 'Alarm'),
        ('NORMAL', 'Normal'),
    ]

    # Sensor identification
    sensor_id = models.CharField(
        _("Sensor ID"),
        max_length=100,
        db_index=True,
        help_text="Unique sensor identifier from MQTT topic"
    )

    sensor_type = models.CharField(
        _("Sensor Type"),
        max_length=20,
        choices=SENSOR_TYPES,
        db_index=True,
        help_text="Type of sensor"
    )

    # Sensor data
    value = models.FloatField(
        _("Sensor Value"),
        null=True,
        blank=True,
        help_text="Numeric sensor reading (temperature, smoke level, etc.)"
    )

    state = models.CharField(
        _("Sensor State"),
        max_length=20,
        choices=STATE_CHOICES,
        null=True,
        blank=True,
        help_text="State-based reading (open/closed, detected/clear)"
    )

    # Metadata
    timestamp = models.DateTimeField(
        _("Timestamp"),
        db_index=True,
        help_text="Sensor-reported timestamp"
    )

    received_at = models.DateTimeField(
        _("Received At"),
        auto_now_add=True,
        help_text="Server received timestamp"
    )

    raw_data = models.JSONField(
        _("Raw MQTT Payload"),
        help_text="Complete MQTT message payload"
    )

    class Meta:
        db_table = 'mqtt_sensor_reading'
        verbose_name = _("Sensor Reading")
        verbose_name_plural = _("Sensor Readings")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['sensor_id', '-timestamp'], name='mqtt_sensor_ts_idx'),
            models.Index(fields=['sensor_type', '-timestamp'], name='mqtt_sensor_type_idx'),
        ]

    def __str__(self):
        return f"{self.sensor_type} {self.sensor_id} @ {self.timestamp}: {self.value or self.state}"


class DeviceAlert(BaseModel, TenantAwareModel):
    """
    Critical alerts from IoT devices.

    Stores panic button events, SOS signals, intrusion detection,
    and other critical device-generated alerts. Requires acknowledgment workflow.

    Compliance: Rule #7 (< 150 lines)
    """

    ALERT_TYPES = [
        ('PANIC', 'Panic Button'),
        ('SOS', 'SOS Distress Signal'),
        ('INTRUSION', 'Intrusion Detected'),
        ('FIRE', 'Fire Alarm'),
        ('MEDICAL', 'Medical Emergency'),
        ('EQUIPMENT_FAILURE', 'Equipment Failure'),
        ('GEOFENCE_VIOLATION', 'Geofence Violation'),
        ('LOW_BATTERY', 'Critical Low Battery'),
        ('OFFLINE', 'Device Offline'),
    ]

    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]

    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('FALSE_ALARM', 'False Alarm'),
    ]

    # Alert identification
    alert_uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False
    )

    source_id = models.CharField(
        _("Source Device/Guard ID"),
        max_length=100,
        db_index=True,
        help_text="Device or guard identifier that triggered alert"
    )

    # Alert details
    alert_type = models.CharField(
        _("Alert Type"),
        max_length=30,
        choices=ALERT_TYPES,
        db_index=True
    )

    severity = models.CharField(
        _("Severity"),
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='HIGH',
        db_index=True
    )

    message = models.TextField(
        _("Alert Message"),
        help_text="Human-readable alert description"
    )

    # Geographic data (optional - if device reports location)
    location = PointField(
        _("Alert Location"),
        srid=4326,
        geography=True,
        null=True,
        blank=True,
        help_text="GPS coordinates of alert (if available)"
    )

    # Acknowledgment workflow
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        db_index=True
    )

    acknowledged_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mqtt_acknowledged_alerts',
        help_text="Person who acknowledged alert"
    )

    acknowledged_at = models.DateTimeField(
        _("Acknowledged At"),
        null=True,
        blank=True,
        help_text="When alert was acknowledged"
    )

    resolved_at = models.DateTimeField(
        _("Resolved At"),
        null=True,
        blank=True,
        help_text="When alert was resolved"
    )

    # Metadata
    timestamp = models.DateTimeField(
        _("Alert Timestamp"),
        db_index=True,
        help_text="Device-reported alert time"
    )

    received_at = models.DateTimeField(
        _("Received At"),
        auto_now_add=True,
        help_text="Server received timestamp"
    )

    raw_data = models.JSONField(
        _("Raw MQTT Payload"),
        help_text="Complete MQTT message payload"
    )

    # Notification tracking
    sms_sent = models.BooleanField(
        _("SMS Sent"),
        default=False,
        help_text="Whether SMS notification was sent"
    )

    email_sent = models.BooleanField(
        _("Email Sent"),
        default=False,
        help_text="Whether email notification was sent"
    )

    push_sent = models.BooleanField(
        _("Push Notification Sent"),
        default=False,
        help_text="Whether mobile push notification was sent"
    )

    class Meta:
        db_table = 'mqtt_device_alert'
        verbose_name = _("Device Alert")
        verbose_name_plural = _("Device Alerts")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['source_id', '-timestamp'], name='mqtt_alert_source_idx'),
            models.Index(fields=['alert_type', 'severity', '-timestamp'], name='mqtt_alert_type_idx'),
            models.Index(fields=['status', '-timestamp'], name='mqtt_alert_status_idx'),
        ]

    def __str__(self):
        return f"{self.alert_type} from {self.source_id} ({self.severity}) @ {self.timestamp}"

    def acknowledge(self, user: People):
        """Acknowledge alert with user and timestamp."""
        self.status = 'ACKNOWLEDGED'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])

    def resolve(self):
        """Mark alert as resolved."""
        self.status = 'RESOLVED'
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
