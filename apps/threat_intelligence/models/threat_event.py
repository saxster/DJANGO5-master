from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone


class ThreatEvent(models.Model):
    """Raw intelligence event from external sources."""
    
    CATEGORY_CHOICES = [
        ('POLITICAL', 'Political Unrest'),
        ('WEATHER', 'Weather/Natural Disaster'),
        ('CYBER', 'Cyber Threat'),
        ('CIVIL_EMERGENCY', 'Civil Emergency'),
        ('TERRORISM', 'Terrorism/Violence'),
        ('CRIME', 'Crime Wave'),
        ('INFRASTRUCTURE', 'Infrastructure Failure'),
        ('HEALTH', 'Public Health Emergency'),
        ('OTHER', 'Other'),
    ]
    
    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
        ('INFO', 'Informational'),
    ]
    
    source = models.ForeignKey(
        'threat_intelligence.IntelligenceSource',
        on_delete=models.CASCADE,
        related_name='events'
    )
    
    external_id = models.CharField(max_length=500, blank=True, db_index=True)
    title = models.CharField(max_length=500)
    description = models.TextField()
    raw_content = models.TextField(help_text="Original unprocessed content")
    
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, db_index=True)
    confidence_score = models.FloatField(
        default=0.5,
        help_text="ML confidence in classification (0.0-1.0)"
    )
    
    # Geospatial fields (PostGIS)
    location = models.PointField(null=True, blank=True, geography=True)
    affected_area = models.PolygonField(null=True, blank=True, geography=True)
    impact_radius_km = models.FloatField(null=True, blank=True)
    
    location_name = models.CharField(max_length=500, blank=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    
    # Temporal fields
    event_start_time = models.DateTimeField(db_index=True)
    event_end_time = models.DateTimeField(null=True, blank=True)
    forecast_window_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="How many hours ahead this event is forecasted"
    )
    
    # NLP extraction results
    entities = models.JSONField(
        default=dict,
        help_text="Extracted entities: organizations, people, locations"
    )
    keywords = models.JSONField(
        default=list,
        help_text="Extracted keywords/tags"
    )
    
    # Source metadata
    source_url = models.URLField(blank=True, max_length=1000)
    source_published_at = models.DateTimeField(null=True, blank=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False, db_index=True)
    processing_error = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-event_start_time', '-severity']
        indexes = [
            models.Index(fields=['category', 'severity', 'event_start_time']),
            models.Index(fields=['is_processed', 'created_at']),
            models.Index(fields=['event_start_time', 'event_end_time']),
            GinIndex(fields=['entities']),
            GinIndex(fields=['keywords']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(confidence_score__gte=0.0) & models.Q(confidence_score__lte=1.0),
                name='valid_confidence_score'
            )
        ]
    
    def __str__(self):
        return f"{self.get_severity_display()}: {self.title[:50]}"
    
    @property
    def is_active(self):
        """Check if event is currently happening or forecasted."""
        now = timezone.now()
        if self.event_end_time:
            return self.event_start_time <= now <= self.event_end_time
        return self.event_start_time <= now
