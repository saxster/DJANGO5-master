"""
Tests for Anti-Spoofing Detection Service.

Tests anti-spoofing detection including texture-based and motion-based
spoofing detection.
"""

import pytest
from apps.face_recognition.services.anti_spoofing import (
    AntiSpoofingService,
    MockAntiSpoofingModel,
    MockMotionAntiSpoofingModel
)


@pytest.fixture
def anti_spoofing_service():
    """Create anti-spoofing service instance."""
    return AntiSpoofingService()


@pytest.mark.django_db
class TestAntiSpoofingService:
    """Test suite for AntiSpoofingService."""

    def test_service_initialization(self, anti_spoofing_service):
        """Test service initializes with correct configuration."""
        assert anti_spoofing_service.liveness_threshold == 0.5
        assert 'TEXTURE_BASED' in anti_spoofing_service.anti_spoofing_models
        assert 'MOTION_BASED' in anti_spoofing_service.anti_spoofing_models

    def test_detect_spoofing_returns_valid_structure(self, anti_spoofing_service):
        """Test detect_spoofing returns correct structure."""
        result = anti_spoofing_service.detect_spoofing('test_image.jpg')

        assert 'spoof_detected' in result
        assert 'spoof_score' in result
        assert 'liveness_score' in result
        assert 'model_scores' in result
        assert 'fraud_indicators' in result

    def test_detect_spoofing_liveness_score_calculation(self, anti_spoofing_service):
        """Test liveness score is inverse of spoof score."""
        result = anti_spoofing_service.detect_spoofing('test_image.jpg')

        spoof_score = result['spoof_score']
        liveness_score = result['liveness_score']

        assert liveness_score == pytest.approx(1.0 - spoof_score, abs=0.01)

    def test_detect_spoofing_no_spoof_detected(self, anti_spoofing_service):
        """Test no spoofing detected for normal images (mock)."""
        result = anti_spoofing_service.detect_spoofing('test_image.jpg')

        assert result['spoof_detected'] is False
        assert result['spoof_score'] < anti_spoofing_service.liveness_threshold

    def test_detect_spoofing_fraud_indicators(self, anti_spoofing_service):
        """Test fraud indicators list is present."""
        result = anti_spoofing_service.detect_spoofing('test_image.jpg')

        assert isinstance(result['fraud_indicators'], list)

    def test_update_threshold_valid(self, anti_spoofing_service):
        """Test updating liveness threshold with valid value."""
        anti_spoofing_service.update_threshold(0.7)
        assert anti_spoofing_service.liveness_threshold == 0.7

    def test_update_threshold_invalid_too_high(self, anti_spoofing_service):
        """Test updating threshold with invalid high value."""
        original_threshold = anti_spoofing_service.liveness_threshold
        anti_spoofing_service.update_threshold(1.5)
        # Should not change
        assert anti_spoofing_service.liveness_threshold == original_threshold

    def test_update_threshold_invalid_too_low(self, anti_spoofing_service):
        """Test updating threshold with invalid low value."""
        original_threshold = anti_spoofing_service.liveness_threshold
        anti_spoofing_service.update_threshold(-0.1)
        # Should not change
        assert anti_spoofing_service.liveness_threshold == original_threshold

    def test_custom_config_initialization(self):
        """Test service initialization with custom config."""
        custom_config = {'liveness_threshold': 0.8}
        service = AntiSpoofingService(config=custom_config)
        assert service.liveness_threshold == 0.8


class TestMockAntiSpoofingModel:
    """Test suite for MockAntiSpoofingModel."""

    def test_detect_spoof_returns_dict(self):
        """Test detect_spoof returns dictionary."""
        model = MockAntiSpoofingModel()
        result = model.detect_spoof('test_image.jpg')
        assert isinstance(result, dict)

    def test_detect_spoof_has_required_fields(self):
        """Test detect_spoof returns required fields."""
        model = MockAntiSpoofingModel()
        result = model.detect_spoof('test_image.jpg')

        assert 'spoof_detected' in result
        assert 'spoof_score' in result
        assert 'confidence' in result


class TestMockMotionAntiSpoofingModel:
    """Test suite for MockMotionAntiSpoofingModel."""

    def test_detect_spoof_returns_dict(self):
        """Test detect_spoof returns dictionary."""
        model = MockMotionAntiSpoofingModel()
        result = model.detect_spoof('test_image.jpg')
        assert isinstance(result, dict)

    def test_detect_spoof_has_required_fields(self):
        """Test detect_spoof returns required fields."""
        model = MockMotionAntiSpoofingModel()
        result = model.detect_spoof('test_image.jpg')

        assert 'spoof_detected' in result
        assert 'spoof_score' in result
        assert 'confidence' in result
