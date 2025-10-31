"""
Tests for Multi-Modal Decision Fusion Service.

Tests multi-modal biometric fusion including weighted scoring,
security analysis, and quality adjustments.
"""

import pytest
from apps.face_recognition.services.multi_modal_fusion import MultiModalFusionService


@pytest.fixture
def fusion_service():
    """Create multi-modal fusion service instance."""
    return MultiModalFusionService()


@pytest.mark.django_db
class TestMultiModalFusionService:
    """Test suite for MultiModalFusionService."""

    def test_service_initialization(self, fusion_service):
        """Test service initializes with correct weights."""
        assert fusion_service.modality_weights['face_recognition'] == 0.6
        assert fusion_service.modality_weights['voice_recognition'] == 0.25
        assert fusion_service.modality_weights['behavioral_biometrics'] == 0.15

    def test_fuse_decisions_all_pass(
        self,
        fusion_service,
        mock_modality_results,
        mock_security_analysis,
        mock_quality_metrics
    ):
        """Test fusion decision when all modalities pass."""
        # Modify mock to have all pass
        mock_modality_results['behavioral_biometrics']['verified'] = True
        mock_modality_results['behavioral_biometrics']['confidence'] = 0.85

        result = fusion_service.fuse_decisions(
            mock_modality_results,
            mock_security_analysis,
            mock_quality_metrics
        )

        assert 'verified' in result
        assert result['confidence'] > 0.0
        assert result['fraud_risk_score'] >= 0.0

    def test_fuse_decisions_deepfake_detected(
        self,
        fusion_service,
        mock_modality_results,
        mock_quality_metrics
    ):
        """Test fusion applies security penalty for deepfake."""
        security_analysis = {
            'deepfake_detected': True,  # Deepfake detected
            '3d_liveness_detected': True,
            'advanced_liveness_score': 0.85
        }

        result = fusion_service.fuse_decisions(
            mock_modality_results,
            security_analysis,
            mock_quality_metrics
        )

        assert result['security_penalty'] >= 0.5
        assert result['fraud_risk_score'] >= 0.4

    def test_fuse_decisions_poor_quality(
        self,
        fusion_service,
        mock_modality_results,
        mock_security_analysis
    ):
        """Test fusion applies penalty for poor quality."""
        poor_quality = {'overall_quality': 0.3}  # Poor quality

        result = fusion_service.fuse_decisions(
            mock_modality_results,
            mock_security_analysis,
            poor_quality
        )

        assert result['quality_score'] < 0.5

    def test_fuse_decisions_no_modalities_verified(
        self,
        fusion_service,
        mock_security_analysis,
        mock_quality_metrics
    ):
        """Test fusion fails when no modalities verified."""
        no_verified = {
            'face_recognition': {'verified': False, 'confidence': 0.3},
            'voice_recognition': {'verified': False, 'confidence': 0.2}
        }

        result = fusion_service.fuse_decisions(
            no_verified,
            mock_security_analysis,
            mock_quality_metrics
        )

        assert result['verified'] is False
        assert 'No biometric modalities successfully verified' in result['recommendations']

    def test_update_weights(self, fusion_service):
        """Test updating modality weights."""
        new_weights = {'face_recognition': 0.8, 'voice_recognition': 0.2}
        fusion_service.update_weights(new_weights)

        assert fusion_service.modality_weights['face_recognition'] == 0.8
        assert fusion_service.modality_weights['voice_recognition'] == 0.2

    def test_update_thresholds(self, fusion_service):
        """Test updating decision thresholds."""
        fusion_service.update_thresholds(
            required_confidence=0.85,
            min_modalities=2,
            max_fraud_risk=0.5,
            min_quality_score=0.5
        )

        assert fusion_service.required_confidence == 0.85
        assert fusion_service.min_modalities == 2
        assert fusion_service.max_fraud_risk == 0.5
        assert fusion_service.min_quality_score == 0.5

    def test_fuse_decisions_recommendations(
        self,
        fusion_service,
        mock_modality_results,
        mock_security_analysis
    ):
        """Test fusion generates recommendations when verification fails."""
        poor_quality = {'overall_quality': 0.2}  # Below minimum

        result = fusion_service.fuse_decisions(
            mock_modality_results,
            mock_security_analysis,
            poor_quality
        )

        assert isinstance(result['recommendations'], list)
        if not result['verified']:
            assert len(result['recommendations']) > 0

    def test_fuse_decisions_detailed_scores(
        self,
        fusion_service,
        mock_modality_results,
        mock_security_analysis,
        mock_quality_metrics
    ):
        """Test fusion returns detailed scoring breakdown."""
        result = fusion_service.fuse_decisions(
            mock_modality_results,
            mock_security_analysis,
            mock_quality_metrics
        )

        assert 'detailed_scores' in result
        assert 'weighted_confidence' in result['detailed_scores']
        assert 'security_penalty' in result['detailed_scores']
        assert 'quality_score' in result['detailed_scores']
        assert 'fraud_risk' in result['detailed_scores']
