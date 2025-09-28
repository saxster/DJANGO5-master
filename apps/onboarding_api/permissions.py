"""
Security permissions for Conversational Onboarding API

This module provides granular permission controls for AI recommendation systems,
ensuring only authorized personnel can approve and apply AI-generated changes
to business-critical data.
"""

import logging
from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class CanApproveAIRecommendations(permissions.BasePermission):
    """
    Permission class to restrict AI recommendation approval to authorized users only.

    This is a critical security control that prevents unauthorized users from
    applying AI-generated changes to business-critical models (Bt, Shift, TypeAssist).

    Authorization Levels (in order of precedence):
    1. Super users - Full access
    2. Staff users with 'can_approve_ai_recommendations' capability
    3. Users with explicit 'ai_recommendation_approver' capability
    4. Site administrators (isadmin=True)
    """

    message = "You do not have permission to approve AI recommendations."

    def has_permission(self, request, view):
        """
        Check if user has permission to approve AI recommendations.

        Args:
            request: HTTP request object
            view: The view being accessed

        Returns:
            bool: True if user is authorized, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            logger.warning("Unauthenticated user attempted to access AI recommendation approval")
            return False

        user = request.user

        # Super users always have access
        if user.is_superuser:
            logger.info(f"Superuser {user.id} granted AI recommendation approval access")
            return True

        # Check for staff users with specific capability
        if user.is_staff and self._has_ai_approval_capability(user):
            logger.info(f"Staff user {user.id} granted AI recommendation approval access")
            return True

        # Check for explicit AI recommendation approver capability
        if self._has_explicit_ai_approver_capability(user):
            logger.info(f"AI approver {user.id} granted recommendation approval access")
            return True

        # Check if user is site administrator
        if getattr(user, 'isadmin', False):
            logger.info(f"Site admin {user.id} granted AI recommendation approval access")
            return True

        # Log failed authorization attempt for security monitoring
        logger.warning(
            f"User {user.id} denied AI recommendation approval access",
            extra={
                'user_id': user.id,
                'user_email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'is_admin': getattr(user, 'isadmin', False),
                'capabilities': self._get_user_capabilities(user)
            }
        )
        return False

    def _has_ai_approval_capability(self, user):
        """Check if user has AI approval capability"""
        try:
            capabilities = getattr(user, 'capabilities', {}) or {}
            return capabilities.get('can_approve_ai_recommendations', False)
        except (AttributeError, TypeError):
            return False

    def _has_explicit_ai_approver_capability(self, user):
        """Check if user has explicit AI approver capability"""
        try:
            capabilities = getattr(user, 'capabilities', {}) or {}
            return (
                capabilities.get('ai_recommendation_approver', False) or
                capabilities.get('system_administrator', False) or
                capabilities.get('tenant_administrator', False)
            )
        except (AttributeError, TypeError):
            return False

    def _get_user_capabilities(self, user):
        """Get user capabilities for logging (security audit)"""
        try:
            return getattr(user, 'capabilities', {}) or {}
        except (AttributeError, TypeError):
            return {}


class CanManageKnowledgeBase(permissions.BasePermission):
    """
    Permission class for knowledge base management operations.

    Required for:
    - Creating/updating authoritative knowledge
    - Managing knowledge sources
    - Document ingestion operations
    """

    message = "You do not have permission to manage the knowledge base."

    def has_permission(self, request, view):
        """Check if user can manage knowledge base"""
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        # Super users and staff have access
        if user.is_superuser or user.is_staff:
            return True

        # Check for knowledge management capability
        try:
            capabilities = getattr(user, 'capabilities', {}) or {}
            return (
                capabilities.get('can_manage_knowledge_base', False) or
                capabilities.get('content_curator', False) or
                getattr(user, 'isadmin', False)
            )
        except (AttributeError, TypeError):
            return False


class CanEscalateConversations(permissions.BasePermission):
    """
    Permission class for conversation escalation operations.

    Required for:
    - Escalating conversations to human reviewers
    - Creating helpdesk tickets from conversations
    """

    message = "You do not have permission to escalate conversations."

    def has_permission(self, request, view):
        """Check if user can escalate conversations"""
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        # All authenticated users can escalate their own conversations
        # Additional checks in view logic for cross-user escalations
        return True


class CanViewConversationAudit(permissions.BasePermission):
    """
    Permission class for viewing conversation audit logs and analytics.

    Required for:
    - Viewing conversation audit trails
    - Accessing AI recommendation analytics
    - System monitoring dashboards
    """

    message = "You do not have permission to view audit information."

    def has_permission(self, request, view):
        """Check if user can view audit information"""
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        # Super users and staff have access
        if user.is_superuser or user.is_staff:
            return True

        # Check for audit viewing capability
        try:
            capabilities = getattr(user, 'capabilities', {}) or {}
            return (
                capabilities.get('can_view_audit_logs', False) or
                capabilities.get('system_monitor', False) or
                getattr(user, 'isadmin', False)
            )
        except (AttributeError, TypeError):
            return False


class AIRecommendationSecurityLogger:
    """
    Security logger for AI recommendation operations.

    Provides comprehensive audit logging for all AI recommendation
    approval, rejection, and application operations.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.AIRecommendationAudit")

    def log_approval_attempt(self, user, session_id, recommendation_data, result):
        """Log AI recommendation approval attempt"""
        self.logger.info(
            f"AI recommendation approval attempt",
            extra={
                'event_type': 'ai_recommendation_approval',
                'user_id': user.id,
                'user_email': user.email,
                'session_id': str(session_id),
                'recommendation_count': len(recommendation_data.get('recommendations', [])),
                'approval_result': result,
                'timestamp': self._get_timestamp(),
                'user_capabilities': getattr(user, 'capabilities', {}),
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            }
        )

    def log_application_result(self, user, session_id, applied_changes, success, error=None):
        """Log AI recommendation application result"""
        self.logger.info(
            f"AI recommendation application result",
            extra={
                'event_type': 'ai_recommendation_application',
                'user_id': user.id,
                'session_id': str(session_id),
                'changes_applied': len(applied_changes),
                'success': success,
                'error': str(error) if error else None,
                'timestamp': self._get_timestamp(),
                'change_details': [
                    {
                        'model': change.get('model'),
                        'action': change.get('action'),
                        'object_id': change.get('object_id')
                    }
                    for change in applied_changes[:10]  # Limit to first 10 for log size
                ]
            }
        )

    def log_security_violation(self, user, attempted_action, reason):
        """Log security violation attempts"""
        self.logger.warning(
            f"AI recommendation security violation",
            extra={
                'event_type': 'security_violation',
                'user_id': user.id if user else None,
                'attempted_action': attempted_action,
                'violation_reason': reason,
                'timestamp': self._get_timestamp(),
                'user_agent': getattr(user, 'last_login', None),
            }
        )

    def _get_timestamp(self):
        """Get current timestamp for logging"""
        from django.utils import timezone
        return timezone.now().isoformat()


# Singleton instance for security logging
security_logger = AIRecommendationSecurityLogger()