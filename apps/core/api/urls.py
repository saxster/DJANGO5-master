"""
Core API URLs
=============
URL routing for Command Center API endpoints (Phase 1).

New endpoints:
- Scope management
- Saved views
- Alert inbox
- Portfolio/multi-site overview
- Site-level overview

Follows REST conventions and domain-driven structure.
"""

from django.urls import path

from apps.core.api.scope_views import (
    CurrentScopeView,
    UpdateScopeView,
    ScopeOptionsView,
)
from apps.core.api.saved_views_api import (
    SavedViewsListCreateView,
    SavedViewDetailView,
    SetDefaultViewView,
)
from apps.core.api.alert_inbox_views import (
    AlertInboxView,
    MarkAlertReadView,
    MarkAllAlertsReadView,
)
from apps.core.api.portfolio_views import (
    PortfolioSummaryView,
    AttendanceMetricsView,
    ToursMetricsView,
    TicketsMetricsView,
    WorkOrdersMetricsView,
    SiteOverviewView,
)
from apps.core.api.admin_help_views import (
    QuickTipsView,
    ContextualHelpView,
    PopularTopicsView,
    SearchHelpView,
    TrackHelpUsageView,
    HelpTopicDetailView,
)
from apps.core.api.mentor_views import (
    MentorSuggestionsAPI,
    MentorAskAPI,
    MentorTrackSuggestionAPI,
    MentorEfficiencyAPI,
    TutorialListAPI,
    TutorialDetailAPI,
)

app_name = "core_api"

urlpatterns = [
    # ============================================
    # Scope Management
    # ============================================
    path(
        "scope/current/",
        CurrentScopeView.as_view(),
        name="scope_current"
    ),
    path(
        "scope/update/",
        UpdateScopeView.as_view(),
        name="scope_update"
    ),
    path(
        "scope/options/",
        ScopeOptionsView.as_view(),
        name="scope_options"
    ),

    # ============================================
    # Saved Views
    # ============================================
    path(
        "saved-views/",
        SavedViewsListCreateView.as_view(),
        name="saved_views_list"
    ),
    path(
        "saved-views/<int:view_id>/",
        SavedViewDetailView.as_view(),
        name="saved_view_detail"
    ),
    path(
        "saved-views/<int:view_id>/set-default/",
        SetDefaultViewView.as_view(),
        name="saved_view_set_default"
    ),

    # ============================================
    # Alert Inbox (Unified Notifications)
    # ============================================
    path(
        "alerts/inbox/",
        AlertInboxView.as_view(),
        name="alert_inbox"
    ),
    path(
        "alerts/<str:alert_id>/mark-read/",
        MarkAlertReadView.as_view(),
        name="alert_mark_read"
    ),
    path(
        "alerts/mark-all-read/",
        MarkAllAlertsReadView.as_view(),
        name="alert_mark_all_read"
    ),

    # ============================================
    # Portfolio Overview (Multi-Site)
    # ============================================
    path(
        "overview/summary/",
        PortfolioSummaryView.as_view(),
        name="portfolio_summary"
    ),
    path(
        "overview/attendance/",
        AttendanceMetricsView.as_view(),
        name="portfolio_attendance"
    ),
    path(
        "overview/tours/",
        ToursMetricsView.as_view(),
        name="portfolio_tours"
    ),
    path(
        "overview/tickets/",
        TicketsMetricsView.as_view(),
        name="portfolio_tickets"
    ),
    path(
        "overview/work-orders/",
        WorkOrdersMetricsView.as_view(),
        name="portfolio_work_orders"
    ),

    # ============================================
    # Site-Level Overview
    # ============================================
    path(
        "sites/<int:bu_id>/overview/",
        SiteOverviewView.as_view(),
        name="site_overview"
    ),

    # ============================================
    # Admin Help System
    # ============================================
    path(
        "admin-help/quick-tips/",
        QuickTipsView.as_view(),
        name="admin_help_quick_tips"
    ),
    path(
        "admin-help/contextual/",
        ContextualHelpView.as_view(),
        name="admin_help_contextual"
    ),
    path(
        "admin-help/popular/",
        PopularTopicsView.as_view(),
        name="admin_help_popular"
    ),
    path(
        "admin-help/search/",
        SearchHelpView.as_view(),
        name="admin_help_search"
    ),
    path(
        "admin-help/<int:topic_id>/",
        HelpTopicDetailView.as_view(),
        name="admin_help_detail"
    ),
    path(
        "admin-help/<int:topic_id>/view/",
        TrackHelpUsageView.as_view(),
        name="admin_help_track_usage"
    ),

    # ============================================
    # AI Mentor System
    # ============================================
    path(
        "admin/mentor/suggestions/",
        MentorSuggestionsAPI.as_view(),
        name="mentor_suggestions"
    ),
    path(
        "admin/mentor/ask/",
        MentorAskAPI.as_view(),
        name="mentor_ask"
    ),
    path(
        "admin/mentor/track-suggestion/",
        MentorTrackSuggestionAPI.as_view(),
        name="mentor_track_suggestion"
    ),
    path(
        "admin/mentor/efficiency/",
        MentorEfficiencyAPI.as_view(),
        name="mentor_efficiency"
    ),
    path(
        "admin/tutorials/",
        TutorialListAPI.as_view(),
        name="tutorial_list"
    ),
    path(
        "admin/tutorials/<str:tutorial_id>/",
        TutorialDetailAPI.as_view(),
        name="tutorial_detail"
    ),
]
