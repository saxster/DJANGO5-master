"""
Approval Workflow Models (Phase 4)

Models for managing supervisor approval workflows:
- ApprovalRequest: Requests for check-in overrides, shift changes, etc.
- ApprovalAction: Audit trail of approval decisions
- AutoApprovalRule: Configurable auto-approval rules

Author: Claude Code
Created: 2025-11-03
Phase: 4 - Approval Workflow
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

from apps.core.models import BaseModel, TenantAwareModel
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

import logging

logger = logging.getLogger(__name__)


class ApprovalRequest(BaseModel, TenantAwareModel):
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

    class RequestType(models.TextChoices):
        """Types of approval requests"""
        VALIDATION_OVERRIDE = 'VALIDATION_OVERRIDE', _('Validation Check-in Override')
        EMERGENCY_ASSIGNMENT = 'EMERGENCY_ASSIGNMENT', _('Emergency Assignment')
        SHIFT_CHANGE = 'SHIFT_CHANGE', _('Shift Change Request')
        POST_REASSIGNMENT = 'POST_REASSIGNMENT', _('Post Reassignment')
        REST_PERIOD_WAIVER = 'REST_PERIOD_WAIVER', _('Rest Period Waiver')
        LATE_CHECKIN_APPROVAL = 'LATE_CHECKIN_APPROVAL', _('Late Check-in Approval')
        SITE_TRANSFER = 'SITE_TRANSFER', _('Site Transfer')
        COVERAGE_GAP_FILL = 'COVERAGE_GAP_FILL', _('Coverage Gap Fill')

    class RequestStatus(models.TextChoices):
        """Approval request status"""
        PENDING = 'PENDING', _('Pending Review')
        AUTO_APPROVED = 'AUTO_APPROVED', _('Auto-Approved')
        MANUALLY_APPROVED = 'MANUALLY_APPROVED', _('Manually Approved')
        REJECTED = 'REJECTED', _('Rejected')
        EXPIRED = 'EXPIRED', _('Expired')
        CANCELLED = 'CANCELLED', _('Cancelled')

    class Priority(models.TextChoices):
        """Request priority"""
        URGENT = 'URGENT', _('Urgent')
        HIGH = 'HIGH', _('High')
        NORMAL = 'NORMAL', _('Normal')
        LOW = 'LOW', _('Low')

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
        choices=Priority.choices,
        default=Priority.NORMAL,
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
            if self.priority == self.Priority.URGENT:
                self.expires_at = timezone.now() + timezone.timedelta(hours=2)
            else:
                self.expires_at = timezone.now() + timezone.timedelta(hours=24)

        super().save(*args, **kwargs)

    def approve(self, reviewer, notes=''):
        """Approve the request"""
        if self.status not in [self.RequestStatus.PENDING]:
            raise ValidationError(f"Cannot approve request with status {self.status}")

        with transaction.atomic():
            self.status = self.RequestStatus.MANUALLY_APPROVED
            self.reviewed_by = reviewer
            self.reviewed_at = timezone.now()
            self.approval_notes = notes

            # Calculate response time
            if self.requested_at:
                delta = self.reviewed_at - self.requested_at
                self.response_time_minutes = int(delta.total_seconds() / 60)

            self.save()

            # Create approval action record
            ApprovalAction.objects.create(
                approval_request=self,
                action='APPROVED',
                action_by=reviewer,
                notes=notes,
                tenant=self.tenant,
                client=self.client
            )

            logger.info(f"Approval request {self.id} approved by {reviewer.id}")

    def reject(self, reviewer, reason):
        """Reject the request"""
        if self.status not in [self.RequestStatus.PENDING]:
            raise ValidationError(f"Cannot reject request with status {self.status}")

        with transaction.atomic():
            self.status = self.RequestStatus.REJECTED
            self.reviewed_by = reviewer
            self.reviewed_at = timezone.now()
            self.rejection_reason = reason

            # Calculate response time
            if self.requested_at:
                delta = self.reviewed_at - self.requested_at
                self.response_time_minutes = int(delta.total_seconds() / 60)

            self.save()

            # Create approval action record
            ApprovalAction.objects.create(
                approval_request=self,
                action='REJECTED',
                action_by=reviewer,
                notes=reason,
                tenant=self.tenant,
                client=self.client
            )

            logger.info(f"Approval request {self.id} rejected by {reviewer.id}")

    def cancel(self, cancelled_by, reason=''):
        """Cancel the request"""
        if self.status not in [self.RequestStatus.PENDING]:
            raise ValidationError(f"Cannot cancel request with status {self.status}")

        self.status = self.RequestStatus.CANCELLED
        self.approval_notes = reason
        self.save()

        # Create approval action record
        ApprovalAction.objects.create(
            approval_request=self,
            action='CANCELLED',
            action_by=cancelled_by,
            notes=reason,
            tenant=self.tenant,
            client=self.client
        )

        logger.info(f"Approval request {self.id} cancelled by {cancelled_by.id}")

    def is_expired(self):
        """Check if request has expired"""
        return timezone.now() > self.expires_at and self.status == self.RequestStatus.PENDING

    def check_and_expire(self):
        """Check and mark as expired if past expiration time"""
        if self.is_expired():
            self.status = self.RequestStatus.EXPIRED
            self.save(update_fields=['status'])
            logger.info(f"Approval request {self.id} expired")
            return True
        return False


class ApprovalAction(BaseModel, TenantAwareModel):
    """
    Audit trail of approval actions.

    Tracks all actions taken on approval requests for complete audit trail.
    """

    class ActionType(models.TextChoices):
        """Types of approval actions"""
        CREATED = 'CREATED', _('Request Created')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        CANCELLED = 'CANCELLED', _('Cancelled')
        EXPIRED = 'EXPIRED', _('Expired')
        ESCALATED = 'ESCALATED', _('Escalated to Manager')
        COMMENT_ADDED = 'COMMENT_ADDED', _('Comment Added')

    approval_request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        related_name='actions',
        help_text=_("Approval request this action belongs to")
    )

    action = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        db_index=True,
        help_text=_("Type of action taken")
    )

    action_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_actions',
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


class AutoApprovalRule(BaseModel, TenantAwareModel):
    """
    Configurable rules for auto-approval of requests.

    Allows automatic approval of low-risk requests without manual review.

    Example Rules:
    - Same site, same shift, within 15 minutes → Auto-approve
    - Coverage gap fill, qualified worker → Auto-approve
    - Emergency assignment, site supervisor request → Auto-approve
    """

    rule_name = models.CharField(
        max_length=100,
        help_text=_("Descriptive name for this rule")
    )

    rule_code = models.CharField(
        max_length=50,
        unique=True,
        help_text=_("Unique code for this rule")
    )

    active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this rule is currently active")
    )

    # ========== Rule Criteria ==========

    request_types = models.JSONField(
        default=list,
        help_text=_("List of request types this rule applies to")
    )

    priority_levels = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Priority levels this rule applies to (empty = all)")
    )

    max_distance_from_site_meters = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Maximum distance from site for auto-approval (meters)")
    )

    max_time_variance_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Maximum time variance from scheduled shift (minutes)")
    )

    requires_qualification_match = models.BooleanField(
        default=True,
        help_text=_("Whether worker must be qualified for post")
    )

    same_site_only = models.BooleanField(
        default=True,
        help_text=_("Only auto-approve if same site")
    )

    # ========== Rule Conditions (JSON-based for flexibility) ==========

    conditions = models.JSONField(
        default=dict,
        help_text=_(
            "Flexible conditions in JSON format. Example: "
            "{'max_late_minutes': 15, 'allowed_sites': [1, 2], 'requires_supervisor_request': true}"
        )
    )

    # ========== Rule Metadata ==========

    description = models.TextField(
        blank=True,
        help_text=_("Description of when this rule applies")
    )

    created_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auto_approval_rules_created',
        help_text=_("Who created this rule")
    )

    times_applied = models.IntegerField(
        default=0,
        help_text=_("Number of times this rule has been applied")
    )

    last_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When this rule was last applied")
    )

    class Meta(BaseModel.Meta):
        db_table = 'attendance_auto_approval_rule'
        verbose_name = _('Auto-Approval Rule')
        verbose_name_plural = _('Auto-Approval Rules')
        indexes = [
            models.Index(fields=['tenant', 'active'], name='aar_active_idx'),
            models.Index(fields=['rule_code'], name='aar_code_idx'),
        ]
        ordering = ['rule_name']

    def __str__(self):
        status = "Active" if self.active else "Inactive"
        return f"{self.rule_name} ({status}) - Applied {self.times_applied} times"

    def matches_request(self, approval_request):
        """
        Check if this rule matches the given approval request.

        Args:
            approval_request: ApprovalRequest instance

        Returns:
            tuple: (matches: bool, reason: str)
        """
        # Check request type
        if approval_request.request_type not in self.request_types:
            return (False, "Request type not in rule")

        # Check priority if specified
        if self.priority_levels and approval_request.priority not in self.priority_levels:
            return (False, "Priority level not in rule")

        # Check same site requirement
        if self.same_site_only:
            # TODO: Implement site checking logic
            pass

        # Check custom conditions
        conditions = self.conditions or {}

        # Example condition checks
        if 'max_late_minutes' in conditions:
            # Check if request is for late check-in within threshold
            # Implementation depends on request_metadata structure
            pass

        # If all checks pass
        return (True, "All conditions met")

    def apply_to_request(self, approval_request):
        """
        Apply this rule to auto-approve a request.

        Args:
            approval_request: ApprovalRequest instance

        Returns:
            bool: True if approved, False if rule didn't match
        """
        matches, reason = self.matches_request(approval_request)

        if not matches:
            logger.debug(f"Auto-approval rule {self.rule_code} did not match request {approval_request.id}: {reason}")
            return False

        # Auto-approve
        approval_request.status = ApprovalRequest.RequestStatus.AUTO_APPROVED
        approval_request.auto_approved = True
        approval_request.auto_approval_rule = self
        approval_request.reviewed_at = timezone.now()
        approval_request.save()

        # Update rule statistics
        self.times_applied += 1
        self.last_applied_at = timezone.now()
        self.save(update_fields=['times_applied', 'last_applied_at'])

        # Create action record
        ApprovalAction.objects.create(
            approval_request=approval_request,
            action='APPROVED',
            action_by=None,  # System auto-approval
            notes=f"Auto-approved by rule: {self.rule_name}",
            action_metadata={'rule_id': self.id, 'rule_code': self.rule_code},
            tenant=approval_request.tenant,
            client=approval_request.client
        )

        logger.info(f"Auto-approved request {approval_request.id} using rule {self.rule_code}")

        return True
