"""
Approval Action Model (Phase 4.4)

Model for tracking approval action audit trail.

Author: Claude Code
Created: 2025-11-05
Phase: 4.4 - Approval Action
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.models import BaseModel, TenantAwareModel
from apps.attendance.models.approval_enums import ApprovalActionType

import logging

logger = logging.getLogger(__name__)


class ApprovalAction(BaseModel, TenantAwareModel):
    """
    Audit trail of approval actions.

    Tracks all actions taken on approval requests for complete audit trail.
    """

    approval_request = models.ForeignKey(
        'attendance.ApprovalRequest',
        on_delete=models.CASCADE,
        related_name='actions',
        help_text=_("Approval request this action belongs to")
    )

    action = models.CharField(
        max_length=20,
        choices=ApprovalActionType.choices,
        db_index=True,
        help_text=_("Type of action taken")
    )

    action_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_approval_actions',
        help_text=_("Person who took this action")
    )

    action_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_("When action was taken")
    )

    notes = models.TextField(
        blank=True,
        help_text=_("Notes about this action")
    )

    action_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Additional metadata about action")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_approval_action'
        verbose_name = _('Approval Action')
        verbose_name_plural = _('Approval Actions')
        indexes = [
            models.Index(fields=['tenant', 'approval_request', 'action_at'], name='aa_request_time_idx'),
            models.Index(fields=['tenant', 'action_by', 'action_at'], name='aa_actor_time_idx'),
        ]
        ordering = ['-action_at']

    def __str__(self):
        actor_name = (self.action_by.get_full_name()
                     if self.action_by and hasattr(self.action_by, 'get_full_name')
                     else 'System')
        return f"{self.get_action_display()} by {actor_name} on {self.action_at.strftime('%Y-%m-%d %H:%M')}"
