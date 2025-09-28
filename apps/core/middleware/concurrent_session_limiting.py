"""
Concurrent Session Limiting Middleware

High-impact security feature to prevent session hijacking and unauthorized access.
Limits the number of concurrent sessions per user and automatically invalidates
oldest sessions when limit is exceeded.

Implements additional security layer for Rule #10: Session Security Standards.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class ConcurrentSessionLimitingMiddleware:
    """
    Limits concurrent sessions per user to prevent session hijacking.

    Configuration:
        MAX_CONCURRENT_SESSIONS: Maximum allowed concurrent sessions (default: 3)
        CONCURRENT_SESSION_ACTION: Action on limit exceeded ('invalidate_oldest' or 'deny_new')

    Features:
    - Tracks active sessions per user in cache
    - Automatically invalidates oldest sessions when limit exceeded
    - Provides session management API for users
    - Logs concurrent session violations
    """

    CACHE_KEY_PREFIX = 'concurrent_sessions:user:'
    CACHE_TTL = 3600

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_concurrent_sessions = getattr(
            settings,
            'MAX_CONCURRENT_SESSIONS',
            3
        )
        self.action_on_limit = getattr(
            settings,
            'CONCURRENT_SESSION_ACTION',
            'invalidate_oldest'
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.get_response(request)

        if not hasattr(request, 'session'):
            return self.get_response(request)

        violation_response = self._check_concurrent_sessions(request)
        if violation_response:
            return violation_response

        self._register_session(request)

        response = self.get_response(request)

        return response

    def _check_concurrent_sessions(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Check if user has exceeded concurrent session limit.

        Args:
            request: HTTP request

        Returns:
            JsonResponse if limit exceeded and action is 'deny_new', None otherwise
        """
        user_id = request.user.id
        current_session_key = request.session.session_key

        active_sessions = self._get_active_sessions(user_id)

        if current_session_key in active_sessions:
            return None

        if len(active_sessions) >= self.max_concurrent_sessions:
            if self.action_on_limit == 'deny_new':
                self._log_session_limit_violation(request, len(active_sessions))

                return JsonResponse({
                    'error': 'Maximum concurrent sessions exceeded',
                    'code': 'MAX_SESSIONS_EXCEEDED',
                    'max_sessions': self.max_concurrent_sessions,
                    'active_sessions': len(active_sessions),
                    'action': 'Please close other sessions and try again'
                }, status=403)

            elif self.action_on_limit == 'invalidate_oldest':
                self._invalidate_oldest_session(user_id, active_sessions)

                self._log_session_auto_invalidation(request, active_sessions)

        return None

    def _register_session(self, request: HttpRequest):
        """
        Register current session as active for user.

        Args:
            request: HTTP request
        """
        user_id = request.user.id
        session_key = request.session.session_key

        active_sessions = self._get_active_sessions(user_id)

        if session_key not in active_sessions:
            active_sessions.append(session_key)

        session_metadata = {
            'sessions': active_sessions,
            'last_updated': timezone.now().isoformat(),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
            'ip_address': self._get_client_ip(request)
        }

        cache_key = f"{self.CACHE_KEY_PREFIX}{user_id}"
        cache.set(cache_key, session_metadata, self.CACHE_TTL)

    def _get_active_sessions(self, user_id: int) -> List[str]:
        """
        Get list of active session keys for user.

        Args:
            user_id: User ID

        Returns:
            List of active session keys
        """
        cache_key = f"{self.CACHE_KEY_PREFIX}{user_id}"
        session_data = cache.get(cache_key)

        if not session_data:
            return []

        active_sessions = session_data.get('sessions', [])

        return self._filter_valid_sessions(active_sessions)

    def _filter_valid_sessions(self, session_keys: List[str]) -> List[str]:
        """
        Filter out expired or invalid sessions.

        Args:
            session_keys: List of session keys to validate

        Returns:
            List of valid session keys
        """
        valid_sessions = []

        for session_key in session_keys:
            try:
                session = Session.objects.get(
                    session_key=session_key,
                    expire_date__gt=timezone.now()
                )
                valid_sessions.append(session_key)

            except Session.DoesNotExist:
                continue

        return valid_sessions

    def _invalidate_oldest_session(self, user_id: int, active_sessions: List[str]):
        """
        Invalidate the oldest session for user.

        Args:
            user_id: User ID
            active_sessions: List of active session keys
        """
        if not active_sessions:
            return

        try:
            sessions = Session.objects.filter(
                session_key__in=active_sessions
            ).order_by('expire_date')

            if sessions.exists():
                oldest_session = sessions.first()
                oldest_session.delete()

                logger.info(
                    f"Invalidated oldest session for user {user_id}",
                    extra={
                        'user_id': user_id,
                        'invalidated_session': oldest_session.session_key[:8] + '...',
                        'reason': 'concurrent_session_limit_exceeded',
                        'active_sessions_count': len(active_sessions)
                    }
                )

        except Session.DoesNotExist:
            pass

    def _log_session_limit_violation(self, request: HttpRequest, session_count: int):
        """
        Log session limit violation.

        Args:
            request: HTTP request
            session_count: Current session count
        """
        logger.warning(
            "Concurrent session limit exceeded - new session denied",
            extra={
                'user_id': request.user.id,
                'peoplecode': getattr(request.user, 'peoplecode', 'unknown'),
                'active_sessions': session_count,
                'max_sessions': self.max_concurrent_sessions,
                'ip_address': self._get_client_ip(request),
                'correlation_id': getattr(request, 'correlation_id', 'unknown')
            }
        )

    def _log_session_auto_invalidation(self, request: HttpRequest, active_sessions: List[str]):
        """
        Log automatic session invalidation.

        Args:
            request: HTTP request
            active_sessions: List of active sessions before invalidation
        """
        logger.info(
            "Auto-invalidated oldest session due to concurrent limit",
            extra={
                'user_id': request.user.id,
                'peoplecode': getattr(request.user, 'peoplecode', 'unknown'),
                'sessions_before': len(active_sessions),
                'max_allowed': self.max_concurrent_sessions,
                'correlation_id': getattr(request, 'correlation_id', 'unknown')
            }
        )

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class SessionManagerAPI:
    """
    API for users to manage their active sessions.

    Provides methods for:
    - Listing active sessions
    - Invalidating specific sessions
    - Invalidating all other sessions (keep current)
    """

    @staticmethod
    def get_user_active_sessions(user_id: int) -> List[Dict[str, str]]:
        """
        Get list of active sessions for user with metadata.

        Args:
            user_id: User ID

        Returns:
            List of session metadata dictionaries
        """
        try:
            sessions = Session.objects.filter(
                expire_date__gt=timezone.now()
            )

            user_sessions = []

            for session in sessions:
                session_data = session.get_decoded()
                session_user_id = session_data.get('_auth_user_id')

                if session_user_id and int(session_user_id) == user_id:
                    user_sessions.append({
                        'session_key': session.session_key[:8] + '...',
                        'created': session.expire_date - timezone.timedelta(
                            seconds=settings.SESSION_COOKIE_AGE
                        ),
                        'expires': session.expire_date,
                        'ip_address': session_data.get('_session_ip', 'unknown'),
                        'user_agent': session_data.get('_session_user_agent', 'unknown')[:50]
                    })

            return user_sessions

        except (Session.DoesNotExist, ValueError, KeyError) as e:
            logger.error(f"Error retrieving user sessions: {str(e)}")
            return []

    @staticmethod
    def invalidate_session(user_id: int, session_key: str) -> bool:
        """
        Invalidate specific session for user.

        Args:
            user_id: User ID (for authorization)
            session_key: Session key to invalidate

        Returns:
            True if invalidated successfully
        """
        try:
            session = Session.objects.get(session_key=session_key)
            session_data = session.get_decoded()
            session_user_id = session_data.get('_auth_user_id')

            if session_user_id and int(session_user_id) == user_id:
                session.delete()

                logger.info(
                    f"User invalidated their own session",
                    extra={
                        'user_id': user_id,
                        'session_key': session_key[:8] + '...'
                    }
                )

                return True

            return False

        except (Session.DoesNotExist, ValueError, KeyError) as e:
            logger.error(f"Error invalidating session: {str(e)}")
            return False

    @staticmethod
    def invalidate_all_other_sessions(user_id: int, current_session_key: str) -> int:
        """
        Invalidate all sessions except current one.

        Args:
            user_id: User ID
            current_session_key: Current session to keep

        Returns:
            Number of sessions invalidated
        """
        try:
            sessions = Session.objects.filter(
                expire_date__gt=timezone.now()
            )

            invalidated_count = 0

            for session in sessions:
                if session.session_key == current_session_key:
                    continue

                session_data = session.get_decoded()
                session_user_id = session_data.get('_auth_user_id')

                if session_user_id and int(session_user_id) == user_id:
                    session.delete()
                    invalidated_count += 1

            logger.info(
                f"User invalidated all other sessions",
                extra={
                    'user_id': user_id,
                    'invalidated_count': invalidated_count,
                    'kept_session': current_session_key[:8] + '...'
                }
            )

            return invalidated_count

        except (Session.DoesNotExist, ValueError, KeyError) as e:
            logger.error(f"Error invalidating other sessions: {str(e)}")
            return 0