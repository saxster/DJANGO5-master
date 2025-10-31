"""
Middleware for Conversational Onboarding API observability and security (Phase 1 MVP)
"""
import time
import logging
from typing import Dict, Any
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from django.contrib.auth import get_user_model
import uuid

logger = logging.getLogger("django")
audit_logger = logging.getLogger("audit")
metrics_logger = logging.getLogger("metrics")

User = get_user_model()


class OnboardingAPIMiddleware(MiddlewareMixin):
    """
    Middleware for onboarding API endpoints providing:
    - Request/response logging
    - Performance metrics
    - Rate limiting
    - Audit trails
    - Error tracking
    """

    # Django 5.2+ requires explicit async_mode declaration
    async_mode = False  # This middleware is synchronous only

    def __init__(self, get_response):
        super().__init__(get_response)
        self.onboarding_api_paths = [
            '/api/v1/onboarding/',
        ]

    def process_request(self, request: HttpRequest):
        """Process incoming request for onboarding API endpoints"""
        if not self._is_onboarding_api_request(request):
            return None

        # Add request start time for performance tracking
        request._onboarding_start_time = time.time()

        # Use existing correlation ID from CorrelationIDMiddleware if available
        correlation_id = getattr(request, '_correlation_id', None)
        if not correlation_id:
            # Fallback to generating new one if core middleware didn't set it
            correlation_id = str(uuid.uuid4())
            request._correlation_id = correlation_id

        # Check rate limits
        if self._is_rate_limited(request):
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'retry_after': 60
            }, status=429)

        # Log API request
        self._log_api_request(request, correlation_id)

        return None

    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Process response for onboarding API endpoints"""
        if not self._is_onboarding_api_request(request):
            return response

        # Calculate response time
        if hasattr(request, '_onboarding_start_time'):
            response_time = time.time() - request._onboarding_start_time
            response['X-Response-Time'] = f"{response_time:.3f}s"
        else:
            response_time = 0

        # Add correlation ID to response
        if hasattr(request, '_correlation_id'):
            response['X-Correlation-ID'] = request._correlation_id

        # Log API response
        self._log_api_response(request, response, response_time)

        # Track metrics
        self._track_metrics(request, response, response_time)

        return response

    def process_exception(self, request: HttpRequest, exception: Exception):
        """Process exceptions in onboarding API endpoints"""
        if not self._is_onboarding_api_request(request):
            return None

        # Log exception with context
        correlation_id = getattr(request, '_correlation_id', 'unknown')
        logger.error(
            f"Onboarding API Exception [{correlation_id}]: {str(exception)}",
            extra={
                'path': request.path,
                'method': request.method,
                'user': str(request.user) if hasattr(request, 'user') else 'anonymous',
                'correlation_id': correlation_id,
                'exception_type': type(exception).__name__
            },
            exc_info=True
        )

        # Track error metrics
        self._track_error_metrics(request, exception)

        return None

    def _is_onboarding_api_request(self, request: HttpRequest) -> bool:
        """Check if request is for onboarding API endpoints"""
        return any(request.path.startswith(path) for path in self.onboarding_api_paths)

    def _is_rate_limited(self, request: HttpRequest) -> bool:
        """Check if request should be rate limited"""
        if not getattr(settings, 'ENABLE_RATE_LIMITING', True):
            return False

        # Get user identifier for rate limiting
        user_key = self._get_user_key_for_rate_limiting(request)

        # Rate limit configuration for onboarding API
        rate_limit_window = getattr(settings, 'ONBOARDING_API_RATE_LIMIT_WINDOW', 60)  # seconds
        max_requests = getattr(settings, 'ONBOARDING_API_MAX_REQUESTS', 30)  # requests per window

        cache_key = f"onboarding_api_rate_limit:{user_key}"

        # Get current request count
        current_count = cache.get(cache_key, 0)

        if current_count >= max_requests:
            return True

        # Increment counter
        cache.set(cache_key, current_count + 1, rate_limit_window)
        return False

    def _get_user_key_for_rate_limiting(self, request: HttpRequest) -> str:
        """Get unique key for rate limiting"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        else:
            # Use IP address for anonymous users
            ip = self._get_client_ip(request)
            return f"ip:{ip}"

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip

    def _log_api_request(self, request: HttpRequest, correlation_id: str):
        """Log API request with audit trail"""
        try:
            # Prepare request data (be careful with sensitive data)
            request_data = {
                'correlation_id': correlation_id,
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.GET),
                'user': str(request.user) if hasattr(request, 'user') else 'anonymous',
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip_address': self._get_client_ip(request),
                'timestamp': time.time()
            }

            # Don't log request body for security reasons (may contain sensitive data)
            # Only log content type and size
            if hasattr(request, 'content_type'):
                request_data['content_type'] = request.content_type

            if hasattr(request, 'body'):
                request_data['content_length'] = len(request.body)

            audit_logger.info(
                f"Onboarding API Request [{correlation_id}]",
                extra=request_data
            )

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error logging API request: {str(e)}")

    def _log_api_response(self, request: HttpRequest, response: HttpResponse, response_time: float):
        """Log API response with audit trail"""
        try:
            correlation_id = getattr(request, '_correlation_id', 'unknown')

            response_data = {
                'correlation_id': correlation_id,
                'status_code': response.status_code,
                'response_time': response_time,
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
                'timestamp': time.time()
            }

            # Log response summary (not full content for security/performance)
            audit_logger.info(
                f"Onboarding API Response [{correlation_id}] - {response.status_code} - {response_time:.3f}s",
                extra=response_data
            )

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error logging API response: {str(e)}")

    def _track_metrics(self, request: HttpRequest, response: HttpResponse, response_time: float):
        """Track performance and usage metrics"""
        try:
            # Resolve URL to get view name
            try:
                resolved_url = resolve(request.path)
                endpoint_name = f"{resolved_url.app_name}:{resolved_url.url_name}" if resolved_url.app_name else resolved_url.url_name
            except (ValueError, TypeError, AttributeError) as e:
                endpoint_name = request.path

            metrics_data = {
                'endpoint': endpoint_name,
                'method': request.method,
                'status_code': response.status_code,
                'response_time': response_time,
                'user_authenticated': hasattr(request, 'user') and request.user.is_authenticated,
                'timestamp': time.time()
            }

            metrics_logger.info(
                f"Onboarding API Metrics - {endpoint_name} - {request.method} - {response.status_code} - {response_time:.3f}s",
                extra=metrics_data
            )

            # Track in cache for basic analytics (could be enhanced with proper metrics system)
            self._update_metrics_cache(endpoint_name, request.method, response.status_code, response_time)

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error tracking metrics: {str(e)}")

    def _update_metrics_cache(self, endpoint: str, method: str, status_code: int, response_time: float):
        """Update cached metrics for basic analytics"""
        try:
            cache_key = f"onboarding_api_metrics:{endpoint}:{method}"
            metrics = cache.get(cache_key, {
                'count': 0,
                'total_response_time': 0,
                'status_codes': {},
                'last_updated': time.time()
            })

            metrics['count'] += 1
            metrics['total_response_time'] += response_time
            metrics['status_codes'][str(status_code)] = metrics['status_codes'].get(str(status_code), 0) + 1
            metrics['last_updated'] = time.time()
            metrics['avg_response_time'] = metrics['total_response_time'] / metrics['count']

            # Cache for 1 hour
            cache.set(cache_key, metrics, 3600)

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error updating metrics cache: {str(e)}")

    def _track_error_metrics(self, request: HttpRequest, exception: Exception):
        """Track error metrics"""
        try:
            error_data = {
                'exception_type': type(exception).__name__,
                'path': request.path,
                'method': request.method,
                'user': str(request.user) if hasattr(request, 'user') else 'anonymous',
                'timestamp': time.time()
            }

            metrics_logger.error(
                f"Onboarding API Error - {type(exception).__name__} - {request.path}",
                extra=error_data
            )

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error tracking error metrics: {str(e)}")

    def _validate_cache_backend_for_production(self) -> Dict[str, Any]:
        """
        Validate cache backend is production-ready for distributed rate limiting

        Returns:
            Dict with validation status and recommendations
        """
        validation_result = {
            'is_valid': True,
            'backend_type': 'unknown',
            'warnings': [],
            'recommendations': []
        }

        try:
            from django.core.cache import cache
            from django.conf import settings

            # Get cache backend configuration
            cache_backend = cache._cache.__class__.__module__ + '.' + cache._cache.__class__.__name__

            if 'redis' in cache_backend.lower():
                validation_result['backend_type'] = 'redis'
                validation_result['is_valid'] = True
            elif 'memcached' in cache_backend.lower():
                validation_result['backend_type'] = 'memcached'
                validation_result['is_valid'] = True
            elif 'locmem' in cache_backend.lower() or 'dummy' in cache_backend.lower():
                validation_result['backend_type'] = 'local_memory'
                validation_result['is_valid'] = False
                validation_result['warnings'].append(
                    'Local memory cache detected - rate limiting may not work correctly in multi-worker environments'
                )
                validation_result['recommendations'].append(
                    'Configure Redis or Memcached for production rate limiting'
                )
            else:
                validation_result['backend_type'] = cache_backend
                validation_result['warnings'].append(
                    f'Unknown cache backend: {cache_backend}'
                )

            # Test cache connectivity
            test_key = f"onboarding_cache_test_{uuid.uuid4()}"
            try:
                cache.set(test_key, 'test_value', 60)
                retrieved_value = cache.get(test_key)
                cache.delete(test_key)

                if retrieved_value != 'test_value':
                    validation_result['is_valid'] = False
                    validation_result['warnings'].append('Cache connectivity test failed')
            except (ConnectionError, TypeError, ValidationError, ValueError) as cache_error:
                validation_result['is_valid'] = False
                validation_result['warnings'].append(f'Cache operation failed: {str(cache_error)}')

            # Production environment check
            if not settings.DEBUG and validation_result['backend_type'] == 'local_memory':
                validation_result['is_valid'] = False
                validation_result['warnings'].append(
                    'Production environment detected with local memory cache - this will cause issues'
                )

        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            validation_result['is_valid'] = False
            validation_result['warnings'].append(f'Cache validation error: {str(e)}')

        return validation_result

    @classmethod
    def get_cache_health_status(cls) -> Dict[str, Any]:
        """
        Get cache health status for monitoring/health checks

        Returns:
            Dict with cache health information
        """
        instance = cls(get_response=lambda r: None)
        return instance._validate_cache_backend_for_production()


