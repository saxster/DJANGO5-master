"""
Conversation Management Views

Handles conversation lifecycle: starting sessions, processing inputs, tracking status.

Migrated from: apps/onboarding_api/views.py (lines 33-333)
Date: 2025-09-30
Refactoring: Phase 3 - God File Elimination
"""
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core_onboarding.models import ConversationSession, LLMRecommendation
from ..serializers import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

    ConversationStartSerializer,
    ConversationProcessSerializer,
    ConversationStatusSerializer,
    LLMRecommendationSerializer,
)
from ..services.llm import get_llm_service
from ..utils.security import require_tenant_scope, with_idempotency
import logging
import uuid

logger = logging.getLogger(__name__)


class ConversationStartView(APIView):
    """Start a new conversational onboarding session"""
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('create_session')
    @with_idempotency('create_session')
    def post(self, request):
        """Create new conversation session with race condition protection"""
        if not self._check_feature_enabled():
            return self._feature_disabled_response()

        serializer = ConversationStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        if not self._validate_user_client(request.user):
            return self._missing_client_response()

        # Handle session creation with advisory lock
        return self._create_session_with_lock(request, data)

    def _check_feature_enabled(self):
        """Check if conversational onboarding is enabled"""
        return settings.ENABLE_CONVERSATIONAL_ONBOARDING

    def _feature_disabled_response(self):
        """Return feature disabled error response"""
        return Response(
            {"error": "Conversational onboarding is not enabled"},
            status=status.HTTP_403_FORBIDDEN
        )

    def _validate_user_client(self, user):
        """Validate that user has a client relation"""
        return hasattr(user, 'client') and user.client

    def _missing_client_response(self):
        """Return missing client error response"""
        return Response(
            {"error": "User must be associated with a client to use conversational onboarding"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def _create_session_with_lock(self, request, data):
        """Create session with PostgreSQL advisory lock protection"""
        from .utils.concurrency import advisory_lock

        lock_context = advisory_lock(
            request.user,
            client_id=request.user.client.id,
            lock_type="session_creation"
        )

        with lock_context as lock_acquired:
            if not lock_acquired:
                return self._lock_unavailable_response()

            return self._handle_session_creation(request, data)

    def _lock_unavailable_response(self):
        """Return lock unavailable error response"""
        return Response({
            "error": "Unable to acquire session lock",
            "message": "Another session creation is in progress. Please try again in a moment.",
            "retry_after": 5
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    def _handle_session_creation(self, request, data):
        """Handle session creation logic"""
        existing_session = self._check_existing_session(request.user)

        if existing_session:
            return self._handle_existing_session(existing_session, data)

        return self._create_new_session(request, data)

    def _check_existing_session(self, user):
        """Check for existing active sessions"""
        active_states = [
            ConversationSession.StateChoices.STARTED,
            ConversationSession.StateChoices.IN_PROGRESS,
            ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS,
            ConversationSession.StateChoices.AWAITING_USER_APPROVAL
        ]

        return ConversationSession.objects.filter(
            user=user,
            client=user.client,
            current_state__in=active_states
        ).first()

    def _handle_existing_session(self, session, data):
        """Handle existing active session"""
        if data.get('resume_existing', False):
            return self._resume_session_response(session)

        if self._is_session_stale(session):
            self._close_stale_session(session)
            return None

        return self._active_session_conflict_response(session)

    def _resume_session_response(self, session):
        """Return response for resumed session"""
        return Response({
            "conversation_id": str(session.session_id),
            "resumed": True,
            "current_state": session.current_state,
            "message": "Resumed existing conversation session"
        })

    def _is_session_stale(self, session):
        """Check if session is stale (>30 minutes old)"""
        from datetime import timedelta
        session_age = timezone.now() - session.mdtz
        return session_age > timedelta(minutes=30)

    def _close_stale_session(self, session):
        """Close stale session"""
        session.current_state = ConversationSession.StateChoices.CANCELLED
        session.error_message = "Session auto-closed due to inactivity"
        session.save()
        logger.info(f"Auto-closed stale session {session.session_id}")

    def _active_session_conflict_response(self, session):
        """Return conflict response for active session"""
        return Response({
            "error": "An active conversation session already exists",
            "existing_session_id": str(session.session_id),
            "session_state": session.current_state,
            "message": "Please complete or cancel the existing session before starting a new one"
        }, status=status.HTTP_409_CONFLICT)

    def _create_new_session(self, request, data):
        """Create new conversation session"""
        session = ConversationSession.objects.create(
            user=request.user,
            client=request.user.client,
            language=data.get('language', 'en'),
            conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
            context_data=data.get('client_context', {}),
            current_state=ConversationSession.StateChoices.STARTED
        )

        logger.info(
            f"Created new conversation session {session.session_id}",
            extra={
                'user_id': request.user.id,
                'client_id': request.user.client.id,
                'session_id': str(session.session_id)
            }
        )

        return self._enhance_session_with_llm(session, data, request)

    def _enhance_session_with_llm(self, session, data, request):
        """Enhance session with LLM-generated questions"""
        try:
            llm_service = get_llm_service()

            enhanced_context = llm_service.enhance_context(
                user_input=data.get('initial_input', ''),
                context=data.get('client_context', {}),
                user=request.user
            )

            initial_questions = llm_service.generate_questions(
                context=enhanced_context,
                conversation_type=session.conversation_type
            )

            session.context_data.update(enhanced_context)
            session.collected_data = {"initial_questions": initial_questions}
            session.current_state = ConversationSession.StateChoices.IN_PROGRESS
            session.save()

            return self._success_response(session, enhanced_context, initial_questions)

        except DATABASE_EXCEPTIONS as e:
            return self._handle_llm_error(session, e)

    def _success_response(self, session, context, questions):
        """Return success response"""
        return Response({
            "conversation_id": session.session_id,
            "enhanced_understanding": context,
            "questions": questions,
            "context": session.context_data
        })

    def _handle_llm_error(self, session, error):
        """Handle LLM service errors"""
        logger.error(f"Error starting conversation {session.session_id}: {str(error)}")
        session.current_state = ConversationSession.StateChoices.ERROR
        session.error_message = str(error)
        session.save()

        return Response(
            {"error": "Failed to initialize conversation"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ConversationProcessView(APIView):
    """Process user input in a conversation"""
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('update_conversation')
    @with_idempotency('process_conversation')
    def post(self, request, conversation_id):
        """Process conversation step (sync or async based on complexity)"""
        if not settings.ENABLE_CONVERSATIONAL_ONBOARDING:
            return Response(
                {"error": "Conversational onboarding is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        session = get_object_or_404(
            ConversationSession,
            session_id=conversation_id,
            user=request.user
        )

        serializer = ConversationProcessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        if self._should_process_async(data['user_input'], session):
            return self._process_async(request, conversation_id, data)
        else:
            return self._process_sync(session, data)

    def _should_process_async(self, user_input, session):
        """Determine if processing should be async"""
        return len(user_input) > 500 or len(session.collected_data) > 10

    def _process_async(self, request, conversation_id, data):
        """Process conversation asynchronously"""
        from background_tasks.onboarding_tasks import process_conversation_step

        friendly_id = str(uuid.uuid4())
        async_result = process_conversation_step.delay(
            conversation_id,
            data['user_input'],
            data.get('context', {}),
            friendly_id
        )

        celery_task_id = async_result.id
        status_url = request.build_absolute_uri(
            f'/api/v1/onboarding/conversation/{conversation_id}/status/'
        )
        task_status_url = request.build_absolute_uri(
            f'/api/v1/onboarding/tasks/{celery_task_id}/status/'
        )

        return Response({
            "status": "processing",
            "status_url": status_url,
            "task_id": celery_task_id,
            "friendly_task_id": friendly_id,
            "task_status_url": task_status_url
        }, status=status.HTTP_202_ACCEPTED)

    def _process_sync(self, session, data):
        """Process conversation synchronously"""
        try:
            llm_service = get_llm_service()

            session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
            session.save()

            result = llm_service.process_conversation_step(
                session=session,
                user_input=data['user_input'],
                context=data.get('context', {})
            )

            session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            session.save()

            return Response({
                "enhanced_recommendations": result.get('recommendations', []),
                "consensus_confidence": result.get('confidence_score', 0.0),
                "next_steps": result.get('next_steps', [])
            })

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error processing conversation: {str(e)}")
            return Response(
                {"error": "Failed to process conversation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConversationStatusView(APIView):
    """Get conversation status and results"""
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('read_conversation')
    def get(self, request, conversation_id):
        """Retrieve conversation status and recommendations"""
        session = get_object_or_404(
            ConversationSession,
            session_id=conversation_id,
            user=request.user
        )

        recommendations = LLMRecommendation.objects.filter(
            session=session
        ).order_by('-cdtz')

        response_data = {
            "state": session.current_state,
            "status": session.current_state,
            "progress": self._calculate_progress(session),
        }

        if session.current_state == ConversationSession.StateChoices.ERROR:
            response_data["error_message"] = session.error_message

        if recommendations.exists():
            recommendation_data = [
                LLMRecommendationSerializer(rec).data for rec in recommendations
            ]
            response_data["enhanced_recommendations"] = recommendation_data
            response_data["recommendations"] = recommendation_data

        return Response(response_data)

    def _calculate_progress(self, session):
        """Calculate conversation progress percentage"""
        state_progress = {
            ConversationSession.StateChoices.STARTED: 0.1,
            ConversationSession.StateChoices.IN_PROGRESS: 0.3,
            ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS: 0.6,
            ConversationSession.StateChoices.AWAITING_USER_APPROVAL: 0.8,
            ConversationSession.StateChoices.COMPLETED: 1.0,
            ConversationSession.StateChoices.CANCELLED: 0.0,
            ConversationSession.StateChoices.ERROR: 0.0,
        }
        return state_progress.get(session.current_state, 0.0)