"""
Management command to train alert priority scoring model.

Usage:
    python manage.py train_priority_model
    python manage.py train_priority_model --force

Requires 500+ resolved alerts with time_to_resolve data.
"""

from django.core.management.base import BaseCommand, CommandError
from apps.noc.ml.priority_model_trainer import PriorityModelTrainer


class Command(BaseCommand):
    help = 'Train XGBoost model for alert priority scoring (requires 500+ resolved alerts)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force retraining even if model already exists',
        )

    def handle(self, *args, **options):
        force_retrain = options['force']

        self.stdout.write(self.style.WARNING('Starting priority model training...'))
        
        if force_retrain:
            self.stdout.write(self.style.WARNING('Force retrain enabled'))

        try:
            metrics = PriorityModelTrainer.train_model(force_retrain=force_retrain)

            if metrics['status'] == 'skipped':
                self.stdout.write(
                    self.style.WARNING(
                        f"Training skipped: {metrics['reason']}. Use --force to retrain."
                    )
                )
                return

            self.stdout.write(self.style.SUCCESS('\nModel trained successfully!'))
            self.stdout.write(f"\nTraining Metrics:")
            self.stdout.write(f"  - Training samples: {metrics['training_samples']}")
            self.stdout.write(f"  - Test samples: {metrics['test_samples']}")
            self.stdout.write(f"  - MAE (Mean Absolute Error): {metrics['mae']:.2f}")
            self.stdout.write(f"  - RMSE (Root Mean Square Error): {metrics['rmse']:.2f}")
            self.stdout.write(f"  - R² Score: {metrics['r2_score']:.3f}")
            self.stdout.write(f"\nModel saved to: apps/noc/ml/models/priority_model.pkl")

        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Training failed: {str(e)}")
