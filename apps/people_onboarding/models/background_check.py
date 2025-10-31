"""
BackgroundCheck Model

Background verification and compliance checks for onboarding candidates.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.core.models import EnhancedTenantModel


class VerificationStatus(models.TextChoices):
    """Verification status choices"""
    PENDING = 'PENDING', _('Pending')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    COMPLETED = 'COMPLETED', _('Completed')
    FAILED = 'FAILED', _('Failed')
    EXPIRED = 'EXPIRED', _('Expired')


class BackgroundCheck(EnhancedTenantModel):
    """
    Background verification and compliance checks.

    Supports multiple verification types:
    - Criminal background check
    - Employment history verification
    - Educational qualification verification
    - Professional license verification
    - Reference checks
    - Credit check (for finance roles)
    - Drug testing
    """

    class VerificationType(models.TextChoices):
        """Types of background checks"""
        CRIMINAL = 'CRIMINAL', _('Criminal Background Check')
        EMPLOYMENT = 'EMPLOYMENT', _('Employment History')
        EDUCATION = 'EDUCATION', _('Educational Qualification')
        LICENSE = 'LICENSE', _('Professional License')
        REFERENCE = 'REFERENCE', _('Reference Check')
        CREDIT = 'CREDIT', _('Credit Check')
        DRUG_TEST = 'DRUG_TEST', _('Drug Testing')
        ADDRESS = 'ADDRESS', _('Address Verification')
        IDENTITY = 'IDENTITY', _('Identity Verification')

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='background_checks'
    )

    # Verification details
    verification_type = models.CharField(
        _('Verification Type'),
        max_length=20,
        choices=VerificationType.choices
    )

    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )

    # Provider details
    verification_provider = models.CharField(
        _('Verification Provider'),
        max_length=200,
        blank=True,
        help_text=_('External agency or internal department')
    )

    provider_reference_number = models.CharField(
        _('Provider Reference'),
        max_length=100,
        blank=True
    )

    # Dates
    requested_date = models.DateField(_('Requested Date'), auto_now_add=True)
    expected_completion_date = models.DateField(_('Expected Completion'), null=True, blank=True)
    actual_completion_date = models.DateField(_('Actual Completion'), null=True, blank=True)
    expiry_date = models.DateField(
        _('Expiry Date'),
        null=True,
        blank=True,
        help_text=_('Date when this verification expires (e.g., drug test validity)')
    )

    # Results
    result = models.CharField(
        _('Result'),
        max_length=20,
        choices=[
            ('CLEAR', _('Clear')),
            ('DISCREPANCY', _('Discrepancy Found')),
            ('FAIL', _('Failed')),
            ('PENDING_REVIEW', _('Pending Review')),
        ],
        blank=True
    )

    result_details = models.JSONField(
        _('Result Details'),
        default=dict,
        blank=True,
        help_text=_('Detailed verification results')
    )

    findings = models.TextField(_('Findings'), blank=True)
    recommendations = models.TextField(_('Recommendations'), blank=True)

    # Documents
    report_file = models.FileField(
        _('Verification Report'),
        upload_to='people_onboarding/background_checks/',
        null=True,
        blank=True
    )

    # Costs
    cost = models.DecimalField(
        _('Cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Flags
    requires_manual_review = models.BooleanField(_('Requires Manual Review'), default=False)
    is_blocking = models.BooleanField(
        _('Is Blocking'),
        default=True,
        help_text=_('Whether this check must pass before proceeding')
    )

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_background_check'
        verbose_name = _('Background Check')
        verbose_name_plural = _('Background Checks')
        indexes = [
            models.Index(fields=['onboarding_request', 'verification_type']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['expiry_date']),
        ]

    def __str__(self):
        return f"{self.onboarding_request.request_number} - {self.get_verification_type_display()}"