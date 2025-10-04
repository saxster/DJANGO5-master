"""
Parlant Tools for Security & Facility Mentor.

Async tool definitions for scorecard operations, violation management,
alert creation, and remediation actions.

Follows .claude/rules.md Rule #11 (specific exception handling).
"""

import logging
from typing import Dict, Any, Optional
from datetime import date, datetime

# Parlant will be imported when available
try:
    import parlant.sdk as p
except ImportError:
    # Fallback for environments without Parlant
    p = None

from django.db import DatabaseError
from asgiref.sync import sync_to_async

from apps.noc.security_intelligence.services import NonNegotiablesService
from apps.noc.services import AlertCorrelationService
from apps.y_helpdesk.models import Ticket

logger = logging.getLogger('helpbot.parlant.tools')


# Tool 1: Get Scorecard
@p.tool
async def get_scorecard(
    context: p.ToolContext,
    check_date: Optional[str] = None
) -> p.ToolResult:
    """
    Get comprehensive scorecard for user's client.

    Args:
        context: Parlant tool context (contains tenant, client, user)
        check_date: Optional date in YYYY-MM-DD format

    Returns:
        ToolResult with scorecard data
    """
    try:
        tenant = context.session_data.get('tenant')
        client = context.session_data.get('client')

        if not tenant or not client:
            return p.ToolResult(
                success=False,
                error="Missing tenant or client context"
            )

        # Parse check_date if provided
        if check_date:
            check_date_obj = datetime.strptime(check_date, '%Y-%m-%d').date()
        else:
            check_date_obj = date.today()

        # Generate scorecard (sync function, wrap in async)
        service = NonNegotiablesService()
        scorecard = await sync_to_async(service.generate_scorecard)(
            tenant=tenant,
            client=client,
            check_date=check_date_obj
        )

        return p.ToolResult({
            'check_date': scorecard.check_date.isoformat(),
            'client_name': client.buname,
            'overall_health_status': scorecard.overall_health_status,
            'overall_health_score': scorecard.overall_health_score,
            'total_violations': scorecard.total_violations,
            'critical_violations': scorecard.critical_violations,
            'pillar_scores': {
                '1': scorecard.pillar_1_score,
                '2': scorecard.pillar_2_score,
                '3': scorecard.pillar_3_score,
                '4': scorecard.pillar_4_score,
                '5': scorecard.pillar_5_score,
                '6': scorecard.pillar_6_score,
                '7': scorecard.pillar_7_score,
            },
            'violations_detail': scorecard.violations_detail,
            'recommendations': scorecard.recommendations,
        })

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        return p.ToolResult(success=False, error=f"Invalid date format. Use YYYY-MM-DD.")
    except DatabaseError as e:
        logger.error(f"Database error getting scorecard: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Database error. Please try again.")


# Tool 2: Get Violations for Specific Pillar
@p.tool
async def get_pillar_violations(
    context: p.ToolContext,
    pillar_id: int
) -> p.ToolResult:
    """
    Get detailed violations for a specific pillar.

    Args:
        context: Parlant tool context
        pillar_id: Pillar number (1-7)

    Returns:
        ToolResult with violation details
    """
    try:
        if pillar_id < 1 or pillar_id > 7:
            return p.ToolResult(success=False, error="Pillar ID must be 1-7")

        # Get latest scorecard
        scorecard_result = await get_scorecard(context)
        if not scorecard_result.success:
            return scorecard_result

        scorecard_data = scorecard_result.data
        violations = scorecard_data['violations_detail'].get(f'pillar_{pillar_id}', [])

        pillar_names = {
            1: "Right Guard at Right Post",
            2: "Supervise Relentlessly",
            3: "24/7 Control Desk",
            4: "Legal & Professional",
            5: "Support the Field",
            6: "Record Everything",
            7: "Respond to Emergencies",
        }

        return p.ToolResult({
            'pillar_id': pillar_id,
            'pillar_name': pillar_names[pillar_id],
            'violations': violations,
            'violation_count': len(violations),
            'pillar_score': scorecard_data['pillar_scores'][str(pillar_id)],
        })

    except (KeyError, AttributeError) as e:
        logger.error(f"Error getting pillar violations: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Could not retrieve pillar violations")


