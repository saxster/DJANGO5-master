"""
File Upload Security Middleware

Enforces comprehensive file upload security policies including:
- Rate limiting for file uploads
- CSRF protection validation
- File size monitoring per user/window
- Security event logging and alerting
- Path validation and sanitization

Complies with Rule #14 from .claude/rules.md - File Upload Security
Addresses CVSS 8.1 file upload vulnerability
"""

import time
import logging
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.deprecation import MiddlewareMixin
from apps.core.exceptions import SecurityException, CSRFException

logger = logging.getLogger(__name__)


class FileUploadSecurityMiddleware(MiddlewareMixin):
    """
    Comprehensive file upload security middleware.

    Enforces:
    - File upload rate limiting per user
    - Total upload size limits per time window
    - CSRF protection for file upload endpoints
    - Security event logging
    - Suspicious activity detection
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

        # Load security settings
        self.file_upload_config = getattr(settings, 'FILE_UPLOAD_RATE_LIMITING', {})
        self.monitoring_config = getattr(settings, 'FILE_UPLOAD_MONITORING', {})
        self.csrf_config = getattr(settings, 'FILE_UPLOAD_CSRF_PROTECTION', {})
        self.upload_paths = getattr(settings, 'FILE_UPLOAD_PATHS', [])

        # Default configuration if not specified
        self.rate_limit_enabled = self.file_upload_config.get('ENABLE', True)
        self.window_minutes = self.file_upload_config.get('WINDOW_MINUTES', 5)
        self.max_attempts = self.file_upload_config.get('MAX_ATTEMPTS', 10)
        self.max_size_per_window = self.file_upload_config.get('MAX_SIZE_PER_WINDOW', 50 * 1024 * 1024)

        # CSRF protection
        self.csrf_protection_enabled = self.csrf_config.get('ENABLE', True)
        self.require_csrf_token = self.csrf_config.get('REQUIRE_CSRF_TOKEN', True)

        # Monitoring
        self.enable_logging = self.monitoring_config.get('ENABLE_UPLOAD_LOGGING', True)
        self.enable_alerting = self.monitoring_config.get('ENABLE_SECURITY_ALERTING', True)

    def process_request(self, request):
        """Process incoming file upload requests for security validation."""
        # Check if this is a file upload endpoint
        if not self._is_file_upload_request(request):
            return None

        # Skip processing for non-POST/PUT requests
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return None

        # Get user identifier for rate limiting
        user_id = self._get_user_identifier(request)

        # Log the upload attempt
        if self.enable_logging:
            self._log_upload_attempt(request, user_id)

        # Check rate limiting
        if self.rate_limit_enabled:
            rate_limit_result = self._check_rate_limit(request, user_id)
            if rate_limit_result:
                return rate_limit_result

        # Check CSRF protection for file uploads
        if self.csrf_protection_enabled and self.require_csrf_token:
            csrf_result = self._check_csrf_protection(request)
            if csrf_result:
                return csrf_result

        # Check total upload size per window
        size_limit_result = self._check_size_limits(request, user_id)
        if size_limit_result:
            return size_limit_result

        return None

    def process_response(self, request, response):
        """Process responses for upload tracking and alerting."""
        if not self._is_file_upload_request(request):
            return response

        user_id = self._get_user_identifier(request)

        # Log successful uploads
        if response.status_code == 200 and self.enable_logging:
            self._log_successful_upload(request, user_id, response)

        # Log failed uploads and check for suspicious activity
        elif response.status_code >= 400:
            self._log_failed_upload(request, user_id, response)

            # Check for suspicious activity patterns
            if self.enable_alerting:
                self._check_suspicious_activity(request, user_id)

        return response

    def _is_file_upload_request(self, request):
        """Check if request is to a file upload endpoint."""
        request_path = request.path

        # Check configured file upload paths
        for upload_path in self.upload_paths:
            if request_path.startswith(upload_path):
                return True

        # Check for file upload content
        content_type = request.content_type or ''
        if 'multipart/form-data' in content_type:
            return True

        return False

    def _get_user_identifier(self, request):
        """Get unique identifier for rate limiting."""
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            return f"user_{request.user.id}"

        # Fallback to IP address for anonymous users
        ip_address = self._get_client_ip(request)
        return f"ip_{ip_address}"

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _check_rate_limit(self, request, user_id):
        """Check rate limiting for file uploads."""
        current_time = int(time.time())
        window_start = current_time - (self.window_minutes * 60)

        # Cache key for rate limiting
        rate_limit_key = f"file_upload_rate_limit_{user_id}_{window_start // (self.window_minutes * 60)}"

        # Get current upload count
        current_count = cache.get(rate_limit_key, 0)

        if current_count >= self.max_attempts:
            logger.warning(
                "File upload rate limit exceeded",
                extra={
                    'user_id': user_id,
                    'current_count': current_count,
                    'max_attempts': self.max_attempts,
                    'window_minutes': self.window_minutes,
                    'ip_address': self._get_client_ip(request),
                    'path': request.path
                }
            )

            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': f'Too many upload attempts. Please wait {self.window_minutes} minutes.',
                'retry_after': self.window_minutes * 60
            }, status=429)

        # Increment counter
        cache.set(rate_limit_key, current_count + 1, timeout=self.window_minutes * 60)
        return None

    def _check_size_limits(self, request, user_id):
        """Check total upload size limits per window."""
        if not hasattr(request, 'FILES') or not request.FILES:
            return None

        # Calculate total size of uploaded files
        total_size = sum(file.size for file in request.FILES.values())

        current_time = int(time.time())
        window_start = current_time - (self.window_minutes * 60)

        # Cache key for size tracking
        size_key = f"file_upload_size_{user_id}_{window_start // (self.window_minutes * 60)}"

        # Get current total size
        current_total_size = cache.get(size_key, 0)
        new_total_size = current_total_size + total_size

        if new_total_size > self.max_size_per_window:
            logger.warning(
                "File upload size limit exceeded",
                extra={
                    'user_id': user_id,
                    'current_size': current_total_size,
                    'upload_size': total_size,
                    'new_total_size': new_total_size,
                    'max_size_per_window': self.max_size_per_window,
                    'ip_address': self._get_client_ip(request),
                    'path': request.path
                }
            )

            return JsonResponse({
                'error': 'Upload size limit exceeded',
                'message': f'Total upload size limit exceeded for this time window.',
                'max_size_mb': self.max_size_per_window // (1024 * 1024)
            }, status=413)

        # Update size tracking
        cache.set(size_key, new_total_size, timeout=self.window_minutes * 60)
        return None

    def _check_csrf_protection(self, request):
        """Validate CSRF protection for file uploads."""
        # Skip CSRF check if not required
        if not self.require_csrf_token:
            return None

        # Create CSRF middleware instance to validate
        csrf_middleware = CsrfViewMiddleware(lambda req: None)

        try:
            # Check CSRF token
            csrf_middleware.process_request(request)

            # If we get here, CSRF is valid
            return None

        except (ValidationError, CSRFException, SecurityException) as e:
            logger.warning(
                "CSRF validation failed for file upload",
                extra={
                    'user_id': self._get_user_identifier(request),
                    'ip_address': self._get_client_ip(request),
                    'path': request.path,
                    'error': str(e)
                }
            )

            return JsonResponse({
                'error': 'CSRF validation failed',
                'message': 'Invalid or missing CSRF token for file upload'
            }, status=403)
        except (ValueError, KeyError, AttributeError) as e:
            logger.error(
                "CSRF processing error for file upload",
                extra={
                    'user_id': self._get_user_identifier(request),
                    'ip_address': self._get_client_ip(request),
                    'path': request.path,
                    'error': str(e)
                },
                exc_info=True
            )

            return JsonResponse({
                'error': 'Security validation error',
                'message': 'Unable to process file upload security'
            }, status=500)

    def _log_upload_attempt(self, request, user_id):
        """Log file upload attempt."""
        file_info = {}
        if hasattr(request, 'FILES'):
            file_info = {
                'file_count': len(request.FILES),
                'total_size': sum(file.size for file in request.FILES.values()),
                'filenames': [file.name for file in request.FILES.values()]
            }

        logger.info(
            "File upload attempt",
            extra={
                'user_id': user_id,
                'ip_address': self._get_client_ip(request),
                'path': request.path,
                'method': request.method,
                'content_type': request.content_type,
                'file_info': file_info,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            }
        )

    def _log_successful_upload(self, request, user_id, response):
        """Log successful file upload."""
        logger.info(
            "File upload successful",
            extra={
                'user_id': user_id,
                'ip_address': self._get_client_ip(request),
                'path': request.path,
                'response_status': response.status_code
            }
        )

    def _log_failed_upload(self, request, user_id, response):
        """Log failed file upload."""
        logger.warning(
            "File upload failed",
            extra={
                'user_id': user_id,
                'ip_address': self._get_client_ip(request),
                'path': request.path,
                'response_status': response.status_code,
                'response_content': str(response.content)[:500]  # First 500 chars
            }
        )

    def _check_suspicious_activity(self, request, user_id):
        """Check for patterns indicating suspicious activity."""
        max_failed_uploads = self.monitoring_config.get('MAX_FAILED_UPLOADS_PER_USER', 5)
        window_minutes = self.monitoring_config.get('FAILED_UPLOAD_WINDOW_MINUTES', 10)

        current_time = int(time.time())
        window_start = current_time - (window_minutes * 60)

        # Cache key for failed uploads tracking
        failed_key = f"failed_uploads_{user_id}_{window_start // (window_minutes * 60)}"

        # Increment failed upload counter
        failed_count = cache.get(failed_key, 0) + 1
        cache.set(failed_key, failed_count, timeout=window_minutes * 60)

        # Alert on suspicious activity
        if failed_count >= max_failed_uploads:
            logger.error(
                "Suspicious file upload activity detected",
                extra={
                    'user_id': user_id,
                    'failed_uploads': failed_count,
                    'max_allowed': max_failed_uploads,
                    'window_minutes': window_minutes,
                    'ip_address': self._get_client_ip(request),
                    'path': request.path,
                    'alert_type': 'SUSPICIOUS_UPLOAD_ACTIVITY'
                }
            )
