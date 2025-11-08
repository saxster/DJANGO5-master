"""
Session Recovery API Views

REST API endpoints for session checkpoint management and recovery.

Following .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization

Author: Claude Code
Date: 2025-10-01
"""

import logging
from typing import Dict, Any

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from apps.onboarding_api.services.session_recovery import (
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

    get_session_recovery_service,
    CheckpointNotFoundError
)

logger = logging.getLogger(__name__)


class SessionCheckpointView(APIView):
    """
    POST /api/v1/onboarding/sessions/{session_id}/checkpoint/

    Create a checkpoint for the current session state.

    Request Body:
        {
            "state": "IN_PROGRESS",
            "data": {...},
            "history": [...],
            "ui_state": {...},
            "version": 1,
            "force": false
        }

    Response:
        {
            "status": "created",
            "checkpoint_version": 5,
            "checkpoint_hash": "a1b2c3d4...",
            "created_at": "2025-10-01T12:00:00Z"
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """Create session checkpoint"""
        try:
            # Verify session ownership
            if not self._verify_session_ownership(session_id, request.user.id):
                return Response(
                    {'error': 'Session not found or access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Parse checkpoint data
            checkpoint_data = {
                'state': request.data.get('state'),
                'data': request.data.get('data', {}),
                'history': request.data.get('history', []),
                'ui_state': request.data.get('ui_state', {}),
                'version': request.data.get('version', 1),
                'metadata': request.data.get('metadata', {})
            }

            force = request.data.get('force', False)

            # Create checkpoint
            recovery_service = get_session_recovery_service()
            result = recovery_service.create_checkpoint(
                session_id=session_id,
                checkpoint_data=checkpoint_data,
                force=force
            )

            return Response(result, status=status.HTTP_201_CREATED)

        except (ValueError, ValidationError) as e:
            logger.warning(f"Invalid checkpoint data for {session_id}: {str(e)}")
            return Response(
                {'error': 'Invalid checkpoint data', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error creating checkpoint: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to create checkpoint'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _verify_session_ownership(self, session_id: str, user_id: int) -> bool:
        """Verify user owns the session"""
        try:
            from apps.core_onboarding.models import ConversationSession
            session = ConversationSession.objects.get(session_id=session_id)
            return session.user_id == user_id
        except ConversationSession.DoesNotExist:
            return False


class SessionResumeView(APIView):
    """
    POST /api/v1/onboarding/sessions/{session_id}/resume/

    Resume a session from the latest checkpoint.

    Response:
        {
            "status": "resumed",
            "session_id": "uuid",
            "resumed_at": "IN_PROGRESS",
            "questions_answered": 5,
            "next_action": {
                "action": "continue_conversation",
                "message": "Welcome back!",
                "next_question_index": 5
            },
            "progress_percent": 45.0
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """Resume session from checkpoint"""
        try:
            recovery_service = get_session_recovery_service()

            # Attempt resume
            result = recovery_service.resume_session(
                session_id=session_id,
                user_id=request.user.id
            )

            logger.info(
                f"Session resumed",
                extra={
                    'session_id': session_id,
                    'user_id': request.user.id
                }
            )

            return Response(result)

        except CheckpointNotFoundError:
            return Response(
                {'error': 'No checkpoint found for this session'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            logger.warning(f"Invalid resume request: {str(e)}")
            return Response(
                {'error': 'Cannot resume session', 'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error resuming session: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to resume session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SessionCheckpointHistoryView(APIView):
    """
    GET /api/v1/onboarding/sessions/{session_id}/checkpoints/

    List historical checkpoints for a session.

    Query Parameters:
        - limit: Maximum number of checkpoints (default: 10)

    Response:
        {
            "session_id": "uuid",
            "checkpoints": [
                {
                    "version": 5,
                    "created_at": "2025-10-01T12:00:00Z",
                    "checkpoint_hash": "a1b2c3d4...",
                    "state": "IN_PROGRESS"
                },
                ...
            ],
            "total": 5
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """List checkpoint history"""
        try:
            # Verify session ownership
            if not self._verify_session_ownership(session_id, request.user.id):
                return Response(
                    {'error': 'Session not found or access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Parse limit
            limit = min(int(request.query_params.get('limit', 10)), 50)

            # Get checkpoint history
            recovery_service = get_session_recovery_service()
            checkpoints = recovery_service.list_checkpoints(
                session_id=session_id,
                limit=limit
            )

            return Response({
                'session_id': session_id,
                'checkpoints': checkpoints,
                'total': len(checkpoints)
            })

        except (ValueError, TypeError) as e:
            return Response(
                {'error': 'Invalid query parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _verify_session_ownership(self, session_id: str, user_id: int) -> bool:
        """Verify user owns the session"""
        try:
            from apps.core_onboarding.models import ConversationSession
            session = ConversationSession.objects.get(session_id=session_id)
            return session.user_id == user_id
        except ConversationSession.DoesNotExist:
            return False


class AbandonmentRiskView(APIView):
    """
    GET /api/v1/onboarding/sessions/{session_id}/risk/

    Get abandonment risk assessment for a session.

    Response:
        {
            "session_id": "uuid",
            "risk_score": 65,
            "risk_level": "high",
            "risk_factors": [
                "moderate_inactivity",
                "question_confusion"
            ],
            "intervention": {
                "recommended_interventions": [
                    {
                        "type": "proactive_reach_out",
                        "action": "send_reminder_email",
                        "message": "Send email reminder with resume link",
                        "priority": "high"
                    }
                ],
                "urgency": "soon"
            },
            "time_inactive_seconds": 420,
            "assessed_at": "2025-10-01T12:00:00Z"
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """Get abandonment risk assessment"""
        try:
            # Verify session ownership (optional for risk assessment)
            if not self._verify_session_ownership(session_id, request.user.id):
                # Allow admins to see any session risk
                if not request.user.is_staff:
                    return Response(
                        {'error': 'Session not found or access denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            # Get risk assessment
            recovery_service = get_session_recovery_service()
            risk_assessment = recovery_service.detect_abandonment_risk(session_id)

            if 'error' in risk_assessment:
                return Response(
                    risk_assessment,
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(risk_assessment)

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Error getting risk assessment: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to assess risk'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _verify_session_ownership(self, session_id: str, user_id: int) -> bool:
        """Verify user owns the session"""
        try:
            from apps.core_onboarding.models import ConversationSession
            session = ConversationSession.objects.get(session_id=session_id)
            return session.user_id == user_id
        except ConversationSession.DoesNotExist:
            return False


class AtRiskSessionsView(APIView):
    """
    GET /api/v1/admin/onboarding/at-risk-sessions/

    Get list of sessions at risk of abandonment (admin only).

    Query Parameters:
        - risk_level: Minimum risk level ('medium', 'high', 'critical')
        - limit: Maximum sessions to return (default: 50)

    Response:
        {
            "sessions": [
                {
                    "session_id": "uuid",
                    "risk_score": 75,
                    "risk_level": "critical",
                    "risk_factors": [...],
                    "intervention": {...},
                    "time_inactive_seconds": 900
                },
                ...
            ],
            "total": 15,
            "filters": {
                "risk_level": "high",
                "limit": 50
            }
        }
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get at-risk sessions"""
        try:
            # Parse query parameters
            risk_level = request.query_params.get('risk_level', 'high')
            limit = min(int(request.query_params.get('limit', 50)), 200)

            # Validate risk level
            valid_levels = ['medium', 'high', 'critical']
            if risk_level not in valid_levels:
                return Response(
                    {'error': f'Invalid risk_level. Must be one of: {valid_levels}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get at-risk sessions
            recovery_service = get_session_recovery_service()
            at_risk_sessions = recovery_service.get_at_risk_sessions(
                risk_level=risk_level,
                limit=limit
            )

            return Response({
                'sessions': at_risk_sessions,
                'total': len(at_risk_sessions),
                'filters': {
                    'risk_level': risk_level,
                    'limit': limit
                }
            })

        except (ValueError, TypeError) as e:
            return Response(
                {'error': 'Invalid query parameters', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Error getting at-risk sessions: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve at-risk sessions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


__all__ = [
    'SessionCheckpointView',
    'SessionResumeView',
    'SessionCheckpointHistoryView',
    'AbandonmentRiskView',
    'AtRiskSessionsView',
]
