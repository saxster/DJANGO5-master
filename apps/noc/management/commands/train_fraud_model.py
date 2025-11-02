"""
Train Fraud Detection Model (XGBoost).

Django management command to train XGBoost fraud detection model.
Handles imbalanced classification with scale_pos_weight.

Usage:
    python manage.py train_fraud_model --tenant=<tenant_id>
    python manage.py train_fraud_model --tenant=1 --days=180

Follows .claude/rules.md:
- Rule #7: Command < 200 lines
- Rule #11: Specific exception handling
- Rule #13: Network timeouts (n/a for local training)
"""

import logging
import time
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve, auc, precision_score, recall_score
import joblib

logger = logging.getLogger('noc.management')


class Command(BaseCommand):
    help = 'Train XGBoost fraud detection model for tenant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=int,
            required=True,
            help='Tenant ID to train model for'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=180,
            help='Days of historical data to use (default: 180)'
        )
        parser.add_argument(
            '--test-size',
            type=float,
            default=0.2,
            help='Test set size fraction (default: 0.2)'
        )

    def handle(self, *args, **options):
        tenant_id = options['tenant']
        days = options['days']
        test_size = options['test_size']

        try:
            from apps.tenants.models import Tenant
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant {tenant_id} not found")

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"Training Fraud Detection Model\n"
            f"Tenant: {tenant.schema_name}\n"
            f"Training Data: {days} days\n"
            f"{'='*70}\n"
        ))

        # Step 1: Export training data
        self.stdout.write("Step 1: Exporting training data...")
        export_result = self._export_training_data(tenant, days)

        if not export_result['success']:
            raise CommandError(f"Data export failed: {export_result['error']}")

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Exported {export_result['record_count']} records\n"
            f"  ✓ Fraud: {export_result['fraud_count']} ({export_result['fraud_count']/export_result['record_count']*100:.1f}%)\n"
            f"  ✓ Normal: {export_result['normal_count']}\n"
        ))

        # Step 2: Load and prepare data
        self.stdout.write("Step 2: Loading and preparing data...")
        X_train, X_test, y_train, y_test = self._prepare_data(
            export_result['csv_path'], test_size
        )

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Train samples: {len(X_train)}\n"
            f"  ✓ Test samples: {len(X_test)}\n"
            f"  ✓ Fraud ratio: {y_train.mean():.4f}\n"
        ))

        # Step 3: Train XGBoost model
        self.stdout.write("Step 3: Training XGBoost model...")
        start_time = time.time()
        model, training_metrics = self._train_model(X_train, y_train, X_test, y_test)
        training_duration = int(time.time() - start_time)

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Training completed in {training_duration}s\n"
            f"  ✓ PR-AUC: {training_metrics['pr_auc']:.3f}\n"
            f"  ✓ Precision @ 80% Recall: {training_metrics['precision_at_80_recall']:.3f}\n"
        ))

        # Step 4: Save model
        self.stdout.write("Step 4: Saving model...")
        model_path = self._save_model(tenant, model)

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Model saved to: {model_path}\n"
        ))

        # Step 5: Register model in database
        self.stdout.write("Step 5: Registering model...")
        model_record = self._register_model(
            tenant, model_path, training_metrics, training_duration,
            len(X_train), int(y_train.sum()), model
        )

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Model registered: {model_record.model_version}\n"
        ))

        # Step 6: Activate model
        self.stdout.write("Step 6: Activating model...")
        model_record.activate()

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"✓ Fraud detection model training complete!\n"
            f"{'='*70}\n"
        ))

    def _export_training_data(self, tenant, days):
        """Export training data to CSV."""
        from apps.noc.security_intelligence.ml.fraud_model_trainer import FraudModelTrainer
        return FraudModelTrainer.export_training_data(tenant, days)

    def _prepare_data(self, csv_path, test_size):
        """Load CSV and prepare train/test sets."""
        # Load CSV
        df = pd.read_csv(csv_path)

        # Feature columns (exclude metadata and label)
        feature_cols = [
            'hour_of_day', 'day_of_week', 'is_weekend', 'is_holiday',
            'gps_drift_meters', 'location_consistency_score',
            'check_in_frequency_zscore', 'late_arrival_rate', 'weekend_work_frequency',
            'face_recognition_confidence', 'biometric_mismatch_count_30d', 'time_since_last_event'
        ]

        X = df[feature_cols].values
        y = df['is_fraud'].values

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        return X_train, X_test, y_train, y_test

    def _train_model(self, X_train, y_train, X_test, y_test):
        """Train XGBoost model with imbalanced class handling."""
        # Calculate scale_pos_weight for imbalanced data
        fraud_ratio = y_train.mean()
        scale_pos_weight = (1 - fraud_ratio) / fraud_ratio if fraud_ratio > 0 else 99

        self.stdout.write(
            f"  → Using scale_pos_weight: {scale_pos_weight:.1f} (fraud ratio: {fraud_ratio:.4f})"
        )

        # XGBoost configuration for imbalanced classification
        model = XGBClassifier(
            scale_pos_weight=scale_pos_weight,
            max_depth=5,
            learning_rate=0.1,
            n_estimators=100,
            eval_metric='aucpr',  # Precision-Recall AUC
            random_state=42,
            use_label_encoder=False
        )

        # Train model
        model.fit(X_train, y_train)

        # Evaluate on test set
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        # Calculate Precision-Recall curve and AUC
        precision, recall, thresholds = precision_recall_curve(y_test, y_pred_proba)
        pr_auc = auc(recall, precision)

        # Find precision at 80% recall
        precision_at_80_recall = self._get_precision_at_recall(precision, recall, target_recall=0.8)

        # Find optimal threshold (maximize F1)
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
        optimal_idx = np.argmax(f1_scores)
        optimal_threshold = thresholds[optimal_idx] if optimal_idx < len(thresholds) else 0.5

        # Feature importance
        feature_names = [
            'hour_of_day', 'day_of_week', 'is_weekend', 'is_holiday',
            'gps_drift_meters', 'location_consistency_score',
            'check_in_frequency_zscore', 'late_arrival_rate', 'weekend_work_frequency',
            'face_recognition_confidence', 'biometric_mismatch_count_30d', 'time_since_last_event'
        ]
        feature_importance = dict(zip(feature_names, model.feature_importances_))

        # Log top 5 features
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        self.stdout.write("\n  Top 5 Features:")
        for feat, importance in top_features:
            self.stdout.write(f"    - {feat}: {importance:.4f}")

        return model, {
            'pr_auc': pr_auc,
            'precision_at_80_recall': precision_at_80_recall,
            'optimal_threshold': optimal_threshold,
            'feature_importance': feature_importance,
            'scale_pos_weight': scale_pos_weight,
        }

    def _get_precision_at_recall(self, precision, recall, target_recall=0.8):
        """Get precision at target recall level."""
        # Find index where recall >= target_recall
        valid_indices = np.where(recall >= target_recall)[0]
        if len(valid_indices) == 0:
            return 0.0
        return precision[valid_indices[0]]

    def _save_model(self, tenant, model):
        """Save model to disk."""
        # Create models directory
        models_dir = Path(settings.MEDIA_ROOT) / 'ml_models'
        models_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"fraud_detector_tenant{tenant.id}_v{timestamp}.joblib"
        model_path = models_dir / filename

        # Save model
        joblib.dump(model, model_path)

        return str(model_path)

    def _register_model(self, tenant, model_path, metrics, training_duration, train_samples, fraud_samples, model):
        """Register model in database."""
        from apps.noc.security_intelligence.models import FraudDetectionModel

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_version = f"v2_{timestamp}"

        model_record = FraudDetectionModel.objects.create(
            tenant=tenant,
            model_version=model_version,
            model_path=model_path,
            pr_auc=metrics['pr_auc'],
            precision_at_80_recall=metrics['precision_at_80_recall'],
            optimal_threshold=metrics['optimal_threshold'],
            train_samples=train_samples,
            fraud_samples=fraud_samples,
            normal_samples=train_samples - fraud_samples,
            class_imbalance_ratio=fraud_samples / train_samples,
            training_duration_seconds=training_duration,
            xgboost_params={
                'max_depth': 5,
                'learning_rate': 0.1,
                'n_estimators': 100,
                'scale_pos_weight': metrics['scale_pos_weight'],
            },
            feature_importance=metrics['feature_importance'],
        )

        return model_record
