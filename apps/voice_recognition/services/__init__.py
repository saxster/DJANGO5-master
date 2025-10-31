"""
Voice Recognition Services (Updated Sprint 2.4)

Service layer for voice biometric authentication including:
- Voice enrollment/onboarding with challenge-response
- Voice verification with anti-spoofing
- Multi-modal fusion with face recognition
- Fraud detection and risk scoring
- Resemblyzer speaker recognition (Sprint 2.4)
- Google Cloud Speech integration (Sprint 2.4)
"""

from .resemblyzer_service import ResemblyzerVoiceService
from .google_speech_service import GoogleSpeechService

__all__ = [
    # Sprint 2.4 - New services
    'ResemblyzerVoiceService',
    'GoogleSpeechService',

    # Existing services
    'VoiceEnrollmentService',
    'VoiceBiometricEngine',
    'VoiceAntiSpoofingService',
    'ChallengeResponseGenerator',
]