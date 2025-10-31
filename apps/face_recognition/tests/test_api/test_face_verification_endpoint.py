"""
Tests for Face Verification API Endpoint.

Tests face verification including similarity matching, liveness detection,
fraud risk assessment, and decision making.
"""

import pytest
import numpy as np
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.face_recognition.models import FaceEmbedding
from apps.peoples.models import People


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def authenticated_user(db):
    """Create authenticated user."""
    return People.objects.create_user(
        username='test_user',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def enrolled_face(db, authenticated_user):
    """Create enrolled face embedding."""
    # Generate mock embedding
    embedding = np.random.normal(0, 1, 512)
    embedding = embedding / np.linalg.norm(embedding)

    return FaceEmbedding.objects.create(
        user=authenticated_user,
        embedding_vector=embedding.tolist(),
        model_name='FaceNet512',
        quality_score=0.85,
        confidence_score=0.90,
        is_primary=True,
        is_active=True
    )


@pytest.fixture
def sample_face_image():
    """Create a sample face image for testing."""
    image = Image.new('RGB', (640, 480), color='white')
    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    buffer.seek(0)

    return SimpleUploadedFile(
        name='test_face.jpg',
        content=buffer.read(),
        content_type='image/jpeg'
    )


@pytest.mark.django_db
class TestFaceVerificationAPI:
    """Test suite for face verification API endpoint."""

    def test_verify_face_requires_authentication(self, api_client, sample_face_image):
        """Test endpoint requires authentication."""
        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': sample_face_image,
            'user_id': 123
        }, format='multipart')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_face_missing_image(self, api_client, authenticated_user, enrolled_face):
        """Test verification fails without image."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'user_id': authenticated_user.id
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_face_missing_user_and_embedding_id(self, api_client, authenticated_user, sample_face_image):
        """Test verification requires either user_id or embedding_id."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': sample_face_image
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_face_user_not_found(self, api_client, authenticated_user, sample_face_image):
        """Test verification fails for non-existent user."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': sample_face_image,
            'user_id': 999999  # Non-existent user
        }, format='multipart')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_verify_face_no_enrollment_found(self, api_client, authenticated_user, sample_face_image):
        """Test verification fails when user has no enrollments."""
        # Create a different user with no enrollments
        other_user = People.objects.create_user(
            username='other_user',
            email='other@example.com',
            password='testpass123'
        )

        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': sample_face_image,
            'user_id': other_user.id
        }, format='multipart')

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'No enrolled face found' in response.data.get('message', '')

    def test_verify_face_returns_verification_result(self, api_client, authenticated_user, enrolled_face, sample_face_image):
        """Test verification returns complete result structure."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': sample_face_image,
            'user_id': authenticated_user.id,
            'enable_liveness': False  # Disable for faster test
        }, format='multipart')

        assert response.status_code == status.HTTP_200_OK
        assert 'verified' in response.data
        assert 'confidence' in response.data
        assert 'similarity' in response.data
        assert 'threshold_met' in response.data
        assert 'fraud_risk_score' in response.data

    def test_verify_face_by_embedding_id(self, api_client, authenticated_user, enrolled_face, sample_face_image):
        """Test verification using specific embedding ID."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': sample_face_image,
            'embedding_id': str(enrolled_face.id),
            'enable_liveness': False
        }, format='multipart')

        assert response.status_code == status.HTTP_200_OK
        assert 'verified' in response.data

    def test_verify_face_invalid_embedding_id(self, api_client, authenticated_user, sample_face_image):
        """Test verification fails with invalid embedding ID."""
        api_client.force_authenticate(user=authenticated_user)

        fake_uuid = str(uuid.uuid4())
        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': sample_face_image,
            'embedding_id': fake_uuid
        }, format='multipart')

        assert response.status_code == status.HTTP_404_NOT_FOUND
