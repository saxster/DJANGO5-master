"""
Admin Help Topic Model - AI-Powered Admin Help System

Provides intelligent, contextual help for Django admin features using friendly,
user-focused language instead of technical jargon.

Following .claude/rules.md:
- Rule #7: Model classes <150 lines (single responsibility)
- Rule #11: Specific exception handling
- Rule #12: Comprehensive database query optimization
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.utils.translation import gettext_lazy as _
from django.core.validators import URLValidator
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager
from apps.core.models.enhanced_base_model import TimestampMixin


class AdminHelpTopic(TenantAwareModel, TimestampMixin):
    """
    AI-powered help topics for Django admin features.
    
    Uses friendly, user-focused language to explain complex admin features
    in simple terms that non-technical users can understand.
    
    Examples:
        - "Quick Actions" instead of "Playbooks"
        - "My Saved Views" instead of "Admin Views"
        - "Priority Alerts" instead of "SLA Breach Predictor"
    """
    
    CATEGORY_CHOICES = [
        ('command_center', _('Command Center')),
        ('workflows', _('Workflows & Automation')),
        ('approvals', _('Approvals & Requests')),
        ('views', _('Views & Filters')),
        ('reports', _('Reports & Analytics')),
        ('notifications', _('Notifications & Alerts')),
        ('scheduling', _('Scheduling & Calendar')),
        ('team', _('Team & Collaboration')),
        ('settings', _('Settings & Configuration')),
    ]
    
    DIFFICULTY_CHOICES = [
        ('beginner', _('Beginner - Easy to learn')),
        ('intermediate', _('Intermediate - Some experience needed')),
        ('advanced', _('Advanced - For power users')),
    ]
    
    objects = TenantAwareManager()
    
    # Core fields
    category = models.CharField(
        _("Category"),
        max_length=50,
        choices=CATEGORY_CHOICES,
        db_index=True,
        help_text=_("Which area of the admin this feature belongs to")
    )
    
    feature_name = models.CharField(
        _("Feature Name"),
        max_length=200,
        help_text=_("User-friendly name (e.g., 'One-Click Actions' not 'Playbooks')")
    )
    
    short_description = models.TextField(
        _("Short Description"),
        max_length=500,
        help_text=_("1-2 sentence summary in plain English")
    )
    
    detailed_explanation = models.TextField(
        _("Detailed Explanation"),
        help_text=_("Full explanation without jargon - write like explaining to a friend")
    )
    
    # Use cases as JSON array
    use_cases = ArrayField(
        models.TextField(),
        verbose_name=_("Use Cases"),
        help_text=_("Real-world examples of when to use this feature"),
        default=list,
        blank=True
    )
    
    # Advantages as JSON array
    advantages = ArrayField(
        models.TextField(),
        verbose_name=_("Advantages"),
        help_text=_("Benefits and advantages of using this feature"),
        default=list,
        blank=True
    )
    
    how_to_use = models.TextField(
        _("How to Use"),
        help_text=_("Step-by-step instructions in simple language"),
        blank=True
    )
    
    video_url = models.URLField(
        _("Video Tutorial URL"),
        blank=True,
        validators=[URLValidator()],
        help_text=_("Optional link to video tutorial")
    )
    
    # Search and discovery
    keywords = ArrayField(
        models.CharField(max_length=100),
        verbose_name=_("Keywords"),
        help_text=_("Search keywords and alternative terms"),
        default=list,
        blank=True
    )
    
    difficulty_level = models.CharField(
        _("Difficulty Level"),
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner',
        db_index=True
    )
    
    # Analytics
    view_count = models.PositiveIntegerField(
        _("View Count"),
        default=0,
        help_text=_("How many times this help topic has been viewed")
    )
    
    helpful_count = models.PositiveIntegerField(
        _("Helpful Count"),
        default=0,
        help_text=_("How many users found this helpful")
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        db_index=True,
        help_text=_("Whether this help topic is currently shown to users")
    )
    
    # Full-text search
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = _("Admin Help Topic")
        verbose_name_plural = _("Admin Help Topics")
        ordering = ['-view_count', 'category', 'feature_name']
        indexes = [
            models.Index(fields=['category', 'difficulty_level']),
            models.Index(fields=['is_active', '-view_count']),
        ]
        unique_together = [('tenant', 'category', 'feature_name')]

    def __str__(self):
        return f"{self.get_category_display()}: {self.feature_name}"

    def increment_view_count(self):
        """Increment the view counter atomically."""
        self.__class__.objects.filter(pk=self.pk).update(
            view_count=models.F('view_count') + 1
        )

    def mark_as_helpful(self):
        """Mark this help topic as helpful (user feedback)."""
        self.__class__.objects.filter(pk=self.pk).update(
            helpful_count=models.F('helpful_count') + 1
        )
    
    def save(self, *args, **kwargs):
        """Override save to update search vector."""
        super().save(*args, **kwargs)
        
        # Update search vector
        if self.pk:
            self.__class__.objects.filter(pk=self.pk).update(
                search_vector=(
                    SearchVector('feature_name', weight='A') +
                    SearchVector('short_description', weight='B') +
                    SearchVector('detailed_explanation', weight='C') +
                    SearchVector('keywords', weight='B')
                )
            )
