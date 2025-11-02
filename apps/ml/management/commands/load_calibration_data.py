"""
Django Management Command: Load Calibration Data

Loads calibration datasets for conformal prediction from various sources:
1. Existing PredictionLog/FraudPredictionLog (historical predictions)
2. Model training holdout set (20% validation split)
3. CSV import (for manual calibration)

Usage:
    python manage.py load_calibration_data --model-type fraud_detector --version 1.0 --source prediction_log
    python manage.py load_calibration_data --model-type fraud_detector --version 1.0 --source csv --file calibration.csv
    python manage.py load_calibration_data --list  # List current calibration sets

Follows .claude/rules.md:
- Rule #7: < 150 lines per method
- Rule #11: Specific exception handling
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import csv
import sys

from apps.ml.services.conformal_predictor import CalibrationDataManager


class Command(BaseCommand):
    help = 'Load calibration data for conformal prediction'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-type',
            type=str,
            help='Model type (fraud_detector, conflict_predictor, etc.)'
        )
        parser.add_argument(
            '--version',
            type=str,
            help='Model version (e.g., 1.0, 2.5)'
        )
        parser.add_argument(
            '--source',
            type=str,
            choices=['prediction_log', 'fraud_log', 'csv'],
            help='Data source for calibration'
        )
        parser.add_argument(
            '--file',
            type=str,
            help='Path to CSV file (for csv source)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Days of historical data to use (default: 30)'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List current calibration sets in cache'
        )
        parser.add_argument(
            '--min-samples',
            type=int,
            default=30,
            help='Minimum calibration samples required (default: 30)'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        if options['list']:
            self.list_calibration_sets()
            return

        # Validate required arguments
        if not options['model_type'] or not options['version'] or not options['source']:
            raise CommandError(
                'Required arguments: --model-type, --version, --source\n'
                'Or use --list to see current calibration sets'
            )

        model_type = options['model_type']
        model_version = options['version']
        source = options['source']

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Loading Calibration Data")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Model Type: {model_type}")
        self.stdout.write(f"Version: {model_version}")
        self.stdout.write(f"Source: {source}")
        self.stdout.write(f"{'='*60}\n")

        try:
            if source == 'prediction_log':
                self.load_from_prediction_log(
                    model_type, model_version, options['days'], options['min_samples']
                )
            elif source == 'fraud_log':
                self.load_from_fraud_log(
                    model_type, model_version, options['days'], options['min_samples']
                )
            elif source == 'csv':
                if not options['file']:
                    raise CommandError('--file required for csv source')
                self.load_from_csv(
                    model_type, model_version, options['file'], options['min_samples']
                )

        except (ValueError, FileNotFoundError, IOError) as e:
            raise CommandError(f"Error loading calibration data: {e}")

    def load_from_prediction_log(self, model_type, model_version, days, min_samples):
        """Load calibration data from PredictionLog."""
        from apps.ml.models.ml_models import PredictionLog

        cutoff_date = timezone.now() - timedelta(days=days)

        # Query predictions with actual outcomes
        logs = PredictionLog.objects.filter(
            model_type=model_type,
            model_version=model_version,
            created_at__gte=cutoff_date,
            actual_conflict_occurred__isnull=False  # Only logs with outcomes
        ).values_list('conflict_probability', 'actual_conflict_occurred')

        if logs.count() == 0:
            raise CommandError(
                f"No prediction logs found for {model_type} v{model_version} "
                f"in last {days} days with actual outcomes"
            )

        predictions = [float(p) for p, _ in logs]
        actuals = [float(a) for _, a in logs]

        self.stdout.write(f"Found {len(predictions)} calibration samples from PredictionLog")

        self._store_calibration_data(
            model_type, model_version, predictions, actuals, min_samples
        )

    def load_from_fraud_log(self, model_type, model_version, days, min_samples):
        """Load calibration data from FraudPredictionLog."""
        from apps.noc.security_intelligence.models import FraudPredictionLog

        cutoff_date = timezone.now() - timedelta(days=days)

        # Query fraud predictions with actual outcomes
        logs = FraudPredictionLog.objects.filter(
            model_version=model_version,
            predicted_at__gte=cutoff_date,
            actual_fraud_detected__isnull=False  # Only logs with outcomes
        ).values_list('fraud_probability', 'actual_fraud_detected')

        if logs.count() == 0:
            raise CommandError(
                f"No fraud prediction logs found for v{model_version} "
                f"in last {days} days with actual outcomes"
            )

        predictions = [float(p) for p, _ in logs]
        actuals = [1.0 if a else 0.0 for _, a in logs]

        self.stdout.write(f"Found {len(predictions)} calibration samples from FraudPredictionLog")

        self._store_calibration_data(
            model_type, model_version, predictions, actuals, min_samples
        )

    def load_from_csv(self, model_type, model_version, file_path, min_samples):
        """
        Load calibration data from CSV file.

        CSV format:
        prediction,actual
        0.75,1
        0.25,0
        ...
        """
        predictions = []
        actuals = []

        try:
            with open(file_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)

                if 'prediction' not in reader.fieldnames or 'actual' not in reader.fieldnames:
                    raise CommandError(
                        "CSV must have 'prediction' and 'actual' columns"
                    )

                for row in reader:
                    try:
                        pred = float(row['prediction'])
                        actual = float(row['actual'])

                        if not (0.0 <= pred <= 1.0):
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Skipping row with out-of-range prediction: {pred}"
                                )
                            )
                            continue

                        if actual not in [0.0, 1.0]:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Skipping row with invalid actual: {actual}"
                                )
                            )
                            continue

                        predictions.append(pred)
                        actuals.append(actual)

                    except (ValueError, KeyError) as e:
                        self.stdout.write(
                            self.style.WARNING(f"Skipping invalid row: {e}")
                        )
                        continue

        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}")
        except IOError as e:
            raise CommandError(f"Error reading file: {e}")

        if not predictions:
            raise CommandError("No valid calibration data found in CSV")

        self.stdout.write(f"Loaded {len(predictions)} calibration samples from CSV")

        self._store_calibration_data(
            model_type, model_version, predictions, actuals, min_samples
        )

    def _store_calibration_data(self, model_type, model_version, predictions, actuals, min_samples):
        """Store calibration data in cache."""
        if len(predictions) < min_samples:
            raise CommandError(
                f"Insufficient calibration samples: {len(predictions)} < {min_samples}\n"
                f"Need at least {min_samples} samples for reliable intervals"
            )

        result = CalibrationDataManager.store_calibration_set(
            model_type=model_type,
            model_version=model_version,
            calibration_predictions=predictions,
            calibration_actuals=actuals
        )

        if result:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully stored {len(predictions)} calibration samples"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Cache key: conformal_calib_{model_type}_{model_version}"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Cache TTL: 1 hour (3600 seconds)"
                )
            )

            # Calculate basic statistics
            import numpy as np
            pred_array = np.array(predictions)
            actual_array = np.array(actuals)

            mean_pred = pred_array.mean()
            mean_actual = actual_array.mean()
            std_pred = pred_array.std()

            self.stdout.write(f"\nCalibration Statistics:")
            self.stdout.write(f"  Mean Prediction: {mean_pred:.3f}")
            self.stdout.write(f"  Mean Actual: {mean_actual:.3f}")
            self.stdout.write(f"  Std Dev Prediction: {std_pred:.3f}")
            self.stdout.write(f"  Positive Rate: {mean_actual:.1%}")

        else:
            raise CommandError("Failed to store calibration data")

    def list_calibration_sets(self):
        """List current calibration sets in cache."""
        # Common model types to check
        model_configs = [
            ('fraud_detector', ['1.0', '2.0', '3.0']),
            ('conflict_predictor', ['1.0', '2.0']),
        ]

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Current Calibration Sets (Cache)")
        self.stdout.write(f"{'='*60}\n")

        found_any = False

        for model_type, versions in model_configs:
            for version in versions:
                cache_key = f'conformal_calib_{model_type}_{version}'
                cached_data = cache.get(cache_key)

                if cached_data:
                    found_any = True
                    n_samples = len(cached_data['predictions'])
                    created_at = cached_data.get('created_at', 'Unknown')

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {model_type} v{version}: {n_samples} samples (created: {created_at})"
                        )
                    )

        if not found_any:
            self.stdout.write(
                self.style.WARNING(
                    "No calibration sets found in cache.\n"
                    "Use: python manage.py load_calibration_data --help"
                )
            )

        self.stdout.write("")
