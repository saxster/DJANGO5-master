from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GinIndex


class EventEscalationHistory(models.Model):
    """Track how threat events evolve over time (for predictive escalation)."""
    
    ESCALATION_STAGE_CHOICES = [
        ('EARLY_SIGNAL', 'Early Signal Detected'),
        ('CHATTER', 'Increased Social Media Chatter'),
        ('OFFICIAL_WARNING', 'Official Warning Issued'),
        ('IMMINENT', 'Event Imminent (24hrs)'),
        ('ACTIVE', 'Event Active'),
        ('AFTERMATH', 'Aftermath/Recovery Phase'),
        ('RESOLVED', 'Resolved'),
    ]
    
    threat_event = models.ForeignKey(
        'threat_intelligence.ThreatEvent',
        on_delete=models.CASCADE,
        related_name='escalation_history'
    )
    
    stage = models.CharField(max_length=30, choices=ESCALATION_STAGE_CHOICES, db_index=True)
    confidence_score = models.FloatField(help_text="ML confidence at this stage")
    severity = models.CharField(max_length=20)
    
    # What changed to trigger this escalation
    trigger_source = models.CharField(max_length=200, blank=True)
    trigger_description = models.TextField(blank=True)
    
    # Prediction metadata (FUTURE-PROOFING)
    predicted_impact_radius_km = models.FloatField(null=True, blank=True)
    predicted_duration_hours = models.FloatField(null=True, blank=True)
    similar_historical_events = models.JSONField(
        default=list,
        help_text="IDs of similar past events for pattern matching"
    )
    
    # Evidence/signals that led to this stage
    supporting_signals = models.JSONField(
        default=list,
        help_text="List of data points supporting this escalation"
    )
    
    stage_reached_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['threat_event', 'stage_reached_at']
        indexes = [
            models.Index(fields=['threat_event', 'stage', 'stage_reached_at']),
            models.Index(fields=['stage', 'stage_reached_at']),
            GinIndex(fields=['supporting_signals']),
        ]
        verbose_name_plural = 'Event escalation histories'
    
    def __str__(self):
        return f"{self.threat_event.title[:30]} - {self.get_stage_display()}"
