"""
Coaching Session Model

Track 1:1 coaching sessions and action items.

Compliance:
- Rule #6: Model < 150 lines
"""

from django.db import models
from apps.core.models import TenantAwareModel, BaseModel


class CoachingSession(TenantAwareModel, BaseModel):
    """
    1:1 coaching sessions between supervisor and worker.
    
    Used to:
    - Track coaching interventions
    - Monitor action item completion
    - Measure coaching effectiveness
    - Document performance discussions
    """
    
    worker = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='coaching_sessions_received',
        help_text="Worker being coached"
    )
    coach = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='coaching_sessions_given',
        help_text="Supervisor conducting session"
    )
    
    # Session Details
    session_date = models.DateTimeField(
        db_index=True,
        help_text="When coaching session occurred"
    )
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Session duration"
    )
    session_type = models.CharField(
        max_length=30,
        choices=[
            ('routine', 'Routine Check-in'),
            ('performance_improvement', 'Performance Improvement'),
            ('goal_setting', 'Goal Setting'),
            ('recognition', 'Recognition & Praise'),
            ('corrective', 'Corrective Action'),
        ],
        default='routine'
    )
    
    # Focus Areas (JSON array)
    focus_areas = models.JSONField(
        default=list,
        help_text="Areas discussed (e.g., ['documentation', 'task_sla', 'attendance'])"
    )
    
    # Action Items (JSON array of objects)
    action_items = models.JSONField(
        default=list,
        help_text="Action items with due dates and completion status"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Coaching session notes (supervisor only)"
    )
    worker_feedback = models.TextField(
        blank=True,
        help_text="Worker's feedback on session"
    )
    
    # Follow-up
    follow_up_date = models.DateField(
        null=True,
        blank=True,
        help_text="Scheduled follow-up date"
    )
    follow_up_completed = models.BooleanField(
        default=False,
        help_text="Whether follow-up occurred"
    )
    
    # Outcomes
    improvement_observed = models.BooleanField(
        null=True,
        blank=True,
        help_text="Was improvement observed in next 2 weeks?"
    )
    effectiveness_rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[
            (1, 'Not Effective'),
            (2, 'Somewhat Effective'),
            (3, 'Moderately Effective'),
            (4, 'Very Effective'),
            (5, 'Extremely Effective'),
        ],
        help_text="Coach's rating of session effectiveness"
    )
    
    class Meta:
        db_table = 'perf_coaching_sessions'
        verbose_name = 'Coaching Session'
        verbose_name_plural = 'Coaching Sessions'
        indexes = [
            models.Index(fields=['tenant', 'worker', 'session_date']),
            models.Index(fields=['tenant', 'coach', 'session_date']),
            models.Index(fields=['tenant', 'session_type']),
            models.Index(fields=['tenant', 'follow_up_date']),
        ]
        ordering = ['-session_date']
    
    def __str__(self):
        return f"{self.coach.loginid} → {self.worker.loginid} on {self.session_date.strftime('%Y-%m-%d')}"
    
    def get_action_items_completion_rate(self):
        """Calculate percentage of action items completed."""
        if not self.action_items:
            return 0
        
        completed = sum(1 for item in self.action_items if item.get('completed', False))
        total = len(self.action_items)
        
        return round((completed / total) * 100, 1) if total > 0 else 0
