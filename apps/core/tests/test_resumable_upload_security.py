"""
Resumable Upload Security Tests

Tests for resumable upload endpoints with CSRF protection.

Tests implemented security fixes from November 5, 2025 code review:
- CSRF protection on upload initialization
- CSRF protection on chunk upload
- CSRF protection on upload completion
- CSRF protection on upload cancellation

Compliance:
- Rule #2: CSRF protection on all mutations
"""

import pytest
import base64
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.core.models.upload_session import UploadSession

People = get_user_model()


@pytest.mark.django_db
class TestResumableUploadCSRFProtection(TestCase):
    """Test CSRF protection on resumable upload endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.client = Client(enforce_csrf_checks=True)
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(loginid='testuser', password='testpass123')

    def test_init_upload_requires_csrf_token(self):
        """Test that upload initialization requires CSRF token."""
        # Attempt POST without CSRF token
        response = self.client.post(
            '/api/v1/upload/init',
            data=json.dumps({
                'filename': 'test.pdf',
                'total_size': 1024000,
                'mime_type': 'application/pdf',
                'file_hash': 'abc123def456'
            }),
            content_type='application/json'
        )
        
        # Should fail with 403 Forbidden
        assert response.status_code == 403
        
        # Verify no upload session was created
        assert UploadSession.objects.count() == 0

    def test_init_upload_succeeds_with_csrf_token(self):
        """Test that upload initialization works with valid CSRF token."""
        # Get CSRF token
        response = self.client.get('/api/v1/upload/init')
        csrf_token = response.cookies.get('csrftoken')
        
        # POST with CSRF token
        response = self.client.post(
            '/api/v1/upload/init',
            data=json.dumps({
                'filename': 'test.pdf',
                'total_size': 1024000,
                'mime_type': 'application/pdf',
                'file_hash': 'abc123def456'
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token.value if csrf_token else None
        )
        
        # Should succeed (201 Created)
        assert response.status_code == 201
        
        # Verify upload session was created
        assert UploadSession.objects.count() == 1

    def test_upload_chunk_requires_csrf_token(self):
        """Test that chunk upload requires CSRF token."""
        # Create upload session
        upload_session = UploadSession.objects.create(
            user=self.user,
            upload_id='test-upload-123',
            filename='test.pdf',
            total_size=1024000,
            mime_type='application/pdf',
            status='active'
        )
        
        # Attempt POST without CSRF token
        chunk_data = b'test chunk data'
        response = self.client.post(
            '/api/v1/upload/chunk',
            data=json.dumps({
                'upload_id': 'test-upload-123',
                'chunk_index': 0,
                'chunk_data': base64.b64encode(chunk_data).decode('utf-8'),
                'checksum': 'abc123'
            }),
            content_type='application/json'
        )
        
        # Should fail with 403 Forbidden
        assert response.status_code == 403

    def test_complete_upload_requires_csrf_token(self):
        """Test that upload completion requires CSRF token."""
        # Create upload session
        upload_session = UploadSession.objects.create(
            user=self.user,
            upload_id='test-upload-456',
            filename='test.pdf',
            total_size=1024000,
            mime_type='application/pdf',
            status='active'
        )
        
        # Attempt POST without CSRF token
        response = self.client.post(
            '/api/v1/upload/complete',
            data=json.dumps({
                'upload_id': 'test-upload-456'
            }),
            content_type='application/json'
        )
        
        # Should fail with 403 Forbidden
        assert response.status_code == 403

    def test_cancel_upload_requires_csrf_token(self):
        """Test that upload cancellation requires CSRF token."""
        # Create upload session
        upload_session = UploadSession.objects.create(
            user=self.user,
            upload_id='test-upload-789',
            filename='test.pdf',
            total_size=1024000,
            mime_type='application/pdf',
            status='active'
        )
        
        # Attempt POST without CSRF token
        response = self.client.post(
            '/api/v1/upload/cancel',
            data=json.dumps({
                'upload_id': 'test-upload-789'
            }),
            content_type='application/json'
        )
        
        # Should fail with 403 Forbidden
        assert response.status_code == 403
        
        # Verify upload session still active
        upload_session.refresh_from_db()
        assert upload_session.status == 'active'


@pytest.mark.django_db
class TestResumableUploadAuthentication(TestCase):
    """Test authentication requirements on upload endpoints."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_init_upload_requires_authentication(self):
        """Test that upload initialization requires authentication."""
        response = self.client.post(
            '/api/v1/upload/init',
            data=json.dumps({
                'filename': 'test.pdf',
                'total_size': 1024000,
                'mime_type': 'application/pdf',
                'file_hash': 'abc123'
            }),
            content_type='application/json'
        )
        
        # Should redirect to login or return 401/403
        assert response.status_code in [302, 401, 403]

    def test_upload_chunk_requires_authentication(self):
        """Test that chunk upload requires authentication."""
        response = self.client.post(
            '/api/v1/upload/chunk',
            data=json.dumps({
                'upload_id': 'test-123',
                'chunk_index': 0,
                'chunk_data': 'data',
                'checksum': 'abc'
            }),
            content_type='application/json'
        )
        
        # Should redirect to login or return 401/403
        assert response.status_code in [302, 401, 403]


__all__ = [
    'TestResumableUploadCSRFProtection',
    'TestResumableUploadAuthentication',
]
