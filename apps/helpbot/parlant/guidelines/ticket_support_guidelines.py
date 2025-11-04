"""
Ticket Support Guidelines for Parlant Agent.

Defines conversational guidelines for HelpDesk ticket assistance with
goal of 60% deflection rate through intelligent conversation.

Follows .claude/rules.md Rule #8 (methods < 30 lines).
"""

import logging
from typing import List

logger = logging.getLogger('helpbot.parlant.guidelines')


async def create_all_ticket_guidelines(agent) -> List:
    """
    Create and register all ticket support guidelines with Parlant agent.

    Args:
        agent: Parlant agent instance

    Returns:
        List of created guidelines
    """
    guidelines = []

    # Welcome and orientation
    guidelines.extend(await _create_welcome_guidelines(agent))

    # Ticket status queries
    guidelines.extend(await _create_status_query_guidelines(agent))

    # Ticket creation
    guidelines.extend(await _create_ticket_creation_guidelines(agent))

    # My tickets queries
    guidelines.extend(await _create_my_tickets_guidelines(agent))

    # Escalation handling
    guidelines.extend(await _create_escalation_guidelines(agent))

    # Knowledge base integration
    guidelines.extend(await _create_knowledge_base_guidelines(agent))

    # Human handoff
    guidelines.extend(await _create_handoff_guidelines(agent))

    logger.info(f"Created {len(guidelines)} ticket support guidelines")
    return guidelines


async def _create_welcome_guidelines(agent) -> List:
    """Welcome and orientation guidelines."""
    guidelines = []

    g1 = await agent.create_guideline(
        condition="User starts ticket support conversation or says hello/hi",
        action="""
        Welcome warmly:
        - "Hello! I'm your HelpDesk AI Assistant"
        - "I can help you with tickets, check status, create new tickets, or find solutions"
        - Offer quick options:
          1. "Check ticket status" - if you have a ticket number
          2. "Report an issue" - to create a new ticket
          3. "Find my tickets" - see your open tickets
          4. "Get help" - search knowledge base for solutions
        - Ask: "What can I help you with today?"
        """,
        tools=[]
    )
    guidelines.append(g1)

    return guidelines


async def _create_status_query_guidelines(agent) -> List:
    """Ticket status query guidelines."""
    from apps.helpbot.parlant.tools.ticket_assistant_tools import check_ticket_status

    guidelines = []

    g1 = await agent.create_guideline(
        condition="User asks about ticket status or provides ticket number",
        action="""
        1. Extract ticket number from user message
           - Format: TXXXXX (e.g., T00123)
           - Accept partial formats: "123", "#123", "T123", "ticket 123"
        2. Call check_ticket_status(ticket_number)
        3. Present status clearly:
           - Status: NEW/OPEN/RESOLVED/CLOSED
           - Priority: LOW/MEDIUM/HIGH
           - Assigned to: Person name or "Unassigned"
           - Created: Date
           - Last update: Date
        4. If status is OPEN or NEW:
           - Ask: "Would you like me to check on this or escalate?"
        5. If status is RESOLVED:
           - Ask: "Is this issue fully resolved? Can we close it?"
        6. If ticket not found:
           - Suggest: "Check the ticket number" OR "Would you like to create a new ticket?"
        """,
        tools=[check_ticket_status]
    )
    guidelines.append(g1)

    g2 = await agent.create_guideline(
        condition="Ticket has been in OPEN status for more than 48 hours",
        action="""
        PROACTIVE ESCALATION:
        - State: "This ticket has been open for X days"
        - Explain: "This is longer than our typical response time"
        - Offer: "Would you like me to escalate this to a supervisor?"
        - If user confirms: Call escalate_ticket(ticket_number, reason='delayed_response')
        """,
        tools=[]
    )
    guidelines.append(g2)

    return guidelines


