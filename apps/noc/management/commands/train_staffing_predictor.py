"""
Django Management Command: Train Staffing Gap Predictor.

Usage: python manage.py train_staffing_predictor --days=90
"""

from django.core.management.base import BaseCommand
from datetime import timedelta
from django.utils import timezone
from apps.noc.ml.predictive_models.predictive_model_trainer import PredictiveModelTrainer
import logging
from apps.core.exceptions.patterns import FILE_EXCEPTIONS


logger = logging.getLogger('noc.management')


class StaffingGapTrainer(PredictiveModelTrainer):
    """Trainer for Staffing Gap Predictor."""

    def extract_training_data(self, days: int):
        """Extract training data from shift/attendance history."""
        # Simplified implementation - would need actual Schedule model integration
        logger.warning("Schedule model not yet fully integrated - returning mock data")
        return [[0] * 6], [0]  # Mock data

    def get_feature_names(self):
        return [
            'scheduled_guards_count',
            'actual_attendance_rate_last_7_days',
            'time_to_next_shift_minutes',
            'site_criticality_score',
            'current_attendance_vs_scheduled_ratio',
            'historical_no_show_rate',
        ]

    def get_model_path(self):
        from apps.noc.ml.predictive_models.staffing_gap_predictor import StaffingGapPredictor
        return StaffingGapPredictor.MODEL_PATH


class Command(BaseCommand):
    help = 'Train Staffing Gap Predictor XGBoost model'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Days of historical data')
        parser.add_argument('--no-smote', action='store_true', help='Disable SMOTE')

    def handle(self, *args, **options):
        days = options['days']
        use_smote = not options['no_smote']

        self.stdout.write(self.style.WARNING(f'Training Staffing Gap Predictor with {days} days of data...'))

        try:
            trainer = StaffingGapTrainer()
            metrics = trainer.train_model(days=days, use_smote=use_smote)

            self.stdout.write(self.style.SUCCESS('\nModel Training Complete!'))
            self.stdout.write(self.style.SUCCESS(f'  F1 Score: {metrics["f1"]:.3f}'))
            self.stdout.write(self.style.SUCCESS(f'  AUC: {metrics["auc"]:.3f}'))

        except FILE_EXCEPTIONS as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
