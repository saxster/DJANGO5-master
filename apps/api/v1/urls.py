"""
API v1 URL Configuration for Mobile Sync Endpoints

Maps domain-specific sync endpoints for offline-first mobile sync.

Following .claude/rules.md patterns for clean URL structure.
"""

from django.urls import path
from apps.activity.views.task_sync_views import TaskSyncView, TaskChangesView
from apps.work_order_management.views.wom_sync_views import WOMSyncView, WOMChangesView
from apps.attendance.views.attendance_sync_views import AttendanceSyncView, AttendanceChangesView
from apps.y_helpdesk.views.ticket_sync_views import TicketSyncView, TicketChangesView

app_name = 'api_v1'

urlpatterns = [
    path('activity/sync/', TaskSyncView.as_view(), name='activity-sync'),
    path('activity/changes/', TaskChangesView.as_view(), name='activity-changes'),

    path('work-orders/sync/', WOMSyncView.as_view(), name='work-orders-sync'),
    path('work-orders/changes/', WOMChangesView.as_view(), name='work-orders-changes'),

    path('attendance/sync/', AttendanceSyncView.as_view(), name='attendance-sync'),
    path('attendance/changes/', AttendanceChangesView.as_view(), name='attendance-changes'),

    path('helpdesk/sync/', TicketSyncView.as_view(), name='helpdesk-sync'),
    path('helpdesk/changes/', TicketChangesView.as_view(), name='helpdesk-changes'),
]