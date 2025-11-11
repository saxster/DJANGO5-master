"""
ML Training Orchestrator Service.

Orchestrates model training workflows by triggering external ML platforms or
coordinating in-process training for development/testing.

Replaces blocking time.sleep() loops with proper async orchestration (Ultrathink remediation).

@ontology(
    domain="ml_training",
    purpose="Orchestrate ML model training workflows without blocking workers",
    criticality="medium",
    data_quality_impact="high - enables real training metrics vs fake metrics",
    tags=["ml", "training", "orchestration", "celery"]
)
"""

import logging
import requests
from typing import Dict, Any, Optional, Callable
from django.conf import settings
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

logger = logging.getLogger('ml_training.orchestrator')

__all__ = ['TrainingOrchestrator']


class TrainingOrchestrator:
    """
    Coordinates ML training workflows by delegating to external platforms
    or triggering lightweight in-process training.
    """

    # Configuration
    EXTERNAL_ML_ENDPOINT = getattr(settings, 'ML_TRAINING_ENDPOINT', None)
    ENABLE_EXTERNAL_TRAINING = getattr(settings, 'ENABLE_EXTERNAL_ML_TRAINING', False)
    MAX_IN_PROCESS_SAMPLES = 10_000  # Safety limit for in-process training

    @classmethod
    def trigger_training(
        cls,
        dataset_id: int,
        model_type: str,
        hyperparameters: Dict[str, Any],
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Trigger model training (external or in-process).

        This method does NOT block on training completion. It either:
        1. Submits job to external platform and returns job ID
        2. Triggers lightweight in-process training for dev/test

        Args:
            dataset_id: Dataset to train on
            model_type: Model architecture (e.g., 'random_forest', 'logistic_regression')
            hyperparameters: Model hyperparameters
            progress_callback: Optional callback for progress updates (pct, message)

        Returns:
            dict: Training job metadata
                - For external: {'job_id': str, 'status': 'submitted', 'platform': 'external'}
                - For in-process: {'model_id': int, 'status': 'completed', 'metrics': {...}}

        Raises:
            ValueError: If dataset too large for in-process or model type unsupported
        """
        from apps.ml_training.models import Dataset

        # Load dataset metadata (NOT the full dataset - just metadata!)
        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            raise ValueError(f"Dataset {dataset_id} not found")

        # Route to external platform if configured
        if cls.ENABLE_EXTERNAL_TRAINING and cls.EXTERNAL_ML_ENDPOINT:
            return cls._trigger_external_training(
                dataset, model_type, hyperparameters, progress_callback
            )

        # Otherwise, use in-process training (dev/test only)
        return cls._trigger_in_process_training(
            dataset, model_type, hyperparameters, progress_callback
        )

    @classmethod
    def _trigger_external_training(
        cls,
        dataset,
        model_type: str,
        hyperparameters: Dict[str, Any],
        progress_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """
        Submit training job to external ML platform (SageMaker, Vertex AI, etc.).

        This method does NOT wait for training to complete. It submits the job
        and returns immediately with a job ID for polling.
        """
        try:
            # Export dataset to cloud storage (S3/GCS)
            from apps.ml_training.services.dataset_ingestion_service import DatasetIngestionService
            dataset_url = DatasetIngestionService.export_to_storage(dataset)

            # Trigger external training job
            callback_url = f"{settings.BASE_URL}/api/ml-training/webhook/training-complete/"

            response = requests.post(
                cls.EXTERNAL_ML_ENDPOINT,
                json={
                    'dataset_url': dataset_url,
                    'dataset_id': dataset.id,
                    'model_type': model_type,
                    'hyperparameters': hyperparameters,
                    'callback_url': callback_url,
                },
                timeout=(5, 15),  # Connect timeout: 5s, Read timeout: 15s (non-blocking!)
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            job_data = response.json()
            job_id = job_data.get('job_id')

            if progress_callback:
                progress_callback(10.0, f"Training job {job_id} submitted to external platform")

            logger.info(
                f"External training job submitted: {job_id}",
                extra={'dataset_id': dataset.id, 'model_type': model_type}
            )

            return {
                'job_id': job_id,
                'status': 'submitted',
                'platform': 'external',
                'message': f'Training job {job_id} submitted. Webhook will notify on completion.'
            }

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Failed to trigger external training: {e}", exc_info=True)
            raise ValueError(f"External ML platform unavailable: {e}")

    @classmethod
    def _trigger_in_process_training(
        cls,
        dataset,
        model_type: str,
        hyperparameters: Dict[str, Any],
        progress_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """
        Lightweight in-process training for development/testing only.

        Safety limits:
        - Max dataset size: 10,000 samples
        - Supported models: logistic_regression, random_forest only
        - No GPU acceleration (CPU only)
        """
        # Validate dataset size
        if dataset.sample_count > cls.MAX_IN_PROCESS_SAMPLES:
            raise ValueError(
                f"Dataset too large ({dataset.sample_count} samples). "
                f"Max for in-process training: {cls.MAX_IN_PROCESS_SAMPLES}. "
                "Use external ML platform for production training."
            )

        # Validate model type
        supported_models = ['logistic_regression', 'random_forest']
        if model_type not in supported_models:
            raise ValueError(
                f"Model type '{model_type}' not supported for in-process training. "
                f"Supported: {supported_models}. "
                "Use external ML platform for advanced models."
            )

        if progress_callback:
            progress_callback(20.0, "Loading dataset for in-process training")

        # Placeholder for actual lightweight training
        # In production, this would:
        # 1. Load features/labels from dataset
        # 2. Train simple sklearn model
        # 3. Evaluate on test set
        # 4. Save model artifact
        # 5. Return actual metrics

        logger.warning(
            "In-process training is a stub. Implement actual training for production use.",
            extra={'dataset_id': dataset.id, 'model_type': model_type}
        )

        if progress_callback:
            progress_callback(100.0, "In-process training stub completed")

        return {
            'model_id': None,  # Would be actual model ID after implementation
            'status': 'stub_completed',
            'message': 'In-process training not fully implemented. Use external platform.',
            'metrics': {
                'note': 'Placeholder metrics - implement actual training for real values'
            }
        }
