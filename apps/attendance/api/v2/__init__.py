"""
Attendance API v2

Type-safe endpoints with GPS validation, facial recognition, and pay calculation.
"""

from apps.attendance.api.v2.viewsets import (
    CheckInView,
    CheckOutView,
    GeofenceValidationView,
    PayRateView,
    FaceEnrollmentView,
    ConveyanceViewSet,
)

__all__ = [
    'CheckInView',
    'CheckOutView',
    'GeofenceValidationView',
    'PayRateView',
    'FaceEnrollmentView',
    'ConveyanceViewSet',
]
