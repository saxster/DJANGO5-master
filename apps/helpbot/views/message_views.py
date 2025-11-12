"""
HelpBot Message Views

Handles chat interactions and message processing.
"""

import logging
from typing import Dict, Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.helpbot.models import HelpBotSession
from apps.helpbot.services import HelpBotConversationService, HelpBotContextService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class HelpBotChatView(APIView):
    """
    Main chat interface for HelpBot conversations.
    Handles starting sessions and processing messages.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.conversation_service = HelpBotConversationService()
        self.context_service = HelpBotContextService()

    def post(self, request):
        """Process a chat message or start new session."""
        try:
            action = request.data.get('action', 'message')

            if action == 'start_session':
                return self._start_session(request, request.data)
            elif action == 'message':
                return self._process_message(request, request.data)
            elif action == 'end_session':
                return self._end_session(request, request.data)
            else:
                return Response(
                    {'error': 'Invalid action. Use: start_session, message, or end_session'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in HelpBot chat view: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        """Get active session information."""
        try:
            active_session = self._get_active_session(request.user)

            if not active_session:
                return Response({
                    'has_active_session': False,
                    'session': None
                })

            history = self.conversation_service.get_session_history(active_session)

            return Response({
                'has_active_session': True,
                'session': self._build_session_response(active_session, history)
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error getting HelpBot session info: {e}", exc_info=True)
            return Response(
                {'error': 'Could not get session info'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _start_session(self, request, data: Dict[str, Any]) -> Response:
        """Start a new HelpBot session."""
        try:
            context = self.context_service.capture_context(
                user=request.user,
                request=request,
                additional_context=data.get('context', {})
            )

            session = self.conversation_service.start_session(
                user=request.user,
                session_type=data.get('session_type', 'general_help'),
                context_data=data.get('context_data', {}),
                language=data.get('language', 'en')
            )

            history = self.conversation_service.get_session_history(session)

            return Response({
                'success': True,
                'session_id': str(session.session_id),
                'session_type': session.session_type,
                'current_state': session.current_state,
                'messages': history,
                'context_suggestions': self.context_service.get_context_suggestions(
                    request.user, context
                )
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error starting HelpBot session: {e}", exc_info=True)
            return Response(
                {'error': 'Could not start session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_message(self, request, data: Dict[str, Any]) -> Response:
        """Process a user message."""
        # Guard clauses for validation
        validation_error = self._validate_message_data(data)
        if validation_error:
            return validation_error

        session = self._get_session_for_message(request.user, data.get('session_id'))
        if not session:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Update context if provided
        if 'context' in data:
            self._update_context(request, session, data['context'])

        return self._send_message(session, data)

    def _get_session_for_message(self, user, session_id):
        """Get session for message processing."""
        try:
            return HelpBotSession.objects.get(session_id=session_id, user=user)
        except HelpBotSession.DoesNotExist:
            return None

    def _update_context(self, request, session, context_data):
        """Update context for session."""
        self.context_service.capture_context(
            user=request.user,
            request=request,
            session=session,
            additional_context=context_data
        )

    def _send_message(self, session, data):
        """Send message and get response."""
        try:
            result = self.conversation_service.process_message(
                session=session,
                user_message=data.get('message', '').strip(),
                message_type=data.get('message_type', 'user_text')
            )
            return Response(result)
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error processing HelpBot message: {e}", exc_info=True)
            return Response(
                {'error': 'Could not process message'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _end_session(self, request, data: Dict[str, Any]) -> Response:
        """End a HelpBot session."""
        session_id = data.get('session_id')

        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = HelpBotSession.objects.get(
                session_id=session_id,
                user=request.user
            )
        except HelpBotSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            success = self.conversation_service.end_session(
                session=session,
                satisfaction_rating=data.get('satisfaction_rating')
            )

            return Response({
                'success': success,
                'message': 'Session ended successfully' if success else 'Error ending session'
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error ending HelpBot session: {e}", exc_info=True)
            return Response(
                {'error': 'Could not end session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _validate_message_data(self, data: Dict[str, Any]) -> Response:
        """Validate message data. Returns error response or None."""
        session_id = data.get('session_id')
        message = data.get('message', '').strip()

        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not message:
            return Response(
                {'error': 'message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return None

    def _get_active_session(self, user):
        """Get active session for user."""
        return HelpBotSession.objects.filter(
            user=user,
            current_state__in=[
                HelpBotSession.StateChoices.ACTIVE,
                HelpBotSession.StateChoices.WAITING
            ]
        ).first()

    def _build_session_response(self, session, history):
        """Build session response data."""
        return {
            'session_id': str(session.session_id),
            'session_type': session.session_type,
            'current_state': session.current_state,
            'language': session.language,
            'voice_enabled': session.voice_enabled,
            'total_messages': session.total_messages,
            'messages': history
        }
