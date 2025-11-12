"""
Gamification Models

Achievement system, streaks, and kudos for positive reinforcement.

Compliance:
- Rule #6: Model < 150 lines each
"""

from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import TenantAwareModel, BaseModel


class PerformanceStreak(TenantAwareModel, BaseModel):
    """
    Track positive performance streaks.
    
    Types:
    - on_time: Consecutive on-time days
    - perfect_patrol: Consecutive 100% checkpoint coverage
    - sla_hit: Consecutive days with 100% SLA compliance
    - zero_ncns: Days without no-call-no-show
    """
    
    worker = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='performance_streaks'
    )
    streak_type = models.CharField(
        max_length=50,
        db_index=True,
        choices=[
            ('on_time', 'On-Time Streak'),
            ('perfect_patrol', 'Perfect Patrol Streak'),
            ('sla_hit', 'SLA Hit Streak'),
            ('zero_ncns', 'Zero NCNS Streak'),
            ('quality_excellence', 'Quality Excellence Streak'),
        ],
        help_text="Type of streak being tracked"
    )
    
    current_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current streak length (days)"
    )
    best_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Personal best streak (all-time)"
    )
    started_date = models.DateField(help_text="When current streak started")
    last_updated = models.DateField(help_text="Last date streak was verified")
    broken_date = models.DateField(null=True, blank=True, help_text="When last broken")
    
    class Meta:
        db_table = 'perf_streaks'
        verbose_name = 'Performance Streak'
        verbose_name_plural = 'Performance Streaks'
        unique_together = [['tenant', 'worker', 'streak_type']]
        indexes = [
            models.Index(fields=['tenant', 'worker', 'streak_type']),
            models.Index(fields=['tenant', 'current_count']),
        ]
    
    def __str__(self):
        return f"{self.worker.loginid} - {self.get_streak_type_display()}: {self.current_count} days"
    
    def increment(self):
        """Increment streak by one day."""
        self.current_count += 1
        if self.current_count > self.best_count:
            self.best_count = self.current_count
    
    def break_streak(self, broken_date):
        """Reset streak to zero."""
        self.current_count = 0
        self.broken_date = broken_date


class Kudos(TenantAwareModel, BaseModel):
    """
    Peer and supervisor recognition system.
    """
    
    recipient = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='kudos_received'
    )
    giver = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='kudos_given'
    )
    kudos_type = models.CharField(
        max_length=50,
        choices=[
            ('teamwork', 'Teamwork'),
            ('quality', 'Quality Work'),
            ('initiative', 'Initiative'),
            ('safety', 'Safety Awareness'),
            ('customer_service', 'Customer Service'),
            ('mentoring', 'Mentoring'),
            ('innovation', 'Innovation'),
        ],
        help_text="Category of recognition"
    )
    message = models.TextField(help_text="Recognition message")
    
    # Context
    related_task = models.ForeignKey(
        'activity.Job',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Related task if applicable"
    )
    related_tour = models.ForeignKey(
        'activity.Tour',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Related tour if applicable"
    )
    
    # Visibility
    visibility = models.CharField(
        max_length=20,
        default='team',
        choices=[
            ('private', 'Private (recipient only)'),
            ('team', 'Team (site level)'),
            ('company', 'Company-wide'),
        ],
        help_text="Who can see this kudos"
    )
    
    class Meta:
        db_table = 'perf_kudos'
        verbose_name = 'Kudos'
        verbose_name_plural = 'Kudos'
        indexes = [
            models.Index(fields=['tenant', 'recipient', 'created_at']),
            models.Index(fields=['tenant', 'giver']),
            models.Index(fields=['tenant', 'kudos_type']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.giver.loginid} → {self.recipient.loginid}: {self.get_kudos_type_display()}"


class Achievement(BaseModel):
    """
    Achievement definitions (tenant-agnostic templates).
    """
    
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Emoji or icon class")
    
    # Criteria (JSON)
    criteria = models.JSONField(
        help_text="Unlock criteria (e.g., {'on_time_rate': 100, 'days': 30})"
    )
    
    # Gamification
    points = models.IntegerField(default=10, help_text="Points awarded")
    rarity = models.CharField(
        max_length=20,
        choices=[
            ('common', 'Common'),
            ('uncommon', 'Uncommon'),
            ('rare', 'Rare'),
            ('epic', 'Epic'),
            ('legendary', 'Legendary'),
        ],
        default='common'
    )
    category = models.CharField(
        max_length=50,
        default='performance',
        help_text="Category (performance, attendance, quality, safety)"
    )
    
    class Meta:
        db_table = 'perf_achievements'
        verbose_name = 'Achievement'
        verbose_name_plural = 'Achievements'
        ordering = ['category', 'rarity', 'name']
    
    def __str__(self):
        return f"{self.icon} {self.name} ({self.rarity})"


class WorkerAchievement(TenantAwareModel, BaseModel):
    """
    Achievements earned by workers.
    """
    
    worker = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='achievements_earned'
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='earned_by_workers'
    )
    earned_date = models.DateField(db_index=True)
    count = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Times earned (for repeatable achievements)"
    )
    
    # Progress tracking
    progress_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Progress toward achievement (for tracking)"
    )
    
    class Meta:
        db_table = 'perf_worker_achievements'
        verbose_name = 'Worker Achievement'
        verbose_name_plural = 'Worker Achievements'
        unique_together = [['tenant', 'worker', 'achievement']]
        indexes = [
            models.Index(fields=['tenant', 'worker', 'earned_date']),
            models.Index(fields=['tenant', 'achievement']),
        ]
        ordering = ['-earned_date']
    
    def __str__(self):
        return f"{self.worker.loginid} earned {self.achievement.name} on {self.earned_date}"
