"""
Wellness API URLs (V2)

Domain: /api/v2/wellness/

Handles journal entries, wellness content, analytics, and privacy with V2 enhancements.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path
from apps.api.v2.views import wellness_views

app_name = 'wellness'

urlpatterns = [
    # Journal endpoints (V2)
    path('journal/', wellness_views.JournalEntriesView.as_view(), name='journal'),
    path('journal/<uuid:entry_id>/media/', wellness_views.JournalMediaUploadView.as_view(), name='journal-media-upload'),
    path('journal/<uuid:entry_id>/media/list/', wellness_views.JournalMediaListView.as_view(), name='journal-media-list'),

    # Wellness content (V2)
    path('content/', wellness_views.WellnessContentView.as_view(), name='content'),

    # Analytics (V2)
    path('analytics/', wellness_views.WellnessAnalyticsView.as_view(), name='analytics'),

    # Privacy settings (V2)
    path('privacy/', wellness_views.PrivacySettingsView.as_view(), name='privacy'),
]
