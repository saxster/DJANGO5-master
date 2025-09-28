"""
Regression Prediction Models
ML-powered prediction of performance regressions and quality issues before release
"""

import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class RegressionPrediction(models.Model):
    """
    ML-based prediction of potential regressions for upcoming releases
    """
    PREDICTION_TYPES = [
        ('performance', 'Performance Regression'),
        ('visual', 'Visual Regression'),
        ('functional', 'Functional Regression'),
        ('crash', 'Crash/Stability'),
        ('memory', 'Memory Leak'),
        ('network', 'Network Issues'),
        ('battery', 'Battery Drain'),
        ('security', 'Security Vulnerability'),
    ]

    RISK_LEVELS = [
        ('low', 'Low Risk (0-30%)'),
        ('medium', 'Medium Risk (30-70%)'),
        ('high', 'High Risk (70-90%)'),
        ('critical', 'Critical Risk (90%+)'),
    ]

    PREDICTION_STATUS = [
        ('pending', 'Pending Validation'),
        ('validated', 'Validated'),
        ('false_positive', 'False Positive'),
        ('confirmed', 'Confirmed in Production'),
        ('mitigated', 'Mitigated'),
    ]

    ML_MODELS = [
        ('gradient_boosting', 'Gradient Boosting'),
        ('random_forest', 'Random Forest'),
        ('neural_network', 'Neural Network'),
        ('time_series', 'Time Series Analysis'),
        ('ensemble', 'Ensemble Model'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Prediction metadata
    prediction_type = models.CharField(max_length=20, choices=PREDICTION_TYPES)
    app_version = models.CharField(max_length=50, help_text="Target app version")
    build_number = models.CharField(max_length=50, blank=True)
    platform = models.CharField(max_length=20, default='all', help_text="android, ios, or all")

    # Risk assessment
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS)
    predicted_risk_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ML predicted risk score (0.0-1.0)"
    )
    confidence_level = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model confidence in prediction (0.0-1.0)"
    )

    # Prediction details
    title = models.CharField(max_length=200)
    description = models.TextField()
    affected_components = models.JSONField(
        default=list,
        help_text="List of components/features likely to be affected"
    )
    contributing_factors = models.JSONField(
        help_text="Factors contributing to the prediction"
    )

    # ML model information
    model_used = models.CharField(max_length=30, choices=ML_MODELS)
    model_version = models.CharField(max_length=20, default='1.0')
    feature_importance = models.JSONField(
        help_text="Feature importance scores from the ML model"
    )

    # Historical data context
    based_on_anomalies = models.ManyToManyField(
        'issue_tracker.AnomalySignature',
        blank=True,
        related_name='regression_predictions',
        help_text="Historical anomalies used for prediction"
    )
    training_data_timeframe = models.CharField(
        max_length=50,
        help_text="Timeframe of training data (e.g., '90 days', '6 months')"
    )
    similar_past_regressions = models.JSONField(
        default=list,
        help_text="References to similar past regressions"
    )

    # Validation and outcome
    status = models.CharField(max_length=20, choices=PREDICTION_STATUS, default='pending')
    actual_outcome = models.TextField(blank=True)
    validation_notes = models.TextField(blank=True)

    # Mitigation recommendations
    recommended_actions = models.JSONField(
        default=list,
        help_text="Recommended mitigation actions"
    )
    suggested_tests = models.JSONField(
        default=list,
        help_text="Suggested additional tests to run"
    )

    # Timeline
    predicted_at = models.DateTimeField(auto_now_add=True)
    target_release_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expected release date for the version"
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-predicted_risk_score', '-confidence_level', '-predicted_at']
        indexes = [
            models.Index(fields=['app_version', 'platform']),
            models.Index(fields=['prediction_type', 'risk_level']),
            models.Index(fields=['status', 'predicted_at']),
            models.Index(fields=['predicted_risk_score', 'confidence_level']),
            models.Index(fields=['target_release_date']),
        ]

    def __str__(self):
        return f"{self.prediction_type.title()} Risk - {self.app_version} ({self.risk_level})"

    @property
    def overall_risk_score(self):
        """Calculate weighted overall risk score"""
        return (self.predicted_risk_score * 0.7) + (self.confidence_level * 0.3)

    @property
    def is_actionable(self):
        """Determine if prediction requires immediate action"""
        return (self.risk_level in ['high', 'critical'] and
                self.confidence_level > 0.7 and
                self.status == 'pending')

    @property
    def days_to_release(self):
        """Calculate days until target release"""
        if not self.target_release_date:
            return None

        delta = self.target_release_date - timezone.now()
        return max(0, delta.days)

    @property
    def urgency_score(self):
        """Calculate urgency based on risk and time to release"""
        if not self.days_to_release:
            return self.overall_risk_score

        # Higher urgency if release is soon
        time_factor = max(0.1, min(1.0, 30 / (self.days_to_release + 1)))
        return self.overall_risk_score * time_factor

    def validate_prediction(self, outcome, notes="", status='validated'):
        """Update prediction with actual outcome"""
        self.actual_outcome = outcome
        self.validation_notes = notes
        self.status = status
        self.validated_at = timezone.now()
        self.save()

        # Update model performance metrics
        self._update_model_performance()

    def mark_mitigated(self, mitigation_actions, notes=""):
        """Mark prediction as mitigated with actions taken"""
        self.status = 'mitigated'
        self.validation_notes = f"Mitigated: {notes}"

        # Update recommended actions with what was actually done
        current_actions = self.recommended_actions or []
        current_actions.append({
            'type': 'mitigation_taken',
            'actions': mitigation_actions,
            'timestamp': timezone.now().isoformat()
        })
        self.recommended_actions = current_actions
        self.save()

    def _update_model_performance(self):
        """Update ML model performance based on validation"""
        # This would update the model accuracy metrics
        # Implementation would depend on ML infrastructure
        pass

    @classmethod
    def get_release_readiness_score(cls, app_version, platform='all'):
        """Calculate release readiness score for a version"""
        predictions = cls.objects.filter(
            app_version=app_version,
            platform=platform,
            status='pending'
        )

        if not predictions.exists():
            return 100.0  # No predictions = ready

        # Calculate weighted risk
        total_weight = 0
        weighted_risk = 0

        for prediction in predictions:
            weight = prediction.confidence_level
            total_weight += weight
            weighted_risk += prediction.predicted_risk_score * weight

        if total_weight == 0:
            return 100.0

        avg_risk = weighted_risk / total_weight
        readiness_score = (1.0 - avg_risk) * 100

        return max(0.0, min(100.0, readiness_score))

    @classmethod
    def get_critical_predictions(cls, days_ahead=7):
        """Get predictions requiring immediate attention"""
        target_date = timezone.now() + timezone.timedelta(days=days_ahead)

        return cls.objects.filter(
            target_release_date__lte=target_date,
            risk_level__in=['high', 'critical'],
            status='pending'
        ).order_by('-urgency_score')

    @classmethod
    def analyze_prediction_accuracy(cls, days=30):
        """Analyze ML model prediction accuracy over time"""

        # Get validated predictions
        validated_predictions = cls.objects.filter(
            predicted_at__gte=since_date,
            status__in=['validated', 'false_positive', 'confirmed']
        )

        if not validated_predictions.exists():
            return {'status': 'insufficient_data'}

        # Accuracy by prediction type
        accuracy_by_type = {}
        for pred_type, _ in cls.PREDICTION_TYPES:
            type_predictions = validated_predictions.filter(prediction_type=pred_type)
            if type_predictions.exists():
                accurate = type_predictions.filter(status='confirmed').count()
                total = type_predictions.count()
                accuracy_by_type[pred_type] = round((accurate / total) * 100, 1)

        # Overall accuracy
        total_validated = validated_predictions.count()
        confirmed = validated_predictions.filter(status='confirmed').count()
        overall_accuracy = round((confirmed / total_validated) * 100, 1)

        # False positive rate
        false_positives = validated_predictions.filter(status='false_positive').count()
        false_positive_rate = round((false_positives / total_validated) * 100, 1)

        # Model performance by confidence level
        high_confidence = validated_predictions.filter(confidence_level__gte=0.8)
        high_conf_accuracy = 0
        if high_confidence.exists():
            high_conf_confirmed = high_confidence.filter(status='confirmed').count()
            high_conf_accuracy = round((high_conf_confirmed / high_confidence.count()) * 100, 1)

        return {
            'overall_accuracy': overall_accuracy,
            'false_positive_rate': false_positive_rate,
            'high_confidence_accuracy': high_conf_accuracy,
            'accuracy_by_type': accuracy_by_type,
            'total_predictions': total_validated,
            'confirmed_predictions': confirmed,
            'analysis_period_days': days
        }


