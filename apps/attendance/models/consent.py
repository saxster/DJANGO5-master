"""
Employee Consent Management Models

Tracks employee consent for GPS tracking and biometric data collection.

Compliance:
- California: Requires explicit consent for GPS tracking (CA Labor Code)
- Louisiana: Requires written consent for GPS tracking (LA Rev Stat 14:323)
- Biometric Privacy Laws: Illinois BIPA, Texas CUBI, Washington HB 1493

Features:
- Digital signature capture
- Policy version tracking
- Consent revocation
- Audit trail
- State-specific consent language
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel
from typing import Optional
import uuid
import logging

logger = logging.getLogger(__name__)


class ConsentPolicy(BaseModel, TenantAwareModel):
    """
    Consent policy definition.

    Stores policy text, version, and state-specific requirements.
    """

    class PolicyType(models.TextChoices):
        GPS_TRACKING = 'GPS_TRACKING', 'GPS Location Tracking'
        BIOMETRIC_DATA = 'BIOMETRIC_DATA', 'Biometric Data Collection'
        PHOTO_CAPTURE = 'PHOTO_CAPTURE', 'Photo Capture'
        FACE_RECOGNITION = 'FACE_RECOGNITION', 'Face Recognition'

    class State(models.TextChoices):
        """US States with specific consent requirements"""
        FEDERAL = 'FEDERAL', 'Federal (Default)'
        CALIFORNIA = 'CA', 'California'
        LOUISIANA = 'LA', 'Louisiana'
        ILLINOIS = 'IL', 'Illinois (BIPA)'
        TEXAS = 'TX', 'Texas (CUBI)'
        WASHINGTON = 'WA', 'Washington'
        NEW_YORK = 'NY', 'New York'

    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )

    policy_type = models.CharField(
        max_length=50,
        choices=PolicyType.choices,
        help_text="Type of consent being requested"
    )

    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.FEDERAL,
        help_text="State jurisdiction for this policy"
    )

    version = models.CharField(
        max_length=20,
        help_text="Policy version (e.g., 1.0, 2.1)"
    )

    title = models.CharField(
        max_length=255,
        help_text="Policy title"
    )

    policy_text = models.TextField(
        help_text="Full policy text (HTML supported)"
    )

    summary = models.TextField(
        help_text="Plain language summary of the policy"
    )

    effective_date = models.DateField(
        help_text="Date this policy becomes effective"
    )

    expiration_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date this policy expires (optional)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this policy is currently active"
    )

    requires_signature = models.BooleanField(
        default=True,
        help_text="Whether digital signature is required"
    )

    requires_written_consent = models.BooleanField(
        default=False,
        help_text="Whether written (not just electronic) consent is required"
    )

    class Meta:
        db_table = 'consent_policy'
        verbose_name = 'Consent Policy'
        verbose_name_plural = 'Consent Policies'
        unique_together = [['policy_type', 'state', 'version']]
        indexes = [
            models.Index(fields=['tenant', 'policy_type', 'is_active'], name='cp_tenant_type_active_idx'),
            models.Index(fields=['effective_date'], name='cp_effective_date_idx'),
        ]
        ordering = ['-effective_date', '-version']

    def __str__(self):
        return f"{self.get_policy_type_display()} - {self.get_state_display()} v{self.version}"

    def clean(self):
        """Validate policy dates"""
        if self.expiration_date and self.expiration_date <= self.effective_date:
            raise ValidationError("Expiration date must be after effective date")


class EmployeeConsentLog(BaseModel, TenantAwareModel):
    """
    Log of employee consent grants and revocations.

    Tracks complete consent lifecycle with audit trail.
    """

    class ConsentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        GRANTED = 'GRANTED', 'Consent Granted'
        REVOKED = 'REVOKED', 'Consent Revoked'
        EXPIRED = 'EXPIRED', 'Consent Expired'
        DENIED = 'DENIED', 'Consent Denied'

    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consent_logs',
        help_text="Employee giving consent"
    )

    policy = models.ForeignKey(
        ConsentPolicy,
        on_delete=models.PROTECT,
        related_name='consent_logs',
        help_text="Policy being consented to"
    )

    status = models.CharField(
        max_length=20,
        choices=ConsentStatus.choices,
        default=ConsentStatus.PENDING,
        help_text="Current consent status"
    )

    # Consent grant information
    granted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When consent was granted"
    )

    granted_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address where consent was granted"
    )

    granted_user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User agent when consent was granted"
    )

    # Digital signature
    signature_data = models.TextField(
        null=True,
        blank=True,
        help_text="Digital signature data (base64 encoded image or typed name)"
    )

    signature_type = models.CharField(
        max_length=20,
        choices=[
            ('TYPED', 'Typed Name'),
            ('DRAWN', 'Drawn Signature'),
            ('ELECTRONIC', 'Electronic Acceptance'),
        ],
        null=True,
        blank=True,
        help_text="Type of signature provided"
    )

    # Written consent (for Louisiana, etc.)
    written_consent_document = models.FileField(
        upload_to='consent_documents/%Y/%m/',
        null=True,
        blank=True,
        help_text="Scanned written consent document (if required)"
    )

    # Revocation information
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When consent was revoked"
    )

    revoked_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for consent revocation"
    )

    revoked_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address where consent was revoked"
    )

    # Expiration
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When consent expires (optional)"
    )

    # Notifications
    notification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notification email was sent"
    )

    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reminder was sent (for pending consents)"
    )

    # Metadata
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Additional notes or context"
    )

    class Meta:
        db_table = 'employee_consent_log'
        verbose_name = 'Employee Consent Log'
        verbose_name_plural = 'Employee Consent Logs'
        indexes = [
            models.Index(fields=['tenant', 'employee', 'status'], name='ecl_tenant_emp_status_idx'),
            models.Index(fields=['tenant', 'policy', 'status'], name='ecl_tenant_policy_status_idx'),
            models.Index(fields=['status', 'expires_at'], name='ecl_status_expires_idx'),
            models.Index(fields=['granted_at'], name='ecl_granted_at_idx'),
        ]
        ordering = ['-granted_at', '-cdtz']

    def __str__(self):
        return f"{self.employee.username} - {self.policy.policy_type} ({self.status})"

    def clean(self):
        """Validate consent log"""
        if self.status == self.ConsentStatus.GRANTED and not self.granted_at:
            raise ValidationError("Granted consent must have granted_at timestamp")

        if self.status == self.ConsentStatus.REVOKED and not self.revoked_at:
            raise ValidationError("Revoked consent must have revoked_at timestamp")

        # Check policy requirement for written consent
        if self.policy.requires_written_consent and self.status == self.ConsentStatus.GRANTED:
            if not self.written_consent_document and not self.signature_data:
                raise ValidationError(
                    f"{self.policy.get_state_display()} requires written consent documentation"
                )

    def grant_consent(self, ip_address: Optional[str] = None,
                     user_agent: Optional[str] = None,
                     signature_data: Optional[str] = None,
                     signature_type: str = 'ELECTRONIC') -> None:
        """
        Grant consent.

        Args:
            ip_address: IP address where consent was granted
            user_agent: User agent string
            signature_data: Digital signature data
            signature_type: Type of signature
        """
        self.status = self.ConsentStatus.GRANTED
        self.granted_at = timezone.now()
        self.granted_ip = ip_address
        self.granted_user_agent = user_agent
        self.signature_data = signature_data
        self.signature_type = signature_type

        # Set expiration if policy has one
        if self.policy.expiration_date:
            from datetime import datetime
            self.expires_at = datetime.combine(
                self.policy.expiration_date,
                datetime.max.time()
            )

        self.save()
        logger.info(f"Consent granted: {self.employee.username} for {self.policy.policy_type}")

    def revoke_consent(self, reason: str, ip_address: Optional[str] = None) -> None:
        """
        Revoke consent.

        Args:
            reason: Reason for revocation
            ip_address: IP address where consent was revoked
        """
        self.status = self.ConsentStatus.REVOKED
        self.revoked_at = timezone.now()
        self.revoked_reason = reason
        self.revoked_ip = ip_address
        self.save()
        logger.info(f"Consent revoked: {self.employee.username} for {self.policy.policy_type} - {reason}")

    def is_active(self) -> bool:
        """Check if consent is currently active"""
        if self.status != self.ConsentStatus.GRANTED:
            return False

        # Check if expired
        if self.expires_at and timezone.now() > self.expires_at:
            if self.status != self.ConsentStatus.EXPIRED:
                self.status = self.ConsentStatus.EXPIRED
                self.save()
            return False

        return True

    @property
    def is_expired(self) -> bool:
        """Check if consent has expired"""
        return self.expires_at and timezone.now() > self.expires_at

    @property
    def days_until_expiration(self) -> Optional[int]:
        """Get days until consent expires"""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return delta.days if delta.days > 0 else 0


class ConsentRequirement(BaseModel, TenantAwareModel):
    """
    Define which employees require which consent based on location, role, etc.

    Allows flexible consent requirements per client/BU/role.
    """

    policy = models.ForeignKey(
        ConsentPolicy,
        on_delete=models.CASCADE,
        related_name='requirements',
        help_text="Policy that is required"
    )

    # Scope filters
    client = models.ForeignKey(
        'client_onboarding.Bt',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='consent_requirements_client',
        help_text="Apply to specific client (optional)"
    )

    bu = models.ForeignKey(
        'client_onboarding.Bt',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='consent_requirements_bu',
        help_text="Apply to specific BU (optional)"
    )

    role = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Apply to specific role (optional)"
    )

    state = models.CharField(
        max_length=20,
        choices=ConsentPolicy.State.choices,
        null=True,
        blank=True,
        help_text="Apply to employees in specific state (optional)"
    )

    # Requirement settings
    is_mandatory = models.BooleanField(
        default=True,
        help_text="Whether consent is mandatory for matching employees"
    )

    blocks_clock_in = models.BooleanField(
        default=True,
        help_text="Whether absence of consent blocks clock-in/out"
    )

    grace_period_days = models.IntegerField(
        default=0,
        help_text="Days before consent becomes mandatory (0 = immediate)"
    )

    reminder_days_before_expiration = models.IntegerField(
        default=30,
        help_text="Days before expiration to send reminder (0 = no reminder)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this requirement is currently active"
    )

    class Meta:
        db_table = 'consent_requirement'
        verbose_name = 'Consent Requirement'
        verbose_name_plural = 'Consent Requirements'
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='cr_tenant_active_idx'),
            models.Index(fields=['client'], name='cr_client_idx'),
            models.Index(fields=['bu'], name='cr_bu_idx'),
        ]

    def __str__(self):
        scope = []
        if self.client:
            scope.append(f"Client:{self.client.name}")
        if self.bu:
            scope.append(f"BU:{self.bu.name}")
        if self.state:
            scope.append(f"State:{self.state}")
        scope_str = ", ".join(scope) if scope else "All"
        return f"{self.policy.policy_type} - {scope_str}"

    def applies_to_user(self, user) -> bool:
        """
        Check if this requirement applies to the given user.

        Args:
            user: User to check

        Returns:
            True if requirement applies, False otherwise
        """
        # Check client
        if self.client and hasattr(user, 'client_id'):
            if user.client_id != self.client.id:
                return False

        # Check BU
        if self.bu and hasattr(user, 'bu_id'):
            if user.bu_id != self.bu.id:
                return False

        # Check role
        if self.role:
            user_roles = getattr(user, 'roles', [])
            if self.role not in user_roles:
                return False

        # Check state (would need user profile with state field)
        if self.state and hasattr(user, 'state'):
            if user.state != self.state:
                return False

        return True
