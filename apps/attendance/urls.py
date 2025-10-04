from django.urls import path
from apps.attendance import views

# Import AI analytics dashboard
try:
    from apps.attendance.ai_analytics_dashboard import AIAnalyticsDashboardView
    AI_ANALYTICS_AVAILABLE = True
except ImportError:
    AI_ANALYTICS_AVAILABLE = False

app_name = "attendance"
urlpatterns = [
    path("attendance/", views.Attendance.as_view(), name="attendance_view"),
    path("travel_expense/", views.Conveyance.as_view(), name="conveyance"),
    path(
        "geofencetracking/", views.GeofenceTracking.as_view(), name="geofencetracking"
    ),
]

# Add AI analytics if available
if AI_ANALYTICS_AVAILABLE:
    urlpatterns.append(
        path("ai-analytics/", AIAnalyticsDashboardView.as_view(), name="ai_analytics_dashboard")
    )
