from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GinIndex


class CollectiveIntelligencePattern(models.Model):
    """Cross-tenant anonymized patterns (privacy-preserving collective learning)."""
    
    PATTERN_TYPE_CHOICES = [
        ('RESPONSE_EFFECTIVENESS', 'Response Protocol Effectiveness'),
        ('FALSE_POSITIVE_COMMON', 'Common False Positive Pattern'),
        ('ESCALATION_TIMELINE', 'Typical Escalation Timeline'),
        ('GEOGRAPHIC_CORRELATION', 'Geographic Event Correlation'),
        ('SEASONAL_TREND', 'Seasonal Trend Pattern'),
    ]
    
    pattern_type = models.CharField(max_length=50, choices=PATTERN_TYPE_CHOICES, db_index=True)
    
    # Anonymized aggregates (NO tenant PII)
    threat_category = models.CharField(max_length=50, db_index=True)
    geographic_region = models.CharField(
        max_length=200,
        blank=True,
        help_text="Broad region (e.g., 'US-Northeast', 'Europe-Central')"
    )
    industry_sector = models.CharField(
        max_length=100,
        blank=True,
        help_text="Anonymized industry (e.g., 'retail', 'manufacturing')"
    )
    
    # Pattern metadata
    pattern_description = models.TextField()
    sample_size = models.PositiveIntegerField(
        help_text="Number of events/tenants contributing to this pattern"
    )
    confidence_score = models.FloatField(
        help_text="Statistical confidence in pattern (0.0-1.0)"
    )
    
    # Actionable insights
    recommended_actions = models.JSONField(
        default=list,
        help_text="List of recommended responses based on pattern"
    )
    effectiveness_metrics = models.JSONField(
        default=dict,
        help_text="Metrics on outcomes: {'action_X': {'success_rate': 0.85}}"
    )
    
    # Pattern data (anonymized)
    pattern_data = models.JSONField(
        default=dict,
        help_text="Statistical summaries, timelines, correlations"
    )
    
    # Temporal validity
    valid_from = models.DateTimeField(auto_now_add=True, db_index=True)
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Pattern expiration (for time-sensitive trends)"
    )
    
    # Usage tracking
    times_applied = models.PositiveIntegerField(default=0)
    times_helpful = models.PositiveIntegerField(default=0)
    times_not_helpful = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-confidence_score', '-sample_size']
        indexes = [
            models.Index(fields=['pattern_type', 'threat_category', 'is_active']),
            models.Index(fields=['geographic_region', 'industry_sector']),
            models.Index(fields=['valid_from', 'valid_until']),
            GinIndex(fields=['pattern_data']),
        ]
    
    def __str__(self):
        return f"{self.get_pattern_type_display()} - {self.threat_category}"
    
    @property
    def helpfulness_ratio(self):
        """Calculate how useful this pattern has been."""
        total = self.times_helpful + self.times_not_helpful
        if total == 0:
            return 0.0
        return self.times_helpful / total
