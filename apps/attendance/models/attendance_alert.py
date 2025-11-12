"""
Attendance Alert Model (Phase 5.3)

Model for alert instances when rules trigger.

Author: Claude Code
Created: 2025-11-05
Phase: 5.3 - Attendance Alert
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.models import BaseModel, TenantAwareModel
from apps.attendance.models.alert_enums import AlertStatus, AlertSeverity
from apps.attendance.models.attendance_alert_actions import AttendanceAlertActions

import logging

logger = logging.getLogger(__name__)


class AttendanceAlert(AttendanceAlertActions, BaseModel, TenantAwareModel):
    """
    Alert instances when rules trigger.

    Tracks individual alert occurrences with:
    - When triggered
    - Who it's for
    - What triggered it
    - Who acknowledged it
    - Resolution details
    """

    # ========== Alert Identification ==========

    alert_rule = models.ForeignKey(
        'attendance.AlertRule',
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
        choices=AlertSeverity.choices,
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
        'client_onboarding.Bt',
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
