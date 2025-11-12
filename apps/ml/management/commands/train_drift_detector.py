"""
Management command to train ML drift detector on historical data.

Usage:
    python manage.py train_drift_detector --days=30
"""

from django.core.management.base import BaseCommand, CommandError
from apps.ml.monitoring.drift_detection import DriftDetector
from apps.core.exceptions.patterns import FILE_EXCEPTIONS



class Command(BaseCommand):
    help = 'Train ML drift detector on historical infrastructure metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of historical data to use for training (default: 30)'
        )

    def handle(self, *args, **options):
        days_back = options['days']

        if days_back < 7:
            raise CommandError('Minimum 7 days of data required for training')

        self.stdout.write(f"Training drift detector on {days_back} days of data...")

        detector = DriftDetector()

        try:
            result = detector.train_on_normal_data(days_back=days_back)

            self.stdout.write(self.style.SUCCESS(
                f"Drift detector trained successfully!"
            ))
            self.stdout.write(f"  Model ID: {result['model_id']}")
            self.stdout.write(f"  Samples: {result['sample_count']}")
            self.stdout.write(f"  Contamination: {result['contamination']}")

        except FILE_EXCEPTIONS as e:
            raise CommandError(f"Failed to train drift detector: {e}")
