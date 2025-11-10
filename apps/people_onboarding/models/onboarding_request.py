"""
OnboardingRequest Model

Core model for tracking people onboarding requests through the entire lifecycle.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.core.models import EnhancedTenantModel


class OnboardingRequest(EnhancedTenantModel):
    """
    Core onboarding request model tracking the complete onboarding lifecycle.

    Supports multiple person types:
    - Employees (full-time, part-time)
    - Contractors (fixed-term)
    - Consultants (project-based)
    - Vendor personnel (vendor employee access)
    - Temporary workers (seasonal, event-based)
    """

    class PersonType(models.TextChoices):
        """Types of people being onboarded"""
        EMPLOYEE_FULLTIME = 'EMPLOYEE_FULLTIME', _('Full-Time Employee')
        EMPLOYEE_PARTTIME = 'EMPLOYEE_PARTTIME', _('Part-Time Employee')
        CONTRACTOR = 'CONTRACTOR', _('Contractor')
        CONSULTANT = 'CONSULTANT', _('Consultant')
        VENDOR_PERSONNEL = 'VENDOR_PERSONNEL', _('Vendor Personnel')
        TEMPORARY_WORKER = 'TEMPORARY_WORKER', _('Temporary Worker')

    class WorkflowState(models.TextChoices):
        """Onboarding workflow states"""
        DRAFT = 'DRAFT', _('Draft')
        SUBMITTED = 'SUBMITTED', _('Submitted')
        DOCUMENT_VERIFICATION = 'DOCUMENT_VERIFICATION', _('Document Verification')
        BACKGROUND_CHECK = 'BACKGROUND_CHECK', _('Background Check')
        PENDING_APPROVAL = 'PENDING_APPROVAL', _('Pending Approval')
        APPROVED = 'APPROVED', _('Approved')
        PROVISIONING = 'PROVISIONING', _('Provisioning Access')
        TRAINING = 'TRAINING', _('Training Phase')
        COMPLETED = 'COMPLETED', _('Completed')
        REJECTED = 'REJECTED', _('Rejected')
        CANCELLED = 'CANCELLED', _('Cancelled')

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField(
        _('Request Number'),
        max_length=50,
        unique=True,
        help_text=_('Auto-generated unique request identifier')
    )

    # Person details
    person_type = models.CharField(
        _('Person Type'),
        max_length=30,
        choices=PersonType.choices,
        help_text=_('Type of person being onboarded')
    )

    # Workflow
    current_state = models.CharField(
        _('Current State'),
        max_length=30,
        choices=WorkflowState.choices,
        default=WorkflowState.DRAFT
    )

    # Relationships
    conversation_session = models.ForeignKey(
        'core_onboarding.ConversationSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='people_onboarding_requests',
        help_text=_('Associated conversational AI session')
    )

    people = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onboarding_record',
        help_text=_('Created People record after successful onboarding')
    )

    changeset = models.ForeignKey(
        'core_onboarding.AIChangeSet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='people_onboarding_changesets',
        help_text=_('Changeset for rollback capability')
    )

    vendor = models.ForeignKey(
        'work_order_management.Vendor',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        help_text=_('Associated vendor company (for vendor personnel)')
    )

    # Dates
    start_date = models.DateField(_('Start Date'), null=True, blank=True)
    expected_completion_date = models.DateField(_('Expected Completion'), null=True, blank=True)
    actual_completion_date = models.DateField(_('Actual Completion'), null=True, blank=True)

    # Metadata
    rejection_reason = models.TextField(_('Rejection Reason'), blank=True)
    cancellation_reason = models.TextField(_('Cancellation Reason'), blank=True)
    notes = models.TextField(_('Notes'), blank=True)

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_request'
        verbose_name = _('Onboarding Request')
        verbose_name_plural = _('Onboarding Requests')
        indexes = [
            models.Index(fields=['request_number']),
            models.Index(fields=['current_state', 'created_at']),
            models.Index(fields=['person_type']),
            models.Index(fields=['start_date']),
        ]

    def __str__(self):
        return f"{self.request_number} - {self.get_person_type_display()}"

    def can_transition_to(self, new_state):
        """Validate if transition to new state is allowed"""
        valid_transitions = {
            self.WorkflowState.DRAFT: [self.WorkflowState.SUBMITTED, self.WorkflowState.CANCELLED],
            self.WorkflowState.SUBMITTED: [self.WorkflowState.DOCUMENT_VERIFICATION, self.WorkflowState.REJECTED],
            self.WorkflowState.DOCUMENT_VERIFICATION: [self.WorkflowState.BACKGROUND_CHECK, self.WorkflowState.REJECTED],
            self.WorkflowState.BACKGROUND_CHECK: [self.WorkflowState.PENDING_APPROVAL, self.WorkflowState.REJECTED],
            self.WorkflowState.PENDING_APPROVAL: [self.WorkflowState.APPROVED, self.WorkflowState.REJECTED],
            self.WorkflowState.APPROVED: [self.WorkflowState.PROVISIONING],
            self.WorkflowState.PROVISIONING: [self.WorkflowState.TRAINING],
            self.WorkflowState.TRAINING: [self.WorkflowState.COMPLETED],
        }
        return new_state in valid_transitions.get(self.current_state, [])
