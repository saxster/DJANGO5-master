"""
Authentication REST API Tests

Tests for login, logout, and token refresh endpoints.

Compliance with .claude/rules.md:
- Tests cover success and failure paths
- Specific exception handling
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.peoples.models import People
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
class TestLoginView:
    """Test cases for LoginView endpoint."""

    def setup_method(self):
        """Set up test client and test user."""
        self.client = APIClient()
        self.login_url = reverse('api_v1:auth:login')

        # Create test user
        self.test_user = People.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            is_active=True
        )

    def test_login_success(self):
        """Test successful login with valid credentials."""
        response = self.client.post(self.login_url, {
            'username': 'testuser@example.com',
            'password': 'TestPassword123!'
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert 'user' in response.data
        assert response.data['user']['username'] == 'testuser@example.com'

    def test_login_with_device_id(self):
        """Test login with device ID tracking."""
        response = self.client.post(self.login_url, {
            'username': 'testuser@example.com',
            'password': 'TestPassword123!',
            'device_id': 'device-uuid-123'
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = self.client.post(self.login_url, {
            'username': 'testuser@example.com',
            'password': 'WrongPassword'
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
        assert response.data['error']['code'] == 'INVALID_CREDENTIALS'

    def test_login_missing_username(self):
        """Test login with missing username."""
        response = self.client.post(self.login_url, {
            'password': 'TestPassword123!'
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert response.data['error']['code'] == 'MISSING_CREDENTIALS'

    def test_login_missing_password(self):
        """Test login with missing password."""
        response = self.client.post(self.login_url, {
            'username': 'testuser@example.com'
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    def test_login_inactive_user(self):
        """Test login with inactive account."""
        self.test_user.is_active = False
        self.test_user.save()

        response = self.client.post(self.login_url, {
            'username': 'testuser@example.com',
            'password': 'TestPassword123!'
        })

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'error' in response.data
        assert response.data['error']['code'] == 'ACCOUNT_DISABLED'


@pytest.mark.django_db
class TestLogoutView:
    """Test cases for LogoutView endpoint."""

    def setup_method(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.logout_url = reverse('api_v1:auth:logout')

        # Create and authenticate test user
        self.test_user = People.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='TestPassword123!',
            is_active=True
        )

        # Generate tokens
        self.refresh = RefreshToken.for_user(self.test_user)
        self.access_token = str(self.refresh.access_token)
        self.refresh_token = str(self.refresh)

    def test_logout_success(self):
        """Test successful logout with valid tokens."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.logout_url, {
            'refresh': self.refresh_token
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert response.data['message'] == 'Logout successful'

    def test_logout_missing_token(self):
        """Test logout without refresh token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.logout_url, {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert response.data['error']['code'] == 'MISSING_TOKEN'

    def test_logout_unauthenticated(self):
        """Test logout without authentication."""
        response = self.client.post(self.logout_url, {
            'refresh': self.refresh_token
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_invalid_token(self):
        """Test logout with invalid refresh token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        response = self.client.post(self.logout_url, {
            'refresh': 'invalid-token-string'
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data


@pytest.mark.django_db
class TestRefreshTokenView:
    """Test cases for RefreshTokenView endpoint."""

    def setup_method(self):
        """Set up test client and tokens."""
        self.client = APIClient()
        self.refresh_url = reverse('api_v1:auth:refresh')

        # Create test user
        self.test_user = People.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='TestPassword123!',
            is_active=True
        )

        # Generate tokens
        self.refresh = RefreshToken.for_user(self.test_user)
        self.refresh_token = str(self.refresh)

    def test_refresh_success(self):
        """Test successful token refresh."""
        response = self.client.post(self.refresh_url, {
            'refresh': self.refresh_token
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_refresh_missing_token(self):
        """Test refresh without token."""
        response = self.client.post(self.refresh_url, {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert response.data['error']['code'] == 'MISSING_TOKEN'

    def test_refresh_invalid_token(self):
        """Test refresh with invalid token."""
        response = self.client.post(self.refresh_url, {
            'refresh': 'invalid-token-string'
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
        assert response.data['error']['code'] == 'INVALID_TOKEN'


__all__ = [
    'TestLoginView',
    'TestLogoutView',
    'TestRefreshTokenView',
]
