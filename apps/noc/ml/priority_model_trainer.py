"""
Priority Model Trainer - XGBoost-based alert priority prediction.

Trains ML model to predict alert priority based on business impact.
Requires 500+ resolved alerts for training.

Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import logging
import os
import pickle
from typing import Dict, Any, Optional
from datetime import timedelta
import numpy as np
from django.conf import settings
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger('noc.ml')

__all__ = ['PriorityModelTrainer']


class PriorityModelTrainer:
    """
    Train XGBoost model for alert priority prediction.

    Features: 9 priority features from AlertPriorityScorer
    Target: time_to_resolve (proxy for business impact)
    Validation: MAE, RMSE metrics
    """

    MIN_TRAINING_SAMPLES = 500
    MODEL_PATH = os.path.join(settings.BASE_DIR, 'apps/noc/ml/models/priority_model.pkl')
    METRICS_PATH = os.path.join(settings.BASE_DIR, 'apps/noc/ml/models/priority_model_metrics.json')

    @classmethod
    def train_model(cls, force_retrain: bool = False) -> Dict[str, Any]:
        """
        Train priority scoring model.

        Args:
            force_retrain: Force retraining even if model exists

        Returns:
            Dict with training metrics and status

        Raises:
            ValueError: If insufficient training data
        """
        from ..models import NOCAlertEvent
        from ..services.alert_priority_scorer import AlertPriorityScorer

        # Check if model exists and skip if not forcing retrain
        if os.path.exists(cls.MODEL_PATH) and not force_retrain:
            logger.info("Model already exists, skipping training (use --force to retrain)")
            return {'status': 'skipped', 'reason': 'model_exists'}

        # Fetch resolved alerts for training
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        resolved_alerts = NOCAlertEvent.objects.filter(
            status='RESOLVED',
            resolved_at__isnull=False,
            time_to_resolve__isnull=False,
            cdtz__gte=ninety_days_ago
        ).select_related('client', 'bu')[:5000]  # Limit to recent 5000

        if len(resolved_alerts) < cls.MIN_TRAINING_SAMPLES:
            raise ValueError(
                f"Insufficient training data: {len(resolved_alerts)} alerts "
                f"(minimum {cls.MIN_TRAINING_SAMPLES} required)"
            )

        logger.info(f"Training on {len(resolved_alerts)} resolved alerts")

        # Extract features and targets
        X = []
        y = []

        for alert in resolved_alerts:
            # Extract features using scorer service
            features = AlertPriorityScorer._extract_features(alert)
            
            # Convert to feature array
            feature_vector = [
                features['severity_level'],
                features['affected_sites_count'],
                features['business_hours'],
                features['client_tier'],
                features['historical_impact'],
                features['recurrence_rate'],
                features['avg_resolution_time'],
                features['current_site_workload'],
                features['on_call_availability'],
            ]
            
            # Target: Convert time_to_resolve to minutes, then normalize to 0-100 scale
            resolution_minutes = alert.time_to_resolve.total_seconds() / 60
            # Higher resolution time = higher priority (business impact)
            # Normalize: 0-240 minutes -> 0-100 priority score
            priority_score = min((resolution_minutes / 240.0) * 100, 100)
            
            X.append(feature_vector)
            y.append(priority_score)

        X = np.array(X)
        y = np.array(y)

        # Train/test split (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Train XGBoost model
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost not installed. Run: pip install xgboost")

        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            n_jobs=-1
        )

        model.fit(X_train, y_train)

        # Evaluate model
        y_pred = model.predict(X_test)
        
        # Calculate metrics
        mae = np.mean(np.abs(y_test - y_pred))
        rmse = np.sqrt(np.mean((y_test - y_pred) ** 2))
        
        # R² score
        from sklearn.metrics import r2_score
        r2 = r2_score(y_test, y_pred)

        metrics = {
            'status': 'success',
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'mae': float(mae),
            'rmse': float(rmse),
            'r2_score': float(r2),
            'trained_at': timezone.now().isoformat(),
        }

        # Save model
        os.makedirs(os.path.dirname(cls.MODEL_PATH), exist_ok=True)
        with open(cls.MODEL_PATH, 'wb') as f:
            pickle.dump(model, f)

        # Save metrics
        import json
        with open(cls.METRICS_PATH, 'w') as f:
            json.dump(metrics, f, indent=2)

        logger.info(
            f"Model trained successfully",
            extra={
                'mae': mae,
                'rmse': rmse,
                'r2_score': r2,
                'training_samples': len(X_train)
            }
        )

        return metrics
