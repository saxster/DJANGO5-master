"""
Management command to train conflict prediction model.

Usage:
    python manage.py train_conflict_model --data-path path/to/data.csv
"""

import os
from datetime import datetime
from django.core.management.base import BaseCommand
from apps.ml.services.training.conflict_model_trainer import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

    ConflictModelTrainer
)
from apps.ml.models.ml_models import ConflictPredictionModel


class Command(BaseCommand):
    """Train conflict prediction model."""

    help = 'Train conflict prediction model'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--data-path',
            type=str,
            default='media/ml_training_data/conflict_predictor_latest.csv',
            help='Path to training CSV'
        )

    def handle(self, *args, **options):
        """Execute command."""
        data_path = options['data_path']

        if not os.path.exists(data_path):
            self.stdout.write(
                self.style.ERROR(
                    f'Training data not found at {data_path}\n'
                    f'Run: python manage.py extract_conflict_training_data'
                )
            )
            return

        # Generate model output path with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_output_path = (
            f'media/ml_models/conflict_predictor_v{timestamp}.joblib'
        )

        # Ensure output directory exists
        os.makedirs(os.path.dirname(model_output_path), exist_ok=True)

        self.stdout.write(f'Training model from {data_path}...')

        try:
            trainer = ConflictModelTrainer()
            metrics = trainer.train_model(data_path, model_output_path)

            # Store model metadata in database
            model = ConflictPredictionModel.objects.create(
                version=f'v{timestamp}',
                algorithm='LogisticRegression',
                accuracy=metrics['test_roc_auc'],
                precision=0.0,  # Will be populated after deployment
                recall=0.0,     # Will be populated after deployment
                f1_score=0.0,   # Will be populated after deployment
                trained_on_samples=metrics['train_samples'],
                feature_count=len(metrics['feature_columns']),
                model_path=model_output_path,
                is_active=False  # Manual activation required
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'\nModel trained successfully!\n'
                    f'Test ROC-AUC: {metrics["test_roc_auc"]:.4f}\n'
                    f'Model saved to: {model_output_path}\n'
                    f'\nActivate with:\n'
                    f'from apps.ml.models.ml_models import '
                    f'ConflictPredictionModel\n'
                    f'ConflictPredictionModel.objects.filter('
                    f'version="v{timestamp}").update(is_active=True)'
                )
            )

        except ValueError as e:
            self.stdout.write(
                self.style.ERROR(f'Training failed: {e}')
            )
        except DATABASE_EXCEPTIONS as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Unexpected error during training: {e}'
                )
            )
            raise
