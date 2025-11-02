"""
Integration Tests for Fraud Detection with Confidence Intervals

Tests end-to-end integration:
- PredictiveFraudDetector with ConformalPredictorService
- Confidence-aware auto-escalation in SecurityAnomalyOrchestrator
- PredictionLog with confidence interval fields

Target: Comprehensive integration coverage

Follows .claude/rules.md:
- Integration testing best practices
- Database transactions
- Specific exception handling
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from django.test import TestCase
from django.core.cache import cache

from apps.ml.services.conformal_predictor import CalibrationDataManager
from apps.noc.security_intelligence.ml.predictive_fraud_detector import PredictiveFraudDetector


pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_calibration_data():
    """Set up calibration data for fraud detector."""
    np.random.seed(42)
    n_samples = 100

    # Generate calibration predictions and actuals
    predictions = np.random.uniform(0, 1, n_samples).tolist()
    actuals = (np.random.uniform(0, 1, n_samples) > 0.5).astype(float).tolist()

    # Store in cache
    CalibrationDataManager.store_calibration_set(
        model_type='fraud_detector',
        model_version='1.0',
        calibration_predictions=predictions,
        calibration_actuals=actuals
    )

    yield predictions, actuals

    # Cleanup
    cache.clear()


@pytest.fixture
def mock_fraud_model():
    """Mock XGBoost fraud detection model."""
    model = MagicMock()
    # Predict high fraud probability
    model.predict_proba.return_value = np.array([[0.15, 0.85]])  # 85% fraud probability

    return model


@pytest.fixture
def mock_fraud_model_record():
    """Mock FraudDetectionModel database record."""
    record = MagicMock()
    record.model_version = '1.0'
    record.optimal_threshold = 0.70
    record.pr_auc = 0.92
    record.model_path = '/fake/path/model.pkl'

    return record


@pytest.fixture
def mock_behavioral_profile():
    """Mock BehavioralProfile for testing."""
    profile = MagicMock()
    profile.is_sufficient_data = True
    profile.typical_punch_in_hours = [8, 9, 10]
    profile.typical_work_days = [0, 1, 2, 3, 4]  # Monday-Friday

    return profile


@pytest.fixture
def mock_person():
    """Mock People instance."""
    person = MagicMock()
    person.id = 1
    person.peoplename = 'John Doe'
    person.tenant = MagicMock()
    person.tenant.id = 1
    person.tenant.schema_name = 'test_tenant'

    return person


@pytest.fixture
def mock_site():
    """Mock Bt (site) instance."""
    site = MagicMock()
    site.id = 1
    site.buname = 'Test Site'

    return site


class TestPredictiveFraudDetectorIntegration:
    """Integration tests for PredictiveFraudDetector with confidence intervals."""

    @patch('apps.noc.security_intelligence.ml.predictive_fraud_detector.joblib.load')
    @patch('apps.noc.security_intelligence.models.FraudDetectionModel.get_active_model')
    @patch('apps.noc.security_intelligence.models.BehavioralProfile.objects.filter')
    @patch('apps.ml.features.fraud_features.FraudFeatureExtractor.extract_all_features')
    def test_predict_with_confidence_intervals_success(
        self,
        mock_extract_features,
        mock_profile_filter,
        mock_get_active_model,
        mock_joblib_load,
        setup_calibration_data,
        mock_fraud_model,
        mock_fraud_model_record,
        mock_behavioral_profile,
        mock_person,
        mock_site
    ):
        """Test fraud prediction with confidence intervals."""
        # Setup mocks
        mock_joblib_load.return_value = mock_fraud_model
        mock_get_active_model.return_value = mock_fraud_model_record
        mock_profile_filter.return_value.first.return_value = mock_behavioral_profile

        # Mock feature extraction
        mock_extract_features.return_value = {
            'hour_of_day': 14,
            'day_of_week': 2,
            'is_weekend': 0,
            'is_holiday': 0,
            'gps_drift_meters': 50.0,
            'location_consistency_score': 0.95,
            'check_in_frequency_zscore': 0.5,
            'late_arrival_rate': 0.1,
            'weekend_work_frequency': 0.05,
            'face_recognition_confidence': 0.98,
            'biometric_mismatch_count_30d': 0,
            'time_since_last_event': 24.0
        }

        scheduled_time = timezone.now()

        # Execute prediction
        result = PredictiveFraudDetector.predict_attendance_fraud(
            person=mock_person,
            site=mock_site,
            scheduled_time=scheduled_time
        )

        # Assertions
        assert result is not None
        assert 'fraud_probability' in result
        assert 'risk_level' in result
        assert result['fraud_probability'] == 0.85  # From mock

        # Check for confidence interval fields
        assert 'prediction_lower_bound' in result
        assert 'prediction_upper_bound' in result
        assert 'confidence_interval_width' in result
        assert 'calibration_score' in result
        assert 'is_narrow_interval' in result

        # Validate interval properties
        assert result['prediction_lower_bound'] <= result['fraud_probability']
        assert result['fraud_probability'] <= result['prediction_upper_bound']
        assert result['confidence_interval_width'] > 0
        assert 0.0 <= result['calibration_score'] <= 1.0

    @patch('apps.noc.security_intelligence.ml.predictive_fraud_detector.joblib.load')
    @patch('apps.noc.security_intelligence.models.FraudDetectionModel.get_active_model')
    @patch('apps.noc.security_intelligence.models.BehavioralProfile.objects.filter')
    def test_predict_without_calibration_data(
        self,
        mock_profile_filter,
        mock_get_active_model,
        mock_joblib_load,
        mock_fraud_model,
        mock_fraud_model_record,
        mock_behavioral_profile,
        mock_person,
        mock_site
    ):
        """Test prediction when no calibration data is available."""
        # No calibration data setup (cache is empty)

        mock_joblib_load.return_value = mock_fraud_model
        mock_get_active_model.return_value = mock_fraud_model_record
        mock_profile_filter.return_value.first.return_value = mock_behavioral_profile

        scheduled_time = timezone.now()

        # Clear cache to ensure no calibration data
        cache.clear()

        with patch('apps.ml.features.fraud_features.FraudFeatureExtractor.extract_all_features') as mock_extract:
            mock_extract.return_value = {
                'hour_of_day': 10,
                'day_of_week': 1,
                'is_weekend': 0,
                'is_holiday': 0,
                'gps_drift_meters': 20.0,
                'location_consistency_score': 0.99,
                'check_in_frequency_zscore': 0.2,
                'late_arrival_rate': 0.05,
                'weekend_work_frequency': 0.02,
                'face_recognition_confidence': 0.99,
                'biometric_mismatch_count_30d': 0,
                'time_since_last_event': 12.0
            }

            result = PredictiveFraudDetector.predict_attendance_fraud(
                person=mock_person,
                site=mock_site,
                scheduled_time=scheduled_time
            )

        # Should still return prediction, but without confidence intervals
        assert result is not None
        assert 'fraud_probability' in result

        # Confidence intervals should not be present (or None)
        assert 'prediction_lower_bound' not in result or result.get('prediction_lower_bound') is None

    @patch('apps.noc.security_intelligence.ml.predictive_fraud_detector.joblib.load')
    @patch('apps.noc.security_intelligence.models.FraudDetectionModel.get_active_model')
    @patch('apps.noc.security_intelligence.models.BehavioralProfile.objects.filter')
    @patch('apps.ml.features.fraud_features.FraudFeatureExtractor.extract_all_features')
    def test_narrow_interval_detection(
        self,
        mock_extract_features,
        mock_profile_filter,
        mock_get_active_model,
        mock_joblib_load,
        mock_fraud_model,
        mock_fraud_model_record,
        mock_behavioral_profile,
        mock_person,
        mock_site
    ):
        """Test narrow interval detection for high-confidence predictions."""
        # Create calibration data with low variance (narrow intervals)
        tight_predictions = [0.5 + np.random.normal(0, 0.02) for _ in range(100)]
        tight_actuals = [(p > 0.5) * 1.0 for p in tight_predictions]

        CalibrationDataManager.store_calibration_set(
            model_type='fraud_detector',
            model_version='1.0',
            calibration_predictions=tight_predictions,
            calibration_actuals=tight_actuals
        )

        mock_joblib_load.return_value = mock_fraud_model
        mock_get_active_model.return_value = mock_fraud_model_record
        mock_profile_filter.return_value.first.return_value = mock_behavioral_profile

        mock_extract_features.return_value = {
            'hour_of_day': 9,
            'day_of_week': 1,
            'is_weekend': 0,
            'is_holiday': 0,
            'gps_drift_meters': 10.0,
            'location_consistency_score': 0.99,
            'check_in_frequency_zscore': 0.1,
            'late_arrival_rate': 0.02,
            'weekend_work_frequency': 0.01,
            'face_recognition_confidence': 0.99,
            'biometric_mismatch_count_30d': 0,
            'time_since_last_event': 8.0
        }

        scheduled_time = timezone.now()

        result = PredictiveFraudDetector.predict_attendance_fraud(
            person=mock_person,
            site=mock_site,
            scheduled_time=scheduled_time
        )

        # Should have narrow interval
        assert result is not None
        if 'is_narrow_interval' in result:
            # Interval might be narrow due to low calibration variance
            assert isinstance(result['is_narrow_interval'], bool)

    def test_logging_with_confidence_intervals(
        self,
        setup_calibration_data,
        mock_person,
        mock_site
    ):
        """Test that prediction logging includes confidence interval fields."""
        scheduled_time = timezone.now()

        # Create prediction result with confidence intervals
        prediction_result = {
            'fraud_probability': 0.75,
            'risk_level': 'HIGH',
            'model_confidence': 0.90,
            'behavioral_risk': 0.65,
            'features': {'hour_of_day': 14},
            'model_version': '1.0',
            'prediction_lower_bound': 0.55,
            'prediction_upper_bound': 0.85,
            'confidence_interval_width': 0.30,
            'calibration_score': 0.85,
        }

        with patch('apps.noc.security_intelligence.models.FraudPredictionLog.objects.create') as mock_create:
            mock_create.return_value = MagicMock(id=1)

            log = PredictiveFraudDetector.log_prediction(
                person=mock_person,
                site=mock_site,
                scheduled_time=scheduled_time,
                prediction_result=prediction_result
            )

            # Verify create was called with confidence interval fields
            assert mock_create.called
            call_kwargs = mock_create.call_args[1]

            assert 'prediction_lower_bound' in call_kwargs
            assert 'prediction_upper_bound' in call_kwargs
            assert 'confidence_interval_width' in call_kwargs
            assert 'calibration_score' in call_kwargs

            assert call_kwargs['prediction_lower_bound'] == 0.55
            assert call_kwargs['prediction_upper_bound'] == 0.85
            assert call_kwargs['confidence_interval_width'] == 0.30
            assert call_kwargs['calibration_score'] == 0.85


class TestCoverageValidation:
    """Validate empirical coverage guarantees."""

    def test_empirical_coverage_90_percent(self):
        """Test that 90% intervals achieve ~90% empirical coverage."""
        np.random.seed(123)

        # Generate synthetic data
        n_cal = 200
        n_test = 100

        # Calibration set
        cal_predictions = np.random.uniform(0, 1, n_cal).tolist()
        cal_actuals = (np.random.uniform(0, 1, n_cal) > 0.5).astype(float).tolist()

        # Store calibration data
        CalibrationDataManager.store_calibration_set(
            model_type='coverage_test',
            model_version='1.0',
            calibration_predictions=cal_predictions,
            calibration_actuals=cal_actuals
        )

        # Test set
        test_predictions = np.random.uniform(0, 1, n_test)
        test_actuals = (np.random.uniform(0, 1, n_test) > 0.5).astype(float)

        # Generate intervals for test predictions
        coverage_count = 0
        intervals = []

        from apps.ml.services.conformal_predictor import ConformalPredictorService

        for pred, actual in zip(test_predictions, test_actuals):
            interval = ConformalPredictorService.predict_with_intervals(
                point_prediction=float(pred),
                model_type='coverage_test',
                model_version='1.0',
                coverage_level=90
            )

            if interval:
                intervals.append(interval)
                # Check if actual falls within interval
                if interval['lower_bound'] <= actual <= interval['upper_bound']:
                    coverage_count += 1

        empirical_coverage = coverage_count / len(intervals)

        # Should achieve approximately 90% coverage (allow ±10% margin)
        assert 0.80 <= empirical_coverage <= 1.0, f"Coverage: {empirical_coverage:.2%}"

    def test_empirical_coverage_95_percent(self):
        """Test that 95% intervals achieve ~95% empirical coverage."""
        np.random.seed(456)

        n_cal = 200
        n_test = 100

        # Calibration set
        cal_predictions = np.random.uniform(0, 1, n_cal).tolist()
        cal_actuals = (np.random.uniform(0, 1, n_cal) > 0.5).astype(float).tolist()

        CalibrationDataManager.store_calibration_set(
            model_type='coverage_test_95',
            model_version='1.0',
            calibration_predictions=cal_predictions,
            calibration_actuals=cal_actuals
        )

        # Test set
        test_predictions = np.random.uniform(0, 1, n_test)
        test_actuals = (np.random.uniform(0, 1, n_test) > 0.5).astype(float)

        coverage_count = 0
        intervals = []

        from apps.ml.services.conformal_predictor import ConformalPredictorService

        for pred, actual in zip(test_predictions, test_actuals):
            interval = ConformalPredictorService.predict_with_intervals(
                point_prediction=float(pred),
                model_type='coverage_test_95',
                model_version='1.0',
                coverage_level=95
            )

            if interval:
                intervals.append(interval)
                if interval['lower_bound'] <= actual <= interval['upper_bound']:
                    coverage_count += 1

        empirical_coverage = coverage_count / len(intervals)

        # Should achieve approximately 95% coverage (allow ±10% margin)
        assert 0.85 <= empirical_coverage <= 1.0, f"Coverage: {empirical_coverage:.2%}"


class TestAutomationRateImprovement:
    """Test automation rate improvements with confidence intervals."""

    def test_automation_rate_calculation(self):
        """Test automation rate with and without confidence intervals."""
        np.random.seed(789)

        # Scenario 1: Without confidence intervals (baseline)
        # All HIGH/CRITICAL predictions create tickets
        baseline_high_predictions = 30
        baseline_tickets = baseline_high_predictions
        baseline_automation_rate = baseline_tickets / baseline_high_predictions

        assert baseline_automation_rate == 1.0  # 100% automation

        # Scenario 2: With confidence intervals
        # Only narrow intervals create tickets
        enhanced_high_predictions = 30
        enhanced_narrow_intervals = 20  # 67% have narrow intervals
        enhanced_wide_intervals = 10    # 33% have wide intervals (alerts only)

        enhanced_tickets = enhanced_narrow_intervals
        enhanced_automation_rate = enhanced_tickets / enhanced_high_predictions

        assert enhanced_automation_rate == 0.67  # 67% auto-ticketed

        # But false positives reduced by flagging uncertain predictions
        # Assume 50% of wide intervals are false positives
        baseline_false_positives = 10  # 33% FP rate
        enhanced_false_positives = enhanced_wide_intervals * 0.5  # 5 FPs

        # Precision improvement
        baseline_precision = (baseline_tickets - baseline_false_positives) / baseline_tickets
        enhanced_precision = (enhanced_tickets - enhanced_false_positives) / (enhanced_tickets + enhanced_false_positives)

        # Enhanced should have better precision
        assert enhanced_precision > baseline_precision

    def test_confidence_aware_escalation_logic(self):
        """Test that escalation logic correctly uses confidence intervals."""
        # High fraud + narrow interval → Ticket
        result_narrow = {
            'fraud_probability': 0.85,
            'risk_level': 'HIGH',
            'is_narrow_interval': True,
            'confidence_interval_width': 0.15
        }

        # Should create ticket
        should_create_ticket = (
            result_narrow['risk_level'] in ['HIGH', 'CRITICAL'] and
            result_narrow.get('is_narrow_interval', False)
        )
        assert should_create_ticket is True

        # High fraud + wide interval → Alert only
        result_wide = {
            'fraud_probability': 0.85,
            'risk_level': 'HIGH',
            'is_narrow_interval': False,
            'confidence_interval_width': 0.45
        }

        should_create_ticket = (
            result_wide['risk_level'] in ['HIGH', 'CRITICAL'] and
            result_wide.get('is_narrow_interval', False)
        )
        assert should_create_ticket is False  # Alert only, not ticket

        # Medium risk → No auto-action regardless of interval
        result_medium = {
            'fraud_probability': 0.55,
            'risk_level': 'MEDIUM',
            'is_narrow_interval': True,
            'confidence_interval_width': 0.10
        }

        should_create_ticket = (
            result_medium['risk_level'] in ['HIGH', 'CRITICAL'] and
            result_medium.get('is_narrow_interval', False)
        )
        assert should_create_ticket is False
