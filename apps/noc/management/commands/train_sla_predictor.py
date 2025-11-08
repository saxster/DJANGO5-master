"""
Django Management Command: Train SLA Breach Predictor.

Trains XGBoost model for predicting SLA breaches 2 hours in advance.
Part of Enhancement #5: Predictive Alerting Engine.

Usage:
    python manage.py train_sla_predictor --days=90
    python manage.py train_sla_predictor --days=180 --no-smote

@ontology(
    domain="noc",
    purpose="Train SLA breach predictor XGBoost model from historical ticket data",
    command="train_sla_predictor",
    criticality="high",
    tags=["noc", "ml", "xgboost", "model-training", "sla-prediction"]
)
"""

from django.core.management.base import BaseCommand
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from apps.noc.ml.predictive_models.predictive_model_trainer import PredictiveModelTrainer
import logging
from apps.core.exceptions.patterns import FILE_EXCEPTIONS


logger = logging.getLogger('noc.management')


class SLABreachTrainer(PredictiveModelTrainer):
    """Trainer for SLA Breach Predictor."""

    def extract_training_data(self, days: int):
        """Extract training data from historical tickets."""
        from apps.y_helpdesk.models import Ticket
        from apps.noc.ml.predictive_models.sla_breach_predictor import SLABreachPredictor

        cutoff_date = timezone.now() - timedelta(days=days)

        # Get closed tickets with SLA policy
        tickets = Ticket.objects.filter(
            cdtz__gte=cutoff_date,
            status='CLOSED',
            sla_policy__isnull=False
        ).select_related('sla_policy', 'bu', 'client')

        features = []
        labels = []

        logger.info(f"Extracting features from {tickets.count()} tickets")

        for ticket in tickets:
            try:
                # Extract features using predictor's feature extraction
                feature_dict = SLABreachPredictor._extract_features(ticket)
                feature_vector = SLABreachPredictor._features_to_vector(feature_dict)

                # Label: Did ticket breach SLA?
                label = 1 if getattr(ticket, 'sla_breached', False) else 0

                features.append(feature_vector)
                labels.append(label)

            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Error extracting features for ticket {ticket.id}: {e}")

        logger.info(f"Extracted {len(features)} training samples")
        return features, labels

    def get_feature_names(self):
        """Return feature names."""
        return [
            'current_age_minutes',
            'priority_level',
            'assigned_status',
            'site_current_workload',
            'historical_avg_resolution_time',
            'time_until_sla_deadline_minutes',
            'assignee_current_workload',
            'business_hours',
        ]

    def get_model_path(self):
        """Return model path."""
        from apps.noc.ml.predictive_models.sla_breach_predictor import SLABreachPredictor
        return SLABreachPredictor.MODEL_PATH


class Command(BaseCommand):
    help = 'Train SLA Breach Predictor XGBoost model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days of historical data to use (default: 90)'
        )
        parser.add_argument(
            '--no-smote',
            action='store_true',
            help='Disable SMOTE class balancing'
        )

    def handle(self, *args, **options):
        days = options['days']
        use_smote = not options['no_smote']

        self.stdout.write(self.style.WARNING(f'Training SLA Breach Predictor with {days} days of data...'))

        try:
            trainer = SLABreachTrainer()
            metrics = trainer.train_model(days=days, use_smote=use_smote)

            self.stdout.write(self.style.SUCCESS('\nModel Training Complete!'))
            self.stdout.write(self.style.SUCCESS(f'  Precision: {metrics["precision"]:.3f}'))
            self.stdout.write(self.style.SUCCESS(f'  Recall: {metrics["recall"]:.3f}'))
            self.stdout.write(self.style.SUCCESS(f'  F1 Score: {metrics["f1"]:.3f}'))
            self.stdout.write(self.style.SUCCESS(f'  AUC: {metrics["auc"]:.3f}'))
            self.stdout.write(self.style.SUCCESS(f'  Test Samples: {metrics["test_samples"]}'))

            self.stdout.write('\nConfusion Matrix:')
            cm = metrics['confusion_matrix']
            self.stdout.write(f'  TN: {cm[0][0]}, FP: {cm[0][1]}')
            self.stdout.write(f'  FN: {cm[1][0]}, TP: {cm[1][1]}')

        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Training failed: {e}'))
            return

        except FILE_EXCEPTIONS as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))
            import traceback
            traceback.print_exc()
            return
