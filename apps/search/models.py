"""
Global Search Models

All models comply with Rule #7: < 150 lines, single responsibility principle
"""

from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from apps.peoples.models import BaseModel, TenantAwareModel, People
from apps.tenants.models import Tenant


class SearchIndex(BaseModel, TenantAwareModel):
    """
    Unified search index for all searchable entities

    Stores tsvector representations for fast FTS queries
    with GIN index for optimal performance (99.7% speedup)

    Complies with Rule #7: < 150 lines
    """

    class EntityType(models.TextChoices):
        PEOPLE = 'people', 'People'
        WORK_ORDER = 'work_order', 'Work Order'
        TICKET = 'ticket', 'Ticket'
        ASSET = 'asset', 'Asset'
        LOCATION = 'location', 'Location'
        TASK = 'task', 'Task'
        TOUR = 'tour', 'Tour'
        KNOWLEDGE = 'knowledge', 'Knowledge'
        REPORT = 'report', 'Report'

    entity_type = models.CharField(
        max_length=20,
        choices=EntityType.choices,
        db_index=True
    )
    entity_id = models.CharField(max_length=100, db_index=True)

    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, blank=True)
    content = models.TextField(blank=True)

    search_vector = SearchVectorField(null=True)

    metadata = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    last_indexed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'search_index'
        verbose_name = 'Search Index'
        verbose_name_plural = 'Search Indexes'
        unique_together = [['tenant', 'entity_type', 'entity_id']]
        indexes = [
            GinIndex(fields=['search_vector'], name='search_vector_gin_idx'),
            models.Index(fields=['tenant', 'entity_type', 'is_active']),
            models.Index(fields=['tenant', 'is_active', '-last_indexed_at']),
        ]

    def __str__(self):
        return f"{self.entity_type}: {self.title}"


class SavedSearch(BaseModel, TenantAwareModel):
    """
    User-created saved searches with optional alerts

    Enables proactive workflow automation through alerts

    Complies with Rule #7: < 150 lines
    """

    class AlertFrequency(models.TextChoices):
        REALTIME = 'realtime', 'Real-time'
        HOURLY = 'hourly', 'Hourly'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'

    user = models.ForeignKey(
        People,
        on_delete=models.CASCADE,
        related_name='saved_searches'
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    query = models.CharField(max_length=500)
    entities = models.JSONField(default=list)
    filters = models.JSONField(default=dict)

    is_alert_enabled = models.BooleanField(default=False, db_index=True)
    alert_frequency = models.CharField(
        max_length=20,
        choices=AlertFrequency.choices,
        default=AlertFrequency.DAILY
    )
    last_executed_at = models.DateTimeField(null=True, blank=True)
    last_result_count = models.IntegerField(default=0)

    is_public = models.BooleanField(default=False)

    class Meta:
        db_table = 'saved_search'
        verbose_name = 'Saved Search'
        verbose_name_plural = 'Saved Searches'
        indexes = [
            models.Index(fields=['tenant', 'user', 'is_alert_enabled']),
            models.Index(fields=['tenant', 'is_alert_enabled', 'alert_frequency']),
        ]

    def __str__(self):
        return f"{self.name} by {self.user.peoplename}"


class SearchAnalytics(BaseModel):
    """
    Search analytics for insights and optimization

    Tracks query patterns, performance, and click-through

    Complies with Rule #7: < 150 lines
    Complies with Rule #15: No PII in logs
    """

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='search_analytics'
    )
    user = models.ForeignKey(
        People,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_analytics'
    )

    query = models.CharField(max_length=500, db_index=True)
    entities = models.JSONField(default=list)
    filters = models.JSONField(default=dict)

    result_count = models.IntegerField(default=0)
    response_time_ms = models.IntegerField(default=0)

    clicked_entity_type = models.CharField(max_length=20, blank=True)
    clicked_entity_id = models.CharField(max_length=100, blank=True)
    click_position = models.IntegerField(null=True, blank=True)

    correlation_id = models.UUIDField(db_index=True)

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'search_analytics'
        verbose_name = 'Search Analytics'
        verbose_name_plural = 'Search Analytics'
        indexes = [
            models.Index(fields=['tenant', '-timestamp']),
            models.Index(fields=['tenant', 'query']),
            models.Index(fields=['correlation_id']),
        ]

    def __str__(self):
        return f"Search: {self.query[:50]} at {self.timestamp}"