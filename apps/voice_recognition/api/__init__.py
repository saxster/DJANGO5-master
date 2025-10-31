"""Voice Recognition REST API module."""

from .views import (
    VoiceEnrollmentView,
    VoiceVerificationView,
    VoiceQualityView,
    VoiceChallengeView
)

from .serializers import (
    VoiceEnrollmentSerializer,
    VoiceVerificationSerializer,
    AudioQualityAssessmentSerializer,
    VoiceChallengeRequestSerializer
)

__all__ = [
    # Views
    'VoiceEnrollmentView',
    'VoiceVerificationView',
    'VoiceQualityView',
    'VoiceChallengeView',

    # Serializers
    'VoiceEnrollmentSerializer',
    'VoiceVerificationSerializer',
    'AudioQualityAssessmentSerializer',
    'VoiceChallengeRequestSerializer',
]
