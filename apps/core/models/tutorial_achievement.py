"""
Tutorial Achievement Models

Gamification system for tutorial completion.

Following .claude/rules.md:
- Rule #18: Model classes <150 lines
- Rule #25: DateTime fields use timezone.now
"""

from django.db import models
from django.utils import timezone
from apps.core.models.enhanced_base_model import EnhancedBaseModel


class UserAchievement(EnhancedBaseModel):
    """Track user achievements and badges"""
    
    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='achievements'
    )
    achievement_id = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    description = models.TextField()
    earned_at = models.DateTimeField(default=timezone.now)
    points = models.IntegerField(default=0)
    badge_icon = models.CharField(max_length=10, default='🏆')
    
    class Meta:
        db_table = 'user_achievements'
        verbose_name = 'User Achievement'
        verbose_name_plural = 'User Achievements'
        unique_together = [('user', 'achievement_id')]
        ordering = ['-earned_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['achievement_id']),
            models.Index(fields=['earned_at'])
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


class TutorialCertificate(EnhancedBaseModel):
    """Tutorial completion certificates"""
    
    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='tutorial_certificates'
    )
    tutorial_id = models.CharField(max_length=100)
    certificate_id = models.CharField(max_length=200, unique=True)
    issued_at = models.DateTimeField(default=timezone.now)
    time_completed_seconds = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'tutorial_certificates'
        verbose_name = 'Tutorial Certificate'
        verbose_name_plural = 'Tutorial Certificates'
        ordering = ['-issued_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['tutorial_id']),
            models.Index(fields=['certificate_id'])
        ]
    
    def __str__(self):
        return f"Certificate: {self.user.username} - {self.tutorial_id}"
    
    @property
    def certificate_url(self):
        """Get shareable certificate URL"""
        return f"/admin/tutorials/certificate/{self.certificate_id}/"