# Tool 3: Create NOC Alert from Violation
@p.tool
async def escalate_violation(
    context: p.ToolContext,
    pillar_id: int,
    violation_type: str,
    description: str,
    severity: str = "HIGH"
) -> p.ToolResult:
    """
    Create NOC alert and escalate violation.

    Args:
        context: Parlant tool context
        pillar_id: Pillar number (1-7)
        violation_type: Type of violation
        description: Human-readable description
        severity: Alert severity (CRITICAL, HIGH, MEDIUM)

    Returns:
        ToolResult with alert ID
    """
    try:
        tenant = context.session_data.get('tenant')
        client = context.session_data.get('client')

        pillar_names = {
            1: "Right Guard at Right Post",
            2: "Supervise Relentlessly",
            3: "24/7 Control Desk",
            4: "Legal & Professional",
            5: "Support the Field",
            6: "Record Everything",
            7: "Respond to Emergencies",
        }

        alert_data = {
            'tenant': tenant,
            'client': client,
            'bu': client,
            'alert_type': violation_type,
            'severity': severity,
            'message': f"[Pillar {pillar_id}: {pillar_names[pillar_id]}] {description}",
            'entity_type': 'non_negotiable_violation',
            'entity_id': pillar_id,
            'metadata': {
                'pillar_id': pillar_id,
                'pillar_name': pillar_names[pillar_id],
                'created_from': 'parlant_conversation',
            }
        }

        alert = await sync_to_async(AlertCorrelationService.process_alert)(alert_data)

        if alert:
            return p.ToolResult({
                'success': True,
                'alert_id': alert.id,
                'message': f"Alert #{alert.id} created and escalated to on-call manager",
            })
        else:
            return p.ToolResult(success=False, error="Alert creation failed (possibly duplicate)")

    except DatabaseError as e:
        logger.error(f"Error creating alert: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Database error creating alert")


# Tool 4: Create Field Support Ticket
@p.tool
async def create_field_support_ticket(
    context: p.ToolContext,
    description: str,
    priority: str = "MEDIUM",
    assigned_to_id: Optional[int] = None
) -> p.ToolResult:
    """
    Create field support ticket for guard resources.

    Args:
        context: Parlant tool context
        description: Ticket description
        priority: Ticket priority (LOW, MEDIUM, HIGH, CRITICAL)
        assigned_to_id: Optional person ID to assign to

    Returns:
        ToolResult with ticket number
    """
    try:
        user = context.session_data.get('user')
        client = context.session_data.get('client')

        # Create ticket
        ticket = await sync_to_async(Ticket.objects.create)(
            ticketdesc=description,
            client=client,
            bu=client,
            priority=priority,
            status='NEW',
            ticketsource='AI_MENTOR',
            cuser=user,
        )

        return p.ToolResult({
            'success': True,
            'ticket_number': ticket.ticketno,
            'ticket_id': ticket.id,
            'message': f"Ticket #{ticket.ticketno} created successfully",
        })

    except DatabaseError as e:
        logger.error(f"Error creating ticket: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Failed to create ticket")


# Tool 5: Get SOP Document (RAG Integration)
@p.tool
async def fetch_sop(
    context: p.ToolContext,
    sop_code: str
) -> p.ToolResult:
    """
    Fetch Standard Operating Procedure document.

    Args:
        context: Parlant tool context
        sop_code: SOP identifier (e.g., 'SEC-007' for mandatory tours)

    Returns:
        ToolResult with SOP content
    """
    try:
        # Integration with existing knowledge base
        from apps.helpbot.services import HelpBotKnowledgeService

        knowledge_service = HelpBotKnowledgeService()

        # Search for SOP in knowledge base
        results = await sync_to_async(knowledge_service.search_knowledge)(
            query=f"SOP {sop_code}",
            category='operations',
            limit=1
        )

        if results:
            sop = results[0]
            return p.ToolResult({
                'sop_code': sop_code,
                'title': sop['title'],
                'content': sop['content'][:500],  # First 500 chars
                'full_url': sop.get('related_urls', [''])[0] if sop.get('related_urls') else None,
            })
        else:
            return p.ToolResult(
                success=False,
                error=f"SOP {sop_code} not found in knowledge base"
            )

    except (ImportError, AttributeError) as e:
        logger.error(f"Error fetching SOP: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Knowledge base unavailable")


