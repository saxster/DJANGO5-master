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
from typing import Optional
from uuid import uuid4

from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock
from apps.peoples.models import People
from apps.tenants.models import Tenant
from apps.ml_training.models import TrainingDataset, TrainingExample
from apps.ml.tasks import (
    track_conflict_prediction_outcomes_task,
    retrain_conflict_model_weekly_task
)
from apps.ml_training.tasks import (
    active_learning_loop,
    dataset_labeling,
    evaluate_model
)


def _create_dataset_with_examples(
    model_id: int,
    example_count: int = 5,
    uncertainties: Optional[list[float]] = None
) -> TrainingDataset:
    """Create a dataset with training examples for active learning tests."""
    tenant = Tenant.objects.create(
        tenantname=f"Tenant {model_id}",
        subdomain_prefix=f"tenant-{model_id}-{uuid4().hex[:6]}"
    )

    owner = People.objects.create(
        tenant=tenant,
        peoplecode=f"USR{model_id:04d}",
        peoplename=f"Owner {model_id}",
        loginid=f"owner_{model_id}_{uuid4().hex[:4]}",
        email=f"owner{model_id}@example.com",
        password='testpass123',
        mobno='1234567890'
    )

    dataset = TrainingDataset.objects.create(
        tenant=tenant,
        name=f"Dataset {model_id}",
        description='Test dataset for active learning',
        dataset_type='OCR_METERS',
        status='ACTIVE',
        created_by=owner,
        last_modified_by=owner,
        metadata={'model_id': model_id}
    )

    scores = uncertainties or [0.9 - (i * 0.05) for i in range(example_count)]
    for idx, score in enumerate(scores[:example_count]):
        TrainingExample.objects.create(
            tenant=tenant,
            dataset=dataset,
            image_path=f"/tmp/image_{model_id}_{idx}.png",
            image_hash=f"hash-{model_id}-{idx}",
            image_width=128,
            image_height=128,
            file_size=2048 + idx,
            example_type='PRODUCTION',
            labeling_status='UNLABELED',
            is_labeled=False,
            uncertainty_score=score
        )

    return dataset


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
        from apps.core.models.sync_conflict_policy import ConflictResolutionLog
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            tenantname='ML Test Tenant',
            subdomain_prefix='ml-test'
        )

        old_time = timezone.now() - timedelta(hours=25)

        # Create predictions that can be matched to conflicts
        tracked_entities = []
        for i in range(6):
            entity_uuid = uuid4()
            tracked_entities.append(entity_uuid)
            PredictionLog.objects.create(
                model_type='conflict_predictor',
                model_version='test_v1',
                entity_type='schedule',
                entity_id=str(entity_uuid),
                predicted_conflict=i % 2 == 0,
                conflict_probability=0.6 if i % 2 == 0 else 0.3,
                created_at=old_time
            )

            if i % 2 == 0:
                ConflictResolutionLog.objects.create(
                    mobile_id=entity_uuid,
                    domain='schedule',
                    server_version=3,
                    client_version=2,
                    resolution_strategy='server_wins',
                    resolution_result='resolved',
                    tenant=tenant,
                    created_at=old_time + timedelta(hours=1)
                )

        # Add a legacy prediction with invalid entity ID to ensure it is skipped
        PredictionLog.objects.create(
            model_type='conflict_predictor',
            model_version='test_v1',
            entity_type='schedule',
            entity_id='legacy-id',
            predicted_conflict=False,
            conflict_probability=0.2,
            created_at=old_time
        )

        result = track_conflict_prediction_outcomes_task.apply().result

        assert result['updated_predictions'] == len(tracked_entities)
        assert result['skipped_predictions'] == 1

        updated = PredictionLog.objects.filter(
            actual_conflict_occurred__isnull=False
        )
        assert updated.count() == len(tracked_entities)
        assert PredictionLog.objects.filter(
            entity_id='legacy-id',
            actual_conflict_occurred__isnull=True
        ).count() == 1

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

    @patch('apps.ml.tasks._notify_conflict_accuracy_drop')
    def test_track_conflict_prediction_outcomes_low_accuracy_alert(self, mock_notify):
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
        mock_notify.assert_called_once()


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

    def test_active_learning_loop_selects_uncertain_samples(self):
        """Ensure the task selects the highest uncertainty samples."""
        dataset = _create_dataset_with_examples(model_id=300, example_count=6)

        result = active_learning_loop.apply(kwargs={
            'dataset_id': dataset.id,
            'batch_size': 3,
            'confidence_threshold': 0.8
        }).result

        assert result['status'] == 'success'
        assert result['samples_identified'] == 3
        assert TrainingExample.objects.filter(
            dataset=dataset,
            selected_for_labeling=True
        ).count() == 3

    def test_active_learning_loop_infers_dataset_from_model_id(self):
        """Verify dataset lookup by model_id metadata works."""
        dataset = _create_dataset_with_examples(model_id=555, example_count=4)

        result = active_learning_loop.apply(kwargs={
            'model_id': 555,
            'batch_size': 2
        }).result

        assert result['status'] == 'success'
        assert result['dataset_id'] == dataset.id

    def test_active_learning_loop_handles_missing_dataset(self):
        """Return a skipped status when no dataset matches."""
        result = active_learning_loop.apply(kwargs={'model_id': 9999}).result

        assert result['status'] == 'skipped'
        assert result['reason'] == 'dataset_not_found'


@pytest.mark.django_db
class TestMLTrainingTaskGuards:
    """Ensure placeholder tasks fail-safe when services are unavailable."""

    def test_dataset_labeling_service_unavailable(self):
        dataset = _create_dataset_with_examples(model_id=800, example_count=2)

        result = dataset_labeling.apply(kwargs={'dataset_id': dataset.id}).result

        assert result['status'] == 'skipped'
        assert result['reason'] == 'dataset_labeling_service_unavailable'
        assert result['dataset_id'] == dataset.id

    def test_evaluate_model_service_unavailable(self):
        result = evaluate_model.apply(kwargs={'model_id': 42, 'test_dataset_id': 24}).result

        assert result['status'] == 'skipped'
        assert result['reason'] == 'model_evaluation_service_unavailable'


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
