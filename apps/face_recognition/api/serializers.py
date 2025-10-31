"""
Face Recognition REST API Serializers (Sprint 2.6)

DRF serializers for biometric face recognition endpoints:
- Face enrollment
- Face verification
- Quality assessment
- Liveness detection

All serializers follow OpenAPI 3.0 specification for mobile code generation.

Author: Development Team
Date: October 2025
"""

from rest_framework import serializers
from apps.face_recognition.models import FaceEmbedding, FaceVerificationLog


class FaceEnrollmentSerializer(serializers.Serializer):
    """
    Serializer for face enrollment endpoint.

    Registers a new face embedding for a user with consent validation.
    """

    image = serializers.ImageField(
        required=True,
        help_text="Face image file (JPG, PNG). Face should be clearly visible."
    )
    user_id = serializers.IntegerField(
        required=True,
        help_text="User ID for enrollment"
    )
    consent_given = serializers.BooleanField(
        required=True,
        help_text="User consent for biometric data collection (GDPR/BIPA compliance)"
    )
    is_primary = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether this is the primary enrollment image"
    )

    def validate_image(self, value):
        """Validate image file."""
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image file too large (max 10MB)")

        # Check content type
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid image format. Allowed: {', '.join(allowed_types)}"
            )

        return value

    def validate_consent_given(self, value):
        """Validate user consent."""
        if not value:
            raise serializers.ValidationError(
                "User consent required for biometric data collection"
            )
        return value


class FaceEnrollmentResponseSerializer(serializers.Serializer):
    """Response serializer for face enrollment."""

    success = serializers.BooleanField()
    embedding_id = serializers.UUIDField(required=False)
    quality_score = serializers.FloatField(required=False)
    confidence_score = serializers.FloatField(required=False)
    message = serializers.CharField(required=False)
    quality_issues = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    recommendations = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )


class FaceVerificationSerializer(serializers.Serializer):
    """
    Serializer for face verification endpoint.

    Verifies a face image against enrolled embeddings.
    """

    image = serializers.ImageField(
        required=True,
        help_text="Face image to verify"
    )
    user_id = serializers.IntegerField(
        required=False,
        help_text="User ID to verify against (optional - can use embedding_id instead)"
    )
    embedding_id = serializers.UUIDField(
        required=False,
        help_text="Specific embedding ID to verify against (optional)"
    )
    enable_liveness = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Enable liveness detection (anti-spoofing)"
    )

    def validate(self, data):
        """Validate that either user_id or embedding_id is provided."""
        if not data.get('user_id') and not data.get('embedding_id'):
            raise serializers.ValidationError(
                "Either user_id or embedding_id must be provided"
            )
        return data


class FaceVerificationResponseSerializer(serializers.Serializer):
    """Response serializer for face verification."""

    verified = serializers.BooleanField()
    confidence = serializers.FloatField()
    similarity = serializers.FloatField()
    match_score = serializers.FloatField()
    threshold_met = serializers.BooleanField()
    fraud_risk_score = serializers.FloatField()
    fraud_indicators = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    quality_metrics = serializers.DictField(required=False)
    anti_spoofing_result = serializers.DictField(required=False)
    message = serializers.CharField(required=False)


class FaceQualityAssessmentSerializer(serializers.Serializer):
    """Serializer for face image quality assessment."""

    image = serializers.ImageField(
        required=True,
        help_text="Face image to assess"
    )


class FaceQualityAssessmentResponseSerializer(serializers.Serializer):
    """Response serializer for quality assessment."""

    overall_quality = serializers.FloatField()
    sharpness_score = serializers.FloatField()
    brightness_score = serializers.FloatField()
    contrast_score = serializers.FloatField()
    face_size_score = serializers.FloatField()
    quality_issues = serializers.ListField(child=serializers.CharField())
    improvement_suggestions = serializers.ListField(child=serializers.CharField())
    acceptable = serializers.BooleanField()


class LivenessDetectionSerializer(serializers.Serializer):
    """Serializer for liveness detection endpoint."""

    image = serializers.ImageField(
        required=True,
        help_text="Face image or video frame for liveness detection"
    )
    detection_type = serializers.ChoiceField(
        choices=['3d_depth', 'passive', 'challenge_response'],
        required=False,
        default='passive',
        help_text="Type of liveness detection to perform"
    )


class LivenessDetectionResponseSerializer(serializers.Serializer):
    """Response serializer for liveness detection."""

    liveness_detected = serializers.BooleanField()
    liveness_score = serializers.FloatField()
    detection_type = serializers.CharField()
    fraud_detected = serializers.BooleanField()
    fraud_indicators = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField(required=False)
