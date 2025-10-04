"""
ML Models for Conflict Prediction

Stores trained model metadata and predictions.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
"""

from django.db import models
from django.utils import timezone


class ConflictPredictionModel(models.Model):
    """Trained ML model metadata."""

    version = models.CharField(max_length=50, unique=True)
    algorithm = models.CharField(max_length=100)
    accuracy = models.FloatField(help_text="Model accuracy score")
    precision = models.FloatField(default=0.0)
    recall = models.FloatField(default=0.0)
    f1_score = models.FloatField(default=0.0)

    trained_on_samples = models.IntegerField()
    feature_count = models.IntegerField()

    model_path = models.CharField(max_length=500)
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ml_conflict_prediction_model'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.version} ({self.algorithm}) - {self.accuracy:.2%}"


class PredictionLog(models.Model):
    """Log of conflict predictions."""

    user = models.ForeignKey('peoples.People', on_delete=models.CASCADE)
    device_id = models.CharField(max_length=255)

    domain = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=255, null=True)

    predicted_conflict = models.BooleanField()
    conflict_probability = models.FloatField()
    risk_level = models.CharField(max_length=20)

    actual_conflict_occurred = models.BooleanField(null=True)
    prediction_correct = models.BooleanField(null=True)

    model_version = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ml_prediction_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['predicted_conflict']),
        ]