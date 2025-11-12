"""
Quick Actions Service

Provides one-click actions for Team Dashboard items.
Handles assignment, completion, and help requests across different item types.

Following CLAUDE.md:
- Rule #7: Service layer pattern (ADR 003)
- Rule #11: Specific exception handling
- Rule #17: Multi-tenant security
"""

import logging
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger(__name__)


class QuickActionsService:
    """
    Service for quick actions on dashboard items.
    
    Provides user-friendly operations:
    - Take ownership
    - Mark complete
    - Request help
    - Reassign
    """
    
    @staticmethod
    @transaction.atomic
    def assign_to_me(
        item_type: str,
        item_id: int,
        user,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Take ownership of a task.
        
        Args:
            item_type: Type of item (TICKET, INCIDENT, JOB)
            item_id: Item ID
            user: User taking ownership
            note: Optional note about taking the task
            
        Returns:
            Result dictionary with success status and message
        """
        try:
            if item_type == 'TICKET':
                from apps.y_helpdesk.models import Ticket
                item = Ticket.objects.select_for_update().get(
                    id=item_id,
                    tenant=user.tenant
                )
                item.assignedtopeople = user
                item.save(update_fields=['assignedtopeople', 'mdtz'])
                
                # Log action
                from apps.y_helpdesk.models import AuditLog
                AuditLog.objects.create(
                    ticket=item,
                    action='ASSIGNED',
                    performed_by=user,
                    details=f"Assigned to {user.get_full_name()}" + (f" - {note}" if note else ""),
                    tenant=user.tenant
                )
                
            elif item_type == 'INCIDENT':
                from apps.noc.models import NOCIncident
                item = NOCIncident.objects.select_for_update().get(
                    id=item_id,
                    tenant=user.tenant
                )
                item.assigned_to = user
                if item.state == 'NEW':
                    item.state = 'ASSIGNED'
                item.save(update_fields=['assigned_to', 'state', 'mdtz'])
                
            elif item_type == 'JOB':
                from apps.activity.models import Job
                item = Job.objects.select_for_update().get(
                    id=item_id,
                    tenant=user.tenant
                )
                item.people = user
                item.save(update_fields=['people', 'mdtz'])
                
            else:
                return {
                    'success': False,
                    'message': f'Unknown item type: {item_type}'
                }
            
            # Invalidate dashboard cache
            from apps.core.services.team_dashboard_service import TeamDashboardService
            TeamDashboardService.invalidate_cache(user.tenant.id, user.id)
            
            logger.info(
                f"User {user.id} took ownership of {item_type} {item_id}",
                extra={
                    'user_id': user.id,
                    'item_type': item_type,
                    'item_id': item_id,
                    'tenant_id': user.tenant.id
                }
            )
            
            return {
                'success': True,
                'message': f"You're now working on this {item_type.lower()}! 🎯",
                'item_id': item_id,
                'item_type': item_type
            }
            
        except ObjectDoesNotExist:
            return {
                'success': False,
                'message': f'{item_type.capitalize()} not found or access denied.'
            }
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error assigning {item_type} {item_id}: {e}",
                exc_info=True,
                extra={'user_id': user.id, 'item_type': item_type, 'item_id': item_id}
            )
            return {
                'success': False,
                'message': 'Unable to assign task. Please try again.'
            }
    
    @staticmethod
    @transaction.atomic
    def mark_complete(
        item_type: str,
        item_id: int,
        user,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark task as done.
        
        Args:
            item_type: Type of item
            item_id: Item ID
            user: User completing the task
            note: Optional completion note
            
        Returns:
            Result dictionary
        """
        try:
            if item_type == 'TICKET':
                from apps.y_helpdesk.models import Ticket
                item = Ticket.objects.select_for_update().get(
                    id=item_id,
                    tenant=user.tenant
                )
                
                # Verify user has permission
                if item.assignedtopeople != user and not user.is_staff:
                    raise PermissionDenied("You can only complete your own tickets.")
                
                item.status = 'RESOLVED'
                item.save(update_fields=['status', 'mdtz'])
                
                # Log completion
                from apps.y_helpdesk.models import AuditLog
                AuditLog.objects.create(
                    ticket=item,
                    action='RESOLVED',
                    performed_by=user,
                    details=f"Marked complete by {user.get_full_name()}" + (f" - {note}" if note else ""),
                    tenant=user.tenant
                )
                
            elif item_type == 'INCIDENT':
                from apps.noc.models import NOCIncident
                item = NOCIncident.objects.select_for_update().get(
                    id=item_id,
                    tenant=user.tenant
                )
                
                if item.assigned_to != user and not user.is_staff:
                    raise PermissionDenied("You can only complete your own incidents.")
                
                item.state = 'RESOLVED'
                item.resolution_notes = note or "Resolved via Team Dashboard"
                item.resolved_at = timezone.now()
                item.save(update_fields=['state', 'resolution_notes', 'resolved_at', 'mdtz'])
                
            elif item_type == 'JOB':
                return {
                    'success': False,
                    'message': 'Jobs cannot be marked complete. Disable the job instead.'
                }
            else:
                return {
                    'success': False,
                    'message': f'Unknown item type: {item_type}'
                }
            
            # Invalidate cache
            from apps.core.services.team_dashboard_service import TeamDashboardService
            TeamDashboardService.invalidate_cache(user.tenant.id, user.id)
            
            logger.info(
                f"User {user.id} completed {item_type} {item_id}",
                extra={
                    'user_id': user.id,
                    'item_type': item_type,
                    'item_id': item_id,
                    'tenant_id': user.tenant.id
                }
            )
            
            return {
                'success': True,
                'message': f"Great work! {item_type.capitalize()} marked as complete. 🎉",
                'item_id': item_id,
                'item_type': item_type
            }
            
        except ObjectDoesNotExist:
            return {
                'success': False,
                'message': f'{item_type.capitalize()} not found or access denied.'
            }
        except PermissionDenied as e:
            return {
                'success': False,
                'message': str(e)
            }
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error completing {item_type} {item_id}: {e}",
                exc_info=True,
                extra={'user_id': user.id, 'item_type': item_type, 'item_id': item_id}
            )
            return {
                'success': False,
                'message': 'Unable to complete task. Please try again.'
            }
    
    @staticmethod
    @transaction.atomic
    def request_help(
        item_type: str,
        item_id: int,
        user,
        help_message: str
    ) -> Dict[str, Any]:
        """
        Ask for help with this task.
        
        Creates a ticket or comment requesting assistance.
        
        Args:
            item_type: Type of item
            item_id: Item ID
            user: User requesting help
            help_message: Description of help needed
            
        Returns:
            Result dictionary
        """
        try:
            # Create a ticket for help request
            from apps.y_helpdesk.models import Ticket
            
            help_ticket = Ticket.objects.create(
                ticketdesc=f"Help Needed: {item_type} #{item_id}\n\n{help_message}",
                priority='HIGH',
                status='NEW',
                identifier='REQUEST',
                ticketcategory_id=1,  # Help Request category
                tenant=user.tenant,
                created_by=user
            )
            
            # Generate ticket number
            help_ticket.ticketno = f"T{help_ticket.id:05d}"
            help_ticket.save(update_fields=['ticketno'])
            
            logger.info(
                f"User {user.id} requested help for {item_type} {item_id}",
                extra={
                    'user_id': user.id,
                    'item_type': item_type,
                    'item_id': item_id,
                    'help_ticket_id': help_ticket.id,
                    'tenant_id': user.tenant.id
                }
            )
            
            return {
                'success': True,
                'message': f"Help request created! Ticket #{help_ticket.ticketno} 🆘",
                'help_ticket_id': help_ticket.id,
                'help_ticket_no': help_ticket.ticketno
            }
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error creating help request for {item_type} {item_id}: {e}",
                exc_info=True,
                extra={'user_id': user.id, 'item_type': item_type, 'item_id': item_id}
            )
            return {
                'success': False,
                'message': 'Unable to create help request. Please contact your supervisor.'
            }
