"""
Attendance API URLs (v1)

Domain: /api/v1/attendance/

Handles attendance tracking, clock in/out, geofence validation, and fraud detection.

Compliance with .claude/rules.md:
- URL files < 200 lines
- Domain-driven structure
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.attendance.api.viewsets import AttendanceViewSet, FraudDetectionView

app_name = 'attendance'

router = DefaultRouter()
router.register(r'', AttendanceViewSet, basename='attendance')

urlpatterns = [
    # Router URLs (CRUD operations)
    # Includes custom actions:
    # - POST /clock-in/
    # - POST /clock-out/
    path('', include(router.urls)),

    # Fraud detection (admin only)
    path('fraud-alerts/', FraudDetectionView.as_view(), name='fraud-alerts'),
]
