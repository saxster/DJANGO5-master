"""
AI Changeset and Approval Models for Conversational Onboarding.

Tracks AI-generated changesets with comprehensive rollback capability
and implements two-person approval workflows for high-risk changes.

Following .claude/rules.md:
- Rule #6: Model classes < 150 lines
- Rule #9: Specific exception handling
- Rule #17: Transaction management for changesets
"""

import uuid
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel


class AIChangeSet(BaseModel, TenantAwareModel):
    """
    Tracks a set of AI-generated changes with rollback capability.
    Implements two-person rule for high-risk changes.
    """

    class StatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPLIED = "applied", _("Applied")
        ROLLED_BACK = "rolled_back", _("Rolled Back")
        FAILED = "failed", _("Failed")
        PARTIALLY_APPLIED = "partially_applied", _("Partially Applied")

    changeset_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_session = models.ForeignKey(
        "ConversationSession",
        on_delete=models.CASCADE,
        related_name="changesets",
        verbose_name=_("Conversation Session")
    )
    status = models.CharField(
        _("Status"),
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    applied_at = models.DateTimeField(_("Applied At"), null=True, blank=True)
    rolled_back_at = models.DateTimeField(_("Rolled Back At"), null=True, blank=True)
    description = models.TextField(
        _("Description"),
        help_text="Human-readable description of changes"
    )
    total_changes = models.PositiveIntegerField(_("Total Changes"), default=0)
    successful_changes = models.PositiveIntegerField(_("Successful Changes"), default=0)
    failed_changes = models.PositiveIntegerField(_("Failed Changes"), default=0)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_changesets",
        verbose_name=_("Approved By")
    )
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rolled_back_changesets",
        verbose_name=_("Rolled Back By"),
        null=True,
        blank=True
    )
    rollback_reason = models.TextField(
        _("Rollback Reason"),
        blank=True,
        null=True,
        help_text="Reason for rolling back changes"
    )
    metadata = models.JSONField(
        _("Additional Metadata"),
        default=dict,
        blank=True,
        help_text="Additional contextual information"
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_ai_changeset"
        verbose_name = "AI Change Set"
        verbose_name_plural = "AI Change Sets"
        indexes = [
            models.Index(fields=['status', 'cdtz'], name='changeset_status_created_idx'),
            models.Index(fields=['conversation_session', 'status'], name='changeset_session_status_idx'),
        ]

    def __str__(self):
        return f"Changeset {self.changeset_id} - {self.status}"

    def requires_two_person_approval(self) -> bool:
        """
        Determine if changeset requires two-person approval based on risk score.
        High-risk threshold: score > 0.7 or more than 10 changes
        """
        risk_score = self.calculate_risk_score()
        return risk_score > 0.7 or self.total_changes > 10

    def calculate_risk_score(self) -> float:
        """
        Calculate risk score (0.0 to 1.0) based on changeset characteristics.
        Higher scores indicate higher risk requiring additional approval.
        """
        risk_factors = []

        if self.total_changes > 20:
            risk_factors.append(0.4)
        elif self.total_changes > 10:
            risk_factors.append(0.3)
        elif self.total_changes > 5:
            risk_factors.append(0.2)

        delete_count = self.change_records.filter(action='delete').count()
        if delete_count > 0:
            risk_factors.append(min(delete_count * 0.15, 0.3))

        has_dependencies = self.change_records.filter(has_dependencies=True).exists()
        if has_dependencies:
            risk_factors.append(0.2)

        return min(sum(risk_factors), 1.0)

    def create_approval_request(self, approver, approval_level: str, request_meta: dict):
        """Create an approval request for this changeset."""
        return ChangeSetApproval.objects.create(
            changeset=self,
            approver=approver,
            approval_level=approval_level,
            status=ChangeSetApproval.StatusChoices.PENDING,
            request_metadata=request_meta
        )

    def auto_assign_secondary_approver(self, primary_approver, request_meta: dict):
        """Auto-assign a secondary approver from eligible users."""
        from apps.peoples.models import People

        eligible_approvers = People.objects.filter(
            isadmin=True,
            enable=True,
            client=self.conversation_session.client
        ).exclude(
            id=primary_approver.id
        )

        if eligible_approvers.exists():
            secondary_approver = eligible_approvers.first()
            return self.create_approval_request(
                approver=secondary_approver,
                approval_level='secondary',
                request_meta=request_meta
            )
        return None

    def get_approval_status(self) -> dict:
        """Get current approval status for this changeset."""
        approvals = self.approvals.all()
        return {
            'total_approvals': approvals.count(),
            'approved_count': approvals.filter(status=ChangeSetApproval.StatusChoices.APPROVED).count(),
            'pending_count': approvals.filter(status=ChangeSetApproval.StatusChoices.PENDING).count(),
            'rejected_count': approvals.filter(status=ChangeSetApproval.StatusChoices.REJECTED).count(),
            'requires_two_person': self.requires_two_person_approval()
        }

    def can_be_applied(self) -> bool:
        """Check if changeset has all required approvals and can be applied."""
        if not self.requires_two_person_approval():
            return True

        approval_status = self.get_approval_status()
        required_approvals = 2 if self.requires_two_person_approval() else 1

        return (
            approval_status['approved_count'] >= required_approvals and
            approval_status['rejected_count'] == 0 and
            self.status == self.StatusChoices.PENDING
        )

    def can_rollback(self) -> bool:
        """Check if changeset can be rolled back."""
        return (
            self.status in [self.StatusChoices.APPLIED, self.StatusChoices.PARTIALLY_APPLIED] and
            self.rolled_back_at is None
        )

    def get_rollback_complexity(self) -> str:
        """Estimate rollback complexity: low, medium, high."""
        if self.failed_changes > 0:
            return "high"
        elif self.change_records.filter(has_dependencies=True).exists():
            return "medium"
        elif self.successful_changes <= 5:
            return "low"
        else:
            return "medium"


class AIChangeRecord(BaseModel):
    """
    Individual change record within a changeset.
    Tracks before/after state for granular rollback.
    """

    class ActionChoices(models.TextChoices):
        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")
        DELETE = "delete", _("Delete")

    class StatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        ROLLED_BACK = "rolled_back", _("Rolled Back")

    record_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    changeset = models.ForeignKey(
        AIChangeSet,
        on_delete=models.CASCADE,
        related_name="change_records",
        verbose_name=_("Change Set")
    )
    sequence_order = models.PositiveIntegerField(_("Sequence Order"))
    model_name = models.CharField(_("Model Name"), max_length=100)
    app_label = models.CharField(_("App Label"), max_length=100)
    object_id = models.CharField(_("Object ID"), max_length=100)
    action = models.CharField(
        _("Action"),
        max_length=20,
        choices=ActionChoices.choices
    )
    before_state = models.JSONField(
        _("Before State"),
        null=True,
        blank=True,
        help_text="Object state before change (for UPDATE/DELETE)"
    )
    after_state = models.JSONField(
        _("After State"),
        null=True,
        blank=True,
        help_text="Object state after change (for CREATE/UPDATE)"
    )
    field_changes = models.JSONField(
        _("Field Changes"),
        default=dict,
        help_text="Specific field-level changes"
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    error_message = models.TextField(_("Error Message"), blank=True, null=True)
    has_dependencies = models.BooleanField(
        _("Has Dependencies"),
        default=False,
        help_text="Whether this change affects related objects"
    )
    dependency_info = models.JSONField(
        _("Dependency Information"),
        default=dict,
        blank=True
    )
    rollback_attempted_at = models.DateTimeField(
        _("Rollback Attempted At"),
        null=True,
        blank=True
    )
    rollback_success = models.BooleanField(
        _("Rollback Success"),
        null=True,
        blank=True
    )
    rollback_error = models.TextField(_("Rollback Error"), blank=True, null=True)

    class Meta(BaseModel.Meta):
        db_table = "onboarding_ai_change_record"
        verbose_name = "AI Change Record"
        verbose_name_plural = "AI Change Records"
        ordering = ['changeset', 'sequence_order']
        constraints = [
            models.UniqueConstraint(
                fields=['changeset', 'sequence_order'],
                name='unique_changeset_sequence'
            )
        ]
        indexes = [
            models.Index(fields=['changeset', 'status'], name='change_record_status_idx'),
            models.Index(fields=['model_name', 'object_id'], name='change_record_object_idx'),
        ]

    def __str__(self):
        return f"{self.action} {self.model_name}:{self.object_id}"


class ChangeSetApproval(BaseModel):
    """
    Approval tracking for changesets implementing two-person rule.
    Records each approval decision with full audit trail.
    """

    class StatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        ESCALATED = "escalated", _("Escalated")

    approval_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    changeset = models.ForeignKey(
        AIChangeSet,
        on_delete=models.CASCADE,
        related_name="approvals",
        verbose_name=_("Change Set")
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="changeset_approvals",
        verbose_name=_("Approver")
    )
    approval_level = models.CharField(
        _("Approval Level"),
        max_length=20,
        choices=[
            ('primary', _('Primary')),
            ('secondary', _('Secondary')),
            ('escalated', _('Escalated'))
        ],
        default='primary'
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    decision_at = models.DateTimeField(_("Decision At"), null=True, blank=True)
    reason = models.TextField(_("Reason"), blank=True)
    conditions = models.TextField(_("Conditions"), blank=True)
    modifications = models.JSONField(_("Modifications"), default=dict, blank=True)
    request_metadata = models.JSONField(
        _("Request Metadata"),
        default=dict,
        blank=True,
        help_text="Request context (IP, user agent, correlation ID)"
    )
    escalation_details = models.JSONField(
        _("Escalation Details"),
        default=dict,
        blank=True,
        help_text="Details if escalated (ticket info, etc.)"
    )

    class Meta(BaseModel.Meta):
        db_table = "onboarding_changeset_approval"
        verbose_name = "Change Set Approval"
        verbose_name_plural = "Change Set Approvals"
        indexes = [
            models.Index(fields=['changeset', 'status'], name='approval_changeset_status_idx'),
            models.Index(fields=['approver', 'status'], name='approval_approver_status_idx'),
        ]

    def __str__(self):
        return f"Approval {self.approval_id} - {self.approval_level} - {self.status}"

    def is_pending(self) -> bool:
        """Check if approval is still pending."""
        return self.status == self.StatusChoices.PENDING

    def approve(self, reason: str = "", conditions: str = "", modifications: dict = None):
        """Approve this changeset with optional conditions/modifications."""
        if not self.is_pending():
            raise ValidationError("Approval already decided")

        with transaction.atomic():
            self.status = self.StatusChoices.APPROVED
            self.decision_at = timezone.now()
            self.reason = reason
            self.conditions = conditions
            self.modifications = modifications or {}
            self.save()

    def reject(self, reason: str):
        """Reject this changeset approval."""
        if not self.is_pending():
            raise ValidationError("Approval already decided")

        with transaction.atomic():
            self.status = self.StatusChoices.REJECTED
            self.decision_at = timezone.now()
            self.reason = reason
            self.save()

    def escalate(self, reason: str):
        """Escalate this approval to senior approvers."""
        if not self.is_pending():
            raise ValidationError("Approval already decided")

        with transaction.atomic():
            self.status = self.StatusChoices.ESCALATED
            self.decision_at = timezone.now()
            self.reason = reason
            self.save()