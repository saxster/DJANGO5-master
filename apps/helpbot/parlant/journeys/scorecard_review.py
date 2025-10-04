"""
Scorecard Review Journey for Parlant.

Guided daily scorecard review workflow with priority-based triage.
Walks operators through RED → AMBER → GREEN pillars systematically.

Follows .claude/rules.md Rule #8 (clear, focused functions).
"""

import logging

logger = logging.getLogger('helpbot.parlant.journeys')


async def create_scorecard_review_journey(agent):
    """
    Create guided daily scorecard review journey.

    Journey Flow:
    1. Get today's scorecard
    2. Show overall health summary
    3. If RED pillars exist: Triage RED items first
    4. If AMBER pillars exist: Review and plan fixes
    5. Confirm GREEN pillars (positive reinforcement)
    6. Generate action plan summary
    7. Offer to start violation resolution for top priority

    Args:
        agent: Parlant agent instance

    Returns:
        Journey instance
    """
    try:
        import parlant.sdk as p

        journey = p.Journey(
            name="scorecard_review",
            description="Daily guided scorecard review with priority-based triage",
            steps=[
                {
                    'name': 'fetch_scorecard',
                    'action': """
                    Call get_scorecard() to retrieve today's data
                    Present executive summary:
                    - "Good morning! Here's your scorecard for [date]"
                    - Overall Health: [GREEN/AMBER/RED] ([score]/100)
                    - Critical Violations: [count]
                    - Total Violations: [count]

                    Quick status per pillar:
                    - 🟢 Pillar X: GREEN (score)
                    - 🟡 Pillar Y: AMBER (score)
                    - 🔴 Pillar Z: RED (score)
                    """,
                    'tools': ['get_scorecard'],
                },
                {
                    'name': 'triage_red_pillars',
                    'action': """
                    If RED pillars exist:
                    - State: "You have [N] RED pillars requiring immediate attention"
                    - List each RED pillar with score and violation count
                    - Explain: "RED status means critical operational risk"

                    For each RED pillar:
                    - Call get_pillar_violations(pillar_id)
                    - Show top 3 violations
                    - Explain severity and impact

                    Ask: "Shall we start resolving these RED items now?
                          I can guide you through each one."

                    If user says yes: Transition to violation_resolution journey
                    If user says no: Continue to AMBER review
                    """,
                    'tools': ['get_pillar_violations', 'get_critical_violations'],
                },
                {
                    'name': 'review_amber_pillars',
                    'action': """
                    If AMBER pillars exist:
                    - State: "[N] AMBER pillars need attention within 24 hours"
                    - List each with brief violation summary
                    - Explain: "AMBER = minor issues, fixable before they escalate"

                    For each AMBER pillar:
                    - Show violation count and types
                    - Provide quick recommendation
                    - Estimate time to fix

                    Ask: "Would you like to create action tickets for AMBER items?"
                    If yes: Offer to create tickets via create_field_support_ticket
                    """,
                    'tools': ['get_pillar_violations', 'create_field_support_ticket'],
                },
                {
                    'name': 'confirm_green_pillars',
                    'action': """
                    If GREEN pillars exist:
                    - POSITIVE REINFORCEMENT: "Excellent performance on [N] pillars!"
                    - List each GREEN pillar
                    - Highlight: "These areas are exceeding operational targets"

                    No action needed for GREEN, but acknowledge success
                    """,
                },
                {
                    'name': 'generate_action_plan',
                    'action': """
                    Summarize action plan:
                    - "Here's your priority action plan for today:"

                    HIGH PRIORITY (RED items):
                    1. [Pillar X violation] - Immediate action required
                    2. [Pillar Y violation] - Escalate to management

                    MEDIUM PRIORITY (AMBER items):
                    3. [Pillar Z violation] - Address within 24 hours
                    4. [Pillar W violation] - Create follow-up ticket

                    LOW PRIORITY (GREEN maintenance):
                    5. Continue monitoring, maintain current standards

                    Estimated time: [X] hours for all HIGH priority items
                    """,
                },
                {
                    'name': 'offer_guided_resolution',
                    'prompt': """
                    I can guide you through resolving these items step-by-step.

                    Options:
                    1. Start resolving RED items now (guided workflow)
                    2. Create tickets for AMBER items (I'll do it)
                    3. View detailed violation report
                    4. Generate client-ready summary
                    5. End review (I'll send action plan via email)

                    What would you like to do?
                    """,
                    'validation': 'User must select an option',
                },
                {
                    'name': 'execute_next_step',
                    'action': """
                    Based on user selection:
                    - Option 1: Start violation_resolution journey for first RED item
                    - Option 2: Loop through AMBER items, create tickets
                    - Option 3: Generate detailed violation report (all pillars)
                    - Option 4: Generate client summary (executive format)
                    - Option 5: Send email summary and end conversation

                    Always confirm what was done before ending
                    """,
                    'tools': ['create_field_support_ticket'],
                },
            ]
        )

        await agent.register_journey(journey)
        logger.info("Scorecard review journey registered successfully")
        return journey

    except (ImportError, AttributeError) as e:
        logger.error(f"Error creating scorecard review journey: {e}", exc_info=True)
        return None
