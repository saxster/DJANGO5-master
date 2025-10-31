"""
Biometric Authentication API URL Configuration (Sprint 2.5)

Unified URL routing for all biometric authentication endpoints:
- Face recognition (enrollment, verification, quality, liveness)
- Voice recognition (enrollment, verification, quality, challenge)

Base URL: /api/v1/biometrics/

Author: Development Team
Date: October 2025
"""

from django.urls import path, include

app_name = 'biometrics'

urlpatterns = [
    # Face recognition endpoints
    # /api/v1/biometrics/face/*
    path('face/', include('apps.face_recognition.api.urls')),

    # Voice recognition endpoints
    # /api/v1/biometrics/voice/*
    path('voice/', include('apps.voice_recognition.api.urls')),
]
