"""
Attendance API v2 URL Configuration
Domain: Attendance (Check-in/out, Conveyance, Geofencing, Face Enrollment)
Generated from Kotlin SDK documentation
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.attendance.api.v2 import viewsets

router = DefaultRouter()
router.register(r'conveyance', viewsets.ConveyanceViewSet, basename='conveyance')

app_name = 'attendance_v2'

urlpatterns = [
    path('', include(router.urls)),

    # Core attendance endpoints
    path('list/', viewsets.AttendanceListView.as_view(), name='attendance-list'),
    path('fraud-alerts/', viewsets.FraudAlertsView.as_view(), name='fraud-alerts'),
    path('posts/', viewsets.PostListView.as_view(), name='posts-list'),

    # Check-in/out
    path('checkin/', viewsets.CheckInView.as_view(), name='checkin'),
    path('checkout/', viewsets.CheckOutView.as_view(), name='checkout'),

    # GPS & validation
    path('geofence/validate/', viewsets.GeofenceValidationView.as_view(), name='geofence-validate'),
    path('pay-rates/<int:user_id>/', viewsets.PayRateView.as_view(), name='pay-rates'),

    # Biometrics
    path('face/enroll/', viewsets.FaceEnrollmentView.as_view(), name='face-enroll'),
]
