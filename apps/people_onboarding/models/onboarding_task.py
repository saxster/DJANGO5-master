"""
OnboardingTask Model

Checklist tasks for onboarding completion tracking.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import EnhancedTenantModel


class TaskPriority(models.TextChoices):
    """Task priority choices"""
    LOW = 'LOW', _('Low')
    MEDIUM = 'MEDIUM', _('Medium')
    HIGH = 'HIGH', _('High')
    CRITICAL = 'CRITICAL', _('Critical')


class OnboardingTask(EnhancedTenantModel):
    """
    Individual tasks in the onboarding checklist.

    Provides granular tracking of all onboarding activities:
    - Document collection
    - Form completion
    - System setup
    - Training attendance
    - Equipment handover
    - Policy acknowledgment
    """

    class TaskCategory(models.TextChoices):
        """Task categories"""
        DOCUMENTATION = 'DOCUMENTATION', _('Documentation')
        VERIFICATION = 'VERIFICATION', _('Verification')
        APPROVAL = 'APPROVAL', _('Approval')
        PROVISIONING = 'PROVISIONING', _('Provisioning')
        TRAINING = 'TRAINING', _('Training')
        EQUIPMENT = 'EQUIPMENT', _('Equipment')
        ADMINISTRATIVE = 'ADMINISTRATIVE', _('Administrative')

    class TaskStatus(models.TextChoices):
        """Task status"""
        TODO = 'TODO', _('To Do')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        BLOCKED = 'BLOCKED', _('Blocked')
        COMPLETED = 'COMPLETED', _('Completed')
        SKIPPED = 'SKIPPED', _('Skipped')

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='tasks'
    )

    # Task details
    category = models.CharField(
        _('Category'),
        max_length=20,
        choices=TaskCategory.choices
    )

    title = models.CharField(_('Title'), max_length=200)
    description = models.TextField(_('Description'), blank=True)

    # Status
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO
    )

    priority = models.CharField(
        _('Priority'),
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM
    )

    # Responsible parties
    assigned_to = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_onboarding_tasks',
        help_text=_('Person responsible for completing this task')
    )

    completed_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_onboarding_tasks'
    )

    # Dates
    due_date = models.DateField(_('Due Date'), null=True, blank=True)
    completed_at = models.DateTimeField(_('Completed At'), null=True, blank=True)

    # Dependencies
    depends_on = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependent_tasks',
        verbose_name=_('Depends On'),
        help_text=_('Tasks that must be completed before this one')
    )

    # Blocking
    blocker_reason = models.TextField(_('Blocker Reason'), blank=True)

    # Skip
    skip_reason = models.TextField(_('Skip Reason'), blank=True)

    # Flags
    is_mandatory = models.BooleanField(_('Is Mandatory'), default=True)
    requires_evidence = models.BooleanField(
        _('Requires Evidence'),
        default=False,
        help_text=_('Requires document/photo proof of completion')
    )

    # Evidence
    evidence_file = models.FileField(
        _('Evidence'),
        upload_to='people_onboarding/task_evidence/',
        null=True,
        blank=True
    )

    completion_notes = models.TextField(_('Completion Notes'), blank=True)

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_task'
        verbose_name = _('Onboarding Task')
        verbose_name_plural = _('Onboarding Tasks')
        ordering = ['priority', 'due_date']
        indexes = [
            models.Index(fields=['onboarding_request', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['due_date', 'status']),
        ]

    def __str__(self):
        return f"{self.onboarding_request.request_number} - {self.title}"

    def can_start(self):
        """Check if all dependencies are completed"""
        return not self.depends_on.exclude(status=self.TaskStatus.COMPLETED).exists()