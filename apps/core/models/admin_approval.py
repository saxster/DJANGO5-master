"""
Approval Request System for Admin Panel
========================================
Allows users to request approval for sensitive actions.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
- Rule #11: Specific exception handling
- Rule #18: DateTimeField standards
"""

from datetime import timedelta
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel


class ApprovalRequest(BaseModel, TenantAwareModel):
    """
    Request approval for sensitive actions before execution.

    Features:
    - Plain-language action descriptions
    - Multi-approver support
    - Auto-expiration
    - Callback task execution after approval
    """

    class Status(models.TextChoices):
        WAITING = "WAITING", _("Waiting for Approval")
        APPROVED = "APPROVED", _("Approved")
        DENIED = "DENIED", _("Denied")
        EXPIRED = "EXPIRED", _("Expired")
        COMPLETED = "COMPLETED", _("Completed")

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_requests_made",
        verbose_name=_("Requested By"),
        help_text=_("Who is asking for approval")
    )

    action_description = models.TextField(
        _("What You Want to Do"),
        help_text=_("Plain English description of the action (e.g., 'Delete 50 old tickets')")
    )

    reason = models.TextField(
        _("Why You Need to Do This"),
        help_text=_("Business justification for this action")
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
        db_index=True
    )

    approver_group = models.ForeignKey(
        "peoples.Pgroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approval_requests",
        verbose_name=_("Approver Group"),
        help_text=_("Which group can approve this")
    )

    approved_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="approval_requests_approved",
        blank=True,
        verbose_name=_("Approved By"),
        help_text=_("People who approved this request")
    )

    denied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_denied",
        verbose_name=_("Denied By"),
        help_text=_("Person who denied this request")
    )

    denial_reason = models.TextField(
        _("Denial Reason"),
        blank=True,
        default="",
        help_text=_("Why this request was denied")
    )

    # What action to execute after approval
    target_model = models.CharField(
        _("Target Model"),
        max_length=100,
        help_text=_("Django model to act on (e.g., 'tickets.Ticket')")
    )

    target_ids = models.JSONField(
        _("Target IDs"),
        default=list,
        encoder=DjangoJSONEncoder,
        help_text=_("List of record IDs to act on")
    )

    callback_task_name = models.CharField(
        _("Callback Task"),
        max_length=200,
        help_text=_("Celery task to execute after approval")
    )

    expires_at = models.DateTimeField(
        _("Expires At"),
        help_text=_("Request auto-expires after this time")
    )

    requested_at = models.DateTimeField(
        _("Requested At"),
        auto_now_add=True
    )

    class Meta(BaseModel.Meta):
        db_table = "admin_approval_request"
        verbose_name = "Approval Request"
        verbose_name_plural = "Approval Requests"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["status"], name="approval_status_idx"),
            models.Index(fields=["requester", "status"], name="approval_req_status_idx"),
            models.Index(fields=["expires_at"], name="approval_expiry_idx"),
        ]

    def __str__(self):
        return f"{self.action_description[:50]} - {self.status}"

    def save(self, *args, **kwargs):
        # Set default expiration (24 hours from now)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)


class ApprovalAction(BaseModel):
    """
    Individual approval or denial decision.

    Features:
    - Track each approver's decision
    - Store comments/reasoning
    - Timestamp decisions
    """

    class Decision(models.TextChoices):
        APPROVE = "APPROVE", _("Approve")
        DENY = "DENY", _("Deny")

    request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        related_name="actions",
        verbose_name=_("Approval Request")
    )

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approval_actions",
        verbose_name=_("Approver")
    )

    decision = models.CharField(
        _("Decision"),
        max_length=10,
        choices=Decision.choices
    )

    comment = models.TextField(
        _("Comment"),
        blank=True,
        default="",
        help_text=_("Optional explanation for this decision")
    )

    decided_at = models.DateTimeField(
        _("Decided At"),
        auto_now_add=True
    )

    class Meta(BaseModel.Meta):
        db_table = "admin_approval_action"
        verbose_name = "Approval Action"
        verbose_name_plural = "Approval Actions"
        ordering = ["-decided_at"]
        indexes = [
            models.Index(fields=["request", "decision"], name="approval_act_req_dec_idx"),
        ]

    def __str__(self):
        return f"{self.approver.username} - {self.decision}"


__all__ = ["ApprovalRequest", "ApprovalAction"]
