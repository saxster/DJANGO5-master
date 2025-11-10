"""
Alert Rule Model (Phase 5.2)

Model for configurable alert rules for attendance monitoring.

Author: Claude Code
Created: 2025-11-05
Phase: 5.2 - Alert Rule
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel, TenantAwareModel
from apps.attendance.models.alert_enums import AlertType, AlertSeverity

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
        choices=AlertSeverity.choices,
        default=AlertSeverity.MEDIUM,
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
        'client_onboarding.Bt',
        blank=True,
        related_name='alert_rules',
        help_text=_("Sites this rule applies to (empty = all sites)")
    )

    applies_to_shifts = models.ManyToManyField(
        'client_onboarding.Shift',
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
