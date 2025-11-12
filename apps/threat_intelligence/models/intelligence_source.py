from django.contrib.gis.db import models
from apps.core.models import TenantAwareModel


class IntelligenceSource(models.Model):
    """External data sources for threat intelligence gathering."""
    
    SOURCE_TYPES = [
        ('NEWS_API', 'News API'),
        ('RSS_FEED', 'RSS Feed'),
        ('WEATHER_API', 'Weather Service'),
        ('GOVERNMENT', 'Government Alert System'),
        ('SOCIAL_MEDIA', 'Social Media Platform'),
        ('THREAT_FEED', 'Security Threat Feed'),
        ('CUSTOM_SCRAPER', 'Custom Web Scraper'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('FAILED', 'Failed'),
        ('RATE_LIMITED', 'Rate Limited'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    endpoint_url = models.URLField(blank=True)
    api_key_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Name of environment variable containing API key"
    )
    
    refresh_interval_minutes = models.PositiveIntegerField(default=60)
    last_fetch_at = models.DateTimeField(null=True, blank=True)
    last_fetch_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    last_fetch_error = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(default=5, help_text="1=highest, 10=lowest")
    
    config = models.JSONField(
        default=dict,
        help_text="Source-specific configuration (query params, filters, etc.)"
    )
    
    # Metrics for monitoring
    total_fetches = models.PositiveIntegerField(default=0)
    total_events_created = models.PositiveIntegerField(default=0)
    average_fetch_duration_seconds = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['is_active', 'last_fetch_at']),
            models.Index(fields=['source_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"
