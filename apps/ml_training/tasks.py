"""
ML Training Platform - Celery Tasks

@ontology(
    domain="ml_ops",
    purpose="Background tasks for ML model training, dataset labeling, and active learning loops",
    task_categories=[
        "Model training (heavyweight, ml_training queue)",
        "Dataset labeling (AI-assisted, ai_processing queue)",
        "Active learning loops (ai_processing queue)",
        "Model evaluation (ai_processing queue)",
        "Feature extraction (heavy_compute queue)"
    ],
    queue_routing={
        "train_model": "ml_training queue (priority 0 - lowest)",
        "active_learning_loop": "ai_processing queue (priority 1)",
        "dataset_labeling": "ai_processing queue (priority 1)",
        "evaluate_model": "ai_processing queue (priority 1)"
    },
    integration_points=[
        "apps/ml_training/services/active_learning_service.py",
        "apps/ml_training/services/dataset_ingestion_service.py",
        "apps/ml_training/services/feedback_integration_service.py"
    ],
    criticality="low",
    dependencies=["scikit-learn", "TensorFlow/PyTorch (optional)", "Celery", "WebSocketBroadcastTask"],
    tags=["ml", "training", "active-learning", "dataset-labeling", "ml-ops"]
)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone as dt_timezone

from celery import shared_task
from django.conf import settings

from apps.core.tasks.websocket_broadcast import WebSocketBroadcastTask
from apps.core.tasks.base import TaskMetrics
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.exceptions.patterns import CELERY_EXCEPTIONS


logger = logging.getLogger("ml_training.tasks")


@shared_task(
    base=WebSocketBroadcastTask,
    bind=True,
    name='apps.ml_training.tasks.train_model',
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
    time_limit=3600 * 4,  # 4 hours hard limit
    soft_time_limit=3600 * 3,  # 3 hours soft limit
)
def train_model(
    self,
    dataset_id: int,
    model_type: str,
    hyperparameters: Dict[str, Any],
    user_id: Optional[int] = None
):
    """
    Train ML model on dataset (heavyweight task).

    Routes to: ml_training queue (priority 0 - lowest)

    Args:
        dataset_id: Dataset ID to train on
        model_type: Model type ('anomaly_detector', 'classifier', 'regressor')
        hyperparameters: Model hyperparameters
        user_id: Optional user ID to notify on completion

    Returns:
        dict: Training results (model_id, metrics, training_time)

    Example:
        train_model.apply_async(
            args=[123, 'anomaly_detector', {'threshold': 0.8}],
            queue='ml_training',
            priority=0
        )
    """
    logger.info(f"Starting model training: dataset={dataset_id}, type={model_type}")

    try:
        # Broadcast training started
        if user_id:
            self.broadcast_task_progress(
                user_id=user_id,
                task_name=f'ML Model Training ({model_type})',
                progress=0.0,
                status='in_progress',
                message='Initializing training pipeline'
            )

        # Trigger training via orchestrator (NO blocking time.sleep()!)
        from apps.ml_training.services.training_orchestrator import TrainingOrchestrator

        # Progress callback for WebSocket broadcasts
        def progress_callback(pct, msg):
            if user_id:
                self.broadcast_task_progress(
                    user_id=user_id,
                    task_name=f'ML Model Training ({model_type})',
                    progress=pct,
                    message=msg
                )

        # Trigger training (external platform or in-process)
        result = TrainingOrchestrator.trigger_training(
            dataset_id=dataset_id,
            model_type=model_type,
            hyperparameters=hyperparameters,
            progress_callback=progress_callback
        )

        # Broadcast completion
        status = result.get('status', 'unknown')
        message = result.get('message', 'Training completed')

        if user_id:
            self.broadcast_task_progress(
                user_id=user_id,
                task_name=f'ML Model Training ({model_type})',
                progress=100.0,
                status='completed',
                message=message
            )

        # Record metrics
        TaskMetrics.increment_counter('ml_model_trained', {
            'model_type': model_type,
        })
        TaskMetrics.record_timing('ml_training_duration', result['training_time_seconds'] * 1000, {
            'model_type': model_type
        })

        logger.info(f"Model training complete: model_id={result['model_id']}, accuracy={result['accuracy']}")

        return result

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error during model training: {e}", exc_info=True)
        raise self.retry(exc=e)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Error training model: {e}", exc_info=True)
        if user_id:
            self.broadcast_task_progress(
                user_id=user_id,
                task_name=f'ML Model Training ({model_type})',
                progress=0.0,
                status='failed',
                message=f'Training failed: {str(e)[:100]}'
            )
        raise


@shared_task(
    base=WebSocketBroadcastTask,
    bind=True,
    name='apps.ml_training.tasks.active_learning_loop',
    max_retries=3,
    default_retry_delay=60,
)
def active_learning_loop(
    self,
    model_id: Optional[int] = None,
    confidence_threshold: float = 0.85,
    batch_size: int = 100,
    dataset_id: Optional[int] = None
):
    """
    Run active learning loop to identify samples for labeling.

    Routes to: ai_processing queue (priority 1)

    Active learning identifies uncertain predictions that need human labeling.

    Args:
        model_id: Optional model ID associated with the dataset
        confidence_threshold: Confidence threshold (below = uncertain)
        batch_size: Number of samples to process
        dataset_id: Explicit dataset ID (overrides model_id mapping)

    Returns:
        dict: Active learning summary

    Example:
        active_learning_loop.apply_async(
            args=[456, 0.85, 100],
            queue='ai_processing',
            priority=1
        )
    """
    logger.info(
        "Starting active learning loop: model=%s, dataset=%s, threshold=%.2f",
        model_id,
        dataset_id,
        confidence_threshold
    )

    try:
        from apps.ml_training.models import TrainingDataset, TrainingExample
        from apps.ml_training.services.active_learning_service import (
            ActiveLearningService
        )

        dataset = None
        if dataset_id is not None:
            dataset = TrainingDataset.objects.filter(id=dataset_id).first()
        if dataset is None and model_id is not None:
            dataset = TrainingDataset.objects.filter(
                metadata__model_id=model_id
            ).first()

        if dataset is None:
            logger.warning(
                "Active learning skipped: dataset not found (model_id=%s, dataset_id=%s)",
                model_id,
                dataset_id
            )
            return {
                'status': 'skipped',
                'reason': 'dataset_not_found',
                'model_id': model_id,
                'samples_identified': 0
            }

        confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        min_uncertainty = 1.0 - confidence_threshold

        service = ActiveLearningService()
        detection = service.detect_uncertain_examples(
            dataset=dataset,
            min_uncertainty=min_uncertainty,
            limit=batch_size
        )

        if not detection.get('success'):
            error_message = detection.get('error', 'detection_failed')
            logger.error(
                "Active learning detection failed for dataset %s: %s",
                dataset.id,
                error_message
            )
            return {
                'status': 'error',
                'reason': error_message,
                'model_id': model_id,
                'dataset_id': dataset.id
            }

        candidates = detection.get('examples') or []
        if not candidates:
            logger.info(
                "Active learning skipped: no uncertain samples above threshold for dataset %s",
                dataset.id
            )
            return {
                'status': 'skipped',
                'reason': 'no_uncertain_samples',
                'model_id': model_id,
                'dataset_id': dataset.id,
                'uncertainty_threshold': min_uncertainty
            }

        selected_examples = sorted(
            candidates,
            key=lambda example: example.uncertainty_score or 0.0,
            reverse=True
        )[:batch_size]

        for priority, example in enumerate(selected_examples, start=1):
            example.selected_for_labeling = True
            base_priority = int((example.uncertainty_score or 0) * 100)
            example.labeling_priority = max(base_priority, 1) + (batch_size - priority)

        TrainingExample.objects.bulk_update(
            selected_examples,
            ['selected_for_labeling', 'labeling_priority']
        )

        TaskMetrics.increment_counter('active_learning_samples_identified', {
            'dataset_id': str(dataset.id),
            'count': str(len(selected_examples))
        })

        recommended_ids = [str(example.uuid) for example in selected_examples]

        logger.info(
            "Active learning loop complete: %s samples identified for dataset %s",
            len(selected_examples),
            dataset.id
        )

        return {
            'status': 'success',
            'model_id': model_id,
            'dataset_id': dataset.id,
            'dataset_name': dataset.name,
            'samples_identified': len(selected_examples),
            'confidence_threshold': confidence_threshold,
            'uncertainty_threshold': min_uncertainty,
            'recommended_for_labeling': recommended_ids,
            'uncertainty_stats': detection.get('uncertainty_stats', {})
        }

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error in active learning loop: {e}", exc_info=True)
        raise self.retry(exc=e)
    except CELERY_EXCEPTIONS as e:
        logger.error(f"Error in active learning loop: {e}", exc_info=True)
        raise


@shared_task(
    base=WebSocketBroadcastTask,
    bind=True,
    name='apps.ml_training.tasks.dataset_labeling',
    max_retries=3,
    default_retry_delay=30,
)
def dataset_labeling(
    self,
    dataset_id: int,
    labeling_strategy: str = 'ai_assisted',
    user_id: Optional[int] = None
):
    """
    Perform dataset labeling (AI-assisted or automated).

    Routes to: ai_processing queue (priority 1)

    Args:
        dataset_id: Dataset ID to label
        labeling_strategy: 'ai_assisted', 'automated', 'manual'
        user_id: Optional user ID to notify

    Returns:
        dict: Labeling results

    Example:
        dataset_labeling.apply_async(
            args=[789, 'ai_assisted', 123],
            queue='ai_processing',
            priority=1
        )
    """
    logger.info(f"Starting dataset labeling: dataset={dataset_id}, strategy={labeling_strategy}")

    try:
        if dataset_id is None:
            logger.warning("Dataset labeling skipped: dataset_id not provided")
            return {
                'status': 'skipped',
                'reason': 'dataset_not_specified',
                'samples_labeled': 0
            }

        from apps.ml_training.models import TrainingDataset

        dataset = TrainingDataset.objects.filter(id=dataset_id).first()
        if dataset is None:
            logger.warning("Dataset labeling skipped: dataset %s not found", dataset_id)
            return {
                'status': 'skipped',
                'reason': 'dataset_not_found',
                'dataset_id': dataset_id,
                'samples_labeled': 0
            }

        # Attempt to load real labeling service. If unavailable, guard task.
        try:
            from apps.ml_training.services.dataset_labeling_service import label_dataset  # type: ignore
        except ModuleNotFoundError:
            logger.warning(
                "Dataset labeling service unavailable; skipping dataset %s",
                dataset_id
            )
            if user_id:
                self.broadcast_task_progress(
                    user_id=user_id,
                    task_name='Dataset Labeling',
                    progress=0.0,
                    status='skipped',
                    message='Dataset labeling service unavailable'
                )
            return {
                'status': 'skipped',
                'reason': 'dataset_labeling_service_unavailable',
                'dataset_id': dataset_id,
                'samples_labeled': 0
            }

        # Real implementation path (unreachable until service lands)
        if user_id:
            self.broadcast_task_progress(
                user_id=user_id,
                task_name='Dataset Labeling',
                progress=0.0,
                message='Initializing labeling pipeline'
            )

        result = label_dataset(dataset_id, labeling_strategy)

        if user_id:
            self.broadcast_task_progress(
                user_id=user_id,
                task_name='Dataset Labeling',
                progress=100.0,
                status='completed',
                message=f"{result.get('samples_labeled', 0)} samples labeled"
            )

        TaskMetrics.increment_counter('dataset_samples_labeled', {
            'strategy': labeling_strategy,
            'count': str(result.get('samples_labeled', 0))
        })

        logger.info(
            "Dataset labeling completed via service: dataset=%s samples=%s",
            dataset_id,
            result.get('samples_labeled')
        )

        result.setdefault('status', 'success')
        result.setdefault('dataset_id', dataset_id)
        return result

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error during dataset labeling: {e}", exc_info=True)
        raise self.retry(exc=e)
    except CELERY_EXCEPTIONS as e:
        logger.error(f"Error labeling dataset: {e}", exc_info=True)
        if user_id:
            self.broadcast_task_progress(
                user_id=user_id,
                task_name='Dataset Labeling',
                progress=0.0,
                status='failed',
                message=f'Labeling failed: {str(e)[:100]}'
            )
        raise


@shared_task(
    base=WebSocketBroadcastTask,
    bind=True,
    name='apps.ml_training.tasks.evaluate_model',
    max_retries=3,
    default_retry_delay=60,
)
def evaluate_model(
    self,
    model_id: int,
    test_dataset_id: int,
    user_id: Optional[int] = None
):
    """
    Evaluate ML model on test dataset.

    Routes to: ai_processing queue (priority 1)

    Args:
        model_id: Model ID to evaluate
        test_dataset_id: Test dataset ID
        user_id: Optional user ID to notify

    Returns:
        dict: Evaluation metrics

    Example:
        evaluate_model.apply_async(
            args=[456, 789, 123],
            queue='ai_processing',
            priority=1
        )
    """
    logger.info(f"Starting model evaluation: model={model_id}, test_dataset={test_dataset_id}")

    try:
        if model_id is None or test_dataset_id is None:
            logger.warning(
                "Model evaluation skipped: missing parameters (model_id=%s, test_dataset_id=%s)",
                model_id,
                test_dataset_id
            )
            return {
                'status': 'skipped',
                'reason': 'missing_parameters'
            }

        try:
            from apps.ml_training.services.evaluation_service import evaluate_ml_model  # type: ignore
        except ModuleNotFoundError:
            logger.warning(
                "Model evaluation service unavailable; skipping model=%s dataset=%s",
                model_id,
                test_dataset_id
            )
            if user_id:
                self.broadcast_to_user(
                    user_id=user_id,
                    message_type='model_evaluation_complete',
                    data={
                        'status': 'skipped',
                        'reason': 'model_evaluation_service_unavailable',
                        'model_id': model_id,
                        'test_dataset_id': test_dataset_id
                    }
                )
            return {
                'status': 'skipped',
                'reason': 'model_evaluation_service_unavailable',
                'model_id': model_id,
                'test_dataset_id': test_dataset_id
            }

        metrics = evaluate_ml_model(model_id, test_dataset_id)

        if user_id:
            self.broadcast_to_user(
                user_id=user_id,
                message_type='model_evaluation_complete',
                data=metrics
            )

        TaskMetrics.increment_counter('ml_model_evaluated', {
            'model_id': str(model_id),
        })

        logger.info(
            "Model evaluation complete via service: model=%s dataset=%s",
            model_id,
            test_dataset_id
        )

        metrics.setdefault('status', 'success')
        return metrics

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error during model evaluation: {e}", exc_info=True)
        raise self.retry(exc=e)
    except CELERY_EXCEPTIONS as e:
        logger.error(f"Error evaluating model: {e}", exc_info=True)
        raise
