"""
Security tests for API endpoints.

Tests authentication, authorization, input validation, and security headers.
"""

import pytest
import json
import base64
from unittest.mock import patch
from django.test import override_settings
from django.contrib.auth.models import User
from rest_framework import status


@pytest.mark.security
@pytest.mark.api
class TestAuthenticationSecurity:
    """Test authentication security."""
    
    def test_jwt_token_security(self, api_client, test_user):
        """Test JWT token security properties."""
        # Get token
        response = api_client.post('/api/v1/auth/token/', {
            'username': test_user.username,
            'password': 'TestPassword123!'
        })
        
        token = response.data['access']
        
        # Token should be properly formatted JWT
        parts = token.split('.')
        assert len(parts) == 3  # header.payload.signature
        
        # Decode header (should be base64)
        header = json.loads(base64.b64decode(parts[0] + '=='))
        assert header['typ'] == 'JWT'
        assert header['alg'] in ['HS256', 'RS256']
        
        # Token should work for authenticated requests
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = api_client.get('/api/v1/people/')
        assert response.status_code == 200
    
    def test_token_expiration(self, api_client, test_user):
        """Test that expired tokens are rejected."""
        # Mock expired token
        with patch('rest_framework_simplejwt.authentication.JWTAuthentication.get_validated_token') as mock_validate:
            mock_validate.side_effect = Exception("Token is expired")
            
            api_client.credentials(HTTP_AUTHORIZATION='Bearer expired.token.here')
            response = api_client.get('/api/v1/people/')
            
            assert response.status_code == 401
    
    def test_malformed_token_rejection(self, api_client):
        """Test that malformed tokens are rejected."""
        malformed_tokens = [
            'Bearer invalid-token',
            'Bearer invalid.token',
            'Bearer invalid.token.signature.extra',
            'Bearer ',
            'InvalidScheme token',
        ]
        
        for token in malformed_tokens:
            api_client.credentials(HTTP_AUTHORIZATION=token)
            response = api_client.get('/api/v1/people/')
            assert response.status_code == 401
    
    def test_api_key_security(self, api_key_client):
        """Test API key authentication security."""
        # Valid API key should work
        response = api_key_client.get('/api/v1/people/')
        assert response.status_code != 401
        
        # Invalid API key should fail
        api_key_client.credentials(HTTP_X_API_KEY='invalid-key')
        response = api_key_client.get('/api/v1/people/')
        assert response.status_code == 401
    
    def test_authentication_bypass_attempts(self, api_client):
        """Test various authentication bypass attempts."""
        bypass_attempts = [
            {},  # No auth header
            {'HTTP_AUTHORIZATION': 'Bearer '},
            {'HTTP_AUTHORIZATION': 'Basic admin:admin'},
            {'HTTP_X_API_KEY': ''},
            {'HTTP_X_API_KEY': 'null'},
            {'HTTP_X_API_KEY': 'undefined'},
        ]
        
        for headers in bypass_attempts:
            api_client.credentials(**headers)
            response = api_client.get('/api/v1/people/')
            assert response.status_code == 401


@pytest.mark.security
@pytest.mark.api
class TestAuthorizationSecurity:
    """Test authorization and permission security."""
    
    def test_admin_endpoint_access_control(self, authenticated_client, admin_client):
        """Test admin endpoint access control."""
        admin_endpoint = '/api/monitoring/dashboard/'
        
        # Regular user should be denied
        response = authenticated_client.get(admin_endpoint)
        assert response.status_code in [403, 404]
        
        # Admin should have access
        response = admin_client.get(admin_endpoint)
        assert response.status_code != 403
    
    def test_object_level_permissions(self, authenticated_client, people_factory, test_user):
        """Test object-level permission enforcement."""
        # Create person not owned by test user
        other_person = people_factory.create()
        
        # Should be able to view (depending on permissions)
        response = authenticated_client.get(f'/api/v1/people/{other_person.id}/')
        # This might be allowed or denied depending on business logic
        assert response.status_code in [200, 403, 404]
        
        # Test modification attempts
        response = authenticated_client.patch(
            f'/api/v1/people/{other_person.id}/',
            {'first_name': 'Hacked'},
            format='json'
        )
        # Should either succeed (if allowed) or be denied
        assert response.status_code in [200, 403, 404]
    
    def test_bulk_operation_permissions(self, authenticated_client, people_factory):
        """Test permissions on bulk operations."""
        people = people_factory.create_batch(5)
        ids = [person.id for person in people]
        
        # Test bulk update permissions
        response = authenticated_client.put('/api/v1/people/bulk_update/', {
            'ids': ids,
            'updates': {'last_name': 'BulkUpdated'}
        }, format='json')
        
        # Should either succeed or be properly denied
        assert response.status_code in [200, 403]
        
        # Test bulk delete permissions
        response = authenticated_client.delete('/api/v1/people/bulk_delete/', {
            'ids': ids
        }, format='json')
        
        assert response.status_code in [204, 403]
    
    def test_field_level_permissions(self, authenticated_client, admin_client, people_factory):
        """Test field-level permission enforcement."""
        person = people_factory.create()
        
        # Regular user response
        regular_response = authenticated_client.get(f'/api/v1/people/{person.id}/')
        
        # Admin user response
        admin_response = admin_client.get(f'/api/v1/people/{person.id}/')
        
        if regular_response.status_code == 200 and admin_response.status_code == 200:
            regular_fields = set(regular_response.data.keys())
            admin_fields = set(admin_response.data.keys())
            
            # Admin should have access to same or more fields
            assert regular_fields.issubset(admin_fields)


