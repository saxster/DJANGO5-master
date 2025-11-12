"""
HelpBot Utility Views

Function-based views and template views for health checks, configuration, and pages.
"""

import logging
from datetime import datetime

from django.conf import settings
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.helpbot.services import HelpBotKnowledgeService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def helpbot_health(request):
    """Health check endpoint for HelpBot services."""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': True,
                'knowledge_service': True,
                'conversation_service': True,
            }
        }

        # Check knowledge service
        if not _check_knowledge_service():
            health_status['services']['knowledge_service'] = False
            health_status['status'] = 'degraded'

        return Response(health_status)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def helpbot_config(request):
    """Get HelpBot configuration for frontend."""
    try:
        config = {
            'enabled': getattr(settings, 'HELPBOT_ENABLED', True),
            'voice_enabled': getattr(settings, 'HELPBOT_VOICE_ENABLED', False),
            'max_message_length': getattr(settings, 'HELPBOT_MAX_MESSAGE_LENGTH', 1000),
            'session_timeout_minutes': getattr(settings, 'HELPBOT_SESSION_TIMEOUT_MINUTES', 60),
            'available_languages': getattr(settings, 'HELPBOT_LANGUAGES', ['en']),
            'features': _build_feature_config(request.user)
        }

        return Response(config)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error getting HelpBot config: {e}", exc_info=True)
        return Response({
            'error': 'Could not get configuration'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HelpBotChatPageView(TemplateView):
    """Full-screen HelpBot chat page."""

    template_name = 'helpbot/chat_page.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add HelpBot-specific context."""
        context = super().get_context_data(**kwargs)

        context.update({
            'helpbot_enabled': getattr(settings, 'HELPBOT_ENABLED', True),
            'voice_enabled': getattr(settings, 'HELPBOT_VOICE_ENABLED', False),
            'max_message_length': getattr(settings, 'HELPBOT_MAX_MESSAGE_LENGTH', 2000),
            'page_title': 'AI Assistant - Help & Support',
        })

        return context


# Helper functions
def _check_knowledge_service():
    """Check if knowledge service is working."""
    try:
        knowledge_service = HelpBotKnowledgeService()
        knowledge_service._record_analytics('health_check', 0)
        return True
    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS):
        return False


def _build_feature_config(user):
    """Build feature configuration based on user permissions."""
    return {
        'knowledge_search': True,
        'context_awareness': True,
        'feedback_collection': True,
        'analytics': user.is_staff or getattr(user, 'isadmin', False),
    }