class OnboardingAuditMiddleware(MiddlewareMixin):
    """
    Specialized audit middleware for onboarding API actions
    Tracks specific onboarding events for compliance and analysis
    """

    # Django 5.2+ requires explicit async_mode declaration
    async_mode = False  # This middleware is synchronous only

    def __init__(self, get_response):
        super().__init__(get_response)
        self.audit_paths = {
            '/api/v1/onboarding/conversation/start/': 'conversation_started',
            '/api/v1/onboarding/recommendations/approve/': 'recommendations_approved',
        }

    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Process response and log audit events"""
        if not self._should_audit(request, response):
            return response

        try:
            self._log_audit_event(request, response)
        except (ConnectionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error logging audit event: {str(e)}")

        return response

    def _should_audit(self, request: HttpRequest, response: HttpResponse) -> bool:
        """Check if request should be audited"""
        # Only audit successful POST requests to specific endpoints
        if request.method != 'POST' or response.status_code >= 400:
            return False

        return any(request.path.startswith(path) for path in self.audit_paths.keys())

    def _log_audit_event(self, request: HttpRequest, response: HttpResponse):
        """Log audit event with business context"""
        event_type = self._get_event_type(request.path)

        audit_data = {
            'event_type': event_type,
            'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
            'ip_address': self._get_client_ip(request),
            'path': request.path,
            'status_code': response.status_code,
            'timestamp': time.time(),
            'correlation_id': getattr(request, '_correlation_id', None)
        }

        # Add business-specific context
        if event_type == 'conversation_started':
            audit_data['business_action'] = 'User initiated conversational onboarding'
        elif event_type == 'recommendations_approved':
            audit_data['business_action'] = 'User approved AI recommendations for system configuration'

        audit_logger.info(
            f"Onboarding Audit Event - {event_type}",
            extra=audit_data
        )

    def _get_event_type(self, path: str) -> str:
        """Get event type from path"""
        for audit_path, event_type in self.audit_paths.items():
            if path.startswith(audit_path):
                return event_type
        return 'unknown_event'

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip