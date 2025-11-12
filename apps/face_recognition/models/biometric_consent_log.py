"""
Biometric Consent and Audit Logging
Created: 2025-11-04
Extracted from models.py as part of god file refactoring

Added 2025-10-01 for regulatory compliance
Complies with: GDPR Article 9, BIPA, CCPA
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from .enums import BiometricConsentType, BiometricOperationType


class BiometricConsentLog(BaseModel, TenantAwareModel):
    """
    Comprehensive audit log for biometric consent and operations.

    Regulatory Requirements:
    - Consent tracking (GDPR Article 9)
    - 7-year retention for audit (BIPA Section 15(d))
    - Withdrawal tracking (GDPR Article 7(3))
    - Purpose limitation (GDPR Article 5(1)(b))
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='biometric_consent_logs',
        help_text="User whose biometric data is being processed"
    )

    # Consent details
    consent_type = models.CharField(
        max_length=50,
        choices=BiometricConsentType.choices,
        help_text="Type of biometric data"
    )
    consent_given = models.BooleanField(
        default=False,
        help_text="Whether consent was given"
    )
    consent_timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="When consent was given or withdrawn"
    )
    consent_method = models.CharField(
        max_length=100,
        help_text="How consent was obtained (e.g., 'mobile_app', 'web_portal')"
    )

    # Purpose and scope
    processing_purpose = models.TextField(
        help_text="Specific purpose for biometric processing (GDPR Article 5(1)(b))"
    )
    data_retention_period = models.IntegerField(
        default=2555,  # 7 years in days
        help_text="Data retention period in days (default: 7 years for BIPA)"
    )

    # Operation tracking
    operation_type = models.CharField(
        max_length=50,
        choices=BiometricOperationType.choices,
        null=True,
        blank=True,
        help_text="Type of biometric operation performed"
    )
    operation_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the biometric operation was performed"
    )
    operation_success = models.BooleanField(
        default=True,
        help_text="Whether the operation succeeded"
    )
    operation_details = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Additional operation metadata (no PII)"
    )

    # Audit trail
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    correlation_id = models.UUIDField(
        default=uuid.uuid4,
        help_text="Correlation ID for request tracing"
    )

    # Withdrawal tracking
    consent_withdrawn = models.BooleanField(
        default=False,
        help_text="Whether consent has been withdrawn"
    )
    withdrawal_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When consent was withdrawn"
    )
    withdrawal_method = models.CharField(
        max_length=100,
        blank=True,
        help_text="How consent was withdrawn"
    )

    class Meta(BaseModel.Meta):
        db_table = 'biometric_consent_log'
        verbose_name = "Biometric Consent Log"
        verbose_name_plural = "Biometric Consent Logs"
        ordering = ['-consent_timestamp']
        indexes = [
            models.Index(fields=['user', 'consent_type']),
            models.Index(fields=['consent_given', 'consent_withdrawn']),
            models.Index(fields=['operation_type', 'operation_timestamp']),
        ]

    def __str__(self):
        return f"{self.user.peoplename} - {self.consent_type} - {self.consent_timestamp}"

    @property
    def is_consent_valid(self):
        """Check if consent is still valid (not withdrawn and within retention period)"""
        if self.consent_withdrawn:
            return False

        if not self.consent_given:
            return False

        # Check if retention period has expired
        retention_end = self.consent_timestamp + timezone.timedelta(days=self.data_retention_period)
        return timezone.now() < retention_end

    @property
    def days_until_expiry(self):
        """Calculate days until consent expires"""
        if not self.consent_given or self.consent_withdrawn:
            return 0

        retention_end = self.consent_timestamp + timezone.timedelta(days=self.data_retention_period)
        days_left = (retention_end - timezone.now()).days
        return max(0, days_left)
