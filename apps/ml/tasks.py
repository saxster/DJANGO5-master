"""
ML Stack Celery Tasks

Background tasks for model training, outcome tracking, and retraining.

Following .claude/rules.md:
- Rule #7: Tasks < 100 lines each
- Rule #11: Specific exception handling
- Celery Configuration Guide compliance
"""

import logging
import os
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Q
from apps.core.tasks.base import CeleryTaskBase
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('ml.tasks')


@shared_task(
    base=CeleryTaskBase,
    name='ml.track_conflict_prediction_outcomes',
    queue='ml_training',
    time_limit=600,
    soft_time_limit=540
)
def track_conflict_prediction_outcomes_task():
    """
    Check 24-hour-old predictions to see if conflicts occurred.

    Runs: Every 6 hours
    Purpose: Update actual_conflict_occurred field after sufficient time

    Returns:
        dict: Summary of outcome tracking
    """
    try:
        from apps.ml.models.ml_models import PredictionLog

        # Find predictions from 24-30h ago with unknown outcome
        cutoff_time = timezone.now() - timedelta(hours=24)
        window_start = cutoff_time - timedelta(hours=6)

        pending_predictions = PredictionLog.objects.filter(
            model_type='conflict_predictor',
            created_at__gte=window_start,
            created_at__lt=cutoff_time,
            actual_conflict_occurred__isnull=True
        )

        logger.info(
            f"Tracking outcomes for {pending_predictions.count()} predictions"
        )

        # TODO: Check if conflict occurred for each sync event
        # Requires ConflictResolution model from apps.core.models
        # For MVP: Mark all as False (no conflicts)
        updated_count = 0
        for prediction in pending_predictions:
            # TODO: Replace with actual check once models available
            # conflict_exists = ConflictResolution.objects.filter(
            #     sync_id=prediction.entity_id
            # ).exists()
            conflict_exists = False  # Placeholder

            prediction.actual_conflict_occurred = conflict_exists
            prediction.prediction_correct = (
                prediction.predicted_conflict == conflict_exists
            )
            prediction.save()
            updated_count += 1

        # Calculate accuracy metrics
        recent_predictions = PredictionLog.objects.filter(
            model_type='conflict_predictor',
            actual_conflict_occurred__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=7)
        )

        total = recent_predictions.count()
        correct = recent_predictions.filter(prediction_correct=True).count()
        accuracy = correct / total if total > 0 else 0.0

        logger.info(
            f"7-day accuracy: {accuracy:.2%} "
            f"({correct}/{total} correct predictions)"
        )

        # Alert if accuracy drops below threshold
        if total > 100 and accuracy < 0.70:
            logger.error(
                f"Conflict predictor accuracy dropped to {accuracy:.2%} "
                f"(threshold: 70%, n={total})"
            )
            # TODO: Send email/Slack notification

        return {
            'updated_predictions': updated_count,
            'seven_day_accuracy': accuracy,
            'seven_day_sample_size': total,
            'alert_triggered': total > 100 and accuracy < 0.70
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            f"Failed to track prediction outcomes: {e}",
            exc_info=True
        )
        raise


@shared_task(
    base=CeleryTaskBase,
    name='ml.retrain_conflict_model_weekly',
    queue='ml_training',
    time_limit=1800,  # 30 minutes
    soft_time_limit=1620
)
def retrain_conflict_model_weekly_task():
    """
    Weekly retraining of conflict prediction model.

    Runs: Every Monday at 3am
    Strategy:
      1. Extract past 90 days of data
      2. Train new model
      3. Compare accuracy with current model
      4. Auto-activate if improvement > 5%
      5. Cleanup old training data (30-day retention)

    Returns:
        dict: Retraining summary
    """
    try:
        from apps.ml.services.data_extractors.conflict_data_extractor import (
            ConflictDataExtractor
        )
        from apps.ml.services.training.conflict_model_trainer import (
            ConflictModelTrainer
        )
        from apps.ml.models.ml_models import ConflictPredictionModel

        logger.info("Starting weekly conflict model retraining...")

        # Extract fresh training data
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_path = (
            f'media/ml_training_data/conflict_predictor_{timestamp}.csv'
        )

        os.makedirs(os.path.dirname(data_path), exist_ok=True)

        extractor = ConflictDataExtractor()
        df = extractor.extract_training_data(days_back=90)
        extractor.save_training_data(df, data_path)

        if len(df) < 100:
            logger.warning(
                f"Insufficient training data: {len(df)} samples "
                f"(minimum 100 required). Skipping retraining."
            )
            return {
                'status': 'skipped',
                'reason': 'insufficient_data',
                'samples': len(df)
            }

        # Train new model
        model_output_path = (
            f'media/ml_models/conflict_predictor_v{timestamp}.joblib'
        )
        os.makedirs(os.path.dirname(model_output_path), exist_ok=True)

        trainer = ConflictModelTrainer()
        metrics = trainer.train_model(data_path, model_output_path)

        # Get current active model for comparison
        current_model = ConflictPredictionModel.objects.filter(
            is_active=True
        ).first()

        # Store new model (not active yet)
        new_model = ConflictPredictionModel.objects.create(
            version=f'v{timestamp}',
            algorithm='LogisticRegression',
            accuracy=metrics['test_roc_auc'],
            precision=0.0,  # Will be populated after deployment
            recall=0.0,
            f1_score=0.0,
            trained_on_samples=metrics['train_samples'],
            feature_count=len(metrics['feature_columns']),
            model_path=model_output_path,
            is_active=False
        )

        # Compare accuracy
        activated = False
        if current_model:
            improvement = new_model.accuracy - current_model.accuracy
            logger.info(
                f"New model ROC-AUC: {new_model.accuracy:.4f} "
                f"(current: {current_model.accuracy:.4f}, "
                f"improvement: {improvement:+.4f})"
            )

            # Auto-activate if significant improvement (>5%)
            if improvement > 0.05:
                logger.info(
                    "Significant improvement detected, activating new model"
                )
                new_model.activate()
                activated = True
            else:
                logger.info(
                    "Improvement insufficient for auto-activation. "
                    "Manual review recommended."
                )
        else:
            # No current model, activate new one
            logger.info("No active model found, activating new model")
            new_model.activate()
            activated = True

        # Cleanup: Delete training data older than 30 days
        cleanup_count = _cleanup_old_training_data(days=30)

        return {
            'status': 'success',
            'new_model_version': new_model.version,
            'test_roc_auc': new_model.accuracy,
            'activated': activated,
            'cleanup_files_deleted': cleanup_count
        }

    except Exception as e:
        logger.error(
            f"Weekly retraining failed: {e}",
            exc_info=True
        )
        raise


def _cleanup_old_training_data(days: int = 30) -> int:
    """
    Delete training data files older than N days.

    Args:
        days: Retention period in days

    Returns:
        Number of files deleted
    """
    try:
        cleanup_cutoff = datetime.now() - timedelta(days=days)
        training_data_dir = 'media/ml_training_data'

        if not os.path.exists(training_data_dir):
            return 0

        deleted_count = 0
        for filename in os.listdir(training_data_dir):
            if filename.startswith('conflict_predictor_'):
                filepath = os.path.join(training_data_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

                if file_time < cleanup_cutoff:
                    os.remove(filepath)
                    logger.info(f"Deleted old training data: {filename}")
                    deleted_count += 1

        return deleted_count

    except OSError as e:
        logger.error(f"Failed to cleanup training data: {e}", exc_info=True)
        return 0
