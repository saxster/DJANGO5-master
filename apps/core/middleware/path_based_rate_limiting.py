"""
Path-Based Rate Limiting Middleware

Enforces the RATE_LIMIT_PATHS setting from settings/security/rate_limiting.py
to provide comprehensive protection against brute force attacks, DoS, and API abuse.

CRITICAL SECURITY:
This middleware addresses CVSS 7.2 vulnerability by implementing Rule #9
from .claude/rules.md - Comprehensive Rate Limiting.

Features:
- IP + User dual tracking
- Exponential backoff for repeated violations
- Automatic IP blocking after threshold
- Trusted IP whitelist bypass
- Per-endpoint rate limit customization
- Real-time monitoring and alerting
"""

import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone as django_tz
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import render

logger = logging.getLogger('rate_limiting')
security_logger = logging.getLogger('security')


class PathBasedRateLimitMiddleware(MiddlewareMixin):
    """
    Enforces rate limiting on paths defined in RATE_LIMIT_PATHS setting.

    Implements comprehensive protection for:
    - /admin/ - Admin panel brute force protection
    - /login/ - Authentication endpoint protection
    - /api/ - API abuse prevention
    - /graphql/ - GraphQL query flooding prevention
    - Password reset endpoints

    Rate Limiting Strategy:
    1. Check if path matches RATE_LIMIT_PATHS
    2. Check IP blocklist (automatic blocking)
    3. Check trusted IP whitelist (bypass)
    4. Apply per-user + per-IP rate limits
    5. Implement exponential backoff for violations
    6. Log all violations for monitoring
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)

        self.enabled = getattr(settings, 'ENABLE_RATE_LIMITING', True)
        self.rate_limit_paths = getattr(settings, 'RATE_LIMIT_PATHS', [])
        self.window_minutes = getattr(settings, 'RATE_LIMIT_WINDOW_MINUTES', 15)
        self.max_attempts = getattr(settings, 'RATE_LIMIT_MAX_ATTEMPTS', 5)
        self.rate_limits = getattr(settings, 'RATE_LIMITS', {})

        self.exponential_backoff_enabled = True
        self.max_backoff_hours = 24
        self.auto_block_threshold = 10

        self.cache_prefix = 'path_rate_limit'
        self.block_cache_prefix = 'blocked_ip'
        self.trusted_ips = self._load_trusted_ips()

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request and apply rate limiting if path matches.

        Args:
            request: Django HttpRequest object

        Returns:
            HttpResponse if rate limited, None to continue
        """
        if not self.enabled:
            return None

        if not self._should_rate_limit_path(request.path):
            return None

        correlation_id = getattr(request, 'correlation_id', 'unknown')
        client_ip = self._get_client_ip(request)

        if self._is_blocked_ip(client_ip):
            return self._create_blocked_response(request, correlation_id, client_ip)

        if self._is_trusted_ip(client_ip):
            return None

        rate_limit_result = self._check_rate_limit(request, client_ip, correlation_id)

        if rate_limit_result:
            self._handle_rate_limit_violation(
                request,
                client_ip,
                rate_limit_result,
                correlation_id
            )
            return self._create_rate_limit_response(
                request,
                rate_limit_result,
                correlation_id
            )

        self._increment_counters(request, client_ip)

        return None

    def _should_rate_limit_path(self, path: str) -> bool:
        """Check if the request path should be rate limited."""
        return any(path.startswith(limit_path) for limit_path in self.rate_limit_paths)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip

    def _get_user_identifier(self, request: HttpRequest) -> Optional[str]:
        """Get user identifier if authenticated."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user_{request.user.id}"
        return None

    def _load_trusted_ips(self) -> set:
        """Load trusted IPs from cache or database."""
        cached_trusted = cache.get('trusted_ips_set')
        if cached_trusted:
            return cached_trusted

        trusted_ips = set(getattr(settings, 'RATE_LIMIT_TRUSTED_IPS', [
            '127.0.0.1',
            '::1',
            'localhost'
        ]))

        cache.set('trusted_ips_set', trusted_ips, 3600)
        return trusted_ips

    def _is_trusted_ip(self, client_ip: str) -> bool:
        """Check if IP is in trusted whitelist."""
        return client_ip in self.trusted_ips

    def _is_blocked_ip(self, client_ip: str) -> bool:
        """Check if IP is in the automatic block list."""
        block_key = f"{self.block_cache_prefix}:{client_ip}"
        block_data = cache.get(block_key)

        if not block_data:
            return False

        if time.time() < block_data.get('blocked_until', 0):
            return True

        cache.delete(block_key)
        return False

    def _get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type for specific rate limit configuration."""
        if path.startswith('/admin/'):
            return 'admin'
        elif path.startswith('/login') or path.startswith('/accounts/login'):
            return 'auth'
        elif path.startswith('/graphql'):
            return 'graphql'
        elif path.startswith('/api/'):
            return 'api'
        elif 'reset-password' in path or 'password-reset' in path:
            return 'auth'
        else:
            return 'default'

    def _get_rate_limit_config(self, endpoint_type: str) -> Tuple[int, int]:
        """
        Get rate limit configuration for endpoint type.

        Returns:
            Tuple of (max_requests, window_seconds)
        """
        if endpoint_type in self.rate_limits:
            config = self.rate_limits[endpoint_type]
            return (
                config.get('max_requests', self.max_attempts),
                config.get('window_seconds', self.window_minutes * 60)
            )

        return (self.max_attempts, self.window_minutes * 60)

    def _check_rate_limit(
        self,
        request: HttpRequest,
        client_ip: str,
        correlation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if request exceeds rate limit.

        Implements dual tracking: IP-based + User-based

        Returns:
            Dict with violation details if rate limited, None otherwise
        """
        endpoint_type = self._get_endpoint_type(request.path)
        max_requests, window_seconds = self._get_rate_limit_config(endpoint_type)

        user_identifier = self._get_user_identifier(request)

        ip_key = f"{self.cache_prefix}:ip:{client_ip}:{endpoint_type}"
        ip_data = cache.get(ip_key, {'count': 0, 'first_request': time.time()})

        if time.time() - ip_data['first_request'] > window_seconds:
            ip_data = {'count': 0, 'first_request': time.time()}

        if ip_data['count'] >= max_requests:
            violation_count = self._get_violation_count(client_ip)
            backoff_seconds = self._calculate_exponential_backoff(violation_count)

            return {
                'reason': 'ip_rate_limit',
                'identifier': client_ip,
                'current': ip_data['count'],
                'limit': max_requests,
                'window_seconds': window_seconds,
                'endpoint_type': endpoint_type,
                'violation_count': violation_count,
                'backoff_seconds': backoff_seconds,
                'path': request.path
            }

        if user_identifier:
            user_key = f"{self.cache_prefix}:{user_identifier}:{endpoint_type}"
            user_data = cache.get(user_key, {'count': 0, 'first_request': time.time()})

            if time.time() - user_data['first_request'] > window_seconds:
                user_data = {'count': 0, 'first_request': time.time()}

            if user_data['count'] >= max_requests:
                violation_count = self._get_violation_count(user_identifier)
                backoff_seconds = self._calculate_exponential_backoff(violation_count)

                return {
                    'reason': 'user_rate_limit',
                    'identifier': user_identifier,
                    'current': user_data['count'],
                    'limit': max_requests,
                    'window_seconds': window_seconds,
                    'endpoint_type': endpoint_type,
                    'violation_count': violation_count,
                    'backoff_seconds': backoff_seconds,
                    'path': request.path
                }

        return None

    def _calculate_exponential_backoff(self, violation_count: int) -> int:
        """
        Calculate exponential backoff delay based on violation count.

        Formula: min(2^violation_count minutes, max_backoff_hours)

        Examples:
        - 1st violation: 2 minutes
        - 2nd violation: 4 minutes
        - 3rd violation: 8 minutes
        - 10th violation: 1024 minutes (capped at 24 hours)
        """
        if not self.exponential_backoff_enabled:
            return self.window_minutes * 60

        backoff_minutes = 2 ** violation_count
        max_backoff_minutes = self.max_backoff_hours * 60

        backoff_minutes = min(backoff_minutes, max_backoff_minutes)

        return backoff_minutes * 60

    def _get_violation_count(self, identifier: str) -> int:
        """Get total violation count for identifier (IP or user)."""
        violation_key = f"{self.cache_prefix}:violations:{identifier}"
        return cache.get(violation_key, 0)

    def _increment_violation_count(self, identifier: str):
        """Increment violation count with 24-hour expiry."""
        violation_key = f"{self.cache_prefix}:violations:{identifier}"
        current_count = cache.get(violation_key, 0)
        cache.set(violation_key, current_count + 1, 86400)

    def _increment_counters(self, request: HttpRequest, client_ip: str):
        """Increment rate limit counters for successful request."""
        endpoint_type = self._get_endpoint_type(request.path)
        _, window_seconds = self._get_rate_limit_config(endpoint_type)

        ip_key = f"{self.cache_prefix}:ip:{client_ip}:{endpoint_type}"
        ip_data = cache.get(ip_key, {'count': 0, 'first_request': time.time()})

        if time.time() - ip_data['first_request'] > window_seconds:
            ip_data = {'count': 1, 'first_request': time.time()}
        else:
            ip_data['count'] += 1

        cache.set(ip_key, ip_data, window_seconds)

        user_identifier = self._get_user_identifier(request)
        if user_identifier:
            user_key = f"{self.cache_prefix}:{user_identifier}:{endpoint_type}"
            user_data = cache.get(user_key, {'count': 0, 'first_request': time.time()})

            if time.time() - user_data['first_request'] > window_seconds:
                user_data = {'count': 1, 'first_request': time.time()}
            else:
                user_data['count'] += 1

            cache.set(user_key, user_data, window_seconds)

    def _handle_rate_limit_violation(
        self,
        request: HttpRequest,
        client_ip: str,
        violation_data: Dict[str, Any],
        correlation_id: str
    ):
        """Handle rate limit violation with logging and blocking."""
        identifier = violation_data['identifier']

        self._increment_violation_count(identifier)

        violation_count = violation_data['violation_count'] + 1

        if violation_count >= self.auto_block_threshold:
            self._auto_block_ip(client_ip, violation_count, violation_data)

        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None

        security_logger.warning(
            f"Rate limit violation on {request.path}",
            extra={
                'correlation_id': correlation_id,
                'client_ip': client_ip,
                'user_id': user_id,
                'endpoint_type': violation_data['endpoint_type'],
                'violation_reason': violation_data['reason'],
                'current_requests': violation_data['current'],
                'limit': violation_data['limit'],
                'total_violations': violation_count,
                'backoff_seconds': violation_data['backoff_seconds']
            }
        )

        self._log_violation_to_database(request, client_ip, violation_data, correlation_id)

    def _auto_block_ip(self, client_ip: str, violation_count: int, violation_data: Dict[str, Any]):
        """Automatically block IP after threshold violations."""
        block_key = f"{self.block_cache_prefix}:{client_ip}"

        block_duration_hours = min(violation_count - self.auto_block_threshold + 1, self.max_backoff_hours)
        block_duration_seconds = block_duration_hours * 3600
        blocked_until_timestamp = time.time() + block_duration_seconds

        block_data = {
            'blocked_at': time.time(),
            'blocked_until': blocked_until_timestamp,
            'violation_count': violation_count,
            'block_duration_hours': block_duration_hours
        }

        cache.set(block_key, block_data, block_duration_seconds)

        try:
            from apps.core.models.rate_limiting import RateLimitBlockedIP

            blocked_until_dt = django_tz.now() + timedelta(hours=block_duration_hours)

            RateLimitBlockedIP.objects.create(
                ip_address=client_ip,
                blocked_until=blocked_until_dt,
                violation_count=violation_count,
                endpoint_type=violation_data.get('endpoint_type', 'unknown'),
                last_violation_path=violation_data.get('path', ''),
                reason=f'Automatic block after {violation_count} violations. Block duration: {block_duration_hours} hours.',
                is_active=True
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error persisting blocked IP: {str(e)}", exc_info=True, extra={'client_ip': client_ip})
        except (ValueError, KeyError) as e:
            logger.warning(f"Invalid data for blocked IP record: {str(e)}", extra={'client_ip': client_ip})

        security_logger.critical(
            f"IP automatically blocked: {client_ip}",
            extra={
                'client_ip': client_ip,
                'violation_count': violation_count,
                'block_duration_hours': block_duration_hours,
                'blocked_until': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(blocked_until_timestamp))
            }
        )

    def _log_violation_to_database(
        self,
        request: HttpRequest,
        client_ip: str,
        violation_data: Dict[str, Any],
        correlation_id: str
    ):
        """Persist violation to database for analytics."""
        try:
            from apps.core.models.rate_limiting import RateLimitViolationLog

            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None

            RateLimitViolationLog.objects.create(
                client_ip=client_ip,
                user=user,
                endpoint_path=request.path,
                endpoint_type=violation_data['endpoint_type'],
                violation_reason=violation_data['reason'],
                request_count=violation_data['current'],
                rate_limit=violation_data['limit'],
                correlation_id=correlation_id,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error logging violation: {str(e)}", exc_info=True, extra={'correlation_id': correlation_id})
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Invalid violation log data: {str(e)}", extra={'correlation_id': correlation_id})

    def _create_rate_limit_response(
        self,
        request: HttpRequest,
        violation_data: Dict[str, Any],
        correlation_id: str
    ) -> HttpResponse:
        """Create appropriate rate limit response based on request type."""
        is_api = request.path.startswith('/api/') or request.path.startswith('/graphql')
        is_htmx = request.META.get('HTTP_HX_REQUEST') == 'true'

        retry_after = violation_data['backoff_seconds']

        if is_api:
            response = JsonResponse({
                'error': {
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'message': self._get_rate_limit_message(violation_data),
                    'correlation_id': correlation_id,
                    'retry_after_seconds': retry_after,
                    'endpoint_type': violation_data['endpoint_type']
                }
            }, status=429)
        elif is_htmx:
            response = HttpResponse(
                f'<div class="alert alert-warning">'
                f'Too many requests. Please wait {retry_after // 60} minutes and try again.'
                f'</div>',
                status=429
            )
        else:
            try:
                response = render(request, 'errors/429.html', {
                    'retry_after_minutes': retry_after // 60,
                    'endpoint_type': violation_data['endpoint_type'],
                    'correlation_id': correlation_id
                }, status=429)
            except (TemplateDoesNotExist, TemplateSyntaxError) as e:
                logger.warning(f"Template error for 429 page: {str(e)}", extra={'correlation_id': correlation_id})
                response = HttpResponse(
                    f'Rate limit exceeded. Please wait {retry_after // 60} minutes.',
                    status=429
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Template context error for 429 page: {str(e)}", extra={'correlation_id': correlation_id})
                response = HttpResponse(
                    f'Rate limit exceeded. Please wait {retry_after // 60} minutes.',
                    status=429
                )

        response['Retry-After'] = str(retry_after)
        response['X-RateLimit-Limit'] = str(violation_data['limit'])
        response['X-RateLimit-Remaining'] = '0'
        response['X-RateLimit-Reset'] = str(int(time.time() + retry_after))
        response['X-RateLimit-Endpoint'] = violation_data['endpoint_type']

        return response

    def _create_blocked_response(
        self,
        request: HttpRequest,
        correlation_id: str,
        client_ip: str
    ) -> HttpResponse:
        """Create response for blocked IPs."""
        block_key = f"{self.block_cache_prefix}:{client_ip}"
        block_data = cache.get(block_key, {})

        blocked_until = block_data.get('blocked_until', time.time())
        remaining_seconds = int(blocked_until - time.time())

        security_logger.error(
            f"Blocked IP attempted access: {client_ip}",
            extra={
                'correlation_id': correlation_id,
                'client_ip': client_ip,
                'path': request.path,
                'remaining_block_seconds': remaining_seconds
            }
        )

        is_api = request.path.startswith('/api/') or request.path.startswith('/graphql')

        if is_api:
            return JsonResponse({
                'error': {
                    'code': 'IP_BLOCKED',
                    'message': f'Your IP has been blocked due to excessive violations. Block expires in {remaining_seconds // 3600} hours.',
                    'correlation_id': correlation_id,
                    'blocked_until': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(blocked_until))
                }
            }, status=403)
        else:
            return HttpResponse(
                f'<h1>Access Blocked</h1>'
                f'<p>Your IP has been temporarily blocked due to excessive rate limit violations.</p>'
                f'<p>Block expires in {remaining_seconds // 3600} hours.</p>'
                f'<p>Correlation ID: {correlation_id}</p>',
                status=403
            )

    def _get_rate_limit_message(self, violation_data: Dict[str, Any]) -> str:
        """Generate user-friendly rate limit message."""
        endpoint_type = violation_data['endpoint_type']
        limit = violation_data['limit']
        window_minutes = violation_data['window_seconds'] // 60

        messages = {
            'admin': f'Too many admin login attempts. Limit: {limit} per {window_minutes} minutes.',
            'auth': f'Too many authentication attempts. Limit: {limit} per {window_minutes} minutes.',
            'api': f'API rate limit exceeded. Limit: {limit} per {window_minutes} minutes.',
            'graphql': f'GraphQL rate limit exceeded. Limit: {limit} per {window_minutes} minutes.',
            'default': f'Rate limit exceeded. Limit: {limit} per {window_minutes} minutes.'
        }

        return messages.get(endpoint_type, messages['default'])


class RateLimitMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to collect rate limiting metrics for monitoring dashboard.

    Tracks:
    - Total rate limit violations per hour
    - Top violating IPs
    - Most targeted endpoints
    - Violation trends
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.metrics_cache_prefix = 'rate_limit_metrics'
        self.metrics_window = 3600

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Track rate limiting metrics from response."""
        if response.status_code == 429:
            self._record_violation_metrics(request, response)

        return response

    def _record_violation_metrics(self, request: HttpRequest, response: HttpResponse):
        """Record metrics for rate limit violation."""
        try:
            timestamp_hour = int(time.time() // 3600) * 3600

            violations_key = f"{self.metrics_cache_prefix}:violations:{timestamp_hour}"
            current_violations = cache.get(violations_key, 0)
            cache.set(violations_key, current_violations + 1, self.metrics_window)

            client_ip = self._get_client_ip(request)
            ip_violations_key = f"{self.metrics_cache_prefix}:ip_violations:{client_ip}"
            ip_violations = cache.get(ip_violations_key, 0)
            cache.set(ip_violations_key, ip_violations + 1, self.metrics_window)

            endpoint_violations_key = f"{self.metrics_cache_prefix}:endpoint:{request.path}:{timestamp_hour}"
            endpoint_violations = cache.get(endpoint_violations_key, 0)
            cache.set(endpoint_violations_key, endpoint_violations + 1, self.metrics_window)

        except ConnectionError as e:
            logger.warning(f"Cache unavailable for metrics recording: {str(e)}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid metrics data: {str(e)}")

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


__all__ = [
    'PathBasedRateLimitMiddleware',
    'RateLimitMonitoringMiddleware',
]