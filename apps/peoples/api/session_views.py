"""
Session Management API Views

RESTful API endpoints for managing user sessions across devices.

Endpoints:
    GET    /api/sessions/          - List user's sessions
    DELETE /api/sessions/{id}/     - Revoke specific session
    POST   /api/sessions/revoke-all/ - Revoke all sessions
    GET    /api/sessions/statistics/ - Get session stats

Security:
    - Authentication required
    - Users can only manage their own sessions
    - Admins can view all sessions

Compliance:
    - GDPR: User control over session data
    - Rule #8: View methods < 30 lines
"""

import logging
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator

from apps.core.decorators import csrf_protect_ajax, rate_limit
from apps.peoples.services.session_management_service import session_management_service

logger = logging.getLogger(__name__)


class SessionListView(LoginRequiredMixin, View):
    """
    List all sessions for current user.

    GET /api/sessions/
    """

    def get(self, request):
        """Get user's active sessions."""
        try:
            sessions = session_management_service.get_user_sessions(
                user=request.user,
                include_revoked=False
            )

            return JsonResponse({
                'success': True,
                'sessions': [
                    {
                        'id': s.id,
                        'device_name': s.device_name,
                        'device_type': s.device_type,
                        'browser': s.browser,
                        'os': s.os,
                        'ip_address': s.ip_address,
                        'location': s.location,
                        'created_at': s.created_at.isoformat(),
                        'last_activity': s.last_activity.isoformat(),
                        'is_current': s.is_current,
                        'is_suspicious': s.is_suspicious,
                        'suspicious_reason': s.suspicious_reason,
                    }
                    for s in sessions
                ]
            })

        except (AttributeError, ValueError) as e:
            logger.error(f"Error listing sessions: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Error retrieving sessions'
            }, status=500)


@method_decorator(csrf_protect_ajax, name='dispatch')
@method_decorator(rate_limit(max_requests=30, window_seconds=300), name='dispatch')
class SessionRevokeView(LoginRequiredMixin, View):
    """
    Revoke a specific session.

    DELETE /api/sessions/{id}/
    
    Security:
    - CSRF protected via csrf_protect_ajax (Rule #2 compliant)
    - Rate limited to 30 requests per 5 minutes
    """

    def delete(self, request, session_id):
        """Revoke session by ID."""
        try:
            current_session_key = request.session.session_key

            success, message = session_management_service.revoke_session(
                session_id=session_id,
                revoked_by=request.user,
                reason='user_action',
                current_session_key=current_session_key
            )

            if success:
                return JsonResponse({
                    'success': True,
                    'message': message
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': message
                }, status=400)

        except (AttributeError, ValueError) as e:
            logger.error(f"Error revoking session: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Error revoking session'
            }, status=500)


@method_decorator(csrf_protect_ajax, name='dispatch')
@method_decorator(rate_limit(max_requests=10, window_seconds=300), name='dispatch')
class SessionRevokeAllView(LoginRequiredMixin, View):
    """
    Revoke all sessions except current.

    POST /api/sessions/revoke-all/
    
    Security:
    - CSRF protected via csrf_protect_ajax (Rule #2 compliant)
    - Rate limited to 10 requests per 5 minutes (stricter due to bulk operation)
    """

    def post(self, request):
        """Revoke all user sessions."""
        try:
            current_session_key = request.session.session_key

            count, message = session_management_service.revoke_all_sessions(
                user=request.user,
                except_current=True,
                current_session_key=current_session_key,
                reason='user_action'
            )

            return JsonResponse({
                'success': True,
                'message': message,
                'revoked_count': count
            })

        except (AttributeError, ValueError) as e:
            logger.error(f"Error revoking all sessions: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Error revoking sessions'
            }, status=500)


class SessionStatisticsView(LoginRequiredMixin, View):
    """
    Get session statistics for current user.

    GET /api/sessions/statistics/
    """

    def get(self, request):
        """Get user's session statistics."""
        try:
            stats = session_management_service.get_session_statistics(request.user)

            return JsonResponse({
                'success': True,
                'statistics': stats
            })

        except (AttributeError, ValueError) as e:
            logger.error(f"Error getting statistics: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Error retrieving statistics'
            }, status=500)
