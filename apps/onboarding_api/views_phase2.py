"""
Phase 2 Views for Enhanced Conversational Onboarding API
Dual-LLM responses, streaming, and knowledge management
"""
import json
import time
import uuid
from datetime import datetime
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

    ConversationSession,
    LLMRecommendation,
    AuthoritativeKnowledge,
    AuthoritativeKnowledgeChunk
)
    ConversationStatusSerializer,
    LLMRecommendationSerializer,
    AuthoritativeKnowledgeSerializer,
)
from .services.llm import get_llm_service, get_checker_service, get_consensus_engine
from .services.knowledge import get_knowledge_service

import logging

logger = logging.getLogger(__name__)


class EnhancedConversationProcessView(APIView):
    """
    Phase 2 Enhanced conversation processing with dual-LLM support
    POST /api/v1/onboarding/conversation/{id}/process-enhanced/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
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

        # Generate trace ID for this request
        trace_id = str(uuid.uuid4())

        # Check if processing should be async
        should_process_async = self._should_process_async_enhanced(data['user_input'], session)

        if should_process_async:
            # Import here to avoid circular imports
            from background_tasks.onboarding_tasks_phase2 import process_conversation_step_enhanced

            process_conversation_step_enhanced.delay(
                str(conversation_id),
                data['user_input'],
                data.get('context', {}),
                trace_id,
                request.user.id
            )

            status_url = request.build_absolute_uri(
                f'/api/v1/onboarding/conversation/{conversation_id}/status/'
            )

            return Response({
                "status": "processing",
                "status_url": status_url,
                "trace_id": trace_id,
                "estimated_completion": "20-60 seconds"
            }, status=status.HTTP_202_ACCEPTED)

        else:
            # Process synchronously with dual-LLM
            try:
                result = self._process_dual_llm_synchronously(
                    session, data['user_input'], data.get('context', {}), trace_id
                )
                return Response(result)
            except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Error processing conversation {conversation_id}: {str(e)}")
                return Response(
                    {"error": "Failed to process conversation", "trace_id": trace_id},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    def _should_process_async_enhanced(self, user_input: str, session: ConversationSession) -> bool:
        """Enhanced async decision logic"""
        # Always use async if checker LLM is enabled
        if getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False):
            return True

        # Check complexity indicators
        complexity_indicators = [
            len(user_input) > 200,
            len(session.collected_data) > 5,
            'complex' in user_input.lower(),
            'multiple' in user_input.lower(),
        ]

        return sum(complexity_indicators) >= 2

    def _process_dual_llm_synchronously(
        self,
        session: ConversationSession,
        user_input: str,
        context: Dict[str, Any],
        trace_id: str
    ) -> Dict[str, Any]:
        """Process with dual-LLM approach synchronously"""
        start_time = time.time()

        # Update session state
        session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
        session.save()

        # Get services
        llm_service = get_llm_service()
        checker_service = get_checker_service()
        knowledge_service = get_knowledge_service()
        consensus_engine = get_consensus_engine()

        # Step 1: Retrieve knowledge for grounding
        knowledge_hits = []
        try:
            knowledge_hits = knowledge_service.retrieve_grounded_context(
                query=user_input,
                top_k=5,
                authority_filter=['high', 'official']
            )
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.warning(f"Knowledge retrieval failed: {str(e)}")

        # Step 2: Generate with Maker LLM
        maker_result = llm_service.process_conversation_step(
            session=session,
            user_input=user_input,
            context=context
        )

        # Step 3: Validate with Checker LLM (if enabled)
        checker_result = None
        if checker_service:
            checker_result = checker_service.validate_recommendations(
                maker_output=maker_result,
                context=context
            )

        # Step 4: Create consensus
        consensus = consensus_engine.create_consensus(
            maker_output=maker_result,
            checker_output=checker_result or {},
            knowledge_hits=knowledge_hits,
            context=context
        )

        # Step 5: Create and store recommendation
        processing_time = int((time.time() - start_time) * 1000)

        recommendation = LLMRecommendation.objects.create(
            session=session,
            maker_output=maker_result,
            checker_output=checker_result,
            consensus=consensus,
            authoritative_sources=knowledge_hits,
            confidence_score=consensus.get('consensus_confidence', 0.0),
            status=LLMRecommendation.StatusChoices.VALIDATED,
            latency_ms=processing_time,
            trace_id=trace_id,
            eval_scores={
                'maker_confidence': maker_result.get('confidence_score', 0.0),
                'checker_confidence': checker_result.get('confidence_adjustment', 0.0) if checker_result else 0.0,
                'consensus_confidence': consensus.get('consensus_confidence', 0.0)
            }
        )

        # Update session
        session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
        session.collected_data.update({
            'trace_id': trace_id,
            'processed_at': datetime.now().isoformat(),
            'recommendation_id': str(recommendation.recommendation_id)
        })
        session.save()

        # Format Phase 2 response
        return {
            "maker_llm_output": maker_result,
            "checker_validation": checker_result,
            "consensus_confidence": consensus.get('consensus_confidence', 0.0),
            "trace_id": trace_id,
            "status": "validated",
            "enhanced_recommendations": consensus.get('final_recommendation', {}),
            "reasoning": consensus.get('reasoning', []),
            "knowledge_grounding": knowledge_hits[:3],  # Top 3 sources
            "decision": consensus.get('decision', 'needs_review'),
            "processing_time_ms": processing_time
        }


class ConversationEventsView(APIView):
    """
    Streaming/polling endpoint for conversation progress
    GET /api/v1/onboarding/conversation/{id}/events/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        session = get_object_or_404(
            ConversationSession,
            session_id=conversation_id,
            user=request.user
        )

        # Check if Server-Sent Events are enabled
        if getattr(settings, 'ENABLE_ONBOARDING_SSE', False):
            return self._stream_events(session)
        else:
            # Long polling fallback
            return self._long_poll_events(session)

    def _stream_events(self, session: ConversationSession):
        """Stream events using Server-Sent Events"""
        def event_stream():
            last_check = datetime.now()
            max_duration = 300  # 5 minutes max
            check_interval = 2  # Check every 2 seconds

            for _ in range(max_duration // check_interval):
                # Refresh session
                session.refresh_from_db()

                # Get latest recommendation
                latest_rec = LLMRecommendation.objects.filter(
                    session=session
                ).order_by('-cdtz').first()

                event_data = {
                    "timestamp": datetime.now().isoformat(),
                    "session_state": session.current_state,
                    "progress": self._calculate_progress(session),
                }

                if latest_rec:
                    event_data.update({
                        "recommendation_status": latest_rec.status,
                        "confidence": latest_rec.confidence_score,
                        "trace_id": latest_rec.trace_id
                    })

                    # Send final results if completed
                    if latest_rec.status == LLMRecommendation.StatusChoices.COMPLETED:
                        event_data["final_recommendations"] = latest_rec.consensus
                        yield f"data: {json.dumps(event_data)}\n\n"
                        break

                yield f"data: {json.dumps(event_data)}\n\n"

                if session.current_state in [
                    ConversationSession.StateChoices.COMPLETED,
                    ConversationSession.StateChoices.ERROR,
                    ConversationSession.StateChoices.CANCELLED
                ]:
                    break

                time.sleep(check_interval)

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def _long_poll_events(self, session: ConversationSession):
        """Long polling fallback"""
        max_wait = 30  # 30 seconds max
        check_interval = 1
        start_time = time.time()

        while time.time() - start_time < max_wait:
            session.refresh_from_db()

            if session.current_state != ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS:
                break

            time.sleep(check_interval)

        # Return current status
        return Response({
            "session_state": session.current_state,
            "progress": self._calculate_progress(session),
            "next_poll_delay": 5  # Suggest 5-second delay for next poll
        })

    def _calculate_progress(self, session: ConversationSession) -> float:
        """Calculate progress percentage"""
        state_progress = {
            ConversationSession.StateChoices.STARTED: 0.1,
            ConversationSession.StateChoices.IN_PROGRESS: 0.3,
            ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS: 0.6,
            ConversationSession.StateChoices.AWAITING_USER_APPROVAL: 0.9,
            ConversationSession.StateChoices.COMPLETED: 1.0,
        }
        return state_progress.get(session.current_state, 0.0)


class KnowledgeDocumentViewSet(ModelViewSet):
    """
    Staff-only knowledge document management
    """
    queryset = AuthoritativeKnowledge.objects.all()
    serializer_class = AuthoritativeKnowledgeSerializer
    permission_classes = [IsAdminUser]

    def create(self, request):
        """Upload new knowledge document"""
        if not getattr(settings, 'ENABLE_ONBOARDING_KB', False):
            return Response(
                {"error": "Knowledge base management is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Handle document upload with chunking
        try:
            knowledge_service = get_knowledge_service()

            data = request.data
            doc_id = knowledge_service.add_document_with_chunking(
                source_org=data.get('source_organization'),
                title=data.get('document_title'),
                content_summary=data.get('content_summary'),
                full_content=data.get('full_content', ''),
                authority_level=data.get('authority_level', 'medium'),
                version=data.get('document_version', ''),
                tags=data.get('tags', {})
            )

            return Response({
                "knowledge_id": doc_id,
                "message": "Document uploaded and chunked successfully"
            }, status=status.HTTP_201_CREATED)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error uploading document: {str(e)}")
            return Response(
                {"error": "Failed to upload document"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def embed_knowledge_document(request, knowledge_id):
    """
    Embed existing knowledge document
    POST /api/v1/onboarding/knowledge/documents/{id}/embed/
    """
    if not getattr(settings, 'ENABLE_ONBOARDING_KB', False):
        return Response(
            {"error": "Knowledge base management is not enabled"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        # Import embedding task
        from background_tasks.onboarding_tasks_phase2 import embed_knowledge_document_task

        full_content = request.data.get('full_content', '')
        if not full_content:
            return Response(
                {"error": "full_content is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enqueue embedding task
        task_id = str(uuid.uuid4())
        embed_knowledge_document_task.delay(knowledge_id, full_content, task_id)

        return Response({
            "message": "Embedding task enqueued",
            "task_id": task_id,
            "status_url": f"/api/v1/onboarding/tasks/{task_id}/status/"
        }, status=status.HTTP_202_ACCEPTED)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error enqueuing embedding task: {str(e)}")
        return Response(
            {"error": "Failed to enqueue embedding task"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_knowledge_enhanced(request):
    """
    Enhanced knowledge search with filtering
    GET /api/v1/onboarding/knowledge/search/
    """
    try:
        query = request.GET.get('q', '')
        authority_level = request.GET.getlist('authority_level')
        max_results = int(request.GET.get('max_results', 10))

        if not query:
            return Response(
                {"error": "Query parameter 'q' is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        knowledge_service = get_knowledge_service()

        # Use enhanced search with re-ranking
        results = knowledge_service.search_with_reranking(
            query=query,
            top_k=max_results,
            authority_filter=authority_level if authority_level else None
        )

        return Response({
            "results": results,
            "query": query,
            "total_results": len(results)
        })

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error searching knowledge: {str(e)}")
        return Response(
            {"error": "Knowledge search failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ConversationEscalationView(APIView):
    """
    Escalate conversation for human review with automatic helpdesk ticket creation
    POST /api/v1/onboarding/conversation/{id}/escalate/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        session = get_object_or_404(
            ConversationSession,
            session_id=conversation_id,
            user=request.user
        )

        escalation_reason = request.data.get('reason', 'User requested human review')
        context_snapshot = request.data.get('context_snapshot', {})
        urgency = request.data.get('urgency', 'medium')  # low, medium, high

        try:
            with transaction.atomic():
                # Update session state
                session.current_state = ConversationSession.StateChoices.ERROR  # Using ERROR as escalation state
                session.error_message = f"Escalated: {escalation_reason}"

                # Store escalation context
                escalation_context = {
                    'reason': escalation_reason,
                    'escalated_at': datetime.now().isoformat(),
                    'escalated_by': str(request.user),
                    'urgency': urgency,
                    'context_snapshot': context_snapshot,
                    'helpdesk_ticket_created': False
                }
                session.context_data.update({'escalation': escalation_context})

                # Create escalation record in latest recommendation if exists
                latest_rec = LLMRecommendation.objects.filter(session=session).order_by('-cdtz').first()
                if latest_rec:
                    latest_rec.status = LLMRecommendation.StatusChoices.NEEDS_REVIEW
                    latest_rec.modifications.update({
                        'escalation_reason': escalation_reason,
                        'escalated_at': datetime.now().isoformat()
                    })
                    latest_rec.save()

                # Create helpdesk ticket for escalated conversation
                helpdesk_ticket = self._create_escalation_ticket(
                    session=session,
                    escalation_reason=escalation_reason,
                    urgency=urgency,
                    escalated_by=request.user
                )

                # Update escalation context with ticket information
                if helpdesk_ticket:
                    escalation_context.update({
                        'helpdesk_ticket_created': True,
                        'ticket_number': helpdesk_ticket.ticketno,
                        'ticket_uuid': str(helpdesk_ticket.uuid)
                    })
                    session.context_data['escalation'] = escalation_context
                    session.save()

                    logger.info(
                        f"Conversation {conversation_id} escalated with ticket {helpdesk_ticket.ticketno}",
                        extra={
                            'user_id': request.user.id,
                            'session_id': conversation_id,
                            'ticket_number': helpdesk_ticket.ticketno,
                            'escalation_reason': escalation_reason
                        }
                    )

                    return Response({
                        "success": True,
                        "message": "Conversation escalated successfully",
                        "escalation_details": {
                            "reason": escalation_reason,
                            "escalated_at": escalation_context['escalated_at'],
                            "urgency": urgency,
                            "helpdesk_ticket": {
                                "ticket_number": helpdesk_ticket.ticketno,
                                "ticket_uuid": str(helpdesk_ticket.uuid),
                                "status": helpdesk_ticket.status,
                                "priority": helpdesk_ticket.priority
                            }
                        }
                    })
                else:
                    # Ticket creation failed, but escalation still recorded
                    session.save()
                    logger.warning(
                        f"Conversation {conversation_id} escalated but ticket creation failed",
                        extra={'user_id': request.user.id, 'session_id': conversation_id}
                    )

                    return Response({
                        "success": True,
                        "message": "Conversation escalated (manual ticket creation required)",
                        "escalation_details": {
                            "reason": escalation_reason,
                            "escalated_at": escalation_context['escalated_at'],
                            "urgency": urgency,
                            "helpdesk_ticket": None
                        }
                    }, status=status.HTTP_202_ACCEPTED)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error escalating conversation {conversation_id}: {str(e)}")
            return Response(
                {"error": "Failed to escalate conversation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _create_escalation_ticket(self, session, escalation_reason, urgency, escalated_by):
        """
        Create a helpdesk ticket for an escalated conversation

        Args:
            session: ConversationSession instance
            escalation_reason: Reason for escalation
            urgency: Urgency level (low, medium, high)
            escalated_by: User who escalated

        Returns:
            Ticket instance or None if creation failed
        """
        try:
            from apps.y_helpdesk.models import Ticket
            from django.utils import timezone
            import uuid

            # Map urgency to priority
            urgency_priority_map = {
                'low': Ticket.Priority.LOW,
                'medium': Ticket.Priority.MEDIUM,
                'high': Ticket.Priority.HIGH
            }

            # Generate ticket number
            ticket_no = f"AI-ESC-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"

            # Build comprehensive ticket description
            conversation_context = self._build_escalation_context(session, escalation_reason)

            ticket = Ticket.objects.create(
                ticketno=ticket_no,
                ticketdesc=conversation_context['description'],
                client=session.client,
                bu=session.client,  # Use client as BU for now
                priority=urgency_priority_map.get(urgency, Ticket.Priority.MEDIUM),
                status=Ticket.Status.NEW,
                identifier=Ticket.Identifier.TICKET,
                performedby=escalated_by,
                ticketlog={
                    'escalation_data': {
                        'conversation_session_id': str(session.session_id),
                        'conversation_type': session.conversation_type,
                        'escalation_reason': escalation_reason,
                        'urgency': urgency,
                        'escalated_by': escalated_by.email,
                        'escalated_at': timezone.now().isoformat(),
                        'conversation_context': conversation_context,
                        'source': 'ai_conversational_onboarding'
                    }
                },
                modifieddatetime=timezone.now()
            )

            logger.info(f"Created helpdesk ticket {ticket_no} for conversation {session.session_id}")
            return ticket

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Failed to create helpdesk ticket for conversation {session.session_id}: {e}")
            return None

    def _build_escalation_context(self, session, escalation_reason):
        """Build comprehensive context for the escalation ticket"""
        try:
            # Get conversation history
            recommendations = LLMRecommendation.objects.filter(session=session).order_by('cdtz')

            description_parts = [
                f"AI Conversational Onboarding - Escalation Required",
                f"",
                f"Conversation ID: {session.session_id}",
                f"User: {session.user.email}",
                f"Client: {session.client.buname if session.client else 'N/A'}",
                f"Language: {session.language}",
                f"Type: {session.conversation_type}",
                f"",
                f"ESCALATION REASON:",
                f"{escalation_reason}",
                f"",
                f"CONVERSATION SUMMARY:",
            ]

            # Add conversation context
            if session.context_data:
                context_summary = session.context_data.get('summary', 'No summary available')
                description_parts.extend([
                    f"Context: {context_summary}",
                    f""
                ])

            # Add AI recommendations if any
            if recommendations.exists():
                description_parts.extend([
                    f"AI RECOMMENDATIONS ({recommendations.count()} total):",
                    f""
                ])

                for i, rec in enumerate(recommendations[:3], 1):  # Limit to first 3
                    description_parts.extend([
                        f"{i}. {rec.recommendation_type}",
                        f"   Status: {rec.status}",
                        f"   Confidence: {rec.confidence_score}",
                        f"   Summary: {rec.system_configuration.get('summary', 'No summary')[:100]}...",
                        f""
                    ])

                if recommendations.count() > 3:
                    description_parts.append(f"   ... and {recommendations.count() - 3} more recommendations")

            # Add escalation instructions
            description_parts.extend([
                f"",
                f"NEXT STEPS:",
                f"1. Review the conversation context and AI recommendations",
                f"2. Contact the user if additional clarification is needed",
                f"3. Either:",
                f"   - Provide manual assistance to complete the onboarding",
                f"   - Fix any issues with the AI recommendations and retry",
                f"   - Escalate to technical team if this represents an AI system issue",
                f"",
                f"User Contact: {session.user.email}",
                f"Session Details: Available in admin panel under Conversation Sessions",
            ])

            return {
                'description': '\n'.join(description_parts),
                'recommendations_count': recommendations.count(),
                'conversation_context': session.context_data,
                'user_email': session.user.email,
                'client_name': session.client.buname if session.client else None
            }

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Failed to build escalation context for {session.session_id}: {e}")
            return {
                'description': f"AI Conversational Onboarding Escalation\n\nReason: {escalation_reason}\nSession: {session.session_id}\nUser: {session.user.email}",
                'recommendations_count': 0,
                'conversation_context': {},
                'error': str(e)
            }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_task_status(request, task_id):
    """
    Get status of background task
    GET /api/v1/onboarding/tasks/{task_id}/status/
    """
    try:
        from celery.result import AsyncResult

        result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready()
        }

        if result.ready():
            if result.successful():
                response_data["result"] = result.result
            else:
                response_data["error"] = str(result.result)

        return Response(response_data)

    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error getting task status {task_id}: {str(e)}")
        return Response(
            {"error": "Failed to get task status"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )