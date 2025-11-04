"""
HelpBot Views

REST API views for HelpBot functionality.
Provides endpoints for chat interaction, session management, and analytics.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View, TemplateView
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.db import transaction

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.helpbot.models import HelpBotSession, HelpBotMessage, HelpBotFeedback, HelpBotContext
from apps.helpbot.services import (
    HelpBotConversationService,
    HelpBotKnowledgeService,
    HelpBotContextService,
    HelpBotAnalyticsService
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class SecurityScorecardView(APIView):
    """
    Security & Facility Mentor Scorecard API.
    Generates and returns non-negotiables scorecard for current user's client.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.conversation_service = HelpBotConversationService()

    def get(self, request):
        """Get scorecard for current user's client."""
        try:
            # Get or create session
            session = HelpBotSession.objects.filter(
                user=request.user,
                session_type=HelpBotSession.SessionTypeChoices.SECURITY_FACILITY
            ).first()

            if not session:
                # Create a temporary session for scorecard generation
                session = HelpBotSession.objects.create(
                    user=request.user,
                    session_type=HelpBotSession.SessionTypeChoices.SECURITY_FACILITY,
                    tenant=request.user.tenant if hasattr(request.user, 'tenant') else None,
                    client=request.user.bu if hasattr(request.user, 'bu') else None,
                )

            # Generate scorecard
            check_date = request.query_params.get('check_date')
            if check_date:
                from datetime import datetime
                check_date = datetime.strptime(check_date, '%Y-%m-%d').date()

            scorecard_data = self.conversation_service.generate_security_scorecard(
                session=session,
                check_date=check_date
            )

            if not scorecard_data['success']:
                return Response(
                    {'error': scorecard_data.get('error', 'Failed to generate scorecard')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(scorecard_data['scorecard'])

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error generating scorecard: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Refresh scorecard (same as GET but with optional parameters in body)."""
        try:
            # Get or create session
            session = HelpBotSession.objects.filter(
                user=request.user,
                session_type=HelpBotSession.SessionTypeChoices.SECURITY_FACILITY
            ).first()

            if not session:
                session = HelpBotSession.objects.create(
                    user=request.user,
                    session_type=HelpBotSession.SessionTypeChoices.SECURITY_FACILITY,
                    tenant=request.user.tenant if hasattr(request.user, 'tenant') else None,
                    client=request.user.bu if hasattr(request.user, 'bu') else None,
                )

            # Generate scorecard with optional parameters
            check_date = request.data.get('check_date')
            if check_date:
                from datetime import datetime
                check_date = datetime.strptime(check_date, '%Y-%m-%d').date()

            scorecard_data = self.conversation_service.generate_security_scorecard(
                session=session,
                check_date=check_date
            )

            if not scorecard_data['success']:
                return Response(
                    {'error': scorecard_data.get('error', 'Failed to generate scorecard')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(scorecard_data['scorecard'])

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error generating scorecard: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            data = request.data
            action = data.get('action', 'message')

            if action == 'start_session':
                return self._start_session(request, data)
            elif action == 'message':
                return self._process_message(request, data)
            elif action == 'end_session':
                return self._end_session(request, data)
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

    def _start_session(self, request, data: Dict[str, Any]) -> Response:
        """Start a new HelpBot session."""
        try:
            # Capture current context
            context = self.context_service.capture_context(
                user=request.user,
                request=request,
                additional_context=data.get('context', {})
            )

            # Start session
            session = self.conversation_service.start_session(
                user=request.user,
                session_type=data.get('session_type', 'general_help'),
                context_data=data.get('context_data', {}),
                language=data.get('language', 'en')
            )

            # Get session history
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
        try:
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

            # Get session
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

            # Update context if provided
            if 'context' in data:
                self.context_service.capture_context(
                    user=request.user,
                    request=request,
                    session=session,
                    additional_context=data['context']
                )

            # Process message
            result = self.conversation_service.process_message(
                session=session,
                user_message=message,
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
        try:
            session_id = data.get('session_id')
            satisfaction_rating = data.get('satisfaction_rating')

            if not session_id:
                return Response(
                    {'error': 'session_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get session
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

            # End session
            success = self.conversation_service.end_session(
                session=session,
                satisfaction_rating=satisfaction_rating
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

    def get(self, request):
        """Get active session information."""
        try:
            # Get active session for user
            active_session = HelpBotSession.objects.filter(
                user=request.user,
                current_state__in=[
                    HelpBotSession.StateChoices.ACTIVE,
                    HelpBotSession.StateChoices.WAITING
                ]
            ).first()

            if not active_session:
                return Response({
                    'has_active_session': False,
                    'session': None
                })

            # Get session history
            history = self.conversation_service.get_session_history(active_session)

            return Response({
                'has_active_session': True,
                'session': {
                    'session_id': str(active_session.session_id),
                    'session_type': active_session.session_type,
                    'current_state': active_session.current_state,
                    'language': active_session.language,
                    'voice_enabled': active_session.voice_enabled,
                    'total_messages': active_session.total_messages,
                    'messages': history
                }
            })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error getting HelpBot session info: {e}", exc_info=True)
            return Response(
                {'error': 'Could not get session info'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HelpBotFeedbackView(APIView):
    """Handle user feedback for HelpBot interactions."""

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.conversation_service = HelpBotConversationService()

    def post(self, request):
        """Submit feedback for a HelpBot message or session."""
        try:
            data = request.data

            session_id = data.get('session_id')
            message_id = data.get('message_id')
            feedback_type = data.get('feedback_type')
            rating = data.get('rating')
            comment = data.get('comment', '').strip()

            # Validate required fields
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

            # Validate feedback type
            valid_types = [choice[0] for choice in HelpBotFeedback.FeedbackTypeChoices.choices]
            if feedback_type not in valid_types:
                return Response(
                    {'error': f'Invalid feedback_type. Valid options: {valid_types}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get session
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

            # Submit feedback
            success = self.conversation_service.add_feedback(
                session=session,
                message_id=message_id or '',
                feedback_type=feedback_type,
                rating=rating,
                comment=comment
            )

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


class HelpBotKnowledgeView(APIView):
    """Access HelpBot knowledge base."""

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.knowledge_service = HelpBotKnowledgeService()

    def get(self, request):
        """Search knowledge base or get specific article."""
        try:
            knowledge_id = request.query_params.get('id')

            if knowledge_id:
                # Get specific knowledge article
                article = self.knowledge_service.get_knowledge_by_id(knowledge_id)
                if not article:
                    return Response(
                        {'error': 'Article not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response({'article': article})

            else:
                # Search knowledge base
                query = request.query_params.get('q', '').strip()
                category = request.query_params.get('category')
                limit = min(int(request.query_params.get('limit', 10)), 50)

                if not query:
                    return Response(
                        {'error': 'Query parameter "q" is required for search'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                results = self.knowledge_service.search_knowledge(
                    query=query,
                    category=category,
                    limit=limit
                )

                return Response({
                    'query': query,
                    'category': category,
                    'results': results,
                    'total': len(results)
                })

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in HelpBot knowledge view: {e}", exc_info=True)
            return Response(
                {'error': 'Could not process knowledge request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HelpBotAnalyticsView(APIView):
    """HelpBot analytics and reporting."""

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.analytics_service = HelpBotAnalyticsService()

    def get(self, request):
        """Get HelpBot analytics data."""
        try:
            # Check if user has permission for analytics
            if not (request.user.is_staff or getattr(request.user, 'isadmin', False)):
                return Response(
                    {'error': 'Permission denied. Admin access required.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            analytics_type = request.query_params.get('type', 'dashboard')
            days = min(int(request.query_params.get('days', 30)), 365)

            if analytics_type == 'dashboard':
                data = self.analytics_service.get_dashboard_data(days)
                return Response(data)

            elif analytics_type == 'insights':
                insights = self.analytics_service.generate_insights(days)
                return Response({'insights': insights})

            elif analytics_type == 'user':
                if not request.user.is_superuser:
                    # Users can only see their own analytics
                    user_analytics = self.analytics_service.get_user_analytics(request.user, days)
                    return Response(user_analytics)
                else:
                    # Superusers can see any user's analytics with user_id param
                    user_id = request.query_params.get('user_id')
                    if user_id:
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        try:
                            target_user = User.objects.get(id=user_id)
                            user_analytics = self.analytics_service.get_user_analytics(target_user, days)
                            return Response(user_analytics)
                        except User.DoesNotExist:
                            return Response(
                                {'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND
                            )
                    else:
                        user_analytics = self.analytics_service.get_user_analytics(request.user, days)
                        return Response(user_analytics)

            else:
                return Response(
                    {'error': 'Invalid analytics type. Use: dashboard, insights, or user'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in HelpBot analytics view: {e}", exc_info=True)
            return Response(
                {'error': 'Could not get analytics data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
                response_data['context'] = {
                    'current_url': current_context.current_url,
                    'page_title': current_context.page_title,
                    'app_name': current_context.app_name,
                    'view_name': current_context.view_name,
                    'timestamp': current_context.timestamp.isoformat(),
                }

            return Response(response_data)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error getting HelpBot context: {e}", exc_info=True)
            return Response(
                {'error': 'Could not get context'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Traditional Django views for integration with existing templates
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
            import json

            # Parse JSON data
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({
                    'error': 'Invalid JSON data'
                }, status=400)

            action = data.get('action')

            if action == 'start_session':
                return self._handle_start_session(request, data)
            elif action == 'send_message':
                return self._handle_send_message(request, data)
            elif action == 'get_suggestions':
                return self._handle_get_suggestions(request, data)
            else:
                return JsonResponse({
                    'error': 'Invalid action'
                }, status=400)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in HelpBot widget view: {e}", exc_info=True)
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)

    def _handle_start_session(self, request, data):
        """Handle session start from widget."""
        try:
            # Capture context from current page
            context = self.context_service.capture_context(
                user=request.user,
                request=request,
                additional_context={
                    'current_url': data.get('current_url', ''),
                    'page_title': data.get('page_title', ''),
                    'widget_context': True
                }
            )

            # Start session
            session = self.conversation_service.start_session(
                user=request.user,
                session_type=data.get('session_type', 'general_help'),
                context_data={'widget_initiated': True},
                language=data.get('language', 'en')
            )

            # Get welcome message
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

    def _handle_send_message(self, request, data):
        """Handle message from widget."""
        try:
            session_id = data.get('session_id')
            message = data.get('message', '').strip()

            if not session_id or not message:
                return JsonResponse({
                    'success': False,
                    'error': 'Session ID and message are required'
                }, status=400)

            # Get session
            try:
                session = HelpBotSession.objects.get(
                    session_id=session_id,
                    user=request.user
                )
            except HelpBotSession.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Session not found'
                }, status=404)

            # Process message
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


# Function-based views for simple endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def helpbot_health(request):
    """Health check endpoint for HelpBot services."""
    try:
        # Basic health checks
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': True,  # If we can execute this, DB is working
                'knowledge_service': True,
                'conversation_service': True,
            }
        }

        # Check knowledge service
        try:
            knowledge_service = HelpBotKnowledgeService()
            knowledge_count = knowledge_service._record_analytics('health_check', 0)
            health_status['services']['knowledge_service'] = True
        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS):
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
            'features': {
                'knowledge_search': True,
                'context_awareness': True,
                'feedback_collection': True,
                'analytics': request.user.is_staff or getattr(request.user, 'isadmin', False),
            }
        }

        return Response(config)

    except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
        logger.error(f"Error getting HelpBot config: {e}", exc_info=True)
        return Response({
            'error': 'Could not get configuration'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Traditional Django template views
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