"""
UI Compatibility Layer for Conversational Onboarding
Bridges the gap between frontend expectations and backend API
"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.onboarding.models import ConversationSession, LLMRecommendation
from .serializers import (
    ConversationStartSerializer,
    ConversationProcessSerializer,
    LLMRecommendationSerializer,
)
from .services.llm import get_llm_service
import uuid
import logging

logger = logging.getLogger(__name__)


class UICompatConversationStartView(APIView):
    """
    UI-compatible conversation start endpoint
    Returns response in the format expected by the frontend
    POST /api/v1/onboarding/conversation/start/ui/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Start conversation with UI-compatible response"""
        serializer = ConversationStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Create conversation session
        session = ConversationSession.objects.create(
            user=request.user,
            client=data['client'],
            language=data.get('language', 'en'),
            conversation_type=data.get('type', ConversationSession.ConversationTypeChoices.INITIAL_SETUP),
            context_data=data.get('context', {})
        )

        # Return UI-expected format
        return Response({
            "session_id": str(session.session_id),
            "initial_message": "Hello! I'm here to help you set up your facility management system. Let's start with some basic information about your organization.",
            "status": "started",
            "language": session.language,
            "questions": [
                "What is the primary purpose of your facility?",
                "How many locations do you manage?",
                "What are your main operational challenges?"
            ]
        })


class UICompatConversationProcessView(APIView):
    """
    UI-compatible conversation process endpoint
    Accepts session_id in body instead of URL path
    POST /api/v1/onboarding/conversation/process/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Process conversation with UI-compatible request/response"""
        # Extract session_id from body (UI sends it this way)
        session_id = request.data.get('session_id')
        user_input = request.data.get('user_input')

        if not session_id or not user_input:
            return Response(
                {"error": "session_id and user_input are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = get_object_or_404(
                ConversationSession,
                session_id=session_id,
                user=request.user
            )
        except (ValueError, TypeError, AttributeError) as e:
            return Response(
                {"error": "Invalid session_id"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if processing should be async
        should_process_async = len(user_input) > 500 or len(session.collected_data) > 10

        if should_process_async:
            # Import here to avoid circular imports
            from background_tasks.onboarding_tasks import process_conversation_step

            # Generate friendly UUID for tracking
            friendly_id = str(uuid.uuid4())

            # Capture the actual Celery task result
            async_result = process_conversation_step.delay(
                str(session_id),
                user_input,
                request.data.get('context', {}),
                friendly_id
            )

            # Use the actual Celery task ID for status polling
            celery_task_id = async_result.id

            # Return UI-expected async response
            return Response({
                "status": "processing",
                "task_id": celery_task_id,
                "session_id": str(session_id),
                "message": "Processing your response...",
            }, status=status.HTTP_202_ACCEPTED)

        else:
            # Process synchronously
            try:
                llm_service = get_llm_service()

                # Update session state
                session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
                session.save()

                # Process with LLM
                result = llm_service.process_conversation_step(
                    session=session,
                    user_input=user_input,
                    context=request.data.get('context', {})
                )

                session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
                session.save()

                # Return UI-expected format
                return Response({
                    "ai_response": result.get('response_text', "I understand. Let me process that information."),
                    "recommendations": result.get('recommendations', []),
                    "next_question": result.get('next_question', "Is there anything else you'd like to configure?"),
                    "session_id": str(session_id),
                    "status": "ready",
                })

            except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, TimeoutError, ValueError) as e:
                logger.error(f"Error processing conversation {session_id}: {str(e)}")
                return Response(
                    {"error": "Failed to process conversation"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


class UICompatTaskStatusView(APIView):
    """
    UI-compatible task status endpoint
    Matches the URL pattern expected by the frontend
    GET /api/v1/onboarding/task-status/{task_id}/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        """Get task status in UI-expected format"""
        from celery.result import AsyncResult

        result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "state": result.state,
        }

        if result.state == 'PENDING':
            response_data.update({
                "status": "pending",
                "progress": 0,
                "message": "Task is waiting to be processed"
            })
        elif result.state == 'PROGRESS':
            response_data.update({
                "status": "processing",
                "progress": result.info.get('current', 0) / result.info.get('total', 100),
                "message": result.info.get('status', 'Processing...')
            })
        elif result.state == 'SUCCESS':
            # Get the result and format for UI
            task_result = result.info
            response_data.update({
                "status": "completed",
                "progress": 1.0,
                "message": "Processing complete",
                "result": {
                    "ai_response": task_result.get('response_text', "Processing complete."),
                    "recommendations": task_result.get('recommendations', []),
                    "next_question": task_result.get('next_question'),
                }
            })
        elif result.state == 'FAILURE':
            response_data.update({
                "status": "failed",
                "progress": 0,
                "message": str(result.info),
                "error": True
            })

        return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ui_compat_conversation_status(request, conversation_id):
    """
    UI-compatible conversation status endpoint
    GET /api/v1/onboarding/conversation/{id}/status/ui/
    """
    session = get_object_or_404(
        ConversationSession,
        session_id=conversation_id,
        user=request.user
    )

    # Get latest recommendations
    recommendations = LLMRecommendation.objects.filter(
        session=session
    ).order_by('-cdtz')[:3]

    # Calculate progress
    progress_map = {
        ConversationSession.StateChoices.STARTED: 0.1,
        ConversationSession.StateChoices.IN_PROGRESS: 0.3,
        ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS: 0.6,
        ConversationSession.StateChoices.AWAITING_USER_APPROVAL: 0.8,
        ConversationSession.StateChoices.COMPLETED: 1.0,
    }

    response_data = {
        "session_id": str(conversation_id),
        "state": session.current_state,
        "progress": progress_map.get(session.current_state, 0.0),
        "status": "active" if session.current_state not in [
            ConversationSession.StateChoices.COMPLETED,
            ConversationSession.StateChoices.CANCELLED,
            ConversationSession.StateChoices.ERROR
        ] else "inactive",
    }

    if session.current_state == ConversationSession.StateChoices.ERROR:
        response_data["error_message"] = session.error_message

    if recommendations:
        response_data["recommendations"] = [
            {
                "id": str(rec.recommendation_id),
                "type": "configuration",
                "content": rec.consensus.get('recommendation', {}) if rec.consensus else {},
                "confidence": rec.confidence_score,
                "status": rec.user_decision
            }
            for rec in recommendations
        ]

    return Response(response_data)