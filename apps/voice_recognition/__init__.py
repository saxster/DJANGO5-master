"""
Voice Recognition App - Voice Biometric Authentication

Provides comprehensive voice biometric authentication with:
- Voice embeddings (voiceprints) for speaker recognition
- Anti-spoofing and liveness detection
- Multi-modal fusion with face recognition
- Fraud detection and risk scoring
"""

default_app_config = 'apps.voice_recognition.apps.VoiceRecognitionConfig'

__all__ = [
    'VoiceEmbedding',
    'VoiceAntiSpoofingModel',
    'VoiceVerificationLog',
    'VoiceBiometricConfig',
]