"""
Conflict Model Trainer

Train sklearn Logistic Regression on conflict data.

Following .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #11: Specific exception handling
"""

import logging
import joblib
import pandas as pd
from typing import Dict, Any
from datetime import datetime
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, classification_report, confusion_matrix
)
from sklearn.pipeline import Pipeline

logger = logging.getLogger('ml.training')


class ConflictModelTrainer:
    """Train and evaluate conflict prediction models."""

    FEATURE_COLUMNS = [
        'concurrent_editors',
        'hours_since_last_sync',
        'user_conflict_rate',
        'entity_edit_frequency',
        # 'field_overlap_score'  # Excluded: not available yet
    ]

    def train_model(
        self,
        data_path: str,
        model_output_path: str
    ) -> Dict[str, Any]:
        """
        Train logistic regression model on conflict data.

        Args:
            data_path: Path to training CSV
            model_output_path: Where to save trained model

        Returns:
            Training metrics dictionary

        Raises:
            FileNotFoundError: If data_path doesn't exist
            ValueError: If insufficient training data
        """
        # Load data
        try:
            df = pd.read_csv(data_path)
            logger.info(
                f"Loaded {len(df)} training samples from {data_path}"
            )
        except FileNotFoundError as e:
            logger.error(f"Training data not found: {data_path}")
            raise

        if len(df) < 100:
            raise ValueError(
                f"Insufficient training data: {len(df)} samples "
                f"(minimum 100 required)"
            )

        # Separate features and target
        X = df[self.FEATURE_COLUMNS]
        y = df['conflict_occurred']

        # Train/test split (80/20 with stratification)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(
            f"Train set: {len(X_train)} samples "
            f"({y_train.sum()} conflicts, {y_train.mean():.2%} positive)"
        )
        logger.info(
            f"Test set: {len(X_test)} samples "
            f"({y_test.sum()} conflicts, {y_test.mean():.2%} positive)"
        )

        # Create sklearn pipeline (scaling + logistic regression)
        model = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', LogisticRegression(
                class_weight='balanced',  # Handle imbalanced classes
                random_state=42,
                max_iter=1000
            ))
        ])

        # Train
        logger.info("Training logistic regression model...")
        model.fit(X_train, y_train)

        # Evaluate
        train_score = roc_auc_score(
            y_train, model.predict_proba(X_train)[:, 1]
        )
        test_score = roc_auc_score(
            y_test, model.predict_proba(X_test)[:, 1]
        )

        logger.info(f"Train ROC-AUC: {train_score:.4f}")
        logger.info(f"Test ROC-AUC: {test_score:.4f}")

        # Detailed metrics
        y_pred = model.predict(X_test)
        logger.info("\nClassification Report:")
        logger.info(classification_report(y_test, y_pred))
        logger.info("\nConfusion Matrix:")
        logger.info(confusion_matrix(y_test, y_pred))

        # Save model
        try:
            joblib.dump(model, model_output_path)
            logger.info(f"Model saved to {model_output_path}")
        except OSError as e:
            logger.error(
                f"Failed to save model to {model_output_path}: {e}",
                exc_info=True
            )
            raise

        # Return metrics for database storage
        metrics = {
            'train_roc_auc': float(train_score),
            'test_roc_auc': float(test_score),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'positive_rate': float(y.mean()),
            'model_path': model_output_path,
            'trained_at': datetime.now().isoformat(),
            'feature_columns': self.FEATURE_COLUMNS
        }

        return metrics
