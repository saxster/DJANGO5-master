"""
AI Mentor Model - Intelligent Admin Guidance System

Tracks AI mentor interactions with administrators to provide contextual,
personalized guidance and measure efficiency improvements.

Following .claude/rules.md:
- Rule #7: Model classes <150 lines (single responsibility)
- Rule #11: Specific exception handling
- Rule #12: Comprehensive database query optimization
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager
from apps.core.models.enhanced_base_model import TimestampMixin


class AdminMentorSession(TenantAwareModel, TimestampMixin):
    """
    Track AI mentor interactions with administrators.
    
    Records session data to enable:
    - Personalized suggestions based on behavior
    - Skill level assessment
    - Efficiency analytics
    - Feature adoption tracking
    """
    
    objects = TenantAwareManager()
    
    SKILL_LEVEL_CHOICES = [
        ('NOVICE', _('New to admin panel')),
        ('INTERMEDIATE', _('Knows basics')),
        ('ADVANCED', _('Power user')),
        ('EXPERT', _('Knows everything')),
    ]
    
    admin_user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='mentor_sessions',
        help_text=_("Administrator being mentored")
    )
    
    # Session tracking
    session_start = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When session started")
    )
    session_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When session ended")
    )
    page_context = models.CharField(
        max_length=500,
        help_text=_("Current admin page URL")
    )
    
    # Learning tracking
    features_used = models.JSONField(
        default=list,
        help_text=_("List of features admin has used")
    )
    features_shown = models.JSONField(
        default=list,
        help_text=_("List of features shown to admin")
    )
    skill_level = models.CharField(
        max_length=20,
        choices=SKILL_LEVEL_CHOICES,
        default='INTERMEDIATE',
        help_text=_("Estimated skill level")
    )
    
    # Interaction history
    questions_asked = models.JSONField(
        default=list,
        help_text=_("Questions admin asked the mentor")
    )
    suggestions_shown = models.JSONField(
        default=list,
        help_text=_("Suggestions displayed to admin")
    )
    suggestions_followed = models.JSONField(
        default=list,
        help_text=_("Suggestions admin acted upon")
    )
    
    # Efficiency metrics
    time_saved_estimate = models.IntegerField(
        default=0,
        help_text=_("Estimated time saved in seconds")
    )
    tasks_completed = models.IntegerField(
        default=0,
        help_text=_("Number of tasks completed")
    )
    shortcuts_used = models.IntegerField(
        default=0,
        help_text=_("Number of keyboard shortcuts used")
    )
    
    class Meta:
        verbose_name = _("Admin Mentor Session")
        verbose_name_plural = _("Admin Mentor Sessions")
        ordering = ['-session_start']
        indexes = [
            models.Index(fields=['admin_user', '-session_start']),
            models.Index(fields=['skill_level']),
        ]
    
    def __str__(self):
        return f"Mentor session for {self.admin_user.username} at {self.session_start}"


class AdminMentorTip(TenantAwareModel, TimestampMixin):
    """
    Contextual tips the AI mentor can show.
    
    Tips are triggered based on:
    - Page context (what admin is viewing)
    - Conditions (system state)
    - User skill level
    - Display frequency rules
    """
    
    objects = TenantAwareManager()
    
    TIP_TYPE_CHOICES = [
        ('SHORTCUT', _('Keyboard shortcut')),
        ('FEATURE', _('Feature suggestion')),
        ('BEST_PRACTICE', _('Best practice')),
        ('TIME_SAVER', _('Time-saving tip')),
        ('WARNING', _('Important warning')),
    ]
    
    FREQUENCY_CHOICES = [
        ('ONCE', _('Show only once')),
        ('DAILY', _('Once per day')),
        ('WEEKLY', _('Once per week')),
        ('ALWAYS', _('Every time condition met')),
    ]
    
    trigger_context = models.CharField(
        max_length=100,
        help_text=_("When to show this tip (e.g., 'viewing_ticket_list')")
    )
    
    condition = models.JSONField(
        default=dict,
        help_text=_("Conditions to show tip: {'tickets_open': '> 10'}")
    )
    
    tip_title = models.CharField(
        max_length=200,
        help_text=_("Catchy title for the tip")
    )
    
    tip_content = models.TextField(
        help_text=_("The actual tip in friendly language")
    )
    
    tip_type = models.CharField(
        max_length=20,
        choices=TIP_TYPE_CHOICES,
        default='FEATURE'
    )
    
    action_button_text = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Call to action: 'Try it now', 'Learn more'")
    )
    
    action_url = models.CharField(
        max_length=500,
        blank=True,
        help_text=_("URL to navigate when action clicked")
    )
    
    priority = models.IntegerField(
        default=5,
        help_text=_("Priority 1-10, higher shows first")
    )
    
    show_frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='ONCE'
    )
    
    active = models.BooleanField(
        default=True,
        help_text=_("Whether this tip is currently active")
    )
    
    class Meta:
        verbose_name = _("Admin Mentor Tip")
        verbose_name_plural = _("Admin Mentor Tips")
        ordering = ['-priority', 'tip_title']
        indexes = [
            models.Index(fields=['trigger_context', 'active']),
            models.Index(fields=['-priority']),
        ]
    
    def __str__(self):
        return f"{self.tip_title} ({self.trigger_context})"
