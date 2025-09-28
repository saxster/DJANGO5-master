from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class FaceRecognitionModel(BaseModel, TenantAwareModel):
    """Face recognition models registry and configuration"""
    
    class ModelType(models.TextChoices):
        FACENET512 = ('FACENET512', 'FaceNet512')
        ARCFACE = ('ARCFACE', 'ArcFace')
        INSIGHTFACE = ('INSIGHTFACE', 'InsightFace')
        ENSEMBLE = ('ENSEMBLE', 'Ensemble Model')
        CUSTOM = ('CUSTOM', 'Custom Model')
    
    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Active')
        INACTIVE = ('INACTIVE', 'Inactive')
        TRAINING = ('TRAINING', 'Training')
        DEPRECATED = ('DEPRECATED', 'Deprecated')
    
    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(max_length=20, choices=ModelType.choices)
    version = models.CharField(max_length=20, default='1.0')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE.value)
    
    # Model configuration
    similarity_threshold = models.FloatField(
        default=0.3,
        help_text="Cosine distance threshold for face matching"
    )
    confidence_threshold = models.FloatField(
        default=0.7,
        help_text="Minimum confidence for face detection"
    )
    
    # Anti-spoofing configuration
    liveness_detection_enabled = models.BooleanField(default=True)
    liveness_threshold = models.FloatField(
        default=0.5,
        help_text="Threshold for liveness detection"
    )
    
    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True, help_text="Model accuracy (0-1)")
    false_acceptance_rate = models.FloatField(null=True, blank=True)
    false_rejection_rate = models.FloatField(null=True, blank=True)
    processing_time_ms = models.FloatField(null=True, blank=True)
    
    # Model files
    model_file_path = models.CharField(max_length=500, null=True, blank=True)
    weights_file_path = models.CharField(max_length=500, null=True, blank=True)
    
    # Usage statistics
    verification_count = models.BigIntegerField(default=0)
    successful_verifications = models.BigIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Model metadata
    training_dataset_info = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Information about training dataset"
    )
    hyperparameters = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Model hyperparameters"
    )

    class Meta(BaseModel.Meta):
        db_table = 'face_recognition_model'
        verbose_name = 'Face Recognition Model'
        verbose_name_plural = 'Face Recognition Models'
    
    def __str__(self):
        return f"{self.name} ({self.model_type})"


