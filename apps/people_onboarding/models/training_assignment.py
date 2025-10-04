"""
TrainingAssignment Model

Mandatory training and orientation tracking for new hires.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import EnhancedTenantModel


class TrainingStatus(models.TextChoices):
    """Training status choices"""
    NOT_STARTED = 'NOT_STARTED', _('Not Started')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    COMPLETED = 'COMPLETED', _('Completed')
    FAILED = 'FAILED', _('Failed')
    OVERDUE = 'OVERDUE', _('Overdue')


class TrainingAssignment(EnhancedTenantModel):
    """
    Training and orientation assignments for new hires.

    Tracks:
    - Safety orientation
    - Policy acknowledgment
    - Mandatory compliance training
    - Equipment operation certification
    - Site-specific training
    - Department induction
    """

    class TrainingType(models.TextChoices):
        """Types of training"""
        SAFETY_ORIENTATION = 'SAFETY_ORIENTATION', _('Safety Orientation')
        POLICY_TRAINING = 'POLICY_TRAINING', _('Company Policies')
        COMPLIANCE = 'COMPLIANCE', _('Compliance Training')
        EQUIPMENT_OPERATION = 'EQUIPMENT_OPERATION', _('Equipment Operation')
        SITE_INDUCTION = 'SITE_INDUCTION', _('Site Induction')
        DEPARTMENT_ORIENTATION = 'DEPARTMENT_ORIENTATION', _('Department Orientation')
        SECURITY_AWARENESS = 'SECURITY_AWARENESS', _('Security Awareness')
        IT_SYSTEMS = 'IT_SYSTEMS', _('IT Systems Training')
        SOFT_SKILLS = 'SOFT_SKILLS', _('Soft Skills')
        TECHNICAL_SKILLS = 'TECHNICAL_SKILLS', _('Technical Skills')

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='training_assignments'
    )

    # Training details
    training_type = models.CharField(
        _('Training Type'),
        max_length=30,
        choices=TrainingType.choices
    )

    training_title = models.CharField(_('Training Title'), max_length=200)
    training_description = models.TextField(_('Description'), blank=True)

    # Status
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=TrainingStatus.choices,
        default=TrainingStatus.NOT_STARTED
    )

    # Dates
    assigned_date = models.DateField(_('Assigned Date'), auto_now_add=True)
    due_date = models.DateField(_('Due Date'))
    start_date = models.DateField(_('Start Date'), null=True, blank=True)
    completion_date = models.DateField(_('Completion Date'), null=True, blank=True)

    # Trainer/Instructor
    trainer = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_onboarding_trainings'
    )

    # Assessment
    requires_assessment = models.BooleanField(_('Requires Assessment'), default=False)
    assessment_score = models.DecimalField(
        _('Assessment Score'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Score out of 100')
    )

    passing_score = models.DecimalField(
        _('Passing Score'),
        max_digits=5,
        decimal_places=2,
        default=70.00,
        help_text=_('Minimum score to pass')
    )

    # Certification
    certificate_issued = models.BooleanField(_('Certificate Issued'), default=False)
    certificate_file = models.FileField(
        _('Certificate'),
        upload_to='people_onboarding/certificates/',
        null=True,
        blank=True
    )

    # Duration
    estimated_duration_hours = models.DecimalField(
        _('Estimated Duration (Hours)'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    actual_duration_hours = models.DecimalField(
        _('Actual Duration (Hours)'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Flags
    is_mandatory = models.BooleanField(_('Is Mandatory'), default=True)
    is_blocking = models.BooleanField(
        _('Is Blocking'),
        default=False,
        help_text=_('Blocks onboarding completion if not done')
    )

    # Notes
    completion_notes = models.TextField(_('Completion Notes'), blank=True)

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_training_assignment'
        verbose_name = _('Training Assignment')
        verbose_name_plural = _('Training Assignments')
        indexes = [
            models.Index(fields=['onboarding_request', 'training_type']),
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"{self.onboarding_request.request_number} - {self.training_title}"