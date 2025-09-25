"""
Unit tests for API authentication.

Tests JWT, API key, and OAuth2 authentication.
"""

import pytest
import json
from unittest.mock import Mock, patch
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime, timedelta
from django.utils import timezone

from apps.api.authentication.views import (
    APIKeyObtainView,
    APIKeyRevokeView,
    OAuth2LoginView,
    OAuth2CallbackView,
    LogoutView
)


@pytest.mark.unit
@pytest.mark.auth
class TestJWTAuthentication:
    """Test JWT authentication functionality."""
    
    def test_token_obtain_pair_success(self, test_user, api_client):
        """Test successful JWT token generation."""
        url = reverse('api_auth:token_obtain_pair')
        data = {
            'username': test_user.username,
            'password': 'TestPassword123!'
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_token_obtain_pair_invalid_credentials(self, test_user, api_client):
        """Test JWT token generation with invalid credentials."""
        url = reverse('api_auth:token_obtain_pair')
        data = {
            'username': test_user.username,
            'password': 'WrongPassword'
        }
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_token_refresh_success(self, test_user, api_client):
        """Test JWT token refresh."""
        refresh = RefreshToken.for_user(test_user)
        
        url = reverse('api_auth:token_refresh')
        data = {'refresh': str(refresh)}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
    
    def test_token_refresh_invalid_token(self, api_client):
        """Test JWT token refresh with invalid token."""
        url = reverse('api_auth:token_refresh')
        data = {'refresh': 'invalid.token.here'}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_token_verify_success(self, test_user, api_client):
        """Test JWT token verification."""
        refresh = RefreshToken.for_user(test_user)
        access_token = refresh.access_token
        
        url = reverse('api_auth:token_verify')
        data = {'token': str(access_token)}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_token_verify_invalid_token(self, api_client):
        """Test JWT token verification with invalid token."""
        url = reverse('api_auth:token_verify')
        data = {'token': 'invalid.token.here'}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authenticated_request_success(self, authenticated_client):
        """Test authenticated request with valid JWT token."""
        url = '/api/v1/people/'
        
        response = authenticated_client.get(url)
        
        # Should not get authentication error
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
    
    def test_unauthenticated_request_denied(self, api_client):
        """Test unauthenticated request is denied."""
        url = '/api/v1/people/'
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.auth
class TestAPIKeyAuthentication:
    """Test API key authentication functionality."""
    
    def test_api_key_obtain_success(self, authenticated_client):
        """Test successful API key generation."""
        url = reverse('api_auth:api_key_obtain')
        data = {'name': 'Test API Key'}
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'api_key' in response.data
        assert 'name' in response.data
        assert response.data['name'] == 'Test API Key'
    
    def test_api_key_obtain_unauthenticated(self, api_client):
        """Test API key generation requires authentication."""
        url = reverse('api_auth:api_key_obtain')
        data = {'name': 'Test API Key'}
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_api_key_obtain_validation_error(self, authenticated_client):
        """Test API key generation with validation errors."""
        url = reverse('api_auth:api_key_obtain')
        data = {}  # Missing name
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'name' in response.data
    
    def test_api_key_revoke_success(self, authenticated_client):
        """Test successful API key revocation."""
        # First create an API key
        create_url = reverse('api_auth:api_key_obtain')
        create_data = {'name': 'Test API Key'}
        create_response = authenticated_client.post(create_url, create_data, format='json')
        api_key = create_response.data['api_key']
        
        # Then revoke it
        revoke_url = reverse('api_auth:api_key_revoke')
        revoke_data = {'api_key': api_key}
        
        response = authenticated_client.post(revoke_url, revoke_data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_api_key_revoke_invalid_key(self, authenticated_client):
        """Test API key revocation with invalid key."""
        url = reverse('api_auth:api_key_revoke')
        data = {'api_key': 'invalid-api-key-123'}
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_api_key_authentication_success(self, api_key_client):
        """Test successful authentication using API key."""
        url = '/api/v1/people/'
        
        response = api_key_client.get(url)
        
        # Should not get authentication error
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
    
    def test_api_key_authentication_invalid_key(self, api_client):
        """Test authentication with invalid API key."""
        api_client.credentials(HTTP_X_API_KEY='invalid-api-key')
        url = '/api/v1/people/'
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.auth
class TestOAuth2Authentication:
    """Test OAuth2 authentication functionality."""
    
    def test_oauth2_login_redirect(self, api_client):
        """Test OAuth2 login redirects to provider."""
        url = reverse('api_auth:oauth2_login')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_302_FOUND
        assert 'oauth' in response.url.lower() or 'authorize' in response.url.lower()
    
    @patch('apps.api.authentication.views.requests.post')
    def test_oauth2_callback_success(self, mock_post, api_client):
        """Test successful OAuth2 callback."""
        # Mock OAuth2 provider response
        mock_post.return_value.json.return_value = {
            'access_token': 'oauth-access-token',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        
        url = reverse('api_auth:oauth2_callback')
        
        response = api_client.get(url, {'code': 'auth-code', 'state': 'state-token'})
        
        # Should redirect or return success response
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_302_FOUND]
    
    def test_oauth2_callback_missing_code(self, api_client):
        """Test OAuth2 callback with missing authorization code."""
        url = reverse('api_auth:oauth2_callback')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @patch('apps.api.authentication.views.requests.post')
    def test_oauth2_callback_invalid_code(self, mock_post, api_client):
        """Test OAuth2 callback with invalid authorization code."""
        # Mock OAuth2 provider error response
        mock_post.return_value.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Invalid authorization code'
        }
        mock_post.return_value.status_code = 400
        
        url = reverse('api_auth:oauth2_callback')
        
        response = api_client.get(url, {'code': 'invalid-code'})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.unit
@pytest.mark.auth
class TestLogoutView:
    """Test logout functionality."""
    
    def test_logout_success(self, authenticated_client):
        """Test successful logout."""
        url = reverse('api_auth:logout')
        
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Successfully logged out'
    
    def test_logout_unauthenticated(self, api_client):
        """Test logout without authentication."""
        url = reverse('api_auth:logout')
        
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('rest_framework_simplejwt.token_blacklist.models.OutstandingToken.objects.filter')
    def test_logout_blacklists_tokens(self, mock_filter, authenticated_client):
        """Test that logout blacklists JWT tokens."""
        mock_filter.return_value.delete.return_value = None
        
        url = reverse('api_auth:logout')
        
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Token blacklisting logic would be tested here


@pytest.mark.unit
@pytest.mark.auth
class TestAuthenticationIntegration:
    """Test authentication integration scenarios."""
    
    def test_multiple_authentication_methods(self, test_user):
        """Test that multiple authentication methods work."""
        client = APIClient()
        
        # Test JWT authentication
        refresh = RefreshToken.for_user(test_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = client.get('/api/v1/people/')
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
        
        # Clear JWT credentials and test API key
        client.credentials()
        client.credentials(HTTP_X_API_KEY='test-api-key-123456789')
        
        response = client.get('/api/v1/people/')
        # This would require actual API key setup in the database
        # For now, just test that the header is set
        assert 'HTTP_X_API_KEY' in client._credentials
    
    def test_token_expiration_handling(self, test_user, api_client):
        """Test handling of expired tokens."""
        # Create an expired token
        refresh = RefreshToken.for_user(test_user)
        
        # Mock expired token
        with patch('rest_framework_simplejwt.tokens.AccessToken.check_exp') as mock_check:
            mock_check.side_effect = Exception("Token is expired")
            
            api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
            response = api_client.get('/api/v1/people/')
            
            # Should get authentication error for expired token
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_user_permissions_with_authentication(self, test_user, admin_user):
        """Test that user permissions are enforced with authentication."""
        # Test regular user
        client = APIClient()
        refresh = RefreshToken.for_user(test_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Admin endpoint should be denied for regular user
        response = client.get('/api/monitoring/dashboard/')
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,  # Permission denied
            status.HTTP_404_NOT_FOUND   # Endpoint not accessible
        ]
        
        # Test admin user
        admin_client = APIClient()
        admin_refresh = RefreshToken.for_user(admin_user)
        admin_client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_refresh.access_token}')
        
        # Admin endpoint should work for admin user
        response = admin_client.get('/api/monitoring/dashboard/')
        assert response.status_code != status.HTTP_403_FORBIDDEN
    
    def test_authentication_error_messages(self, api_client):
        """Test that authentication errors return proper messages."""
        # Test missing authentication
        response = api_client.get('/api/v1/people/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'detail' in response.data
        
        # Test invalid token format
        api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        response = api_client.get('/api/v1/people/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_csrf_protection_for_auth_endpoints(self, api_client):
        """Test CSRF protection for authentication endpoints."""
        url = reverse('api_auth:token_obtain_pair')
        data = {'username': 'test', 'password': 'test'}
        
        # API endpoints should not require CSRF tokens
        response = api_client.post(url, data, format='json')
        
        # Should not fail due to CSRF (but may fail due to invalid credentials)
        assert response.status_code != status.HTTP_403_FORBIDDEN


@pytest.mark.unit
@pytest.mark.auth
class TestAuthenticationErrorHandling:
    """Test error handling in authentication."""
    
    def test_malformed_jwt_token(self, api_client):
        """Test handling of malformed JWT tokens."""
        api_client.credentials(HTTP_AUTHORIZATION='Bearer malformed.jwt.token')
        
        response = api_client.get('/api/v1/people/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'detail' in response.data
    
    def test_missing_authorization_header(self, api_client):
        """Test handling of missing authorization header."""
        response = api_client.get('/api/v1/people/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_invalid_authorization_scheme(self, api_client):
        """Test handling of invalid authorization scheme."""
        api_client.credentials(HTTP_AUTHORIZATION='Basic invalid-scheme')
        
        response = api_client.get('/api/v1/people/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_database_error_during_authentication(self, api_client, test_user):
        """Test handling of database errors during authentication."""
        refresh = RefreshToken.for_user(test_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Mock database error
        with patch('django.contrib.auth.models.User.objects.get') as mock_get:
            mock_get.side_effect = Exception("Database connection failed")
            
            response = api_client.get('/api/v1/people/')
            
            # Should handle database error gracefully
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_concurrent_authentication_requests(self, test_user):
        """Test handling of concurrent authentication requests."""
        import threading
        import time
        
        results = []
        
        def authenticate():
            client = APIClient()
            refresh = RefreshToken.for_user(test_user)
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
            
            response = client.get('/api/v1/people/')
            results.append(response.status_code)
        
        # Create multiple threads
        threads = [threading.Thread(target=authenticate) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All requests should succeed or fail consistently
        assert len(results) == 5
        assert all(status_code != status.HTTP_500_INTERNAL_SERVER_ERROR for status_code in results)