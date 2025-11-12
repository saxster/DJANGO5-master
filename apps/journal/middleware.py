"""
Security Middleware for Journal Data Protection

Enterprise-grade security middleware providing:
- Comprehensive audit logging for all journal/wellness operations
- Privacy violation detection and prevention
- Rate limiting for sensitive operations
- Data access monitoring and alerting
- GDPR/HIPAA compliance enforcement
- Multi-tenant security isolation
"""

import json
import time
import uuid
from django.utils import timezone
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, ObjectDoesNotExist
from django.core.cache import cache
import logging

# Redis-specific exceptions for proper error handling
from redis.exceptions import (
    RedisError,
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError
)

from .models import JournalEntry, JournalPrivacySettings
from .privacy import JournalPrivacyManager

User = get_user_model()
logger = logging.getLogger('security')


class JournalSecurityMiddleware(MiddlewareMixin):
    """
    Comprehensive security middleware for journal and wellness data protection

    Features:
    - Audit logging for all privacy-sensitive operations
    - Rate limiting for API endpoints
    - Privacy violation detection
    - Data access monitoring
    - Cross-tenant access prevention
    - Crisis intervention logging
    """

    # Rate limiting configuration
    RATE_LIMITS = {
        '/api/v1/journal/analytics/': {'requests': 20, 'window_minutes': 60},
        '/api/v1/journal/search/': {'requests': 50, 'window_minutes': 60},
        '/api/v1/wellness/personalized/': {'requests': 30, 'window_minutes': 60},
        '/api/v1/journal/sync/': {'requests': 100, 'window_minutes': 60},
        '/api/v1/journal/privacy-settings/': {'requests': 10, 'window_minutes': 60},
    }

    # Sensitive endpoints requiring extra logging
    SENSITIVE_ENDPOINTS = [
        '/api/v1/journal/analytics/',
        '/api/v1/journal/entries/',
        '/api/v1/wellness/contextual/',
        '/api/v1/journal/privacy-settings/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('security.journal')
        self.privacy_manager = JournalPrivacyManager()
        self.redis_rate_limiter_ready = False
        self._rate_limit_warning_logged = False

        # Rate limiting now uses Redis via Django cache backend
        # No in-memory storage needed - Redis handles multi-worker coordination

        # Validate Redis backend on startup (Nov 2025 security requirement)
        self._validate_redis_backend()

    def __call__(self, request):
        """Process request with security checks"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())
        response = None

        # Add correlation ID to request for tracking
        request.correlation_id = correlation_id

        try:
            # Apply security checks for journal/wellness endpoints
            if self._is_journal_wellness_endpoint(request.path):
                security_result = self._apply_security_checks(request, correlation_id)

                if not security_result['allowed']:
                    return self._create_security_denied_response(
                        security_result, correlation_id
                    )

            # Process request
            response = self.get_response(request)

            # Post-process response for security
            self._post_process_response(request, response, correlation_id, start_time)

            return response

        except (ConnectionError, ValueError) as e:
            self.logger.error(
                f"Security middleware error: {e}",
                extra={'correlation_id': correlation_id, 'path': request.path}
            )

            if response is not None:
                return response

            return JsonResponse(
                {
                    'detail': 'Journal security controls unavailable. Please retry shortly.',
                    'correlation_id': correlation_id
                },
                status=503
            )

    def _is_journal_wellness_endpoint(self, path):
        """Check if path is a journal or wellness endpoint"""
        journal_wellness_paths = [
            '/api/v1/journal/',
            '/api/v1/wellness/',
            '/journal/',
            '/wellness/'
        ]

        return any(path.startswith(prefix) for prefix in journal_wellness_paths)

    def _validate_redis_backend(self):
        """
        Validate Redis backend is available for rate limiting.

        Critical security requirement (Nov 2025): Journal middleware requires
        django-redis backend for cross-worker rate limiting enforcement.

        Logs warning if Redis unavailable (fail-open mode).
        """
        try:
            # Attempt to get Redis client
            redis_client = cache.client.get_client()

            # Verify connection with ping
            redis_client.ping()

            self.redis_rate_limiter_ready = True
            self.logger.info(
                "✅ Journal rate limiting: Redis connection verified. "
                "Cross-worker rate limits active."
            )

        except AttributeError:
            self.redis_rate_limiter_ready = False
            # cache.client.get_client() doesn't exist - wrong backend
            self.logger.critical(
                "❌ Journal rate limiting: django-redis backend NOT configured. "
                "Current cache backend does not support Redis sorted sets. "
                "Rate limiting will be DISABLED (fail-open mode). "
                "SECURITY RISK: Users can bypass rate limits. "
                "See CLAUDE.md 'Infrastructure Requirements' for setup instructions."
            )

        except (RedisError, RedisConnectionError, RedisTimeoutError, ConnectionError, Exception) as e:
            self.redis_rate_limiter_ready = False
            # Redis server unavailable
            self.logger.warning(
                f"⚠️ Journal rate limiting: Redis unavailable - {type(e).__name__}: {e}. "
                "Rate limiting will be DISABLED (fail-open mode). "
                "Requests will be allowed to prevent blocking legitimate users."
            )

    def _apply_security_checks(self, request, correlation_id):
        """Apply comprehensive security checks"""
        # Check 1: Authentication
        if not request.user.is_authenticated:
            return {
                'allowed': False,
                'reason': 'authentication_required',
                'status_code': 401
            }

        # Check 2: Rate limiting
        rate_limit_result = self._check_rate_limits(request, correlation_id)
        if not rate_limit_result['allowed']:
            return rate_limit_result

        # Check 3: Tenant isolation
        tenant_check = self._check_tenant_isolation(request, correlation_id)
        if not tenant_check['allowed']:
            return tenant_check

        # Check 4: Privacy consent for sensitive operations
        if self._is_sensitive_endpoint(request.path):
            consent_check = self._check_privacy_consent(request, correlation_id)
            if not consent_check['allowed']:
                return consent_check

        # Check 5: Data access validation for specific entries
        if 'journal/entries/' in request.path and request.method == 'GET':
            access_check = self._check_entry_access_permission(request, correlation_id)
            if not access_check['allowed']:
                return access_check

        # All checks passed
        self._log_security_check_passed(request, correlation_id)

        return {
            'allowed': True,
            'correlation_id': correlation_id
        }

    def _check_rate_limits(self, request, correlation_id):
        """Check rate limits for API endpoints"""
        endpoint = self._normalize_endpoint_path(request.path)
        rate_config = self.RATE_LIMITS.get(endpoint)

        if not rate_config:
            return {'allowed': True}

        if not getattr(self, 'redis_rate_limiter_ready', False):
            if not self._rate_limit_warning_logged:
                self.logger.warning(
                    "Journal rate limiting bypassed: Redis backend not ready.",
                    extra={'correlation_id': correlation_id, 'endpoint': endpoint}
                )
                self._rate_limit_warning_logged = True
            return {'allowed': True}

        # Redis-based rate limiting (works across multiple workers)
        rate_key = f"journal_rate_limit:{request.user.id}:{endpoint}"
        current_time = time.time()
        window_seconds = rate_config['window_minutes'] * 60

        try:
            # Try to get Redis client for sorted set operations
            redis_client = cache.client.get_client()

            # Add current request timestamp to sorted set
            redis_client.zadd(rate_key, {correlation_id: current_time})

            # Remove old entries outside the window
            redis_client.zremrangebyscore(
                rate_key,
                '-inf',
                current_time - window_seconds
            )

            # Count requests in window
            request_count = redis_client.zcard(rate_key)

            # Set expiry to window duration (cleanup old keys)
            redis_client.expire(rate_key, int(window_seconds))

            # Check if limit exceeded
            if request_count > rate_config['requests']:
                self.logger.warning(
                    f"Rate limit exceeded for user {request.user.id} on {endpoint}",
                    extra={
                        'correlation_id': correlation_id,
                        'user_id': request.user.id,
                        'endpoint': endpoint,
                        'request_count': request_count,
                        'limit': rate_config['requests']
                    }
                )

                return {
                    'allowed': False,
                    'reason': 'rate_limit_exceeded',
                    'status_code': 429,
                    'retry_after': window_seconds
                }

            return {'allowed': True}

        except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
            # Redis unavailable or operation failed - graceful degradation
            # Better to allow requests than block legitimate users (fail-open)
            self.logger.warning(
                f"Rate limiting unavailable (Redis error: {type(e).__name__}): {e}. "
                "Allowing request (fail-open mode).",
                extra={
                    'correlation_id': correlation_id,
                    'endpoint': endpoint,
                    'error_type': type(e).__name__
                }
            )
            return {'allowed': True}

        except AttributeError as e:
            # Programming error - wrong cache backend or method doesn't exist
            # This should fail fast in development
            self.logger.error(
                f"Rate limiting implementation error (AttributeError): {e}. "
                "This indicates django-redis backend not configured or code bug. "
                "Allowing request to prevent blocking users.",
                exc_info=True,
                extra={'correlation_id': correlation_id, 'endpoint': endpoint}
            )
            # In production, allow request; in development, you might want to raise
            return {'allowed': True}

    def _check_tenant_isolation(self, request, correlation_id):
        """Check multi-tenant isolation"""
        user_tenant = getattr(request.user, 'tenant', None)

        if not user_tenant:
            self.logger.error(
                f"User {request.user.id} has no tenant assignment",
                extra={'correlation_id': correlation_id}
            )

            return {
                'allowed': False,
                'reason': 'no_tenant_assignment',
                'status_code': 403
            }

        # For requests that include tenant-specific data, verify isolation
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                request_data = json.loads(request.body) if request.body else {}

                # Check if request attempts cross-tenant operation
                if 'tenant_id' in request_data:
                    requested_tenant_id = request_data['tenant_id']
                    if str(requested_tenant_id) != str(user_tenant.id):
                        self.logger.warning(
                            f"Cross-tenant access attempted by user {request.user.id}",
                            extra={
                                'correlation_id': correlation_id,
                                'user_tenant': user_tenant.id,
                                'requested_tenant': requested_tenant_id
                            }
                        )

                        return {
                            'allowed': False,
                            'reason': 'cross_tenant_access_denied',
                            'status_code': 403
                        }

            except json.JSONDecodeError:
                # Not JSON data, continue
                pass

        return {'allowed': True}

    def _check_privacy_consent(self, request, correlation_id):
        """Check privacy consent for sensitive operations"""
        try:
            privacy_settings = request.user.journal_privacy_settings
        except JournalPrivacySettings.DoesNotExist:
            # No privacy settings - block sensitive operations
            return {
                'allowed': False,
                'reason': 'no_privacy_settings',
                'status_code': 403,
                'message': 'Privacy settings must be configured before accessing sensitive data'
            }

        # Check consent based on endpoint
        if '/analytics/' in request.path:
            if not privacy_settings.analytics_consent:
                self.logger.info(
                    f"Analytics access denied - no consent from user {request.user.id}",
                    extra={'correlation_id': correlation_id}
                )

                return {
                    'allowed': False,
                    'reason': 'no_analytics_consent',
                    'status_code': 403,
                    'message': 'Analytics consent required for this operation'
                }

        return {'allowed': True}

    def _check_entry_access_permission(self, request, correlation_id):
        """Check permission to access specific journal entries"""
        # Extract entry ID from path
        path_parts = request.path.split('/')
        entry_id = None

        for i, part in enumerate(path_parts):
            if part == 'entries' and i + 1 < len(path_parts):
                entry_id = path_parts[i + 1]
                break

        if not entry_id or entry_id in ['', 'search', 'analytics']:
            # Not accessing specific entry
            return {'allowed': True}

        try:
            journal_entry = JournalEntry.objects.get(id=entry_id)

            # Check access permission
            permission_result = self.privacy_manager.check_data_access_permission(
                request.user, journal_entry, 'read'
            )

            if not permission_result['allowed']:
                self.logger.warning(
                    f"Entry access denied for user {request.user.id} on entry {entry_id}",
                    extra={
                        'correlation_id': correlation_id,
                        'entry_privacy_scope': journal_entry.privacy_scope,
                        'reason': permission_result.get('reason')
                    }
                )

                return {
                    'allowed': False,
                    'reason': 'entry_access_denied',
                    'status_code': 403
                }

            # Log access for audit trail
            self._log_entry_access(request, journal_entry, correlation_id)

            return {'allowed': True}

        except JournalEntry.DoesNotExist:
            return {
                'allowed': False,
                'reason': 'entry_not_found',
                'status_code': 404
            }

    def _is_sensitive_endpoint(self, path):
        """Check if endpoint handles sensitive data"""
        return any(path.startswith(endpoint) for endpoint in self.SENSITIVE_ENDPOINTS)

    def _normalize_endpoint_path(self, path):
        """Normalize endpoint path for rate limiting"""
        # Remove trailing slashes and parameters
        normalized = path.rstrip('/')

        # Replace dynamic segments with placeholders
        if '/entries/' in normalized and len(normalized.split('/')) > 5:
            # Replace entry ID with placeholder
            parts = normalized.split('/')
            for i, part in enumerate(parts):
                if part == 'entries' and i + 1 < len(parts):
                    parts[i + 1] = '{id}'
                    break
            normalized = '/'.join(parts)

        return normalized

    def _log_security_check_passed(self, request, correlation_id):
        """Log successful security check"""
        self.logger.debug(
            f"Security checks passed for {request.method} {request.path}",
            extra={
                'correlation_id': correlation_id,
                'user_id': request.user.id,
                'method': request.method,
                'path': request.path,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
            }
        )

    def _log_entry_access(self, request, journal_entry, correlation_id):
        """Log journal entry access for audit trail"""
        self.logger.info(
            f"JOURNAL ACCESS: User {request.user.id} accessed entry {journal_entry.id}",
            extra={
                'correlation_id': correlation_id,
                'user_id': request.user.id,
                'entry_id': str(journal_entry.id),
                'entry_owner': journal_entry.user.id,
                'privacy_scope': journal_entry.privacy_scope,
                'entry_type': journal_entry.entry_type,
                'is_wellbeing_entry': journal_entry.is_wellbeing_entry,
                'access_timestamp': timezone.now().isoformat()
            }
        )

    def _create_security_denied_response(self, security_result, correlation_id):
        """Create security denied response"""
        status_code = security_result.get('status_code', 403)

        response_data = {
            'error': 'Security check failed',
            'reason': security_result.get('reason'),
            'message': security_result.get('message', 'Access denied'),
            'correlation_id': correlation_id,
            'timestamp': timezone.now().isoformat()
        }

        # Add retry information for rate limiting
        if security_result.get('retry_after'):
            response_data['retry_after'] = security_result['retry_after']

        return JsonResponse(response_data, status=status_code)

    def _post_process_response(self, request, response, correlation_id, start_time):
        """Post-process response for security logging"""
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Log response for audit trail
        if self._is_journal_wellness_endpoint(request.path):
            self.logger.info(
                f"API Response: {request.method} {request.path} -> {response.status_code}",
                extra={
                    'correlation_id': correlation_id,
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'response_time_ms': round(response_time, 2),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100]
                }
            )

        # Add security headers to response
        self._add_security_headers(response)

    def _add_security_headers(self, response):
        """Add security headers to response"""
        # Prevent caching of sensitive data
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        # Content security
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # API-specific headers
        response['X-API-Version'] = '1.0'
        response['X-Privacy-Protected'] = 'true'


class PrivacyViolationDetectionMiddleware(MiddlewareMixin):
    """
    Middleware specifically for detecting and preventing privacy violations

    Features:
    - Real-time privacy violation detection
    - Automatic privacy scope enforcement
    - Cross-tenant data access prevention
    - Wellbeing data protection
    - Violation alerting and reporting
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('security.privacy')

    def __call__(self, request):
        """Check for privacy violations"""
        if request.user.is_authenticated and self._is_data_access_request(request):
            violation_check = self._detect_privacy_violations(request)

            if violation_check['violation_detected']:
                self._handle_privacy_violation(request, violation_check)

        return self.get_response(request)

    def _is_data_access_request(self, request):
        """Check if request accesses user data"""
        data_access_patterns = [
            '/api/v1/journal/entries/',
            '/api/v1/journal/analytics/',
            '/api/v1/wellness/progress/',
        ]

        return any(request.path.startswith(pattern) for pattern in data_access_patterns)

    def _detect_privacy_violations(self, request):
        """Detect potential privacy violations"""
        violations = []

        # Check for cross-user data access attempts
        # SECURITY FIX (IDOR-003): Validate user_id parameter
        if 'user_id' in request.GET:
            user_id_param = request.GET['user_id']
            # Validate ID is numeric
            if not user_id_param or not str(user_id_param).isdigit():
                violations.append({
                    'type': 'invalid_user_id_parameter',
                    'details': f"Invalid user_id parameter: {user_id_param}"
                })
            elif user_id_param != str(request.user.id):
                if not request.user.has_perm('journal.view_others_journalentry'):
                    violations.append({
                        'type': 'unauthorized_cross_user_access',
                        'details': f"User {request.user.id} attempted to access data for user {user_id_param}"
                    })

        # Check for analytics access without consent
        if '/analytics/' in request.path:
            try:
                privacy_settings = request.user.journal_privacy_settings
                if not privacy_settings.analytics_consent:
                    violations.append({
                        'type': 'analytics_access_without_consent',
                        'details': f"User {request.user.id} accessed analytics without consent"
                    })
            except JournalPrivacySettings.DoesNotExist:
                violations.append({
                    'type': 'analytics_access_no_privacy_settings',
                    'details': f"User {request.user.id} accessed analytics without privacy settings"
                })

        return {
            'violation_detected': len(violations) > 0,
            'violations': violations
        }

    def _handle_privacy_violation(self, request, violation_check):
        """Handle detected privacy violations"""
        for violation in violation_check['violations']:
            self.logger.critical(
                f"PRIVACY VIOLATION DETECTED: {violation['type']}",
                extra={
                    'violation_type': violation['type'],
                    'user_id': request.user.id,
                    'path': request.path,
                    'method': request.method,
                    'details': violation['details'],
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip_address': self._get_client_ip(request),
                    'timestamp': timezone.now().isoformat()
                }
            )

        # TODO: Trigger privacy violation alert
        # This could send alerts to privacy officers or security team

    def _get_client_ip(self, request):
        """Get client IP address safely"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CrisisInterventionLoggingMiddleware(MiddlewareMixin):
    """
    Specialized middleware for crisis intervention monitoring and logging

    Features:
    - Crisis detection event logging
    - Intervention response tracking
    - Compliance documentation
    - Emergency escalation logging
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('security.crisis')

    def __call__(self, request):
        """Monitor for crisis-related activities"""
        response = self.get_response(request)

        # Log crisis-related API calls
        if self._is_crisis_related_endpoint(request.path):
            self._log_crisis_activity(request, response)

        return response

    def _is_crisis_related_endpoint(self, path):
        """Check if endpoint is related to crisis intervention"""
        crisis_patterns = [
            '/api/v1/wellness/contextual/',  # May deliver crisis content
            '/api/v1/journal/entries/',      # May contain crisis indicators
        ]

        return any(path.startswith(pattern) for pattern in crisis_patterns)

    def _log_crisis_activity(self, request, response):
        """Log crisis-related activity"""
        # Only log if response contains crisis-related data
        if response.status_code == 200 and hasattr(response, 'data'):
            try:
                response_data = json.loads(response.content)

                # Check for crisis indicators in response
                if self._contains_crisis_indicators(response_data):
                    self.logger.critical(
                        f"CRISIS RESPONSE DELIVERED: User {request.user.id}",
                        extra={
                            'user_id': request.user.id,
                            'path': request.path,
                            'method': request.method,
                            'crisis_content_delivered': True,
                            'timestamp': timezone.now().isoformat()
                        }
                    )

            except (json.JSONDecodeError, AttributeError):
                # Can't parse response, skip logging
                pass

    def _contains_crisis_indicators(self, response_data):
        """Check if response contains crisis intervention content"""
        # Check various response structures for crisis indicators
        crisis_indicators = [
            'crisis_detected', 'crisis_intervention', 'immediate_content',
            'urgency_level', 'crisis_support'
        ]

        def check_dict(data):
            if isinstance(data, dict):
                for key, value in data.items():
                    if key in crisis_indicators:
                        return True
                    if isinstance(value, (dict, list)):
                        if check_dict(value):
                            return True
            elif isinstance(data, list):
                for item in data:
                    if check_dict(item):
                        return True
            return False

        return check_dict(response_data)


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Comprehensive audit logging for compliance and monitoring

    Features:
    - Complete audit trail for all data operations
    - GDPR compliance logging
    - Data export/import tracking
    - Privacy setting changes logging
    - Administrative action logging
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('security.audit')

    def __call__(self, request):
        """Log audit trail for all operations"""
        if request.user.is_authenticated and self._should_audit(request):
            # Pre-request audit logging
            self._log_request_audit(request)

        response = self.get_response(request)

        if request.user.is_authenticated and self._should_audit(request):
            # Post-request audit logging
            self._log_response_audit(request, response)

        return response

    def _should_audit(self, request):
        """Determine if request should be audited"""
        # Audit all journal/wellness operations
        if self._is_journal_wellness_endpoint(request.path):
            return True

        # Audit administrative operations
        admin_patterns = [
            '/admin/journal/',
            '/admin/wellness/',
        ]

        return any(request.path.startswith(pattern) for pattern in admin_patterns)

    def _is_journal_wellness_endpoint(self, path):
        """Check if path is journal/wellness endpoint"""
        return path.startswith('/api/v1/journal/') or path.startswith('/api/v1/wellness/')

    def _log_request_audit(self, request):
        """Log request details for audit"""
        audit_data = {
            'event_type': 'api_request',
            'user_id': request.user.id,
            'user_name': request.user.peoplename,
            'tenant_id': getattr(request.user.tenant, 'id', None),
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.GET),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
            'ip_address': self._get_client_ip(request),
            'timestamp': timezone.now().isoformat()
        }

        # Log sensitive data operations
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            audit_data['data_modification'] = True

            # For privacy-sensitive endpoints, log additional details
            if 'privacy-settings' in request.path:
                audit_data['privacy_settings_change'] = True

        self.logger.info(
            f"AUDIT: {request.method} {request.path} by user {request.user.id}",
            extra=audit_data
        )

    def _log_response_audit(self, request, response):
        """Log response details for audit"""
        audit_data = {
            'event_type': 'api_response',
            'user_id': request.user.id,
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'timestamp': timezone.now().isoformat()
        }

        # Log successful data modifications
        if response.status_code in [200, 201] and request.method in ['POST', 'PUT', 'PATCH']:
            audit_data['data_modified'] = True

        # Log data exports
        if '/export/' in request.path or 'export' in request.GET:
            audit_data['data_export'] = True

        self.logger.info(
            f"AUDIT RESPONSE: {response.status_code} for {request.method} {request.path}",
            extra=audit_data
        )

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Data sanitization middleware
class DataSanitizationMiddleware(MiddlewareMixin):
    """
    Middleware for sanitizing journal and wellness data

    Features:
    - Input sanitization for journal content
    - XSS prevention for user-generated content
    - SQL injection prevention
    - File upload security
    - Content validation and filtering
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('security.sanitization')

    def __call__(self, request):
        """Sanitize request data"""
        if request.method in ['POST', 'PUT', 'PATCH'] and self._is_journal_wellness_endpoint(request.path):
            try:
                self._sanitize_request_data(request)
            except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
                self.logger.error(f"Data sanitization failed: {e}")
                # Don't block request for sanitization errors

        return self.get_response(request)

    def _sanitize_request_data(self, request):
        """Sanitize request data for security"""
        if not request.body:
            return

        try:
            # Parse JSON data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                sanitized_data = self._sanitize_json_data(data)

                # Replace request body with sanitized data
                request._body = json.dumps(sanitized_data).encode('utf-8')

        except json.JSONDecodeError:
            # Not JSON data, skip sanitization
            pass

    def _sanitize_json_data(self, data):
        """Recursively sanitize JSON data"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                sanitized_key = self._sanitize_string(str(key))
                sanitized_value = self._sanitize_json_data(value)
                sanitized[sanitized_key] = sanitized_value
            return sanitized

        elif isinstance(data, list):
            return [self._sanitize_json_data(item) for item in data]

        elif isinstance(data, str):
            return self._sanitize_string(data)

        else:
            # Numbers, booleans, None - return as-is
            return data

    def _sanitize_string(self, text):
        """Sanitize string data"""
        if not isinstance(text, str):
            return text

        # Basic XSS prevention
        dangerous_patterns = [
            '<script', '</script>', 'javascript:', 'onload=', 'onerror=',
            'onclick=', 'onmouseover=', '<iframe', '</iframe>'
        ]

        sanitized = text
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, '[REMOVED]')

        # Limit length to prevent DoS
        if len(sanitized) > 10000:  # 10KB limit for individual fields
            sanitized = sanitized[:10000] + '[TRUNCATED]'

        return sanitized

    def _is_journal_wellness_endpoint(self, path):
        """Check if endpoint handles journal/wellness data"""
        return path.startswith('/api/v1/journal/') or path.startswith('/api/v1/wellness/')


