"""
Tests for Voice Enrollment API Endpoint.

Tests voice enrollment including audio upload, quality validation,
consent tracking, and voiceprint creation.
"""

import pytest
import numpy as np
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.voice_recognition.models import VoiceEmbedding, BiometricConsentLog
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
def sample_audio_file():
    """Create a sample audio file for testing."""
    # Create a simple test WAV file (mock)
    audio_content = b'RIFF' + b'\x00' * 100  # Minimal WAV header
    return SimpleUploadedFile(
        name='test_voice.wav',
        content=audio_content,
        content_type='audio/wav'
    )


@pytest.mark.django_db
class TestVoiceEnrollmentAPI:
    """Test suite for voice enrollment API endpoint."""

    def test_enroll_voice_requires_authentication(self, api_client, sample_audio_file):
        """Test endpoint requires authentication."""
        response = api_client.post('/api/v1/biometrics/voice/enroll/', {
            'audio': sample_audio_file,
            'user_id': 123,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_enroll_voice_missing_consent(self, api_client, authenticated_user, sample_audio_file):
        """Test enrollment fails without consent."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/voice/enroll/', {
            'audio': sample_audio_file,
            'user_id': authenticated_user.id,
            'consent_given': False
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enroll_voice_missing_audio(self, api_client, authenticated_user):
        """Test enrollment fails without audio."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/voice/enroll/', {
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enroll_voice_user_not_found(self, api_client, authenticated_user, sample_audio_file):
        """Test enrollment fails for non-existent user."""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post('/api/v1/biometrics/voice/enroll/', {
            'audio': sample_audio_file,
            'user_id': 999999,  # Non-existent user
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_enroll_voice_creates_consent_log(self, api_client, authenticated_user, sample_audio_file):
        """Test enrollment creates biometric consent log."""
        api_client.force_authenticate(user=authenticated_user)

        initial_count = BiometricConsentLog.objects.count()

        api_client.post('/api/v1/biometrics/voice/enroll/', {
            'audio': sample_audio_file,
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        # Consent log should always be created
        assert BiometricConsentLog.objects.count() == initial_count + 1

    def test_enroll_voice_invalid_audio_format(self, api_client, authenticated_user):
        """Test enrollment rejects invalid audio format."""
        api_client.force_authenticate(user=authenticated_user)

        # Create a text file instead of audio
        text_file = SimpleUploadedFile(
            name='test.txt',
            content=b'This is not audio',
            content_type='text/plain'
        )

        response = api_client.post('/api/v1/biometrics/voice/enroll/', {
            'audio': text_file,
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enroll_voice_oversized_audio(self, api_client, authenticated_user):
        """Test enrollment rejects oversized audio files."""
        api_client.force_authenticate(user=authenticated_user)

        # Create a large fake audio file (>50MB)
        large_content = b'0' * (51 * 1024 * 1024)  # 51MB
        large_file = SimpleUploadedFile(
            name='large_audio.wav',
            content=large_content,
            content_type='audio/wav'
        )

        response = api_client.post('/api/v1/biometrics/voice/enroll/', {
            'audio': large_file,
            'user_id': authenticated_user.id,
            'consent_given': True
        }, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
