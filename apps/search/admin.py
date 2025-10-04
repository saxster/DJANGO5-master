"""
Django Admin for Search Models
"""

from django.contrib import admin
from apps.search.models import SearchIndex, SavedSearch, SearchAnalytics


@admin.register(SearchIndex)
class SearchIndexAdmin(admin.ModelAdmin):
    list_display = ['entity_type', 'title', 'tenant', 'is_active', 'last_indexed_at']
    list_filter = ['entity_type', 'is_active', 'tenant']
    search_fields = ['title', 'subtitle', 'entity_id']
    readonly_fields = ['last_indexed_at']


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'tenant', 'is_alert_enabled', 'alert_frequency']
    list_filter = ['is_alert_enabled', 'alert_frequency', 'tenant']
    search_fields = ['name', 'query', 'user__peoplename']


@admin.register(SearchAnalytics)
class SearchAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['query', 'tenant', 'result_count', 'response_time_ms', 'timestamp']
    list_filter = ['tenant', 'timestamp']
    search_fields = ['query', 'correlation_id']
    readonly_fields = ['timestamp', 'correlation_id']