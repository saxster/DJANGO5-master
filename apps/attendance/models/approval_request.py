"""
Approval Request Model (Phase 4.2)

Model for managing approval requests for attendance exceptions.

Author: Claude Code
Created: 2025-11-05
Phase: 4.2 - Approval Request
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

from apps.core.models import BaseModel, TenantAwareModel
from apps.attendance.models.approval_enums import (
    RequestType, RequestStatus, RequestPriority
)
from apps.attendance.models.approval_request_actions import ApprovalRequestActions

import logging

logger = logging.getLogger(__name__)


class ApprovalRequest(ApprovalRequestActions, BaseModel, TenantAwareModel):
    """
    Approval requests for attendance exceptions.

    Handles:
    - Validation override requests (wrong site/shift/post)
    - Emergency assignment requests
    - Ad-hoc shift change requests
    - Late check-in approvals
    - Rest period violation approvals

    Workflow:
    PENDING → Supervisor reviews
         ├─ APPROVED → Worker can proceed
         ├─ REJECTED → Worker cannot proceed
         ├─ EXPIRED → Auto-rejected after timeout
         └─ CANCELLED → Requester cancelled

    Auto-Approval:
    - Can be auto-approved based on configurable rules
    - Example: Same site, qualified worker, within 2 hours
    """

    # ========== Core Request Info ==========

    request_type = models.CharField(
        max_length=30,
        choices=RequestType.choices,
        db_index=True,
        help_text=_("Type of approval request")
    )

    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        db_index=True,
        help_text=_("Current status of request")
    )

    priority = models.CharField(
        max_length=10,
        choices=RequestPriority.choices,
        default=RequestPriority.NORMAL,
        db_index=True,
        help_text=_("Request priority")
    )

    # ========== Requester Info ==========

    requested_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='approval_requests_submitted',
        db_index=True,
        help_text=_("Worker or supervisor who submitted request")
    )

    requested_for = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='approval_requests_for',
        null=True,
        blank=True,
        help_text=_("Worker who will benefit from approval (if different from requester)")
    )

    # ========== Request Details ==========

    title = models.CharField(
        max_length=200,
        help_text=_("Short description of request")
    )

    description = models.TextField(
        help_text=_("Detailed description and justification")
    )

    reason_code = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Machine-readable reason code (e.g., 'EMERGENCY', 'COVERAGE_GAP')")
    )

    # ========== Related Objects ==========

    related_site = models.ForeignKey(
        'onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_requests',
        help_text=_("Site related to this request")
    )

    related_post = models.ForeignKey(
        'attendance.Post',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_requests',
        help_text=_("Post related to this request")
    )

    related_shift = models.ForeignKey(
        'onboarding.Shift',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_requests',
        help_text=_("Shift related to this request")
    )

    related_assignment = models.ForeignKey(
        'attendance.PostAssignment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_requests',
        help_text=_("PostAssignment related to this request")
    )

    related_ticket = models.ForeignKey(
        'y_helpdesk.Ticket',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_requests',
        help_text=_("Helpdesk ticket that triggered this request")
    )

    # ========== Validation Override Data ==========

    validation_failure_reason = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Original validation failure code (if override request)")
    )

    validation_failure_details = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Details from ValidationResult (if override request)")
    )

    # ========== Approval/Rejection ==========

    reviewed_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_requests_reviewed',
        help_text=_("Supervisor who reviewed this request")
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=_("When request was reviewed")
    )

    approval_notes = models.TextField(
        blank=True,
        help_text=_("Notes from reviewer")
    )

    rejection_reason = models.TextField(
        blank=True,
        help_text=_("Reason for rejection")
    )

    # ========== Auto-Approval ==========

    auto_approved = models.BooleanField(
        default=False,
        help_text=_("Whether this was automatically approved")
    )

    auto_approval_rule = models.ForeignKey(
        'attendance.AutoApprovalRule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_requests',
        help_text=_("Auto-approval rule that was applied")
    )

    # ========== Timing & Expiration ==========

    requested_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_("When request was submitted")
    )

    expires_at = models.DateTimeField(
        db_index=True,
        help_text=_("When request expires if not reviewed")
    )

    response_time_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Minutes from request to response")
    )

    # ========== Notification Tracking ==========

    supervisor_notified = models.BooleanField(
        default=False,
        help_text=_("Whether supervisor was notified")
    )

    supervisor_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When supervisor was notified")
    )

    requester_notified_of_decision = models.BooleanField(
        default=False,
        help_text=_("Whether requester was notified of decision")
    )

    # ========== Metadata ==========

    request_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Extensible metadata (GPS, device, validation details, etc.)")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_approval_request'
        verbose_name = _('Approval Request')
        verbose_name_plural = _('Approval Requests')
        indexes = [
            models.Index(fields=['tenant', 'status', 'requested_at'], name='ar_status_time_idx'),
            models.Index(fields=['tenant', 'requested_by', 'status'], name='ar_requester_status_idx'),
            models.Index(fields=['tenant', 'reviewed_by', 'reviewed_at'], name='ar_reviewer_time_idx'),
            models.Index(fields=['tenant', 'expires_at', 'status'], name='ar_expiration_idx'),
            models.Index(fields=['tenant', 'request_type', 'status'], name='ar_type_status_idx'),
        ]
        ordering = ['-requested_at']

    def __str__(self):
        requester_name = (self.requested_by.get_full_name()
                         if hasattr(self.requested_by, 'get_full_name')
                         else str(self.requested_by))
        return f"{self.get_request_type_display()} - {requester_name} - {self.status}"

    def save(self, *args, **kwargs):
        """Auto-populate expiration time if not set"""
        if not self.expires_at:
            # Default: expires in 24 hours for normal, 2 hours for urgent
            if self.priority == RequestPriority.URGENT:
                self.expires_at = timezone.now() + timezone.timedelta(hours=2)
            else:
                self.expires_at = timezone.now() + timezone.timedelta(hours=24)

        super().save(*args, **kwargs)

    def is_expired(self):
        """Check if request has expired"""
        return timezone.now() > self.expires_at and self.status == RequestStatus.PENDING

    def check_and_expire(self):
        """Check and mark as expired if past expiration time"""
        if self.is_expired():
            self.status = RequestStatus.EXPIRED
            self.save(update_fields=['status'])
            logger.info(f"Approval request {self.id} expired")
            return True
        return False
