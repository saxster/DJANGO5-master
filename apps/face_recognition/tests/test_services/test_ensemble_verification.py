"""
Tests for Ensemble Verification Service.

Tests ensemble face verification using multiple models and
cosine similarity calculations.
"""

import pytest
import numpy as np
from apps.face_recognition.services.ensemble_verification import (
    EnsembleVerificationService,
    MockFaceNetModel,
    MockArcFaceModel,
    MockInsightFaceModel
)


@pytest.fixture
def ensemble_service():
    """Create ensemble verification service instance."""
    return EnsembleVerificationService()


class TestEnsembleVerificationService:
    """Test suite for EnsembleVerificationService."""

    def test_service_initialization(self, ensemble_service):
        """Test service initializes with all models."""
        assert len(ensemble_service.models) == 3
        assert 'FaceNet512' in ensemble_service.models
        assert 'ArcFace' in ensemble_service.models
        assert 'InsightFace' in ensemble_service.models

    def test_calculate_cosine_similarity_identical_vectors(self, ensemble_service):
        """Test cosine similarity for identical vectors."""
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([1, 0, 0])

        similarity = ensemble_service.calculate_cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0, abs=0.01)

    def test_calculate_cosine_similarity_orthogonal_vectors(self, ensemble_service):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([0, 1, 0])

        similarity = ensemble_service.calculate_cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.5, abs=0.01)  # Normalized to 0-1

    def test_calculate_cosine_similarity_opposite_vectors(self, ensemble_service):
        """Test cosine similarity for opposite vectors."""
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([-1, 0, 0])

        similarity = ensemble_service.calculate_cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0, abs=0.01)  # Normalized to 0-1

    def test_calculate_cosine_similarity_none_vector(self, ensemble_service):
        """Test cosine similarity handles None vectors."""
        vec1 = np.array([1, 0, 0])
        vec2 = None

        similarity = ensemble_service.calculate_cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_calculate_cosine_similarity_mismatched_shapes(self, ensemble_service):
        """Test cosine similarity handles mismatched vector shapes."""
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([1, 0])

        similarity = ensemble_service.calculate_cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_calculate_cosine_similarity_zero_vectors(self, ensemble_service):
        """Test cosine similarity handles zero vectors."""
        vec1 = np.array([0, 0, 0])
        vec2 = np.array([1, 0, 0])

        similarity = ensemble_service.calculate_cosine_similarity(vec1, vec2)
        assert similarity == 0.0


class TestMockFaceRecognitionModels:
    """Test suite for mock face recognition models."""

    def test_mock_facenet_model(self):
        """Test MockFaceNetModel extracts features."""
        model = MockFaceNetModel()
        features = model.extract_features('test_image.jpg')

        assert features is not None
        assert len(features) == 512
        assert np.linalg.norm(features) == pytest.approx(1.0, abs=0.01)

    def test_mock_arcface_model(self):
        """Test MockArcFaceModel extracts features."""
        model = MockArcFaceModel()
        features = model.extract_features('test_image.jpg')

        assert features is not None
        assert len(features) == 512
        assert np.linalg.norm(features) == pytest.approx(1.0, abs=0.01)

    def test_mock_insightface_model(self):
        """Test MockInsightFaceModel extracts features."""
        model = MockInsightFaceModel()
        features = model.extract_features('test_image.jpg')

        assert features is not None
        assert len(features) == 512
        assert np.linalg.norm(features) == pytest.approx(1.0, abs=0.01)

    def test_mock_models_deterministic(self):
        """Test mock models produce deterministic results for same image."""
        model = MockFaceNetModel()

        features1 = model.extract_features('test_image.jpg')
        features2 = model.extract_features('test_image.jpg')

        # Same image should produce same features
        np.testing.assert_array_almost_equal(features1, features2)

    def test_mock_models_different_for_different_images(self):
        """Test mock models produce different results for different images."""
        model = MockFaceNetModel()

        features1 = model.extract_features('test_image1.jpg')
        features2 = model.extract_features('test_image2.jpg')

        # Different images should produce different features
        similarity = np.dot(features1, features2)
        assert similarity < 1.0  # Not identical
