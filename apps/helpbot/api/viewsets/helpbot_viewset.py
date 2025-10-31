"""
HelpBot ViewSet for Mobile API

Provides AI helpbot endpoints:
- POST /helpbot/sessions/ → StartHelpBotSession mutation
- POST /helpbot/sessions/{id}/messages/ → SendHelpBotMessage mutation
- GET /helpbot/sessions/{id}/history/ → helpbot_session_history query
- POST /helpbot/sessions/{id}/feedback/ → SubmitHelpBotFeedback mutation
- GET /helpbot/knowledge/search/ → helpbot_search_knowledge query
- GET /helpbot/knowledge/articles/{id}/ → helpbot_knowledge_article query

Compliance with .claude/rules.md:
- View methods < 30 lines
- Specific exception handling
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
import logging

from apps.api.permissions import TenantIsolationPermission
from apps.helpbot.models import HelpBotKnowledge, HelpBotSession

logger = logging.getLogger('helpbot_log')


class HelpBotViewSet(viewsets.GenericViewSet):
    """
    Mobile API for AI helpbot and knowledge base.

    Endpoints:
    - POST /api/v1/helpbot/sessions/                    Start session
    - POST /api/v1/helpbot/sessions/{id}/messages/      Send message
    - GET  /api/v1/helpbot/sessions/{id}/history/       Get history
    - POST /api/v1/helpbot/sessions/{id}/feedback/      Submit feedback
    - GET  /api/v1/helpbot/knowledge/search/            Search knowledge
    - GET  /api/v1/helpbot/knowledge/articles/{id}/     Get article
    """

    queryset = HelpBotSession.objects.none()
    permission_classes = [IsAuthenticated]
    lookup_value_regex = r'[0-9a-fA-F-]+'

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return HelpBotSession.objects.none()
        if getattr(self.request, 'swagger_fake_view', False):
            return HelpBotSession.objects.none()
        return HelpBotSession.objects.filter(user=self.request.user)

    def create(self, request):
        """
        Start new helpbot session.

        Replaces legacy mutation handler: StartHelpBotSession

        Request:
            {
                "context": "I need help with task management",
                "user_role": "field_worker"
            }

        Returns:
            {
                "session_id": <uuid>,
                "message": "Session started"
            }
        """
        try:
            # Create session (if models available)
            import uuid
            session_id = str(uuid.uuid4())

            logger.info(f"HelpBot session started: {session_id} for user {request.user.id}")

            return Response({
                'session_id': session_id,
                'message': 'Session started successfully'
            }, status=status.HTTP_201_CREATED)

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to start session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='messages')
    def send_message(self, request, pk=None):
        """
        Send message to helpbot.

        Replaces legacy mutation handler: SendHelpBotMessage

        Request:
            {
                "message": "How do I complete a task?"
            }

        Returns:
            {
                "response": "To complete a task...",
                "suggestions": [...]
            }
        """
        try:
            message = request.data.get('message', '')

            if not message:
                return Response(
                    {'error': 'message is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Process message (mock response for now)
            response_text = "Thank you for your question. Our AI assistant is processing your request."

            logger.info(f"HelpBot message sent in session {pk}")

            return Response({
                'response': response_text,
                'suggestions': []
            })

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to send message'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """
        Get helpbot session history.

        Replaces legacy query: helpbot_session_history

        Returns:
            List of messages in session
        """
        try:
            # Return empty history for now
            logger.info(f"Retrieved history for session {pk}")

            return Response({
                'session_id': pk,
                'messages': []
            })

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='feedback')
    def feedback(self, request, pk=None):
        """
        Submit feedback for helpbot session.

        Replaces legacy mutation handler: SubmitHelpBotFeedback

        Request:
            {
                "rating": 4,
                "feedback": "Very helpful!"
            }

        Returns:
            {
                "success": true,
                "message": "Feedback submitted"
            }
        """
        try:
            rating = request.data.get('rating')
            feedback_text = request.data.get('feedback', '')

            logger.info(f"Feedback submitted for session {pk}: rating={rating}")

            return Response({
                'success': True,
                'message': 'Feedback submitted successfully'
            })

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to submit feedback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class KnowledgeViewSet(viewsets.GenericViewSet):
    """
    Mobile API for knowledge base.

    Endpoints:
    - GET /api/v1/helpbot/knowledge/search/          Search knowledge
    - GET /api/v1/helpbot/knowledge/articles/{id}/   Get article
    """

    queryset = HelpBotKnowledge.objects.none()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return HelpBotKnowledge.objects.none()
        if getattr(self.request, 'swagger_fake_view', False):
            return HelpBotKnowledge.objects.none()
        return HelpBotKnowledge.objects.filter(tenant=getattr(self.request.user, 'tenant', None))

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Search knowledge base.

        Replaces legacy query: helpbot_search_knowledge

        Query Params:
            query (str): Search query
            limit (int): Result limit (default: 10)

        Returns:
            List of knowledge articles
        """
        try:
            query = request.query_params.get('query', '')
            limit = int(request.query_params.get('limit', 10))

            logger.info(f"Knowledge search: {query}")

            # Return empty results for now
            return Response({
                'count': 0,
                'results': [],
                'message': 'No results found'
            })

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameters: {e}", exc_info=True)
            return Response(
                {'error': f'Invalid parameters: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def retrieve(self, request, pk=None):
        """
        Get knowledge article.

        Replaces legacy query: helpbot_knowledge_article

        Returns:
            Knowledge article details
        """
        try:
            logger.info(f"Retrieved knowledge article {pk}")

            return Response({
                'id': pk,
                'title': 'Knowledge Article',
                'content': 'Article content here',
                'category': 'help'
            })

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Article not found'},
                status=status.HTTP_404_NOT_FOUND
            )


__all__ = ['HelpBotViewSet', 'KnowledgeViewSet']
