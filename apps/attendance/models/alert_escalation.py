"""
Alert Escalation Model (Phase 5.5)

Model for tracking alert escalations for SLA monitoring.

Author: Claude Code
Created: 2025-11-05
Phase: 5.5 - Alert Escalation
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel, TenantAwareModel

import logging

logger = logging.getLogger(__name__)


class AlertEscalation(BaseModel, TenantAwareModel):
    """
    Tracks alert escalations for SLA monitoring.

    Records when alerts are escalated and to whom.
    """

    alert = models.ForeignKey(
        'attendance.AttendanceAlert',
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