class FaceEmbedding(BaseModel, TenantAwareModel):
    """Face embeddings for registered users"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='face_embeddings'
    )
    
    # Embedding data
    embedding_vector = ArrayField(
        models.FloatField(),
        size=512,  # Default for FaceNet512, adjust as needed
        help_text="Face embedding vector"
    )
    
    # Source information
    source_image_path = models.CharField(max_length=500, null=True, blank=True)
    source_image_hash = models.CharField(max_length=64, null=True, blank=True)
    extraction_model = models.ForeignKey(
        FaceRecognitionModel,
        on_delete=models.PROTECT,
        help_text="Model used to extract this embedding"
    )
    
    # Quality metrics
    face_confidence = models.FloatField(
        help_text="Confidence of face detection (0-1)"
    )
    image_quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Quality score of source image (0-1)"
    )
    
    # Embedding metadata
    extraction_timestamp = models.DateTimeField(auto_now_add=True)
    face_landmarks = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text="Detected face landmarks"
    )
    
    # Status and validation
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary embedding for the user"
    )
    is_validated = models.BooleanField(
        default=False,
        help_text="Whether this embedding has been validated"
    )
    validation_score = models.FloatField(null=True, blank=True)
    
    # Usage statistics
    verification_count = models.IntegerField(default=0)
    successful_matches = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'face_embedding'
        verbose_name = 'Face Embedding'
        verbose_name_plural = 'Face Embeddings'
        indexes = [
            models.Index(fields=['user', 'is_primary']),
            models.Index(fields=['extraction_model', 'is_validated']),
        ]
    
    def __str__(self):
        return f"Face Embedding: {self.user.username} ({self.extraction_model.name})"


class FaceVerificationLog(BaseModel, TenantAwareModel):
    """Detailed log of face verification attempts"""
    
    class VerificationResult(models.TextChoices):
        SUCCESS = ('SUCCESS', 'Verification Successful')
        FAILED = ('FAILED', 'Verification Failed')
        ERROR = ('ERROR', 'Verification Error')
        REJECTED = ('REJECTED', 'Rejected by Anti-spoofing')
        NO_FACE = ('NO_FACE', 'No Face Detected')
        MULTIPLE_FACES = ('MULTIPLE_FACES', 'Multiple Faces Detected')
    
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
    
    # Model and embedding used
    verification_model = models.ForeignKey(
        FaceRecognitionModel,
        on_delete=models.PROTECT
    )
    matched_embedding = models.ForeignKey(
        FaceEmbedding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Similarity metrics
    similarity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Similarity score (1 - cosine distance)"
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall confidence in verification"
    )
    
    # Anti-spoofing results
    liveness_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Liveness detection score"
    )
    spoof_detected = models.BooleanField(default=False)
    
    # Image analysis
    input_image_path = models.CharField(max_length=500, null=True, blank=True)
    input_image_hash = models.CharField(max_length=64, null=True, blank=True)
    face_detection_confidence = models.FloatField(null=True, blank=True)
    
    # Performance metrics
    processing_time_ms = models.FloatField(null=True, blank=True)
    model_load_time_ms = models.FloatField(null=True, blank=True)
    
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

    class Meta(BaseModel.Meta):
        db_table = 'face_verification_log'
        verbose_name = 'Face Verification Log'
        verbose_name_plural = 'Face Verification Logs'
        indexes = [
            models.Index(fields=['user', 'verification_timestamp']),
            models.Index(fields=['result', 'verification_timestamp']),
            models.Index(fields=['fraud_risk_score', 'spoof_detected']),
        ]
    
    def __str__(self):
        return f"{self.result}: {self.user.username} @ {self.verification_timestamp}"


class AntiSpoofingModel(BaseModel, TenantAwareModel):
    """Anti-spoofing models for liveness detection"""
    
    class ModelType(models.TextChoices):
        TEXTURE_BASED = ('TEXTURE_BASED', 'Texture-based')
        MOTION_BASED = ('MOTION_BASED', 'Motion-based')
        DEPTH_BASED = ('DEPTH_BASED', 'Depth-based')
        CHALLENGE_RESPONSE = ('CHALLENGE_RESPONSE', 'Challenge-Response')
        MULTI_MODAL = ('MULTI_MODAL', 'Multi-modal')
    
    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(max_length=20, choices=ModelType.choices)
    version = models.CharField(max_length=20, default='1.0')
    
    # Detection thresholds
    liveness_threshold = models.FloatField(
        default=0.5,
        help_text="Threshold for liveness classification"
    )
    
    # Performance metrics
    true_positive_rate = models.FloatField(null=True, blank=True)
    false_positive_rate = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    
    # Model configuration
    model_file_path = models.CharField(max_length=500, null=True, blank=True)
    requires_motion = models.BooleanField(
        default=False,
        help_text="Whether model requires motion detection"
    )
    requires_user_interaction = models.BooleanField(
        default=False,
        help_text="Whether model requires user interaction"
    )
    
    # Usage statistics
    detection_count = models.BigIntegerField(default=0)
    spoof_detections = models.BigIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = 'anti_spoofing_model'
        verbose_name = 'Anti-Spoofing Model'
        verbose_name_plural = 'Anti-Spoofing Models'
    
    def __str__(self):
        return f"{self.name} ({self.model_type})"


class FaceRecognitionConfig(BaseModel, TenantAwareModel):
    """Configuration for face recognition system"""
    
    class ConfigType(models.TextChoices):
        SYSTEM = ('SYSTEM', 'System Configuration')
        SECURITY = ('SECURITY', 'Security Settings')
        PERFORMANCE = ('PERFORMANCE', 'Performance Settings')
        INTEGRATION = ('INTEGRATION', 'Integration Settings')
    
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
        db_table = 'face_recognition_config'
        verbose_name = 'Face Recognition Configuration'
        verbose_name_plural = 'Face Recognition Configurations'
        ordering = ['priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.config_type})"


class FaceQualityMetrics(BaseModel):
    """Face image quality assessment metrics"""
    
    image_path = models.CharField(max_length=500, unique=True)
    image_hash = models.CharField(max_length=64, unique=True)
    
    # Quality scores (0-1, higher is better)
    overall_quality = models.FloatField(help_text="Overall image quality score")
    sharpness_score = models.FloatField(help_text="Image sharpness score")
    brightness_score = models.FloatField(help_text="Brightness adequacy score")
    contrast_score = models.FloatField(help_text="Contrast adequacy score")
    
    # Face-specific quality
    face_size_score = models.FloatField(help_text="Face size adequacy score")
    face_pose_score = models.FloatField(help_text="Face pose quality score")
    eye_visibility_score = models.FloatField(help_text="Eye visibility score")
    
    # Technical metrics
    resolution_width = models.IntegerField()
    resolution_height = models.IntegerField()
    file_size_bytes = models.BigIntegerField()
    
    # Detection metadata
    face_detection_confidence = models.FloatField()
    landmark_quality = models.JSONField(
        encoder=DjangoJSONEncoder,
        help_text="Quality of detected landmarks"
    )
    
    # Analysis metadata
    analysis_timestamp = models.DateTimeField(auto_now_add=True)
    analysis_model_version = models.CharField(max_length=50, default='1.0')
    
    # Recommendations
    quality_issues = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Identified quality issues"
    )
    improvement_suggestions = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=list,
        help_text="Suggestions for improvement"
    )

    class Meta:
        db_table = 'face_quality_metrics'
        verbose_name = 'Face Quality Metrics'
        verbose_name_plural = 'Face Quality Metrics'
        indexes = [
            models.Index(fields=['overall_quality', 'analysis_timestamp']),
            models.Index(fields=['image_hash']),
        ]
    
    def __str__(self):
        return f"Quality: {self.overall_quality:.2f} - {self.image_path}"