"""
Playbook Execution Model.

Tracks individual playbook execution runs with action results and approval workflow.

Follows .claude/rules.md Rule #7 (models <150 lines).

@ontology(
    domain="noc",
    purpose="Track playbook execution runs with action-level results",
    business_value="Audit trail and metrics for automated remediation",
    criticality="high",
    tags=["noc", "soar", "automation", "execution-tracking", "audit"]
)
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['PlaybookExecution']


class PlaybookExecution(BaseModel, TenantAwareModel):
    """
    Tracks individual playbook execution run.

    Each execution represents one attempt to run a playbook in response to
    a finding. Stores detailed action-level results, timing metrics, and
    approval workflow information.

    Status Flow:
    PENDING → RUNNING → SUCCESS/PARTIAL/FAILED
              ↓
           CANCELLED (if manually stopped)
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending - Awaiting approval'),
        ('RUNNING', 'Running - Execution in progress'),
        ('SUCCESS', 'Success - All actions completed'),
        ('PARTIAL', 'Partial Success - Some actions failed'),
        ('FAILED', 'Failed - Execution failed'),
        ('CANCELLED', 'Cancelled - Manually stopped'),
    ]

    execution_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    playbook = models.ForeignKey(
        'noc.ExecutablePlaybook',
        on_delete=models.CASCADE,
        related_name='executions',
        help_text="Playbook being executed"
    )

    finding = models.ForeignKey(
        'noc_security_intelligence.AuditFinding',
        on_delete=models.CASCADE,
        related_name='playbook_executions',
        help_text="Finding that triggered this execution"
    )

    # Execution state
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Current execution status"
    )

    # Action results (list of dicts)
    action_results = models.JSONField(
        default=list,
        help_text="Results for each action: [{action, status, output, duration, error}, ...]"
    )

    # Timing metrics
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When execution started"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution completed"
    )

    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Total execution duration in seconds"
    )

    # Approval workflow
    requires_approval = models.BooleanField(
        default=False,
        help_text="Whether this execution requires manual approval"
    )

    approved_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_playbook_executions',
        help_text="User who approved execution"
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution was approved"
    )

    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error message if execution failed"
    )

    # Execution metadata
    execution_context = models.JSONField(
        default=dict,
        help_text="Additional context about execution environment"
    )

    class Meta:
        db_table = 'noc_playbook_execution'
        verbose_name = _("Playbook Execution")
        verbose_name_plural = _("Playbook Executions")
        indexes = [
            models.Index(fields=['tenant', 'status', '-cdtz']),
            models.Index(fields=['playbook', '-cdtz']),
            models.Index(fields=['finding', '-cdtz']),
            models.Index(fields=['-started_at']),
        ]
        ordering = ['-cdtz']

    def __str__(self) -> str:
        return f"{self.playbook.name} → {self.status} (Finding: {self.finding.id})"

    def get_success_count(self) -> int:
        """Count successful actions."""
        return sum(1 for result in self.action_results if result.get('status') == 'success')

    def get_failed_count(self) -> int:
        """Count failed actions."""
        return sum(1 for result in self.action_results if result.get('status') == 'failed')

    def get_total_actions(self) -> int:
        """Get total number of actions."""
        return len(self.action_results)

    def is_complete(self) -> bool:
        """Check if execution is in terminal state."""
        return self.status in ['SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED']
