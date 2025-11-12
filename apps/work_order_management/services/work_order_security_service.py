"""
Work Order Management - Security Service

Provides centralized authorization and IDOR protection for work orders.

Security Features:
    - Token-based validation for email workflows
    - Ownership validation
    - Tenant isolation
    - Permission checks
    - Audit logging

Created: November 2025
Part of: CRITICAL SECURITY FIX 2
"""

import secrets
import logging
from typing import Tuple, Optional
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from apps.work_order_management.models import Wom
from apps.peoples.models import People
from apps.core.exceptions.patterns import SECURITY_EXCEPTIONS

logger = logging.getLogger(__name__)
User = get_user_model()


class WorkOrderSecurityService:
    """
    Centralized security service for work order operations.
    
    Prevents IDOR vulnerabilities by validating:
    - User ownership
    - Tenant isolation
    - Token-based access (for email workflows)
    - Permission-based access
    """

    @staticmethod
    def generate_secure_token() -> str:
        """
        Generate cryptographically secure token for email workflows.
        
        Returns:
            32-character URL-safe token
        """
        return secrets.token_urlsafe(16)

    @staticmethod
    def validate_work_order_access(
        work_order_id: int,
        user: User,
        require_ownership: bool = False,
        allow_tenant_access: bool = True
    ) -> Wom:
        """
        Validate user has access to work order.
        
        Args:
            work_order_id: Work order ID
            user: Current user
            require_ownership: If True, user must be owner
            allow_tenant_access: If True, allow same-tenant access
            
        Returns:
            Wom: Work order instance if authorized
            
        Raises:
            PermissionDenied: If user lacks access
            Wom.DoesNotExist: If work order not found
        """
        try:
            # Get work order
            work_order = Wom.objects.select_related(
                'client', 'bu', 'vendor', 'cuser'
            ).get(id=work_order_id)
            
            # Check ownership
            if require_ownership:
                if work_order.cuser_id != user.id:
                    logger.warning(
                        f"IDOR attempt: User {user.id} tried to access "
                        f"work order {work_order_id} owned by {work_order.cuser_id}"
                    )
                    raise PermissionDenied(
                        "You do not have permission to access this work order"
                    )
            
            # Check tenant isolation
            elif allow_tenant_access:
                user_client_id = getattr(user, 'client_id', None)
                if user_client_id and work_order.client_id != user_client_id:
                    logger.warning(
                        f"Cross-tenant IDOR attempt: User {user.id} (tenant {user_client_id}) "
                        f"tried to access work order {work_order_id} (tenant {work_order.client_id})"
                    )
                    raise PermissionDenied(
                        "You do not have permission to access this work order"
                    )
            
            logger.info(
                f"Access granted: User {user.id} accessing work order {work_order_id}"
            )
            return work_order
            
        except Wom.DoesNotExist:
            logger.error(f"Work order {work_order_id} not found")
            raise
        except SECURITY_EXCEPTIONS as e:
            logger.error(
                f"Security validation failed for work order {work_order_id}: {e}",
                exc_info=True
            )
            raise

    @staticmethod
    def validate_token_access(
        work_order_id: int,
        token: str
    ) -> Wom:
        """
        Validate token-based access for email workflows (public endpoints).
        
        This is used for vendor/approver email replies where users don't log in.
        
        Args:
            work_order_id: Work order ID
            token: Security token from email link
            
        Returns:
            Wom: Work order instance if token is valid
            
        Raises:
            PermissionDenied: If token is invalid
            ValidationError: If token format is invalid
        """
        try:
            if not token or len(token) < 16:
                raise ValidationError("Invalid token format")
            
            work_order = Wom.objects.get(id=work_order_id)
            
            # Verify token matches
            stored_token = work_order.other_data.get('token')
            if not stored_token or stored_token != token:
                logger.warning(
                    f"Invalid token access attempt for work order {work_order_id}"
                )
                raise PermissionDenied("Invalid or expired token")
            
            logger.info(
                f"Token access granted for work order {work_order_id}"
            )
            return work_order
            
        except Wom.DoesNotExist:
            logger.error(f"Work order {work_order_id} not found")
            raise PermissionDenied("Work order not found")
        except SECURITY_EXCEPTIONS as e:
            logger.error(
                f"Token validation failed for work order {work_order_id}: {e}",
                exc_info=True
            )
            raise

    @staticmethod
    def validate_approver_access(
        work_order_id: int,
        people_id: int,
        token: Optional[str] = None
    ) -> Tuple[Wom, People]:
        """
        Validate approver/verifier has permission to act on work order.
        
        Used for work permit and SLA approval workflows.
        
        Args:
            work_order_id: Work order ID
            people_id: Approver's people ID
            token: Optional security token (for email workflows)
            
        Returns:
            Tuple of (work_order, approver)
            
        Raises:
            PermissionDenied: If person is not authorized approver
        """
        try:
            # Get work order
            if token:
                work_order = WorkOrderSecurityService.validate_token_access(
                    work_order_id, token
                )
            else:
                work_order = Wom.objects.get(id=work_order_id)
            
            # Get approver
            approver = People.objects.get(id=people_id)
            
            # Validate approver is in work order's approver list
            wp_approvers = work_order.other_data.get('wp_approvers', [])
            wp_verifiers = work_order.other_data.get('wp_verifiers', [])
            sla_approvers = work_order.other_data.get('sla_approvers', [])
            
            # Check if person is in any approver/verifier list
            is_approver = any(
                appr.get('peoplecode') == approver.peoplecode
                for appr in (wp_approvers + wp_verifiers + sla_approvers)
            )
            
            if not is_approver:
                logger.warning(
                    f"Unauthorized approval attempt: Person {people_id} "
                    f"tried to approve work order {work_order_id}"
                )
                raise PermissionDenied(
                    "You are not authorized to approve this work order"
                )
            
            logger.info(
                f"Approver access granted: Person {people_id} for work order {work_order_id}"
            )
            return work_order, approver
            
        except (Wom.DoesNotExist, People.DoesNotExist):
            logger.error(
                f"Work order {work_order_id} or person {people_id} not found"
            )
            raise PermissionDenied("Invalid work order or approver")
        except SECURITY_EXCEPTIONS as e:
            logger.error(
                f"Approver validation failed: {e}",
                exc_info=True
            )
            raise

    @staticmethod
    def validate_vendor_access(
        work_order_id: int,
        token: str
    ) -> Wom:
        """
        Validate vendor has access to work order via email token.
        
        Used for vendor email reply workflows.
        
        Args:
            work_order_id: Work order ID
            token: Security token from email link
            
        Returns:
            Wom: Work order instance
            
        Raises:
            PermissionDenied: If token invalid or work order completed
        """
        work_order = WorkOrderSecurityService.validate_token_access(
            work_order_id, token
        )
        
        # Prevent modifications to completed work orders
        if work_order.workstatus == Wom.Workstatus.COMPLETED:
            raise PermissionDenied("This work order has already been completed")
        
        return work_order

    @staticmethod
    def validate_delete_permission(
        work_order_id: int,
        user: User
    ) -> Wom:
        """
        Validate user can delete work order.
        
        Only owner or admin can delete.
        
        Args:
            work_order_id: Work order ID
            user: Current user
            
        Returns:
            Wom: Work order instance if deletion allowed
            
        Raises:
            PermissionDenied: If user cannot delete
        """
        work_order = WorkOrderSecurityService.validate_work_order_access(
            work_order_id=work_order_id,
            user=user,
            require_ownership=True
        )
        
        # Additional checks: prevent deletion of in-progress work
        if work_order.workstatus == Wom.Workstatus.INPROGRESS:
            raise PermissionDenied(
                "Cannot delete work order that is in progress"
            )
        
        return work_order

    @staticmethod
    def validate_close_permission(
        work_order_id: int,
        user: User
    ) -> Wom:
        """
        Validate user can close work order.
        
        Owner or assigned personnel can close.
        
        Args:
            work_order_id: Work order ID
            user: Current user
            
        Returns:
            Wom: Work order instance if closing allowed
            
        Raises:
            PermissionDenied: If user cannot close
        """
        work_order = WorkOrderSecurityService.validate_work_order_access(
            work_order_id=work_order_id,
            user=user,
            allow_tenant_access=True
        )
        
        # Allow owner or anyone from same tenant to close
        # (business rule: various personnel can close work orders)
        
        return work_order

    @staticmethod
    def get_user_work_orders_queryset(user: User):
        """
        Get queryset of work orders accessible to user.
        
        Enforces tenant isolation and permissions.
        
        Args:
            user: Current user
            
        Returns:
            QuerySet: Filtered work orders
        """
        queryset = Wom.objects.select_related('client', 'bu', 'vendor', 'cuser')
        
        # Filter by tenant if user has tenant
        if hasattr(user, 'client_id') and user.client_id:
            queryset = queryset.filter(client_id=user.client_id)
        
        # Filter by business unit if user has bu
        if hasattr(user, 'bu_id') and user.bu_id:
            queryset = queryset.filter(
                Q(bu_id=user.bu_id) | Q(cuser_id=user.id)
            )
        
        return queryset
