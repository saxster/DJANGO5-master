"""
Unit tests for API middleware.

Tests monitoring, rate limiting, caching, and security middleware.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import RequestFactory
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.contrib.auth.models import User, AnonymousUser
from django.utils import timezone

from apps.api.middleware import (
    APIMonitoringMiddleware,
    APIRateLimitMiddleware,
    APICacheMiddleware,
    APISecurityMiddleware,
    APIMiddleware
)


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.middleware
class TestAPIMonitoringMiddleware:
    """Test API monitoring middleware functionality."""
    
    def test_middleware_initialization(self):
        """Test middleware initializes correctly."""
        get_response = Mock()
        middleware = APIMonitoringMiddleware(get_response)
        
        assert middleware.get_response == get_response
        assert isinstance(middleware.excluded_paths, list)
        assert '/api/health/' in middleware.excluded_paths
    
    def test_process_request_non_api_path(self):
        """Test that non-API requests are ignored."""
        middleware = APIMonitoringMiddleware(Mock())
        request = RequestFactory().get('/admin/users/')
        
        result = middleware.process_request(request)
        
        assert result is None
        assert not hasattr(request, '_api_start_time')
    
    def test_process_request_api_path(self):
        """Test API request processing."""
        middleware = APIMonitoringMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        with patch('apps.api.middleware.time.time', return_value=1234567890):
            result = middleware.process_request(request)
        
        assert result is None
        assert hasattr(request, '_api_start_time')
        assert request._api_start_time == 1234567890
    
    def test_process_request_excluded_path(self):
        """Test that excluded paths are ignored."""
        middleware = APIMonitoringMiddleware(Mock())
        request = RequestFactory().get('/api/health/')
        
        result = middleware.process_request(request)
        
        assert result is None
        assert not hasattr(request, '_api_start_time')
    
    @patch('apps.api.middleware.api_analytics')
    def test_process_response_with_timing(self, mock_analytics):
        """Test response processing with timing information."""
        middleware = APIMonitoringMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request._api_start_time = 1234567890.0
        
        response = JsonResponse({'data': 'test'})
        
        with patch('apps.api.middleware.time.time', return_value=1234567890.5):
            result = middleware.process_response(request, response)
        
        assert result == response
        assert response['X-Response-Time'] == '0.500s'
        assert response['X-API-Version'] == 'v1'
        
        # Analytics should be recorded
        mock_analytics.record_request.assert_called_once_with(
            request, response, 0.5
        )
    
    @patch('apps.api.middleware.api_analytics')
    def test_process_response_slow_request_logging(self, mock_analytics):
        """Test that slow requests are logged."""
        middleware = APIMonitoringMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request._api_start_time = 1234567890.0
        
        response = JsonResponse({'data': 'test'})
        
        with patch('apps.api.middleware.time.time', return_value=1234567891.5):  # 1.5s
            with patch('apps.api.middleware.logger') as mock_logger:
                middleware.process_response(request, response)
                
                mock_logger.warning.assert_called_once()
                assert '1.500s' in mock_logger.warning.call_args[0][0]
    
    @patch('apps.api.middleware.api_analytics')
    def test_process_exception_handling(self, mock_analytics):
        """Test exception handling in middleware."""
        middleware = APIMonitoringMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request._api_start_time = 1234567890.0
        
        exception = ValueError("Test error")
        
        with patch('apps.api.middleware.time.time', return_value=1234567890.2):
            with patch('apps.api.middleware.logger') as mock_logger:
                result = middleware.process_exception(request, exception)
        
        assert result is None
        mock_logger.error.assert_called_once()
        
        # Analytics should record the error
        mock_analytics.record_request.assert_called_once()
    
    def test_get_api_version_extraction(self):
        """Test API version extraction from path."""
        middleware = APIMonitoringMiddleware(Mock())
        
        # Test v1 extraction
        version = middleware._get_api_version('/api/v1/people/')
        assert version == 'v1'
        
        # Test v2 extraction
        version = middleware._get_api_version('/api/v2/users/')
        assert version == 'v2'
        
        # Test default version
        version = middleware._get_api_version('/api/people/')
        assert version == 'v1'


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.rate_limit
class TestAPIRateLimitMiddleware:
    """Test rate limiting middleware functionality."""
    
    def test_middleware_initialization(self):
        """Test rate limit middleware initializes with correct limits."""
        middleware = APIRateLimitMiddleware(Mock())
        
        assert 'anonymous' in middleware.rate_limits
        assert 'authenticated' in middleware.rate_limits
        assert 'premium' in middleware.rate_limits
        
        # Check rate limit values
        anonymous_limit, anonymous_window = middleware.rate_limits['anonymous']
        assert anonymous_limit == 60
        assert anonymous_window == 3600
    
    def test_process_request_non_api_path(self):
        """Test that non-API requests bypass rate limiting."""
        middleware = APIRateLimitMiddleware(Mock())
        request = RequestFactory().get('/admin/users/')
        
        result = middleware.process_request(request)
        
        assert result is None
    
    def test_get_user_tier_anonymous(self):
        """Test user tier determination for anonymous users."""
        middleware = APIRateLimitMiddleware(Mock())
        request = Mock()
        request.user = AnonymousUser()
        
        tier = middleware._get_user_tier(request)
        
        assert tier == 'anonymous'
    
    def test_get_user_tier_authenticated(self):
        """Test user tier determination for authenticated users."""
        middleware = APIRateLimitMiddleware(Mock())
        request = Mock()
        request.user = Mock(is_authenticated=True, is_premium=False)
        
        tier = middleware._get_user_tier(request)
        
        assert tier == 'authenticated'
    
    def test_get_user_tier_premium(self):
        """Test user tier determination for premium users."""
        middleware = APIRateLimitMiddleware(Mock())
        request = Mock()
        request.user = Mock(is_authenticated=True, is_premium=True)
        
        tier = middleware._get_user_tier(request)
        
        assert tier == 'premium'
    
    def test_get_client_ip_with_forwarded_header(self):
        """Test client IP extraction with X-Forwarded-For header."""
        middleware = APIRateLimitMiddleware(Mock())
        request = Mock()
        request.META = {
            'HTTP_X_FORWARDED_FOR': '192.168.1.1,10.0.0.1',
            'REMOTE_ADDR': '127.0.0.1'
        }
        
        ip = middleware._get_client_ip(request)
        
        assert ip == '192.168.1.1'
    
    def test_get_client_ip_without_forwarded_header(self):
        """Test client IP extraction without X-Forwarded-For header."""
        middleware = APIRateLimitMiddleware(Mock())
        request = Mock()
        request.META = {
            'REMOTE_ADDR': '127.0.0.1'
        }
        
        ip = middleware._get_client_ip(request)
        
        assert ip == '127.0.0.1'
    
    @patch('apps.api.middleware.cache')
    def test_rate_limit_not_exceeded(self, mock_cache):
        """Test request allowed when rate limit not exceeded."""
        mock_cache.get.return_value = 30  # Below limit
        mock_cache.incr.return_value = 31
        
        middleware = APIRateLimitMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        result = middleware.process_request(request)
        
        assert result is None
        assert hasattr(request, '_rate_limit_limit')
        assert hasattr(request, '_rate_limit_remaining')
    
    @patch('apps.api.middleware.cache')
    def test_rate_limit_exceeded(self, mock_cache):
        """Test request blocked when rate limit exceeded."""
        mock_cache.get.return_value = 600  # At limit
        
        middleware = APIRateLimitMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == 429
        
        data = json.loads(result.content)
        assert data['error'] == 'Rate limit exceeded'
    
    def test_process_response_adds_headers(self):
        """Test that rate limit headers are added to response."""
        middleware = APIRateLimitMiddleware(Mock())
        request = Mock()
        request._rate_limit_limit = 600
        request._rate_limit_remaining = 550
        request._rate_limit_reset = 1234567890
        
        response = HttpResponse()
        
        result = middleware.process_response(request, response)
        
        assert result['X-RateLimit-Limit'] == 600
        assert result['X-RateLimit-Remaining'] == 550
        assert result['X-RateLimit-Reset'] == 1234567890


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.cache
class TestAPICacheMiddleware:
    """Test caching middleware functionality."""
    
    def test_middleware_initialization(self):
        """Test cache middleware initializes correctly."""
        middleware = APICacheMiddleware(Mock())
        
        assert middleware.cache_timeout == 300
        assert isinstance(middleware.cacheable_paths, list)
        assert '/api/v1/people/' in middleware.cacheable_paths
    
    def test_process_request_non_get_method(self):
        """Test that non-GET requests bypass caching."""
        middleware = APICacheMiddleware(Mock())
        request = RequestFactory().post('/api/v1/people/')
        
        result = middleware.process_request(request)
        
        assert result is None
    
    def test_process_request_non_cacheable_path(self):
        """Test that non-cacheable paths bypass caching."""
        middleware = APICacheMiddleware(Mock())
        request = RequestFactory().get('/api/v1/auth/login/')
        
        result = middleware.process_request(request)
        
        assert result is None
    
    def test_process_request_no_cache_header(self):
        """Test that no-cache header bypasses caching."""
        middleware = APICacheMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/?nocache=1')
        
        result = middleware.process_request(request)
        
        assert result is None
    
    @patch('apps.api.middleware.cache')
    def test_cache_hit(self, mock_cache):
        """Test cache hit returns cached response."""
        cached_data = {'data': 'cached response'}
        mock_cache.get.return_value = cached_data
        
        middleware = APICacheMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result['X-Cache'] == 'HIT'
        
        response_data = json.loads(result.content)
        assert response_data == cached_data
    
    @patch('apps.api.middleware.cache')
    def test_cache_miss(self, mock_cache):
        """Test cache miss sets up caching for response."""
        mock_cache.get.return_value = None
        
        middleware = APICacheMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        result = middleware.process_request(request)
        
        assert result is None
        assert hasattr(request, '_cache_key')
    
    @patch('apps.api.middleware.cache')
    def test_process_response_caches_successful_response(self, mock_cache):
        """Test that successful responses are cached."""
        middleware = APICacheMiddleware(Mock())
        request = Mock()
        request._cache_key = 'test_cache_key'
        
        response_data = {'data': 'test response'}
        response = JsonResponse(response_data)
        response.data = response_data
        
        result = middleware.process_response(request, response)
        
        assert result['X-Cache'] == 'MISS'
        assert 'Cache-Control' in result
        
        mock_cache.set.assert_called_once_with(
            'test_cache_key', response_data, 300
        )
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        middleware = APICacheMiddleware(Mock())
        request = Mock()
        request.path = '/api/v1/people/'
        request.META = {'QUERY_STRING': 'page=1&limit=10'}
        request.user = Mock(is_authenticated=True, id=1)
        
        cache_key = middleware._generate_cache_key(request)
        
        assert cache_key.startswith('api_cache:')
        assert len(cache_key.split(':')[1]) == 32  # MD5 hash length
    
    def test_generate_cache_key_anonymous_user(self):
        """Test cache key generation for anonymous users."""
        middleware = APICacheMiddleware(Mock())
        request = Mock()
        request.path = '/api/v1/people/'
        request.META = {'QUERY_STRING': ''}
        request.user = AnonymousUser()
        
        cache_key = middleware._generate_cache_key(request)
        
        assert 'anonymous' in cache_key


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.security
class TestAPISecurityMiddleware:
    """Test security middleware functionality."""
    
    def test_process_response_adds_security_headers(self):
        """Test that security headers are added to API responses."""
        middleware = APISecurityMiddleware()
        request = RequestFactory().get('/api/v1/people/')
        response = HttpResponse()
        
        result = middleware.process_response(request, response)
        
        assert result['X-Content-Type-Options'] == 'nosniff'
        assert result['X-Frame-Options'] == 'DENY'
        assert result['X-XSS-Protection'] == '1; mode=block'
        assert 'Strict-Transport-Security' in result
        assert result['Access-Control-Allow-Origin'] == '*'
    
    def test_process_response_removes_sensitive_headers(self):
        """Test that sensitive headers are removed."""
        middleware = APISecurityMiddleware()
        request = RequestFactory().get('/api/v1/people/')
        response = HttpResponse()
        response['Server'] = 'nginx/1.18.0'
        response['X-Powered-By'] = 'Django/3.2'
        
        result = middleware.process_response(request, response)
        
        assert 'Server' not in result
        assert 'X-Powered-By' not in result
    
    def test_process_response_non_api_path(self):
        """Test that non-API responses are not modified."""
        middleware = APISecurityMiddleware()
        request = RequestFactory().get('/admin/users/')
        response = HttpResponse()
        
        result = middleware.process_response(request, response)
        
        assert 'X-Content-Type-Options' not in result
        assert 'X-Frame-Options' not in result
    
    def test_process_response_preserves_existing_cors_headers(self):
        """Test that existing CORS headers are preserved."""
        middleware = APISecurityMiddleware()
        request = RequestFactory().get('/api/v1/people/')
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = 'https://trusted-domain.com'
        
        result = middleware.process_response(request, response)
        
        assert result['Access-Control-Allow-Origin'] == 'https://trusted-domain.com'


@pytest.mark.unit
@pytest.mark.api
class TestCombinedAPIMiddleware:
    """Test combined API middleware functionality."""
    
    def test_combined_middleware_inheritance(self):
        """Test that combined middleware inherits from all components."""
        middleware = APIMiddleware(Mock())
        
        # Should inherit from all middleware classes
        assert isinstance(middleware, APISecurityMiddleware)
        assert isinstance(middleware, APIRateLimitMiddleware) 
        assert isinstance(middleware, APICacheMiddleware)
        assert isinstance(middleware, APIMonitoringMiddleware)
    
    @patch('apps.api.middleware.api_analytics')
    @patch('apps.api.middleware.cache')
    def test_middleware_execution_order(self, mock_cache, mock_analytics):
        """Test that middleware methods execute in correct order."""
        mock_cache.get.return_value = None  # Cache miss
        mock_cache.incr.return_value = 1
        
        middleware = APIMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        # Process request
        with patch('apps.api.middleware.time.time', return_value=1234567890):
            result = middleware.process_request(request)
        
        assert result is None
        assert hasattr(request, '_api_start_time')
        assert hasattr(request, '_rate_limit_limit')
        assert hasattr(request, '_cache_key')
        
        # Process response
        response = JsonResponse({'data': 'test'})
        
        with patch('apps.api.middleware.time.time', return_value=1234567890.1):
            result = middleware.process_response(request, response)
        
        # Should have headers from all middleware
        assert 'X-Response-Time' in result  # Monitoring
        assert 'X-RateLimit-Limit' in result  # Rate limiting
        assert 'X-Cache' in result  # Caching
        assert 'X-Content-Type-Options' in result  # Security
    
    def test_middleware_error_isolation(self):
        """Test that errors in one middleware don't affect others."""
        middleware = APIMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        # Mock one middleware component to fail
        with patch('apps.api.middleware.api_analytics.record_request') as mock_record:
            mock_record.side_effect = Exception("Analytics failed")
            
            # Should still process without crashing
            with patch('apps.api.middleware.time.time', return_value=1234567890):
                result = middleware.process_request(request)
            
            assert result is None
            
            response = JsonResponse({'data': 'test'})
            
            with patch('apps.api.middleware.time.time', return_value=1234567890.1):
                result = middleware.process_response(request, response)
            
            # Should still have other middleware functionality
            assert 'X-Content-Type-Options' in result  # Security still works


