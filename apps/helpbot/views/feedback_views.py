"""
HelpBot Feedback Views

Handles user feedback collection for HelpBot interactions.
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.helpbot.models import HelpBotSession, HelpBotFeedback
from apps.helpbot.services import HelpBotConversationService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class HelpBotFeedbackView(APIView):
    """Handle user feedback for HelpBot interactions."""

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.conversation_service = HelpBotConversationService()

    def post(self, request):
        """Submit feedback for a HelpBot message or session."""
        try:
            # Guard clauses for validation
            validation_error = self._validate_feedback_data(request.data)
            if validation_error:
                return validation_error

            session_id = request.data.get('session_id')
            session = self._get_session(session_id, request.user)

            if not session:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            success = self._submit_feedback(session, request.data)

            return Response({
                'success': success,
                'message': 'Feedback submitted successfully' if success else 'Error submitting feedback'
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error submitting HelpBot feedback: {e}", exc_info=True)
            return Response(
                {'error': 'Could not submit feedback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _validate_feedback_data(self, data):
        """Validate feedback data. Returns error response or None."""
        session_id = data.get('session_id')
        feedback_type = data.get('feedback_type')

        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not feedback_type:
            return Response(
                {'error': 'feedback_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_types = [choice[0] for choice in HelpBotFeedback.FeedbackTypeChoices.choices]
        if feedback_type not in valid_types:
            return Response(
                {'error': f'Invalid feedback_type. Valid options: {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return None

    def _get_session(self, session_id, user):
        """Get session by ID and user."""
        try:
            return HelpBotSession.objects.get(
                session_id=session_id,
                user=user
            )
        except HelpBotSession.DoesNotExist:
            return None

    def _submit_feedback(self, session, data):
        """Submit feedback using conversation service."""
        return self.conversation_service.add_feedback(
            session=session,
            message_id=data.get('message_id') or '',
            feedback_type=data.get('feedback_type'),
            rating=data.get('rating'),
            comment=data.get('comment', '').strip()
        )