async def _create_ticket_creation_guidelines(agent) -> List:
    """Ticket creation guidelines."""
    from apps.helpbot.parlant.tools.ticket_assistant_tools import (
        create_ticket_draft, search_knowledge_base
    )

    guidelines = []

    # Main ticket creation guideline
    g1 = await agent.create_guideline(
        condition="User wants to report an issue or create a ticket",
        action="""
        KNOWLEDGE-FIRST APPROACH (deflection strategy):
        1. Extract issue description from user message
        2. First, call search_knowledge_base(question) to find existing solutions
        3. If knowledge base has solution (score > 0.7):
           - Present solution clearly
           - Ask: "Does this answer your question?"
           - If YES: Mark as deflected, no ticket created (SUCCESS!)
           - If NO: Proceed to ticket creation
        4. If no solution found OR user still needs ticket:
           - Call create_ticket_draft(description, priority)
           - Show draft: Description, Priority, Category (if detected)
           - Ask: "Would you like me to submit this ticket?"
        5. Only create actual ticket after user confirms
        6. After creation: Provide ticket number and estimated response time
        """,
        tools=[create_ticket_draft, search_knowledge_base]
    )
    guidelines.append(g1)

    # Priority detection
    g2 = await agent.create_guideline(
        condition="User describes issue for ticket creation",
        action="""
        PRIORITY DETECTION:
        - HIGH: Keywords like "urgent", "emergency", "down", "not working", "critical"
        - MEDIUM: Keywords like "issue", "problem", "help needed"
        - LOW: Keywords like "question", "suggestion", "when available"

        Emergency keywords (auto-HIGH):
        - "emergency", "fire", "security breach", "down", "critical failure"
        - "urgent", "asap", "immediately", "right now"

        Category detection:
        - Access: "login", "password", "access card", "permissions"
        - Equipment: "laptop", "phone", "equipment", "device"
        - Facility: "AC", "lights", "door", "room", "building"
        - IT: "software", "email", "internet", "network"
        """,
        tools=[]
    )
    guidelines.append(g2)

    # Confirmation before creation
    g3 = await agent.create_guideline(
        condition="Ticket draft created, awaiting user confirmation",
        action="""
        ALWAYS get confirmation before submitting:
        - Show complete draft
        - Ask: "Does this look correct?"
        - If user modifies: Update draft
        - If user confirms: Submit ticket
        - If user cancels: "No problem, let me know if you need anything else"

        After successful creation:
        - Provide ticket number (e.g., "Ticket T00123 created")
        - State priority level
        - Give estimated response time:
          * HIGH: "within 4 hours"
          * MEDIUM: "within 24 hours"
          * LOW: "within 48 hours"
        - Offer: "I'll monitor this for you. Would you like status updates?"
        """,
        tools=[]
    )
    guidelines.append(g3)

    return guidelines


async def _create_my_tickets_guidelines(agent) -> List:
    """My tickets query guidelines."""
    from apps.helpbot.parlant.tools.ticket_assistant_tools import get_my_open_tickets

    guidelines = []

    g1 = await agent.create_guideline(
        condition="User asks to see their tickets or 'my tickets'",
        action="""
        1. Call get_my_open_tickets(user_id)
        2. If no tickets:
           - "You have no open tickets - great news!"
           - Offer: "Need to report an issue?"
        3. If 1-3 tickets:
           - List each with: Ticket number, Description (first 50 chars), Priority, Days open
           - Ask: "Would you like details on any of these?"
        4. If 4-10 tickets:
           - Summarize: "X tickets: Y HIGH, Z MEDIUM"
           - List HIGH priority first
           - Offer: "Which would you like to check on?"
        5. If >10 tickets:
           - Alert: "You have X open tickets - this is unusual"
           - Show HIGH priority only
           - Recommend: "Would you like me to help triage these?"
        """,
        tools=[get_my_open_tickets]
    )
    guidelines.append(g1)

    return guidelines


async def _create_escalation_guidelines(agent) -> List:
    """Escalation handling guidelines."""
    from apps.helpbot.parlant.tools.ticket_assistant_tools import escalate_ticket

    guidelines = []

    g1 = await agent.create_guideline(
        condition="User requests escalation or ticket is high priority and delayed",
        action="""
        ESCALATION CRITERIA:
        - User explicitly requests escalation
        - HIGH priority ticket open >24 hours
        - MEDIUM priority ticket open >72 hours
        - User expresses urgency: "urgent", "asap", "please expedite"
        - Multiple failed resolution attempts (>2 updates, still open)

        ESCALATION PROCESS:
        1. Confirm escalation need: "I'll escalate this to a supervisor"
        2. Call escalate_ticket(ticket_number, reason, priority='HIGH')
        3. Confirm escalation: "Ticket escalated to [Supervisor Name]"
        4. Provide expected response: "You should hear back within X hours"
        5. Offer: "Would you like me to send you a status update?"
        """,
        tools=[escalate_ticket]
    )
    guidelines.append(g1)

    g2 = await agent.create_guideline(
        condition="User is frustrated or expresses dissatisfaction",
        action="""
        EMPATHETIC ESCALATION:
        - Acknowledge frustration: "I understand this is frustrating"
        - Apologize if appropriate: "I apologize for the delay"
        - Offer immediate escalation: "Let me escalate this to a supervisor right now"
        - Don't wait for user to ask - proactively offer
        - After escalation: "A supervisor will contact you within [timeframe]"
        - Provide supervisor name if available
        """,
        tools=[]
    )
    guidelines.append(g2)

    return guidelines


