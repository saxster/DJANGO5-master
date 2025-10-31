"""
PII Access Audit Trail Models

Models for tracking access to sensitive PII fields.
Provides comprehensive audit trail for GDPR/HIPAA compliance.

Features:
- Field-level access tracking
- Admin access logging
- Redaction event logging
- Compliance reporting
- Searchable audit trail

Author: Claude Code
Date: 2025-10-01
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from datetime import datetime, timezone as dt_timezone, timedelta

User = get_user_model()


class PIIAccessLog(models.Model):
    """
    Audit log for access to PII fields.

    Tracks every access to sensitive fields for compliance.
    """

    ACCESS_TYPE_CHOICES = [
        ('read', 'Read'),
        ('write', 'Write'),
        ('delete', 'Delete'),
        ('redacted', 'Redacted'),
        ('admin_view', 'Admin View'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Who accessed what
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='pii_access_logs',
        help_text="User who accessed PII"
    )
    accessed_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pii_accessed_logs',
        help_text="User whose PII was accessed"
    )

    # What was accessed
    model_type = models.CharField(
        max_length=100,
        help_text="Model type (JournalEntry, WellnessInteraction, etc.)"
    )
    instance_id = models.UUIDField(
        help_text="ID of accessed instance"
    )
    field_name = models.CharField(
        max_length=100,
        help_text="Name of PII field accessed"
    )

    # Access details
    access_type = models.CharField(
        max_length=20,
        choices=ACCESS_TYPE_CHOICES,
        help_text="Type of access"
    )
    was_redacted = models.BooleanField(
        default=False,
        help_text="Whether field was redacted"
    )
    redaction_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reason for redaction"
    )

    # Context
    request_path = models.CharField(
        max_length=500,
        help_text="Request path"
    )
    request_method = models.CharField(
        max_length=10,
        help_text="HTTP method"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Client user agent"
    )

    # Severity and classification
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium',
        help_text="Severity of access"
    )
    justification = models.TextField(
        blank=True,
        help_text="Justification for access (for admin access)"
    )

    # Timestamps
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "PII Access Log"
        verbose_name_plural = "PII Access Logs"
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['user', 'accessed_at']),
            models.Index(fields=['accessed_user', 'accessed_at']),
            models.Index(fields=['model_type', 'instance_id']),
            models.Index(fields=['field_name']),
            models.Index(fields=['access_type']),
            models.Index(fields=['was_redacted']),
            models.Index(fields=['severity']),
            models.Index(fields=['accessed_at']),
        ]

    def __str__(self):
        return f"{self.user} {self.access_type} {self.field_name} ({self.accessed_at})"

    @classmethod
    def log_access(
        cls,
        user,
        accessed_user,
        model_type: str,
        instance_id: str,
        field_name: str,
        access_type: str,
        was_redacted: bool = False,
        request=None,
        **kwargs
    ):
        """
        Create an access log entry.

        Args:
            user: User accessing PII
            accessed_user: User whose PII is accessed
            model_type: Type of model
            instance_id: Instance ID
            field_name: Field name
            access_type: Type of access
            was_redacted: Whether redacted
            request: HTTP request (optional)
            **kwargs: Additional fields

        Returns:
            PIIAccessLog: Created log entry
        """
        log_data = {
            'user': user,
            'accessed_user': accessed_user,
            'model_type': model_type,
            'instance_id': instance_id,
            'field_name': field_name,
            'access_type': access_type,
            'was_redacted': was_redacted,
        }

        # Extract request context if provided
        if request:
            log_data['request_path'] = request.path
            log_data['request_method'] = request.method
            log_data['ip_address'] = cls._get_client_ip(request)
            log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]
        else:
            log_data['request_path'] = 'unknown'
            log_data['request_method'] = 'unknown'

        # Add any additional fields
        log_data.update(kwargs)

        return cls.objects.create(**log_data)

    @staticmethod
    def _get_client_ip(request) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '')

    @classmethod
    def get_user_access_report(cls, user, days=30):
        """
        Generate access report for a user.

        Args:
            user: User to generate report for
            days: Number of days to include

        Returns:
            dict: Access report
        """
        cutoff_date = timezone.now() - timedelta(days=days)

        # Get all access logs for this user
        logs = cls.objects.filter(
            accessed_user=user,
            accessed_at__gte=cutoff_date
        )

        return {
            'user_id': str(user.id),
            'period_days': days,
            'total_accesses': logs.count(),
            'accesses_by_type': {
                access_type: logs.filter(access_type=access_type).count()
                for access_type, _ in cls.ACCESS_TYPE_CHOICES
            },
            'redacted_accesses': logs.filter(was_redacted=True).count(),
            'admin_accesses': logs.filter(user__is_staff=True).count(),
            'unique_accessors': logs.values('user').distinct().count(),
            'generated_at': timezone.now().isoformat(),
        }


class PIIRedactionEvent(models.Model):
    """
    Log of PII redaction events.

    Tracks when and why PII was redacted.
    """

    REDACTION_REASON_CHOICES = [
        ('non_owner', 'Non-Owner Access'),
        ('privacy_scope', 'Privacy Scope Violation'),
        ('consent_missing', 'Consent Not Given'),
        ('policy_violation', 'Policy Violation'),
        ('automatic', 'Automatic Redaction'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # What was redacted
    model_type = models.CharField(
        max_length=100,
        help_text="Model type"
    )
    instance_id = models.UUIDField(
        help_text="Instance ID"
    )
    fields_redacted = ArrayField(
        models.CharField(max_length=100),
        help_text="List of fields redacted"
    )

    # Why and when
    redaction_reason = models.CharField(
        max_length=50,
        choices=REDACTION_REASON_CHOICES,
        help_text="Reason for redaction"
    )
    requesting_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='caused_redactions',
        help_text="User who caused redaction"
    )
    redacted_at = models.DateTimeField(auto_now_add=True)

    # Context
    request_path = models.CharField(max_length=500)
    redaction_count = models.IntegerField(
        default=1,
        help_text="Number of fields redacted"
    )

    class Meta:
        verbose_name = "PII Redaction Event"
        verbose_name_plural = "PII Redaction Events"
        ordering = ['-redacted_at']
        indexes = [
            models.Index(fields=['model_type', 'instance_id']),
            models.Index(fields=['redaction_reason']),
            models.Index(fields=['requesting_user', 'redacted_at']),
            models.Index(fields=['redacted_at']),
        ]

    def __str__(self):
        return f"Redacted {self.redaction_count} fields ({self.redaction_reason})"

    @classmethod
    def log_redaction(
        cls,
        model_type: str,
        instance_id: str,
        fields_redacted: list,
        redaction_reason: str,
        requesting_user=None,
        request_path: str = 'unknown'
    ):
        """
        Log a redaction event.

        Args:
            model_type: Type of model
            instance_id: Instance ID
            fields_redacted: List of fields redacted
            redaction_reason: Reason for redaction
            requesting_user: User who caused redaction
            request_path: Request path

        Returns:
            PIIRedactionEvent: Created event
        """
        return cls.objects.create(
            model_type=model_type,
            instance_id=instance_id,
            fields_redacted=fields_redacted,
            redaction_reason=redaction_reason,
            requesting_user=requesting_user,
            request_path=request_path,
            redaction_count=len(fields_redacted)
        )
