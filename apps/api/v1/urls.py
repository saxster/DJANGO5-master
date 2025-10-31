"""
API v1 URL Configuration

Maps both mobile sync endpoints and web Command Center API endpoints.

Following .claude/rules.md patterns for clean URL structure.
"""

from django.urls import path, include
from apps.activity.views.task_sync_views import TaskSyncView, TaskChangesView
# Updated path after views package rename
from apps.work_order_management.views_extra.wom_sync_views import WOMSyncView, WOMChangesView
from apps.attendance.views.attendance_sync_views import AttendanceSyncView, AttendanceChangesView
from apps.y_helpdesk.views_extra.ticket_sync_views import TicketSyncView, TicketChangesView

app_name = 'api_v1'

urlpatterns = [
    # ============================================
    # Mobile Sync Endpoints (Existing)
    # ============================================
    path('activity/sync/', TaskSyncView.as_view(), name='activity-sync'),
    path('activity/changes/', TaskChangesView.as_view(), name='activity-changes'),

    path('work-orders/sync/', WOMSyncView.as_view(), name='work-orders-sync'),
    path('work-orders/changes/', WOMChangesView.as_view(), name='work-orders-changes'),

    path('attendance/sync/', AttendanceSyncView.as_view(), name='attendance-sync'),
    path('attendance/changes/', AttendanceChangesView.as_view(), name='attendance-changes'),

    path('helpdesk/sync/', TicketSyncView.as_view(), name='helpdesk-sync'),
    path('helpdesk/changes/', TicketChangesView.as_view(), name='helpdesk-changes'),

    # ============================================
    # Command Center API (Phase 1 - Oct 2025)
    # ============================================
    # Scope, alerts, portfolio, saved views
    path('', include('apps.core.api.urls', namespace='core')),

    # ============================================
    # Domain-Driven REST API (legacy API Migration - Oct 2025)
    # ============================================
    # Clean, domain-driven URL structure for REST API
    path('auth/', include('apps.api.v1.auth_urls')),
    path('people/', include('apps.api.v1.people_urls')),
    path('operations/', include('apps.api.v1.operations_urls')),
    path('wellness/', include('apps.api.v1.wellness_urls')),
    path('admin/', include('apps.api.v1.admin_urls')),
    path('helpbot/', include('apps.api.v1.helpbot_urls')),
    path('assets/', include('apps.api.v1.assets_urls')),
    path('attendance/', include('apps.api.v1.attendance_urls')),
    path('help-desk/', include('apps.api.v1.helpdesk_urls')),
    path('reports/', include('apps.api.v1.reports_urls')),
    path('files/', include('apps.api.v1.file_urls')),
]