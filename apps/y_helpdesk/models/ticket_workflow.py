"""
Ticket Workflow Model - Extracted workflow concerns from main Ticket model

Handles workflow-specific data and state management, reducing the complexity
of the main Ticket model and enabling optimized queries.

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Model classes <150 lines
- Rule #12: Database query optimization
"""

from django.db import models
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from apps.peoples.models import BaseModel, TenantAwareModel
import logging

logger = logging.getLogger(__name__)


def workflow_defaults():
    """Default workflow data structure."""
    return {
        "workflow_history": [],
        "escalation_attempts": [],
        "assignment_history": [],
        "status_transitions": []
    }


class TicketWorkflow(BaseModel, TenantAwareModel):
    """
    Workflow and state management for tickets.

    Extracted from main Ticket model to:
    - Reduce core model complexity
    - Enable optimized queries (join only when workflow data needed)
    - Improve race condition handling
    - Separate workflow concerns from core ticket data
    """

    class WorkflowStatus(models.TextChoices):
        ACTIVE = ("ACTIVE", "Active")
        PAUSED = ("PAUSED", "Paused")
        COMPLETED = ("COMPLETED", "Completed")
        CANCELLED = ("CANCELLED", "Cancelled")

    # Core workflow relationship
    ticket = models.OneToOneField(
        'y_helpdesk.Ticket',
        on_delete=models.CASCADE,
        related_name='workflow',
        help_text='Related ticket for this workflow'
    )

    # Escalation tracking
    escalation_level = models.IntegerField(
        default=0,
        help_text='Current escalation level'
    )
    is_escalated = models.BooleanField(
        default=False,
        help_text='Whether ticket has been escalated'
    )
    escalation_count = models.IntegerField(
        default=0,
        help_text='Total number of escalations'
    )
    last_escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When ticket was last escalated'
    )

    # Workflow state
    workflow_status = models.CharField(
        max_length=20,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.ACTIVE,
        help_text='Current workflow status'
    )
    workflow_started_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When workflow was initiated'
    )
    workflow_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When workflow was completed'
    )

    # Activity tracking
    last_activity_at = models.DateTimeField(
        auto_now=True,
        help_text='Last activity timestamp'
    )
    activity_count = models.IntegerField(
        default=0,
        help_text='Total number of activities'
    )

    # Workflow data storage
    workflow_data = models.JSONField(
        default=workflow_defaults,
        encoder=DjangoJSONEncoder,
        help_text='Workflow history and metadata'
    )

    # Performance tracking
    response_time_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Time to first response in hours'
    )
    resolution_time_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Time to resolution in hours'
    )

    class Meta(BaseModel.Meta):
        db_table = "ticket_workflow"
        indexes = [
            models.Index(fields=['escalation_level', 'is_escalated']),
            models.Index(fields=['workflow_status', 'last_activity_at']),
            models.Index(fields=['ticket', 'escalation_level']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(escalation_level__gte=0),
                name="escalation_level_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(escalation_count__gte=0),
                name="escalation_count_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(activity_count__gte=0),
                name="activity_count_non_negative"
            ),
        ]

    def __str__(self):
        return f"Workflow for Ticket #{self.ticket.ticketno if self.ticket else 'Unknown'}"

    def add_workflow_entry(self, action: str, details: dict, user=None):
        """
        Add entry to workflow history.

        Args:
            action: Action performed (e.g., 'escalated', 'assigned', 'commented')
            details: Action details
            user: User who performed the action
        """
        if not self.workflow_data:
            self.workflow_data = workflow_defaults()

        entry = {
            'timestamp': timezone.now().isoformat(),
            'action': action,
            'details': details,
            'user_id': user.id if user else None,
            'user_name': user.peoplename if user and hasattr(user, 'peoplename') else None
        }

        self.workflow_data['workflow_history'].append(entry)
        self.activity_count = models.F('activity_count') + 1
        self.last_activity_at = timezone.now()

        logger.info(
            f"Workflow entry added for ticket {self.ticket_id}: {action}",
            extra={
                'ticket_id': self.ticket_id,
                'action': action,
                'user_id': user.id if user else None,
                'workflow_id': self.id
            }
        )

    def escalate(self, assigned_to=None, escalation_reason=None, user=None):
        """
        Escalate the ticket workflow.

        Args:
            assigned_to: New assignee after escalation
            escalation_reason: Reason for escalation
            user: User performing escalation
        """
        from django.db import transaction

        with transaction.atomic():
            # Increment escalation level atomically
            self.__class__.objects.filter(pk=self.pk).update(
                escalation_level=models.F('escalation_level') + 1,
                escalation_count=models.F('escalation_count') + 1,
                is_escalated=True,
                last_escalated_at=timezone.now(),
                last_activity_at=timezone.now()
            )

            # Refresh from database
            self.refresh_from_db()

            # Add escalation entry to workflow history
            escalation_details = {
                'previous_level': self.escalation_level - 1,
                'new_level': self.escalation_level,
                'reason': escalation_reason,
                'assigned_to': assigned_to
            }

            self.add_workflow_entry('escalated', escalation_details, user)
            self.save(update_fields=['workflow_data', 'activity_count'])

            logger.warning(
                f"Ticket {self.ticket_id} escalated to level {self.escalation_level}",
                extra={
                    'ticket_id': self.ticket_id,
                    'escalation_level': self.escalation_level,
                    'reason': escalation_reason,
                    'user_id': user.id if user else None
                }
            )

    def complete_workflow(self, completion_reason=None, user=None):
        """
        Mark workflow as completed.

        Args:
            completion_reason: Reason for completion
            user: User completing the workflow
        """
        self.workflow_status = self.WorkflowStatus.COMPLETED
        self.workflow_completed_at = timezone.now()
        self.last_activity_at = timezone.now()

        # Calculate resolution time if workflow is being completed
        if self.workflow_started_at:
            duration = timezone.now() - self.workflow_started_at
            self.resolution_time_hours = duration.total_seconds() / 3600

        completion_details = {
            'reason': completion_reason,
            'resolution_time_hours': float(self.resolution_time_hours) if self.resolution_time_hours else None
        }

        self.add_workflow_entry('completed', completion_details, user)
        self.save()

    def get_workflow_summary(self) -> dict:
        """
        Get summary of workflow state and metrics.

        Returns:
            Dictionary with workflow summary
        """
        return {
            'escalation_level': self.escalation_level,
            'escalation_count': self.escalation_count,
            'is_escalated': self.is_escalated,
            'workflow_status': self.workflow_status,
            'activity_count': self.activity_count,
            'response_time_hours': float(self.response_time_hours) if self.response_time_hours else None,
            'resolution_time_hours': float(self.resolution_time_hours) if self.resolution_time_hours else None,
            'last_activity': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'workflow_duration_hours': (
                (timezone.now() - self.workflow_started_at).total_seconds() / 3600
                if self.workflow_started_at else None
            )
        }