"""
Violation Resolution Journey for Parlant.

Multi-step conversational workflow for investigating and resolving
non-negotiables violations.

Follows .claude/rules.md Rule #8 (clear, focused functions).
"""

import logging

logger = logging.getLogger('helpbot.parlant.journeys')


async def create_violation_resolution_journey(agent):
    """
    Create guided journey for resolving violations.

    Journey Flow:
    1. Identify violation (from scorecard or user input)
    2. Explain root cause and impact
    3. Present remediation options (3-5 options)
    4. User selects option
    5. Execute action (create ticket, escalate, assign)
    6. Confirm resolution path
    7. Link to relevant SOP for future prevention

    Args:
        agent: Parlant agent instance

    Returns:
        Journey instance
    """
    try:
        import parlant.sdk as p

        journey = p.Journey(
            name="violation_resolution",
            description="Guided workflow for investigating and resolving non-negotiables violations",
            steps=[
                {
                    'name': 'identify_violation',
                    'prompt': 'Which violation would you like to address? (Provide pillar ID or violation type)',
                    'validation': 'Must specify pillar ID (1-7) or violation type',
                },
                {
                    'name': 'explain_root_cause',
                    'action': """
                    Call get_pillar_violations for specified pillar
                    Explain:
                    - What went wrong (specific violation)
                    - Why it matters (impact on operations, safety, compliance)
                    - How long it's been an issue
                    Use data-driven language with specific numbers
                    """,
                    'tools': ['get_pillar_violations', 'explain_pillar'],
                },
                {
                    'name': 'present_options',
                    'action': """
                    Present 3-5 remediation options based on violation type:

                    For TOUR_OVERDUE:
                    1. Dispatch relief guard (fastest - 10-15 min)
                    2. Contact current guard (verify status)
                    3. Mark as force majeure (requires justification)
                    4. Escalate to supervisor (for investigation)

                    For ALERT_NOT_ACKNOWLEDGED:
                    1. Acknowledge alert now (if operator has authority)
                    2. Assign to on-call operator
                    3. Escalate to management (if SLA breach severe)

                    For COMPLIANCE_REPORT_MISSING:
                    1. Generate report immediately
                    2. Create HIGH priority task for report team
                    3. Escalate to compliance officer

                    Always explain pros/cons of each option
                    """,
                },
                {
                    'name': 'user_selects_option',
                    'prompt': 'Which option would you like to proceed with? (Enter number 1-5)',
                    'validation': 'Must select a valid option number',
                },
                {
                    'name': 'execute_action',
                    'action': """
                    Based on selected option, execute appropriate tool:
                    - Option involves escalation → Call escalate_violation
                    - Option involves ticket → Call create_field_support_ticket
                    - Option involves assignment → Call assign_guard (if tool exists)

                    Confirm execution:
                    "✅ Action completed:
                     - [What was done]
                     - [Ticket/Alert number if created]
                     - [Who was notified]
                     - [Expected resolution time]"
                    """,
                    'tools': ['escalate_violation', 'create_field_support_ticket'],
                },
                {
                    'name': 'link_sop',
                    'action': """
                    Link to relevant SOP for prevention:
                    - Pillar 2 violations → SOP-SEC-007 (Mandatory Tours)
                    - Pillar 3 violations → SOP-NOC-003 (Alert Response)
                    - Pillar 4 violations → SOP-COMP-001 (Compliance Reporting)
                    - Pillar 7 violations → SOP-EMERG-001 (Crisis Response)

                    Call fetch_sop with appropriate code
                    Present: "To prevent this in future, review [SOP Name]: [Summary]"
                    """,
                    'tools': ['fetch_sop'],
                },
                {
                    'name': 'confirm_next_steps',
                    'prompt': 'Would you like to address another violation, view updated scorecard, or end session?',
                },
            ]
        )

        await agent.register_journey(journey)
        logger.info("Violation resolution journey registered successfully")
        return journey

    except (ImportError, AttributeError) as e:
        logger.error(f"Error creating violation resolution journey: {e}", exc_info=True)
        return None