# Tool 6: Explain Pillar Requirements
@p.tool
async def explain_pillar(
    context: p.ToolContext,
    pillar_id: int
) -> p.ToolResult:
    """
    Explain requirements and scoring criteria for a pillar.

    Args:
        context: Parlant tool context
        pillar_id: Pillar number (1-7)

    Returns:
        ToolResult with pillar explanation
    """
    explanations = {
        1: {
            'name': 'Right Guard at Right Post',
            'requirement': 'Ensure guards are scheduled correctly without conflicts or coverage gaps',
            'checks': ['Schedule health score ≥90%', 'No hotspots (>70% load)', 'Optimal distribution'],
            'green_criteria': 'Schedule health ≥90%',
            'amber_criteria': 'Schedule health 70-89%',
            'red_criteria': 'Schedule health <70%',
            'sla': 'Continuous coverage with <10% load variance',
        },
        2: {
            'name': 'Supervise Relentlessly',
            'requirement': 'Guards complete mandatory tours and scan all checkpoints',
            'checks': ['Tour completion within grace period', 'Checkpoint coverage ≥80%', 'No overdue tours'],
            'green_criteria': '0 violations',
            'amber_criteria': '1-2 violations, none CRITICAL',
            'red_criteria': '3+ violations OR any CRITICAL',
            'sla': 'All mandatory tours complete within 30 min grace period, ≥80% checkpoint coverage',
        },
        3: {
            'name': '24/7 Control Desk',
            'requirement': 'All alerts acknowledged and escalated within SLA',
            'checks': ['CRITICAL alerts ack ≤15 min', 'HIGH alerts ack ≤30 min', 'No stale alerts'],
            'green_criteria': '0 SLA breaches',
            'amber_criteria': '1-2 breaches, no CRITICAL',
            'red_criteria': 'Any CRITICAL alert not ack\'d in 15 min',
            'sla': 'CRITICAL ≤15min, HIGH ≤30min, MEDIUM ≤60min',
        },
        4: {
            'name': 'Legal & Professional',
            'requirement': 'Compliance reports (PF/ESIC/UAN, payroll) generated on time',
            'checks': ['Attendance summary generated daily', 'Compliance reports on schedule'],
            'green_criteria': 'All reports generated on time',
            'amber_criteria': '1 report delayed',
            'red_criteria': 'Multiple reports missing OR never generated',
            'sla': 'Daily attendance reports by 6 AM, monthly compliance by 5th of month',
        },
        5: {
            'name': 'Support the Field',
            'requirement': 'Guards receive uniforms, equipment, and support promptly',
            'checks': ['Tickets resolved <72 hours', 'No >5 day old tickets'],
            'green_criteria': '0 overdue tickets',
            'amber_criteria': '1-3 tickets overdue',
            'red_criteria': '>10 tickets overdue',
            'sla': 'Field support requests resolved within 72 hours',
        },
        6: {
            'name': 'Record Everything',
            'requirement': 'Daily, weekly, monthly reports generated and delivered',
            'checks': ['Daily reports generated', 'Weekly summaries delivered', 'Monthly analytics completed'],
            'green_criteria': 'All reports current',
            'amber_criteria': '1-2 reports delayed',
            'red_criteria': '>5 reports missing',
            'sla': 'Daily reports by 6 AM, weekly by Monday 10 AM, monthly by 5th',
        },
        7: {
            'name': 'Respond to Emergencies',
            'requirement': 'Crisis events trigger immediate escalation and response',
            'checks': ['Crisis tickets assigned ≤5 min', 'Escalation ≤2 min if unassigned'],
            'green_criteria': 'Perfect emergency response',
            'red_criteria': 'ANY delay (no AMBER - life safety)',
            'sla': 'Crisis assignment ≤5min, escalation ≤2min, zero tolerance',
        },
    }

    if pillar_id < 1 or pillar_id > 7:
        return p.ToolResult(success=False, error="Pillar ID must be 1-7")

    return p.ToolResult(explanations[pillar_id])


# Tool 7: Get Critical Violations Summary
@p.tool
async def get_critical_violations(
    context: p.ToolContext
) -> p.ToolResult:
    """
    Get all CRITICAL violations across all pillars.

    Returns:
        ToolResult with list of CRITICAL violations
    """
    try:
        scorecard_result = await get_scorecard(context)
        if not scorecard_result.success:
            return scorecard_result

        scorecard_data = scorecard_result.data
        critical_violations = []

        for pillar_key, violations in scorecard_data['violations_detail'].items():
            for violation in violations:
                if violation.get('severity') == 'CRITICAL':
                    violation['pillar'] = pillar_key
                    critical_violations.append(violation)

        return p.ToolResult({
            'critical_count': len(critical_violations),
            'violations': critical_violations,
            'requires_immediate_action': len(critical_violations) > 0,
        })

    except (KeyError, AttributeError) as e:
        logger.error(f"Error getting critical violations: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Could not retrieve critical violations")


# Tool 8: Get Pillar Status (Quick Check)
@p.tool
async def get_pillar_status(
    context: p.ToolContext,
    pillar_id: int
) -> p.ToolResult:
    """
    Quick status check for a single pillar.

    Args:
        pillar_id: Pillar number (1-7)

    Returns:
        ToolResult with status (GREEN/AMBER/RED) and score
    """
    try:
        scorecard_result = await get_scorecard(context)
        if not scorecard_result.success:
            return scorecard_result

        scorecard_data = scorecard_result.data
        score = scorecard_data['pillar_scores'][str(pillar_id)]

        # Determine status based on score
        if score >= 90:
            status = 'GREEN'
        elif score >= 70:
            status = 'AMBER'
        else:
            status = 'RED'

        pillar_names = {
            1: "Right Guard at Right Post",
            2: "Supervise Relentlessly",
            3: "24/7 Control Desk",
            4: "Legal & Professional",
            5: "Support the Field",
            6: "Record Everything",
            7: "Respond to Emergencies",
        }

        return p.ToolResult({
            'pillar_id': pillar_id,
            'pillar_name': pillar_names[pillar_id],
            'status': status,
            'score': score,
            'violation_count': len(scorecard_data['violations_detail'].get(f'pillar_{pillar_id}', [])),
        })

    except (KeyError, ValueError) as e:
        logger.error(f"Error getting pillar status: {e}", exc_info=True)
        return p.ToolResult(success=False, error="Invalid pillar ID")


# Export all tools
ALL_TOOLS = [
    get_scorecard,
    get_pillar_violations,
    escalate_violation,
    create_field_support_ticket,
    fetch_sop,
    explain_pillar,
    get_critical_violations,
    get_pillar_status,
]
