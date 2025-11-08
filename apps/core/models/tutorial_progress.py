"""
Tutorial Progress Tracking Models

Tracks user progress through interactive tutorials.

Following .claude/rules.md:
- Rule #18: Model classes <150 lines
- Rule #25: DateTime fields use timezone.now
"""

from django.db import models
from django.utils import timezone
from apps.core.models.enhanced_base_model import EnhancedBaseModel


class TutorialProgress(EnhancedBaseModel):
    """Track user progress through tutorials"""
    
    STATUS_CHOICES = [
        ('STARTED', 'Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('SKIPPED', 'Skipped')
    ]
    
    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='tutorial_progress'
    )
    tutorial_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='STARTED'
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    steps_completed = models.JSONField(default=list)
    time_spent_seconds = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'tutorial_progress'
        verbose_name = 'Tutorial Progress'
        verbose_name_plural = 'Tutorial Progress'
        unique_together = [('user', 'tutorial_id')]
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['tutorial_id']),
            models.Index(fields=['completed_at'])
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.tutorial_id} ({self.status})"
    
    @property
    def completion_time_display(self):
        """Human-readable completion time"""
        if self.time_spent_seconds < 60:
            return f"{self.time_spent_seconds}s"
        minutes = self.time_spent_seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m"
    
    @property
    def progress_percent(self):
        """Calculate progress percentage"""
        from apps.core.tutorials.content import TUTORIALS
        
        if self.tutorial_id not in TUTORIALS:
            return 0
        
        total_steps = len(TUTORIALS[self.tutorial_id]['steps'])
        completed_steps = len(self.steps_completed or [])
        
        if total_steps == 0:
            return 100
        
        return int((completed_steps / total_steps) * 100)
