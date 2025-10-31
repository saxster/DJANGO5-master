"""
Voice Recognition Models - Voice Biometric Authentication

Comprehensive voice biometric authentication system with:
- Voice embedding (voiceprint) storage
- Anti-spoofing and liveness detection
- Verification logging with fraud indicators
- Multi-modal support

Following .claude/rules.md:
- Rule #7: Model classes <150 lines (split into separate models)
- Rule #9: Specific exception handling
"""

from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class VoiceEmbedding(BaseModel, TenantAwareModel):
    """
    Voice embeddings (voiceprints) for registered users.

    Stores speaker embeddings extracted from voice samples for
    biometric authentication. Similar to face embeddings but for voice.

    Following .claude/rules.md Rule #7: <150 lines
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='voice_embeddings'
    )

    # Embedding data (512-dimensional vector typical for speaker recognition)
    embedding_vector = ArrayField(
        models.FloatField(),
        size=512,
        help_text="Voice embedding vector (voiceprint)"
    )

    # Source information
    source_audio_path = models.CharField(max_length=500, null=True, blank=True)
    source_audio_hash = models.CharField(max_length=64, null=True, blank=True)
    extraction_model_name = models.CharField(
        max_length=100,
        default='google-speaker-recognition',
        help_text="Model used to extract this voiceprint"
    )
    extraction_model_version = models.CharField(max_length=20, default='1.0')

    # Quality metrics
    voice_confidence = models.FloatField(
        help_text="Confidence of voice detection (0-1)"
    )
    audio_quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Quality score of source audio (0-1)"
    )
    snr_db = models.FloatField(
        null=True,
        blank=True,
        help_text="Signal-to-noise ratio in decibels"
    )

    # Language and context
    language_code = models.CharField(
        max_length=10,
        default='en-US',
        help_text="Language of voice sample"
    )
    sample_text = models.TextField(
        null=True,
        blank=True,
        help_text="Text spoken in the sample (if available)"
    )
    sample_duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Duration of audio sample in seconds"
    )

    # Embedding metadata
    extraction_timestamp = models.DateTimeField(auto_now_add=True)
    audio_features = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text="Additional audio features (pitch, tempo, etc.)"
    )

    # Status and validation
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary voiceprint for the user"
    )
    is_validated = models.BooleanField(
        default=False,
        help_text="Whether this voiceprint has been validated"
    )
    validation_score = models.FloatField(null=True, blank=True)

    # Usage statistics
    verification_count = models.IntegerField(default=0)
    successful_matches = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'voice_embedding'
        verbose_name = 'Voice Embedding'
        verbose_name_plural = 'Voice Embeddings'
        indexes = [
            models.Index(fields=['user', 'is_primary']),
            models.Index(fields=['extraction_model_name', 'is_validated']),
            models.Index(fields=['language_code', 'is_validated']),
        ]

    def __str__(self):
        return f"Voice Embedding: {self.user.username} ({self.language_code})"


class VoiceAntiSpoofingModel(BaseModel, TenantAwareModel):
    """
    Voice anti-spoofing models for liveness detection.

    Tracks different anti-spoofing techniques used to detect:
    - Playback attacks
    - AI-generated voices (deepfakes)
    - Voice conversion/modification
    - Text-to-speech synthesis

    Following .claude/rules.md Rule #7: <150 lines
    """

    class ModelType(models.TextChoices):
        PLAYBACK_DETECTION = ('PLAYBACK_DETECTION', 'Playback Detection')
        DEEPFAKE_DETECTION = ('DEEPFAKE_DETECTION', 'Deepfake Detection')
        CHANNEL_ANALYSIS = ('CHANNEL_ANALYSIS', 'Channel Analysis')
        ACOUSTIC_FINGERPRINT = ('ACOUSTIC_FINGERPRINT', 'Acoustic Fingerprinting')
        LIVENESS_CHALLENGE = ('LIVENESS_CHALLENGE', 'Challenge-Response')
        MULTI_MODAL = ('MULTI_MODAL', 'Multi-modal Detection')

    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(max_length=30, choices=ModelType.choices)
    version = models.CharField(max_length=20, default='1.0')

    # Detection thresholds
    liveness_threshold = models.FloatField(
        default=0.5,
        help_text="Threshold for liveness classification"
    )
    spoof_threshold = models.FloatField(
        default=0.7,
        help_text="Threshold for spoof detection"
    )

    # Performance metrics
    true_positive_rate = models.FloatField(null=True, blank=True)
    false_positive_rate = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    # Model configuration
    model_file_path = models.CharField(max_length=500, null=True, blank=True)
    requires_challenge_response = models.BooleanField(
        default=False,
        help_text="Whether model requires challenge-response interaction"
    )
    supported_languages = ArrayField(
        models.CharField(max_length=10),
        default=list,
        help_text="Supported language codes"
    )

    # Usage statistics
    detection_count = models.BigIntegerField(default=0)
    spoof_detections = models.BigIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = 'voice_anti_spoofing_model'
        verbose_name = 'Voice Anti-Spoofing Model'
        verbose_name_plural = 'Voice Anti-Spoofing Models'
        indexes = [
            models.Index(fields=['cdtz'], name='v_antispoof_cdtz_idx'),
            models.Index(fields=['mdtz'], name='v_antispoof_mdtz_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.model_type})"


class VoiceVerificationLog(BaseModel, TenantAwareModel):
    """
    Detailed log of voice verification attempts with fraud indicators.

    Enhanced version for comprehensive voice biometric authentication tracking.
    Stores verification results, confidence scores, quality metrics, and
    anti-spoofing analysis.

    Following .claude/rules.md Rule #7: <150 lines
    """

    class VerificationResult(models.TextChoices):
        SUCCESS = ('SUCCESS', 'Verification Successful')
        FAILED = ('FAILED', 'Verification Failed')
        ERROR = ('ERROR', 'Verification Error')
        REJECTED = ('REJECTED', 'Rejected by Anti-spoofing')
        NO_VOICE = ('NO_VOICE', 'No Voice Detected')
        POOR_QUALITY = ('POOR_QUALITY', 'Poor Audio Quality')

    # Verification context
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # Verification details
    verification_timestamp = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=20, choices=VerificationResult.choices)

    # Matched embedding
    matched_embedding = models.ForeignKey(
        VoiceEmbedding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Similarity metrics
    similarity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Voice similarity score (0-1)"
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall confidence in verification (0-1)"
    )

    # Anti-spoofing results
    liveness_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Liveness detection score (0-1)"
    )
    spoof_detected = models.BooleanField(default=False)
    spoof_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of spoofing detected (e.g., PLAYBACK, DEEPFAKE)"
    )

    # Audio analysis
    input_audio_path = models.CharField(max_length=500, null=True, blank=True)
    input_audio_hash = models.CharField(max_length=64, null=True, blank=True)
    audio_quality_score = models.FloatField(null=True, blank=True)
    audio_duration_seconds = models.FloatField(null=True, blank=True)
    snr_db = models.FloatField(null=True, blank=True, help_text="Signal-to-noise ratio")

    # Challenge-response (if applicable)
    challenge_phrase = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Challenge phrase used for liveness detection"
    )
    challenge_matched = models.BooleanField(
        default=False,
        help_text="Whether spoken phrase matched challenge"
    )

    # Performance metrics
    processing_time_ms = models.FloatField(null=True, blank=True)

    # Error information
    error_message = models.TextField(null=True, blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)

    # Detailed analysis
    verification_metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Detailed verification metadata"
    )

    # Fraud indicators
    fraud_indicators = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Detected fraud indicators"
    )
    fraud_risk_score = models.FloatField(
        default=0.0,
        help_text="Calculated fraud risk score (0-1)"
    )

    # Device and context
    device_id = models.CharField(max_length=100, null=True, blank=True)
    device_info = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Device information"
    )

    class Meta(BaseModel.Meta):
        db_table = 'voice_verification_log'
        verbose_name = 'Voice Verification Log'
        verbose_name_plural = 'Voice Verification Logs'
        indexes = [
            models.Index(fields=['user', 'verification_timestamp']),
            models.Index(fields=['result', 'verification_timestamp']),
            models.Index(fields=['fraud_risk_score', 'spoof_detected']),
            models.Index(fields=['device_id', 'verification_timestamp']),
        ]

    def __str__(self):
        return f"{self.result}: {self.user.username} @ {self.verification_timestamp}"


class VoiceBiometricConfig(BaseModel, TenantAwareModel):
    """
    Configuration for voice biometric authentication system.

    System-wide and per-user voice biometric settings including
    thresholds, anti-spoofing configuration, and language preferences.

    Following .claude/rules.md Rule #7: <150 lines
    """

    class ConfigType(models.TextChoices):
        SYSTEM = ('SYSTEM', 'System Configuration')
        SECURITY = ('SECURITY', 'Security Settings')
        PERFORMANCE = ('PERFORMANCE', 'Performance Settings')
        USER_PREFERENCE = ('USER_PREFERENCE', 'User Preferences')

    name = models.CharField(max_length=100, unique=True)
    config_type = models.CharField(max_length=20, choices=ConfigType.choices)
    description = models.TextField()

    # Configuration data
    config_data = models.JSONField(
        encoder=DjangoJSONEncoder,
        help_text="Configuration parameters"
    )

    # Scope
    applies_to_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        help_text="Users this configuration applies to (empty = all users)"
    )
    applies_to_locations = ArrayField(
        models.CharField(max_length=100),
        blank=True,
        default=list,
        help_text="Location codes this configuration applies to"
    )

    # Status
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=100,
        help_text="Configuration priority (lower = higher priority)"
    )

    # Validation
    last_validated = models.DateTimeField(null=True, blank=True)
    validation_errors = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=list,
        help_text="Configuration validation errors"
    )

    # Usage tracking
    applied_count = models.IntegerField(default=0)
    last_applied = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'voice_biometric_config'
        verbose_name = 'Voice Biometric Configuration'
        verbose_name_plural = 'Voice Biometric Configurations'
        ordering = ['priority', 'name']

    def __str__(self):
        return f"{self.name} ({self.config_type})"