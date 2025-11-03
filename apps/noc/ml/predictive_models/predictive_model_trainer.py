"""
Predictive Model Trainer Base Class.

Common infrastructure for training XGBoost predictors with:
- Feature extraction
- Train/test split
- Imbalanced class handling (SMOTE)
- Model persistence
- Validation metrics

Part of Enhancement #5: Predictive Alerting Engine from NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md.

Follows .claude/rules.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling

@ontology(
    domain="noc",
    purpose="Base class for training XGBoost predictive models with imbalanced class handling",
    ml_framework="XGBoost",
    features=["SMOTE for class balancing", "train/test split", "validation metrics"],
    criticality="high",
    tags=["noc", "ml", "xgboost", "model-training"]
)
"""

import joblib
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from abc import ABC, abstractmethod
import numpy as np
from django.conf import settings
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

logger = logging.getLogger('noc.predictive.trainer')

__all__ = ['PredictiveModelTrainer']


class PredictiveModelTrainer(ABC):
    """
    Base class for training predictive models.

    Subclasses must implement:
    - extract_training_data() - Get historical data with labels
    - get_feature_names() - Return ordered list of feature names
    - get_model_path() - Return path to save trained model
    """

    TEST_SIZE = 0.2
    RANDOM_STATE = 42
    IMBALANCE_THRESHOLD = 0.3  # If minority class <30%, use SMOTE

    @abstractmethod
    def extract_training_data(self, days: int) -> Tuple[List[List[float]], List[int]]:
        """
        Extract training data from last N days.

        Args:
            days: Number of days of historical data to use

        Returns:
            (features, labels) - List of feature vectors and binary labels
        """
        pass

    @abstractmethod
    def get_feature_names(self) -> List[str]:
        """Return ordered list of feature names."""
        pass

    @abstractmethod
    def get_model_path(self) -> Path:
        """Return path to save trained model."""
        pass

    def train_model(self, days: int = 90, use_smote: bool = True) -> Dict[str, Any]:
        """
        Train XGBoost model on historical data.

        Args:
            days: Number of days of training data
            use_smote: Whether to use SMOTE for class balancing

        Returns:
            Dict with metrics: precision, recall, f1, auc, confusion_matrix

        Raises:
            ValueError: If insufficient training data
        """
        logger.info(f"Training {self.__class__.__name__} with {days} days of data")

        # Extract training data
        X, y = self.extract_training_data(days)

        if len(X) < 100:
            raise ValueError(f"Insufficient training data: {len(X)} samples (need at least 100)")

        X = np.array(X)
        y = np.array(y)

        # Check class balance
        class_ratio = sum(y) / len(y)
        logger.info(f"Class balance: {class_ratio:.2%} positive samples")

        # Apply SMOTE if imbalanced
        if use_smote and (class_ratio < self.IMBALANCE_THRESHOLD or class_ratio > (1 - self.IMBALANCE_THRESHOLD)):
            X, y = self._apply_smote(X, y)
            logger.info(f"Applied SMOTE, new sample count: {len(X)}")

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.TEST_SIZE, random_state=self.RANDOM_STATE, stratify=y
        )

        # Train XGBoost model
        model = self._train_xgboost(X_train, y_train)

        # Validate
        metrics = self._validate_model(model, X_test, y_test)

        # Save model
        self._save_model(model)

        logger.info(f"Model trained successfully: F1={metrics['f1']:.3f}, AUC={metrics['auc']:.3f}")
        return metrics

    def _apply_smote(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Apply SMOTE for class balancing."""
        try:
            from imblearn.over_sampling import SMOTE
            smote = SMOTE(random_state=self.RANDOM_STATE)
            X_resampled, y_resampled = smote.fit_resample(X, y)
            return X_resampled, y_resampled
        except ImportError:
            logger.warning("imblearn not available, skipping SMOTE")
            return X, y
        except ValueError as e:
            logger.warning(f"SMOTE failed: {e}, proceeding without resampling")
            return X, y

    def _train_xgboost(self, X_train: np.ndarray, y_train: np.ndarray):
        """Train XGBoost classifier."""
        try:
            import xgboost as xgb

            # Calculate scale_pos_weight for class imbalance
            neg_count = sum(y_train == 0)
            pos_count = sum(y_train == 1)
            scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                scale_pos_weight=scale_pos_weight,
                random_state=self.RANDOM_STATE,
                use_label_encoder=False,
                eval_metric='logloss'
            )

            model.fit(X_train, y_train)
            return model

        except ImportError:
            raise ImportError("XGBoost not installed. Install with: pip install xgboost")

    def _validate_model(self, model, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        """Validate model and return metrics."""
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        metrics = {
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'auc': roc_auc_score(y_test, y_pred_proba),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'test_samples': len(y_test),
            'feature_names': self.get_feature_names(),
        }

        return metrics

    def _save_model(self, model) -> None:
        """Save trained model to disk."""
        model_path = self.get_model_path()
        model_path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(model, model_path)
        logger.info(f"Model saved to {model_path}")
