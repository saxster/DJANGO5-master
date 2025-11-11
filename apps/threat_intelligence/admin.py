from django.contrib.gis import admin
from apps.threat_intelligence.models import (
    IntelligenceSource,
    ThreatEvent,
    TenantIntelligenceProfile,
    IntelligenceAlert,
    EventEscalationHistory,
    CollectiveIntelligencePattern,
    TenantLearningProfile,
)


@admin.register(IntelligenceSource)
class IntelligenceSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'is_active', 'last_fetch_status', 'last_fetch_at', 'total_events_created']
    list_filter = ['source_type', 'is_active', 'last_fetch_status']
    search_fields = ['name', 'endpoint_url']
    readonly_fields = ['last_fetch_at', 'total_fetches', 'total_events_created', 'average_fetch_duration_seconds']


@admin.register(ThreatEvent)
class ThreatEventAdmin(admin.GISModelAdmin):  # OSMGeoAdmin deprecated in Django 5.x
    list_display = ['title', 'category', 'severity', 'confidence_score', 'event_start_time', 'location_name', 'is_processed']
    list_filter = ['category', 'severity', 'is_processed', 'source']
    search_fields = ['title', 'description', 'location_name']
    readonly_fields = ['created_at', 'updated_at', 'raw_content']
    date_hierarchy = 'event_start_time'


@admin.register(TenantIntelligenceProfile)
class TenantIntelligenceProfileAdmin(admin.GISModelAdmin):
    list_display = ['tenant', 'minimum_severity', 'is_active', 'enable_websocket', 'enable_sms', 'enable_email']
    list_filter = ['is_active', 'enable_auto_tuning', 'enable_collective_intelligence']
    search_fields = ['tenant__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(IntelligenceAlert)
class IntelligenceAlertAdmin(admin.ModelAdmin):
    list_display = ['threat_event', 'tenant', 'severity', 'delivery_status', 'tenant_response', 'created_at']
    list_filter = ['severity', 'delivery_status', 'tenant_response', 'work_order_created']
    search_fields = ['threat_event__title', 'tenant__name']
    readonly_fields = ['created_at', 'updated_at', 'delivered_at', 'response_timestamp']
    date_hierarchy = 'created_at'


@admin.register(EventEscalationHistory)
class EventEscalationHistoryAdmin(admin.ModelAdmin):
    list_display = ['threat_event', 'stage', 'severity', 'confidence_score', 'stage_reached_at']
    list_filter = ['stage', 'severity']
    search_fields = ['threat_event__title', 'trigger_description']
    readonly_fields = ['stage_reached_at']


@admin.register(CollectiveIntelligencePattern)
class CollectiveIntelligencePatternAdmin(admin.ModelAdmin):
    list_display = ['pattern_type', 'threat_category', 'sample_size', 'confidence_score', 'is_active', 'helpfulness_ratio']
    list_filter = ['pattern_type', 'threat_category', 'is_active']
    search_fields = ['pattern_description', 'geographic_region']
    readonly_fields = ['created_at', 'updated_at', 'times_applied', 'times_helpful', 'times_not_helpful']


@admin.register(TenantLearningProfile)
class TenantLearningProfileAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'total_alerts_received', 'actionable_rate', 'false_positive_rate', 'last_retrained_at']
    list_filter = ['last_retrained_at']
    search_fields = ['tenant__name']
    readonly_fields = ['created_at', 'updated_at', 'last_retrained_at', 'total_alerts_received', 'total_actionable', 'total_false_positives']
