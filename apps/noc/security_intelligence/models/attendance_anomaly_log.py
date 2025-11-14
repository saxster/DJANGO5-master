"""
Attendance Anomaly Log Model.

Records detected attendance anomalies for audit trail and analysis.
Linked to NOC alert system for real-time notifications.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class AttendanceAnomalyLog(BaseModel, TenantAwareModel):
    """
    Log of detected attendance anomalies.

    Records anomalies for investigation, reporting, and ML training.
    """

    ANOMALY_TYPE_CHOICES = [
        ('WRONG_PERSON', 'Wrong Person at Site'),
        ('UNAUTHORIZED_SITE', 'Unauthorized Site Access'),
        ('IMPOSSIBLE_SHIFTS', 'Impossible Back-to-Back Shifts'),
        ('OVERTIME_VIOLATION', 'Overtime Violation'),
        ('BUDDY_PUNCHING', 'Buddy Punching Detected'),
        ('GPS_SPOOFING', 'GPS Spoofing Suspected'),
        ('GEOFENCE_VIOLATION', 'Geofence Violation'),
        ('BIOMETRIC_ANOMALY', 'Biometric Pattern Anomaly'),
        ('SCHEDULE_MISMATCH', 'Schedule Mismatch'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('DETECTED', 'Detected'),
        ('INVESTIGATING', 'Under Investigation'),
        ('CONFIRMED', 'Confirmed Fraud'),
        ('FALSE_POSITIVE', 'False Positive'),
        ('RESOLVED', 'Resolved'),
    ]

    anomaly_type = models.CharField(
        max_length=30,
        choices=ANOMALY_TYPE_CHOICES,
        db_index=True,
        help_text="Type of anomaly detected"
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        db_index=True,
        help_text="Severity of the anomaly"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DETECTED',
        db_index=True,
        help_text="Investigation status"
    )

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_anomalies',
        help_text="Person involved in anomaly"
    )

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='attendance_anomalies',
        help_text="Site where anomaly occurred"
    )

    attendance_event = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detected_anomalies',
        help_text="Related attendance event"
    )

    noc_alert = models.ForeignKey(
        'noc.NOCAlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_anomalies',
        help_text="Related NOC alert"
    )

    detected_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When anomaly was detected"
    )

    confidence_score = models.FloatField(
        help_text="Detection confidence (0-1)"
    )

    # Anomaly details
    expected_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expected_at_site',
        help_text="Expected person (for WRONG_PERSON)"
    )

    distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance for travel analysis (km)"
    )

    time_available_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time available for travel (minutes)"
    )

    time_required_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time required for travel (minutes)"
    )

    continuous_work_hours = models.FloatField(
        null=True,
        blank=True,
        help_text="Continuous work hours (for overtime)"
    )

    evidence_data = models.JSONField(
        default=dict,
        help_text="Additional evidence and metadata"
    )

    # Investigation fields
    investigated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investigated_anomalies',
        help_text="Investigator"
    )

    investigated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When investigation completed"
    )

    investigation_notes = models.TextField(
        blank=True,
        help_text="Investigation findings"
    )

    action_taken = models.TextField(
        blank=True,
        help_text="Actions taken to resolve"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_attendance_anomaly_log'
        verbose_name = 'Attendance Anomaly Log'
        verbose_name_plural = 'Attendance Anomaly Logs'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['tenant', 'detected_at']),
            models.Index(fields=['person', 'detected_at']),
            models.Index(fields=['site', 'anomaly_type', 'detected_at']),
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['anomaly_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_anomaly_type_display()} - {self.person.peoplename} @ {self.site.name}"

    def mark_confirmed(self, investigated_by, notes=""):
        """Mark anomaly as confirmed fraud."""
        self.status = 'CONFIRMED'
        self.investigated_by = investigated_by
        self.investigated_at = timezone.now()
        if notes:
            self.investigation_notes = notes
        self.save()

    def mark_false_positive(self, investigated_by, notes=""):
        """Mark anomaly as false positive."""
        self.status = 'FALSE_POSITIVE'
        self.investigated_by = investigated_by
        self.investigated_at = timezone.now()
        if notes:
            self.investigation_notes = notes
        self.save()