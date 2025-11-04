"""
Biometric Audit Log
Created: 2025-11-04
Extracted from models.py as part of god file refactoring

Required for GDPR Article 30 (Records of processing activities)
"""
import uuid
from django.db import models
from apps.peoples.models import BaseModel
from .biometric_consent_log import BiometricConsentLog
from .enums import BiometricOperationType


class BiometricAuditLog(BaseModel):
    """
    Detailed audit log for every biometric operation.

    Required for GDPR Article 30 (Records of processing activities).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    consent_log = models.ForeignKey(
        BiometricConsentLog,
        on_delete=models.CASCADE,
        related_name='audit_entries',
        help_text="Related consent log"
    )

    # Operation details
    operation_timestamp = models.DateTimeField(auto_now_add=True)
    operation_type = models.CharField(
        max_length=50,
        choices=BiometricOperationType.choices
    )
    operation_success = models.BooleanField()
    processing_time_ms = models.IntegerField(
        help_text="Operation processing time in milliseconds"
    )

    # Security context
    request_id = models.UUIDField(
        help_text="Unique request ID"
    )
    session_id = models.CharField(
        max_length=255,
        help_text="User session ID"
    )
    api_endpoint = models.CharField(
        max_length=255,
        help_text="API endpoint called"
    )

    # Failure tracking
    error_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Error code if operation failed"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message (sanitized, no PII)"
    )

    # Compliance flags
    consent_validated = models.BooleanField(
        default=False,
        help_text="Whether consent was validated before operation"
    )
    retention_policy_applied = models.BooleanField(
        default=False,
        help_text="Whether retention policy was applied"
    )

    class Meta(BaseModel.Meta):
        db_table = 'biometric_audit_log'
        verbose_name = "Biometric Audit Log"
        verbose_name_plural = "Biometric Audit Logs"
        ordering = ['-operation_timestamp']
        indexes = [
            models.Index(fields=['consent_log', 'operation_timestamp']),
            models.Index(fields=['operation_type', 'operation_success']),
            models.Index(fields=['request_id']),
        ]

    def __str__(self):
        return f"{self.operation_type} - {self.operation_timestamp}"
