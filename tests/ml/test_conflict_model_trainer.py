"""
Unit Tests for Conflict Model Trainer

Tests sklearn Logistic Regression training pipeline.

Coverage:
- Synthetic data training
- Model serialization/deserialization
- Accuracy metrics extraction
- Imbalanced class handling
- Edge cases

Follows .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
import os
import tempfile
import pandas as pd
import joblib
from apps.ml.services.training.conflict_model_trainer import (
    ConflictModelTrainer
)


class TestConflictModelTraining:
    """Test suite for conflict model training."""

    @pytest.mark.slow
    def test_train_model_on_synthetic_data(self):
        """Test model training on synthetic dataset with known pattern."""
        # Create synthetic training data
        df = create_synthetic_conflict_data(n_samples=1000, conflict_rate=0.1)

        trainer = ConflictModelTrainer()

        # Create temporary file for model
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_csv:
            csv_path = tmp_csv.name.replace('.joblib', '.csv')

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_model:
            model_path = tmp_model.name

        try:
            # Save synthetic data
            df.to_csv(csv_path, index=False)

            # Train model
            metrics = trainer.train_model(csv_path, model_path)

            # Verify metrics
            assert 'train_roc_auc' in metrics
            assert 'test_roc_auc' in metrics
            assert metrics['test_roc_auc'] > 0.70  # Should exceed 70%

            # Verify model file exists
            assert os.path.exists(model_path)

            # Verify metadata
            assert metrics['train_samples'] > 0
            assert metrics['test_samples'] > 0
            assert 0.0 < metrics['positive_rate'] < 1.0

        finally:
            # Cleanup
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(model_path):
                os.remove(model_path)

    @pytest.mark.slow
    def test_model_serialization_deserialization(self):
        """Test that trained model can be saved and loaded."""
        df = create_synthetic_conflict_data(n_samples=500)
        trainer = ConflictModelTrainer()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as tmp_csv:
            csv_path = tmp_csv.name

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_model:
            model_path = tmp_model.name

        try:
            df.to_csv(csv_path, index=False)
            metrics = trainer.train_model(csv_path, model_path)

            # Load model
            loaded_model = joblib.load(model_path)

            # Verify model can make predictions
            X_test = df[trainer.FEATURE_COLUMNS].head(5)
            predictions = loaded_model.predict(X_test)

            assert len(predictions) == 5
            assert all(pred in [0, 1] for pred in predictions)

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(model_path):
                os.remove(model_path)

    @pytest.mark.slow
    def test_imbalanced_class_handling(self):
        """Test that model handles imbalanced classes (10% positive)."""
        # Create highly imbalanced dataset (5% conflicts)
        df = create_synthetic_conflict_data(n_samples=1000, conflict_rate=0.05)

        trainer = ConflictModelTrainer()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as tmp_csv:
            csv_path = tmp_csv.name

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_model:
            model_path = tmp_model.name

        try:
            df.to_csv(csv_path, index=False)
            metrics = trainer.train_model(csv_path, model_path)

            # Model should still achieve reasonable performance
            # (class_weight='balanced' should help)
            assert metrics['test_roc_auc'] > 0.65

            # Verify positive rate matches expectation
            assert 0.03 < metrics['positive_rate'] < 0.07

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(model_path):
                os.remove(model_path)

    def test_insufficient_training_data_error(self):
        """Test that training fails with insufficient data (< 100 samples)."""
        # Create tiny dataset
        df = create_synthetic_conflict_data(n_samples=50)

        trainer = ConflictModelTrainer()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as tmp_csv:
            csv_path = tmp_csv.name

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_model:
            model_path = tmp_model.name

        try:
            df.to_csv(csv_path, index=False)

            # Should raise ValueError
            with pytest.raises(ValueError, match='Insufficient training data'):
                trainer.train_model(csv_path, model_path)

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(model_path):
                os.remove(model_path)

    def test_missing_training_file_error(self):
        """Test that training fails with missing CSV file."""
        trainer = ConflictModelTrainer()

        with pytest.raises(FileNotFoundError):
            trainer.train_model(
                '/nonexistent/path.csv',
                '/tmp/model.joblib'
            )

    @pytest.mark.slow
    def test_feature_columns_correct(self):
        """Test that model uses correct feature columns."""
        df = create_synthetic_conflict_data(n_samples=500)
        trainer = ConflictModelTrainer()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as tmp_csv:
            csv_path = tmp_csv.name

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_model:
            model_path = tmp_model.name

        try:
            df.to_csv(csv_path, index=False)
            metrics = trainer.train_model(csv_path, model_path)

            # Verify feature columns in metadata
            assert 'feature_columns' in metrics
            assert 'concurrent_editors' in metrics['feature_columns']
            assert 'hours_since_last_sync' in metrics['feature_columns']

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(model_path):
                os.remove(model_path)


class TestModelMetrics:
    """Test model metrics extraction."""

    @pytest.mark.slow
    def test_metrics_include_roc_auc(self):
        """Test that ROC-AUC is calculated and returned."""
        df = create_synthetic_conflict_data(n_samples=500)
        trainer = ConflictModelTrainer()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as tmp_csv:
            csv_path = tmp_csv.name

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_model:
            model_path = tmp_model.name

        try:
            df.to_csv(csv_path, index=False)
            metrics = trainer.train_model(csv_path, model_path)

            assert 0.0 <= metrics['train_roc_auc'] <= 1.0
            assert 0.0 <= metrics['test_roc_auc'] <= 1.0

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(model_path):
                os.remove(model_path)

    @pytest.mark.slow
    def test_metrics_include_sample_counts(self):
        """Test that train/test sample counts are returned."""
        df = create_synthetic_conflict_data(n_samples=500)
        trainer = ConflictModelTrainer()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as tmp_csv:
            csv_path = tmp_csv.name

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp_model:
            model_path = tmp_model.name

        try:
            df.to_csv(csv_path, index=False)
            metrics = trainer.train_model(csv_path, model_path)

            # 80/20 split
            assert metrics['train_samples'] == 400
            assert metrics['test_samples'] == 100

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            if os.path.exists(model_path):
                os.remove(model_path)


# ========== HELPER FUNCTIONS ==========

def create_synthetic_conflict_data(
    n_samples: int = 1000,
    conflict_rate: float = 0.1
) -> pd.DataFrame:
    """
    Create synthetic conflict prediction dataset with known pattern.

    Pattern:
    - High concurrent_editors -> high conflict probability
    - High hours_since_last_sync -> high conflict probability
    - High user_conflict_rate -> high conflict probability

    Args:
        n_samples: Number of samples to generate
        conflict_rate: Proportion of positive samples (conflicts)

    Returns:
        DataFrame with features and labels
    """
    import numpy as np

    np.random.seed(42)  # Reproducible

    # Feature ranges
    concurrent_editors = np.random.randint(0, 5, n_samples)
    hours_since_last_sync = np.random.uniform(0, 48, n_samples)
    user_conflict_rate = np.random.uniform(0, 0.5, n_samples)
    entity_edit_frequency = np.random.uniform(0, 10, n_samples)

    # Generate labels with pattern
    # conflict_prob = 0.05 + 0.15*concurrent + 0.10*hours/24 + 0.20*conflict_rate
    conflict_prob = (
        0.05
        + 0.15 * (concurrent_editors / 5)
        + 0.10 * (hours_since_last_sync / 48)
        + 0.20 * user_conflict_rate
    )

    # Add noise
    conflict_prob += np.random.normal(0, 0.05, n_samples)
    conflict_prob = np.clip(conflict_prob, 0, 1)

    # Generate binary labels
    conflict_occurred = (conflict_prob > 0.5).astype(int)

    # Adjust to target conflict rate
    n_conflicts = int(n_samples * conflict_rate)
    conflict_indices = np.argsort(conflict_prob)[-n_conflicts:]
    conflict_occurred = np.zeros(n_samples, dtype=int)
    conflict_occurred[conflict_indices] = 1

    # Create DataFrame
    df = pd.DataFrame({
        'concurrent_editors': concurrent_editors,
        'hours_since_last_sync': hours_since_last_sync,
        'user_conflict_rate': user_conflict_rate,
        'entity_edit_frequency': entity_edit_frequency,
        'conflict_occurred': conflict_occurred
    })

    return df
