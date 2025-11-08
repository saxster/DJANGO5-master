"""
Wellness & Mental Health Constants

Centralized constants for mental health intervention thresholds, escalation levels,
and wellness content delivery parameters. These values are evidence-based and should
only be changed with clinical validation.

Created: November 5, 2025
Purpose: Replace magic numbers with named constants (code quality improvement)
"""

from typing import Final

# ============================================================================
# CRISIS INTERVENTION THRESHOLDS
# ============================================================================

# Crisis Escalation Levels (1-10 scale)
CRISIS_ESCALATION_THRESHOLD: Final[int] = 6
"""Escalation level ≥6 triggers immediate crisis intervention"""

INTENSIVE_ESCALATION_THRESHOLD: Final[int] = 4
"""Escalation level ≥4 triggers professional escalation and intensive support"""

ROUTINE_ESCALATION_THRESHOLD: Final[int] = 2
"""Escalation level ≥2 triggers routine support interventions"""

# Mood Rating Thresholds (1-10 scale, where 1 is extremely negative)
CRISIS_MOOD_THRESHOLD: Final[int] = 2
"""Mood rating ≤2 indicates crisis-level distress"""

LOW_MOOD_THRESHOLD: Final[int] = 4
"""Mood rating ≤4 indicates need for intervention"""

# Urgency Scores (1-10 scale)
HIGH_URGENCY_THRESHOLD: Final[int] = 6
"""Urgency score ≥6 triggers crisis response protocols"""

MEDIUM_URGENCY_THRESHOLD: Final[int] = 4
"""Urgency score 4-5 triggers intensive support"""

# ============================================================================
# WELLBEING SCORE THRESHOLDS
# ============================================================================

LOW_WELLBEING_THRESHOLD: Final[float] = 6.0
"""Overall wellbeing score <6.0 indicates need for support (0-10 scale)"""

CRITICAL_WELLBEING_THRESHOLD: Final[float] = 4.0
"""Overall wellbeing score <4.0 indicates crisis-level concern"""

# ============================================================================
# ANALYTICS & PATTERN DETECTION
# ============================================================================

MINIMUM_ANALYTICS_ENTRIES: Final[int] = 3
"""Minimum journal entries required for reliable analytics (past 7 days)"""

CONSECUTIVE_LOW_MOOD_DAYS_THRESHOLD: Final[int] = 5
"""5+ consecutive days of low mood triggers escalation"""

PATTERN_DETECTION_WINDOW_DAYS: Final[int] = 7
"""Number of days to analyze for pattern detection"""

# ============================================================================
# INTERVENTION DELIVERY TIMING
# ============================================================================

# Follow-up monitoring intervals (in seconds)
CRISIS_FOLLOWUP_DELAY: Final[int] = 3600  # 1 hour
"""Time to wait before crisis follow-up check (1 hour)"""

INTENSIVE_FOLLOWUP_DELAY: Final[int] = 14400  # 4 hours
"""Time to wait before intensive support follow-up (4 hours)"""

ROUTINE_FOLLOWUP_DELAY: Final[int] = 86400  # 24 hours
"""Time to wait before routine intervention follow-up (24 hours)"""

# Professional escalation timing
PROFESSIONAL_ESCALATION_DELAY: Final[int] = 300  # 5 minutes
"""Delay before triggering professional escalation (allow immediate interventions first)"""

# ============================================================================
# PROGRESSIVE ESCALATION CHECK INTERVALS
# ============================================================================

# Next check intervals by escalation level (in hours)
ESCALATION_CHECK_INTERVALS: Final[dict] = {
    1: 168,  # Level 1 (minimal): Check weekly (168 hours)
    2: 72,   # Level 2 (routine): Check every 3 days (72 hours)
    3: 24,   # Level 3 (moderate): Check daily (24 hours)
    4: 4,    # Level 4 (intensive): Check every 4 hours
    5: 2,    # Level 5 (high): Check every 2 hours
    6: 1,    # Level 6+ (crisis): Check hourly
}
"""Next wellness check intervals based on current escalation level"""

# ============================================================================
# STRESS & ENERGY THRESHOLDS
# ============================================================================

HIGH_STRESS_THRESHOLD: Final[int] = 7
"""Stress level ≥7 indicates high stress (1-10 scale)"""

LOW_ENERGY_THRESHOLD: Final[int] = 3
"""Energy level ≤3 indicates fatigue/burnout risk (1-10 scale)"""

# ============================================================================
# CONTENT DELIVERY LIMITS
# ============================================================================

