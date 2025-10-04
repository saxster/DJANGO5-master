"""
AccessProvisioning Model

System access, biometric enrollment, and physical access provisioning.
Complies with Rule #7: < 150 lines
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import EnhancedTenantModel


class AccessType(models.TextChoices):
    """Access provisioning type choices"""
    BIOMETRIC_FACE = 'BIOMETRIC_FACE', _('Face Recognition Enrollment')
    BIOMETRIC_VOICE = 'BIOMETRIC_VOICE', _('Voice Biometric Enrollment')
    BIOMETRIC_FINGERPRINT = 'BIOMETRIC_FINGERPRINT', _('Fingerprint Enrollment')
    LOGIN_CREDENTIALS = 'LOGIN_CREDENTIALS', _('System Login Credentials')
    EMAIL_ACCOUNT = 'EMAIL_ACCOUNT', _('Email Account')
    VPN_ACCESS = 'VPN_ACCESS', _('VPN Access')
    DEVICE_ASSIGNMENT = 'DEVICE_ASSIGNMENT', _('Device Assignment')
    BADGE_ID = 'BADGE_ID', _('Badge/ID Card')
    SITE_ACCESS = 'SITE_ACCESS', _('Physical Site Access')
    PARKING_SPACE = 'PARKING_SPACE', _('Parking Space')
    LOCKER = 'LOCKER', _('Locker Assignment')
    SOFTWARE_LICENSE = 'SOFTWARE_LICENSE', _('Software License')


class AccessProvisioning(EnhancedTenantModel):
    """
    Access provisioning and enrollment tracking.

    Automates:
    - Biometric enrollment (face, voice, fingerprint)
    - System credential creation
    - Physical access permissions
    - Asset assignments
    """

    class ProvisioningStatus(models.TextChoices):
        """Provisioning status"""
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
        REVOKED = 'REVOKED', _('Revoked')

    # Identifiers
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # Relationships
    onboarding_request = models.ForeignKey(
        'people_onboarding.OnboardingRequest',
        on_delete=models.CASCADE,
        related_name='access_provisions'
    )

    # Access details
    access_type = models.CharField(
        _('Access Type'),
        max_length=30,
        choices=AccessType.choices
    )

    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=ProvisioningStatus.choices,
        default=ProvisioningStatus.PENDING
    )

    # Provisioning metadata
    provisioned_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='provisioned_access'
    )

    provisioned_at = models.DateTimeField(_('Provisioned At'), null=True, blank=True)

    # Access details (JSON for flexibility)
    access_details = models.JSONField(
        _('Access Details'),
        default=dict,
        blank=True,
        help_text=_('Details like device ID, badge number, email address, etc.')
    )

    # For site access
    allowed_sites = models.ManyToManyField(
        'onboarding.Bt',
        blank=True,
        related_name='onboarded_personnel_access',
        verbose_name=_('Allowed Sites')
    )

    # Dates
    access_start_date = models.DateField(_('Access Start Date'), null=True, blank=True)
    access_end_date = models.DateField(
        _('Access End Date'),
        null=True,
        blank=True,
        help_text=_('For contractors/temporary workers')
    )

    # Revocation
    revoked_at = models.DateTimeField(_('Revoked At'), null=True, blank=True)
    revocation_reason = models.TextField(_('Revocation Reason'), blank=True)

    # Failure tracking
    failure_reason = models.TextField(_('Failure Reason'), blank=True)
    retry_count = models.PositiveSmallIntegerField(_('Retry Count'), default=0)

    # Flags
    requires_approval = models.BooleanField(_('Requires Approval'), default=True)
    is_temporary = models.BooleanField(_('Is Temporary'), default=False)

    class Meta(EnhancedTenantModel.Meta):
        db_table = 'people_onboarding_access_provisioning'
        verbose_name = _('Access Provisioning')
        verbose_name_plural = _('Access Provisionings')
        indexes = [
            models.Index(fields=['onboarding_request', 'access_type']),
            models.Index(fields=['status']),
            models.Index(fields=['access_end_date']),
        ]

    def __str__(self):
        return f"{self.onboarding_request.request_number} - {self.get_access_type_display()}"