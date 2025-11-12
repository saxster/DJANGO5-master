"""
Simplified admin URL configuration.

Historically this module exposed several placeholder views that lived under
the ``/admin/`` namespace. Those views have been removed; the admin now routes
directly to Django's ``admin.site.urls`` while keeping the legacy
``/admin/django/`` entry point for users that bookmarked it.
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from apps.core.views.team_dashboard_view import TeamDashboardView, TeamDashboardAPIView
from apps.core.views.timeline_views import (
    PersonTimelineView,
    AssetTimelineView,
    LocationTimelineView
)

urlpatterns = [
    # Team Dashboard - Unified operations queue
    path("dashboard/team/", TeamDashboardView.as_view(), name="admin_team_dashboard"),
    path("dashboard/team/api/", TeamDashboardAPIView.as_view(), name="admin_team_dashboard_api"),
    
    # Activity Timeline - 360° entity profiles
    path("timeline/person/<int:person_id>/", PersonTimelineView.as_view(), name="person_timeline"),
    path("timeline/asset/<int:asset_id>/", AssetTimelineView.as_view(), name="asset_timeline"),
    path("timeline/location/<int:location_id>/", LocationTimelineView.as_view(), name="location_timeline"),
    
    # Admin site
    path("", admin.site.urls),
    path("django/", RedirectView.as_view(pattern_name="admin:index", permanent=False)),
]
