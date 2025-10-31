"""
Tests for Image Quality Assessment Service.

Tests image quality assessment including sharpness, brightness, contrast,
face detection, and quality recommendations.
"""

import pytest
import numpy as np
from apps.face_recognition.services.quality_assessment import ImageQualityAssessmentService


@pytest.fixture
def quality_service():
    """Create quality assessment service instance."""
    return ImageQualityAssessmentService()


@pytest.mark.django_db
class TestImageQualityAssessmentService:
    """Test suite for ImageQualityAssessmentService."""

    def test_service_initialization(self, quality_service):
        """Test service initializes with correct thresholds."""
        assert quality_service.sharpness_threshold == 0.5
        assert quality_service.brightness_threshold == 0.5
        assert quality_service.contrast_threshold == 0.4
        assert quality_service.face_size_threshold == 0.7

    def test_calculate_image_hash(self, quality_service, sample_image_path):
        """Test image hash calculation."""
        hash_value = quality_service.calculate_image_hash(sample_image_path)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 16

    def test_calculate_image_hash_nonexistent_file(self, quality_service):
        """Test hash calculation for nonexistent file."""
        hash_value = quality_service.calculate_image_hash('/nonexistent/file.jpg')
        assert isinstance(hash_value, str)
        assert len(hash_value) == 16

    def test_calculate_roi_sharpness(self, quality_service):
        """Test ROI sharpness calculation."""
        # Create a simple test image (sharp)
        sharp_roi = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        sharpness = quality_service.calculate_roi_sharpness(sharp_roi)
        assert 0.0 <= sharpness <= 1.0

    def test_calculate_roi_brightness(self, quality_service):
        """Test ROI brightness calculation."""
        # Create medium gray ROI (optimal brightness)
        gray_roi = np.full((100, 100), 127, dtype=np.uint8)
        brightness = quality_service.calculate_roi_brightness(gray_roi)
        assert brightness > 0.8  # Should be high for optimal gray

    def test_calculate_roi_contrast(self, quality_service):
        """Test ROI contrast calculation."""
        # High contrast ROI
        high_contrast_roi = np.array([[0, 255] * 50] * 100, dtype=np.uint8)
        contrast = quality_service.calculate_roi_contrast(high_contrast_roi)
        assert contrast > 0.5

    def test_calculate_face_size_score_optimal(self, quality_service):
        """Test face size score calculation for optimal size."""
        # Face is 25% of image (optimal range 10-40%)
        score = quality_service.calculate_face_size_score(100, 100, 200, 200)
        assert score == 1.0

    def test_calculate_face_size_score_too_small(self, quality_service):
        """Test face size score for too small face."""
        # Face is 5% of image (below 10% threshold)
        score = quality_service.calculate_face_size_score(50, 50, 500, 500)
        assert 0.0 < score < 1.0

    def test_generate_improvement_suggestions_no_face(self, quality_service):
        """Test suggestions generation when no face detected."""
        suggestions = quality_service.generate_improvement_suggestions(['NO_FACE_DETECTED'])
        assert len(suggestions) > 0
        assert any('face is clearly visible' in s for s in suggestions)

    def test_generate_improvement_suggestions_low_sharpness(self, quality_service):
        """Test suggestions for low sharpness."""
        suggestions = quality_service.generate_improvement_suggestions(['LOW_SHARPNESS'])
        assert len(suggestions) > 0
        assert any('camera shake' in s or 'focus' in s for s in suggestions)

    def test_generate_improvement_suggestions_poor_lighting(self, quality_service):
        """Test suggestions for poor lighting."""
        suggestions = quality_service.generate_improvement_suggestions(['POOR_LIGHTING'])
        assert len(suggestions) > 0
        assert any('lighting' in s.lower() for s in suggestions)

    def test_generate_improvement_suggestions_multiple_issues(self, quality_service):
        """Test suggestions for multiple quality issues."""
        issues = ['LOW_SHARPNESS', 'POOR_LIGHTING', 'SMALL_FACE_SIZE']
        suggestions = quality_service.generate_improvement_suggestions(issues)
        assert len(suggestions) == 3

    def test_estimate_face_pose_quality_returns_valid_score(self, quality_service):
        """Test face pose quality estimation returns valid score."""
        # Create a simple face-like image
        face_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        pose_score = quality_service.estimate_face_pose_quality(face_image)
        assert 0.0 <= pose_score <= 1.0

    def test_check_eye_visibility_returns_valid_score(self, quality_service):
        """Test eye visibility check returns valid score."""
        # Create a simple face-like image
        face_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        face_roi = (10, 10, 80, 80)
        eye_score = quality_service.check_eye_visibility(face_image, face_roi)
        assert 0.0 <= eye_score <= 1.0
