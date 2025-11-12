"""
Fraud Detection Model Registry.

Stores metadata for trained XGBoost fraud detection models.
Manages model versioning and activation per tenant.

Architecture:
- One active model per tenant at a time
- Models stored in media/ml_models/
- Performance metrics tracked for monitoring
- Supports A/B testing with model_version

Follows .claude/rules.md Rule #7: Model < 150 lines.
"""

from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
import logging

logger = logging.getLogger('noc.security_intelligence.models')


class FraudDetectionModel(BaseModel, TenantAwareModel):
    """
    Fraud detection model registry.

    Tracks trained XGBoost models for attendance fraud prediction.
    """

    model_version = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Model version identifier (e.g., 'v1_20251102_143000')"
    )

    model_path = models.CharField(
        max_length=500,
        help_text="Path to saved model file (.joblib)"
    )

    # Performance metrics (Precision-Recall focused for imbalanced data)
    pr_auc = models.FloatField(
        help_text="Precision-Recall AUC (target: >0.70)"
    )

    precision_at_80_recall = models.FloatField(
        help_text="Precision at 80% recall (target: >0.50)"
    )

    optimal_threshold = models.FloatField(
        default=0.5,
        help_text="Optimal decision threshold for classification"
    )

    # Training metadata
    train_samples = models.IntegerField(
        help_text="Number of training samples"
    )

    fraud_samples = models.IntegerField(
        default=0,
        help_text="Number of fraud samples in training set"
    )

    normal_samples = models.IntegerField(
        default=0,
        help_text="Number of normal samples in training set"
    )

    class_imbalance_ratio = models.FloatField(
        default=0.0,
        help_text="Fraud samples / Total samples (e.g., 0.01 = 1% fraud)"
    )

    # Activation status
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this model is active for predictions"
    )

    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When model was activated"
    )

    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When model was deactivated"
    )

    # Additional metrics
    metadata = models.JSONField(
        default=dict,
        help_text="Additional model metadata (feature importance, hyperparameters, etc.)"
    )

    training_duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Training duration in seconds"
    )

    xgboost_params = models.JSONField(
        default=dict,
        help_text="XGBoost hyperparameters used"
    )

    feature_importance = models.JSONField(
        default=dict,
        help_text="Feature importance scores"
    )

    class Meta(BaseModel.Meta):
        db_table = 'noc_fraud_detection_model'
        verbose_name = 'Fraud Detection Model'
        verbose_name_plural = 'Fraud Detection Models'
        ordering = ['-cdtz']
        unique_together = [['tenant', 'model_version']]
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['model_version']),
            models.Index(fields=['pr_auc']),
        ]

    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f"{self.model_version} ({status}) - PR-AUC: {self.pr_auc:.3f}"

    @transaction.atomic
    def activate(self):
        """
        Activate this model for the tenant.

        Deactivates all other models and sets this as active.
        Clears model cache to force reload.
        """
        try:
            # Deactivate all other models for this tenant
            FraudDetectionModel.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).exclude(id=self.id).update(
                is_active=False,
                deactivated_at=timezone.now()
            )

            # Activate this model
            self.is_active = True
            self.activated_at = timezone.now()
            self.save()

            # Clear model cache
            self.clear_model_cache()

            logger.info(
                f"Activated fraud detection model {self.model_version} "
                f"for tenant {self.tenant.schema_name}"
            )

            return True

        except (ValueError, AttributeError) as e:
            logger.error(f"Model activation error: {e}", exc_info=True)
            return False

    @classmethod
    def get_active_model(cls, tenant):
        """
        Get active fraud detection model for tenant.

        Args:
            tenant: Tenant instance

        Returns:
            FraudDetectionModel instance or None
        """
        try:
            return cls.objects.filter(
                tenant=tenant,
                is_active=True
            ).first()
        except (ValueError, AttributeError) as e:
            logger.error(f"Error fetching active model: {e}", exc_info=True)
            return None

    @classmethod
    def clear_model_cache(cls):
        """Clear cached model instances."""
        # Cache key format: fraud_model_{tenant_id}
        cache.delete_pattern('fraud_model_*')
        logger.info("Cleared fraud detection model cache")

    def get_performance_summary(self) -> dict:
        """
        Get model performance summary for dashboard.

        Returns:
            dict: Performance metrics and metadata
        """
        return {
            'model_version': self.model_version,
            'pr_auc': round(self.pr_auc, 3),
            'precision_at_80_recall': round(self.precision_at_80_recall, 3),
            'optimal_threshold': round(self.optimal_threshold, 3),
            'train_samples': self.train_samples,
            'fraud_samples': self.fraud_samples,
            'normal_samples': self.normal_samples,
            'class_imbalance_ratio': round(self.class_imbalance_ratio, 4),
            'is_active': self.is_active,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'training_duration_seconds': self.training_duration_seconds,
            'top_features': self._get_top_features(5),
        }

    def _get_top_features(self, n=5) -> list:
        """Get top N important features."""
        if not self.feature_importance:
            return []

        # Sort features by importance
        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {'feature': name, 'importance': round(score, 4)}
            for name, score in sorted_features[:n]
        ]
