"""
Django Management Command: Train Device Failure Predictor.

Usage: python manage.py train_device_predictor --days=90
"""

from django.core.management.base import BaseCommand
from datetime import timedelta
from django.utils import timezone
from apps.noc.ml.predictive_models.predictive_model_trainer import PredictiveModelTrainer
import logging
from apps.core.exceptions.patterns import FILE_EXCEPTIONS


logger = logging.getLogger('noc.management')


class DeviceFailureTrainer(PredictiveModelTrainer):
    """Trainer for Device Failure Predictor."""

    def extract_training_data(self, days: int):
        """Extract training data from device history."""
        # Simplified implementation - would need actual Device model
        logger.warning("Device model not yet integrated - returning mock data")
        return [[0] * 7], [0]  # Mock data

    def get_feature_names(self):
        return [
            'offline_duration_last_7_days',
            'sync_health_score_trend',
            'time_since_last_event_minutes',
            'event_frequency_last_24h',
            'battery_level',
            'gps_accuracy_degradation',
            'device_type_failure_rate',
        ]

    def get_model_path(self):
        from apps.noc.ml.predictive_models.device_failure_predictor import DeviceFailurePredictor
        return DeviceFailurePredictor.MODEL_PATH


class Command(BaseCommand):
    help = 'Train Device Failure Predictor XGBoost model'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Days of historical data')
        parser.add_argument('--no-smote', action='store_true', help='Disable SMOTE')

    def handle(self, *args, **options):
        days = options['days']
        use_smote = not options['no_smote']

        self.stdout.write(self.style.WARNING(f'Training Device Failure Predictor with {days} days of data...'))

        try:
            trainer = DeviceFailureTrainer()
            metrics = trainer.train_model(days=days, use_smote=use_smote)

            self.stdout.write(self.style.SUCCESS('\nModel Training Complete!'))
            self.stdout.write(self.style.SUCCESS(f'  F1 Score: {metrics["f1"]:.3f}'))
            self.stdout.write(self.style.SUCCESS(f'  AUC: {metrics["auc"]:.3f}'))

        except FILE_EXCEPTIONS as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
