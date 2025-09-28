"""
Views for Conversational Onboarding API (Phase 1 MVP)
"""
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .permissions import CanApproveAIRecommendations
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from apps.onboarding.models import ConversationSession, LLMRecommendation, AuthoritativeKnowledge
    ConversationProcessSerializer,
    RecommendationApprovalSerializer,
    ConversationStatusSerializer,
    LLMRecommendationSerializer,
    AuthoritativeKnowledgeSerializer,
    TaskStatusSerializer,
)
from .services.llm import get_llm_service
from .services.knowledge import get_knowledge_service
from .utils.security import require_tenant_scope, with_idempotency
import logging
import uuid

logger = logging.getLogger(__name__)


class ConversationStartView(APIView):
    """
    Start a new conversational onboarding session
    POST /api/v1/onboarding/conversation/start/
    """
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('create_session')
    @with_idempotency('create_session')
    def post(self, request):
        if not settings.ENABLE_CONVERSATIONAL_ONBOARDING:
            return Response(
                {"error": "Conversational onboarding is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ConversationStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validate that user has a client relation
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client to use conversational onboarding"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Use PostgreSQL advisory lock to prevent race conditions during session creation
        from .utils.concurrency import advisory_lock

        with advisory_lock(request.user, client_id=request.user.client.id, lock_type="session_creation") as lock_acquired:
            if not lock_acquired:
                return Response({
                    "error": "Unable to acquire session lock",
                    "message": "Another session creation is in progress. Please try again in a moment.",
                    "retry_after": 5
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

            # Check for existing active sessions (now protected by advisory lock)
            active_states = [
                ConversationSession.StateChoices.STARTED,
                ConversationSession.StateChoices.IN_PROGRESS,
                ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS,
                ConversationSession.StateChoices.AWAITING_USER_APPROVAL
            ]

            existing_session = ConversationSession.objects.filter(
                user=request.user,
                client=request.user.client,
                current_state__in=active_states
            ).first()

            if existing_session:
                # Option 1: Return existing session info if resume requested
                if data.get('resume_existing', False):
                    return Response({
                        "conversation_id": str(existing_session.session_id),
                        "resumed": True,
                        "current_state": existing_session.current_state,
                        "message": "Resumed existing conversation session"
                    })

                # Option 2: Auto-close stale session if older than 30 minutes
                from datetime import timedelta

                session_age = timezone.now() - existing_session.mdtz
                if session_age > timedelta(minutes=30):
                    existing_session.current_state = ConversationSession.StateChoices.CANCELLED
                    existing_session.error_message = "Session auto-closed due to inactivity"
                    existing_session.save()
                    logger.info(f"Auto-closed stale session {existing_session.session_id}")
                else:
                    # Session is still active and recent
                    return Response({
                        "error": "An active conversation session already exists",
                        "existing_session_id": str(existing_session.session_id),
                        "session_state": existing_session.current_state,
                        "message": "Please complete or cancel the existing session before starting a new one"
                    }, status=status.HTTP_409_CONFLICT)

            # Create new conversation session (now race-condition safe)
            session = ConversationSession.objects.create(
                user=request.user,
                client=request.user.client,
                language=data.get('language', 'en'),
                conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
                context_data=data.get('client_context', {}),
                current_state=ConversationSession.StateChoices.STARTED
            )

            logger.info(
                f"Created new conversation session {session.session_id} for user {request.user.id}",
                extra={
                    'user_id': request.user.id,
                    'client_id': request.user.client.id,
                    'session_id': str(session.session_id),
                    'conversation_type': session.conversation_type,
                    'language': session.language
                }
            )

        # Get enhanced context from services
        try:
            llm_service = get_llm_service()
            knowledge_service = get_knowledge_service()

            enhanced_context = llm_service.enhance_context(
                user_input=data.get('initial_input', ''),
                context=data.get('client_context', {}),
                user=request.user
            )

            # Generate initial questions
            initial_questions = llm_service.generate_questions(
                context=enhanced_context,
                conversation_type=session.conversation_type
            )

            session.context_data.update(enhanced_context)
            session.collected_data = {"initial_questions": initial_questions}
            session.current_state = ConversationSession.StateChoices.IN_PROGRESS
            session.save()

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error starting conversation {session.session_id}: {str(e)}")
            session.current_state = ConversationSession.StateChoices.ERROR
            session.error_message = str(e)
            session.save()

            return Response(
                {"error": "Failed to initialize conversation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            "conversation_id": session.session_id,
            "enhanced_understanding": enhanced_context,
            "questions": initial_questions,
            "context": session.context_data
        })


class ConversationProcessView(APIView):
    """
    Process user input in a conversation
    POST /api/v1/onboarding/conversation/{id}/process/
    """
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('update_conversation')
    @with_idempotency('process_conversation')
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

        # Check if processing should be async (based on complexity)
        should_process_async = self._should_process_async(data['user_input'], session)

        if should_process_async:
            # Import here to avoid circular imports
            from background_tasks.onboarding_tasks import process_conversation_step

            # Generate a friendly UUID for tracking
            friendly_id = str(uuid.uuid4())

            # Capture the actual Celery task result
            async_result = process_conversation_step.delay(
                conversation_id,
                data['user_input'],
                data.get('context', {}),
                friendly_id
            )

            # Use the actual Celery task ID for status polling
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

        else:
            # Process synchronously
            try:
                result = self._process_synchronously(session, data['user_input'], data.get('context', {}))
                return Response(result)
            except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Error processing conversation {conversation_id}: {str(e)}")
                return Response(
                    {"error": "Failed to process conversation"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    def _should_process_async(self, user_input, session):
        """Determine if processing should be async based on complexity"""
        # Simple heuristics for MVP - can be enhanced later
        return len(user_input) > 500 or len(session.collected_data) > 10

    def _process_synchronously(self, session, user_input, context):
        """Process conversation synchronously"""
        llm_service = get_llm_service()

        # Update session state
        session.current_state = ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS
        session.save()

        # Process with LLM
        result = llm_service.process_conversation_step(
            session=session,
            user_input=user_input,
            context=context
        )

        session.current_state = ConversationSession.StateChoices.AWAITING_USER_APPROVAL
        session.save()

        return {
            "enhanced_recommendations": result.get('recommendations', []),
            "consensus_confidence": result.get('confidence_score', 0.0),
            "next_steps": result.get('next_steps', [])
        }


class ConversationStatusView(APIView):
    """
    Get conversation status and results
    GET /api/v1/onboarding/conversation/{id}/status/
    """
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('read_conversation')
    def get(self, request, conversation_id):
        session = get_object_or_404(
            ConversationSession,
            session_id=conversation_id,
            user=request.user
        )

        # Get latest recommendations
        recommendations = LLMRecommendation.objects.filter(
            session=session
        ).order_by('-cdtz')

        response_data = {
            "state": session.current_state,
            "status": session.current_state,  # UI compatibility
            "progress": self._calculate_progress(session),
        }

        if session.current_state == ConversationSession.StateChoices.ERROR:
            response_data["error_message"] = session.error_message

        if recommendations.exists():
            recommendation_data = [
                LLMRecommendationSerializer(rec).data for rec in recommendations
            ]
            response_data["enhanced_recommendations"] = recommendation_data
            response_data["recommendations"] = recommendation_data  # UI compatibility

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


class RecommendationApprovalView(APIView):
    """
    Approve or reject AI recommendations with security controls

    POST /api/v1/onboarding/recommendations/approve/

    SECURITY: This endpoint can modify business-critical data (Bt, Shift, TypeAssist).
    Access is restricted to authorized personnel only through CanApproveAIRecommendations.

    All approval attempts and applications are comprehensively audited.
    """
    permission_classes = [CanApproveAIRecommendations]

    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @require_tenant_scope('approve_recommendations')
    @with_idempotency('approve_recommendations')
    def post(self, request):
        # Import security logger
        from .permissions import security_logger

        if not settings.ENABLE_CONVERSATIONAL_ONBOARDING:
            security_logger.log_security_violation(
                request.user,
                'ai_recommendation_approval',
                'conversational_onboarding_disabled'
            )
            return Response(
                {"error": "Conversational onboarding is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = RecommendationApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            security_logger.log_security_violation(
                request.user,
                'ai_recommendation_approval',
                f'invalid_data: {serializer.errors}'
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        session_id = data.get('session_id')

        # SECURITY: Validate tenant scoping for approval process
        if session_id and not request.user.is_superuser:
            try:
                from apps.onboarding.models import ConversationSession
                conversation_session = ConversationSession.objects.get(session_id=session_id)

                # Check that approver's client matches session client
                if hasattr(request.user, 'client') and request.user.client:
                    if conversation_session.client != request.user.client:
                        security_logger.log_security_violation(
                            request.user,
                            'ai_recommendation_approval',
                            f'tenant_boundary_violation: user_client={request.user.client.id}, session_client={conversation_session.client.id}'
                        )
                        return Response(
                            {
                                "error": "Access denied: You can only approve recommendations for your organization",
                                "code": "TENANT_BOUNDARY_VIOLATION"
                            },
                            status=status.HTTP_403_FORBIDDEN
                        )
                else:
                    # User has no client association - this shouldn't happen for approval users
                    security_logger.log_security_violation(
                        request.user,
                        'ai_recommendation_approval',
                        'no_client_association'
                    )
                    return Response(
                        {
                            "error": "Access denied: User must be associated with a client",
                            "code": "NO_CLIENT_ASSOCIATION"
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
            except ConversationSession.DoesNotExist:
                security_logger.log_security_violation(
                    request.user,
                    'ai_recommendation_approval',
                    f'invalid_session_id: {session_id}'
                )
                return Response(
                    {
                        "error": "Invalid session ID",
                        "code": "INVALID_SESSION"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Log approval attempt for security audit
        security_logger.log_approval_attempt(
            request.user,
            session_id,
            data,
            'initiated'
        )

        try:
            # Import integration adapter and models
            from .integration.mapper import IntegrationAdapter
            from apps.onboarding.models import ConversationSession

            # Get the conversation session if session_id provided
            conversation_session = None
            if session_id:
                try:
                    conversation_session = ConversationSession.objects.get(session_id=session_id)
                except ConversationSession.DoesNotExist:
                    logger.warning(f"ConversationSession {session_id} not found, proceeding without changeset tracking")

            adapter = IntegrationAdapter()

            # Create changeset for tracking changes (if not dry run and session exists)
            changeset = None
            if not data['dry_run'] and conversation_session:
                changeset = adapter.create_changeset(
                    conversation_session=conversation_session,
                    approved_by=request.user,
                    description=f"AI Recommendations Applied - {len(data['approved_items'])} items approved"
                )
                logger.info(f"Created changeset {changeset.changeset_id} for approval")

                # Check if two-person approval is required
                if changeset.requires_two_person_approval():
                    # Create primary approval request
                    request_meta = {
                        'ip_address': self._get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'correlation_id': getattr(request, '_correlation_id', None)
                    }

                    primary_approval = changeset.create_approval_request(
                        approver=request.user,
                        approval_level='primary',
                        request_meta=request_meta
                    )

                    # Auto-assign secondary approver if needed
                    secondary_approval = changeset.auto_assign_secondary_approver(
                        primary_approver=request.user,
                        request_meta=request_meta
                    )

                    # Send webhook notification for secondary approval requirement
                    if getattr(settings, 'ENABLE_WEBHOOK_NOTIFICATIONS', False) and secondary_approval:
                        try:
                            from .services.notifications import notify_approval_pending

                            approval_url = request.build_absolute_uri(
                                f'/api/v1/onboarding/approvals/{secondary_approval.id}/decide/'
                            )

                            notify_approval_pending(
                                session_id=str(conversation_session.session_id),
                                changeset_id=str(changeset.changeset_id),
                                approver_email=secondary_approval.approver.email,
                                client_name=conversation_session.client.buname,
                                approval_level='secondary',
                                risk_score=changeset.calculate_risk_score(),
                                changes_count=len(data['approved_items']),
                                approval_url=approval_url
                            )
                        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                            logger.warning(f"Failed to send approval notification: {str(e)}")

                    # Two-person approval required - don't apply changes yet
                    return Response({
                        "two_person_approval_required": True,
                        "changeset_id": str(changeset.changeset_id),
                        "risk_score": changeset.calculate_risk_score(),
                        "approval_status": changeset.get_approval_status(),
                        "primary_approval_id": str(primary_approval.id) if primary_approval else None,
                        "secondary_approval_id": str(secondary_approval.id) if secondary_approval else None,
                        "message": "High-risk changeset requires secondary approval before applying",
                        "next_action": "Awaiting secondary approver decision"
                    })

            result = adapter.apply_recommendations(
                approved_items=data['approved_items'],
                rejected_items=data['rejected_items'],
                reasons=data['reasons'],
                modifications=data['modifications'],
                dry_run=data['dry_run'],
                user=request.user,
                changeset=changeset  # Pass changeset for tracking
            )

            # Log successful application
            security_logger.log_application_result(
                request.user,
                session_id,
                result.get('changes', []),
                success=True
            )

            # Log final approval result
            security_logger.log_approval_attempt(
                request.user,
                session_id,
                data,
                'completed_successfully'
            )

            # Send webhook notification for successful changeset application
            if getattr(settings, 'ENABLE_WEBHOOK_NOTIFICATIONS', False) and changeset:
                try:
                    from .services.notifications import notify_changeset_applied

                    notify_changeset_applied(
                        session_id=str(conversation_session.session_id) if conversation_session else session_id,
                        changeset_id=str(changeset.changeset_id),
                        applied_by_email=request.user.email,
                        client_name=conversation_session.client.buname if conversation_session else 'Unknown',
                        changes_applied=len(result.get('changes', [])),
                        rollback_available=changeset.can_rollback()
                    )
                except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                    logger.warning(f"Failed to send changeset applied notification: {str(e)}")

            return Response({
                "system_configuration": result.get('configuration', {}),
                "implementation_plan": result.get('plan', []),
                "learning_update_applied": result.get('learning_applied', False),
                "audit_trail_id": result.get('audit_trail_id'),  # For rollback reference
                "changeset_id": str(changeset.changeset_id) if changeset else None,  # Changeset for rollback
                "changes_applied": len(result.get('changes', [])),
                "rollback_available": changeset.can_rollback() if changeset else False
            })

        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            # Log failed application for security monitoring
            security_logger.log_application_result(
                request.user,
                session_id,
                [],
                success=False,
                error=e
            )

            security_logger.log_approval_attempt(
                request.user,
                session_id,
                data,
                f'failed: {str(e)}'
            )

            logger.error(
                f"Error applying AI recommendations for user {request.user.id}: {str(e)}",
                extra={
                    'user_id': request.user.id,
                    'session_id': session_id,
                    'approved_items_count': len(data.get('approved_items', [])),
                    'rejected_items_count': len(data.get('rejected_items', [])),
                }
            )

            return Response(
                {
                    "error": "Failed to apply recommendations",
                    "audit_trail_id": None,
                    "support_reference": str(session_id) if session_id else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SecondaryApprovalView(APIView):
    """
    Handle secondary approvals for high-risk changesets implementing two-person rule.

    POST /api/v1/onboarding/approvals/{approval_id}/decide/

    SECURITY: This endpoint handles the second approval for high-risk changes.
    Access is restricted to authorized secondary approvers.
    """
    permission_classes = [CanApproveAIRecommendations]

    def post(self, request, approval_id):
        from .permissions import security_logger
        from apps.onboarding.models import ChangeSetApproval, AIChangeSet

        if not settings.ENABLE_CONVERSATIONAL_ONBOARDING:
            return Response(
                {"error": "Conversational onboarding is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Get the approval request
            approval = get_object_or_404(ChangeSetApproval, id=approval_id)

            # SECURITY: Validate tenant scoping - approver must be from same client
            if not request.user.is_superuser:
                if hasattr(request.user, 'client') and request.user.client:
                    if approval.changeset.conversation_session.client != request.user.client:
                        security_logger.log_security_violation(
                            request.user,
                            'secondary_approval',
                            f'tenant_boundary_violation: user_client={request.user.client.id}, changeset_client={approval.changeset.conversation_session.client.id}'
                        )
                        return Response(
                            {"error": "Access denied: You can only approve changesets for your organization"},
                            status=status.HTTP_403_FORBIDDEN
                        )

            # Validate approver is the assigned secondary approver
            if approval.approver != request.user:
                security_logger.log_security_violation(
                    request.user,
                    'secondary_approval',
                    f'unauthorized_approver: expected={approval.approver.id}, actual={request.user.id}'
                )
                return Response(
                    {"error": "Access denied: You are not the assigned approver for this request"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if already decided
            if not approval.is_pending():
                return Response(
                    {
                        "error": "Approval already decided",
                        "current_status": approval.status,
                        "decided_at": approval.decision_at
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get decision from request
            decision = request.data.get('decision')  # 'approve', 'reject', 'escalate'
            reason = request.data.get('reason', '')
            conditions = request.data.get('conditions', '')
            modifications = request.data.get('modifications', {})

            if decision not in ['approve', 'reject', 'escalate']:
                return Response(
                    {"error": "Invalid decision. Must be 'approve', 'reject', or 'escalate'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Record audit trail
            approval.ip_address = self._get_client_ip(request)
            approval.user_agent = request.META.get('HTTP_USER_AGENT', '')
            approval.correlation_id = getattr(request, '_correlation_id', None)

            # Process the decision
            if decision == 'approve':
                approval.approve(reason=reason, conditions=conditions, modifications=modifications)

                # Check if changeset is now fully approved
                changeset = approval.changeset
                if changeset.can_be_applied():
                    # Apply the changeset
                    from .integration.mapper import IntegrationAdapter
                    adapter = IntegrationAdapter()

                    result = adapter.apply_changeset(changeset)

                    security_logger.log_application_result(
                        request.user,
                        changeset.conversation_session.session_id,
                        result.get('changes', []),
                        success=result.get('success', False)
                    )

                    return Response({
                        "decision": "approved",
                        "changeset_applied": True,
                        "changeset_id": str(changeset.changeset_id),
                        "approval_status": changeset.get_approval_status(),
                        "changes_applied": len(result.get('changes', [])),
                        "audit_trail_id": result.get('audit_trail_id'),
                        "message": "Secondary approval granted and changeset applied successfully"
                    })
                else:
                    return Response({
                        "decision": "approved",
                        "changeset_applied": False,
                        "changeset_id": str(changeset.changeset_id),
                        "approval_status": changeset.get_approval_status(),
                        "message": "Secondary approval granted, awaiting additional approvals"
                    })

            elif decision == 'reject':
                approval.reject(reason=reason)

                # Log rejection
                security_logger.log_approval_attempt(
                    request.user,
                    approval.changeset.conversation_session.session_id,
                    {'decision': 'rejected', 'reason': reason},
                    'secondary_rejected'
                )

                return Response({
                    "decision": "rejected",
                    "changeset_id": str(approval.changeset.changeset_id),
                    "approval_status": approval.changeset.get_approval_status(),
                    "message": "Secondary approval rejected - changeset will not be applied"
                })

            elif decision == 'escalate':
                approval.escalate(reason=reason)

                # Create helpdesk ticket for escalated approval
                try:
                    from apps.y_helpdesk.models import Ticket
                    from django.utils import timezone
                    import uuid

                    # Generate ticket number for approval escalation
                    ticket_no = f"APPR-ESC-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"

                    # Build escalation context for approval
                    changeset = approval.changeset
                    session = changeset.session

                    escalation_description = f"""
APPROVAL ESCALATION - Conversational Onboarding

Session ID: {session.session_id}
Changeset ID: {changeset.changeset_id}
Approval Level: {approval.approval_level}
Escalation Reason: {reason or 'Secondary approval escalated by approver'}

Original Request Summary:
- Conversation Type: {session.conversation_type}
- Current State: {session.get_current_state_display()}
- Requested by: {session.user.email}
- Client: {session.client.name if session.client else 'N/A'}

Changeset Summary:
{changeset.summary if hasattr(changeset, 'summary') else 'No summary available'}

Recommendations requiring approval:
{changeset.recommendations_summary if hasattr(changeset, 'recommendations_summary') else 'Details in changeset data'}

This escalation requires senior approver review and decision on the AI-generated recommendations.

Next Steps:
1. Senior approver should review the full conversation context
2. Assess the AI recommendations for safety and compliance
3. Make final approval/rejection decision
4. Update the approval status through the admin interface or API

Escalated by: {request.user.email}
Escalated at: {timezone.now().isoformat()}
                    """.strip()

                    # Create helpdesk ticket
                    helpdesk_ticket = Ticket.objects.create(
                        ticketno=ticket_no,
                        ticketdesc=escalation_description,
                        client=session.client,
                        bu=session.client,  # Use client as BU
                        priority=Ticket.Priority.HIGH,  # Approvals are high priority
                        status=Ticket.Status.NEW,
                        identifier=Ticket.Identifier.TICKET,
                        performedby=request.user,
                        ticketlog={
                            'escalation_data': {
                                'conversation_session_id': str(session.session_id),
                                'changeset_id': str(changeset.changeset_id),
                                'approval_id': str(approval.approval_id),
                                'approval_level': approval.approval_level,
                                'escalation_reason': reason,
                                'escalated_by': request.user.email,
                                'escalated_at': timezone.now().isoformat(),
                                'source': 'ai_approval_escalation'
                            }
                        }
                    )

                    # Update approval with ticket reference
                    approval.escalation_details = {
                        'helpdesk_ticket_id': helpdesk_ticket.uuid,
                        'ticket_number': helpdesk_ticket.ticketno,
                        'escalated_at': timezone.now().isoformat(),
                        'escalated_by': request.user.email,
                        'reason': reason
                    }
                    approval.save()

                    logger.info(
                        f"Secondary approval escalated with helpdesk ticket {helpdesk_ticket.ticketno}",
                        extra={
                            'user_id': request.user.id,
                            'changeset_id': str(changeset.changeset_id),
                            'approval_id': str(approval.approval_id),
                            'ticket_number': helpdesk_ticket.ticketno,
                            'escalation_reason': reason
                        }
                    )

                    # Send webhook notification for escalation
                    if getattr(settings, 'ENABLE_WEBHOOK_NOTIFICATIONS', False):
                        try:
                            from .services.notifications import notify_escalation_created

                            escalation_url = request.build_absolute_uri(
                                f'/admin/y_helpdesk/ticket/{helpdesk_ticket.uuid}/change/'
                            )

                            notify_escalation_created(
                                session_id=str(session.session_id),
                                changeset_id=str(changeset.changeset_id),
                                escalated_by_email=request.user.email,
                                escalation_reason=reason or 'Secondary approval escalated',
                                ticket_number=helpdesk_ticket.ticketno,
                                client_name=session.client.buname,
                                escalation_url=escalation_url
                            )
                        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                            logger.warning(f"Failed to send escalation notification: {str(e)}")

                    return Response({
                        "decision": "escalated",
                        "changeset_id": str(approval.changeset.changeset_id),
                        "approval_status": approval.changeset.get_approval_status(),
                        "message": "Approval escalated to senior approvers",
                        "escalation_details": {
                            "ticket_number": helpdesk_ticket.ticketno,
                            "ticket_uuid": str(helpdesk_ticket.uuid),
                            "escalated_at": timezone.now().isoformat(),
                            "reason": reason
                        }
                    })

                except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as escalation_error:
                    logger.error(f"Failed to create escalation ticket: {str(escalation_error)}")

                    # Still return success for the escalation, but note ticket creation failure
                    return Response({
                        "decision": "escalated",
                        "changeset_id": str(approval.changeset.changeset_id),
                        "approval_status": approval.changeset.get_approval_status(),
                        "message": "Approval escalated to senior approvers (ticket creation failed - check logs)",
                        "warning": "Helpdesk ticket could not be created automatically"
                    })

        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            security_logger.log_security_violation(
                request.user,
                'secondary_approval',
                f'approval_error: {str(e)}'
            )
            logger.error(f"Secondary approval error for user {request.user.id}: {str(e)}")

            return Response(
                {"error": "Secondary approval failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ChangeSetRollbackView(APIView):
    """
    Rollback a previously applied AI changeset

    POST /api/v1/onboarding/changesets/{changeset_id}/rollback/

    SECURITY: This endpoint can undo business-critical changes.
    Access is restricted to authorized personnel only.
    """
    permission_classes = [CanApproveAIRecommendations]

    def post(self, request, changeset_id):
        from .permissions import security_logger
        from apps.onboarding.models import AIChangeSet

        try:
            # Get the changeset
            changeset = get_object_or_404(AIChangeSet, changeset_id=changeset_id)

            # Check if rollback is allowed
            if not changeset.can_rollback():
                security_logger.log_security_violation(
                    request.user,
                    'changeset_rollback',
                    f'rollback_not_available: {changeset.status}'
                )
                return Response(
                    {
                        "error": "Changeset cannot be rolled back",
                        "status": changeset.status,
                        "rolled_back_at": changeset.rolled_back_at
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get rollback reason from request
            rollback_reason = request.data.get('reason', 'Manual rollback requested')

            # Perform rollback through integration adapter
            from .integration.mapper import IntegrationAdapter
            adapter = IntegrationAdapter()

            result = adapter.rollback_changeset(
                changeset=changeset,
                rollback_reason=rollback_reason,
                rollback_user=request.user
            )

            # Log rollback operation
            security_logger.log_application_result(
                request.user,
                changeset.conversation_session.session_id,
                result.get('rollback_operations', []),
                success=result.get('success', False),
                error=result.get('error')
            )

            if result.get('success', False):
                return Response({
                    "message": "Changeset rolled back successfully",
                    "changeset_id": str(changeset.changeset_id),
                    "rolled_back_changes": result.get('rolled_back_count', 0),
                    "failed_rollbacks": result.get('failed_count', 0),
                    "rollback_complexity": changeset.get_rollback_complexity()
                })
            else:
                return Response(
                    {
                        "error": "Rollback failed",
                        "details": result.get('error'),
                        "partial_success": result.get('partial_success', False)
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            security_logger.log_security_violation(
                request.user,
                'changeset_rollback',
                f'rollback_exception: {str(e)}'
            )
            logger.error(f"Changeset rollback error for user {request.user.id}: {str(e)}")

            return Response(
                {"error": "Rollback operation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChangeSetListView(APIView):
    """
    List changesets with filtering and rollback capabilities

    GET /api/v1/onboarding/changesets/

    Query parameters:
    - status: Filter by changeset status
    - conversation_id: Filter by conversation session
    - can_rollback: Filter by rollback capability
    """
    permission_classes = [CanApproveAIRecommendations]

    def get(self, request):
        from apps.onboarding.models import AIChangeSet

        # Build queryset with filters
        queryset = AIChangeSet.objects.all().order_by('-cdtz')

        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        conversation_id = request.query_params.get('conversation_id')
        if conversation_id:
            queryset = queryset.filter(conversation_session__session_id=conversation_id)

        can_rollback_filter = request.query_params.get('can_rollback')
        if can_rollback_filter == 'true':
            queryset = queryset.filter(
                status__in=[AIChangeSet.StatusChoices.APPLIED, AIChangeSet.StatusChoices.PARTIALLY_APPLIED],
                rolled_back_at__isnull=True
            )

        # Pagination
        from django.core.paginator import Paginator
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        page = int(request.query_params.get('page', 1))

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        # Serialize results
        changesets = []
        for changeset in page_obj.object_list:
            changesets.append({
                "changeset_id": str(changeset.changeset_id),
                "conversation_session_id": str(changeset.conversation_session.session_id),
                "status": changeset.status,
                "description": changeset.description,
                "total_changes": changeset.total_changes,
                "successful_changes": changeset.successful_changes,
                "failed_changes": changeset.failed_changes,
                "applied_at": changeset.applied_at,
                "approved_by": changeset.approved_by.email if changeset.approved_by else None,
                "can_rollback": changeset.can_rollback(),
                "rollback_complexity": changeset.get_rollback_complexity(),
                "rolled_back_at": changeset.rolled_back_at,
                "rolled_back_by": changeset.rolled_back_by.email if changeset.rolled_back_by else None
            })

        return Response({
            "changesets": changesets,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "total_count": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous()
            }
        })


class AuthoritativeKnowledgeViewSet(ModelViewSet):
    """
    ViewSet for managing authoritative knowledge (admin/staff only)
    """
    queryset = AuthoritativeKnowledge.objects.all()
    serializer_class = AuthoritativeKnowledgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_staff:
            return AuthoritativeKnowledge.objects.none()
        return super().get_queryset()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_knowledge(request):
    """
    Validate knowledge against authoritative sources
    POST /api/v1/onboarding/knowledge/validate/

    Expected payload:
    {
        "recommendation": {
            "type": "business_unit_config",
            "content": {...}
        },
        "context": {
            "session_id": "uuid",
            "client_id": "id"
        }
    }
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        data = request.data

        # Validate required fields
        if 'recommendation' not in data:
            return Response(
                {"error": "Missing 'recommendation' field"},
                status=status.HTTP_400_BAD_REQUEST
            )

        recommendation = data['recommendation']
        context = data.get('context', {})

        # Initialize knowledge service with proper factory function
        from .services.knowledge import get_knowledge_service
        knowledge_service = get_knowledge_service()

        # Validate the recommendation against knowledge base
        validation_result = knowledge_service.validate_recommendation_against_knowledge(
            recommendation=recommendation,
            context=context
        )

        # Enhance the result with additional validation details
        enhanced_result = {
            'validation_status': 'valid' if validation_result['is_valid'] else 'invalid',
            'confidence_score': validation_result['confidence_score'],
            'is_compliant': validation_result['is_valid'],
            'supporting_sources': validation_result['supporting_sources'],
            'potential_conflicts': validation_result['potential_conflicts'],
            'recommendations': validation_result.get('recommendations', []),
            'validation_details': {
                'sources_checked': len(validation_result['supporting_sources']),
                'conflicts_found': len(validation_result['potential_conflicts']),
                'validation_timestamp': timezone.now().isoformat(),
                'validated_by': request.user.email
            }
        }

        # Add risk assessment
        if validation_result['confidence_score'] < 0.6:
            enhanced_result['risk_level'] = 'high'
            enhanced_result['warning'] = 'Low confidence in validation - manual review recommended'
        elif validation_result['confidence_score'] < 0.8:
            enhanced_result['risk_level'] = 'medium'
            enhanced_result['warning'] = 'Medium confidence - consider additional verification'
        else:
            enhanced_result['risk_level'] = 'low'

        return Response(enhanced_result, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error in knowledge validation: {str(e)}")
        return Response(
            {
                "error": "Knowledge validation failed",
                "details": str(e),
                "support_reference": timezone.now().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# NOTE: The basic knowledge search stub has been removed as it was unused.
# Knowledge search functionality is now handled by:
# - views_phase2.search_knowledge_enhanced (enhanced search with context)
# - knowledge_views.KnowledgeSearchAPIView (advanced search with filtering)
#
# URLs point to the enhanced implementations:
# - /api/v1/onboarding/knowledge/search/ -> search_knowledge_enhanced
# - /api/v1/onboarding/knowledge/search-advanced/ -> KnowledgeSearchAPIView


class FeatureStatusView(APIView):
    """
    Check if conversational onboarding feature is enabled and return configuration
    GET /api/v1/onboarding/status/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return feature status and configuration"""
        response_data = {
            'enabled': settings.ENABLE_CONVERSATIONAL_ONBOARDING,
            'flags': {
                'dual_llm_enabled': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', False),
                'streaming_enabled': getattr(settings, 'ENABLE_ONBOARDING_SSE', False),
                'personalization_enabled': getattr(settings, 'ENABLE_ONBOARDING_PERSONALIZATION', False),
                'knowledge_base_enabled': getattr(settings, 'ENABLE_ONBOARDING_KB', True),
                'ai_experiments_enabled': getattr(settings, 'ENABLE_ONBOARDING_EXPERIMENTS', False),
            },
            'configuration': {
                'max_session_duration_minutes': getattr(settings, 'ONBOARDING_SESSION_DURATION', 30),
                'max_recommendations_per_session': getattr(settings, 'ONBOARDING_MAX_RECOMMENDATIONS', 5),
                'languages_supported': getattr(settings, 'ONBOARDING_LANGUAGES', ['en']),
                'llm_provider': getattr(settings, 'ONBOARDING_LLM_PROVIDER', 'dummy'),
            },
            'version': '1.0.0'
        }

        # Add user capabilities check
        if hasattr(request.user, 'capabilities') and request.user.capabilities:
            response_data['user_capabilities'] = {
                'can_approve_recommendations': request.user.capabilities.get('can_approve_ai_recommendations', False),
                'can_access_admin_dashboard': request.user.capabilities.get('can_access_ai_admin_dashboard', False),
                'can_override_ai_decisions': request.user.capabilities.get('can_override_ai_decisions', False),
            }
        else:
            response_data['user_capabilities'] = {
                'can_approve_recommendations': False,
                'can_access_admin_dashboard': False,
                'can_override_ai_decisions': False,
            }

        return Response(response_data)


class ChangeSetDiffPreviewView(APIView):
    """
    Generate a preview of changes that would be applied
    POST /api/v1/onboarding/changeset/preview/
    """
    permission_classes = [CanApproveAIRecommendations]

    def post(self, request):
        """Generate diff preview for proposed changes"""
        from .integration.mapper import IntegrationAdapter
        from apps.onboarding.models import Bt, Shift, TypeAssist

        approved_items = request.data.get('approved_items', [])
        modifications = request.data.get('modifications', {})

        if not approved_items:
            return Response(
                {"error": "No items to preview"},
                status=status.HTTP_400_BAD_REQUEST
            )

        adapter = IntegrationAdapter()
        diff_preview = {
            'changes': [],
            'summary': {
                'total_changes': 0,
                'fields_modified': 0,
                'entities_affected': set()
            }
        }

        try:
            for item in approved_items:
                entity_type = item.get('entity_type')
                entity_id = item.get('entity_id')
                changes = item.get('changes', {})

                # Apply any user modifications
                if str(entity_id) in modifications:
                    changes.update(modifications[str(entity_id)])

                # Get current state
                current_state = None
                if entity_type == 'bt':
                    try:
                        bt = Bt.objects.get(id=entity_id)
                        current_state = {
                            'buname': bt.buname,
                            'bucode': bt.bucode,
                            'bupreferences': bt.bupreferences,
                            'enable': bt.enable
                        }
                    except Bt.DoesNotExist:
                        current_state = None

                elif entity_type == 'shift':
                    try:
                        shift = Shift.objects.get(id=entity_id)
                        current_state = {
                            'shiftname': shift.shiftname,
                            'starttime': str(shift.starttime) if shift.starttime else None,
                            'endtime': str(shift.endtime) if shift.endtime else None,
                            'peoplecount': shift.peoplecount,
                            'captchafreq': shift.captchafreq
                        }
                    except Shift.DoesNotExist:
                        current_state = None

                elif entity_type == 'typeassist':
                    try:
                        ta = TypeAssist.objects.get(id=entity_id)
                        current_state = {
                            'taname': ta.taname,
                            'tacode': ta.tacode,
                            'tatype': ta.tatype.id if ta.tatype else None,
                            'enable': ta.enable
                        }
                    except TypeAssist.DoesNotExist:
                        current_state = None

                # Create diff entry
                diff_entry = {
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'operation': 'create' if current_state is None else 'update',
                    'before': current_state,
                    'after': changes,
                    'fields_changed': []
                }

                # Calculate field changes
                if current_state:
                    for field, new_value in changes.items():
                        old_value = current_state.get(field)
                        if old_value != new_value:
                            diff_entry['fields_changed'].append({
                                'field': field,
                                'old': old_value,
                                'new': new_value
                            })
                            diff_preview['summary']['fields_modified'] += 1
                else:
                    diff_entry['fields_changed'] = [
                        {'field': k, 'old': None, 'new': v}
                        for k, v in changes.items()
                    ]
                    diff_preview['summary']['fields_modified'] += len(changes)

                diff_preview['changes'].append(diff_entry)
                diff_preview['summary']['entities_affected'].add(entity_type)
                diff_preview['summary']['total_changes'] += 1

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error generating diff preview: {str(e)}")
            return Response(
                {"error": f"Failed to generate preview: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Convert set to list for JSON serialization
        diff_preview['summary']['entities_affected'] = list(diff_preview['summary']['entities_affected'])

        return Response(diff_preview)


class ConfigurationTemplatesView(APIView):
    """
    Manage and apply configuration templates for faster onboarding

    GET /api/v1/onboarding/templates/ - List all templates
    POST /api/v1/onboarding/templates/recommend/ - Get template recommendations
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all available configuration templates"""
        from .services.config_templates import get_template_service

        template_service = get_template_service()
        templates = template_service.get_all_templates()

        # Convert to API-friendly format
        template_data = []
        for template in templates:
            template_dict = template.to_dict()
            # Add preview information without full config details
            template_dict['preview'] = {
                'business_units_count': len(template.config.get('business_units', [])),
                'shifts_count': len(template.config.get('shifts', [])),
                'type_assists_count': len(template.config.get('type_assists', [])),
                'complexity': template.metadata.get('complexity', 'medium'),
                'setup_time_minutes': template.metadata.get('setup_time_minutes', 30)
            }
            # Remove full config from list view for performance
            del template_dict['config']
            template_data.append(template_dict)

        return Response({
            'templates': template_data,
            'total_count': len(template_data)
        })

    def post(self, request):
        """Get template recommendations based on provided context"""
        from .services.config_templates import get_template_service

        # Validate that user has a client relation for scoping
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client to use templates"},
                status=status.HTTP_400_BAD_REQUEST
            )

        template_service = get_template_service()

        # Get context from request
        context = {
            'site_type': request.data.get('site_type', ''),
            'operating_hours': request.data.get('operating_hours', ''),
            'staff_count': request.data.get('staff_count', 0),
            'security_level': request.data.get('security_level', 'medium')
        }

        # Get recommendations
        recommendations = template_service.recommend_templates(context)

        return Response({
            'context': context,
            'recommendations': recommendations
        })


class ConfigurationTemplateDetailView(APIView):
    """
    Get details for a specific configuration template

    GET /api/v1/onboarding/templates/{template_id}/ - Get template details
    POST /api/v1/onboarding/templates/{template_id}/apply/ - Apply template
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, template_id):
        """Get detailed configuration template information"""
        from .services.config_templates import get_template_service

        template_service = get_template_service()
        template = template_service.get_template(template_id)

        if not template:
            return Response(
                {'error': f'Template {template_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(template.to_dict())

    def post(self, request, template_id):
        """Apply a configuration template with optional customizations"""
        from .services.config_templates import get_template_service

        # Validate that user has a client relation
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client to apply templates"},
                status=status.HTTP_400_BAD_REQUEST
            )

        template_service = get_template_service()

        try:
            # Get customizations from request
            customizations = request.data.get('customizations', {})
            dry_run = request.data.get('dry_run', True)

            # Apply template
            applied_config = template_service.apply_template(template_id, customizations)

            if not dry_run:
                # Log the template application for security audit
                logger.info(
                    f"User {request.user.id} applied template {template_id} for client {request.user.client.id}"
                )

                return Response({
                    'template_applied': True,
                    'template_id': template_id,
                    'applied_config': applied_config,
                    'message': 'Template configuration ready for system application'
                })
            else:
                return Response({
                    'template_applied': False,
                    'preview': applied_config,
                    'dry_run': True,
                    'message': 'Template preview generated (dry run mode)'
                })

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Template application error: {str(e)}")
            return Response(
                {'error': 'Template application failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cache_health_check(request):
    """
    Check cache backend health for rate limiting functionality
    GET /api/v1/onboarding/health/cache/

    This endpoint validates that the cache backend is properly configured
    for production use with distributed rate limiting.
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from .middleware import OnboardingAPIMiddleware

        cache_status = OnboardingAPIMiddleware.get_cache_health_status()

        # Determine HTTP status based on validation result
        http_status = status.HTTP_200_OK if cache_status['is_valid'] else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response({
            'cache_health': cache_status,
            'system_status': 'healthy' if cache_status['is_valid'] else 'degraded',
            'checked_at': timezone.now().isoformat(),
            'recommendations': cache_status.get('recommendations', [])
        }, status=http_status)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Cache health check error: {str(e)}")
        return Response({
            'error': 'Cache health check failed',
            'details': str(e),
            'system_status': 'unknown',
            'checked_at': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def logging_health_check(request):
    """
    Check logging configuration and health for onboarding API
    GET /api/v1/onboarding/health/logging/

    This endpoint validates that all required loggers are properly configured
    and accessible for production use.
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from .utils.logging_validation import get_logging_health_status

        logging_health = get_logging_health_status()

        # Determine HTTP status based on health
        if logging_health['overall_health'] == 'critical':
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        elif logging_health['overall_health'] == 'degraded':
            http_status = status.HTTP_200_OK  # Still operational but with warnings
        else:
            http_status = status.HTTP_200_OK

        return Response({
            'logging_health': logging_health,
            'system_status': logging_health['overall_health'],
            'checked_at': timezone.now().isoformat(),
            'recommendations': logging_health.get('recommendations', []),
            'critical_issues': logging_health.get('critical_issues', [])
        }, status=http_status)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Logging health check error: {str(e)}")
        return Response({
            'error': 'Logging health check failed',
            'details': str(e),
            'system_status': 'unknown',
            'checked_at': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def logging_documentation(request):
    """
    Get logging setup documentation
    GET /api/v1/onboarding/documentation/logging/

    Returns comprehensive documentation for configuring and maintaining
    the logging system for the onboarding API.
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from .utils.logging_validation import create_logger_setup_documentation

        documentation = create_logger_setup_documentation()

        return Response({
            'documentation': documentation,
            'format': 'markdown',
            'generated_at': timezone.now().isoformat(),
            'version': '1.0'
        }, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error generating logging documentation: {str(e)}")
        return Response({
            'error': 'Documentation generation failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def preflight_validation(request):
    """
    Preflight validation endpoint for conversational onboarding readiness

    GET /api/v1/onboarding/preflight/
    POST /api/v1/onboarding/preflight/

    This endpoint performs comprehensive validation to ensure the tenant and user
    are properly configured before enabling conversational onboarding features.

    Returns detailed validation results with actionable recommendations.
    """
    try:
        from .utils.preflight import run_preflight_validation

        # Get client from user or request parameters
        client = request.user.client if hasattr(request.user, 'client') and request.user.client else None

        # For POST requests, allow specifying different client (staff only)
        if request.method == 'POST' and request.user.is_staff:
            data = request.data if hasattr(request, 'data') else {}
            client_id = data.get('client_id')
            if client_id:
                try:
                    from apps.onboarding.models import Bt
                    client = Bt.objects.get(id=client_id)
                except Bt.DoesNotExist:
                    return Response({
                        'error': 'Specified client not found',
                        'client_id': client_id
                    }, status=status.HTTP_400_BAD_REQUEST)

        if not client:
            return Response({
                'error': 'User must be associated with a client for preflight validation',
                'user_id': request.user.id,
                'user_email': request.user.email
            }, status=status.HTTP_400_BAD_REQUEST)

        # Run comprehensive preflight validation
        validation_results = run_preflight_validation(client=client, user=request.user)

        # Determine HTTP status based on validation results
        if validation_results['overall_status'] == 'critical':
            http_status = status.HTTP_412_PRECONDITION_FAILED  # Cannot proceed
        elif validation_results['overall_status'] == 'warning':
            http_status = status.HTTP_200_OK  # Can proceed with cautions
        else:
            http_status = status.HTTP_200_OK  # Ready to go

        # Add context information
        response_data = {
            'preflight_validation': validation_results,
            'client_info': {
                'id': client.id,
                'name': getattr(client, 'buname', 'Unknown'),
                'code': getattr(client, 'bucode', 'Unknown'),
                'is_active': getattr(client, 'is_active', False)
            },
            'user_info': {
                'id': request.user.id,
                'email': request.user.email,
                'capabilities': request.user.get_all_capabilities() if hasattr(request.user, 'get_all_capabilities') else {}
            },
            'next_steps': _get_next_steps_recommendations(validation_results),
            'validation_timestamp': timezone.now().isoformat()
        }

        # Log validation for monitoring
        logger.info(
            f"Preflight validation completed for client {client.id}: {validation_results['overall_status']}",
            extra={
                'client_id': client.id,
                'user_id': request.user.id,
                'validation_status': validation_results['overall_status'],
                'is_ready': validation_results['is_ready'],
                'critical_issues_count': len(validation_results['critical_issues']),
                'warnings_count': len(validation_results['warnings'])
            }
        )

        return Response(response_data, status=http_status)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Preflight validation error: {str(e)}")
        return Response({
            'error': 'Preflight validation failed',
            'details': str(e),
            'validation_status': 'error',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_next_steps_recommendations(validation_results: dict) -> list:
    """
    Generate actionable next steps based on validation results

    Args:
        validation_results: Results from preflight validation

    Returns:
        List of recommended next steps
    """
    next_steps = []

    if validation_results['overall_status'] == 'critical':
        next_steps.append({
            'priority': 'critical',
            'action': 'resolve_critical_issues',
            'title': 'Resolve Critical Issues',
            'description': 'Fix all critical issues before enabling conversational onboarding',
            'issues': validation_results['critical_issues']
        })

    if validation_results['warnings']:
        next_steps.append({
            'priority': 'warning',
            'action': 'review_warnings',
            'title': 'Review Warnings',
            'description': 'Address warnings to improve onboarding experience',
            'warnings': validation_results['warnings']
        })

    if validation_results['recommendations']:
        next_steps.append({
            'priority': 'recommendation',
            'action': 'implement_recommendations',
            'title': 'Implement Recommendations',
            'description': 'Follow recommendations for optimal configuration',
            'recommendations': validation_results['recommendations']
        })

    if validation_results['is_ready']:
        next_steps.append({
            'priority': 'info',
            'action': 'enable_onboarding',
            'title': 'Enable Conversational Onboarding',
            'description': 'System is ready - you can now enable conversational onboarding features',
            'endpoint': '/api/v1/onboarding/conversation/start/',
            'admin_url': '/admin/onboarding_api/peopleonboardingproxy/'
        })

    return next_steps


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def preflight_quick_check(request):
    """
    Quick preflight check for basic readiness

    GET /api/v1/onboarding/preflight/quick/

    Performs essential validation checks only for faster response.
    Use full preflight validation for comprehensive assessment.
    """
    try:
        client = request.user.client if hasattr(request.user, 'client') and request.user.client else None

        if not client:
            return Response({
                'ready': False,
                'reason': 'No client associated with user',
                'next_action': 'contact_administrator'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Quick checks only
        quick_checks = {
            'client_active': getattr(client, 'is_active', False),
            'user_active': request.user.is_active,
            'feature_enabled': getattr(settings, 'ENABLE_CONVERSATIONAL_ONBOARDING', False),
            'user_has_capability': request.user.get_capability('can_use_conversational_onboarding') if hasattr(request.user, 'get_capability') else False
        }

        all_passed = all(quick_checks.values())

        response_data = {
            'ready': all_passed,
            'quick_checks': quick_checks,
            'timestamp': timezone.now().isoformat()
        }

        if not all_passed:
            response_data['next_action'] = 'run_full_preflight_validation'
            response_data['full_validation_url'] = '/api/v1/onboarding/preflight/'

        return Response(response_data, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Quick preflight check error: {str(e)}")
        return Response({
            'ready': False,
            'error': str(e),
            'next_action': 'contact_support'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health_monitoring(request):
    """
    System health monitoring endpoint with auto-degradation
    GET /api/v1/onboarding/health/system/

    Provides comprehensive system health status and auto-degradation information.
    This endpoint is used by monitoring systems and administrators.
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from .utils.monitoring import get_system_health, get_degradation_status

        # Get comprehensive health report
        health_report = get_system_health()
        degradation_status = get_degradation_status()

        # Combine reports
        response_data = {
            'system_health': health_report,
            'degradation_status': degradation_status,
            'monitoring_metadata': {
                'endpoint': '/api/v1/onboarding/health/system/',
                'version': '1.0',
                'checked_at': timezone.now().isoformat()
            }
        }

        # Determine HTTP status based on health
        if health_report['overall_status'].value == 'critical':
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        elif health_report['overall_status'].value == 'degraded':
            http_status = status.HTTP_200_OK  # Still operational but degraded
        else:
            http_status = status.HTTP_200_OK

        return Response(response_data, status=http_status)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"System health monitoring error: {str(e)}")
        return Response({
            'error': 'System health monitoring failed',
            'details': str(e),
            'system_status': 'unknown',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_degradations(request):
    """
    Reset system degradations (admin only)
    POST /api/v1/onboarding/health/reset-degradations/

    Allows administrators to reset auto-applied degradations.
    """
    if not request.user.is_staff:
        return Response(
            {"error": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        from .utils.monitoring import reset_system_degradations

        level = request.data.get('level') if hasattr(request, 'data') else None
        reset_result = reset_system_degradations(level)

        logger.info(
            f"System degradations reset by {request.user.email}: {reset_result}",
            extra={
                'user_id': request.user.id,
                'user_email': request.user.email,
                'reset_level': level,
                'reset_details': reset_result
            }
        )

        return Response({
            'success': True,
            'reset_result': reset_result,
            'message': f"Degradations reset successfully",
            'reset_by': request.user.email,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Degradation reset error: {str(e)}")
        return Response({
            'error': 'Failed to reset degradations',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def degradation_status(request):
    """
    Get current degradation status
    GET /api/v1/onboarding/health/degradations/

    Returns current auto-degradation status for monitoring.
    """
    try:
        from .utils.monitoring import get_degradation_status

        status_info = get_degradation_status()

        return Response({
            'degradation_status': status_info,
            'checked_at': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Degradation status check error: {str(e)}")
        return Response({
            'error': 'Failed to check degradation status',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class QuickStartRecommendationsView(APIView):
    """
    Get intelligent quick-start recommendations for rapid onboarding
    POST /api/v1/onboarding/quickstart/recommendations/
    """
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('read_templates')
    def post(self, request):
        """Get quick-start recommendations based on minimal site information"""
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client to use quick-start"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Extract site information from request
            site_info = {
                'industry': request.data.get('industry', ''),
                'size': request.data.get('size', 'medium'),
                'operating_hours': request.data.get('operating_hours', 'business_hours'),
                'security_level': request.data.get('security_level', 'medium'),
                'staff_count': request.data.get('staff_count', 25),
                'special_requirements': request.data.get('special_requirements', [])
            }

            from .services.config_templates import get_template_service
            template_service = get_template_service()

            # Get intelligent recommendations
            recommendations = template_service.get_quick_start_recommendations(site_info)

            # Add client-specific context
            recommendations['client_info'] = {
                'id': request.user.client.id,
                'name': request.user.client.buname,
                'code': request.user.client.bucode
            }

            # Add deployment readiness check
            if recommendations['primary_template']:
                deployment_check = template_service.validate_template_compatibility(
                    recommendations['primary_template']['template_id'],
                    {
                        'max_devices': 100,  # Could get from client constraints
                        'max_staff': 200,
                        'available_features': ['gps', 'facial_recognition', 'device_tracking']
                    }
                )
                recommendations['deployment_readiness'] = deployment_check

            return Response(recommendations)

        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"Quick-start recommendations error: {str(e)}")
            return Response(
                {"error": "Failed to generate recommendations"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OneClickDeploymentView(APIView):
    """
    Deploy a template configuration with one click
    POST /api/v1/onboarding/templates/{template_id}/deploy/
    """
    permission_classes = [IsAuthenticated]

    @require_tenant_scope('create_configuration')
    @with_idempotency('deploy_template')
    def post(self, request, template_id):
        """Deploy template configuration to client database"""
        if not hasattr(request.user, 'client') or not request.user.client:
            return Response(
                {"error": "User must be associated with a client for deployment"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from .services.config_templates import get_template_service
            template_service = get_template_service()

            # Get customizations and deployment options
            customizations = request.data.get('customizations', {})
            dry_run = request.data.get('dry_run', True)
            create_changeset = request.data.get('create_changeset', True)

            # Validate template exists
            template = template_service.get_template(template_id)
            if not template:
                return Response(
                    {"error": f"Template {template_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check compatibility
            deployment_check = template_service.validate_template_compatibility(
                template_id,
                {
                    'max_devices': 100,
                    'max_staff': 200,
                    'available_features': ['gps', 'facial_recognition', 'device_tracking']
                }
            )

            if not deployment_check['compatible']:
                return Response({
                    "error": "Template not compatible with client constraints",
                    "compatibility_issues": deployment_check['issues'],
                    "warnings": deployment_check['warnings']
                }, status=status.HTTP_400_BAD_REQUEST)

            # Apply template
            deployment_result = template_service.apply_template_to_tenant(
                template_id=template_id,
                client=request.user.client,
                user=request.user,
                customizations=customizations,
                dry_run=dry_run
            )

            # Create changeset for tracking if not dry run
            changeset_info = None
            if not dry_run and create_changeset and not deployment_result['errors']:
                try:
                    from .integration.mapper import IntegrationAdapter
                    from apps.onboarding.models import ConversationSession

                    # Create a pseudo-session for template deployment tracking
                    session = ConversationSession.objects.create(
                        user=request.user,
                        client=request.user.client,
                        conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
                        context_data={'template_deployment': True, 'template_id': template_id},
                        current_state=ConversationSession.StateChoices.COMPLETED
                    )

                    adapter = IntegrationAdapter()
                    changeset = adapter.create_changeset(
                        conversation_session=session,
                        approved_by=request.user,
                        description=f"Template Deployment: {template.name} ({template_id})"
                    )

                    changeset_info = {
                        'changeset_id': str(changeset.changeset_id),
                        'session_id': str(session.session_id),
                        'rollback_available': True
                    }

                except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
                    logger.warning(f"Failed to create changeset for template deployment: {str(e)}")

            # Send webhook notification for successful deployment
            if not dry_run and not deployment_result['errors'] and getattr(settings, 'ENABLE_WEBHOOK_NOTIFICATIONS', False):
                try:
                    from .services.notifications import notify_changeset_applied

                    notify_changeset_applied(
                        session_id=changeset_info['session_id'] if changeset_info else 'template_deployment',
                        changeset_id=changeset_info['changeset_id'] if changeset_info else 'direct_template',
                        applied_by_email=request.user.email,
                        client_name=request.user.client.buname,
                        changes_applied=len(deployment_result['created_objects']['business_units']) +
                                       len(deployment_result['created_objects']['shifts']) +
                                       len(deployment_result['created_objects']['type_assists']),
                        rollback_available=bool(changeset_info)
                    )
                except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
                    logger.warning(f"Failed to send template deployment notification: {str(e)}")

            response_data = {
                'deployment_result': deployment_result,
                'template_info': {
                    'template_id': template_id,
                    'template_name': template.name,
                    'estimated_setup_time': template.metadata.get('setup_time_minutes', 30)
                },
                'compatibility_check': deployment_check,
                'changeset_info': changeset_info
            }

            if dry_run:
                response_data['message'] = 'Template deployment preview completed (dry run)'
            else:
                response_data['message'] = 'Template deployed successfully' if not deployment_result['errors'] else 'Template deployment completed with errors'

            return Response(response_data)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Template deployment error: {str(e)}")
            return Response(
                {"error": "Template deployment failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TemplateAnalyticsView(APIView):
    """
    Get template analytics and usage statistics
    GET /api/v1/onboarding/templates/analytics/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get comprehensive template analytics"""
        if not request.user.is_staff:
            return Response(
                {"error": "Staff access required for analytics"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            from .services.config_templates import get_template_service
            template_service = get_template_service()

            # Get analytics data
            analytics = template_service.get_template_analytics()
            usage_stats = template_service.get_template_usage_stats()

            # Combine data
            response_data = {
                'template_analytics': analytics,
                'usage_statistics': usage_stats,
                'system_info': {
                    'total_templates_available': len(template_service.get_all_templates()),
                    'last_updated': timezone.now().isoformat()
                }
            }

            return Response(response_data)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Template analytics error: {str(e)}")
            return Response(
                {"error": "Failed to retrieve analytics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )