"""
Face Recognition API URL Configuration (Sprint 2.5)

URL patterns for face biometric REST API endpoints.
"""

from django.urls import path
from .views import (
    FaceEnrollmentView,
    FaceVerificationView,
    FaceQualityView,
    FaceLivenessView
)

app_name = 'face_recognition_api'

urlpatterns = [
    # Face enrollment
    path('enroll/', FaceEnrollmentView.as_view(), name='face-enroll'),

    # Face verification
    path('verify/', FaceVerificationView.as_view(), name='face-verify'),

    # Quality assessment
    path('quality/', FaceQualityView.as_view(), name='face-quality'),

    # Liveness detection
    path('liveness/', FaceLivenessView.as_view(), name='face-liveness'),
]
