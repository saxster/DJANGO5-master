"""
HelpBot Context Views

Handles user context management for context-aware assistance.
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.helpbot.services import HelpBotContextService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class HelpBotContextView(APIView):
    """Manage user context for HelpBot."""

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.context_service = HelpBotContextService()

    def post(self, request):
        """Update user context."""
        try:
            context = self.context_service.capture_context(
                user=request.user,
                request=request,
                additional_context=request.data.get('context', {})
            )

            return Response({
                'success': True,
                'context_id': str(context.context_id),
                'suggestions': self.context_service.get_context_suggestions(
                    request.user, context
                )
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error updating HelpBot context: {e}", exc_info=True)
            return Response(
                {'error': 'Could not update context'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        """Get current user context and suggestions."""
        try:
            current_context = self.context_service.get_current_context(request.user)
            suggestions = self.context_service.get_context_suggestions(
                request.user, current_context
            )

            response_data = {
                'suggestions': suggestions,
                'has_context': current_context is not None
            }

            if current_context:
                response_data['context'] = self._build_context_data(current_context)

            return Response(response_data)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error getting HelpBot context: {e}", exc_info=True)
            return Response(
                {'error': 'Could not get context'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _build_context_data(self, context):
        """Build context data response."""
        return {
            'current_url': context.current_url,
            'page_title': context.page_title,
            'app_name': context.app_name,
            'view_name': context.view_name,
            'timestamp': context.timestamp.isoformat(),
        }
