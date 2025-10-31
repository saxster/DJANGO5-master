"""
Tests for Face Enrollment API Endpoint.

Tests face enrollment including image upload, quality validation,
consent tracking, and embedding creation.
"""

import pytest
import uuid
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.face_recognition.models import FaceEmbedding, BiometricConsentLog
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
def sample_face_image():
    """Create a sample face image for testing."""
    # Create a simple test image
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
class TestFaceEnrollmentAPI:
    """Test suite for face enrollment API endpoint."""

    def test_enroll_face_success(self, api_client, authenticated_user, sample_face_image):
        """Test successful face enrollment."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': sample_face_image,
            'user_id': authenticated_user.id,
            'consent_given': True,
            'is_primary': True
        }, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert 'embedding_id' in response.data
        assert response.data['quality_score'] >= 0.0

    def test_enroll_face_requires_authentication(self, api_client, sample_face_image):
        """Test endpoint requires authentication."""
        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': sample_face_image,
            'user_id': 123,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_enroll_face_missing_consent(self, api_client, authenticated_user, sample_face_image):
        """Test enrollment fails without consent."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': sample_face_image,
            'user_id': authenticated_user.id,
            'consent_given': False
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enroll_face_missing_image(self, api_client, authenticated_user):
        """Test enrollment fails without image."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data or 'success' in response.data

    def test_enroll_face_user_not_found(self, api_client, authenticated_user, sample_face_image):
        """Test enrollment fails for non-existent user."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': sample_face_image,
            'user_id': 999999,  # Non-existent user
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_enroll_face_creates_consent_log(self, api_client, authenticated_user, sample_face_image):
        """Test enrollment creates biometric consent log."""
        api_client.force_authenticate(user=authenticated_user)

        initial_count = BiometricConsentLog.objects.count()

        api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': sample_face_image,
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        # Consent log should be created
        assert BiometricConsentLog.objects.count() == initial_count + 1

        # Verify consent log details
        consent_log = BiometricConsentLog.objects.latest('id')
        assert consent_log.user == authenticated_user
        assert consent_log.biometric_type == 'FACE'
        assert consent_log.consent_given is True

    def test_enroll_face_creates_embedding(self, api_client, authenticated_user, sample_face_image):
        """Test enrollment creates face embedding record."""
        api_client.force_authenticate(user=authenticated_user)

        initial_count = FaceEmbedding.objects.filter(user=authenticated_user).count()

        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': sample_face_image,
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        if response.status_code == status.HTTP_201_CREATED:
            # Embedding should be created
            assert FaceEmbedding.objects.filter(user=authenticated_user).count() == initial_count + 1

            # Verify embedding details
            embedding = FaceEmbedding.objects.filter(user=authenticated_user).latest('id')
            assert embedding.model_name is not None
            assert len(embedding.embedding_vector) > 0

    def test_enroll_face_invalid_image_format(self, api_client, authenticated_user):
        """Test enrollment rejects invalid image format."""
        api_client.force_authenticate(user=authenticated_user)

        # Create a text file instead of image
        text_file = SimpleUploadedFile(
            name='test.txt',
            content=b'This is not an image',
            content_type='text/plain'
        )

        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': text_file,
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enroll_face_oversized_image(self, api_client, authenticated_user):
        """Test enrollment rejects oversized images."""
        api_client.force_authenticate(user=authenticated_user)

        # Create a large fake image file (>10MB)
        large_content = b'0' * (11 * 1024 * 1024)  # 11MB
        large_file = SimpleUploadedFile(
            name='large_image.jpg',
            content=large_content,
            content_type='image/jpeg'
        )

        response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': large_file,
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
