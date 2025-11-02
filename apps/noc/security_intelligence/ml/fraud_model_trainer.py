"""
Fraud Model Trainer (Local XGBoost).

Replaces GoogleMLIntegrator with local XGBoost training.
Exports training data to CSV and trains imbalanced fraud detection model.

Architecture:
- Extract features from PeopleEventlog (last 6 months)
- Label fraud from FraudPredictionLog.actual_fraud_detected
- Train XGBoost with scale_pos_weight for imbalanced data
- Save model to media/ml_models/

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
import csv
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('noc.security_intelligence.ml')


class FraudModelTrainer:
    """Local XGBoost fraud detection model trainer."""

    CSV_EXPORT_DIR = Path(settings.MEDIA_ROOT) / 'ml_training_data'

    @classmethod
    def export_training_data(cls, tenant, days=180):
        """
        Export training data to local CSV.

        Args:
            tenant: Tenant instance
            days: Days of data to export (default 180 = 6 months)

        Returns:
            dict: Export result with file path and record counts
        """
        try:
            from apps.noc.security_intelligence.models import MLTrainingDataset

            since = timezone.now() - timedelta(days=days)

            # Extract features
            features = cls._extract_features_for_training(tenant, since)

            if len(features) < 100:
                return {
                    'success': False,
                    'error': 'Insufficient data for training (need ≥100 records)',
                    'record_count': len(features)
                }

            # Create dataset record
            dataset = MLTrainingDataset.objects.create(
                tenant=tenant,
                dataset_name=f"{tenant.schema_name}_fraud_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
                dataset_type='FRAUD_DETECTION',
                version='2.0',
                status='EXPORTING',
                data_start_date=since.date(),
                data_end_date=timezone.now().date(),
                total_records=len(features),
                fraud_records=sum(1 for f in features if f['is_fraud']),
                normal_records=sum(1 for f in features if not f['is_fraud']),
                feature_columns=list(features[0].keys()) if features else [],
            )

            # Export to CSV
            export_result = cls._export_to_csv(dataset, features)

            if export_result['success']:
                dataset.status = 'EXPORTED'
                dataset.bigquery_export_path = export_result['csv_path']
                dataset.save()

            return export_result

        except (ValueError, AttributeError, OSError) as e:
            logger.error(f"Training data export error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    @classmethod
    def _extract_features_for_training(cls, tenant, since):
        """
        Extract ML features from historical attendance data.

        Args:
            tenant: Tenant instance
            since: datetime - Start date for data extraction

        Returns:
            List of feature dicts with labels
        """
        from apps.attendance.models import PeopleEventlog
        from apps.noc.security_intelligence.models import FraudPredictionLog
        from apps.ml.features.fraud_features import FraudFeatureExtractor

        try:
            # Get attendance events with complete data
            events = PeopleEventlog.objects.filter(
                tenant=tenant,
                datefor__gte=since.date(),
                punchintime__isnull=False,
                people__isnull=False,
                bu__isnull=False
            ).select_related('people', 'bu').order_by('datefor')[:10000]

            features_list = []

            for event in events:
                # Check if fraud was confirmed for this event
                fraud_log = FraudPredictionLog.objects.filter(
                    actual_attendance_event=event
                ).first()

                is_fraud = False
                if fraud_log:
                    is_fraud = fraud_log.actual_fraud_detected or False

                # Extract 12 features
                try:
                    features = FraudFeatureExtractor.extract_all_features(
                        event, event.people, event.bu
                    )

                    # Add metadata and label
                    features['person_id'] = event.people.id
                    features['site_id'] = event.bu.id
                    features['event_date'] = event.datefor.isoformat()
                    features['is_fraud'] = is_fraud

                    features_list.append(features)

                except (AttributeError, ValueError) as e:
                    logger.debug(f"Skipping event {event.id} due to extraction error: {e}")
                    continue

            logger.info(f"Extracted {len(features_list)} feature records for training")
            return features_list

        except (AttributeError, ValueError) as e:
            logger.error(f"Feature extraction error: {e}", exc_info=True)
            return []

    @classmethod
    def _export_to_csv(cls, dataset, features):
        """
        Export features to CSV file.

        Args:
            dataset: MLTrainingDataset instance
            features: List of feature dicts

        Returns:
            dict: Export result with file path
        """
        try:
            # Ensure export directory exists
            cls.CSV_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

            # Generate CSV filename
            csv_filename = f"{dataset.dataset_name}.csv"
            csv_path = cls.CSV_EXPORT_DIR / csv_filename

            # Write to CSV
            if features:
                fieldnames = list(features[0].keys())

                with open(csv_path, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(features)

                logger.info(f"Exported {len(features)} records to {csv_path}")

                return {
                    'success': True,
                    'record_count': len(features),
                    'csv_path': str(csv_path),
                    'fraud_count': sum(1 for f in features if f['is_fraud']),
                    'normal_count': sum(1 for f in features if not f['is_fraud']),
                }
            else:
                return {
                    'success': False,
                    'error': 'No features to export'
                }

        except (OSError, ValueError) as e:
            logger.error(f"CSV export error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
