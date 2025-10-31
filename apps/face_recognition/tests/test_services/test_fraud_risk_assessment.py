"""
Tests for Fraud Risk Assessment Service.

Tests fraud risk assessment including confidence analysis, quality checks,
anti-spoofing integration, and historical fraud pattern analysis.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.face_recognition.services.fraud_risk_assessment import FraudRiskAssessmentService
from apps.face_recognition.models import FaceVerificationLog


@pytest.fixture
def fraud_service():
    """Create fraud risk assessment service instance."""
    return FraudRiskAssessmentService()


@pytest.mark.django_db
class TestFraudRiskAssessmentService:
    """Test suite for FraudRiskAssessmentService."""

    def test_service_initialization(self, fraud_service):
        """Test service initializes with correct thresholds."""
        assert fraud_service.low_confidence_threshold == 0.5
        assert fraud_service.poor_quality_threshold == 0.4
        assert fraud_service.high_fraud_threshold == 0.7

    def test_assess_fraud_risk_low_confidence(self, fraud_service, sample_user):
        """Test fraud risk increases with low confidence."""
        result = {'confidence': 0.3, 'fraud_indicators': []}
        assessment = fraud_service.assess_fraud_risk(result, sample_user.id)

        assert assessment['fraud_risk_score'] >= 0.3
        assert 'LOW_VERIFICATION_CONFIDENCE' in assessment['fraud_indicators']

    def test_assess_fraud_risk_poor_quality(self, fraud_service, sample_user):
        """Test fraud risk increases with poor quality."""
        result = {
            'confidence': 0.8,
            'quality_metrics': {'overall_quality': 0.2},
            'fraud_indicators': []
        }
        assessment = fraud_service.assess_fraud_risk(result, sample_user.id)

        assert assessment['fraud_risk_score'] >= 0.2
        assert 'POOR_IMAGE_QUALITY' in assessment['fraud_indicators']

    def test_assess_fraud_risk_spoof_detected(self, fraud_service, sample_user):
        """Test fraud risk increases when spoof detected."""
        result = {
            'confidence': 0.8,
            'anti_spoofing_result': {
                'spoof_detected': True,
                'fraud_indicators': ['TEXTURE_SPOOFING_DETECTED']
            },
            'fraud_indicators': []
        }
        assessment = fraud_service.assess_fraud_risk(result, sample_user.id)

        assert assessment['fraud_risk_score'] >= 0.5
        assert 'TEXTURE_SPOOFING_DETECTED' in assessment['fraud_indicators']

    def test_assess_fraud_risk_model_inconsistency(self, fraud_service, sample_user):
        """Test fraud risk increases with model inconsistency."""
        result = {
            'confidence': 0.8,
            'model_results': {
                'FaceNet512': {'similarity': 0.9},
                'ArcFace': {'similarity': 0.5},
                'InsightFace': {'similarity': 0.6}
            },
            'fraud_indicators': []
        }
        assessment = fraud_service.assess_fraud_risk(result, sample_user.id)

        assert 'MODEL_INCONSISTENCY' in assessment['fraud_indicators']

    def test_assess_fraud_risk_recent_fraud_history(self, fraud_service, sample_user):
        """Test fraud risk increases with recent fraud history."""
        # Create recent fraudulent verifications
        for i in range(3):
            FaceVerificationLog.objects.create(
                user=sample_user,
                verified=False,
                fraud_risk_score=0.8,
                verification_timestamp=timezone.now() - timedelta(days=i)
            )

        result = {'confidence': 0.8, 'fraud_indicators': []}
        assessment = fraud_service.assess_fraud_risk(result, sample_user.id)

        assert 'RECENT_FRAUD_HISTORY' in assessment['fraud_indicators']

    def test_make_verification_decision_all_pass(self, fraud_service):
        """Test verification decision when all checks pass."""
        result = {
            'threshold_met': True,
            'confidence_met': True,
            'fraud_risk_score': 0.2,
            'anti_spoofing_result': {'spoof_detected': False},
            'quality_metrics': {'overall_quality': 0.8}
        }
        decision = fraud_service.make_verification_decision(result)
        assert decision is True

    def test_make_verification_decision_high_fraud_risk(self, fraud_service):
        """Test verification fails with high fraud risk."""
        result = {
            'threshold_met': True,
            'confidence_met': True,
            'fraud_risk_score': 0.9,  # High fraud risk
            'anti_spoofing_result': {'spoof_detected': False},
            'quality_metrics': {'overall_quality': 0.8}
        }
        decision = fraud_service.make_verification_decision(result)
        assert decision is False

    def test_make_verification_decision_spoof_detected(self, fraud_service):
        """Test verification fails when spoof detected."""
        result = {
            'threshold_met': True,
            'confidence_met': True,
            'fraud_risk_score': 0.2,
            'anti_spoofing_result': {'spoof_detected': True},  # Spoof detected
            'quality_metrics': {'overall_quality': 0.8}
        }
        decision = fraud_service.make_verification_decision(result)
        assert decision is False

    def test_calculate_risk_level_low(self, fraud_service):
        """Test risk level calculation for low risk."""
        level = fraud_service.calculate_risk_level(0.2)
        assert level == 'LOW'

    def test_calculate_risk_level_medium(self, fraud_service):
        """Test risk level calculation for medium risk."""
        level = fraud_service.calculate_risk_level(0.5)
        assert level == 'MEDIUM'

    def test_calculate_risk_level_high(self, fraud_service):
        """Test risk level calculation for high risk."""
        level = fraud_service.calculate_risk_level(0.8)
        assert level == 'HIGH'

    def test_custom_config_initialization(self):
        """Test service initialization with custom config."""
        custom_config = {
            'low_confidence_threshold': 0.6,
            'high_fraud_threshold': 0.8
        }
        service = FraudRiskAssessmentService(config=custom_config)
        assert service.low_confidence_threshold == 0.6
        assert service.high_fraud_threshold == 0.8
