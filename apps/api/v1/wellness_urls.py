"""
Wellness API URLs (v1)

Domain: /api/v1/wellness/

Handles journal entries, wellness content, analytics, and privacy settings.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.wellness.api.viewsets import (
    JournalViewSet,
    WellnessContentViewSet,
    WellnessAnalyticsViewSet,
    PrivacySettingsViewSet,
)

app_name = 'wellness'

router = DefaultRouter()

# Journal endpoints
router.register(r'journal', JournalViewSet, basename='journal')

# Wellness content endpoints
router.register(r'content', WellnessContentViewSet, basename='wellness-content')

# Analytics endpoints
router.register(r'analytics', WellnessAnalyticsViewSet, basename='wellness-analytics')

# Privacy settings endpoints
router.register(r'privacy', PrivacySettingsViewSet, basename='privacy-settings')

urlpatterns = [
    # Journal endpoints (replace legacy API):
    # - journal/entries/ (POST) → CreateJournalEntry mutation
    # - journal/entries/ (GET) → journal_entries query
    # - journal/entries/{id}/ (GET) → journal_entry query
    #
    # Wellness content endpoints (replace legacy API):
    # - content/daily-tip/ → daily_wellness_tip query
    # - content/personalized/ → personalized_wellness_content query
    # - content/track-interaction/ → TrackWellnessInteraction mutation
    #
    # Analytics endpoints (replace legacy API):
    # - analytics/my-progress/ → my_wellness_progress query
    # - analytics/wellbeing-analytics/ → my_wellbeing_analytics query
    #
    # Privacy endpoints (replace legacy API):
    # - privacy/settings/ (GET) → my_privacy_settings query
    # - privacy/settings/ (PATCH) → UpdatePrivacySettings mutation
    path('', include(router.urls)),
]
