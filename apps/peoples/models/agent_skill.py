"""
Agent Skill Model - Track agent skills for smart assignment.

Following CLAUDE.md:
- Models < 150 lines
- TenantAwareModel for multi-tenancy
- Specific exception handling
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.peoples.models.base_model import BaseModel
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager


class AgentSkill(BaseModel, TenantAwareModel):
    """
    Track what each person is good at for intelligent task routing.
    
    Automatically updated based on task completion history.
    Used by SmartAssignmentService to suggest best assignees.
    
    Fields:
        agent: Person who has this skill
        category: Type of task (TypeAssist)
        skill_level: 1-4 star rating
        certified: Official training completed
        last_used: Last time worked on this type
        total_handled: Count of completed tasks
        avg_completion_time: Average resolution time
        success_rate: First-time resolution percentage
    """
    
    SKILL_LEVELS = [
        (1, '⭐ Learning (can handle basic tasks)'),
        (2, '⭐⭐ Good (can work independently)'),
        (3, '⭐⭐⭐ Expert (go-to person)'),
        (4, '⭐⭐⭐⭐ Master (can train others)'),
    ]
    
    objects = TenantAwareManager()
    
    agent = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='skills',
        help_text=_("Who has this skill")
    )
    
    category = models.ForeignKey(
        'core_onboarding.TypeAssist',
        on_delete=models.CASCADE,
        help_text=_("What type of task")
    )
    
    skill_level = models.IntegerField(
        choices=SKILL_LEVELS,
        default=2,
        help_text=_("How skilled are they?")
    )
    
    certified = models.BooleanField(
        default=False,
        help_text=_("Have they completed official training?")
    )
    
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Last time they worked on this type of task")
    )
    
    total_handled = models.IntegerField(
        default=0,
        help_text=_("Total tasks of this type they've completed")
    )
    
    avg_completion_time = models.DurationField(
        null=True,
        blank=True,
        help_text=_("Average time to complete this type of task")
    )
    
    success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("% of tasks completed successfully first time")
    )
    
    class Meta:
        unique_together = ['agent', 'category', 'tenant']
        verbose_name = _("Agent Skill")
        verbose_name_plural = _("Agent Skills")
        indexes = [
            models.Index(fields=['agent', 'category']),
            models.Index(fields=['skill_level']),
            models.Index(fields=['certified']),
        ]
    
    def __str__(self):
        stars = '⭐' * self.skill_level
        category_name = self.category.taname if hasattr(self.category, 'taname') else str(self.category)
        return f"{self.agent.get_full_name()} - {category_name} {stars}"
    
    def get_skill_display(self):
        """Human-readable skill level with stars."""
        return '⭐' * self.skill_level
