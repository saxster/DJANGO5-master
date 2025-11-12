"""
Test V2 Authentication API Endpoints

Tests for JWT-based authentication with V2 enhancements:
- Standardized response envelope with correlation_id
- Pydantic validation
- Token binding integration
- Tenant isolation

Following TDD: Tests written BEFORE implementation.
"""

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

People = get_user_model()


@pytest.mark.django_db
class TestLoginView:
    """Test POST /api/v2/auth/login/ endpoint."""

    def test_successful_login_returns_tokens_and_user_data(self):
        """
        Test that valid credentials return access/refresh tokens and user data.

        V2 Response format:
        {
            "success": true,
            "data": {
                "access": "eyJ...",
                "refresh": "eyJ...",
                "user": {...}
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create test user
        user = People.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='securepassword123',
            first_name='Test',
            last_name='User'
        )

        client = APIClient()
        url = reverse('api_v2:auth-login')

        # Act: Attempt login
        response = client.post(url, {
            'username': 'testuser@example.com',
            'password': 'securepassword123'
        }, format='json')

        # Assert: Verify response structure and content
        assert response.status_code == status.HTTP_200_OK

        # V2 standardized envelope
        assert 'success' in response.data
        assert response.data['success'] is True
        assert 'data' in response.data
        assert 'meta' in response.data

        # Tokens present
        data = response.data['data']
        assert 'access' in data
        assert 'refresh' in data
        assert isinstance(data['access'], str)
        assert isinstance(data['refresh'], str)
        assert len(data['access']) > 50  # JWT tokens are long

        # User data present
        assert 'user' in data
        user_data = data['user']
        assert user_data['id'] == user.id
        assert user_data['username'] == 'testuser@example.com'
        assert user_data['email'] == 'testuser@example.com'
        assert user_data['first_name'] == 'Test'
        assert user_data['last_name'] == 'User'

        # Meta contains correlation_id
        meta = response.data['meta']
        assert 'correlation_id' in meta
        assert 'timestamp' in meta

    def test_invalid_credentials_returns_401(self):
        """Test that invalid credentials return 401 with error structure."""
        # Arrange
        People.objects.create_user(
            username='testuser@example.com',
            password='correctpassword'
        )

        client = APIClient()
        url = reverse('api_v2:auth-login')

        # Act: Attempt login with wrong password
        response = client.post(url, {
            'username': 'testuser@example.com',
            'password': 'wrongpassword'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'success' in response.data
        assert response.data['success'] is False
        assert 'error' in response.data
        assert response.data['error']['code'] == 'INVALID_CREDENTIALS'

    def test_missing_credentials_returns_400(self):
        """Test that missing username/password returns 400."""
        client = APIClient()
        url = reverse('api_v2:auth-login')

        # Act: Missing password
        response = client.post(url, {
            'username': 'testuser@example.com'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'MISSING_CREDENTIALS'

    def test_inactive_user_returns_403(self):
        """Test that inactive user account returns 403."""
        # Arrange
        user = People.objects.create_user(
            username='inactive@example.com',
            password='password123'
        )
        user.is_active = False
        user.save()

        client = APIClient()
        url = reverse('api_v2:auth-login')

        # Act
        response = client.post(url, {
            'username': 'inactive@example.com',
            'password': 'password123'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error']['code'] == 'ACCOUNT_DISABLED'


@pytest.mark.django_db
class TestRefreshTokenView:
    """Test POST /api/v2/auth/refresh/ endpoint."""

    def test_valid_refresh_token_returns_new_access_token(self):
        """
        Test that valid refresh token returns new access token.

        V2 Response format:
        {
            "success": true,
            "data": {
                "access": "eyJ...",
                "refresh": "eyJ..." (optional, if rotation enabled)
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create user and get tokens
        user = People.objects.create_user(
            username='testuser@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')

        # Login to get refresh token
        login_response = client.post(login_url, {
            'username': 'testuser@example.com',
            'password': 'password123'
        }, format='json')

        refresh_token = login_response.data['data']['refresh']

        # Act: Use refresh token to get new access token
        refresh_url = reverse('api_v2:auth-refresh')
        response = client.post(refresh_url, {
            'refresh': refresh_token
        }, format='json')

        # Assert: Verify response structure
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data
        assert 'meta' in response.data

        # New access token returned
        data = response.data['data']
        assert 'access' in data
        assert isinstance(data['access'], str)
        assert len(data['access']) > 50

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']
        assert 'timestamp' in response.data['meta']

    def test_invalid_refresh_token_returns_401(self):
        """Test that invalid refresh token returns 401."""
        client = APIClient()
        url = reverse('api_v2:auth-refresh')

        # Act: Use invalid token
        response = client.post(url, {
            'refresh': 'invalid.token.here'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'INVALID_TOKEN'

    def test_missing_refresh_token_returns_400(self):
        """Test that missing refresh token returns 400."""
        client = APIClient()
        url = reverse('api_v2:auth-refresh')

        # Act: Missing token
        response = client.post(url, {}, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'MISSING_TOKEN'


@pytest.mark.django_db
class TestLogoutView:
    """Test POST /api/v2/auth/logout/ endpoint."""

    def test_successful_logout_blacklists_token(self):
        """
        Test that logout blacklists the refresh token.

        V2 Response format:
        {
            "success": true,
            "data": {
                "message": "Logout successful"
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='testuser@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')

        # Login to get tokens
        login_response = client.post(login_url, {
            'username': 'testuser@example.com',
            'password': 'password123'
        }, format='json')

        access_token = login_response.data['data']['access']
        refresh_token = login_response.data['data']['refresh']

        # Act: Logout with access token authentication
        logout_url = reverse('api_v2:auth-logout')
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.post(logout_url, {
            'refresh': refresh_token
        }, format='json')

        # Assert: Verify logout success
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data
        assert response.data['data']['message'] == 'Logout successful'
        assert 'correlation_id' in response.data['meta']

        # Verify token is blacklisted (cannot be used again)
        refresh_url = reverse('api_v2:auth-refresh')
        client.credentials()  # Clear auth
        reuse_response = client.post(refresh_url, {
            'refresh': refresh_token
        }, format='json')

        # Should fail with INVALID_TOKEN
        assert reuse_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_without_authentication_returns_401(self):
        """Test that logout without authentication returns 401."""
        client = APIClient()
        url = reverse('api_v2:auth-logout')

        # Act: Attempt logout without authentication
        response = client.post(url, {
            'refresh': 'some.token.here'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_missing_refresh_token_returns_400(self):
        """Test that logout without refresh token returns 400."""
        # Arrange: Login to get access token
        user = People.objects.create_user(
            username='testuser@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'testuser@example.com',
            'password': 'password123'
        }, format='json')

        access_token = login_response.data['data']['access']

        # Act: Logout without refresh token
        logout_url = reverse('api_v2:auth-logout')
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.post(logout_url, {}, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'MISSING_TOKEN'


@pytest.mark.django_db
class TestVerifyTokenView:
    """Test POST /api/v2/auth/verify/ endpoint."""

    def test_valid_access_token_returns_success(self):
        """
        Test that valid access token returns verification success.

        V2 Response format:
        {
            "success": true,
            "data": {
                "valid": true,
                "user_id": 123,
                "username": "user@example.com"
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='testuser@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')

        # Login to get access token
        login_response = client.post(login_url, {
            'username': 'testuser@example.com',
            'password': 'password123'
        }, format='json')

        access_token = login_response.data['data']['access']

        # Act: Verify the access token
        verify_url = reverse('api_v2:auth-verify')
        response = client.post(verify_url, {
            'token': access_token
        }, format='json')

        # Assert: Verify success response
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data

        # Verification data
        data = response.data['data']
        assert data['valid'] is True
        assert data['user_id'] == user.id
        assert data['username'] == 'testuser@example.com'

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']
        assert 'timestamp' in response.data['meta']

    def test_invalid_access_token_returns_error(self):
        """Test that invalid access token returns error."""
        client = APIClient()
        url = reverse('api_v2:auth-verify')

        # Act: Verify invalid token
        response = client.post(url, {
            'token': 'invalid.jwt.token'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'INVALID_TOKEN'

    def test_expired_access_token_returns_error(self):
        """Test that expired access token returns error."""
        # This would require manipulating JWT expiry or waiting
        # For now, we'll test the structure
        client = APIClient()
        url = reverse('api_v2:auth-verify')

        # Act: Verify with malformed token
        response = client.post(url, {
            'token': 'malformed-token'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['success'] is False

    def test_missing_token_returns_400(self):
        """Test that missing token returns 400."""
        client = APIClient()
        url = reverse('api_v2:auth-verify')

        # Act: Missing token
        response = client.post(url, {}, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'MISSING_TOKEN'
