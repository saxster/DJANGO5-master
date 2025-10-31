"""
Wellness API ViewSets

ViewSets for wellness and journal domain REST API.
"""

from apps.wellness.api.viewsets.journal_viewset import JournalViewSet
from apps.wellness.api.viewsets.wellness_content_viewset import WellnessContentViewSet
from apps.wellness.api.viewsets.wellness_analytics_viewset import WellnessAnalyticsViewSet
from apps.wellness.api.viewsets.privacy_settings_viewset import PrivacySettingsViewSet

__all__ = [
    'JournalViewSet',
    'WellnessContentViewSet',
    'WellnessAnalyticsViewSet',
    'PrivacySettingsViewSet',
]
