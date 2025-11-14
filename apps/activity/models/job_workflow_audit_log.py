"""
Job Workflow Audit Log Model

Comprehensive audit trail for all job and jobneed workflow state changes.
Tracks status transitions, assignment changes, and system operations.

Following .claude/rules.md:
- Rule 7: Model complexity limits (< 150 lines)
- Rule 11: Specific exception handling
- Single responsibility: Audit logging only
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from apps.core.models import BaseModel
from apps.tenants.models import TenantAwareModel
import uuid


class JobWorkflowAuditLog(BaseModel, TenantAwareModel):
    """
    Audit log for job workflow state transitions.

    Tracks all changes to job/jobneed status, assignments, and critical fields.
    Immutable record for compliance and debugging.
    """

    class OperationType(models.TextChoices):
        STATUS_CHANGE = 'STATUS_CHANGE', 'Status Change'
        ASSIGNMENT_CHANGE = 'ASSIGNMENT_CHANGE', 'Assignment Change'
        CHECKPOINT_UPDATE = 'CHECKPOINT_UPDATE', 'Checkpoint Update'
        AUTOCLOSE = 'AUTOCLOSE', 'Auto Close'
        ESCALATION = 'ESCALATION', 'Escalation'
        CREATION = 'CREATION', 'Creation'
        DELETION = 'DELETION', 'Deletion'

    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False
    )

    job = models.ForeignKey(
        'activity.Job',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_audit_logs',
        help_text='Parent job (if applicable)'
    )

    jobneed = models.ForeignKey(
        'activity.Jobneed',
        on_delete=models.CASCADE,
        related_name='workflow_audit_logs',
        help_text='Jobneed that was modified'
    )

    operation_type = models.CharField(
        max_length=50,
        choices=OperationType.choices,
        db_index=True,
        help_text='Type of workflow operation'
    )

    old_status = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        help_text='Previous status value'
    )

    new_status = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        help_text='New status value'
    )

    old_assignment_person_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='Previous assigned person ID'
    )

    new_assignment_person_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='New assigned person ID'
    )

    old_assignment_group_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='Previous assigned group ID'
    )

    new_assignment_group_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='New assigned group ID'
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='job_workflow_changes',
        help_text='User or system that made the change'
    )

    change_timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When the change occurred'
    )

    lock_acquisition_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Time taken to acquire lock (milliseconds)'
    )

    transaction_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Total transaction duration (milliseconds)'
    )

    metadata = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text='Additional metadata about the change'
    )

    correlation_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text='Correlation ID for tracing related operations'
    )

    class Meta:
        db_table = 'job_workflow_audit_log'
        ordering = ['-change_timestamp']
        indexes = [
            models.Index(fields=['jobneed', 'change_timestamp'], name='audit_jobneed_ts_idx'),
            models.Index(fields=['operation_type', 'change_timestamp'], name='audit_op_ts_idx'),
            models.Index(fields=['changed_by', 'change_timestamp'], name='audit_user_ts_idx'),
            models.Index(fields=['old_status', 'new_status'], name='audit_status_transition_idx'),
        ]
        verbose_name = 'Job Workflow Audit Log'
        verbose_name_plural = 'Job Workflow Audit Logs'

    def __str__(self):
        return f"{self.operation_type}: {self.jobneed_id} at {self.change_timestamp}"