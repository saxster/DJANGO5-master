"""
Activity API URL Configuration

URL routing for operations domain REST API.

Endpoints:
- /operations/tasks/          - Task sync endpoints (mobile)
- /operations/jobs/           - Job CRUD
- /operations/jobneeds/       - Jobneed CRUD
- /operations/questionsets/   - Question set CRUD
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.activity.api.viewsets.task_sync_viewset import TaskSyncViewSet
from apps.activity.api.viewsets import (
    JobViewSet,
    JobneedViewSet,
    QuestionSetViewSet,
)

# Create router for standard CRUD operations
router = DefaultRouter()
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'jobneeds', JobneedViewSet, basename='jobneed')
router.register(r'questionsets', QuestionSetViewSet, basename='questionset')

# Mobile sync endpoints
router.register(r'tasks', TaskSyncViewSet, basename='task-sync')

app_name = 'activity_api'

urlpatterns = [
    path('', include(router.urls)),
]