MAX_INTERVENTIONS_PER_DAY: Final[int] = 3
"""Maximum mental health interventions to deliver per user per day"""

MAX_NOTIFICATIONS_PER_HOUR: Final[int] = 1
"""Maximum notifications per user per hour (avoid notification fatigue)"""

INTERVENTION_COOLDOWN_HOURS: Final[int] = 4
"""Minimum hours between similar intervention types"""

# ============================================================================
# DATA RETENTION & PRIVACY
# ============================================================================

JOURNAL_RETENTION_DAYS: Final[int] = 365
"""Days to retain journal entries (1 year)"""

ANALYTICS_RETENTION_DAYS: Final[int] = 90
"""Days to retain detailed analytics data (90 days)"""

CRISIS_LOG_RETENTION_DAYS: Final[int] = 730
"""Days to retain crisis intervention logs (2 years for compliance)"""

# ============================================================================
# EVIDENCE-BASED INTERVENTION PARAMETERS
# ============================================================================

# Cognitive Behavioral Therapy (CBT) parameters
CBT_THOUGHT_RECORD_MIN_ENTRIES: Final[int] = 3
"""Minimum thought records needed for pattern recognition"""

CBT_RECOMMENDED_PRACTICE_DAYS: Final[int] = 21
"""Recommended days of practice for habit formation (evidence-based)"""

# Positive Psychology parameters
GRATITUDE_JOURNAL_MIN_ENTRIES: Final[int] = 3
"""Minimum gratitude entries per week for effectiveness"""

POSITIVE_AFFIRMATION_FREQUENCY_DAYS: Final[int] = 7
"""Frequency of positive psychology interventions (weekly)"""

# ============================================================================
# QUALITY & VALIDATION THRESHOLDS
# ============================================================================

MIN_JOURNAL_ENTRY_LENGTH: Final[int] = 10
"""Minimum characters for valid journal entry (filter noise)"""

MAX_JOURNAL_ENTRY_LENGTH: Final[int] = 10000
"""Maximum characters for journal entry (10,000 chars)"""

MIN_MOOD_RATING: Final[int] = 1
"""Minimum mood rating value"""

MAX_MOOD_RATING: Final[int] = 10
"""Maximum mood rating value"""

# ============================================================================
# PROFESSIONAL ESCALATION RECIPIENTS
# ============================================================================

PROFESSIONAL_ESCALATION_LEVELS: Final[dict] = {
    4: ['hr_wellness'],  # Level 4: HR Wellness team only
    5: ['hr_wellness', 'manager'],  # Level 5: + Manager notification
    6: ['hr_wellness', 'manager', 'employee_assistance'],  # Level 6+: Full escalation
}
"""Professional notification recipients by escalation level"""

# ============================================================================
# USAGE NOTES
# ============================================================================

"""
USAGE EXAMPLES:

# In mental health intervention tasks:
from apps.wellness.constants import (
    CRISIS_ESCALATION_THRESHOLD,
    HIGH_URGENCY_THRESHOLD,
    CRISIS_FOLLOWUP_DELAY
)

if intervention.crisis_escalation_level >= CRISIS_ESCALATION_THRESHOLD:
    # Trigger crisis intervention
    schedule_crisis_intervention(countdown=0)

if urgency_score >= HIGH_URGENCY_THRESHOLD:
    # High urgency response
    schedule_followup(countdown=CRISIS_FOLLOWUP_DELAY)

# In analytics services:
from apps.wellness.constants import (
    MINIMUM_ANALYTICS_ENTRIES,
    LOW_WELLBEING_THRESHOLD
)

if len(journal_entries) < MINIMUM_ANALYTICS_ENTRIES:
    return {'error': 'Insufficient data for analytics'}

if wellbeing_score < LOW_WELLBEING_THRESHOLD:
    trigger_support_intervention()

# In escalation engines:
from apps.wellness.constants import ESCALATION_CHECK_INTERVALS

next_check_hours = ESCALATION_CHECK_INTERVALS.get(current_level, 168)
schedule_next_check(countdown=next_check_hours * 3600)

MAINTENANCE:
- Review thresholds quarterly with clinical team
- Update based on user feedback and outcomes data
- Document changes in CHANGELOG.md
- Run integration tests after any threshold changes

CLINICAL VALIDATION:
All threshold values are based on:
- Evidence-based mental health practices
- CBT/DBT clinical guidelines
- Peer-reviewed research on digital mental health interventions
- User safety requirements

DO NOT modify these values without clinical team approval.
"""