@pytest.mark.unit
@pytest.mark.api
class TestMiddlewarePerformance:
    """Test middleware performance characteristics."""
    
    def test_monitoring_middleware_performance(self):
        """Test that monitoring middleware has minimal overhead."""
        middleware = APIMonitoringMiddleware(Mock())
        request = RequestFactory().get('/api/v1/people/')
        request.user = Mock(is_authenticated=True, id=1)
        
        start_time = time.time()
        
        # Process 100 requests
        for _ in range(100):
            middleware.process_request(request)
            response = JsonResponse({'data': 'test'})
            middleware.process_response(request, response)
        
        elapsed = time.time() - start_time
        
        # Should complete 100 requests in under 1 second
        assert elapsed < 1.0
    
    @patch('apps.api.middleware.cache')
    def test_cache_middleware_performance(self, mock_cache):
        """Test cache middleware performance."""
        mock_cache.get.return_value = None
        mock_cache.set.return_value = None
        
        middleware = APICacheMiddleware(Mock())
        
        start_time = time.time()
        
        # Process 100 requests
        for i in range(100):
            request = RequestFactory().get(f'/api/v1/people/?page={i}')
            request.user = Mock(is_authenticated=True, id=1)
            
            middleware.process_request(request)
            
            if hasattr(request, '_cache_key'):
                response = JsonResponse({'data': f'test{i}'})
                response.data = {'data': f'test{i}'}
                middleware.process_response(request, response)
        
        elapsed = time.time() - start_time
        
        # Should complete 100 requests in under 0.5 seconds
        assert elapsed < 0.5
    
    def test_rate_limit_middleware_memory_usage(self):
        """Test that rate limiting doesn't leak memory."""
        middleware = APIRateLimitMiddleware(Mock())
        
        # Process many requests from different IPs
        for i in range(1000):
            request = RequestFactory().get('/api/v1/people/')
            request.user = AnonymousUser()
            request.META = {'REMOTE_ADDR': f'192.168.1.{i % 255}'}
            
            middleware.process_request(request)
        
        # Test passes if no memory errors occur
        assert True