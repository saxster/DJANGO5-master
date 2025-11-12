"""
Unit Tests for ML Services.

Tests pattern analysis, profiling, and predictive detection.
Follows .claude/rules.md testing standards.
"""

import pytest
import warnings
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestPatternAnalyzer:
    """Test pattern analysis methods."""

    def test_analyze_temporal_patterns(self, test_person, attendance_event):
        """Test temporal pattern analysis."""
        from apps.noc.security_intelligence.ml import PatternAnalyzer
        from apps.attendance.models import PeopleEventlog

        for i in range(15):
            PeopleEventlog.objects.create(
                tenant=test_person.tenant,
                people=test_person,
                bu=attendance_event.bu,
                datefor=timezone.now().date() - timedelta(days=i),
                punchintime=timezone.now().replace(hour=9, minute=0)
            )

        result = PatternAnalyzer.analyze_temporal_patterns(test_person, days=30)

        assert result is not None
        assert 'typical_hours' in result
        assert 'total_observations' in result
        assert result['total_observations'] >= 15

    def test_analyze_site_patterns(self, test_person, attendance_event):
        """Test site pattern analysis."""
        from apps.noc.security_intelligence.ml import PatternAnalyzer

        result = PatternAnalyzer.analyze_site_patterns(test_person, days=30)

        if result:
            assert 'primary_sites' in result
            assert 'site_variety_score' in result


@pytest.mark.django_db
class TestBehavioralProfiler:
    """Test behavioral profiling methods."""

    def test_create_profile_insufficient_data(self, test_person):
        """Test profile creation with insufficient data."""
        from apps.noc.security_intelligence.ml import BehavioralProfiler

        profile = BehavioralProfiler.create_or_update_profile(test_person, days=30)

        assert profile is None or not profile.is_sufficient_data

    def test_profile_needs_retraining(self, test_person, attendance_event):
        """Test profile retraining check."""
        from apps.noc.security_intelligence.models import BehavioralProfile

        profile = BehavioralProfile.objects.create(
            tenant=test_person.tenant,
            person=test_person,
            profile_start_date=timezone.now().date() - timedelta(days=90),
            profile_end_date=timezone.now().date(),
            total_observations=50,
            last_trained_at=timezone.now() - timedelta(days=35)
        )

        assert profile.needs_retraining(days_threshold=30) is True

    def test_profile_age_calculation(self, test_person):
        """Test profile age calculation."""
        from apps.noc.security_intelligence.models import BehavioralProfile

        profile = BehavioralProfile.objects.create(
            tenant=test_person.tenant,
            person=test_person,
            profile_start_date=timezone.now().date() - timedelta(days=90),
            profile_end_date=timezone.now().date(),
            total_observations=100
        )

        assert profile.profile_age_days == 90


@pytest.mark.django_db
class TestGoogleMLIntegrator:
    """Test Google ML integration methods."""

    def test_deprecation_warning(self):
        """Test deprecation warning is raised on instantiation."""
        from apps.noc.security_intelligence.ml import GoogleMLIntegrator

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            integrator = GoogleMLIntegrator()

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "FraudModelTrainer" in str(w[0].message)
            assert "PredictiveFraudDetector" in str(w[0].message)

    def test_export_training_data(self, tenant):
        """Test training data export."""
        from apps.noc.security_intelligence.ml import GoogleMLIntegrator

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = GoogleMLIntegrator.export_training_data(tenant, days=30)

        assert 'success' in result
        if result['success']:
            assert 'record_count' in result

    def test_ml_training_dataset_lifecycle(self, tenant):
        """Test ML training dataset status transitions."""
        from apps.noc.security_intelligence.models import MLTrainingDataset

        dataset = MLTrainingDataset.objects.create(
            tenant=tenant,
            dataset_name='test_dataset',
            dataset_type='FRAUD_DETECTION',
            version='1.0',
            status='PREPARING',
            data_start_date=timezone.now().date() - timedelta(days=90),
            data_end_date=timezone.now().date(),
            total_records=1000,
            fraud_records=100,
            normal_records=900
        )

        dataset.mark_training_started()
        assert dataset.status == 'TRAINING'
        assert dataset.training_started_at is not None

        metrics = {
            'accuracy': 0.87,
            'precision': 0.85,
            'recall': 0.89,
            'f1_score': 0.87,
        }

        dataset.mark_training_completed(metrics)
        assert dataset.status == 'TRAINED'
        assert dataset.model_accuracy == 0.87


@pytest.mark.django_db
class TestPredictiveFraudDetector:
    """Test predictive fraud detection."""

    def test_predict_attendance_fraud(self, test_person, site_bt):
        """Test fraud prediction."""
        from apps.noc.security_intelligence.ml import PredictiveFraudDetector

        scheduled_time = timezone.now() + timedelta(hours=2)

        prediction = PredictiveFraudDetector.predict_attendance_fraud(
            test_person,
            site_bt,
            scheduled_time
        )

        assert 'fraud_probability' in prediction
        assert 'risk_level' in prediction
        assert 'model_confidence' in prediction
        assert 0 <= prediction['fraud_probability'] <= 1

    def test_fraud_prediction_logging(self, test_person, site_bt):
        """Test prediction logging."""
        from apps.noc.security_intelligence.ml import PredictiveFraudDetector
        from apps.noc.security_intelligence.models import FraudPredictionLog

        scheduled_time = timezone.now() + timedelta(hours=2)

        prediction_result = {
            'fraud_probability': 0.65,
            'risk_level': 'HIGH',
            'model_confidence': 0.85,
            'behavioral_risk': 0.3,
            'features': {'hour': 14},
            'model_version': '1.0',
        }

        log = PredictiveFraudDetector.log_prediction(
            test_person,
            site_bt,
            scheduled_time,
            prediction_result
        )

        assert log is not None
        assert log.fraud_probability == 0.65
        assert log.risk_level == 'HIGH'

    def test_prediction_outcome_tracking(self, test_person, attendance_event):
        """Test prediction outcome recording."""
        from apps.noc.security_intelligence.models import FraudPredictionLog

        prediction = FraudPredictionLog.objects.create(
            tenant=test_person.tenant,
            person=test_person,
            site=attendance_event.bu,
            predicted_at=timezone.now() - timedelta(hours=1),
            prediction_type='ATTENDANCE',
            fraud_probability=0.70,
            risk_level='HIGH',
            model_confidence=0.85
        )

        prediction.record_outcome(
            attendance_event=attendance_event,
            fraud_detected=True,
            fraud_score=0.75
        )

        assert prediction.actual_fraud_detected is True
        assert prediction.actual_fraud_score == 0.75
        assert prediction.prediction_accuracy is not None
        assert prediction.prediction_accuracy >= 0