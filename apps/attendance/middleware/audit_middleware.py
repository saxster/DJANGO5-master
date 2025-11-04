"""
Attendance Audit Logging Middleware

Automatically logs all access to attendance-related endpoints for compliance.

Captures:
- Who accessed what attendance data
- When and from where (IP, user agent)
- What action was performed
- How long it took
- Whether it succeeded or failed

Performance:
- Asynchronous logging (doesn't block request)
- Batch writes for high-traffic endpoints
- <50ms overhead target

Compliance:
- SOC 2 Type II: Complete audit trail
- ISO 27001: Access monitoring
- 6-year retention for regulatory compliance
"""

import logging
import time
from typing import Optional, Dict, Any
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.attendance.models.audit_log import AttendanceAccessLog
import re
import json

logger = logging.getLogger(__name__)
User = get_user_model()


class AttendanceAuditMiddleware(MiddlewareMixin):
    """
    Middleware to audit all attendance-related API access.

    This middleware intercepts requests to attendance endpoints and creates
    audit log entries with comprehensive information about the access.
    """

    # Patterns for endpoints that should be audited
    AUDIT_PATTERNS = [
        r'^/api/v[12]/attendance/',
        r'^/api/v[12]/assets/geofences/',
        r'^/attendance/',
    ]

    # Actions that should NOT be audited (health checks, metrics, etc.)
    SKIP_PATTERNS = [
        r'/health/?$',
        r'/metrics/?$',
        r'/api/docs/?',
    ]

    # Map HTTP methods to audit actions
    METHOD_TO_ACTION = {
        'GET': AttendanceAccessLog.Action.VIEW,
        'POST': AttendanceAccessLog.Action.CREATE,
        'PUT': AttendanceAccessLog.Action.UPDATE,
        'PATCH': AttendanceAccessLog.Action.UPDATE,
        'DELETE': AttendanceAccessLog.Action.DELETE,
    }

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

        # Compile regex patterns for efficiency
        self.audit_regex = [re.compile(pattern) for pattern in self.AUDIT_PATTERNS]
        self.skip_regex = [re.compile(pattern) for pattern in self.SKIP_PATTERNS]

    def should_audit(self, request) -> bool:
        """
        Determine if this request should be audited.

        Args:
            request: Django request object

        Returns:
            True if request should be audited, False otherwise
        """
        path = request.path

        # Skip certain paths
        for pattern in self.skip_regex:
            if pattern.search(path):
                return False

        # Check if path matches audit patterns
        for pattern in self.audit_regex:
            if pattern.search(path):
                return True

        return False

    def process_request(self, request):
        """
        Called before view processing.

        Attaches start time to request for duration calculation.
        """
        if self.should_audit(request):
            request._audit_start_time = time.time()

        return None

    def process_response(self, request, response):
        """
        Called after view processing.

        Creates audit log entry if applicable.
        """
        # Skip if not auditable
        if not self.should_audit(request):
            return response

        # Skip if audit logging disabled
        if not getattr(settings, 'ENABLE_ATTENDANCE_AUDIT_LOGGING', True):
            return response

        # Calculate duration
        duration_ms = None
        if hasattr(request, '_audit_start_time'):
            duration_seconds = time.time() - request._audit_start_time
            duration_ms = int(duration_seconds * 1000)

        # Extract audit data
        try:
            self._create_audit_log(request, response, duration_ms)
        except Exception as e:
            # Don't fail the request if audit logging fails
            logger.error(f"Failed to create audit log: {e}", exc_info=True)

        return response

    def _create_audit_log(self, request, response, duration_ms: Optional[int]):
        """
        Create an audit log entry for this request.

        Args:
            request: Django request object
            response: Django response object
            duration_ms: Duration of request in milliseconds
        """
        # Get user (may be None for anonymous requests)
        user = getattr(request, 'user', None)
        if user and not user.is_authenticated:
            user = None

        # Determine action based on method and path
        action = self._determine_action(request)

        # Extract attendance record ID if present
        attendance_record_id = self._extract_attendance_id(request.path)

        # Get impersonation info if applicable
        impersonated_by = getattr(request, 'impersonated_by', None)

        # Extract old/new values for updates
        old_values, new_values = self._extract_change_data(request, response)

        # Determine resource type
        resource_type = self._determine_resource_type(request.path)

        # Create audit log entry asynchronously (if celery available)
        if getattr(settings, 'CELERY_ENABLED', False):
            from apps.attendance.tasks.audit_tasks import create_audit_log_async
            create_audit_log_async.delay(
                user_id=user.id if user else None,
                action=action,
                attendance_record_id=attendance_record_id,
                resource_type=resource_type,
                request_data=self._serialize_request_data(request),
                duration_ms=duration_ms,
                status_code=response.status_code,
                old_values=old_values,
                new_values=new_values,
                impersonated_by_id=impersonated_by.id if impersonated_by else None,
            )
        else:
            # Synchronous logging if Celery not available
            AttendanceAccessLog.log_access(
                user=user,
                action=action,
                attendance_record_id=attendance_record_id,
                resource_type=resource_type,
                request=request,
                duration_ms=duration_ms,
                status_code=response.status_code,
                old_values=old_values,
                new_values=new_values,
                impersonated_by=impersonated_by,
            )

    def _determine_action(self, request) -> str:
        """
        Determine audit action based on HTTP method and path.

        Args:
            request: Django request object

        Returns:
            Action string from AttendanceAccessLog.Action choices
        """
        path = request.path
        method = request.method

        # Special actions based on path
        if '/approve/' in path:
            return AttendanceAccessLog.Action.APPROVE
        elif '/reject/' in path:
            return AttendanceAccessLog.Action.REJECT
        elif '/lock/' in path:
            return AttendanceAccessLog.Action.LOCK
        elif '/export/' in path:
            return AttendanceAccessLog.Action.EXPORT
        elif '/face-verify/' in path or '/clock-in/' in path or '/clock-out/' in path:
            return AttendanceAccessLog.Action.FACE_VERIFY
        elif '/validate/' in path and 'geofence' in path:
            return AttendanceAccessLog.Action.GPS_VALIDATE

        # Default to method-based action
        return self.METHOD_TO_ACTION.get(method, AttendanceAccessLog.Action.VIEW)

    def _extract_attendance_id(self, path: str) -> Optional[int]:
        """
        Extract attendance record ID from request path.

        Args:
            path: Request path

        Returns:
            Attendance record ID if found, None otherwise
        """
        # Pattern: /api/v1/attendance/123/ or /attendance/123/
        match = re.search(r'/attendance/(\d+)/', path)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass

        return None

    def _determine_resource_type(self, path: str) -> str:
        """
        Determine resource type from path.

        Args:
            path: Request path

        Returns:
            Resource type string
        """
        if '/geofence' in path:
            return AttendanceAccessLog.ResourceType.GEOFENCE
        elif '/photo' in path:
            return AttendanceAccessLog.ResourceType.ATTENDANCE_PHOTO
        elif '/audit' in path:
            return AttendanceAccessLog.ResourceType.AUDIT_LOG
        else:
            return AttendanceAccessLog.ResourceType.ATTENDANCE_RECORD

    def _extract_change_data(self, request, response) -> tuple:
        """
        Extract old and new values for update operations.

        Args:
            request: Django request object
            response: Django response object

        Returns:
            Tuple of (old_values, new_values) or (None, None)
        """
        # Only for update operations
        if request.method not in ['PUT', 'PATCH', 'POST']:
            return None, None

        old_values = None
        new_values = None

        try:
            # New values from request body
            if hasattr(request, 'body') and request.body:
                try:
                    new_values = json.loads(request.body)
                    # Sanitize sensitive fields
                    if isinstance(new_values, dict):
                        new_values = self._sanitize_sensitive_data(new_values)
                except json.JSONDecodeError:
                    pass

            # Old values would need to be captured in the view
            # This is a limitation of middleware - we can't fetch old values
            # Views should attach them via: request._audit_old_values = {...}
            if hasattr(request, '_audit_old_values'):
                old_values = request._audit_old_values

        except Exception as e:
            logger.warning(f"Failed to extract change data: {e}")

        return old_values, new_values

    def _sanitize_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive fields from audit data.

        Args:
            data: Dictionary to sanitize

        Returns:
            Sanitized dictionary
        """
        sensitive_fields = [
            'password',
            'token',
            'secret',
            'api_key',
            'private_key',
            'credit_card',
            'ssn',
        ]

        sanitized = data.copy()
        for key in list(sanitized.keys()):
            # Check if key contains sensitive term
            if any(term in key.lower() for term in sensitive_fields):
                sanitized[key] = '***REDACTED***'

            # Recursively sanitize nested dicts
            elif isinstance(sanitized[key], dict):
                sanitized[key] = self._sanitize_sensitive_data(sanitized[key])

        return sanitized

    def _serialize_request_data(self, request) -> Dict[str, Any]:
        """
        Serialize request data for async processing.

        Args:
            request: Django request object

        Returns:
            Serializable dictionary with request metadata
        """
        return {
            'path': request.path,
            'method': request.method,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'correlation_id': getattr(request, 'correlation_id', None),
        }

    @staticmethod
    def _get_client_ip(request) -> Optional[str]:
        """Extract client IP address from request"""
        # Check for IP in forwarded headers (if behind proxy)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()

        # Check CloudFlare header
        cf_connecting_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_connecting_ip:
            return cf_connecting_ip

        # Fallback to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR')


# Optional: Decorator for views that need to attach old values
def audit_change(old_value_func=None):
    """
    Decorator to capture old values for audit logging.

    Usage:
        @audit_change(lambda self, request, pk: AttendanceRecord.objects.get(pk=pk))
        def update(self, request, pk):
            ...
    """
    def decorator(view_func):
        def wrapper(*args, **kwargs):
            request = args[1] if len(args) > 1 else kwargs.get('request')
            if request and old_value_func:
                try:
                    old_obj = old_value_func(*args, **kwargs)
                    if hasattr(old_obj, '__dict__'):
                        # Serialize model instance
                        request._audit_old_values = {
                            k: str(v) for k, v in old_obj.__dict__.items()
                            if not k.startswith('_')
                        }
                except Exception as e:
                    logger.warning(f"Failed to capture old values: {e}")

            return view_func(*args, **kwargs)
        return wrapper
    return decorator
