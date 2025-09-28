"""
Session Activity Monitoring Middleware

Implements Rule #10: Session Security Standards
- Tracks last activity timestamp for each session
- Enforces configurable activity timeout
- Detects and prevents stale session usage
- Integrates with security monitoring
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings
from django.contrib.auth import logout
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class SessionActivityMiddleware:
    """
    Tracks session activity and enforces timeout policies.

    Features:
    - Tracks last_activity timestamp in session
    - Enforces configurable inactivity timeout
    - Logs timeout events for security monitoring
    - Integrates with correlation IDs for tracking
    """

    SESSION_ACTIVITY_KEY = '_last_activity'
    SESSION_IP_KEY = '_session_ip'
    SESSION_USER_AGENT_KEY = '_session_user_agent'

    CACHE_KEY_ACTIVE_SESSIONS = 'session_activity:active_count'
    CACHE_KEY_TIMEOUT_EVENTS = 'session_activity:timeout_events'

    def __init__(self, get_response):
        self.get_response = get_response
        self.activity_timeout = getattr(
            settings,
            'SESSION_ACTIVITY_TIMEOUT',
            30 * 60
        )
        self.enable_geo_tracking = getattr(
            settings,
            'SESSION_ENABLE_GEO_TRACKING',
            False
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not hasattr(request, 'session'):
            return self.get_response(request)

        if self._should_skip_tracking(request):
            return self.get_response(request)

        timeout_response = self._check_activity_timeout(request)
        if timeout_response:
            return timeout_response

        self._track_session_metadata(request)

        response = self.get_response(request)

        self._update_activity_timestamp(request)

        self._update_activity_metrics()

        return response

    def _should_skip_tracking(self, request: HttpRequest) -> bool:
        """Skip tracking for static files and health checks."""
        path = request.path
        skip_paths = ['/static/', '/media/', '/health/', '/monitoring/health/']
        return any(path.startswith(skip) for skip in skip_paths)

    def _check_activity_timeout(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Check if session has exceeded inactivity timeout.
        Returns JsonResponse if timed out, None otherwise.
        """
        if not request.user.is_authenticated:
            return None

        last_activity = request.session.get(self.SESSION_ACTIVITY_KEY)

        if not last_activity:
            return None

        try:
            last_activity_time = datetime.fromisoformat(last_activity)
            time_since_activity = timezone.now() - last_activity_time

            if time_since_activity.total_seconds() > self.activity_timeout:
                self._handle_activity_timeout(request, time_since_activity)

                return JsonResponse({
                    'error': 'Session expired due to inactivity',
                    'code': 'SESSION_TIMEOUT',
                    'redirect': '/accounts/login/',
                    'timeout_duration': int(time_since_activity.total_seconds())
                }, status=401)

        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid last_activity timestamp in session: {e}",
                extra={'session_key': request.session.session_key}
            )

        return None

    def _handle_activity_timeout(self, request: HttpRequest, timeout_duration: timedelta):
        """Handle session timeout with logging and cleanup."""
        correlation_id = getattr(request, 'correlation_id', 'unknown')

        logger.warning(
            "Session timed out due to inactivity",
            extra={
                'correlation_id': correlation_id,
                'user_id': request.user.id if request.user.is_authenticated else None,
                'session_key': request.session.session_key,
                'timeout_duration_seconds': int(timeout_duration.total_seconds()),
                'last_activity': request.session.get(self.SESSION_ACTIVITY_KEY),
                'ip_address': self._get_client_ip(request)
            }
        )

        self._increment_timeout_counter()

        logout(request)

    def _track_session_metadata(self, request: HttpRequest):
        """Track session metadata for security monitoring."""
        if not request.user.is_authenticated:
            return

        current_ip = self._get_client_ip(request)
        stored_ip = request.session.get(self.SESSION_IP_KEY)

        if stored_ip and stored_ip != current_ip:
            logger.warning(
                "Session IP address changed - possible session hijacking",
                extra={
                    'user_id': request.user.id,
                    'session_key': request.session.session_key,
                    'original_ip': stored_ip,
                    'new_ip': current_ip,
                    'correlation_id': getattr(request, 'correlation_id', 'unknown')
                }
            )

        request.session[self.SESSION_IP_KEY] = current_ip

        current_user_agent = request.META.get('HTTP_USER_AGENT', '')
        stored_user_agent = request.session.get(self.SESSION_USER_AGENT_KEY)

        if stored_user_agent and stored_user_agent != current_user_agent:
            logger.warning(
                "Session User-Agent changed - possible session hijacking",
                extra={
                    'user_id': request.user.id,
                    'session_key': request.session.session_key,
                    'correlation_id': getattr(request, 'correlation_id', 'unknown')
                }
            )

        request.session[self.SESSION_USER_AGENT_KEY] = current_user_agent

    def _update_activity_timestamp(self, request: HttpRequest):
        """Update the last activity timestamp in session."""
        if request.user.is_authenticated:
            request.session[self.SESSION_ACTIVITY_KEY] = timezone.now().isoformat()

    def _update_activity_metrics(self):
        """Update cached metrics for monitoring dashboard."""
        try:
            current_count = cache.get(self.CACHE_KEY_ACTIVE_SESSIONS, 0)
            cache.set(self.CACHE_KEY_ACTIVE_SESSIONS, current_count, 300)
        except ConnectionError as e:
            logger.debug(f"Cache unavailable for activity metrics: {e}")
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid metrics data: {e}")

    def _increment_timeout_counter(self):
        """Increment timeout event counter for security monitoring."""
        try:
            timeout_events = cache.get(self.CACHE_KEY_TIMEOUT_EVENTS, 0)
            cache.set(
                self.CACHE_KEY_TIMEOUT_EVENTS,
                timeout_events + 1,
                3600
            )
        except ConnectionError:
            pass

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class SessionRotationMiddleware:
    """
    Handles automatic session rotation on privilege changes.

    Works in conjunction with People model signals to rotate
    session keys when user privileges are elevated.
    """

    SESSION_ROTATION_FLAG = '_requires_rotation'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if hasattr(request, 'session') and request.user.is_authenticated:
            if request.session.get(self.SESSION_ROTATION_FLAG):
                self._rotate_session(request)
                del request.session[self.SESSION_ROTATION_FLAG]

        return self.get_response(request)

    def _rotate_session(self, request: HttpRequest):
        """
        Rotate session key to prevent session fixation.
        """
        old_session_key = request.session.session_key
        request.session.cycle_key()
        new_session_key = request.session.session_key

        correlation_id = getattr(request, 'correlation_id', 'unknown')

        logger.info(
            "Session rotated due to privilege change",
            extra={
                'correlation_id': correlation_id,
                'user_id': request.user.id,
                'old_session_key': old_session_key[:8] + '...',
                'new_session_key': new_session_key[:8] + '...',
                'timestamp': timezone.now().isoformat()
            }
        )