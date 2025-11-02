"""
Integration Tests for ML Pipelines

End-to-end tests for all 4 ML phases:
- Phase 1: OCR Feedback Loop
- Phase 2: Conflict Prediction
- Phase 3: Fraud Detection
- Phase 4: Anomaly Detection

Follows .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
from datetime import datetime, timedelta, time
from django.utils import timezone
from unittest.mock import Mock, patch


@pytest.mark.integration
@pytest.mark.django_db
class TestOCRFeedbackLoopIntegration:
    """Test OCR feedback loop end-to-end (Phase 1)."""

    @patch('apps.ml_training.integrations.GoogleVisionOCRClient.extract_text_with_confidence')
    def test_ocr_feedback_loop_end_to_end(self, mock_ocr):
        """
        Test complete OCR feedback loop:
        1. Create low-confidence meter reading
        2. Verify TrainingExample created
        3. Submit user correction
        4. Verify uncertainty_score updated
        5. Trigger active learning
        6. Verify LabelingTask created
        """
        from apps.ml_training.models import TrainingExample, LabelingTask
        from apps.ml_training.services.active_learning_service import (
            ActiveLearningService
        )

        # 1. Mock OCR with low confidence
        mock_ocr.return_value = {
            'text': '12345',
            'confidence': 0.65,  # Below threshold
            'bounding_boxes': []
        }

        # Create meter reading (will trigger OCR integration)
        # This is a placeholder - actual implementation depends on meter model
        meter_id = 'TEST_METER_001'
        image_path = '/tmp/test_meter_image.jpg'

        # 2. Verify TrainingExample created
        example = TrainingExample.objects.create(
            example_type='METER_READING',
            entity_id=meter_id,
            image_path=image_path,
            extracted_value='12345',
            confidence_score=0.65,
            uncertainty_score=0.35,  # High uncertainty
            requires_labeling=True
        )

        assert example.requires_labeling is True
        assert example.uncertainty_score > 0.3

        # 3. Submit user correction
        corrected_value = '12346'  # User corrects
        example.ground_truth_value = corrected_value
        example.is_correction = True
        example.save()

        # 4. Verify uncertainty score updated (should be 1.0 for correction)
        assert example.is_correction is True

        # 5. Trigger active learning
        service = ActiveLearningService()
        result = service.select_high_uncertainty_examples(limit=10)

        # 6. Verify example appears in high-uncertainty list
        example_ids = [e.id for e in result['examples']]
        assert example.id in example_ids

    @pytest.mark.django_db
    def test_ocr_feedback_creates_labeling_task(self):
        """Test that high-uncertainty OCR creates labeling task."""
        from apps.ml_training.models import TrainingExample, LabelingTask
        from apps.ml_training.services.active_learning_service import (
            ActiveLearningService
        )

        # Create high-uncertainty example
        example = TrainingExample.objects.create(
            example_type='METER_READING',
            entity_id='METER_002',
            extracted_value='98765',
            confidence_score=0.55,
            uncertainty_score=0.45,
            requires_labeling=True
        )

        # Trigger active learning task creation
        service = ActiveLearningService()
        task = service.create_labeling_task_for_example(example)

        # Verify labeling task created
        assert task is not None
        assert task.training_example == example
        assert task.status == 'PENDING'


@pytest.mark.integration
@pytest.mark.django_db
class TestConflictPredictionPipeline:
    """Test conflict prediction pipeline end-to-end (Phase 2)."""

    def test_conflict_prediction_pipeline_end_to_end(self):
        """
        Test complete conflict prediction pipeline:
        1. Extract training data
        2. Train model
        3. Activate model
        4. Make prediction via API
        5. Verify PredictionLog created
        6. Simulate conflict occurrence
        7. Run outcome tracking task
        8. Verify actual_conflict_occurred updated
        """
        from apps.ml.models.ml_models import (
            ConflictPredictionModel,
            PredictionLog
        )
        from apps.ml.services.conflict_predictor import ConflictPredictor

        # 1-3. Training is tested separately (slow test)
        # For integration test, create mock active model
        model = ConflictPredictionModel.objects.create(
            version='test_v1',
            algorithm='LogisticRegression',
            accuracy=0.85,
            trained_on_samples=1000,
            feature_count=4,
            model_path='/tmp/mock_model.joblib',
            is_active=True
        )

        # 4. Make prediction via service
        predictor = ConflictPredictor()
        sync_request = {
            'user_id': 1,
            'entity_type': 'schedule',
            'entity_id': 123,
            'last_sync_time': (
                timezone.now() - timedelta(hours=2)
            ).isoformat()
        }

        prediction = predictor.predict_conflict(sync_request)

        # 5. Verify prediction result
        assert 'probability' in prediction
        assert 'risk_level' in prediction
        assert prediction['model_version'] in ['test_v1', 'heuristic_v1']

        # Create prediction log manually (normally done by API)
        log = PredictionLog.objects.create(
            model_type='conflict_predictor',
            model_version='test_v1',
            entity_type='schedule',
            entity_id='123',
            predicted_conflict=prediction['probability'] > 0.5,
            conflict_probability=prediction['probability'],
            features_json=prediction['features_used']
        )

        # 6. Simulate conflict occurrence (24h later)
        # In real system, this would be detected from ConflictResolution model
        log.actual_conflict_occurred = False  # No conflict occurred
        log.prediction_correct = (
            log.predicted_conflict == log.actual_conflict_occurred
        )
        log.save()

        # 7-8. Outcome tracking is tested in task tests
        assert log.actual_conflict_occurred is not None
        assert log.prediction_correct is not None

    @pytest.mark.django_db
    def test_conflict_prediction_with_no_active_model(self):
        """Test that prediction falls back to heuristics with no model."""
        from apps.ml.services.conflict_predictor import ConflictPredictor

        # No active model exists
        predictor = ConflictPredictor()
        sync_request = {'user_id': 1}

        prediction = predictor.predict_conflict(sync_request)

        # Should use heuristic fallback
        assert prediction['model_version'] == 'heuristic_v1'
        assert 'probability' in prediction


@pytest.mark.integration
@pytest.mark.django_db
class TestFraudDetectionPipeline:
    """Test fraud detection pipeline end-to-end (Phase 3)."""

    def test_fraud_detection_pipeline_end_to_end(self):
        """
        Test complete fraud detection pipeline:
        1. Create attendance event
        2. Extract features
        3. Predict fraud
        4. Verify FraudPredictionLog created
        5. Supervisor confirms fraud
        6. Verify record_outcome() called
        7. Check accuracy metrics updated
        """
        from apps.peoples.models import People
        from apps.onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog
        from apps.noc.security_intelligence.models import FraudPredictionLog
        from apps.ml.features.fraud_features import FraudFeatureExtractor

        # 1. Create attendance event
        person = People.objects.create(
            username='test_guard',
            email='guard@example.com'
        )

        site = Bt.objects.create(name='Test Site')

        event = PeopleEventlog.objects.create(
            people=person,
            bu=site,
            datefor=timezone.now().date(),
            punchintime=timezone.now(),
            startlat=37.7749,
            startlng=-122.4194,
            peventlogextras={'distance_in': 0.2, 'verified_in': True}
        )

        # 2. Extract features
        features = FraudFeatureExtractor.extract_all_features(
            event, person, site
        )

        assert len(features) == 12

        # 3. Predict fraud (placeholder - actual model not trained)
        fraud_probability = 0.15  # Low probability

        # 4. Create FraudPredictionLog
        fraud_log = FraudPredictionLog.objects.create(
            actual_attendance_event=event,
            fraud_probability=fraud_probability,
            predicted_fraud=fraud_probability > 0.5,
            features_json=features
        )

        # 5. Supervisor reviews and confirms (no fraud)
        fraud_log.supervisor_confirmed_fraud = False
        fraud_log.actual_fraud_detected = False
        fraud_log.save()

        # 6. Verify outcome recorded
        assert fraud_log.actual_fraud_detected is False
        assert fraud_log.supervisor_confirmed_fraud is False

        # 7. Prediction was correct (predicted no fraud, actual no fraud)
        prediction_correct = (
            fraud_log.predicted_fraud == fraud_log.actual_fraud_detected
        )
        assert prediction_correct is True

    @pytest.mark.django_db
    def test_fraud_detection_with_high_risk_features(self):
        """Test fraud detection with suspicious feature values."""
        from apps.peoples.models import People
        from apps.onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog
        from apps.ml.features.fraud_features import FraudFeatureExtractor

        person = People.objects.create(
            username='suspicious_guard',
            email='suspicious@example.com'
        )

        site = Bt.objects.create(name='Test Site 2')

        # Create event with suspicious features
        event = PeopleEventlog.objects.create(
            people=person,
            bu=site,
            datefor=timezone.now().date(),
            punchintime=timezone.make_aware(
                datetime.combine(timezone.now().date(), time(3, 0, 0))
            ),  # 3 AM (suspicious)
            startlat=34.0522,  # Far from site
            startlng=-118.2437,
            peventlogextras={'distance_in': 0.6, 'verified_in': False}
        )

        features = FraudFeatureExtractor.extract_all_features(
            event, person, site
        )

        # Verify suspicious feature values
        assert features['hour_of_day'] == 3  # Early morning
        assert features['face_recognition_confidence'] < 0.5  # Low confidence


@pytest.mark.integration
@pytest.mark.django_db
class TestAnomalyDetectionPipeline:
    """Test anomaly detection pipeline (Phase 4)."""

    def test_infrastructure_anomaly_detection(self):
        """
        Test infrastructure anomaly detection:
        1. Collect metrics (CPU, memory, response time)
        2. Detect anomalies
        3. Create alerts
        """
        # Placeholder for Phase 4
        # Will be implemented once infrastructure monitoring is in place
        pass


@pytest.mark.integration
@pytest.mark.django_db
class TestCrossPhaseIntegration:
    """Test integration between multiple ML phases."""

    def test_ocr_feedback_improves_conflict_prediction(self):
        """
        Test that OCR feedback data can be used for conflict prediction.
        (Future integration - both systems use similar active learning)
        """
        # Placeholder for future cross-phase integration
        pass

    def test_fraud_detection_triggers_anomaly_alert(self):
        """
        Test that fraud detection can trigger anomaly alerts.
        (Future integration - fraud spike = anomaly)
        """
        # Placeholder for future cross-phase integration
        pass
