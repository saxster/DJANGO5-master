"""
Voice Recognition REST API Serializers (Sprint 2.6)

DRF serializers for biometric voice recognition endpoints:
- Voice enrollment
- Voice verification
- Audio quality assessment
- Challenge-response verification

All serializers follow OpenAPI 3.0 specification for mobile code generation.

Author: Development Team
Date: October 2025
"""

from rest_framework import serializers
from apps.voice_recognition.models import VoiceEmbedding, VoiceVerificationLog


class VoiceEnrollmentSerializer(serializers.Serializer):
    """
    Serializer for voice enrollment endpoint.

    Registers a new voiceprint for a user with consent validation.
    """

    audio = serializers.FileField(
        required=True,
        help_text="Audio file (WAV, MP3, M4A). Minimum 2 seconds of clear speech."
    )
    user_id = serializers.IntegerField(
        required=True,
        help_text="User ID for enrollment"
    )
    consent_given = serializers.BooleanField(
        required=True,
        help_text="User consent for biometric voice data collection (GDPR/BIPA compliance)"
    )
    is_primary = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether this is the primary voiceprint"
    )

    def validate_audio(self, value):
        """Validate audio file."""
        # Check file size (max 50MB)
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("Audio file too large (max 50MB)")

        # Check content type
        allowed_types = [
            'audio/wav', 'audio/wave', 'audio/x-wav',
            'audio/mpeg', 'audio/mp3',
            'audio/m4a', 'audio/mp4'
        ]
        if value.content_type and value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid audio format. Allowed: WAV, MP3, M4A"
            )

        return value

    def validate_consent_given(self, value):
        """Validate user consent."""
        if not value:
            raise serializers.ValidationError(
                "User consent required for voice biometric data collection"
            )
        return value


class VoiceEnrollmentResponseSerializer(serializers.Serializer):
    """Response serializer for voice enrollment."""

    success = serializers.BooleanField()
    voiceprint_id = serializers.UUIDField(required=False)
    quality_score = serializers.FloatField(required=False)
    confidence_score = serializers.FloatField(required=False)
    message = serializers.CharField(required=False)
    audio_quality = serializers.DictField(required=False)
    quality_issues = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    recommendations = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )


class VoiceVerificationSerializer(serializers.Serializer):
    """
    Serializer for voice verification endpoint.

    Verifies a voice sample against enrolled voiceprints.
    """

    audio = serializers.FileField(
        required=True,
        help_text="Audio file to verify"
    )
    user_id = serializers.IntegerField(
        required=False,
        help_text="User ID to verify against (optional - can use voiceprint_id instead)"
    )
    voiceprint_id = serializers.UUIDField(
        required=False,
        help_text="Specific voiceprint ID to verify against (optional)"
    )
    enable_anti_spoofing = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Enable anti-spoofing detection"
    )

    def validate(self, data):
        """Validate that either user_id or voiceprint_id is provided."""
        if not data.get('user_id') and not data.get('voiceprint_id'):
            raise serializers.ValidationError(
                "Either user_id or voiceprint_id must be provided"
            )
        return data


class VoiceVerificationResponseSerializer(serializers.Serializer):
    """Response serializer for voice verification."""

    verified = serializers.BooleanField()
    confidence = serializers.FloatField()
    similarity = serializers.FloatField()
    match_score = serializers.FloatField()
    threshold_met = serializers.BooleanField()
    fraud_risk_score = serializers.FloatField()
    spoof_detected = serializers.BooleanField(required=False)
    quality_metrics = serializers.DictField(required=False)
    message = serializers.CharField(required=False)


class VoiceChallengeRequestSerializer(serializers.Serializer):
    """Serializer for challenge generation request."""

    user_id = serializers.IntegerField(
        required=True,
        help_text="User ID for challenge generation"
    )
    challenge_type = serializers.ChoiceField(
        choices=['phrase', 'digits', 'words'],
        required=False,
        default='phrase',
        help_text="Type of challenge to generate"
    )


class VoiceChallengeResponseSerializer(serializers.Serializer):
    """Response serializer for challenge generation."""

    challenge_id = serializers.UUIDField()
    challenge_text = serializers.CharField()
    challenge_type = serializers.CharField()
    expires_at = serializers.DateTimeField()
    timeout_seconds = serializers.IntegerField()


class AudioQualityAssessmentSerializer(serializers.Serializer):
    """Serializer for audio quality assessment."""

    audio = serializers.FileField(
        required=True,
        help_text="Audio file to assess"
    )


class AudioQualityAssessmentResponseSerializer(serializers.Serializer):
    """Response serializer for audio quality assessment."""

    overall_quality = serializers.FloatField()
    snr_db = serializers.FloatField(help_text="Signal-to-noise ratio in dB")
    duration_seconds = serializers.FloatField()
    sample_rate = serializers.IntegerField()
    quality_issues = serializers.ListField(child=serializers.CharField())
    recommendations = serializers.ListField(child=serializers.CharField())
    acceptable = serializers.BooleanField()
