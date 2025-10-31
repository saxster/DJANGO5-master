"""
Voice Recognition API URL Configuration (Sprint 2.5)

URL patterns for voice biometric REST API endpoints.
"""

from django.urls import path
from .views import (
    VoiceEnrollmentView,
    VoiceVerificationView,
    VoiceQualityView,
    VoiceChallengeView
)

app_name = 'voice_recognition_api'

urlpatterns = [
    # Voice enrollment
    path('enroll/', VoiceEnrollmentView.as_view(), name='voice-enroll'),

    # Voice verification
    path('verify/', VoiceVerificationView.as_view(), name='voice-verify'),

    # Quality assessment
    path('quality/', VoiceQualityView.as_view(), name='voice-quality'),

    # Challenge generation
    path('challenge/', VoiceChallengeView.as_view(), name='voice-challenge'),
]
