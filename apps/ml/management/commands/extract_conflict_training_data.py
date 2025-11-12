"""
Management command to extract conflict prediction training data.

Usage:
    python manage.py extract_conflict_training_data --days-back 90
"""

import os
from django.core.management.base import BaseCommand
from apps.ml.services.data_extractors.conflict_data_extractor import (
    ConflictDataExtractor
)


class Command(BaseCommand):
    """Extract training data for conflict prediction model."""

    help = 'Extract training data for conflict prediction model'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days-back',
            type=int,
            default=90,
            help='Number of days to look back (default: 90)'
        )
        parser.add_argument(
            '--output-path',
            type=str,
            default='media/ml_training_data/conflict_predictor_latest.csv',
            help='Output CSV file path'
        )

    def handle(self, *args, **options):
        """Execute command."""
        days_back = options['days_back']
        output_path = options['output_path']

        self.stdout.write(
            f'Extracting training data from past {days_back} days...'
        )

        extractor = ConflictDataExtractor()
        df = extractor.extract_training_data(days_back=days_back)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        extractor.save_training_data(df, output_path)

        if len(df) == 0:
            self.stdout.write(
                self.style.WARNING(
                    'No training data extracted. '
                    'This is expected if SyncLog models are not yet created.'
                )
            )
        else:
            conflict_count = df['conflict_occurred'].sum()
            positive_rate = df['conflict_occurred'].mean()

            self.stdout.write(
                self.style.SUCCESS(
                    f'Training data extracted: {len(df)} samples, '
                    f'{conflict_count} conflicts '
                    f'({positive_rate:.2%} positive rate)'
                )
            )
