"""
Emergency Escalation Journey for Parlant.

CRITICAL priority journey for Pillar 7 violations (life safety).
Auto-escalation with minimal user interaction required.

Follows .claude/rules.md Rule #8 (focused, safety-critical).
"""

import logging

logger = logging.getLogger('helpbot.parlant.journeys')


async def create_emergency_escalation_journey(agent):
    """
    Create CRITICAL emergency escalation journey.

    Journey Flow (FAST - Life Safety):
    1. Detect CRITICAL emergency violation
    2. Auto-create NOC alert (NO user confirmation)
    3. Auto-escalate to on-call manager
    4. Confirm escalation actions taken
    5. Initiate incident documentation
    6. Brief incident commander
    7. Continuous monitoring until resolved

    Args:
        agent: Parlant agent instance

    Returns:
        Journey instance
    """
    try:
        import parlant.sdk as p

        journey = p.Journey(
            name="emergency_escalation",
            description="CRITICAL: Automated emergency response workflow for life safety violations",
            priority="CRITICAL",  # Highest priority journey
            steps=[
                {
                    'name': 'detect_emergency',
                    'action': """
                    AUTOMATIC DETECTION (triggered by Pillar 7 violation):
                    - Call get_pillar_violations(pillar_id=7)
                    - Identify emergency type:
                      * EMERGENCY_ESCALATION_DELAYED (crisis ticket >2 min)
                      * EMERGENCY_TICKET_UNASSIGNED (crisis ticket >5 min unassigned)
                      * PANIC_BUTTON_DELAYED (if panic system integrated)

                    NO USER PROMPT - Auto-proceed to alert creation
                    """,
                    'tools': ['get_pillar_violations'],
                },
                {
                    'name': 'auto_create_alert',
                    'action': """
                    AUTOMATIC ALERT CREATION (NO confirmation needed):
                    - Call escalate_violation(pillar_id=7, severity='CRITICAL')
                    - State to user: "🚨 CRITICAL ALERT CREATED AUTOMATICALLY"
                    - Show: Alert ID, escalation target, timestamp

                    Log for audit: User ID, timestamp, emergency type, actions taken

                    This step is AUTOMATIC per Pillar 7 protocol
                    """,
                    'tools': ['escalate_violation'],
                    'auto_execute': True,  # No user confirmation
                },
                {
                    'name': 'notify_management',
                    'action': """
                    IMMEDIATE NOTIFICATIONS:
                    - On-call manager: SMS + voice call
                    - Site supervisor: Immediate notification
                    - Senior management: CRITICAL alert email

                    State to user:
                    "✅ Emergency escalation in progress:
                     - Alert #[ID] created at [timestamp]
                     - On-call manager [Name] notified via SMS + call
                     - Site supervisor [Name] notified
                     - Incident #[ID] opened for investigation"

                    Show: Expected response time (<2 minutes for on-call)
                    """,
                },
                {
                    'name': 'brief_situation',
                    'action': """
                    SITUATION BRIEFING:
                    - Crisis Type: [Emergency ticket delay / unassigned crisis / etc.]
                    - Time Delay: [X] minutes over [Y] minute SLA
                    - Affected: [Guard name / Site / etc.]
                    - Current Status: [Unassigned / Delayed escalation / etc.]
                    - Potential Risk: [Guard in danger / Crisis unhandled / etc.]

                    ACTIONS TAKEN (auto):
                    - Alert #[ID] created and escalated
                    - Management notified
                    - Incident investigation initiated

                    YOUR IMMEDIATE ACTIONS:
                    1. Monitor for on-call response (expect call within 2 min)
                    2. Stand by for incident commander instructions
                    3. Document timeline (I'm recording this conversation)
                    """,
                },
                {
                    'name': 'initiate_incident_doc',
                    'action': """
                    AUTOMATIC INCIDENT DOCUMENTATION:
                    - Incident ID: [Generated]
                    - Timestamp: [CRITICAL violation detected time]
                    - Type: Pillar 7 - Emergency Response Delay
                    - Severity: CRITICAL
                    - Description: [Auto-filled from violation data]
                    - Actions Taken: [Alert created, management notified]

                    State to user:
                    "📋 Incident report initiated - Incident #[ID]
                     You'll need to complete this within 24 hours per protocol."

                    Offer: "I can help you draft the incident report now, or we can do it after resolution?"
                    """,
                },
                {
                    'name': 'continuous_monitoring',
                    'action': """
                    MONITORING STATUS:
                    - "I'll continue monitoring this incident until marked resolved"
                    - "Escalation timer: [X] minutes since alert creation"
                    - "Expected on-call response: Within [Y] minutes"

                    Auto-check every 60 seconds:
                    - Has on-call manager acknowledged? (check NOCAlertEvent)
                    - Has incident been assigned? (check incident status)
                    - Has resolution begun? (check ticket updates)

                    If NO response within 5 minutes of escalation:
                    - ESCALATE AGAIN to backup on-call
                    - Notify senior management
                    - State: "🚨 ESCALATION #2: No response from primary on-call"
                    """,
                    'monitoring': True,  # Continuous monitoring mode
                    'check_interval_seconds': 60,
                },
                {
                    'name': 'confirm_resolution_or_escalate_further',
                    'prompt': """
                    Current incident status: [Status from monitoring]

                    Options:
                    1. Incident acknowledged and being handled → Mark journey complete
                    2. No response from on-call → Escalate to backup/senior management
                    3. Incident resolved → Close incident, complete documentation
                    4. Incident ongoing → Continue monitoring, brief incident commander

                    What's the current situation?
                    """,
                    'validation': 'User must provide status update',
                },
            ]
        )

        await agent.register_journey(journey)
        logger.info("Emergency escalation journey registered successfully")
        return journey

    except (ImportError, AttributeError) as e:
        logger.error(f"Error creating emergency escalation journey: {e}", exc_info=True)
        return None


async def create_all_journeys(agent):
    """
    Create and register all conversational journeys.

    Args:
        agent: Parlant agent instance

    Returns:
        List of created journeys
    """
    from apps.helpbot.parlant.journeys.violation_resolution import create_violation_resolution_journey

    journeys = []

    # Journey 1: Violation Resolution
    j1 = await create_violation_resolution_journey(agent)
    if j1:
        journeys.append(j1)

    # Journey 2: Scorecard Review
    j2 = await create_scorecard_review_journey(agent)
    if j2:
        journeys.append(j2)

    # Journey 3: Emergency Escalation
    j3 = await create_emergency_escalation_journey(agent)
    if j3:
        journeys.append(j3)

    logger.info(f"Created and registered {len(journeys)} conversational journeys")
    return journeys
