"""
Parlant Tools for Ticket Assistant.

Async tool definitions for ticket operations, knowledge base search,
and escalation management.

Follows .claude/rules.md Rule #11 (specific exception handling).
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Parlant will be imported when available
try:
    import parlant.sdk as p
except ImportError:
    # Fallback for environments without Parlant
    p = None

from django.db import DatabaseError, IntegrityError
from django.utils import timezone
from asgiref.sync import sync_to_async

from apps.y_helpdesk.models import Ticket
from apps.peoples.models import People

logger = logging.getLogger('helpbot.parlant.tools')


def extract_ticket_number(text: str) -> Optional[str]:
    """
    Extract ticket number from user message.

    Accepts formats: T00123, #123, ticket 123, 123

    Args:
        text: User message text

    Returns:
        Normalized ticket number (TXXXXX format) or None
    """
    # Try various patterns
    patterns = [
        r'T\d{5}',  # T00123
        r'#(\d+)',  # #123
        r'ticket\s+(\d+)',  # ticket 123
        r'\b(\d{3,5})\b',  # 123 (standalone number)
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract number
            if pattern.startswith('T'):
                return match.group(0)
            else:
                num = match.group(1) if '(' in pattern else match.group(0)
                # Normalize to TXXXXX format
                return f"T{int(num):05d}"

    return None


def detect_priority(description: str) -> str:
    """
    Detect ticket priority from description using keyword analysis.

    Args:
        description: Ticket description text

    Returns:
        Priority level: HIGH, MEDIUM, or LOW
    """
    description_lower = description.lower()

    # HIGH priority keywords
    high_keywords = [
        'urgent', 'emergency', 'asap', 'critical', 'immediately', 'right now',
        'down', 'not working', 'broken', 'failed', 'failure', 'security breach',
        'fire', 'safety', 'danger'
    ]

    # LOW priority keywords
    low_keywords = [
        'question', 'suggestion', 'when available', 'whenever', 'future',
        'enhancement', 'nice to have', 'if possible'
    ]

    # Check HIGH priority first
    if any(keyword in description_lower for keyword in high_keywords):
        return 'HIGH'

    # Check LOW priority
    if any(keyword in description_lower for keyword in low_keywords):
        return 'LOW'

    # Default to MEDIUM
    return 'MEDIUM'


def detect_category(description: str) -> Optional[str]:
    """
    Detect ticket category from description.

    Args:
        description: Ticket description text

    Returns:
        Category name or None
    """
    description_lower = description.lower()

    categories = {
        'Access': ['login', 'password', 'access', 'card', 'permission', 'auth', 'unlock'],
        'Equipment': ['laptop', 'phone', 'equipment', 'device', 'hardware', 'computer'],
        'Facility': ['ac', 'air conditioning', 'lights', 'door', 'room', 'building', 'facility'],
        'IT Support': ['software', 'email', 'internet', 'network', 'system', 'application'],
        'Maintenance': ['repair', 'fix', 'broken', 'maintenance', 'service'],
    }

    for category, keywords in categories.items():
        if any(keyword in description_lower for keyword in keywords):
            return category

    return None


# Tool 1: Check Ticket Status
@p.tool
async def check_ticket_status(
    context: p.ToolContext,
    ticket_number: str
) -> p.ToolResult:
    """
    Check the status of a ticket by number.

    Args:
        context: Parlant tool context
        ticket_number: Ticket number (TXXXXX format)

    Returns:
        ToolResult with ticket status information
    """
    try:
        # Normalize ticket number
        if not ticket_number.startswith('T'):
            ticket_number = extract_ticket_number(f"T{ticket_number}")

        # Query ticket
        ticket = await sync_to_async(
            Ticket.objects.select_related('assignedtopeople', 'client').filter(
                ticketno=ticket_number
            ).first
        )()

        if not ticket:
            return p.ToolResult(
                success=False,
                error=f"No ticket found with number {ticket_number}"
            )

        # Calculate time metrics
        created_delta = timezone.now() - ticket.cdtz
        days_open = created_delta.days
        hours_open = created_delta.total_seconds() / 3600

        # Get last update time
        try:
            last_update = ticket.modifieddatetime
            if last_update:
                update_delta = timezone.now() - last_update
                hours_since_update = update_delta.total_seconds() / 3600
            else:
                hours_since_update = hours_open
        except Exception:
            hours_since_update = hours_open

        return p.ToolResult({
            'ticket_number': ticket.ticketno,
            'status': ticket.status,
            'priority': ticket.priority or 'MEDIUM',
            'description': ticket.ticketdesc[:200],  # First 200 chars
            'assigned_to': ticket.assignedtopeople.peoplename if ticket.assignedtopeople else 'Unassigned',
            'created_date': ticket.cdtz.isoformat(),
            'days_open': days_open,
            'hours_open': round(hours_open, 1),
            'hours_since_update': round(hours_since_update, 1),
            'client': ticket.client.buname if ticket.client else 'Unknown',
            'is_delayed': (ticket.priority == 'HIGH' and hours_open > 24) or
                         (ticket.priority == 'MEDIUM' and hours_open > 72),
        })

    except DatabaseError as e:
        logger.error(f"Database error checking ticket status: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Database error checking ticket")
    except Exception as e:
        logger.error(f"Unexpected error checking ticket status: {e}", exc_info=True)
        return p.ToolResult(success=False, error=f"Error: {str(e)}")


# Tool 2: Get My Open Tickets
@p.tool
async def get_my_open_tickets(
    context: p.ToolContext,
    limit: int = 10
) -> p.ToolResult:
    """
    Get all open tickets for the current user.

    Args:
        context: Parlant tool context
        limit: Maximum number of tickets to return (default 10)

    Returns:
        ToolResult with list of open tickets
    """
    try:
        user = context.session_data.get('user')
        if not user:
            return p.ToolResult(success=False, error="User not found in session")

        user_id = user.id if hasattr(user, 'id') else user

        # Query open tickets
        tickets = await sync_to_async(list)(
            Ticket.objects.select_related('assignedtopeople', 'client')
            .filter(
                assignedtopeople_id=user_id,
                status__in=['NEW', 'OPEN', 'ASSIGNED']
            )
            .order_by('-priority', '-cdtz')
            [:limit]
        )

        if not tickets:
            return p.ToolResult({
                'ticket_count': 0,
                'tickets': [],
                'message': 'You have no open tickets'
            })

        # Format ticket list
        ticket_list = []
        priority_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}

        for ticket in tickets:
            created_delta = timezone.now() - ticket.cdtz
            days_open = created_delta.days

            priority = ticket.priority or 'MEDIUM'
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

            ticket_list.append({
                'ticket_number': ticket.ticketno,
                'description': ticket.ticketdesc[:50] + '...' if len(ticket.ticketdesc) > 50 else ticket.ticketdesc,
                'priority': priority,
                'status': ticket.status,
                'days_open': days_open,
                'created_date': ticket.cdtz.isoformat(),
            })

        return p.ToolResult({
            'ticket_count': len(ticket_list),
            'tickets': ticket_list,
            'priority_summary': priority_counts,
            'has_high_priority': priority_counts.get('HIGH', 0) > 0,
        })

    except DatabaseError as e:
        logger.error(f"Database error getting open tickets: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Database error retrieving tickets")
    except Exception as e:
        logger.error(f"Unexpected error getting open tickets: {e}", exc_info=True)
        return p.ToolResult(success=False, error=f"Error: {str(e)}")


# Tool 3: Create Ticket Draft
@p.tool
async def create_ticket_draft(
    context: p.ToolContext,
    description: str,
    priority: Optional[str] = None
) -> p.ToolResult:
    """
    Create a draft ticket (requires user confirmation before submission).

    Args:
        context: Parlant tool context
        description: Ticket description
        priority: Optional priority (HIGH/MEDIUM/LOW), auto-detected if not provided

    Returns:
        ToolResult with draft ticket information
    """
    try:
        # Auto-detect priority if not provided
        if not priority:
            priority = detect_priority(description)

        # Auto-detect category
        category = detect_category(description)

        # Estimate response time based on priority
        response_times = {
            'HIGH': '4 hours',
            'MEDIUM': '24 hours',
            'LOW': '48 hours'
        }

        draft = {
            'description': description,
            'priority': priority,
            'category': category or 'General',
            'status': 'DRAFT',
            'estimated_response': response_times.get(priority, '24 hours'),
            'ready_to_submit': True,
        }

        return p.ToolResult({
            'draft': draft,
            'message': f"Draft ticket created with {priority} priority",
            'confirmation_required': True,
        })

    except Exception as e:
        logger.error(f"Error creating ticket draft: {e}", exc_info=True)
        return p.ToolResult(success=False, error=f"Error creating draft: {str(e)}")


# Tool 4: Submit Ticket
@p.tool
async def submit_ticket(
    context: p.ToolContext,
    description: str,
    priority: str = 'MEDIUM',
    category: Optional[str] = None
) -> p.ToolResult:
    """
    Submit a new ticket after user confirmation.

    Args:
        context: Parlant tool context
        description: Ticket description
        priority: Ticket priority (HIGH/MEDIUM/LOW)
        category: Optional category

    Returns:
        ToolResult with created ticket number
    """
    try:
        user = context.session_data.get('user')
        client = context.session_data.get('client')
        tenant = context.session_data.get('tenant')

        if not user or not client:
            return p.ToolResult(
                success=False,
                error="Missing user or client context"
            )

        # Create ticket
        ticket = await sync_to_async(Ticket.objects.create)(
            ticketdesc=description,
            client=client,
            bu=client,
            priority=priority,
            status='NEW',
            ticketsource='AI_ASSISTANT',
            cuser=user,
            tenant=tenant,
        )

        # Calculate estimated response time
        response_times = {
            'HIGH': '4 hours',
            'MEDIUM': '24 hours',
            'LOW': '48 hours'
        }

        return p.ToolResult({
            'success': True,
            'ticket_number': ticket.ticketno,
            'ticket_id': ticket.id,
            'priority': priority,
            'estimated_response': response_times.get(priority, '24 hours'),
            'message': f"Ticket {ticket.ticketno} created successfully",
        })

    except IntegrityError as e:
        logger.error(f"Integrity error creating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Failed to create ticket (integrity error)")
    except DatabaseError as e:
        logger.error(f"Database error creating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Database error creating ticket")
    except Exception as e:
        logger.error(f"Unexpected error creating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error=f"Error: {str(e)}")


# Tool 5: Search Knowledge Base
@p.tool
async def search_knowledge_base(
    context: p.ToolContext,
    question: str,
    limit: int = 3
) -> p.ToolResult:
    """
    Search HelpBot knowledge base for solutions.

    Args:
        context: Parlant tool context
        question: User's question or search query
        limit: Maximum number of results (default 3)

    Returns:
        ToolResult with search results
    """
    try:
        from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService

        knowledge_service = HelpBotKnowledgeService()

        # Search knowledge base
        results = await sync_to_async(knowledge_service.search_knowledge)(
            query=question,
            category='helpdesk',  # Focus on helpdesk-related knowledge
            limit=limit
        )

        if not results:
            return p.ToolResult({
                'found': False,
                'results': [],
                'message': "I couldn't find an answer in the knowledge base. Would you like me to create a ticket or connect you with support?",
            })

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                'title': result.get('title', 'Untitled'),
                'content': result.get('content', '')[:500],  # First 500 chars
                'category': result.get('category', 'General'),
                'effectiveness_score': result.get('effectiveness_score', 0.5),
            })

        # Determine confidence based on top result's effectiveness score
        top_score = formatted_results[0].get('effectiveness_score', 0.5) if formatted_results else 0
        confidence = 'high' if top_score > 0.8 else 'medium' if top_score > 0.5 else 'low'

        return p.ToolResult({
            'found': True,
            'results': formatted_results,
            'result_count': len(formatted_results),
            'confidence': confidence,
            'top_result': formatted_results[0] if formatted_results else None,
        })

    except ImportError:
        logger.error("Knowledge service not available")
        return p.ToolResult(success=False, error="Knowledge base service unavailable")
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}", exc_info=True)
        return p.ToolResult(success=False, error=f"Search error: {str(e)}")


# Tool 6: Escalate Ticket
@p.tool
async def escalate_ticket(
    context: p.ToolContext,
    ticket_number: str,
    reason: str,
    priority: str = 'HIGH'
) -> p.ToolResult:
    """
    Escalate a ticket to supervisor or higher priority.

    Args:
        context: Parlant tool context
        ticket_number: Ticket number to escalate
        reason: Reason for escalation
        priority: New priority level (default HIGH)

    Returns:
        ToolResult with escalation confirmation
    """
    try:
        # Normalize ticket number
        if not ticket_number.startswith('T'):
            ticket_number = extract_ticket_number(f"T{ticket_number}")

        # Get ticket
        ticket = await sync_to_async(
            Ticket.objects.select_related('assignedtopeople').filter(
                ticketno=ticket_number
            ).first
        )()

        if not ticket:
            return p.ToolResult(
                success=False,
                error=f"Ticket {ticket_number} not found"
            )

        # Update ticket priority and add escalation note
        original_priority = ticket.priority
        ticket.priority = priority

        # Update ticket log
        escalation_entry = {
            'when': timezone.now().isoformat(),
            'who': 'AI Assistant',
            'action': 'ESCALATED',
            'details': f"Escalated from {original_priority} to {priority}. Reason: {reason}",
            'previous_priority': original_priority,
        }

        # Get current ticketlog and append
        current_log = ticket.ticketlog or {"ticket_history": []}
        current_log["ticket_history"].append(escalation_entry)
        ticket.ticketlog = current_log

        await sync_to_async(ticket.save)(update_fields=['priority'])

        return p.ToolResult({
            'success': True,
            'ticket_number': ticket_number,
            'original_priority': original_priority,
            'new_priority': priority,
            'escalation_reason': reason,
            'message': f"Ticket {ticket_number} escalated to {priority} priority",
            'assigned_to': ticket.assignedtopeople.peoplename if ticket.assignedtopeople else 'Unassigned',
        })

    except DatabaseError as e:
        logger.error(f"Database error escalating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Database error escalating ticket")
    except Exception as e:
        logger.error(f"Unexpected error escalating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error=f"Error: {str(e)}")


# Tool 7: Update Ticket Status
@p.tool
async def update_ticket_status(
    context: p.ToolContext,
    ticket_number: str,
    new_status: str,
    comment: Optional[str] = None
) -> p.ToolResult:
    """
    Update ticket status (for closing resolved tickets, etc.).

    Args:
        context: Parlant tool context
        ticket_number: Ticket number
        new_status: New status (OPEN/RESOLVED/CLOSED)
        comment: Optional comment for the status change

    Returns:
        ToolResult with update confirmation
    """
    try:
        # Validate status
        valid_statuses = ['OPEN', 'RESOLVED', 'CLOSED', 'ONHOLD', 'CANCELLED']
        if new_status not in valid_statuses:
            return p.ToolResult(
                success=False,
                error=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Normalize ticket number
        if not ticket_number.startswith('T'):
            ticket_number = extract_ticket_number(f"T{ticket_number}")

        # Get ticket
        ticket = await sync_to_async(
            Ticket.objects.filter(ticketno=ticket_number).first
        )()

        if not ticket:
            return p.ToolResult(
                success=False,
                error=f"Ticket {ticket_number} not found"
            )

        # Update status
        old_status = ticket.status
        ticket.status = new_status

        if comment:
            ticket.comments = comment

        # Add to history
        status_entry = {
            'when': timezone.now().isoformat(),
            'who': 'AI Assistant',
            'action': 'STATUS_CHANGED',
            'details': f"Status changed from {old_status} to {new_status}. {comment or ''}",
            'previous_status': old_status,
        }

        current_log = ticket.ticketlog or {"ticket_history": []}
        current_log["ticket_history"].append(status_entry)
        ticket.ticketlog = current_log

        await sync_to_async(ticket.save)(update_fields=['status', 'comments'])

        return p.ToolResult({
            'success': True,
            'ticket_number': ticket_number,
            'old_status': old_status,
            'new_status': new_status,
            'message': f"Ticket {ticket_number} status updated to {new_status}",
        })

    except DatabaseError as e:
        logger.error(f"Database error updating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Database error updating ticket")
    except Exception as e:
        logger.error(f"Unexpected error updating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error=f"Error: {str(e)}")


# Export all tools
ALL_TICKET_TOOLS = [
    check_ticket_status,
    get_my_open_tickets,
    create_ticket_draft,
    submit_ticket,
    search_knowledge_base,
    escalate_ticket,
    update_ticket_status,
]
