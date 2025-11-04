"""
Fraud Alert Model

Tracks fraud detection alerts for manager review.

Features:
- Real-time fraud alerts
- Manager assignment
- Investigation workflow
- Resolution tracking
- Escalation management
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
import uuid


class FraudAlert(BaseModel, TenantAwareModel):
    """
    Fraud detection alert requiring investigation.
    """

    class AlertType(models.TextChoices):
        BUDDY_PUNCHING = 'BUDDY_PUNCHING', 'Buddy Punching'
        GPS_SPOOFING = 'GPS_SPOOFING', 'GPS Spoofing'
        IMPOSSIBLE_TRAVEL = 'IMPOSSIBLE_TRAVEL', 'Impossible Travel'
        DEVICE_SHARING = 'DEVICE_SHARING', 'Device Sharing'
        UNUSUAL_PATTERN = 'UNUSUAL_PATTERN', 'Unusual Pattern'
        BIOMETRIC_MISMATCH = 'BIOMETRIC_MISMATCH', 'Biometric Mismatch'
        TEMPORAL_ANOMALY = 'TEMPORAL_ANOMALY', 'Temporal Anomaly'
        HIGH_RISK_BEHAVIOR = 'HIGH_RISK_BEHAVIOR', 'High Risk Behavior'

    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        INVESTIGATING = 'INVESTIGATING', 'Under Investigation'
        RESOLVED_LEGITIMATE = 'RESOLVED_LEGITIMATE', 'Resolved - Legitimate'
        RESOLVED_FRAUD = 'RESOLVED_FRAUD', 'Resolved - Fraud Confirmed'
        FALSE_POSITIVE = 'FALSE_POSITIVE', 'False Positive'
        ESCALATED = 'ESCALATED', 'Escalated'

    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, db_index=True)

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fraud_alerts',
        help_text="Employee flagged for suspicious activity"
    )

    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.CASCADE,
        related_name='fraud_alerts',
        help_text="Attendance record that triggered alert"
    )

    alert_type = models.CharField(max_length=50, choices=AlertType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)

    fraud_score = models.FloatField(help_text="Fraud detection score (0-1)")
    risk_score = models.IntegerField(help_text="Risk score (0-100)")

    detection_timestamp = models.DateTimeField(default=timezone.now)
    evidence = models.JSONField(help_text="Evidence and anomaly details")
    anomalies_detected = models.JSONField(default=list)

    # Investigation
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_fraud_alerts',
        help_text="Manager assigned to investigate"
    )

    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_fraud_alerts'
    )

    investigation_notes = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)

    # Actions taken
    auto_blocked = models.BooleanField(default=False, help_text="Was attendance auto-blocked")
    manager_notified = models.BooleanField(default=False)
    employee_notified = models.BooleanField(default=False)

    # Escalation
    is_escalated = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'fraud_alert'
        verbose_name = 'Fraud Alert'
        verbose_name_plural = 'Fraud Alerts'
        indexes = [
            models.Index(fields=['tenant', 'status'], name='fa_tenant_status_idx'),
            models.Index(fields=['tenant', 'employee'], name='fa_tenant_emp_idx'),
            models.Index(fields=['severity', 'status'], name='fa_severity_status_idx'),
            models.Index(fields=['assigned_to', 'status'], name='fa_assigned_status_idx'),
            models.Index(fields=['detection_timestamp'], name='fa_detection_time_idx'),
        ]
        ordering = ['-detection_timestamp']

    def __str__(self):
        return f"{self.alert_type} - {self.employee.username} ({self.severity})"
