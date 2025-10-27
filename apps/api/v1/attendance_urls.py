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

# Import views when they're created
# from apps.attendance.api import views

app_name = 'attendance'

router = DefaultRouter()
# router.register(r'', views.AttendanceViewSet, basename='attendance')

urlpatterns = [
    # Router URLs (CRUD operations)
    path('', include(router.urls)),

    # Additional endpoints (to be implemented)
    # path('clock-in/', views.ClockInView.as_view(), name='clock-in'),
    # path('clock-out/', views.ClockOutView.as_view(), name='clock-out'),
    # path('validate-location/', views.ValidateLocationView.as_view(), name='validate-location'),
    # path('history/', views.AttendanceHistoryView.as_view(), name='history'),
    # path('fraud-alerts/', views.FraudAlertsView.as_view(), name='fraud-alerts'),
]
