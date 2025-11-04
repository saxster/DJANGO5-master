"""
Alert & Monitoring Models (Phase 5)

Models for real-time attendance monitoring and alerting:
- AlertRule: Configurable alert rules with thresholds
- AttendanceAlert: Alert instances when rules trigger
- AlertEscalation: Escalation tracking for unacknowledged alerts

Industry Standard: 10 alert types covering all critical scenarios

Author: Claude Code
Created: 2025-11-03
Phase: 5 - Real-Time Monitoring
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel, TenantAwareModel

import logging

logger = logging.getLogger(__name__)


class AlertRule(BaseModel, TenantAwareModel):
    """
    Configurable alert rules for attendance monitoring.

    Standard Rules (Industry Best Practice 2025):
    1. No-Show Alert (30 min after shift start)
    2. Late Check-In Alert (grace period expired)
    3. Wrong Post Alert (outside geofence)
    4. Missing Check-Out Alert (2 hours after shift end)
    5. Coverage Gap Alert (post vacant with no assignment)
    6. Overtime Warning (approaching 12 hours)
    7. Rest Period Violation (< 10 hours since last shift)
    8. Multiple Mismatch Alert (3+ failures in 24h)
    9. Geofence Breach Alert (worker left assigned area)
    10. Certification Expiry Alert (7 days before expiry)
    """

    class AlertType(models.TextChoices):
        """Alert types"""
        NO_SHOW = 'NO_SHOW', _('No-Show Alert')
        LATE_CHECKIN = 'LATE_CHECKIN', _('Late Check-in Alert')
        WRONG_POST = 'WRONG_POST', _('Wrong Post Alert')
        MISSING_CHECKOUT = 'MISSING_CHECKOUT', _('Missing Check-out Alert')
        COVERAGE_GAP = 'COVERAGE_GAP', _('Coverage Gap Alert')
        OVERTIME_WARNING = 'OVERTIME_WARNING', _('Overtime Warning')
        REST_VIOLATION = 'REST_VIOLATION', _('Rest Period Violation')
        MULTIPLE_MISMATCH = 'MULTIPLE_MISMATCH', _('Multiple Mismatch Alert')
        GEOFENCE_BREACH = 'GEOFENCE_BREACH', _('Geofence Breach Alert')
        CERT_EXPIRY = 'CERT_EXPIRY', _('Certification Expiry Alert')
        CUSTOM = 'CUSTOM', _('Custom Alert')

    class Severity(models.TextChoices):
        """Alert severity"""
        CRITICAL = 'CRITICAL', _('Critical')
        HIGH = 'HIGH', _('High')
        MEDIUM = 'MEDIUM', _('Medium')
        LOW = 'LOW', _('Low')
        INFO = 'INFO', _('Informational')

    # ========== Rule Identification ==========

    rule_name = models.CharField(
        max_length=100,
        help_text=_("Descriptive name for this rule")
    )

    rule_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Unique code for this rule")
    )

    alert_type = models.CharField(
        max_length=30,
        choices=AlertType.choices,
        db_index=True,
        help_text=_("Type of alert this rule generates")
    )

    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.MEDIUM,
        db_index=True,
        help_text=_("Alert severity level")
    )

    # ========== Rule Status ==========

    active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this rule is currently active")
    )

    description = models.TextField(
        blank=True,
        help_text=_("Description of when this alert triggers")
    )

    # ========== Thresholds & Configuration ==========

    threshold_minutes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        help_text=_("Time threshold in minutes (e.g., 30 for no-show)")
    )

    threshold_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text=_("Count threshold (e.g., 3 for multiple mismatches)")
    )

    threshold_percentage = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text=_("Percentage threshold (e.g., 50% for coverage gap)")
    )

    # ========== Scope Filters ==========

    applies_to_sites = models.ManyToManyField(
        'onboarding.Bt',
        blank=True,
        related_name='alert_rules',
        help_text=_("Sites this rule applies to (empty = all sites)")
    )

    applies_to_shifts = models.ManyToManyField(
        'onboarding.Shift',
        blank=True,
        related_name='alert_rules',
        help_text=_("Shifts this rule applies to (empty = all shifts)")
    )

    applies_to_risk_levels = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Post risk levels this rule applies to (empty = all)")
    )

    # ========== Actions ==========

    send_notification = models.BooleanField(
        default=True,
        help_text=_("Send notification when alert triggers")
    )

    create_ticket = models.BooleanField(
        default=False,
        help_text=_("Create helpdesk ticket when alert triggers")
    )

    notification_recipients = models.ManyToManyField(
        'peoples.People',
        blank=True,
        related_name='alert_rule_notifications',
        help_text=_("People to notify when this alert triggers")
    )

    notification_template = models.TextField(
        blank=True,
        help_text=_("Notification message template (supports variables)")
    )

    # ========== Escalation ==========

    escalation_enabled = models.BooleanField(
        default=False,
        help_text=_("Enable escalation if alert not acknowledged")
    )

    escalation_delay_minutes = models.IntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(1440)],
        help_text=_("Minutes to wait before escalating")
    )

    escalation_recipients = models.ManyToManyField(
        'peoples.People',
        blank=True,
        related_name='alert_rule_escalations',
        help_text=_("People to escalate to if not acknowledged")
    )

    # ========== Deduplication ==========

    deduplicate_window_minutes = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        help_text=_("Don't create duplicate alerts within this window (minutes)")
    )

    # ========== Statistics ==========

    times_triggered = models.IntegerField(
        default=0,
        help_text=_("Number of times this rule has triggered")
    )

    last_triggered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When this rule last triggered")
    )

    # ========== Metadata ==========

    rule_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Extensible rule configuration")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_alert_rule'
        verbose_name = _('Alert Rule')
        verbose_name_plural = _('Alert Rules')
        indexes = [
            models.Index(fields=['tenant', 'active', 'alert_type'], name='ar_active_type_idx'),
            models.Index(fields=['tenant', 'severity'], name='ar_severity_idx'),
        ]
        ordering = ['severity', 'rule_name']

    def __str__(self):
        return f"{self.rule_name} ({self.get_severity_display()}) - {self.times_triggered} triggers"


class AttendanceAlert(BaseModel, TenantAwareModel):
    """
    Alert instances when rules trigger.

    Tracks individual alert occurrences with:
    - When triggered
    - Who it's for
    - What triggered it
    - Who acknowledged it
    - Resolution details
    """

    class AlertStatus(models.TextChoices):
        """Alert lifecycle status"""
        ACTIVE = 'ACTIVE', _('Active')
        ACKNOWLEDGED = 'ACKNOWLEDGED', _('Acknowledged')
        RESOLVED = 'RESOLVED', _('Resolved')
        ESCALATED = 'ESCALATED', _('Escalated')
        AUTO_RESOLVED = 'AUTO_RESOLVED', _('Auto-Resolved')
        CANCELLED = 'CANCELLED', _('Cancelled')

    # ========== Alert Identification ==========

    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.CASCADE,
        related_name='alerts',
        db_index=True,
        help_text=_("Rule that triggered this alert")
    )

    status = models.CharField(
        max_length=20,
        choices=AlertStatus.choices,
        default=AlertStatus.ACTIVE,
        db_index=True,
        help_text=_("Current alert status")
    )

    severity = models.CharField(
        max_length=10,
        choices=AlertRule.Severity.choices,
        db_index=True,
        help_text=_("Alert severity (copied from rule)")
    )

    # ========== Alert Context ==========

    triggered_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_("When alert was triggered")
    )

    triggered_for_worker = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts_for',
        help_text=_("Worker this alert is about")
    )

    triggered_for_site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts',
        help_text=_("Site this alert is for")
    )

    triggered_for_post = models.ForeignKey(
        'attendance.Post',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts',
        help_text=_("Post this alert is for")
    )

    triggered_for_assignment = models.ForeignKey(
        'attendance.PostAssignment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts',
        help_text=_("Assignment this alert is for")
    )

    # ========== Alert Message ==========

    title = models.CharField(
        max_length=200,
        help_text=_("Alert title")
    )

    message = models.TextField(
        help_text=_("Alert message/description")
    )

    # ========== Acknowledgement ==========

    acknowledged_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_acknowledged',
        help_text=_("Who acknowledged this alert")
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=_("When alert was acknowledged")
    )

    acknowledgement_notes = models.TextField(
        blank=True,
        help_text=_("Notes from acknowledger")
    )

    # ========== Resolution ==========

    resolved_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_resolved',
        help_text=_("Who resolved this alert")
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When alert was resolved")
    )

    resolution_notes = models.TextField(
        blank=True,
        help_text=_("How alert was resolved")
    )

    # ========== Escalation ==========

    escalated = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Whether alert was escalated")
    )

    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When alert was escalated")
    )

    escalated_to = models.ManyToManyField(
        'peoples.People',
        blank=True,
        related_name='escalated_alerts',
        help_text=_("People alert was escalated to")
    )

    # ========== Metrics ==========

    time_to_acknowledge_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Minutes from trigger to acknowledgement")
    )

    time_to_resolve_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Minutes from trigger to resolution")
    )

    # ========== Metadata ==========

    alert_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Alert context data (GPS, validation details, metrics, etc.)"
        )
    )

    # ========== Related Records ==========

    related_ticket = models.ForeignKey(
        'y_helpdesk.Ticket',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_alerts',
        help_text=_("Helpdesk ticket created for this alert")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_alert'
        verbose_name = _('Attendance Alert')
        verbose_name_plural = _('Attendance Alerts')
        indexes = [
            models.Index(fields=['tenant', 'status', 'triggered_at'], name='aa_status_time_idx'),
            models.Index(fields=['tenant', 'severity', 'status'], name='aa_severity_status_idx'),
            models.Index(fields=['tenant', 'triggered_for_site', 'status'], name='aa_site_status_idx'),
            models.Index(fields=['tenant', 'triggered_for_worker', 'status'], name='aa_worker_status_idx'),
            models.Index(fields=['tenant', 'alert_rule', 'triggered_at'], name='aa_rule_time_idx'),
            models.Index(fields=['tenant', 'escalated', 'status'], name='aa_escalated_idx'),
        ]
        ordering = ['-triggered_at']

    def __str__(self):
        return f"{self.alert_rule.rule_name} - {self.get_status_display()} ({self.triggered_at.strftime('%Y-%m-%d %H:%M')})"

    def acknowledge(self, acknowledger, notes=''):
        """Acknowledge the alert"""
        if self.status not in [self.AlertStatus.ACTIVE, self.AlertStatus.ESCALATED]:
            raise ValidationError(f"Cannot acknowledge alert with status {self.status}")

        self.status = self.AlertStatus.ACKNOWLEDGED
        self.acknowledged_by = acknowledger
        self.acknowledged_at = timezone.now()
        self.acknowledgement_notes = notes

        # Calculate time to acknowledge
        if self.triggered_at:
            delta = self.acknowledged_at - self.triggered_at
            self.time_to_acknowledge_minutes = int(delta.total_seconds() / 60)

        self.save()
        logger.info(f"Alert {self.id} acknowledged by {acknowledger.id}")

    def resolve(self, resolver, notes=''):
        """Resolve the alert"""
        if self.status in [self.AlertStatus.RESOLVED, self.AlertStatus.AUTO_RESOLVED, self.AlertStatus.CANCELLED]:
            raise ValidationError(f"Alert already {self.status}")

        self.status = self.AlertStatus.RESOLVED
        self.resolved_by = resolver
        self.resolved_at = timezone.now()
        self.resolution_notes = notes

        # Calculate time to resolve
        if self.triggered_at:
            delta = self.resolved_at - self.triggered_at
            self.time_to_resolve_minutes = int(delta.total_seconds() / 60)

        self.save()
        logger.info(f"Alert {self.id} resolved by {resolver.id}")

    def escalate(self, escalate_to_users):
        """Escalate the alert to higher-level supervisors"""
        self.escalated = True
        self.escalated_at = timezone.now()
        self.status = self.AlertStatus.ESCALATED
        self.save()

        # Add escalation recipients
        self.escalated_to.set(escalate_to_users)

        logger.warning(f"Alert {self.id} escalated to {len(escalate_to_users)} users")

    def auto_resolve(self, reason=''):
        """Auto-resolve alert (condition no longer met)"""
        self.status = self.AlertStatus.AUTO_RESOLVED
        self.resolved_at = timezone.now()
        self.resolution_notes = f"Auto-resolved: {reason}"

        if self.triggered_at:
            delta = self.resolved_at - self.triggered_at
            self.time_to_resolve_minutes = int(delta.total_seconds() / 60)

        self.save()
        logger.info(f"Alert {self.id} auto-resolved: {reason}")

    def should_escalate(self):
        """Check if alert should be escalated"""
        if not self.alert_rule.escalation_enabled:
            return False

        if self.status != self.AlertStatus.ACTIVE:
            return False

        if self.escalated:
            return False

        # Check if enough time has passed
        if self.triggered_at:
            elapsed = timezone.now() - self.triggered_at
            elapsed_minutes = elapsed.total_seconds() / 60
            return elapsed_minutes >= self.alert_rule.escalation_delay_minutes

        return False


class AlertEscalation(BaseModel, TenantAwareModel):
    """
    Tracks alert escalations for SLA monitoring.

    Records when alerts are escalated and to whom.
    """

    alert = models.ForeignKey(
        AttendanceAlert,
        on_delete=models.CASCADE,
        related_name='escalations',
        help_text=_("Alert that was escalated")
    )

    escalated_from = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalations_from',
        help_text=_("Original recipient who didn't respond")
    )

    escalated_to = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='escalations_to',
        help_text=_("Person escalated to")
    )

    escalated_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_("When escalation occurred")
    )

    escalation_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_("Escalation level (1 = first escalation, 2 = second, etc.)")
    )

    reason = models.TextField(
        blank=True,
        help_text=_("Reason for escalation")
    )

    acknowledged = models.BooleanField(
        default=False,
        help_text=_("Whether escalated recipient acknowledged")
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When escalation was acknowledged")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_alert_escalation'
        verbose_name = _('Alert Escalation')
        verbose_name_plural = _('Alert Escalations')
        indexes = [
            models.Index(fields=['tenant', 'alert', 'escalated_at'], name='ae_alert_time_idx'),
            models.Index(fields=['tenant', 'escalated_to', 'acknowledged'], name='ae_recipient_ack_idx'),
        ]
        ordering = ['-escalated_at']

    def __str__(self):
        escalated_to_name = (self.escalated_to.get_full_name()
                            if hasattr(self.escalated_to, 'get_full_name')
                            else str(self.escalated_to))
        return f"Alert {self.alert.id} escalated to {escalated_to_name} (Level {self.escalation_level})"
