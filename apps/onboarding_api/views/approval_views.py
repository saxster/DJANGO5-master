"""
Approval Workflow Views

Handles AI recommendation approvals with two-person rule and security auditing.

Migrated from: apps/onboarding_api/views.py (lines 335-907)
Date: 2025-09-30
Refactoring: Phase 3 - God File Elimination

SECURITY: These endpoints modify business-critical data.
Access restricted through CanApproveAIRecommendations permission.
All operations are comprehensively audited.
"""
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import CanApproveAIRecommendations
from ..serializers import RecommendationApprovalSerializer
from apps.core_onboarding.models import ConversationSession
from apps.core_onboarding.models import ChangeSetApproval
import logging
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


logger = logging.getLogger(__name__)


class RecommendationApprovalView(APIView):
    """
    Approve or reject AI recommendations with security controls.
    
    POST /api/v1/onboarding/recommendations/approve/
    
    Implements two-person approval rule for high-risk changes.
    """
    permission_classes = [CanApproveAIRecommendations]

    def post(self, request):
        """Process approval request with comprehensive security validation"""
        from ..permissions import security_logger

        if not self._check_feature_enabled():
            security_logger.log_security_violation(
                request.user,
                'ai_recommendation_approval',
                'conversational_onboarding_disabled'
            )
            return self._feature_disabled_response()

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

        # SECURITY: Validate tenant scoping
        tenant_validation = self._validate_tenant_scope(request.user, session_id, security_logger)
        if tenant_validation:
            return tenant_validation

        # Log approval attempt
        security_logger.log_approval_attempt(
            request.user, session_id, data, 'initiated'
        )

        try:
            return self._process_approval(request, data, session_id, security_logger)
        except (ValueError, TypeError, AttributeError) as e:
            return self._handle_approval_error(request, session_id, data, e, security_logger)

    def _check_feature_enabled(self):
        """Check if feature is enabled"""
        return settings.ENABLE_CONVERSATIONAL_ONBOARDING

    def _feature_disabled_response(self):
        """Return feature disabled error"""
        return Response(
            {"error": "Conversational onboarding is not enabled"},
            status=status.HTTP_403_FORBIDDEN
        )

    def _validate_tenant_scope(self, user, session_id, security_logger):
        """Validate tenant scoping for approval"""
        if not session_id or user.is_superuser:
            return None

        try:
            conversation_session = ConversationSession.objects.get(session_id=session_id)

            if hasattr(user, 'client') and user.client:
                if conversation_session.client != user.client:
                    security_logger.log_security_violation(
                        user,
                        'ai_recommendation_approval',
                        f'tenant_boundary_violation: user_client={user.client.id}, session_client={conversation_session.client.id}'
                    )
                    return Response(
                        {
                            "error": "Access denied: You can only approve recommendations for your organization",
                            "code": "TENANT_BOUNDARY_VIOLATION"
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                security_logger.log_security_violation(
                    user,
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
                user,
                'ai_recommendation_approval',
                f'invalid_session_id: {session_id}'
            )
            return Response(
                {"error": "Invalid session ID", "code": "INVALID_SESSION"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return None

    def _process_approval(self, request, data, session_id, security_logger):
        """Process the approval request"""
        from ..integration.mapper import IntegrationAdapter

        conversation_session = None
        if session_id:
            try:
                conversation_session = ConversationSession.objects.get(session_id=session_id)
            except ConversationSession.DoesNotExist:
                logger.warning(f"ConversationSession {session_id} not found")

        adapter = IntegrationAdapter()

        # Create changeset if not dry run
        changeset = None
        if not data['dry_run'] and conversation_session:
            changeset = adapter.create_changeset(
                conversation_session=conversation_session,
                approved_by=request.user,
                description=f"AI Recommendations Applied - {len(data['approved_items'])} items"
            )

            # Check two-person approval requirement
            if changeset.requires_two_person_approval():
                return self._handle_two_person_approval(request, changeset, data)

        # Apply recommendations
        result = adapter.apply_recommendations(
            approved_items=data['approved_items'],
            rejected_items=data['rejected_items'],
            reasons=data['reasons'],
            modifications=data['modifications'],
            dry_run=data['dry_run'],
            user=request.user,
            changeset=changeset
        )

        # Log success
        security_logger.log_application_result(
            request.user, session_id, result.get('changes', []), success=True
        )
        security_logger.log_approval_attempt(
            request.user, session_id, data, 'completed_successfully'
        )

        return Response({
            "system_configuration": result.get('configuration', {}),
            "implementation_plan": result.get('plan', []),
            "audit_trail_id": result.get('audit_trail_id'),
            "changeset_id": str(changeset.changeset_id) if changeset else None,
            "changes_applied": len(result.get('changes', [])),
            "rollback_available": changeset.can_rollback() if changeset else False
        })

    def _handle_two_person_approval(self, request, changeset, data):
        """Handle two-person approval requirement"""
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

        secondary_approval = changeset.auto_assign_secondary_approver(
            primary_approver=request.user,
            request_meta=request_meta
        )

        return Response({
            "two_person_approval_required": True,
            "changeset_id": str(changeset.changeset_id),
            "risk_score": changeset.calculate_risk_score(),
            "approval_status": changeset.get_approval_status(),
            "primary_approval_id": str(primary_approval.id) if primary_approval else None,
            "secondary_approval_id": str(secondary_approval.id) if secondary_approval else None,
            "message": "High-risk changeset requires secondary approval",
            "next_action": "Awaiting secondary approver decision"
        })

    def _handle_approval_error(self, request, session_id, data, error, security_logger):
        """Handle approval processing errors"""
        security_logger.log_application_result(
            request.user, session_id, [], success=False, error=error
        )
        security_logger.log_approval_attempt(
            request.user, session_id, data, f'failed: {str(error)}'
        )

        logger.error(
            f"Error applying AI recommendations: {str(error)}",
            extra={
                'user_id': request.user.id,
                'session_id': session_id,
                'approved_items_count': len(data.get('approved_items', []))
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

    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class SecondaryApprovalView(APIView):
    """
    Handle secondary approvals for high-risk changesets.
    
    POST /api/v1/onboarding/approvals/{approval_id}/decide/
    
    Implements second approval in two-person rule.
    """
    permission_classes = [CanApproveAIRecommendations]

    def post(self, request, approval_id):
        """Process secondary approval decision"""
        from ..permissions import security_logger
        from apps.core_onboarding.models import ChangeSetApproval

        if not settings.ENABLE_CONVERSATIONAL_ONBOARDING:
            return Response(
                {"error": "Conversational onboarding is not enabled"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            approval = get_object_or_404(ChangeSetApproval, id=approval_id)

            # Validate security
            security_validation = self._validate_secondary_approval(
                request.user, approval, security_logger
            )
            if security_validation:
                return security_validation

            # Get decision
            decision = request.data.get('decision')
            if decision not in ['approve', 'reject', 'escalate']:
                return Response(
                    {"error": "Invalid decision. Must be 'approve', 'reject', or 'escalate'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Process decision
            return self._process_decision(request, approval, decision, security_logger)

        except NETWORK_EXCEPTIONS as e:
            return self._handle_secondary_approval_error(request, e, security_logger)

    def _validate_secondary_approval(self, user, approval, security_logger):
        """Validate secondary approval request"""
        # Tenant scoping check
        if not user.is_superuser:
            if hasattr(user, 'client') and user.client:
                if approval.changeset.conversation_session.client != user.client:
                    security_logger.log_security_violation(
                        user, 'secondary_approval',
                        f'tenant_boundary_violation'
                    )
                    return Response(
                        {"error": "Access denied: You can only approve changesets for your organization"},
                        status=status.HTTP_403_FORBIDDEN
                    )

        # Approver validation
        if approval.approver != user:
            security_logger.log_security_violation(
                user, 'secondary_approval',
                f'unauthorized_approver: expected={approval.approver.id}, actual={user.id}'
            )
            return Response(
                {"error": "Access denied: You are not the assigned approver"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Status validation
        if not approval.is_pending():
            return Response(
                {
                    "error": "Approval already decided",
                    "current_status": approval.status,
                    "decided_at": approval.decision_at
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return None

    def _process_decision(self, request, approval, decision, security_logger):
        """Process approval decision"""
        reason = request.data.get('reason', '')
        conditions = request.data.get('conditions', '')
        modifications = request.data.get('modifications', {})

        # Record audit trail
        approval.ip_address = self._get_client_ip(request)
        approval.user_agent = request.META.get('HTTP_USER_AGENT', '')
        approval.correlation_id = getattr(request, '_correlation_id', None)

        if decision == 'approve':
            return self._handle_approve_decision(
                request, approval, reason, conditions, modifications, security_logger
            )
        elif decision == 'reject':
            return self._handle_reject_decision(
                request, approval, reason, security_logger
            )
        elif decision == 'escalate':
            return self._handle_escalate_decision(
                request, approval, reason
            )

    def _handle_approve_decision(self, request, approval, reason, conditions, modifications, security_logger):
        """Handle approval decision"""
        approval.approve(reason=reason, conditions=conditions, modifications=modifications)

        changeset = approval.changeset
        if changeset.can_be_applied():
            from ..integration.mapper import IntegrationAdapter
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
                "message": "Secondary approval granted and changeset applied"
            })
        else:
            return Response({
                "decision": "approved",
                "changeset_applied": False,
                "changeset_id": str(changeset.changeset_id),
                "approval_status": changeset.get_approval_status(),
                "message": "Secondary approval granted, awaiting additional approvals"
            })

    def _handle_reject_decision(self, request, approval, reason, security_logger):
        """Handle reject decision"""
        approval.reject(reason=reason)

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

    def _handle_escalate_decision(self, request, approval, reason):
        """Handle escalate decision"""
        approval.escalate(reason=reason)

        # Create helpdesk ticket for escalation
        try:
            from apps.y_helpdesk.models import Ticket

            changeset = approval.changeset
            session = changeset.conversation_session

            ticket_no = f"APPR-ESC-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"

            helpdesk_ticket = Ticket.objects.create(
                ticketno=ticket_no,
                ticketdesc=self._build_escalation_description(session, changeset, approval, reason, request),
                client=session.client,
                bu=session.client,
                priority=Ticket.Priority.HIGH,
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

            approval.escalation_details = {
                'helpdesk_ticket_id': helpdesk_ticket.uuid,
                'ticket_number': helpdesk_ticket.ticketno,
                'escalated_at': timezone.now().isoformat(),
                'escalated_by': request.user.email,
                'reason': reason
            }
            approval.save()

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

        except (ValueError, TypeError, AttributeError) as escalation_error:
            logger.error(f"Failed to create escalation ticket: {str(escalation_error)}")
            return Response({
                "decision": "escalated",
                "changeset_id": str(approval.changeset.changeset_id),
                "approval_status": approval.changeset.get_approval_status(),
                "message": "Approval escalated (ticket creation failed - check logs)",
                "warning": "Helpdesk ticket could not be created automatically"
            })

    def _build_escalation_description(self, session, changeset, approval, reason, request):
        """Build escalation description"""
        return f"""
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

This escalation requires senior approver review and decision.

Escalated by: {request.user.email}
Escalated at: {timezone.now().isoformat()}
        """.strip()

    def _handle_secondary_approval_error(self, request, error, security_logger):
        """Handle secondary approval errors"""
        security_logger.log_security_violation(
            request.user, 'secondary_approval', f'approval_error: {str(error)}'
        )
        logger.error(f"Secondary approval error: {str(error)}")

        return Response(
            {"error": "Secondary approval failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