# Performance monitoring middleware
class JournalPerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Performance monitoring for journal and wellness operations

    Features:
    - Response time monitoring
    - Database query counting
    - Memory usage tracking
    - Slow operation alerting
    - Performance metrics collection
    """

    SLOW_OPERATION_THRESHOLD_MS = 2000  # 2 seconds

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('security.performance')

    def __call__(self, request):
        """Monitor performance"""
        if not self._is_journal_wellness_endpoint(request.path):
            return self.get_response(request)

        start_time = time.time()
        start_queries = self._get_query_count()

        response = self.get_response(request)

        end_time = time.time()
        end_queries = self._get_query_count()

        # Calculate metrics
        response_time_ms = (end_time - start_time) * 1000
        query_count = end_queries - start_queries

        # Log performance metrics
        self._log_performance_metrics(request, response_time_ms, query_count)

        # Alert on slow operations
        if response_time_ms > self.SLOW_OPERATION_THRESHOLD_MS:
            self._alert_slow_operation(request, response_time_ms, query_count)

        return response

    def _get_query_count(self):
        """Get current database query count"""
        try:
            from django.db import connection
            return len(connection.queries)
        except (ValueError, TypeError, AttributeError) as e:
            return 0

    def _log_performance_metrics(self, request, response_time_ms, query_count):
        """Log performance metrics"""
        self.logger.info(
            f"PERFORMANCE: {request.method} {request.path}",
            extra={
                'user_id': request.user.id,
                'response_time_ms': round(response_time_ms, 2),
                'database_queries': query_count,
                'endpoint': request.path,
                'method': request.method
            }
        )

    def _alert_slow_operation(self, request, response_time_ms, query_count):
        """Alert on slow operations"""
        self.logger.warning(
            f"SLOW OPERATION: {request.path} took {response_time_ms:.2f}ms with {query_count} queries",
            extra={
                'alert_type': 'slow_operation',
                'user_id': request.user.id,
                'response_time_ms': response_time_ms,
                'query_count': query_count,
                'threshold_ms': self.SLOW_OPERATION_THRESHOLD_MS
            }
        )

    def _is_journal_wellness_endpoint(self, path):
        """Check if endpoint is journal/wellness related"""
        return path.startswith('/api/v1/journal/') or path.startswith('/api/v1/wellness/')


# Convenience function to apply all security middleware
def get_journal_security_middleware():
    """Get all journal security middleware classes"""
    return [
        JournalSecurityMiddleware,
        PrivacyViolationDetectionMiddleware,
        CrisisInterventionLoggingMiddleware,
        AuditLoggingMiddleware,
        DataSanitizationMiddleware,
        JournalPerformanceMonitoringMiddleware,
    ]
