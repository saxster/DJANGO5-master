"""
Agent Recommendation Model

Stores AI-generated recommendations for dashboard agents.
Follows JSON schema template for Tasks, Tours, Alerts, Assets, Attendance, Routes.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Integration with existing multi-tenant architecture

Dashboard Agent Intelligence - Phase 1.1
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class AgentRecommendation(models.Model):
    """
    AI-generated recommendations from dashboard agents.

    Supports all dashboard modules:
    - Tasks (TaskBot)
    - Tours (TourBot)
    - Alerts (AlertBot)
    - Assets (AssetBot)
    - Attendance (AttendanceBot)
    """

    # Agent metadata
    agent_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Agent identifier (e.g., 'taskbot-001')"
    )
    agent_name = models.CharField(
        max_length=100,
        help_text="Human-readable agent name (e.g., 'TaskBot')"
    )

    # Context - Dashboard module and tenant
    module = models.CharField(
        max_length=50,
        db_index=True,
        choices=[
            ('tasks', 'Tasks'),
            ('tours', 'Tours'),
            ('alerts', 'Alerts'),
            ('assets', 'Assets'),
            ('attendance', 'Attendance'),
            ('routes', 'Routes'),
        ],
        help_text="Dashboard module this recommendation targets"
    )
    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='agent_recommendations',
        help_text="Site/business unit for this recommendation"
    )
    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='agent_recommendations_client',
        null=True,
        blank=True,
        help_text="Tenant client for multi-tenant isolation"
    )
    time_range_start = models.DateTimeField(
        help_text="Analysis period start"
    )
    time_range_end = models.DateTimeField(
        help_text="Analysis period end"
    )
    context_metrics = models.JSONField(
        default=dict,
        help_text="Module-specific metrics (flexible JSON structure)"
    )

    # Recommendation content
    summary = models.TextField(
        help_text="Human-readable summary of recommendation"
    )
    details = models.JSONField(
        default=list,
        help_text="Array of entity-specific details (tasks, tours, etc.)"
    )
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score (0.0-1.0)"
    )
    severity = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='medium',
        db_index=True,
        help_text="Severity/priority level"
    )

    # Actions - UI hooks for user interaction
    actions = models.JSONField(
        default=list,
        help_text="Array of actionable buttons: [{label, type, endpoint, payload, url}]"
    )

    # Lifecycle management
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending_review', 'Pending Review'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('auto_executed', 'Auto Executed'),
        ],
        default='pending_review',
        db_index=True,
        help_text="Recommendation lifecycle status"
    )
    human_feedback = models.TextField(
        null=True,
        blank=True,
        help_text="User feedback or notes"
    )
    dependencies = models.JSONField(
        default=list,
        help_text="Array of dependent recommendation IDs"
    )
    auto_executed = models.BooleanField(
        default=False,
        help_text="Whether action was auto-executed by agent"
    )

    # LLM provider tracking
    llm_provider = models.CharField(
        max_length=20,
        default='gemini',
        help_text="LLM provider used (gemini, anthropic, openai)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Recommendation expiration time"
    )

    class Meta:
        db_table = 'core_agent_recommendation'
        ordering = ['-created_at', '-severity', '-confidence']
        indexes = [
            models.Index(fields=['agent_id', 'module']),
            models.Index(fields=['site', 'status']),
            models.Index(fields=['client', 'module']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['created_at', 'expires_at']),
        ]
        verbose_name = 'Agent Recommendation'
        verbose_name_plural = 'Agent Recommendations'

    def __str__(self):
        return f"{self.agent_name} - {self.module} - {self.summary[:50]}"

    def is_expired(self):
        """Check if recommendation has expired"""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def is_actionable(self):
        """Check if recommendation can be acted upon"""
        return (
            not self.is_expired() and
            self.status == 'pending_review' and
            len(self.actions) > 0
        )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'agent_name': self.agent_name,
            'module': self.module,
            'summary': self.summary,
            'details': self.details,
            'confidence': self.confidence,
            'severity': self.severity,
            'actions': self.actions,
            'status': self.status,
            'llm_provider': self.llm_provider,
            'created_at': self.created_at.isoformat(),
            'is_actionable': self.is_actionable(),
        }
