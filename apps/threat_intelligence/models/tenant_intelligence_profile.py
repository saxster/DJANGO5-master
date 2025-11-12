from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GinIndex
from apps.core.models import TenantAwareModel


class TenantIntelligenceProfile(TenantAwareModel):
    """Per-tenant configuration for threat intelligence monitoring."""
    
    ALERT_URGENCY_CHOICES = [
        ('IMMEDIATE', 'Immediate (WebSocket + SMS)'),
        ('RAPID', '15 minutes (WebSocket + Email)'),
        ('STANDARD', '1 hour (Email summary)'),
        ('DIGEST', 'Daily digest only'),
        ('DISABLED', 'No alerts'),
    ]
    
    # Geospatial monitoring
    monitored_locations = models.MultiPolygonField(
        geography=True,
        help_text="Geofences around tenant facilities requiring monitoring"
    )
    buffer_radius_km = models.FloatField(
        default=10.0,
        help_text="Expand monitored area by this radius"
    )
    
    # Category preferences (future-proofed for ML tuning)
    threat_categories = models.JSONField(
        default=list,
        help_text="List of enabled threat categories"
    )
    category_weights = models.JSONField(
        default=dict,
        help_text="Per-category importance weights (for ML scoring)"
    )
    
    # Alert thresholds
    minimum_severity = models.CharField(max_length=20, default='MEDIUM')
    minimum_confidence = models.FloatField(
        default=0.6,
        help_text="Minimum ML confidence to trigger alert (0.0-1.0)"
    )
    
    alert_urgency_critical = models.CharField(
        max_length=20,
        choices=ALERT_URGENCY_CHOICES,
        default='IMMEDIATE'
    )
    alert_urgency_high = models.CharField(
        max_length=20,
        choices=ALERT_URGENCY_CHOICES,
        default='RAPID'
    )
    alert_urgency_medium = models.CharField(
        max_length=20,
        choices=ALERT_URGENCY_CHOICES,
        default='STANDARD'
    )
    alert_urgency_low = models.CharField(
        max_length=20,
        choices=ALERT_URGENCY_CHOICES,
        default='DIGEST'
    )
    
    # Notification channels
    enable_websocket = models.BooleanField(default=True)
    enable_sms = models.BooleanField(default=False)
    enable_email = models.BooleanField(default=True)
    enable_work_order_creation = models.BooleanField(default=False)
    
    # Emergency contacts (future-proofed)
    emergency_contacts = models.JSONField(
        default=list,
        help_text="List of {role, name, phone, email} for critical alerts"
    )
    
    # Operational hours (alerts outside hours go to digest)
    operational_hours = models.JSONField(
        default=dict,
        help_text="Per-day operating hours: {'monday': {'start': '08:00', 'end': '18:00'}}"
    )
    
    # ML learning preferences (FUTURE-PROOFING)
    enable_auto_tuning = models.BooleanField(
        default=True,
        help_text="Allow ML to adjust thresholds based on feedback"
    )
    enable_collective_intelligence = models.BooleanField(
        default=True,
        help_text="Participate in anonymized cross-tenant pattern sharing"
    )
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            GinIndex(fields=['threat_categories']),
        ]
    
    def __str__(self):
        return f"Intelligence Profile - {self.tenant.name}"
    
    def get_alert_urgency_for_severity(self, severity):
        """Map severity to configured urgency level."""
        mapping = {
            'CRITICAL': self.alert_urgency_critical,
            'HIGH': self.alert_urgency_high,
            'MEDIUM': self.alert_urgency_medium,
            'LOW': self.alert_urgency_low,
        }
        return mapping.get(severity, 'DIGEST')
