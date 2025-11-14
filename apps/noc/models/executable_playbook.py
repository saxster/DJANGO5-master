"""
Executable Playbook Model.

Automated remediation playbooks for SOAR-lite incident response.
Converts manual runbooks to automated workflows with action sequencing.

Industry benchmark: 62% auto-resolution rate.

Follows .claude/rules.md Rule #7 (models <150 lines).

@ontology(
    domain="noc",
    purpose="Automated remediation playbooks with executable action sequences",
    business_value="60%+ auto-resolution rate without human intervention",
    industry_benchmark="62% auto-resolution (Splunk, IBM QRadar)",
    criticality="high",
    tags=["noc", "soar", "automation", "playbook", "remediation"]
)
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.core.models import BaseModel

__all__ = ['ExecutablePlaybook']


class ExecutablePlaybook(BaseModel, TenantAwareModel):
    """
    Automated remediation playbook with executable action sequences.

    Playbooks define automated response workflows that can be triggered
    when specific findings occur. Each playbook contains an ordered sequence
    of actions with timeout and error handling configurations.

    Action Types Supported:
    - send_notification: Email/Slack/Teams notification
    - create_ticket: Auto-create helpdesk ticket
    - assign_resource: Auto-assign personnel
    - collect_diagnostics: Gather logs/metrics
    - wait_for_condition: Poll until condition met

    Example playbook actions:
    [
        {
            "type": "send_notification",
            "params": {"channel": "slack", "message": "Critical alert"},
            "timeout": 30,
            "critical": false
        },
        {
            "type": "create_ticket",
            "params": {"priority": "HIGH", "title": "Auto-created"},
            "timeout": 60,
            "critical": true
        }
    ]
    """

    playbook_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Human-readable playbook name"
    )

    description = models.TextField(
        help_text="Detailed description of playbook purpose and actions"
    )

    # Trigger conditions
    finding_types = models.JSONField(
        default=list,
        help_text="List of finding types that trigger this playbook (e.g., ['TOUR_OVERDUE', 'SILENT_SITE'])"
    )

    severity_threshold = models.CharField(
        max_length=20,
        choices=[
            ('CRITICAL', 'Critical'),
            ('HIGH', 'High'),
            ('MEDIUM', 'Medium'),
            ('LOW', 'Low'),
        ],
        default='MEDIUM',
        help_text="Minimum severity level to trigger playbook"
    )

    auto_execute = models.BooleanField(
        default=False,
        db_index=True,
        help_text="If True, playbook executes automatically. If False, requires manual approval."
    )

    # Playbook definition
    actions = models.JSONField(
        default=list,
        help_text="Ordered list of actions: [{type, params, timeout, critical}, ...]"
    )

    # Execution statistics
    total_executions = models.IntegerField(
        default=0,
        help_text="Total number of times playbook has been executed"
    )

    successful_executions = models.IntegerField(
        default=0,
        help_text="Number of successful executions (all actions passed)"
    )

    failed_executions = models.IntegerField(
        default=0,
        help_text="Number of failed executions"
    )

    avg_execution_time_seconds = models.FloatField(
        default=0.0,
        help_text="Average execution time in seconds"
    )

    success_rate = models.FloatField(
        default=0.0,
        help_text="Success rate (successful_executions / total_executions)"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="If False, playbook will not be triggered"
    )

    class Meta:
        db_table = 'noc_executable_playbook'
        verbose_name = _("Executable Playbook")
        verbose_name_plural = _("Executable Playbooks")
        indexes = [
            models.Index(fields=['tenant', 'auto_execute', 'is_active']),
            models.Index(fields=['tenant', 'is_active']),
        ]
        ordering = ['-cdtz']

    def __str__(self) -> str:
        auto_flag = " [AUTO]" if self.auto_execute else ""
        return f"{self.name}{auto_flag} ({self.success_rate:.0%} success)"

    def update_stats(self, execution_duration_seconds: float, success: bool):
        """
        Update playbook execution statistics.

        Args:
            execution_duration_seconds: Duration of execution
            success: Whether execution was successful
        """
        self.total_executions += 1

        if success:
            self.successful_executions += 1

        # Update average execution time (rolling average)
        if self.total_executions == 1:
            self.avg_execution_time_seconds = execution_duration_seconds
        else:
            # Weighted average: (old_avg * (n-1) + new_value) / n
            self.avg_execution_time_seconds = (
                (self.avg_execution_time_seconds * (self.total_executions - 1) + execution_duration_seconds)
                / self.total_executions
            )

        # Update success rate
        self.success_rate = self.successful_executions / self.total_executions

        self.save(update_fields=[
            'total_executions',
            'successful_executions',
            'avg_execution_time_seconds',
            'success_rate'
        ])
