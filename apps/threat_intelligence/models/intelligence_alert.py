from django.contrib.gis.db import models
from apps.core.models import TenantAwareModel
from django.utils import timezone


class IntelligenceAlert(TenantAwareModel):
    """Alerts delivered to specific tenants (with feedback loop for ML learning)."""
    
    DELIVERY_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('SUPPRESSED', 'Suppressed (outside hours/digest)'),
    ]
    
    RESPONSE_CHOICES = [
        ('NO_RESPONSE', 'No Response Yet'),
        ('ACTIONABLE', 'Triggered Response Protocol'),
        ('NOTED', 'Acknowledged - No Action Needed'),
        ('FALSE_POSITIVE', 'Not Relevant/False Positive'),
        ('MISSED', 'Should Have Alerted Sooner'),
        ('TOO_SENSITIVE', 'Too Many Similar Alerts'),
    ]
    
    threat_event = models.ForeignKey(
        'threat_intelligence.ThreatEvent',
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    
    intelligence_profile = models.ForeignKey(
        'threat_intelligence.TenantIntelligenceProfile',
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    
    # Alert metadata
    severity = models.CharField(max_length=20, db_index=True)
    urgency_level = models.CharField(max_length=20)
    distance_km = models.FloatField(
        help_text="Distance from nearest monitored facility"
    )
    
    # Delivery tracking
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    delivery_channels = models.JSONField(
        default=list,
        help_text="Channels used: ['websocket', 'email', 'sms']"
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_error = models.TextField(blank=True)
    
    # CRITICAL: Feedback loop for ML learning
    tenant_response = models.CharField(
        max_length=30,
        choices=RESPONSE_CHOICES,
        default='NO_RESPONSE',
        db_index=True
    )
    response_timestamp = models.DateTimeField(null=True, blank=True)
    response_notes = models.TextField(blank=True)
    
    # Auto-generated work order tracking
    work_order_created = models.BooleanField(default=False)
    work_order = models.ForeignKey(
        'work_order_management.Wom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='intelligence_alerts'
    )
    
    # User interaction tracking
    viewed_by = models.ManyToManyField(
        'peoples.People',
        through='IntelligenceAlertView',
        related_name='viewed_intelligence_alerts'
    )
    acknowledged_by = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # FUTURE-PROOFING: Escalation tracking
    escalation_level = models.PositiveSmallIntegerField(default=0)
    escalated_to = models.JSONField(
        default=list,
        help_text="List of people/roles escalated to"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'delivery_status', 'created_at']),
            models.Index(fields=['severity', 'tenant_response']),
            models.Index(fields=['tenant', 'tenant_response', 'created_at']),
        ]
    
    def __str__(self):
        return f"Alert for {self.tenant.name}: {self.threat_event.title[:40]}"
    
    def mark_actionable(self, user, notes=""):
        """Record that tenant took action on this alert."""
        self.tenant_response = 'ACTIONABLE'
        self.response_timestamp = timezone.now()
        self.response_notes = notes
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()
    
    def mark_false_positive(self, user, notes=""):
        """Record false positive for ML retraining."""
        self.tenant_response = 'FALSE_POSITIVE'
        self.response_timestamp = timezone.now()
        self.response_notes = notes
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()


class IntelligenceAlertView(models.Model):
    """Track who viewed which alerts (for engagement metrics)."""
    
    alert = models.ForeignKey('IntelligenceAlert', on_delete=models.CASCADE)
    user = models.ForeignKey('peoples.People', on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    view_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        unique_together = ['alert', 'user']
        indexes = [
            models.Index(fields=['alert', 'viewed_at']),
        ]
