"""
HelpBot Widget Views

Traditional Django views for widget integration with existing templates.
"""

import json
import logging

from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from apps.helpbot.models import HelpBotSession
from apps.helpbot.services import HelpBotConversationService, HelpBotContextService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


@method_decorator([login_required, csrf_exempt], name='dispatch')
class HelpBotWidgetView(View):
    """
    Traditional Django view for HelpBot widget integration.
    Returns JSON responses for AJAX calls from existing templates.
    """

    def __init__(self):
        super().__init__()
        self.conversation_service = HelpBotConversationService()
        self.context_service = HelpBotContextService()

    def post(self, request):
        """Handle AJAX requests from HelpBot widget."""
        try:
            data = self._parse_json_body(request)

            if data is None:
                return JsonResponse({'error': 'Invalid JSON data'}, status=400)

            action = data.get('action')

            # Route to appropriate handler
            if action == 'start_session':
                return self._handle_start_session(request, data)
            elif action == 'send_message':
                return self._handle_send_message(request, data)
            elif action == 'get_suggestions':
                return self._handle_get_suggestions(request, data)
            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in HelpBot widget view: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)

    def _parse_json_body(self, request):
        """Parse JSON from request body."""
        try:
            return json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return None

    def _handle_start_session(self, request, data):
        """Handle session start from widget."""
        try:
            context = self._capture_widget_context(request, data)
            session = self._create_widget_session(request.user, data)
            history = self.conversation_service.get_session_history(session)

            return JsonResponse({
                'success': True,
                'session_id': str(session.session_id),
                'messages': history,
                'context_suggestions': self.context_service.get_context_suggestions(
                    request.user, context
                )
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error starting widget session: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Could not start session'
            }, status=500)

    def _capture_widget_context(self, request, data):
        """Capture context from widget."""
        return self.context_service.capture_context(
            user=request.user,
            request=request,
            additional_context={
                'current_url': data.get('current_url', ''),
                'page_title': data.get('page_title', ''),
                'widget_context': True
            }
        )

    def _create_widget_session(self, user, data):
        """Create session from widget."""
        return self.conversation_service.start_session(
            user=user,
            session_type=data.get('session_type', 'general_help'),
            context_data={'widget_initiated': True},
            language=data.get('language', 'en')
        )

    def _handle_send_message(self, request, data):
        """Handle message from widget."""
        # Guard clauses for validation
        session_id = data.get('session_id')
        message = data.get('message', '').strip()

        if not session_id or not message:
            return JsonResponse({
                'success': False,
                'error': 'Session ID and message are required'
            }, status=400)

        session = self._get_session(session_id, request.user)

        if not session:
            return JsonResponse({
                'success': False,
                'error': 'Session not found'
            }, status=404)

        try:
            result = self.conversation_service.process_message(
                session=session,
                user_message=message
            )
            return JsonResponse(result)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error processing widget message: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Could not process message'
            }, status=500)

    def _handle_get_suggestions(self, request, data):
        """Get context-based suggestions."""
        try:
            current_context = self.context_service.get_current_context(request.user)
            suggestions = self.context_service.get_context_suggestions(
                request.user, current_context
            )

            return JsonResponse({
                'success': True,
                'suggestions': suggestions
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error getting suggestions: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Could not get suggestions'
            }, status=500)

    def _get_session(self, session_id, user):
        """Get session by ID and user."""
        try:
            return HelpBotSession.objects.get(
                session_id=session_id,
                user=user
            )
        except HelpBotSession.DoesNotExist:
            return None