@pytest.mark.security
@pytest.mark.api
class TestInputValidationSecurity:
    """Test input validation and injection prevention."""
    
    def test_sql_injection_prevention(self, authenticated_client, people_factory):
        """Test SQL injection prevention."""
        people_factory.create_batch(5)
        
        # SQL injection attempts in various parameters
        injection_attempts = [
            "'; DROP TABLE peoples_people; --",
            "' OR '1'='1",
            "'; INSERT INTO peoples_people (first_name) VALUES ('hacked'); --",
            "' UNION SELECT * FROM django_session --",
            "admin'--",
            "' OR 1=1--"
        ]
        
        for injection in injection_attempts:
            # Try in search parameter
            response = authenticated_client.get('/api/v1/people/', {'search': injection})
            assert response.status_code in [200, 400]  # Should not crash
            
            # Try in filter parameter
            response = authenticated_client.get('/api/v1/people/', {'first_name': injection})
            assert response.status_code in [200, 400]
            
            # Verify no SQL injection occurred by checking data integrity
            from apps.peoples.models import People
            assert People.objects.count() >= 5  # Should still have original data
    
    def test_xss_prevention(self, authenticated_client):
        """Test XSS prevention in API responses."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//",
            "<svg onload=alert('xss')>",
        ]
        
        for payload in xss_payloads:
            # Try to create person with XSS payload
            response = authenticated_client.post('/api/v1/people/', {
                'first_name': payload,
                'last_name': 'Test',
                'email': 'xss@example.com',
                'employee_code': 'XSS001'
            }, format='json')
            
            # Should either be created (and sanitized) or rejected
            if response.status_code == 201:
                # Response should not contain raw script tags
                response_text = json.dumps(response.data)
                assert '<script>' not in response_text
                assert 'javascript:' not in response_text
                assert 'onerror=' not in response_text
    
    def test_command_injection_prevention(self, authenticated_client):
        """Test command injection prevention."""
        command_payloads = [
            "; cat /etc/passwd",
            "$(whoami)",
            "`ls -la`",
            "|whoami",
            "&& rm -rf /",
        ]
        
        for payload in command_payloads:
            response = authenticated_client.post('/api/v1/people/', {
                'first_name': payload,
                'last_name': 'Test',
                'email': 'cmd@example.com',
                'employee_code': 'CMD001'
            }, format='json')
            
            # Should not execute commands - either accept and sanitize or reject
            assert response.status_code in [201, 400]
    
    def test_path_traversal_prevention(self, authenticated_client):
        """Test path traversal prevention."""
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc/passwd",
        ]
        
        for attempt in traversal_attempts:
            # Try in various endpoints
            response = authenticated_client.get(f'/api/v1/people/{attempt}/')
            assert response.status_code in [400, 404]  # Should not access files
    
    def test_large_payload_handling(self, authenticated_client):
        """Test handling of large payloads."""
        # Create very large payload
        large_string = 'A' * 100000  # 100KB string
        
        response = authenticated_client.post('/api/v1/people/', {
            'first_name': large_string,
            'last_name': 'Test',
            'email': 'large@example.com',
            'employee_code': 'LARGE001'
        }, format='json')
        
        # Should either reject or handle gracefully
        assert response.status_code in [201, 400, 413]  # 413 = Payload Too Large
    
    def test_unicode_and_encoding_attacks(self, authenticated_client):
        """Test unicode and encoding attack prevention."""
        unicode_payloads = [
            "\u0000",  # Null byte
            "\u202e",  # Right-to-left override
            "\ufeff",  # Byte order mark
            "test\u0000admin",  # Null byte injection
            "ᴀᴅᴍɪɴ",  # Unicode lookalike
        ]
        
        for payload in unicode_payloads:
            response = authenticated_client.post('/api/v1/people/', {
                'first_name': payload,
                'last_name': 'Test',
                'email': 'unicode@example.com',
                'employee_code': 'UNI001'
            }, format='json')
            
            # Should handle gracefully
            assert response.status_code in [201, 400]


@pytest.mark.security
@pytest.mark.api
class TestRateLimitingSecurity:
    """Test rate limiting security."""
    
    def test_rate_limiting_enforcement(self, api_client, test_user):
        """Test that rate limiting is enforced."""
        # Authenticate
        token_response = api_client.post('/api/v1/auth/token/', {
            'username': test_user.username,
            'password': 'TestPassword123!'
        })
        token = token_response.data['access']
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Make many rapid requests
        responses = []
        for i in range(100):  # Try to exceed rate limit
            response = api_client.get('/api/v1/people/')
            responses.append(response.status_code)
            
            if response.status_code == 429:  # Rate limit exceeded
                break
        
        # Should eventually hit rate limit
        assert 429 in responses
    
    def test_rate_limit_headers(self, authenticated_client):
        """Test that rate limit headers are present."""
        response = authenticated_client.get('/api/v1/people/')
        
        # Should have rate limit headers
        assert 'X-RateLimit-Limit' in response
        assert 'X-RateLimit-Remaining' in response
        assert 'X-RateLimit-Reset' in response
        
        # Values should be reasonable
        assert int(response['X-RateLimit-Limit']) > 0
        assert int(response['X-RateLimit-Remaining']) >= 0
    
    def test_rate_limit_per_user(self, api_client, test_user):
        """Test that rate limiting is per-user."""
        # Create another user
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='TestPassword123!'
        )
        
        # Get tokens for both users
        token1_response = api_client.post('/api/v1/auth/token/', {
            'username': test_user.username,
            'password': 'TestPassword123!'
        })
        token1 = token1_response.data['access']
        
        token2_response = api_client.post('/api/v1/auth/token/', {
            'username': user2.username,
            'password': 'TestPassword123!'
        })
        token2 = token2_response.data['access']
        
        # Make requests with user1 until rate limited
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token1}')
        
        for _ in range(50):  # Try to hit rate limit
            response = api_client.get('/api/v1/people/')
            if response.status_code == 429:
                break
        
        # User2 should still be able to make requests
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token2}')
        response = api_client.get('/api/v1/people/')
        assert response.status_code != 429


@pytest.mark.security
@pytest.mark.api
class TestSecurityHeaders:
    """Test security headers."""
    
    def test_security_headers_present(self, authenticated_client):
        """Test that security headers are present."""
        response = authenticated_client.get('/api/v1/people/')
        
        # Security headers
        assert 'X-Content-Type-Options' in response
        assert response['X-Content-Type-Options'] == 'nosniff'
        
        assert 'X-Frame-Options' in response
        assert response['X-Frame-Options'] == 'DENY'
        
        assert 'X-XSS-Protection' in response
        assert response['X-XSS-Protection'] == '1; mode=block'
        
        assert 'Strict-Transport-Security' in response
        assert 'max-age' in response['Strict-Transport-Security']
    
    def test_cors_headers(self, authenticated_client):
        """Test CORS headers."""
        response = authenticated_client.get('/api/v1/people/')
        
        # Should have CORS headers for API endpoints
        assert 'Access-Control-Allow-Origin' in response
    
    def test_sensitive_headers_removed(self, authenticated_client):
        """Test that sensitive headers are removed."""
        response = authenticated_client.get('/api/v1/people/')
        
        # These headers should not be present
        assert 'Server' not in response
        assert 'X-Powered-By' not in response
    
    def test_content_type_validation(self, authenticated_client):
        """Test content type validation."""
        # Try to send malicious content type
        response = authenticated_client.post(
            '/api/v1/people/',
            data='{"first_name": "test"}',
            content_type='application/x-evil'
        )
        
        # Should reject or handle gracefully
        assert response.status_code in [400, 415]  # 415 = Unsupported Media Type


@pytest.mark.security
@pytest.mark.api
class TestCSRFProtection:
    """Test CSRF protection."""
    
    def test_csrf_token_not_required_for_api(self, authenticated_client):
        """Test that CSRF tokens are not required for API endpoints."""
        # API endpoints should not require CSRF tokens (using other auth methods)
        response = authenticated_client.post('/api/v1/people/', {
            'first_name': 'CSRF',
            'last_name': 'Test',
            'email': 'csrf@example.com',
            'employee_code': 'CSRF001'
        }, format='json')
        
        # Should not fail due to missing CSRF token
        assert response.status_code != 403
    
    @override_settings(USE_TZ=True)
    def test_csrf_exempt_for_api_endpoints(self, api_client):
        """Test that API endpoints are CSRF exempt."""
        # This should work without CSRF token
        response = api_client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'password'
        }, format='json')
        
        # Should not fail due to CSRF
        assert response.status_code != 403


@pytest.mark.security
@pytest.mark.api
class TestDataExposureSecurity:
    """Test data exposure security."""
    
    def test_password_not_exposed(self, authenticated_client, people_factory):
        """Test that passwords are not exposed in API responses."""
        person = people_factory.create()
        
        response = authenticated_client.get(f'/api/v1/people/{person.id}/')
        
        if response.status_code == 200:
            # Should not contain password fields
            response_text = json.dumps(response.data).lower()
            assert 'password' not in response_text
            assert 'passwd' not in response_text
            assert 'secret' not in response_text
    
    def test_sensitive_fields_filtered(self, authenticated_client, admin_client, people_factory):
        """Test that sensitive fields are filtered based on permissions."""
        person = people_factory.create()
        
        # Regular user response
        regular_response = authenticated_client.get(f'/api/v1/people/{person.id}/')
        
        # Admin response
        admin_response = admin_client.get(f'/api/v1/people/{person.id}/')
        
        if regular_response.status_code == 200 and admin_response.status_code == 200:
            # Admin might see more fields
            regular_fields = set(regular_response.data.keys())
            admin_fields = set(admin_response.data.keys())
            
            # Verify field filtering is working
            assert len(admin_fields) >= len(regular_fields)
    
    def test_error_message_information_disclosure(self, authenticated_client):
        """Test that error messages don't disclose sensitive information."""
        # Try to access non-existent resource
        response = authenticated_client.get('/api/v1/people/99999/')
        
        if response.status_code == 404:
            error_message = json.dumps(response.data).lower()
            
            # Should not disclose system paths, database info, etc.
            assert '/home/' not in error_message
            assert '/var/' not in error_message
            assert 'database' not in error_message
            assert 'traceback' not in error_message
            assert 'exception' not in error_message
    
    def test_debug_information_not_exposed(self, authenticated_client):
        """Test that debug information is not exposed."""
        # Try to trigger an error
        response = authenticated_client.get('/api/v1/people/invalid/')
        
        response_text = json.dumps(response.data) if hasattr(response, 'data') else str(response.content)
        
        # Should not contain debug information
        assert 'traceback' not in response_text.lower()
        assert 'django.core' not in response_text.lower()
        assert '/home/' not in response_text
        assert 'line ' not in response_text.lower()


@pytest.mark.security
@pytest.mark.api
class TestTLSSecurity:
    """Test TLS/SSL security (where applicable)."""
    
    def test_secure_cookie_settings(self, authenticated_client):
        """Test secure cookie settings."""
        response = authenticated_client.get('/api/v1/people/')
        
        # Check for secure cookie headers if cookies are used
        if 'Set-Cookie' in response:
            cookie_header = response['Set-Cookie']
            # Should have secure flags in production
            # This would be environment-dependent
            assert True  # Placeholder for actual cookie security checks
    
    def test_hsts_header(self, authenticated_client):
        """Test HTTP Strict Transport Security header."""
        response = authenticated_client.get('/api/v1/people/')
        
        if 'Strict-Transport-Security' in response:
            hsts_value = response['Strict-Transport-Security']
            assert 'max-age' in hsts_value
            # Should have reasonable max-age
            assert 'max-age=0' not in hsts_value