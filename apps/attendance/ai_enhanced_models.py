"""
AI-Enhanced Models for Advanced Attendance Management
Extends existing attendance models with AI capabilities
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from datetime import timedelta


class AIAttendanceRecord(BaseModel, TenantAwareModel):
    """Enhanced attendance record with comprehensive AI analytics"""
    
    class VerificationStatus(models.TextChoices):
        PENDING = ('PENDING', 'Pending Verification')
        VERIFIED = ('VERIFIED', 'AI Verified')
        FAILED = ('FAILED', 'Verification Failed')
        SUSPICIOUS = ('SUSPICIOUS', 'Flagged as Suspicious')
        MANUAL_REVIEW = ('MANUAL_REVIEW', 'Requires Manual Review')
    
    class BiometricModality(models.TextChoices):
        FACE = ('FACE', 'Face Recognition')
        VOICE = ('VOICE', 'Voice Recognition')
        BEHAVIORAL = ('BEHAVIORAL', 'Behavioral Biometrics')
        MULTI_MODAL = ('MULTI_MODAL', 'Multi-Modal')
    
    # Link to original attendance record
    attendance_record = models.OneToOneField(
        'attendance.PeopleEventlog',
        on_delete=models.CASCADE,
        related_name='ai_enhancement'
    )
    
    # AI Verification Results
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING.value
    )
    
    primary_modality = models.CharField(
        max_length=20,
        choices=BiometricModality.choices,
        default=BiometricModality.FACE.value
    )
    
    modalities_used = ArrayField(
        models.CharField(max_length=20, choices=BiometricModality.choices),
        default=list,
        help_text="All biometric modalities used for verification"
    )
    
    # Confidence and Quality Metrics
    overall_confidence = models.FloatField(
        default=0.0,
        help_text="Overall verification confidence (0-1)"
    )
    
    face_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Face recognition confidence (0-1)"
    )
    
    voice_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Voice recognition confidence (0-1)"
    )
    
    behavioral_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Behavioral biometrics confidence (0-1)"
    )
    
    image_quality_score = models.FloatField(
        default=0.0,
        help_text="Input image quality score (0-1)"
    )
    
    liveness_score = models.FloatField(
        default=0.0,
        help_text="Liveness detection score (0-1)"
    )
    
    # Fraud and Security Analysis
    fraud_risk_score = models.FloatField(
        default=0.0,
        help_text="Calculated fraud risk score (0-1)"
    )
    
    security_alerts = ArrayField(
        models.CharField(max_length=100),
        default=list,
        help_text="Security alerts triggered during verification"
    )
    
    anomaly_indicators = ArrayField(
        models.CharField(max_length=100),
        default=list,
        help_text="Behavioral or technical anomaly indicators"
    )
    
    # Technical Metrics
    processing_time_ms = models.FloatField(
        default=0.0,
        help_text="Total processing time in milliseconds"
    )
    
    model_versions = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Versions of AI models used"
    )
    
    # Detailed Analysis Results
    face_analysis = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text="Detailed face recognition analysis"
    )
    
    voice_analysis = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text="Detailed voice recognition analysis"
    )
    
    behavioral_analysis = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text="Detailed behavioral analysis"
    )
    
    quality_analysis = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Comprehensive quality analysis"
    )
    
    # Environmental Context
    device_info = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Device and browser information"
    )
    
    location_context = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Location and environmental context"
    )
    
    temporal_context = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Temporal patterns and context"
    )
    
    # Review and Validation
    requires_manual_review = models.BooleanField(
        default=False,
        help_text="Whether this record requires manual review"
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_ai_attendance'
    )
    
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    review_notes = models.TextField(blank=True)
    
    # AI Recommendations
    ai_recommendations = ArrayField(
        models.CharField(max_length=200),
        default=list,
        help_text="AI-generated recommendations"
    )
    
    improvement_suggestions = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=list,
        help_text="Suggestions for improving verification accuracy"
    )
    
    class Meta(BaseModel.Meta):
        db_table = 'ai_attendance_record'
        verbose_name = 'AI Attendance Record'
        verbose_name_plural = 'AI Attendance Records'
        indexes = [
            models.Index(fields=['verification_status', 'createdon']),
            models.Index(fields=['fraud_risk_score', 'createdon']),
            models.Index(fields=['requires_manual_review', 'createdon']),
            models.Index(fields=['overall_confidence', 'verification_status']),
        ]
    
    def __str__(self):
        return f"AI Record: {self.attendance_record.people.peoplename if self.attendance_record.people else 'Unknown'} - {self.verification_status}"
    
    @property
    def is_high_risk(self) -> bool:
        """Check if this is a high-risk attendance record"""
        return self.fraud_risk_score >= 0.6 or len(self.security_alerts) > 0
    
    @property
    def verification_quality_grade(self) -> str:
        """Get quality grade based on confidence and quality scores"""
        avg_score = (self.overall_confidence + self.image_quality_score + self.liveness_score) / 3
        
        if avg_score >= 0.9:
            return 'A+'
        elif avg_score >= 0.8:
            return 'A'
        elif avg_score >= 0.7:
            return 'B'
        elif avg_score >= 0.6:
            return 'C'
        else:
            return 'D'


class PredictiveAttendanceInsight(BaseModel, TenantAwareModel):
    """Predictive insights for attendance patterns"""
    
    class InsightType(models.TextChoices):
        ATTENDANCE_PREDICTION = ('ATTENDANCE_PREDICTION', 'Attendance Prediction')
        FRAUD_RISK_PREDICTION = ('FRAUD_RISK_PREDICTION', 'Fraud Risk Prediction')
        BEHAVIORAL_ANOMALY = ('BEHAVIORAL_ANOMALY', 'Behavioral Anomaly')
        SYSTEM_OPTIMIZATION = ('SYSTEM_OPTIMIZATION', 'System Optimization')
        USER_ENGAGEMENT = ('USER_ENGAGEMENT', 'User Engagement')
    
    class ConfidenceLevel(models.TextChoices):
        LOW = ('LOW', 'Low (0-60%)')
        MEDIUM = ('MEDIUM', 'Medium (60-80%)')
        HIGH = ('HIGH', 'High (80-95%)')
        VERY_HIGH = ('VERY_HIGH', 'Very High (95%+)')
    
    # Prediction Details
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="User this prediction applies to (null for system-wide)"
    )
    
    insight_type = models.CharField(
        max_length=30,
        choices=InsightType.choices
    )
    
    prediction_date = models.DateTimeField(
        help_text="Date/time for which prediction is made"
    )
    
    prediction_horizon_hours = models.IntegerField(
        default=24,
        help_text="Prediction horizon in hours"
    )
    
    # Prediction Results
    predicted_value = models.FloatField(
        help_text="Predicted numerical value"
    )
    
    confidence_score = models.FloatField(
        help_text="Prediction confidence (0-1)"
    )
    
    confidence_level = models.CharField(
        max_length=10,
        choices=ConfidenceLevel.choices
    )
    
    # Supporting Data
    input_features = models.JSONField(
        encoder=DjangoJSONEncoder,
        help_text="Features used to generate prediction"
    )
    
    model_metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Metadata about the model used"
    )
    
    historical_context = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Historical context informing the prediction"
    )
    
    # Prediction Validation
    actual_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Actual value when known (for validation)"
    )
    
    prediction_accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="Calculated accuracy once actual value is known"
    )
    
    validated_at = models.DateTimeField(null=True, blank=True)
    
    # Actionable Insights
    recommended_actions = ArrayField(
        models.CharField(max_length=200),
        default=list,
        help_text="Recommended actions based on prediction"
    )
    
    impact_assessment = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Assessment of potential impact"
    )
    
    business_context = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Business context and implications"
    )
    
    class Meta(BaseModel.Meta):
        db_table = 'predictive_attendance_insight'
        verbose_name = 'Predictive Attendance Insight'
        verbose_name_plural = 'Predictive Attendance Insights'
        indexes = [
            models.Index(fields=['insight_type', 'prediction_date']),
            models.Index(fields=['user', 'prediction_date']),
            models.Index(fields=['confidence_level', 'createdon']),
            models.Index(fields=['prediction_date', 'confidence_score']),
        ]
    
    def __str__(self):
        user_str = f" for {self.user.username}" if self.user else " (System-wide)"
        return f"{self.insight_type}{user_str} - {self.prediction_date}"
    
    @property
    def is_accurate_prediction(self) -> bool:
        """Check if prediction was accurate (if validated)"""
        if self.actual_value is not None and self.prediction_accuracy is not None:
            return self.prediction_accuracy >= 0.8
        return False
    
    @property
    def days_until_prediction(self) -> int:
        """Days until prediction date"""
        delta = self.prediction_date - timezone.now()
        return max(0, delta.days)


class AIModelPerformanceMetrics(BaseModel, TenantAwareModel):
    """Track performance metrics for AI models"""
    
    class ModelType(models.TextChoices):
        FACE_RECOGNITION = ('FACE_RECOGNITION', 'Face Recognition')
        DEEPFAKE_DETECTION = ('DEEPFAKE_DETECTION', 'Deepfake Detection')
        LIVENESS_DETECTION = ('LIVENESS_DETECTION', 'Liveness Detection')
        VOICE_RECOGNITION = ('VOICE_RECOGNITION', 'Voice Recognition')
        BEHAVIORAL_ANALYSIS = ('BEHAVIORAL_ANALYSIS', 'Behavioral Analysis')
        FRAUD_DETECTION = ('FRAUD_DETECTION', 'Fraud Detection')
        ANOMALY_DETECTION = ('ANOMALY_DETECTION', 'Anomaly Detection')
    
    # Model Identification
    model_name = models.CharField(max_length=100)
    model_type = models.CharField(max_length=30, choices=ModelType.choices)
    model_version = models.CharField(max_length=50)
    measurement_date = models.DateTimeField(auto_now_add=True)
    measurement_period_hours = models.IntegerField(default=24)
    
    # Performance Metrics
    accuracy = models.FloatField(help_text="Model accuracy (0-1)")
    precision = models.FloatField(help_text="Model precision (0-1)")
    recall = models.FloatField(help_text="Model recall (0-1)")
    f1_score = models.FloatField(help_text="F1 score (0-1)")
    
    # Error Rates
    false_positive_rate = models.FloatField(help_text="False positive rate (0-1)")
    false_negative_rate = models.FloatField(help_text="False negative rate (0-1)")
    
    # Performance Metrics
    avg_processing_time_ms = models.FloatField(help_text="Average processing time")
    p95_processing_time_ms = models.FloatField(help_text="95th percentile processing time")
    max_processing_time_ms = models.FloatField(help_text="Maximum processing time")
    
    # Volume Metrics
    total_predictions = models.BigIntegerField(help_text="Total predictions made")
    successful_predictions = models.BigIntegerField(help_text="Successful predictions")
    failed_predictions = models.BigIntegerField(help_text="Failed predictions")
    
    # Resource Usage
    avg_cpu_usage_percent = models.FloatField(default=0.0)
    avg_memory_usage_mb = models.FloatField(default=0.0)
    avg_gpu_usage_percent = models.FloatField(default=0.0)
    
    # Quality Metrics
    input_quality_distribution = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Distribution of input quality scores"
    )
    
    confidence_distribution = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Distribution of confidence scores"
    )
    
    # Detailed Analysis
    performance_breakdown = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Detailed performance breakdown"
    )
    
    error_analysis = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Analysis of errors and failures"
    )
    
    # Trends and Comparisons
    trend_vs_previous = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Performance trend compared to previous period"
    )
    
    benchmark_comparison = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Comparison with benchmark performance"
    )
    
    class Meta(BaseModel.Meta):
        db_table = 'ai_model_performance_metrics'
        verbose_name = 'AI Model Performance Metrics'
        verbose_name_plural = 'AI Model Performance Metrics'
        indexes = [
            models.Index(fields=['model_type', 'measurement_date']),
            models.Index(fields=['model_name', 'model_version']),
            models.Index(fields=['accuracy', 'measurement_date']),
        ]
        unique_together = ['model_name', 'model_version', 'measurement_date']
    
    def __str__(self):
        return f"{self.model_name} v{self.model_version} - {self.measurement_date.date()}"
    
    @property
    def overall_health_score(self) -> float:
        """Calculate overall model health score"""
        # Weighted combination of key metrics
        health_score = (
            self.accuracy * 0.3 +
            self.f1_score * 0.2 +
            (1 - self.false_positive_rate) * 0.2 +
            (1 - self.false_negative_rate) * 0.2 +
            min(1.0, 1000.0 / max(self.avg_processing_time_ms, 1)) * 0.1
        )
        return min(1.0, max(0.0, health_score))
    
    @property
    def performance_grade(self) -> str:
        """Get performance grade"""
        score = self.overall_health_score
        if score >= 0.95:
            return 'A+'
        elif score >= 0.90:
            return 'A'
        elif score >= 0.80:
            return 'B'
        elif score >= 0.70:
            return 'C'
        else:
            return 'D'


class AttendanceAuditTrail(BaseModel, TenantAwareModel):
    """Comprehensive audit trail for attendance records with AI insights"""
    
    class ActionType(models.TextChoices):
        CREATE = ('CREATE', 'Record Created')
        UPDATE = ('UPDATE', 'Record Updated')
        VERIFY = ('VERIFY', 'AI Verification')
        REVIEW = ('REVIEW', 'Manual Review')
        APPROVE = ('APPROVE', 'Approved')
        REJECT = ('REJECT', 'Rejected')
        FLAG = ('FLAG', 'Flagged for Review')
        EXPORT = ('EXPORT', 'Exported')
    
    # Record References
    attendance_record = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.CASCADE,
        related_name='audit_trail'
    )
    
    ai_record = models.ForeignKey(
        AIAttendanceRecord,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='audit_trail'
    )
    
    # Action Details
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    action_timestamp = models.DateTimeField(auto_now_add=True)
    
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User who performed the action (null for system actions)"
    )
    
    system_component = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="System component that performed the action"
    )
    
    # Change Details
    changes_made = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Detailed changes made"
    )
    
    previous_values = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="Previous values before change"
    )
    
    new_values = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        help_text="New values after change"
    )
    
    # Context Information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    session_id = models.CharField(max_length=255, null=True, blank=True)
    
    # AI Context
    ai_confidence_at_action = models.FloatField(
        null=True,
        blank=True,
        help_text="AI confidence score at time of action"
    )
    
    ai_recommendations = ArrayField(
        models.CharField(max_length=200),
        default=list,
        help_text="AI recommendations at time of action"
    )
    
    # Compliance and Notes
    reason = models.TextField(
        blank=True,
        help_text="Reason for the action"
    )
    
    compliance_notes = models.TextField(
        blank=True,
        help_text="Notes related to compliance requirements"
    )
    
    business_justification = models.TextField(
        blank=True,
        help_text="Business justification for the action"
    )
    
    class Meta(BaseModel.Meta):
        db_table = 'attendance_audit_trail'
        verbose_name = 'Attendance Audit Trail'
        verbose_name_plural = 'Attendance Audit Trails'
        indexes = [
            models.Index(fields=['attendance_record', 'action_timestamp']),
            models.Index(fields=['action_type', 'action_timestamp']),
            models.Index(fields=['performed_by', 'action_timestamp']),
        ]
    
    def __str__(self):
        user_str = f"by {self.performed_by.username}" if self.performed_by else "by System"
        return f"{self.action_type} {user_str} - {self.action_timestamp}"