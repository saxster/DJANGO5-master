"""
Integration Tests for ML Prediction → Log → Alert Workflow.

Tests complete prediction workflow from attendance event to alert creation.
Follows .claude/rules.md testing standards.
"""

import pytest
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestMLPredictionIntegration:
    """Test ML prediction integration with orchestrator."""

    def test_prediction_log_alert_workflow_high_risk(
        self, security_config, attendance_event, mocker
    ):
        """Test complete workflow: Prediction → Log → Alert for HIGH risk."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import FraudPredictionLog
        from apps.noc.models import NOCAlertEvent

        # Mock ML predictor to return HIGH risk
        high_risk_prediction = {
            'fraud_probability': 0.72,
            'risk_level': 'HIGH',
            'model_confidence': 0.89,
            'behavioral_risk': 0.55,
            'features': {
                'hour_of_day': 22,
                'is_weekend': True,
                'gps_drift_meters': 450,
            },
            'model_version': 'v1.2.0',
            'prediction_method': 'xgboost',
        }

        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value=high_risk_prediction
        )

        # Process attendance event
        result = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify prediction was logged
        prediction_log = FraudPredictionLog.objects.filter(
            person=attendance_event.people,
            site=attendance_event.bu,
            prediction_type='ATTENDANCE'
        ).first()

        assert prediction_log is not None
        assert prediction_log.fraud_probability == 0.72
        assert prediction_log.risk_level == 'HIGH'
        assert prediction_log.model_version == 'v1.2.0'

        # Verify alert was created
        alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION',
            entity_id=attendance_event.id
        ).first()

        assert alert is not None
        assert alert.severity == 'HIGH'
        assert alert.metadata['ml_prediction']['fraud_probability'] == 0.72
        assert alert.metadata['person_name'] == attendance_event.people.peoplename

    def test_prediction_log_alert_workflow_critical_risk(
        self, security_config, attendance_event, mocker
    ):
        """Test complete workflow for CRITICAL risk with detailed features."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import FraudPredictionLog
        from apps.noc.models import NOCAlertEvent

        # Mock ML predictor to return CRITICAL risk
        critical_risk_prediction = {
            'fraud_probability': 0.94,
            'risk_level': 'CRITICAL',
            'model_confidence': 0.96,
            'behavioral_risk': 0.88,
            'features': {
                'hour_of_day': 3,
                'day_of_week': 0,
                'is_weekend': False,
                'gps_drift_meters': 2300,
                'location_consistency_score': 0.12,
                'biometric_mismatch_count_30d': 5,
            },
            'model_version': 'v1.2.0',
            'prediction_method': 'xgboost',
        }

        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value=critical_risk_prediction
        )

        # Process attendance event
        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify prediction was logged with all features
        prediction_log = FraudPredictionLog.objects.filter(
            person=attendance_event.people,
            site=attendance_event.bu
        ).first()

        assert prediction_log is not None
        assert prediction_log.fraud_probability == 0.94
        assert prediction_log.risk_level == 'CRITICAL'
        assert prediction_log.features_used['gps_drift_meters'] == 2300
        assert prediction_log.baseline_deviation == 0.88

        # Verify CRITICAL alert was created
        alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION',
            entity_id=attendance_event.id
        ).first()

        assert alert is not None
        assert alert.severity == 'CRITICAL'
        assert '94.0%' in alert.message or '94%' in alert.message

    def test_prediction_log_no_alert_for_low_risk(
        self, security_config, attendance_event, mocker
    ):
        """Test that LOW risk creates log but no alert."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import FraudPredictionLog
        from apps.noc.models import NOCAlertEvent

        # Mock ML predictor to return LOW risk
        low_risk_prediction = {
            'fraud_probability': 0.18,
            'risk_level': 'LOW',
            'model_confidence': 0.85,
            'behavioral_risk': 0.05,
            'features': {'hour_of_day': 9, 'is_weekend': False},
            'model_version': 'v1.2.0',
            'prediction_method': 'xgboost',
        }

        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value=low_risk_prediction
        )

        # Process attendance event
        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify prediction was logged
        prediction_log = FraudPredictionLog.objects.filter(
            person=attendance_event.people,
            site=attendance_event.bu
        ).first()

        assert prediction_log is not None
        assert prediction_log.fraud_probability == 0.18
        assert prediction_log.risk_level == 'LOW'

        # Verify NO alert was created
        alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION',
            entity_id=attendance_event.id
        ).first()

        assert alert is None

    def test_ml_prediction_with_heuristic_anomaly_detection(
        self, security_config, attendance_event, other_person, mocker
    ):
        """Test ML prediction runs alongside heuristic anomaly detection."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.security_intelligence.models import (
            ShiftScheduleCache,
            AttendanceAnomalyLog,
            FraudPredictionLog
        )

        # Create schedule mismatch for heuristic detection
        ShiftScheduleCache.objects.create(
            tenant=attendance_event.tenant,
            person=other_person,  # Different person scheduled
            site=attendance_event.bu,
            shift_date=attendance_event.datefor,
            scheduled_start=attendance_event.punchintime,
            scheduled_end=attendance_event.punchintime + timedelta(hours=8),
            cache_valid_until=timezone.now() + timedelta(days=1)
        )

        # Mock ML predictor
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value={
                'fraud_probability': 0.68,
                'risk_level': 'HIGH',
                'model_confidence': 0.87,
                'behavioral_risk': 0.5,
                'features': {},
                'model_version': 'v1.0',
                'prediction_method': 'xgboost',
            }
        )
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.log_prediction'
        )

        # Process attendance event
        result = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify both ML prediction log and heuristic anomaly log exist
        prediction_log = FraudPredictionLog.objects.filter(
            person=attendance_event.people
        ).first()
        assert prediction_log is not None

        anomaly_log = AttendanceAnomalyLog.objects.filter(
            attendance_event=attendance_event
        ).first()
        assert anomaly_log is not None
        assert anomaly_log.anomaly_type == 'WRONG_PERSON'

    def test_ml_prediction_exception_doesnt_break_workflow(
        self, security_config, attendance_event, mocker
    ):
        """Test that ML prediction exception allows heuristics to run."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator

        # Mock ML predictor to raise exception
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            side_effect=Exception("Database connection failed")
        )

        # Process should complete without exception
        result = SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify result structure is valid
        assert isinstance(result, dict)
        assert 'anomalies' in result
        assert 'biometric_logs' in result
        assert 'gps_logs' in result

    def test_prediction_metadata_contains_all_fields(
        self, security_config, attendance_event, mocker
    ):
        """Test that alert metadata contains all required ML prediction fields."""
        from apps.noc.security_intelligence.services import SecurityAnomalyOrchestrator
        from apps.noc.models import NOCAlertEvent

        # Mock comprehensive prediction
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.predict_attendance_fraud',
            return_value={
                'fraud_probability': 0.81,
                'risk_level': 'CRITICAL',
                'model_confidence': 0.93,
                'behavioral_risk': 0.72,
                'features': {
                    'hour_of_day': 2,
                    'gps_drift_meters': 1800,
                    'biometric_mismatch_count_30d': 3,
                },
                'model_version': 'v1.3.0',
                'prediction_method': 'xgboost',
                'optimal_threshold': 0.65,
            }
        )
        mocker.patch(
            'apps.noc.security_intelligence.ml.predictive_fraud_detector.PredictiveFraudDetector.log_prediction'
        )

        # Process attendance event
        SecurityAnomalyOrchestrator.process_attendance_event(attendance_event)

        # Verify alert metadata
        alert = NOCAlertEvent.objects.filter(
            alert_type='ML_FRAUD_PREDICTION'
        ).first()

        assert alert is not None
        metadata = alert.metadata

        # Verify required fields
        assert 'ml_prediction' in metadata
        assert 'model_version' in metadata
        assert 'features' in metadata
        assert 'person_id' in metadata
        assert 'person_name' in metadata
        assert 'prediction_method' in metadata
        assert 'behavioral_risk' in metadata

        # Verify values
        assert metadata['model_version'] == 'v1.3.0'
        assert metadata['prediction_method'] == 'xgboost'
        assert metadata['behavioral_risk'] == 0.72
        assert metadata['features']['gps_drift_meters'] == 1800
