from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GinIndex
from apps.core.models import TenantAwareModel


class TenantLearningProfile(TenantAwareModel):
    """ML-adjusted preferences per tenant (auto-tuning based on feedback)."""
    
    intelligence_profile = models.OneToOneField(
        'threat_intelligence.TenantIntelligenceProfile',
        on_delete=models.CASCADE,
        related_name='learning_profile'
    )
    
    # Category-specific learned preferences
    category_sensitivity = models.JSONField(
        default=dict,
        help_text="Per-category adjusted thresholds: {'POLITICAL': 0.7, 'WEATHER': 0.4}"
    )
    
    # Time-of-day preferences (learned from response patterns)
    optimal_alert_hours = models.JSONField(
        default=dict,
        help_text="Hours when tenant is most responsive: {'weekday': [8, 17], 'weekend': []}"
    )
    
    # Source trust scores (learned from feedback)
    source_trust_scores = models.JSONField(
        default=dict,
        help_text="Per-source reliability for this tenant: {'source_id': 0.85}"
    )
    
    # Response pattern metrics
    total_alerts_received = models.PositiveIntegerField(default=0)
    total_actionable = models.PositiveIntegerField(default=0)
    total_false_positives = models.PositiveIntegerField(default=0)
    total_missed = models.PositiveIntegerField(default=0)
    
    average_response_time_minutes = models.FloatField(
        default=0.0,
        help_text="How quickly tenant typically responds to alerts"
    )
    
    # Geographic adjustment (learned from distance/response correlation)
    effective_monitoring_radius_km = models.FloatField(
        null=True,
        blank=True,
        help_text="ML-calculated optimal radius based on past responses"
    )
    
    # Feature importance scores (FUTURE: for explainability)
    feature_importance = models.JSONField(
        default=dict,
        help_text="Which features matter most for this tenant's decisions"
    )
    
    # Last ML training metadata
    last_retrained_at = models.DateTimeField(null=True, blank=True)
    training_sample_size = models.PositiveIntegerField(default=0)
    model_accuracy_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Predictive accuracy of tenant-specific model"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'last_retrained_at']),
            GinIndex(fields=['category_sensitivity']),
        ]
    
    def __str__(self):
        return f"Learning Profile - {self.tenant.name}"
    
    @property
    def actionable_rate(self):
        """Percentage of alerts that led to action."""
        if self.total_alerts_received == 0:
            return 0.0
        return (self.total_actionable / self.total_alerts_received) * 100
    
    @property
    def false_positive_rate(self):
        """Percentage of alerts marked as false positives."""
        if self.total_alerts_received == 0:
            return 0.0
        return (self.total_false_positives / self.total_alerts_received) * 100
