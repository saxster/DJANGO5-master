"""
Journal App URLs Configuration

Complete URL patterns for the journal system API endpoints with:
- CRUD operations for journal entries
- Advanced search with privacy filtering
- Analytics and insights generation
- Mobile sync with conflict resolution
- Privacy settings management
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    JournalEntryViewSet, JournalSearchView, JournalAnalyticsView,
    JournalSyncView, JournalPrivacySettingsView
)
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

app_name = 'journal'

# REST API router for journal entries
router = DefaultRouter()
router.register(r'entries', JournalEntryViewSet, basename='journalentry')

urlpatterns = [
    # Web UI Templates
    path('dashboard/', login_required(TemplateView.as_view(template_name='journal/dashboard.html')), name='wellness-dashboard'),
    path('entries/', login_required(TemplateView.as_view(template_name='journal/entries_list.html')), name='journal-entries-list'),
    path('entry/new/', login_required(TemplateView.as_view(template_name='journal/entry_new.html')), name='journal-entry-new'),
    path('analytics/', login_required(TemplateView.as_view(template_name='journal/analytics.html')), name='journal-analytics-ui'),

    # REST API endpoints from router
    path('api/', include(router.urls)),

    # Advanced search endpoint
    path('api/search/', JournalSearchView.as_view(), name='journal-search'),

    # Analytics and insights API
    path('api/analytics/', JournalAnalyticsView.as_view(), name='journal-analytics'),

    # Mobile client sync
    path('api/sync/', JournalSyncView.as_view(), name='journal-sync'),

    # Privacy settings management
    path('api/privacy-settings/', JournalPrivacySettingsView.as_view(), name='journal-privacy-settings'),

    # Additional API endpoints provided by JournalEntryViewSet custom actions:
    # POST /api/entries/bulk_create/ - Bulk create entries for mobile sync
    # GET /api/entries/analytics_summary/ - Quick analytics summary
    # POST /api/entries/{id}/bookmark/ - Toggle bookmark status
    # GET /api/entries/{id}/related_wellness_content/ - Get related wellness content
]