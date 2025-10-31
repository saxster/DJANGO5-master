"""
Tests for Deepfake Detection Service.

Tests ensemble deepfake detection using multiple models.
"""

import pytest
from apps.face_recognition.services.deepfake_detection import (
    DeepfakeDetectionService,
    DeeperForensicsModel,
    FaceForensicsPlusPlusModel,
    CelebDFModel,
    DFDCModel,
    FaceSwapperDetectionModel
)


@pytest.fixture
def deepfake_service():
    """Create deepfake detection service instance."""
    return DeepfakeDetectionService()


@pytest.mark.django_db
class TestDeepfakeDetectionService:
    """Test suite for DeepfakeDetectionService."""

    def test_service_initialization(self, deepfake_service):
        """Test service initializes with all models."""
        assert len(deepfake_service.deepfake_models) == 5
        assert 'deeper_forensics' in deepfake_service.deepfake_models
        assert 'face_forensics_pp' in deepfake_service.deepfake_models
        assert 'celeb_df' in deepfake_service.deepfake_models
        assert 'dfdc' in deepfake_service.deepfake_models
        assert 'face_swapper' in deepfake_service.deepfake_models

    @pytest.mark.asyncio
    async def test_detect_deepfake_returns_valid_structure(self, deepfake_service):
        """Test detect_deepfake returns correct structure."""
        result = await deepfake_service.detect_deepfake('test_image.jpg')

        assert 'deepfake_detected' in result
        assert 'deepfake_score' in result
        assert 'model_scores' in result
        assert 'fraud_indicators' in result
        assert 'authenticity_score' in result

    @pytest.mark.asyncio
    async def test_detect_deepfake_authenticity_calculation(self, deepfake_service):
        """Test authenticity score is inverse of deepfake score."""
        result = await deepfake_service.detect_deepfake('test_image.jpg')

        deepfake_score = result['deepfake_score']
        authenticity_score = result['authenticity_score']

        assert authenticity_score == pytest.approx(1.0 - deepfake_score, abs=0.01)

    @pytest.mark.asyncio
    async def test_detect_deepfake_no_deepfake_detected(self, deepfake_service):
        """Test no deepfake detected for normal images (mock)."""
        result = await deepfake_service.detect_deepfake('test_image.jpg')

        assert result['deepfake_detected'] is False
        assert result['deepfake_score'] < deepfake_service.deepfake_threshold

    @pytest.mark.asyncio
    async def test_detect_deepfake_model_scores(self, deepfake_service):
        """Test individual model scores are returned."""
        result = await deepfake_service.detect_deepfake('test_image.jpg')

        assert isinstance(result['model_scores'], dict)
        assert len(result['model_scores']) > 0

    def test_set_executor_pool(self, deepfake_service):
        """Test setting executor pool."""
        from concurrent.futures import ThreadPoolExecutor

        pool = ThreadPoolExecutor(max_workers=2)
        deepfake_service.set_executor_pool(pool)

        assert deepfake_service.executor_pool == pool
        pool.shutdown()


class TestDeepfakeModels:
    """Test suite for individual deepfake detection models."""

    def test_deeper_forensics_model(self):
        """Test DeeperForensics model."""
        model = DeeperForensicsModel()
        result = model.detect_deepfake('test_image.jpg')

        assert isinstance(result, dict)
        assert 'deepfake_detected' in result
        assert 'deepfake_score' in result

    def test_face_forensics_plus_plus_model(self):
        """Test FaceForensics++ model."""
        model = FaceForensicsPlusPlusModel()
        result = model.detect_deepfake('test_image.jpg')

        assert isinstance(result, dict)
        assert 'deepfake_detected' in result

    def test_celeb_df_model(self):
        """Test Celeb-DF model."""
        model = CelebDFModel()
        result = model.detect_deepfake('test_image.jpg')

        assert isinstance(result, dict)
        assert 'deepfake_detected' in result

    def test_dfdc_model(self):
        """Test DFDC model."""
        model = DFDCModel()
        result = model.detect_deepfake('test_image.jpg')

        assert isinstance(result, dict)
        assert 'deepfake_detected' in result

    def test_face_swapper_detection_model(self):
        """Test FaceSwapper detection model."""
        model = FaceSwapperDetectionModel()
        result = model.detect_deepfake('test_image.jpg')

        assert isinstance(result, dict)
        assert 'deepfake_detected' in result
