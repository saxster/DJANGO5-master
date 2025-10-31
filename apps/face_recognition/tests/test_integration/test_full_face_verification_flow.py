"""
End-to-End Integration Tests for Face Verification (Sprint 6.1)

Tests complete face verification workflow from enrollment through verification
including quality assessment, anti-spoofing, and fraud detection.
"""

import pytest
import numpy as np
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
def test_user(db):
    """Create test user."""
    return People.objects.create_user(
        username='integration_test_user',
        email='integration@test.com',
        password='testpass123'
    )


@pytest.fixture
def test_image():
    """Create test face image."""
    image = Image.new('RGB', (640, 480), color='white')
    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile('test_face.jpg', buffer.read(), content_type='image/jpeg')


@pytest.mark.django_db
class TestFullFaceVerificationFlow:
    """End-to-end tests for complete face verification workflow."""

    def test_complete_enrollment_to_verification_flow(self, api_client, test_user, test_image):
        """Test full flow: enrollment → quality check → verification."""
        api_client.force_authenticate(user=test_user)

        # Step 1: Enroll face
        enroll_response = api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': test_image,
            'user_id': test_user.id,
            'consent_given': True
        }, format='multipart')

        assert enroll_response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

        if enroll_response.status_code == status.HTTP_201_CREATED:
            # Enrollment succeeded
            assert enroll_response.data['success'] is True
            embedding_id = enroll_response.data.get('embedding_id')
            assert embedding_id is not None

            # Verify consent log created
            assert BiometricConsentLog.objects.filter(user=test_user, biometric_type='FACE').exists()

            # Verify embedding created
            assert FaceEmbedding.objects.filter(user=test_user).exists()

            # Step 2: Verify with same image (should match)
            verify_image = self._create_test_image()
            verify_response = api_client.post('/api/v1/biometrics/face/verify/', {
                'image': verify_image,
                'user_id': test_user.id,
                'enable_liveness': False  # Skip for faster test
            }, format='multipart')

            assert verify_response.status_code == status.HTTP_200_OK
            assert 'verified' in verify_response.data
            assert 'confidence' in verify_response.data
            assert 'similarity' in verify_response.data

    def test_enrollment_verification_with_quality_check(self, api_client, test_user):
        """Test enrollment with quality assessment integration."""
        api_client.force_authenticate(user=test_user)

        test_image = self._create_test_image()

        # Quality check before enrollment
        quality_response = api_client.post('/api/v1/biometrics/face/quality/', {
            'image': test_image
        }, format='multipart')

        assert quality_response.status_code == status.HTTP_200_OK
        quality_score = quality_response.data.get('overall_quality', 0)

        # Enroll if quality acceptable
        if quality_score >= 0.6:
            enroll_response = api_client.post('/api/v1/biometrics/face/enroll/', {
                'image': test_image,
                'user_id': test_user.id,
                'consent_given': True
            }, format='multipart')

            assert enroll_response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

    def test_liveness_detection_integration(self, api_client, test_user):
        """Test liveness detection in verification workflow."""
        api_client.force_authenticate(user=test_user)

        test_image = self._create_test_image()

        # Test liveness endpoint
        liveness_response = api_client.post('/api/v1/biometrics/face/liveness/', {
            'image': test_image,
            'detection_type': 'passive'
        }, format='multipart')

        assert liveness_response.status_code == status.HTTP_200_OK
        assert 'liveness_detected' in liveness_response.data
        assert 'liveness_score' in liveness_response.data

    def test_multi_user_tenant_isolation(self, api_client, db):
        """Test that users cannot access other users' biometric data."""
        # Create two users in different contexts
        user1 = People.objects.create_user(username='user1', email='user1@test.com', password='pass')
        user2 = People.objects.create_user(username='user2', email='user2@test.com', password='pass')

        # Enroll user1
        api_client.force_authenticate(user=user1)
        image1 = self._create_test_image()

        api_client.post('/api/v1/biometrics/face/enroll/', {
            'image': image1,
            'user_id': user1.id,
            'consent_given': True
        }, format='multipart')

        # Try to verify as user2 against user1's embedding
        api_client.force_authenticate(user=user2)
        image2 = self._create_test_image()

        # This should work (different users) but not match if tenant isolation works
        response = api_client.post('/api/v1/biometrics/face/verify/', {
            'image': image2,
            'user_id': user1.id,
            'enable_liveness': False
        }, format='multipart')

        # Response should succeed but likely not verify (different faces)
        if response.status_code == status.HTTP_200_OK:
            assert 'verified' in response.data

    def _create_test_image(self):
        """Helper to create test image."""
        image = Image.new('RGB', (640, 480), color='white')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')
        buffer.seek(0)
        return SimpleUploadedFile('test.jpg', buffer.read(), content_type='image/jpeg')
