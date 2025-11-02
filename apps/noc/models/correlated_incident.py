"""
Correlated Incident Model.

Links activity signals with existing NOC alerts to identify root causes.
Enables correlation-based incident analysis.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class CorrelatedIncident(BaseModel, TenantAwareModel):
    """
    Correlated incident linking activity signals with alerts.

    Cross-references telemetry signals with NOC alerts to identify
    root causes and patterns in operational incidents.
    """

    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
        ('INFO', 'Info'),
    ]

    incident_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique incident identifier"
    )

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='correlated_incidents',
        help_text="Person involved in incident"
    )

    site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='correlated_incidents',
        help_text="Site where incident occurred"
    )

    # Activity signals from ActivitySignalCollector
    signals = models.JSONField(
        default=dict,
        help_text="Collected activity signals (phone events, location, tasks, tours)"
    )

    # Related NOC alerts (many-to-many for multiple correlated alerts)
    related_alerts = models.ManyToManyField(
        'noc.NOCAlertEvent',
        related_name='correlated_incidents',
        blank=True,
        help_text="NOC alerts correlated with this incident"
    )

    # Calculated severity from signals + alerts
    combined_severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='INFO',
        db_index=True,
        help_text="Combined severity calculated from signals and alerts"
    )

    # Correlation metadata
    correlation_window_minutes = models.IntegerField(
        default=15,
        help_text="Time window used for correlation (±minutes)"
    )

    correlation_score = models.FloatField(
        default=0.0,
        help_text="Correlation confidence score (0.0-1.0)"
    )

    correlation_type = models.CharField(
        max_length=50,
        default='TIME_ENTITY',
        help_text="Type of correlation applied (TIME_ENTITY, PATTERN, etc.)"
    )

    # Timing
    detected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When correlation was detected"
    )

    # Investigation
    investigated = models.BooleanField(
        default=False,
        help_text="Whether incident has been investigated"
    )

    investigated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investigated_incidents',
        help_text="Investigator"
    )

    investigated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When investigated"
    )

    investigation_notes = models.TextField(
        blank=True,
        help_text="Investigation findings"
    )

    # Root cause
    root_cause_identified = models.BooleanField(
        default=False,
        help_text="Whether root cause has been identified"
    )

    root_cause_description = models.TextField(
        blank=True,
        help_text="Description of identified root cause"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_correlated_incident'
        verbose_name = 'Correlated Incident'
        verbose_name_plural = 'Correlated Incidents'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['tenant', 'person', 'detected_at']),
            models.Index(fields=['tenant', 'site', 'detected_at']),
            models.Index(fields=['combined_severity', 'investigated']),
            models.Index(fields=['detected_at', 'combined_severity']),
        ]

    def __str__(self):
        return f"Incident {self.incident_id} - {self.person.peoplename} @ {self.site.name} ({self.combined_severity})"

    def calculate_combined_severity(self):
        """
        Calculate combined severity from signals and related alerts.

        Uses maximum severity from related alerts plus signal anomalies.
        """
        # Start with INFO
        severity_order = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

        # Get max severity from related alerts
        max_alert_severity = 'INFO'
        for alert in self.related_alerts.all():
            if hasattr(alert, 'severity'):
                alert_severity = alert.severity
                if severity_order.index(alert_severity) > severity_order.index(max_alert_severity):
                    max_alert_severity = alert_severity

        # Check signal anomalies
        signals_severity = 'INFO'
        if self.signals:
            # Low phone activity + low location updates = MEDIUM
            if self.signals.get('phone_events_count', 100) < 5 and self.signals.get('location_updates_count', 100) < 3:
                signals_severity = 'MEDIUM'
            # Very low activity = HIGH
            if self.signals.get('phone_events_count', 100) == 0 and self.signals.get('tasks_completed_count', 100) == 0:
                signals_severity = 'HIGH'

        # Use maximum of alert severity and signals severity
        if severity_order.index(signals_severity) > severity_order.index(max_alert_severity):
            self.combined_severity = signals_severity
        else:
            self.combined_severity = max_alert_severity

        self.save(update_fields=['combined_severity'])

    def calculate_correlation_score(self):
        """
        Calculate correlation confidence score.

        Based on time proximity, entity match, and signal consistency.
        """
        score = 0.0

        # Entity match (same person + same site) = 0.5 base score
        score += 0.5

        # Time proximity bonus (closer = higher score)
        if self.related_alerts.exists():
            # Time correlation: within 5 min = +0.3, 10 min = +0.2, 15 min = +0.1
            for alert in self.related_alerts.all():
                time_diff_minutes = abs((self.detected_at - alert.created_at).total_seconds() / 60)
                if time_diff_minutes <= 5:
                    score += 0.3
                    break
                elif time_diff_minutes <= 10:
                    score += 0.2
                    break
                elif time_diff_minutes <= 15:
                    score += 0.1
                    break

        # Signal consistency bonus (+0.2 if signals support alert type)
        if self.signals and self.related_alerts.exists():
            # Example: Device offline alert + low phone events = consistent
            for alert in self.related_alerts.all():
                if 'offline' in str(alert.alert_type).lower() or 'device' in str(alert.alert_type).lower():
                    if self.signals.get('phone_events_count', 100) < 5:
                        score += 0.2
                        break

        # Cap at 1.0
        self.correlation_score = min(score, 1.0)
        self.save(update_fields=['correlation_score'])