class ModelPerformanceMetrics(models.Model):
    """
    Track ML model performance over time for continuous improvement
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Model identification
    model_name = models.CharField(max_length=50, choices=RegressionPrediction.ML_MODELS)
    model_version = models.CharField(max_length=20)
    prediction_type = models.CharField(max_length=20, choices=RegressionPrediction.PREDICTION_TYPES)

    # Performance metrics
    accuracy_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    precision_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    recall_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    f1_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    auc_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )

    # Training data
    training_samples = models.IntegerField()
    validation_samples = models.IntegerField()
    feature_count = models.IntegerField()

    # Prediction performance
    false_positive_rate = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    false_negative_rate = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )

    # Time-based metrics
    measured_at = models.DateTimeField(auto_now_add=True)
    measurement_period_days = models.IntegerField(default=30)

    # Additional metadata
    hyperparameters = models.JSONField(default=dict)
    feature_importance_top10 = models.JSONField(default=list)

    class Meta:
        ordering = ['-measured_at']
        indexes = [
            models.Index(fields=['model_name', 'model_version']),
            models.Index(fields=['prediction_type', 'measured_at']),
            models.Index(fields=['accuracy_score', 'measured_at']),
        ]

    def __str__(self):
        return f"{self.model_name} v{self.model_version} - {self.prediction_type} (Acc: {self.accuracy_score:.2f})"

    @property
    def overall_performance_score(self):
        """Calculate weighted overall performance score"""
        return (
            self.accuracy_score * 0.3 +
            self.precision_score * 0.25 +
            self.recall_score * 0.25 +
            self.f1_score * 0.2
        )

    @classmethod
    def get_best_model(cls, prediction_type):
        """Get best performing model for a prediction type"""
        return cls.objects.filter(
            prediction_type=prediction_type
        ).order_by('-overall_performance_score').first()

    @classmethod
    def track_model_drift(cls, model_name, prediction_type, days=90):
        """Track performance drift over time"""
        from datetime import timedelta

        since_date = timezone.now() - timedelta(days=days)
        metrics = cls.objects.filter(
            model_name=model_name,
            prediction_type=prediction_type,
            measured_at__gte=since_date
        ).order_by('measured_at')

        if len(metrics) < 2:
            return {'status': 'insufficient_data'}

        # Calculate trend
        recent_performance = metrics.last().overall_performance_score
        baseline_performance = metrics.first().overall_performance_score

        drift = recent_performance - baseline_performance
        drift_percentage = (drift / baseline_performance) * 100

        return {
            'drift_percentage': round(drift_percentage, 2),
            'trend': 'improving' if drift > 0.05 else 'degrading' if drift < -0.05 else 'stable',
            'recent_performance': round(recent_performance, 3),
            'baseline_performance': round(baseline_performance, 3),
            'measurements_count': len(metrics)
        }