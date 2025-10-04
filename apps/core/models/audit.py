"""
Audit Models

Comprehensive audit trail for all entity operations.

Features:
- Generic audit log for all entities
- State transition tracking
- Bulk operation tracking
- Permission denial logging
- PII redaction (Rule #15 compliance)
- Retention policies (90 days hot, 2 years cold)

Compliance with .claude/rules.md:
- Rule #7: Model < 150 lines
- Rule #15: No PII in logs
- Rule #17: Transaction management
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.peoples.models import BaseModel, TenantAwareModel, People
from apps.tenants.models import Tenant
import uuid


class AuditEventType(models.TextChoices):
    """Types of auditable events"""
    CREATED = 'CREATED', 'Entity Created'
    UPDATED = 'UPDATED', 'Entity Updated'
    DELETED = 'DELETED', 'Entity Deleted'
    STATE_CHANGED = 'STATE_CHANGED', 'State Transition'
    BULK_OPERATION = 'BULK_OPERATION', 'Bulk Operation'
    PERMISSION_DENIED = 'PERMISSION_DENIED', 'Permission Denied'
    DATA_ACCESSED = 'DATA_ACCESSED', 'Data Accessed'
    EXPORT_EXECUTED = 'EXPORT_EXECUTED', 'Data Export'


class AuditLevel(models.TextChoices):
    """Audit log severity levels"""
    INFO = 'INFO', 'Information'
    WARNING = 'WARNING', 'Warning'
    ERROR = 'ERROR', 'Error'
    CRITICAL = 'CRITICAL', 'Critical'
    SECURITY = 'SECURITY', 'Security Event'


class AuditLog(BaseModel, TenantAwareModel):
    """
    Universal audit log for all entities.

    Tracks all significant operations across the system for:
    - Compliance and regulatory requirements
    - Security monitoring and forensics
    - Debugging and troubleshooting
    - User activity tracking

    Note: PII fields are automatically redacted (Rule #15)
    """

    # Event identification
    correlation_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text='Unique ID for grouping related events'
    )
    event_type = models.CharField(
        max_length=30,
        choices=AuditEventType.choices,
        db_index=True
    )
    level = models.CharField(
        max_length=20,
        choices=AuditLevel.choices,
        default=AuditLevel.INFO,
        db_index=True
    )

    # Entity being audited (generic foreign key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    content_object = GenericForeignKey('content_type', 'object_id')

    # User and session context
    user = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Event details
    action = models.CharField(max_length=100, help_text='Action performed')
    message = models.TextField(help_text='Human-readable description')

    # Change tracking (before/after state)
    changes = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text='Fields changed with before/after values'
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text='Additional context data'
    )

    # Security flags
    security_flags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text='Security-relevant flags (e.g., ["suspicious_activity", "privilege_escalation"])'
    )

    # Timing
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Operation duration in milliseconds'
    )

    # Retention management
    retention_until = models.DateTimeField(
        db_index=True,
        help_text='When this log can be archived/deleted'
    )
    is_archived = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'audit_log'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'event_type', '-timestamp']),
            models.Index(fields=['tenant', 'user', '-timestamp']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['level', '-timestamp']),
            models.Index(fields=['retention_until', 'is_archived']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.action} at {self.timestamp}"

    def save(self, *args, **kwargs):
        """Set retention date on save"""
        if not self.retention_until:
            # Default: 90 days hot storage
            self.retention_until = timezone.now() + timezone.timedelta(days=90)
        super().save(*args, **kwargs)


class StateTransitionAudit(BaseModel):
    """
    Specialized audit log for state machine transitions.

    Tracks all state changes with rich context for:
    - Workflow analysis
    - SLA tracking
    - Compliance verification
    """

    audit_log = models.OneToOneField(
        AuditLog,
        on_delete=models.CASCADE,
        related_name='state_transition'
    )

    # State transition details
    from_state = models.CharField(max_length=50)
    to_state = models.CharField(max_length=50)
    transition_successful = models.BooleanField(default=True)
    failure_reason = models.TextField(blank=True)

    # Approval/rejection tracking
    approved_by = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transitions'
    )
    rejection_reason = models.TextField(blank=True)

    # Timing metrics
    time_in_previous_state = models.DurationField(
        null=True,
        blank=True,
        help_text='How long entity was in previous state'
    )

    class Meta:
        db_table = 'state_transition_audit'
        verbose_name = 'State Transition Audit'
        verbose_name_plural = 'State Transition Audits'

    def __str__(self):
        return f"{self.from_state} → {self.to_state}"


class BulkOperationAudit(BaseModel):
    """
    Audit log for bulk operations.

    Tracks batch operations with detailed success/failure metrics.
    """

    audit_log = models.OneToOneField(
        AuditLog,
        on_delete=models.CASCADE,
        related_name='bulk_operation'
    )

    # Operation details
    operation_type = models.CharField(
        max_length=50,
        help_text='Type of bulk operation (approve, reject, assign, etc.)'
    )
    entity_type = models.CharField(max_length=50)

    # Metrics
    total_items = models.IntegerField(help_text='Total items in operation')
    successful_items = models.IntegerField(help_text='Successfully processed')
    failed_items = models.IntegerField(help_text='Failed to process')

    # Item tracking
    successful_ids = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text='IDs of successfully processed items'
    )
    failed_ids = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text='IDs of failed items'
    )

    # Failure details
    failure_details = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text='Detailed error messages for failed items'
    )

    # Rollback tracking
    was_rolled_back = models.BooleanField(default=False)
    rollback_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'bulk_operation_audit'
        verbose_name = 'Bulk Operation Audit'
        verbose_name_plural = 'Bulk Operation Audits'

    def __str__(self):
        return f"Bulk {self.operation_type}: {self.successful_items}/{self.total_items} successful"


class PermissionDenialAudit(BaseModel):
    """
    Audit log for permission denials.

    Tracks all access control violations for security monitoring.
    """

    audit_log = models.OneToOneField(
        AuditLog,
        on_delete=models.CASCADE,
        related_name='permission_denial'
    )

    # Permission details
    required_permissions = ArrayField(
        models.CharField(max_length=100),
        help_text='Permissions that were required'
    )
    user_permissions = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text='Permissions the user actually has'
    )

    # Request details
    attempted_action = models.CharField(max_length=100)
    request_path = models.CharField(max_length=500)
    request_method = models.CharField(max_length=10)

    # Risk assessment
    is_suspicious = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Flagged as potentially suspicious activity'
    )
    risk_score = models.IntegerField(
        default=0,
        help_text='Risk score (0-100, higher = more suspicious)'
    )

    class Meta:
        db_table = 'permission_denial_audit'
        verbose_name = 'Permission Denial Audit'
        verbose_name_plural = 'Permission Denial Audits'
        indexes = [
            models.Index(fields=['is_suspicious', '-created_on']),
            models.Index(fields=['risk_score']),
        ]

    def __str__(self):
        return f"Access denied: {self.attempted_action}"
