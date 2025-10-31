"""
Pytest configuration and shared fixtures for face_recognition tests.

Provides reusable fixtures for testing biometric authentication features.
"""

import pytest
import numpy as np
from django.contrib.auth import get_user_model
from apps.face_recognition.models import FaceEmbedding, FaceRecognitionConfig

People = get_user_model()


@pytest.fixture
def sample_user(db):
    """Create a sample user for testing."""
    return People.objects.create_user(
        username='test_user',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def sample_face_embedding(db, sample_user):
    """Create a sample face embedding for testing."""
    # Generate a mock embedding vector
    embedding_vector = np.random.normal(0, 1, 512)
    embedding_vector = embedding_vector / np.linalg.norm(embedding_vector)

    return FaceEmbedding.objects.create(
        user=sample_user,
        embedding_vector=embedding_vector.tolist(),
        model_name='FaceNet512',
        quality_score=0.85,
        confidence_score=0.90,
        is_primary=True
    )


@pytest.fixture
def face_recognition_config(db):
    """Create a face recognition configuration for testing."""
    return FaceRecognitionConfig.objects.create(
        similarity_threshold=0.7,
        confidence_threshold=0.75,
        quality_threshold=0.6,
        liveness_threshold=0.5,
        deepfake_threshold=0.7,
        depth_threshold=0.6,
        micro_expression_analysis=False,
        heart_rate_detection=False,
        challenge_response_enabled=False,
        is_active=True
    )


@pytest.fixture
def sample_image_path():
    """Provide a sample image path for testing."""
    return 'apps/face_recognition/tests/fixtures/sample_faces/test_face.jpg'


@pytest.fixture
def sample_embeddings_list():
    """Generate a list of sample embeddings for testing."""
    embeddings = []
    for i in range(3):
        embedding = np.random.normal(0, 1, 512)
        embedding = embedding / np.linalg.norm(embedding)
        embeddings.append(embedding)
    return embeddings


@pytest.fixture
def mock_verification_result():
    """Provide a mock verification result for testing."""
    return {
        'verified': True,
        'confidence': 0.85,
        'similarity': 0.90,
        'threshold_met': True,
        'confidence_met': True,
        'quality_metrics': {
            'overall_quality': 0.75,
            'sharpness_score': 0.80,
            'brightness_score': 0.70,
            'contrast_score': 0.75
        },
        'anti_spoofing_result': {
            'spoof_detected': False,
            'spoof_score': 0.1,
            'liveness_score': 0.9
        },
        'fraud_indicators': [],
        'fraud_risk_score': 0.15
    }


@pytest.fixture
def mock_modality_results():
    """Provide mock modality results for multi-modal fusion testing."""
    return {
        'face_recognition': {
            'verified': True,
            'confidence': 0.88
        },
        'voice_recognition': {
            'verified': True,
            'confidence': 0.82
        },
        'behavioral_biometrics': {
            'verified': False,
            'confidence': 0.55
        }
    }


@pytest.fixture
def mock_security_analysis():
    """Provide mock security analysis for testing."""
    return {
        'deepfake_detected': False,
        '3d_liveness_detected': True,
        'advanced_liveness_score': 0.85
    }


@pytest.fixture
def mock_quality_metrics():
    """Provide mock quality metrics for testing."""
    return {
        'overall_quality': 0.80,
        'sharpness': 0.85,
        'brightness': 0.75,
        'contrast': 0.80
    }
