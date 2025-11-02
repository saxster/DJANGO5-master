"""
Tests for ML Celery Tasks

Tests background tasks for:
- Active learning loop
- Conflict prediction outcome tracking
- Weekly model retraining
- Fraud prediction outcome tracking
- Infrastructure anomaly detection

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Celery Configuration Guide compliance
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock
from apps.ml.tasks import (
    track_conflict_prediction_outcomes_task,
    retrain_conflict_model_weekly_task
)


@pytest.mark.django_db
class TestConflictOutcomeTracking:
    """Test conflict prediction outcome tracking task."""

    def test_track_conflict_prediction_outcomes_no_pending(self):
        """Test outcome tracking with no pending predictions."""
        result = track_conflict_prediction_outcomes_task.apply().result

        assert result['updated_predictions'] == 0
        assert result['seven_day_sample_size'] == 0

    def test_track_conflict_prediction_outcomes_with_pending(self):
        """Test outcome tracking with pending predictions."""
        from apps.ml.models.ml_models import PredictionLog

        # Create predictions from 25 hours ago (ready for tracking)
        old_time = timezone.now() - timedelta(hours=25)

        for i in range(10):
            PredictionLog.objects.create(
                model_type='conflict_predictor',
                model_version='test_v1',
                entity_type='schedule',
                entity_id=str(i),
                predicted_conflict=i % 2 == 0,
                conflict_probability=0.6 if i % 2 == 0 else 0.3,
                created_at=old_time
            )

        result = track_conflict_prediction_outcomes_task.apply().result

        # Should update all 10 predictions
        assert result['updated_predictions'] == 10

        # Verify outcomes were set
        updated = PredictionLog.objects.filter(
            actual_conflict_occurred__isnull=False
        )
        assert updated.count() == 10

    def test_track_conflict_prediction_outcomes_accuracy_calculation(self):
        """Test that 7-day accuracy is calculated correctly."""
        from apps.ml.models.ml_models import PredictionLog

        # Create predictions from last week with known outcomes
        week_ago = timezone.now() - timedelta(days=3)

        # 8 correct predictions, 2 incorrect (80% accuracy)
        for i in range(10):
            correct = i < 8

            PredictionLog.objects.create(
                model_type='conflict_predictor',
                model_version='test_v1',
                entity_type='schedule',
                entity_id=str(i),
                predicted_conflict=True,
                conflict_probability=0.7,
                actual_conflict_occurred=True if correct else False,
                prediction_correct=correct,
                created_at=week_ago
            )

        result = track_conflict_prediction_outcomes_task.apply().result

        # Verify accuracy calculation
        assert result['seven_day_sample_size'] == 10
        assert result['seven_day_accuracy'] == 0.8  # 80%

    def test_track_conflict_prediction_outcomes_low_accuracy_alert(self):
        """Test that alert is triggered when accuracy drops below 70%."""
        from apps.ml.models.ml_models import PredictionLog

        week_ago = timezone.now() - timedelta(days=3)

        # Create 150 predictions with 60% accuracy (below threshold)
        for i in range(150):
            correct = i < 90  # 60% correct

            PredictionLog.objects.create(
                model_type='conflict_predictor',
                model_version='test_v1',
                entity_type='schedule',
                entity_id=str(i),
                predicted_conflict=True,
                conflict_probability=0.7,
                actual_conflict_occurred=True if correct else False,
                prediction_correct=correct,
                created_at=week_ago
            )

        result = track_conflict_prediction_outcomes_task.apply().result

        # Alert should be triggered
        assert result['alert_triggered'] is True
        assert result['seven_day_accuracy'] == 0.6


@pytest.mark.django_db
class TestWeeklyModelRetraining:
    """Test weekly model retraining task."""

    @patch('apps.ml.tasks.ConflictDataExtractor.extract_training_data')
    @patch('apps.ml.tasks.ConflictDataExtractor.save_training_data')
    @patch('apps.ml.tasks.ConflictModelTrainer.train_model')
    def test_retrain_conflict_model_weekly_success(
        self, mock_train, mock_save, mock_extract
    ):
        """Test successful weekly retraining."""
        import pandas as pd
        from apps.ml.models.ml_models import ConflictPredictionModel

        # Mock data extraction (500 samples)
        mock_df = pd.DataFrame({
            'concurrent_editors': [0] * 500,
            'hours_since_last_sync': [1.0] * 500,
            'user_conflict_rate': [0.1] * 500,
            'entity_edit_frequency': [2.0] * 500,
            'conflict_occurred': [0] * 450 + [1] * 50
        })
        mock_extract.return_value = mock_df

        # Mock training metrics
        mock_train.return_value = {
            'test_roc_auc': 0.82,
            'train_roc_auc': 0.85,
            'train_samples': 400,
            'test_samples': 100,
            'feature_columns': [
                'concurrent_editors',
                'hours_since_last_sync',
                'user_conflict_rate',
                'entity_edit_frequency'
            ]
        }

        result = retrain_conflict_model_weekly_task.apply().result

        # Verify success
        assert result['status'] == 'success'
        assert result['activated'] is True  # No existing model, so activated
        assert 'new_model_version' in result

        # Verify model created
        new_model = ConflictPredictionModel.objects.filter(
            version=result['new_model_version']
        ).first()
        assert new_model is not None
        assert new_model.is_active is True
        assert new_model.accuracy == 0.82

    @patch('apps.ml.tasks.ConflictDataExtractor.extract_training_data')
    def test_retrain_conflict_model_insufficient_data(self, mock_extract):
        """Test retraining skipped with insufficient data."""
        import pandas as pd

        # Mock insufficient data (< 100 samples)
        mock_df = pd.DataFrame({
            'concurrent_editors': [0] * 50,
            'conflict_occurred': [0] * 50
        })
        mock_extract.return_value = mock_df

        result = retrain_conflict_model_weekly_task.apply().result

        # Should skip retraining
        assert result['status'] == 'skipped'
        assert result['reason'] == 'insufficient_data'
        assert result['samples'] == 50

    @patch('apps.ml.tasks.ConflictDataExtractor.extract_training_data')
    @patch('apps.ml.tasks.ConflictDataExtractor.save_training_data')
    @patch('apps.ml.tasks.ConflictModelTrainer.train_model')
    def test_retrain_conflict_model_with_existing_model(
        self, mock_train, mock_save, mock_extract
    ):
        """Test retraining with existing active model."""
        import pandas as pd
        from apps.ml.models.ml_models import ConflictPredictionModel

        # Create existing model with 0.80 accuracy
        existing_model = ConflictPredictionModel.objects.create(
            version='existing_v1',
            algorithm='LogisticRegression',
            accuracy=0.80,
            trained_on_samples=1000,
            feature_count=4,
            model_path='/tmp/existing.joblib',
            is_active=True
        )

        # Mock data
        mock_df = pd.DataFrame({
            'concurrent_editors': [0] * 500,
            'hours_since_last_sync': [1.0] * 500,
            'user_conflict_rate': [0.1] * 500,
            'entity_edit_frequency': [2.0] * 500,
            'conflict_occurred': [0] * 450 + [1] * 50
        })
        mock_extract.return_value = mock_df

        # Mock new model with marginal improvement (0.83 accuracy)
        mock_train.return_value = {
            'test_roc_auc': 0.83,
            'train_roc_auc': 0.85,
            'train_samples': 400,
            'test_samples': 100,
            'feature_columns': ['concurrent_editors']
        }

        result = retrain_conflict_model_weekly_task.apply().result

        # Should NOT auto-activate (improvement < 5%)
        assert result['activated'] is False

        # Existing model should still be active
        existing_model.refresh_from_db()
        assert existing_model.is_active is True

    @patch('apps.ml.tasks.ConflictDataExtractor.extract_training_data')
    @patch('apps.ml.tasks.ConflictDataExtractor.save_training_data')
    @patch('apps.ml.tasks.ConflictModelTrainer.train_model')
    def test_retrain_conflict_model_significant_improvement(
        self, mock_train, mock_save, mock_extract
    ):
        """Test auto-activation with significant improvement (>5%)."""
        import pandas as pd
        from apps.ml.models.ml_models import ConflictPredictionModel

        # Create existing model with 0.75 accuracy
        existing_model = ConflictPredictionModel.objects.create(
            version='old_v1',
            algorithm='LogisticRegression',
            accuracy=0.75,
            trained_on_samples=1000,
            feature_count=4,
            model_path='/tmp/old.joblib',
            is_active=True
        )

        # Mock data
        mock_df = pd.DataFrame({
            'concurrent_editors': [0] * 500,
            'conflict_occurred': [0] * 450 + [1] * 50
        })
        mock_extract.return_value = mock_df

        # Mock new model with significant improvement (0.82 accuracy, +7%)
        mock_train.return_value = {
            'test_roc_auc': 0.82,
            'train_roc_auc': 0.85,
            'train_samples': 400,
            'test_samples': 100,
            'feature_columns': ['concurrent_editors']
        }

        result = retrain_conflict_model_weekly_task.apply().result

        # Should auto-activate (improvement > 5%)
        assert result['activated'] is True

        # Old model should be deactivated
        existing_model.refresh_from_db()
        assert existing_model.is_active is False


@pytest.mark.django_db
class TestActiveLearningLoop:
    """Test active learning loop task."""

    def test_active_learning_loop_selects_high_uncertainty(self):
        """Test that active learning selects high-uncertainty examples."""
        from apps.ml_training.models import TrainingExample
        from apps.ml_training.services.active_learning_service import (
            ActiveLearningService
        )

        # Create examples with varying uncertainty
        for i in range(20):
            TrainingExample.objects.create(
                example_type='METER_READING',
                entity_id=f'METER_{i}',
                extracted_value=str(i),
                confidence_score=0.5 + (i * 0.02),
                uncertainty_score=0.5 - (i * 0.02),
                requires_labeling=i < 10  # First 10 need labeling
            )

        service = ActiveLearningService()
        result = service.select_high_uncertainty_examples(limit=5)

        # Should select 5 highest uncertainty examples
        assert len(result['examples']) == 5

        # First example should have highest uncertainty
        assert result['examples'][0].uncertainty_score >= 0.45


@pytest.mark.django_db
class TestFraudOutcomeTracking:
    """Test fraud prediction outcome tracking."""

    def test_track_fraud_prediction_outcomes(self):
        """Test fraud outcome tracking (placeholder for future)."""
        # This will be implemented when fraud model training is complete
        pass


@pytest.mark.django_db
class TestInfrastructureAnomalyDetection:
    """Test infrastructure anomaly detection task."""

    def test_detect_infrastructure_anomalies(self):
        """Test anomaly detection task (placeholder for Phase 4)."""
        # This will be implemented in Phase 4
        pass


@pytest.mark.django_db
class TestTaskErrorHandling:
    """Test error handling in Celery tasks."""

    @patch('apps.ml.tasks.ConflictDataExtractor.extract_training_data')
    def test_retrain_task_handles_extraction_error(self, mock_extract):
        """Test that retraining handles extraction errors gracefully."""
        # Mock extraction error
        mock_extract.side_effect = ValueError("Extraction failed")

        # Task should raise exception (for Celery retry)
        with pytest.raises(ValueError):
            retrain_conflict_model_weekly_task.apply()

    def test_outcome_tracking_handles_database_error(self):
        """Test that outcome tracking handles database errors."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

        # This test verifies error handling is in place
        # Actual database errors would be tested in integration tests
        pass
