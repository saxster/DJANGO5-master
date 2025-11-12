"""
Quick Action Models - User-Friendly Runbooks/Playbooks

One-click responses to common situations with automated and manual steps.

Author: Claude Code
Date: 2025-11-07
CLAUDE.md Compliance: <150 lines per model
"""

from django.db import models
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from apps.core.models.enhanced_base_model import TimestampMixin, TenantAwareModel


class QuickAction(TimestampMixin, TenantAwareModel):
    """
    Quick Action - One-click response to common situations.
    
    User-friendly runbook that executes automated steps and guides
    users through manual steps with checklists.
    """
    
    # What is this action?
    name = models.CharField(
        max_length=200,
        help_text=_("Action verb name (e.g., 'Fix Camera Offline')")
    )
    description = models.TextField(
        help_text=_("What this action does in plain English")
    )
    when_to_use = models.TextField(
        help_text=_("When should someone use this action?")
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Is this action available to use?")
    )
    
    # Who can use it?
    available_for_types = models.JSONField(
        default=list,
        help_text=_("ContentType IDs this action applies to (e.g., [ticket, incident])")
    )
    user_groups = models.ManyToManyField(
        Group,
        blank=True,
        help_text=_("Which user groups can execute this action?")
    )
    
    # What happens automatically?
    automated_steps = models.JSONField(
        default=list,
        help_text=_(
            "Steps that run automatically. Format: "
            "[{'action_label': 'Ping camera', 'action_type': 'ping_device', 'params': {...}}]"
        )
    )
    
    # What do users need to do?
    manual_steps = models.JSONField(
        default=list,
        help_text=_(
            "Steps users complete manually. Format: "
            "[{'instruction': 'Check power LED', 'needs_photo': true, 'needs_note': false}]"
        )
    )
    
    # Analytics
    times_used = models.IntegerField(
        default=0,
        help_text=_("How many times this action has been executed")
    )
    average_completion_time = models.DurationField(
        null=True,
        blank=True,
        help_text=_("Average time to complete all steps")
    )
    success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_("Percentage of successful executions")
    )
    
    class Meta:
        verbose_name = _("Quick Action")
        verbose_name_plural = _("Quick Actions")
        ordering = ['-times_used', 'name']
        indexes = [
            models.Index(fields=['is_active', '-times_used']),
        ]
    
    def __str__(self):
        return f"⚡ {self.name}"
    
    @property
    def steps_count(self):
        """Total number of steps (automated + manual)."""
        return len(self.automated_steps) + len(self.manual_steps)
    
    def can_user_execute(self, user):
        """Check if user has permission to execute this action."""
        if not self.is_active:
            return False
        
        # If no groups specified, available to all
        if not self.user_groups.exists():
            return True
        
        # Check if user is in any of the allowed groups
        return self.user_groups.filter(id__in=user.groups.all()).exists()
    
    def clean(self):
        """Validate automated and manual steps structure."""
        # Validate automated_steps format
        if not isinstance(self.automated_steps, list):
            raise ValidationError({'automated_steps': 'Must be a list'})
        
        for step in self.automated_steps:
            if not isinstance(step, dict):
                raise ValidationError({'automated_steps': 'Each step must be a dictionary'})
            if 'action_label' not in step or 'action_type' not in step:
                raise ValidationError({
                    'automated_steps': 'Each step must have action_label and action_type'
                })
        
        # Validate manual_steps format
        if not isinstance(self.manual_steps, list):
            raise ValidationError({'manual_steps': 'Must be a list'})
        
        for step in self.manual_steps:
            if not isinstance(step, dict):
                raise ValidationError({'manual_steps': 'Each step must be a dictionary'})
            if 'instruction' not in step:
                raise ValidationError({'manual_steps': 'Each step must have instruction'})


class QuickActionExecution(TimestampMixin, TenantAwareModel):
    """
    Record of a Quick Action execution.
    
    Tracks what happened when a user executed a quick action,
    including automated step results and manual step completion.
    """
    
    quick_action = models.ForeignKey(
        QuickAction,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    # What item was this action performed on?
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Who executed it?
    executed_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        related_name='quick_action_executions'
    )
    
    # Results
    automated_results = models.JSONField(
        default=list,
        help_text=_("Results of automated steps")
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Waiting for manual steps'),
            ('in_progress', 'User completing steps'),
            ('completed', 'All done ✓'),
            ('failed', 'Something went wrong'),
            ('cancelled', 'User cancelled')
        ],
        default='pending'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Performance tracking
    execution_duration = models.DurationField(
        null=True,
        blank=True,
        help_text=_("How long total execution took")
    )
    
    class Meta:
        verbose_name = _("Quick Action Execution")
        verbose_name_plural = _("Quick Action Executions")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['executed_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.quick_action.name} - {self.status}"


class QuickActionChecklist(TimestampMixin, TenantAwareModel):
    """
    Manual step checklist for a Quick Action execution.
    
    Tracks user progress through manual steps with photos and notes.
    """
    
    execution = models.OneToOneField(
        QuickActionExecution,
        on_delete=models.CASCADE,
        related_name='checklist'
    )
    
    steps = models.JSONField(
        default=list,
        help_text=_(
            "Checklist items. Format: "
            "[{'instruction': '...', 'completed': true, 'photo_url': '...', 'note': '...'}]"
        )
    )
    
    completion_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_("Percentage of steps completed")
    )
    
    class Meta:
        verbose_name = _("Quick Action Checklist")
        verbose_name_plural = _("Quick Action Checklists")
    
    def __str__(self):
        return f"Checklist for {self.execution}"
    
    def update_completion(self):
        """Recalculate completion percentage."""
        if not self.steps:
            self.completion_percentage = 0
            return
        
        completed = sum(1 for step in self.steps if step.get('completed', False))
        total = len(self.steps)
        self.completion_percentage = (completed / total) * 100 if total > 0 else 0
        self.save(update_fields=['completion_percentage', 'updated_at'])
