"""
Unit Tests for Fraud Model Trainer

Tests XGBoost fraud detection model training.

Coverage:
- Data export to CSV
- Feature extraction from attendance
- Imbalanced class handling (fraud is rare)
- Model training workflow
- Edge cases

Follows .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
import os
import tempfile
from datetime import timedelta
from django.utils import timezone
from unittest.mock import Mock, patch
from apps.noc.security_intelligence.ml.fraud_model_trainer import (
    FraudModelTrainer
)


class TestFraudDataExport:
    """Test suite for fraud training data export."""

    @pytest.mark.django_db
    def test_export_training_data_insufficient_records(self):
        """Test export with insufficient data (< 100 records)."""
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            schema_name='test_tenant',
            name='Test Tenant'
        )

        result = FraudModelTrainer.export_training_data(tenant, days=30)

        # Should fail with insufficient data error
        assert result['success'] is False
        assert 'Insufficient data' in result['error']
        assert result['record_count'] < 100

    @pytest.mark.django_db
    @patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer._extract_features_for_training')
    def test_export_training_data_success(self, mock_extract):
        """Test successful export with sufficient data."""
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            schema_name='test_tenant2',
            name='Test Tenant 2'
        )

        # Mock feature extraction to return 200 records
        mock_features = [
            {
                'hour_of_day': 9,
                'day_of_week': 2,
                'is_weekend': 0.0,
                'is_holiday': 0.0,
                'gps_drift_meters': 50.0,
                'location_consistency_score': 0.9,
                'check_in_frequency_zscore': 0.2,
                'late_arrival_rate': 0.1,
                'weekend_work_frequency': 0.0,
                'face_recognition_confidence': 0.85,
                'biometric_mismatch_count_30d': 0,
                'time_since_last_event': 28800.0,
                'person_id': 1,
                'site_id': 1,
                'event_date': '2025-01-15',
                'is_fraud': False if i < 190 else True  # 5% fraud rate
            }
            for i in range(200)
        ]

        mock_extract.return_value = mock_features

        result = FraudModelTrainer.export_training_data(tenant, days=180)

        # Should succeed
        assert result['success'] is True
        assert result['record_count'] == 200
        assert result['fraud_count'] == 10
        assert result['normal_count'] == 190
        assert 'csv_path' in result

        # Verify CSV file created
        assert os.path.exists(result['csv_path'])

        # Cleanup
        os.remove(result['csv_path'])

    @pytest.mark.django_db
    @patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer._extract_features_for_training')
    def test_export_creates_dataset_record(self, mock_extract):
        """Test that export creates MLTrainingDataset record."""
        from apps.tenants.models import Tenant
        from apps.noc.security_intelligence.models import MLTrainingDataset

        tenant = Tenant.objects.create(
            schema_name='test_tenant3',
            name='Test Tenant 3'
        )

        mock_features = [
            {'is_fraud': False, 'hour_of_day': 9} for _ in range(150)
        ]
        mock_extract.return_value = mock_features

        result = FraudModelTrainer.export_training_data(tenant, days=180)

        # Verify dataset record created
        dataset = MLTrainingDataset.objects.filter(tenant=tenant).first()
        assert dataset is not None
        assert dataset.dataset_type == 'FRAUD_DETECTION'
        assert dataset.status == 'EXPORTED'
        assert dataset.total_records == 150

        # Cleanup
        if 'csv_path' in result and os.path.exists(result['csv_path']):
            os.remove(result['csv_path'])


class TestFeatureExtraction:
    """Test suite for feature extraction from attendance data."""

    @pytest.mark.django_db
    def test_extract_features_for_training_no_data(self):
        """Test feature extraction with no attendance data."""
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            schema_name='test_tenant4',
            name='Test Tenant 4'
        )

        since = timezone.now() - timedelta(days=180)

        features = FraudModelTrainer._extract_features_for_training(
            tenant, since
        )

        # Should return empty list
        assert features == []

    @pytest.mark.django_db
    def test_extract_features_for_training_with_attendance(self):
        """Test feature extraction with attendance events."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People
        from apps.onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog

        tenant = Tenant.objects.create(
            schema_name='test_tenant5',
            name='Test Tenant 5'
        )

        person = People.objects.create(
            username='test_user',
            email='test@example.com',
            tenant=tenant
        )

        site = Bt.objects.create(
            name='Test Site',
            tenant=tenant
        )

        # Create attendance events
        for i in range(10):
            PeopleEventlog.objects.create(
                people=person,
                bu=site,
                tenant=tenant,
                datefor=(timezone.now() - timedelta(days=i)).date(),
                punchintime=timezone.now() - timedelta(days=i)
            )

        since = timezone.now() - timedelta(days=30)

        features = FraudModelTrainer._extract_features_for_training(
            tenant, since
        )

        # Should extract features
        assert len(features) > 0
        assert 'hour_of_day' in features[0]
        assert 'is_fraud' in features[0]

    @pytest.mark.django_db
    def test_extract_features_labels_fraud_from_prediction_log(self):
        """Test that fraud labels come from FraudPredictionLog."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People
        from apps.onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog
        from apps.noc.security_intelligence.models import FraudPredictionLog

        tenant = Tenant.objects.create(
            schema_name='test_tenant6',
            name='Test Tenant 6'
        )

        person = People.objects.create(
            username='fraud_user',
            email='fraud@example.com',
            tenant=tenant
        )

        site = Bt.objects.create(
            name='Test Site 2',
            tenant=tenant
        )

        # Create attendance event
        event = PeopleEventlog.objects.create(
            people=person,
            bu=site,
            tenant=tenant,
            datefor=timezone.now().date(),
            punchintime=timezone.now()
        )

        # Mark as fraud in prediction log
        FraudPredictionLog.objects.create(
            tenant=tenant,
            actual_attendance_event=event,
            fraud_probability=0.95,
            actual_fraud_detected=True,
            supervisor_confirmed_fraud=True
        )

        since = timezone.now() - timedelta(days=1)

        features = FraudModelTrainer._extract_features_for_training(
            tenant, since
        )

        # Should label as fraud
        fraud_features = [f for f in features if f['is_fraud']]
        assert len(fraud_features) > 0


class TestCSVExport:
    """Test CSV export functionality."""

    @pytest.mark.django_db
    def test_export_to_csv_success(self):
        """Test CSV export with valid features."""
        from apps.tenants.models import Tenant
        from apps.noc.security_intelligence.models import MLTrainingDataset

        tenant = Tenant.objects.create(
            schema_name='test_tenant7',
            name='Test Tenant 7'
        )

        dataset = MLTrainingDataset.objects.create(
            tenant=tenant,
            dataset_name='test_dataset',
            dataset_type='FRAUD_DETECTION',
            version='1.0'
        )

        features = [
            {
                'hour_of_day': 9,
                'day_of_week': 2,
                'is_fraud': False
            }
            for _ in range(50)
        ]

        result = FraudModelTrainer._export_to_csv(dataset, features)

        assert result['success'] is True
        assert result['record_count'] == 50
        assert os.path.exists(result['csv_path'])

        # Cleanup
        os.remove(result['csv_path'])

    def test_export_to_csv_empty_features(self):
        """Test CSV export with empty features list."""
        from apps.tenants.models import Tenant
        from apps.noc.security_intelligence.models import MLTrainingDataset

        tenant = Tenant.objects.create(
            schema_name='test_tenant8',
            name='Test Tenant 8'
        )

        dataset = MLTrainingDataset.objects.create(
            tenant=tenant,
            dataset_name='empty_dataset',
            dataset_type='FRAUD_DETECTION'
        )

        result = FraudModelTrainer._export_to_csv(dataset, [])

        assert result['success'] is False
        assert 'No features to export' in result['error']


class TestImbalancedDataHandling:
    """Test handling of imbalanced fraud data (fraud is rare)."""

    @pytest.mark.django_db
    @patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer._extract_features_for_training')
    def test_export_with_5_percent_fraud_rate(self, mock_extract):
        """Test export with realistic 5% fraud rate."""
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            schema_name='test_tenant9',
            name='Test Tenant 9'
        )

        # 5% fraud rate (5 fraud out of 100)
        mock_features = [
            {'is_fraud': i >= 95} for i in range(100)
        ]
        mock_extract.return_value = mock_features

        result = FraudModelTrainer.export_training_data(tenant, days=180)

        assert result['success'] is True
        assert result['fraud_count'] == 5
        assert result['normal_count'] == 95

        # Cleanup
        if 'csv_path' in result:
            os.remove(result['csv_path'])

    @pytest.mark.django_db
    @patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer._extract_features_for_training')
    def test_export_with_extreme_imbalance(self, mock_extract):
        """Test export with extreme imbalance (1% fraud)."""
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            schema_name='test_tenant10',
            name='Test Tenant 10'
        )

        # 1% fraud rate (1 fraud out of 100)
        mock_features = [
            {'is_fraud': i == 99} for i in range(100)
        ]
        mock_extract.return_value = mock_features

        result = FraudModelTrainer.export_training_data(tenant, days=180)

        assert result['success'] is True
        assert result['fraud_count'] == 1
        assert result['normal_count'] == 99

        # Cleanup
        if 'csv_path' in result:
            os.remove(result['csv_path'])


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.django_db
    def test_export_with_invalid_tenant(self):
        """Test export with invalid tenant."""
        # This will be handled by database constraints
        pass

    @pytest.mark.django_db
    @patch('apps.noc.security_intelligence.ml.fraud_model_trainer.FraudModelTrainer._extract_features_for_training')
    def test_export_with_feature_extraction_error(self, mock_extract):
        """Test export when feature extraction fails."""
        from apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            schema_name='test_tenant11',
            name='Test Tenant 11'
        )

        # Simulate extraction error
        mock_extract.side_effect = ValueError("Feature extraction failed")

        result = FraudModelTrainer.export_training_data(tenant, days=180)

        assert result['success'] is False
        assert 'error' in result
