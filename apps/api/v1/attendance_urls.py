"""
Attendance API URLs (v1)

Domain: /api/v1/attendance/

Handles attendance tracking, clock in/out, geofence validation, fraud detection,
and post assignment management (Phase 2-3).

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.attendance.api.viewsets import AttendanceViewSet, FraudDetectionView
from apps.attendance.api.viewsets_post import (
    PostViewSet,
    PostAssignmentViewSet,
    PostOrderAcknowledgementViewSet,
    WorkerPostViewSet,
)

app_name = 'attendance'

# Main router for attendance records
router = DefaultRouter()
router.register(r'', AttendanceViewSet, basename='attendance')

# Phase 2: Post management routers
posts_router = DefaultRouter()
posts_router.register(r'posts', PostViewSet, basename='post')
posts_router.register(r'post-assignments', PostAssignmentViewSet, basename='post-assignment')
posts_router.register(r'post-acknowledgements', PostOrderAcknowledgementViewSet, basename='post-acknowledgement')
posts_router.register(r'my-posts', WorkerPostViewSet, basename='worker-post')

urlpatterns = [
    # Phase 1: Attendance tracking (CRUD operations)
    # Includes custom actions:
    # - POST /clock-in/  (with Phase 1 shift validation + optional Phase 3 post validation)
    # - POST /clock-out/
    path('', include(router.urls)),

    # Phase 2-3: Post management endpoints
    # Includes:
    # - GET/POST/PATCH/DELETE /posts/
    # - GET/POST/PATCH/DELETE /post-assignments/
    # - GET/POST /post-acknowledgements/
    # - GET /my-posts/ (worker-facing)
    path('', include(posts_router.urls)),

    # Fraud detection (admin only)
    path('fraud-alerts/', FraudDetectionView.as_view(), name='fraud-alerts'),
]