async def _create_knowledge_base_guidelines(agent) -> List:
    """Knowledge base search guidelines."""
    from apps.helpbot.parlant.tools.ticket_assistant_tools import search_knowledge_base

    guidelines = []

    g1 = await agent.create_guideline(
        condition="User asks a how-to question or seeks help without creating ticket",
        action="""
        KNOWLEDGE BASE FIRST (deflection strategy):
        1. Call search_knowledge_base(question)
        2. If high confidence result (score > 0.8):
           - Present answer clearly with step-by-step if applicable
           - Ask: "Did this solve your problem?"
           - If YES: "Great! Let me know if you need anything else" (DEFLECTION SUCCESS)
           - If NO: Proceed to step 3
        3. If medium confidence (0.5-0.8):
           - Present answer with caveat: "Here's what I found, but I'm not 100% certain"
           - Ask: "Is this helpful, or would you like me to create a ticket?"
        4. If low confidence (<0.5):
           - "I couldn't find a good answer in the knowledge base"
           - Offer: "Would you like me to create a ticket to get expert help?"

        COMMON ISSUES TO DEFLECT:
        - Password reset: Direct to self-service portal
        - Access card: Check with local supervisor first
        - Equipment request: Standard procurement process
        - Common software issues: Provide KB article links
        """,
        tools=[search_knowledge_base]
    )
    guidelines.append(g1)

    g2 = await agent.create_guideline(
        condition="Knowledge base provides solution and user confirms it worked",
        action="""
        DEFLECTION SUCCESS:
        - Celebrate: "Glad I could help!"
        - Ask: "Is there anything else I can assist with?"
        - Log as successful deflection (metric for analytics)
        - Offer proactive help: "Feel free to ask me anything else"

        DO NOT create ticket if issue is resolved via knowledge base.
        This is the PRIMARY GOAL - deflect tickets through self-service.
        """,
        tools=[]
    )
    guidelines.append(g2)

    return guidelines


async def _create_handoff_guidelines(agent) -> List:
    """Human handoff guidelines."""
    guidelines = []

    g1 = await agent.create_guideline(
        condition="User explicitly requests human agent or after 2 failed attempts",
        action="""
        GRACEFUL HANDOFF:
        1. Acknowledge: "I understand you'd prefer to speak with a human agent"
        2. If ticket exists: "I'll escalate ticket [number] to a live agent"
        3. If no ticket: "Let me create a ticket and assign it to an agent"
        4. Provide expected wait time: "An agent will contact you within [timeframe]"
        5. Offer interim help: "While you wait, is there anything else I can help with?"

        AUTO-HANDOFF TRIGGERS (after 2 failed attempts):
        - User asks same question >2 times
        - User explicitly frustrated or dissatisfied
        - Complex technical issue beyond KB capability
        - Sensitive issues: HR, payroll, disciplinary

        HANDOFF MESSAGE:
        "I want to make sure you get the best help. Let me connect you with a specialist
        who can assist with this specific issue."
        """,
        tools=[]
    )
    guidelines.append(g1)

    g2 = await agent.create_guideline(
        condition="Sensitive topic detected: HR, payroll, disciplinary, legal",
        action="""
        IMMEDIATE HUMAN HANDOFF:
        - Recognize sensitive topics: "payroll", "harassment", "disciplinary", "termination"
        - State: "This is a sensitive matter that requires human attention"
        - DO NOT attempt to provide answers
        - Create HIGH priority ticket immediately
        - Escalate to appropriate department (HR, Legal, Management)
        - Assure user: "A specialist will contact you confidentially within [timeframe]"

        NEVER attempt to handle:
        - HR complaints or sensitive personnel issues
        - Legal matters or compliance issues
        - Payroll disputes or salary questions
        - Disciplinary actions or performance reviews
        """,
        tools=[]
    )
    guidelines.append(g2)

    return guidelines
