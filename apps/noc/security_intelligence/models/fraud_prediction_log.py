"""
Fraud Prediction Log Model.

Records ML-based fraud predictions before attendance occurs.
Enables proactive fraud prevention.

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


class FraudPredictionLog(BaseModel, TenantAwareModel):
    """
    ML-based fraud prediction log.

    Predicts fraud probability before attendance occurs.
    """

    PREDICTION_TYPE_CHOICES = [
        ('ATTENDANCE', 'Attendance Fraud'),
        ('BIOMETRIC', 'Biometric Fraud'),
        ('GPS', 'GPS Spoofing'),
        ('BEHAVIORAL', 'Behavioral Anomaly'),
    ]

    RISK_LEVEL_CHOICES = [
        ('MINIMAL', 'Minimal Risk'),
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical Risk'),
    ]

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='fraud_predictions',
        help_text="Person for whom prediction was made"
    )

    site = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='fraud_predictions',
        help_text="Predicted site"
    )

    predicted_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When prediction was made"
    )

    prediction_type = models.CharField(
        max_length=20,
        choices=PREDICTION_TYPE_CHOICES,
        help_text="Type of fraud predicted"
    )

    fraud_probability = models.FloatField(
        help_text="Predicted fraud probability (0-1)"
    )

    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        db_index=True,
        help_text="Predicted risk level"
    )

    model_confidence = models.FloatField(
        help_text="ML model confidence (0-1)"
    )

    # Feature values used for prediction
    features_used = models.JSONField(
        default=dict,
        help_text="Feature values used in prediction"
    )

    # Behavioral baseline comparison
    baseline_deviation = models.FloatField(
        default=0.0,
        help_text="Deviation from behavioral baseline (0-1)"
    )

    anomaly_indicators = models.JSONField(
        default=list,
        help_text="List of anomaly indicators detected"
    )

    # Model metadata
    model_version = models.CharField(
        max_length=50,
        default='1.0',
        help_text="ML model version used"
    )

    model_type = models.CharField(
        max_length=50,
        default='automl_classifier',
        help_text="Type of ML model used"
    )

    # Conformal prediction confidence intervals (Phase 1 enhancement)
    prediction_lower_bound = models.FloatField(
        null=True,
        blank=True,
        help_text='Lower bound of prediction interval (90% coverage)'
    )
    prediction_upper_bound = models.FloatField(
        null=True,
        blank=True,
        help_text='Upper bound of prediction interval (90% coverage)'
    )
    confidence_interval_width = models.FloatField(
        null=True,
        blank=True,
        help_text='Width of confidence interval (upper - lower)'
    )
    calibration_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Conformal predictor calibration quality (0-1)'
    )

    # SHAP explainability (Phase 4, Feature 1)
    shap_values = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text='SHAP feature contributions for this prediction'
    )
    explanation_text = models.TextField(
        blank=True,
        help_text='Human-readable explanation (top contributing features)'
    )

    # Outcome tracking (for model improvement)
    actual_attendance_event = models.ForeignKey(
        'attendance.PeopleEventlog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fraud_predictions',
        help_text="Actual attendance event (if occurred)"
    )

    actual_fraud_detected = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether actual fraud was detected"
    )

    actual_fraud_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Actual fraud score from detection"
    )

    prediction_accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="Prediction accuracy (for feedback loop)"
    )

    # Actions taken
    preventive_action_taken = models.BooleanField(
        default=False,
        help_text="Whether preventive action was taken"
    )

    action_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of preventive action"
    )

    action_details = models.TextField(
        blank=True,
        help_text="Details of action taken"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_fraud_prediction_log'
        verbose_name = 'Fraud Prediction Log'
        verbose_name_plural = 'Fraud Prediction Logs'
        ordering = ['-predicted_at']
        indexes = [
            models.Index(fields=['tenant', 'predicted_at']),
            models.Index(fields=['person', 'predicted_at']),
            models.Index(fields=['risk_level', 'predicted_at']),
            models.Index(fields=['fraud_probability']),
            models.Index(fields=['actual_fraud_detected']),
            models.Index(
                fields=['confidence_interval_width'],
                name='fraud_pred_log_ci_width_idx'
            ),
        ]

    def __str__(self):
        return f"Prediction: {self.person.peoplename} - {self.risk_level} ({self.fraud_probability:.2f})"

    @property
    def is_narrow_interval(self):
        """
        Check if prediction has narrow confidence interval (high confidence).

        Narrow interval defined as width < 0.2, indicating high certainty.
        Used for human-out-of-loop automation eligibility.
        """
        if self.confidence_interval_width is None:
            return False
        return self.confidence_interval_width < 0.2

    def record_outcome(self, attendance_event, fraud_detected, fraud_score):
        """
        Record actual outcome for feedback loop.

        Args:
            attendance_event: Actual PeopleEventlog instance
            fraud_detected: bool
            fraud_score: float
        """
        self.actual_attendance_event = attendance_event
        self.actual_fraud_detected = fraud_detected
        self.actual_fraud_score = fraud_score

        prediction_diff = abs(self.fraud_probability - fraud_score)
        self.prediction_accuracy = 1.0 - min(prediction_diff, 1.0)

        self.save()

    @classmethod
    def get_prediction_accuracy_stats(cls, tenant, days=30):
        """Get prediction accuracy statistics."""
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)

        predictions = cls.objects.filter(
            tenant=tenant,
            predicted_at__gte=since,
            actual_fraud_detected__isnull=False
        )

        if predictions.count() == 0:
            return None

        from django.db.models import Avg, Count

        stats = predictions.aggregate(
            avg_accuracy=Avg('prediction_accuracy'),
            total_predictions=Count('id'),
            correct_predictions=Count('id', filter=models.Q(prediction_accuracy__gte=0.8))
        )

        return {
            'avg_accuracy': stats['avg_accuracy'],
            'total_predictions': stats['total_predictions'],
            'correct_predictions': stats['correct_predictions'],
            'accuracy_rate': stats['correct_predictions'] / stats['total_predictions'] * 100,
        }