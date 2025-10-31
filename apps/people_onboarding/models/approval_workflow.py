"""
ApprovalWorkflow Model

Multi-stakeholder approval workflow for onboarding requests.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.core.models import EnhancedTenantModel


class ApprovalDecision(models.TextChoices):
    """Approval decision choices"""
    PENDING = 'PENDING', _('Pending')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')
    ESCALATED = 'ESCALATED', _('Escalated')


class ApprovalWorkflow(EnhancedTenantModel):
    """
    Multi-level approval workflow for onboarding requests.

    Supports risk-based routing:
    - Low Risk: HR approval only
    - Medium Risk: HR → Manager
    - High Risk: HR → Security → IT → Manager
    - Critical Risk: Multi-level + background check
    """

    class ApprovalLevel(models.TextChoices):
        """Approval levels in the workflow"""
        HR = 'HR', _('HR Approval')
        MANAGER = 'MANAGER', _('Manager Approval')
        SECURITY = 'SECURITY', _('Security Approval')
        IT = 'IT', _('IT Approval')
        FINANCE = 'FINANCE', _('Finance Approval')
        EXECUTIVE = 'EXECUTIVE', _('Executive Approval')

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='approval_workflows'
    )

    # Approval details
    approval_level = models.CharField(
        _('Approval Level'),
        max_length=20,
        choices=ApprovalLevel.choices
    )

    sequence_number = models.PositiveSmallIntegerField(
        _('Sequence Number'),
        help_text=_('Order in the approval chain (1, 2, 3...)')
    )

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='onboarding_approvals',
        help_text=_('Person responsible for this approval')
    )

    # Decision
    decision = models.CharField(
        _('Decision'),
        max_length=20,
        choices=ApprovalDecision.choices,
        default=ApprovalDecision.PENDING
    )

    decision_date = models.DateTimeField(_('Decision Date'), null=True, blank=True)
    decision_notes = models.TextField(_('Decision Notes'), blank=True)

    # Escalation
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalated_onboarding_approvals',
        help_text=_('Person to whom approval was escalated')
    )

    escalation_reason = models.TextField(_('Escalation Reason'), blank=True)

    # Audit trail
    request_sent_at = models.DateTimeField(_('Request Sent At'), auto_now_add=True)
    reminder_sent_count = models.PositiveSmallIntegerField(_('Reminder Count'), default=0)
    last_reminder_sent_at = models.DateTimeField(_('Last Reminder Sent'), null=True, blank=True)

    # Metadata
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    user_agent = models.TextField(_('User Agent'), blank=True)

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_approval_workflow'
        verbose_name = _('Approval Workflow')
        verbose_name_plural = _('Approval Workflows')
        ordering = ['onboarding_request', 'sequence_number']
        indexes = [
            models.Index(fields=['onboarding_request', 'sequence_number']),
            models.Index(fields=['approver', 'decision']),
            models.Index(fields=['decision', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['onboarding_request', 'sequence_number'],
                name='unique_onboarding_sequence'
            )
        ]

    def __str__(self):
        return f"{self.onboarding_request.request_number} - {self.get_approval_level_display()} ({self.get_decision_display()})"

    def approve(self, notes='', ip_address=None, user_agent=''):
        """Approve this workflow step"""
        self.decision = ApprovalDecision.APPROVED
        self.decision_date = timezone.now()
        self.decision_notes = notes
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.save()

    def reject(self, notes='', ip_address=None, user_agent=''):
        """Reject this workflow step"""
        self.decision = ApprovalDecision.REJECTED
        self.decision_date = timezone.now()
        self.decision_notes = notes
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.save()

    def escalate(self, escalated_to, reason='', ip_address=None, user_agent=''):
        """Escalate to another approver"""
        self.decision = ApprovalDecision.ESCALATED
        self.escalated_to = escalated_to
        self.escalation_reason = reason
        self.decision_date = timezone.now()
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.save()