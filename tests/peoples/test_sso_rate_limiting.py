"""
Tests for SSO Callback Rate Limiting

Verifies DoS protection through rate limiting.
Tests both SAML and OIDC endpoints.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.peoples.views.sso_callback import saml_acs_view, oidc_callback_view

People = get_user_model()


@pytest.fixture
def request_factory():
    """Provide request factory."""
    return RequestFactory()


@pytest.fixture
def mock_user():
    """Create mock user for tests."""
    user = Mock(spec=People)
    user.id = 1
    user.username = "testuser"
    user.is_authenticated = True
    return user


class TestSAMLRateLimiting:
    """Test rate limiting on SAML ACS endpoint."""
    
    @patch('apps.peoples.views.sso_callback.SAML2Backend')
    @patch('apps.peoples.views.sso_callback._parse_saml_response')
    @patch('apps.peoples.views.sso_callback.AuditLoggingService.log_authentication')
    @patch('apps.peoples.views.sso_callback.login')
    def test_saml_under_rate_limit_succeeds(
        self, mock_login, mock_audit, mock_parse, mock_backend, 
        request_factory, mock_user
    ):
        """Test SAML callback succeeds under rate limit."""
        mock_parse.return_value = {'attributes': {}}
        mock_backend.return_value.authenticate.return_value = mock_user
        
        request = request_factory.post(
            '/sso/saml/acs/',
            {'SAMLResponse': 'base64encodedresponse', 'RelayState': '/dashboard/'}
        )
        request.user = Mock(is_authenticated=False)
        
        # Should succeed (first request, under limit)
        with patch('apps.peoples.views.sso_callback.ratelimit', lambda *args, **kwargs: lambda f: f):
            response = saml_acs_view(request)
            assert response.status_code == 302  # Redirect on success
            mock_audit.assert_called_once()
    
    @patch('apps.peoples.views.sso_callback._get_client_ip')
    @patch('apps.peoples.views.sso_callback.AuditLoggingService.log_authentication')
    def test_saml_rate_limit_exceeded_returns_429(
        self, mock_audit, mock_get_ip, request_factory
    ):
        """Test SAML callback returns 429 when rate limited."""
        mock_get_ip.return_value = '192.168.1.100'
        
        request = request_factory.post(
            '/sso/saml/acs/',
            {'SAMLResponse': 'base64encodedresponse'}
        )
        request.user = Mock(is_authenticated=False, username='anonymous')
        request.limited = True  # Simulate rate limit
        
        # Manually trigger Ratelimited exception
        from django_ratelimit.exceptions import Ratelimited
        
        with patch('apps.peoples.views.sso_callback._parse_saml_response') as mock_parse:
            mock_parse.side_effect = Ratelimited()
            
            response = saml_acs_view(request)
            
            assert response.status_code == 429
            assert 'Too many requests' in response.json()['error']
            # Verify audit log for rate limit violation
            mock_audit.assert_called_with(
                None, 'saml_sso', success=False, error='Rate limit exceeded'
            )
    
    @patch('apps.peoples.views.sso_callback.logger')
    @patch('apps.peoples.views.sso_callback._get_client_ip')
    def test_saml_rate_limit_logs_violation(
        self, mock_get_ip, mock_logger, request_factory
    ):
        """Test rate limit violations are logged for monitoring."""
        mock_get_ip.return_value = '10.0.0.50'
        
        request = request_factory.post(
            '/sso/saml/acs/',
            {'SAMLResponse': 'base64encodedresponse'}
        )
        request.user = Mock(is_authenticated=False, username='attacker')
        
        from django_ratelimit.exceptions import Ratelimited
        
        with patch('apps.peoples.views.sso_callback._parse_saml_response') as mock_parse:
            mock_parse.side_effect = Ratelimited()
            
            saml_acs_view(request)
            
            # Verify warning logged with IP and user
            mock_logger.warning.assert_called_once()
            log_message = mock_logger.warning.call_args[0][0]
            assert 'SAML rate limit exceeded' in log_message
            assert '10.0.0.50' in log_message


class TestOIDCRateLimiting:
    """Test rate limiting on OIDC callback endpoint."""
    
    @patch('apps.peoples.views.sso_callback.OIDCBackend')
    @patch('apps.peoples.views.sso_callback._exchange_code_for_token')
    @patch('apps.peoples.views.sso_callback.AuditLoggingService.log_authentication')
    @patch('apps.peoples.views.sso_callback.login')
    def test_oidc_under_rate_limit_succeeds(
        self, mock_login, mock_audit, mock_exchange, mock_backend,
        request_factory, mock_user
    ):
        """Test OIDC callback succeeds under rate limit."""
        mock_exchange.return_value = {'sub': '12345', 'email': 'test@example.com'}
        mock_backend.return_value.authenticate.return_value = mock_user
        
        request = request_factory.get(
            '/sso/oidc/callback/',
            {'code': 'authcode123', 'state': '/dashboard/'}
        )
        request.user = Mock(is_authenticated=False)
        
        with patch('apps.peoples.views.sso_callback.ratelimit', lambda *args, **kwargs: lambda f: f):
            response = oidc_callback_view(request)
            assert response.status_code == 302
            mock_audit.assert_called_once()
    
    @patch('apps.peoples.views.sso_callback._get_client_ip')
    @patch('apps.peoples.views.sso_callback.AuditLoggingService.log_authentication')
    def test_oidc_rate_limit_exceeded_returns_429(
        self, mock_audit, mock_get_ip, request_factory
    ):
        """Test OIDC callback returns 429 when rate limited."""
        mock_get_ip.return_value = '172.16.0.1'
        
        request = request_factory.get(
            '/sso/oidc/callback/',
            {'code': 'authcode123'}
        )
        request.user = Mock(is_authenticated=False, username='anonymous')
        
        from django_ratelimit.exceptions import Ratelimited
        
        with patch('apps.peoples.views.sso_callback._exchange_code_for_token') as mock_exchange:
            mock_exchange.side_effect = Ratelimited()
            
            response = oidc_callback_view(request)
            
            assert response.status_code == 429
            assert 'Too many requests' in response.json()['error']
            mock_audit.assert_called_with(
                None, 'oidc_sso', success=False, error='Rate limit exceeded'
            )
    
    @patch('apps.peoples.views.sso_callback.logger')
    @patch('apps.peoples.views.sso_callback._get_client_ip')
    def test_oidc_rate_limit_logs_violation(
        self, mock_get_ip, mock_logger, request_factory
    ):
        """Test OIDC rate limit violations logged."""
        mock_get_ip.return_value = '203.0.113.42'
        
        request = request_factory.get(
            '/sso/oidc/callback/',
            {'code': 'authcode123'}
        )
        request.user = Mock(is_authenticated=True, username='malicious_user')
        
        from django_ratelimit.exceptions import Ratelimited
        
        with patch('apps.peoples.views.sso_callback._exchange_code_for_token') as mock_exchange:
            mock_exchange.side_effect = Ratelimited()
            
            oidc_callback_view(request)
            
            mock_logger.warning.assert_called_once()
            log_message = mock_logger.warning.call_args[0][0]
            assert 'OIDC rate limit exceeded' in log_message
            assert '203.0.113.42' in log_message


class TestRateLimitConfiguration:
    """Test rate limit decorator configuration."""
    
    def test_saml_has_ip_rate_limit(self):
        """Verify SAML endpoint has IP-based rate limiting."""
        # Check decorators are applied
        import inspect
        from apps.peoples.views.sso_callback import saml_acs_view
        
        # django-ratelimit decorators should be present
        source = inspect.getsource(saml_acs_view)
        assert '@ratelimit' in source
        assert "key='ip'" in source
        assert "rate='10/m'" in source
    
    def test_saml_has_user_rate_limit(self):
        """Verify SAML endpoint has user-based rate limiting."""
        import inspect
        from apps.peoples.views.sso_callback import saml_acs_view
        
        source = inspect.getsource(saml_acs_view)
        assert "key='user_or_ip'" in source
        assert "rate='20/m'" in source
    
    def test_oidc_has_ip_rate_limit(self):
        """Verify OIDC endpoint has IP-based rate limiting."""
        import inspect
        from apps.peoples.views.sso_callback import oidc_callback_view
        
        source = inspect.getsource(oidc_callback_view)
        assert '@ratelimit' in source
        assert "key='ip'" in source
        assert "rate='10/m'" in source
    
    def test_oidc_has_user_rate_limit(self):
        """Verify OIDC endpoint has user-based rate limiting."""
        import inspect
        from apps.peoples.views.sso_callback import oidc_callback_view
        
        source = inspect.getsource(oidc_callback_view)
        assert "key='user_or_ip'" in source
        assert "rate='20/m'" in source


class TestClientIPExtraction:
    """Test IP extraction helper."""
    
    def test_extracts_ip_from_x_forwarded_for(self, request_factory):
        """Test IP extraction from X-Forwarded-For header."""
        from apps.peoples.views.sso_callback import _get_client_ip
        
        request = request_factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 198.51.100.1'
        
        ip = _get_client_ip(request)
        assert ip == '203.0.113.1'
    
    def test_extracts_ip_from_remote_addr(self, request_factory):
        """Test IP extraction from REMOTE_ADDR."""
        from apps.peoples.views.sso_callback import _get_client_ip
        
        request = request_factory.get('/')
        request.META['REMOTE_ADDR'] = '192.0.2.1'
        
        ip = _get_client_ip(request)
        assert ip == '192.0.2.1'
    
    def test_handles_missing_ip(self, request_factory):
        """Test graceful handling when IP missing."""
        from apps.peoples.views.sso_callback import _get_client_ip
        
        request = request_factory.get('/')
        # No IP headers
        
        ip = _get_client_ip(request)
        assert ip == 'unknown'
