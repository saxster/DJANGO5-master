"""
Finding Categorizer Service.

Automatically categorizes findings into SAFETY/SECURITY/OPERATIONAL/DEVICE_HEALTH/COMPLIANCE.
Determines severity based on finding type and context.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from typing import Tuple

logger = logging.getLogger('noc.finding_categorizer')


class FindingCategorizer:
    """
    Categorizes findings based on type and context.

    Categories:
    - SAFETY: Lone worker, panic, missing patrols
    - SECURITY: Geofence, tours, access, suspicious patterns
    - OPERATIONAL: SLA, tasks, productivity, scheduling
    - DEVICE_HEALTH: Offline, GPS drift, battery, connectivity
    - COMPLIANCE: Reports, attendance, legal requirements
    """

    CATEGORY_RULES = {
        # Safety-related patterns
        'SAFETY': [
            'PANIC', 'DURESS', 'LONE_WORKER', 'MISSING_PATROL', 'NO_RESPONSE',
            'EMERGENCY', 'DISTRESS', 'GUARD_DOWN'
        ],

        # Security-related patterns
        'SECURITY': [
            'TOUR', 'CHECKPOINT', 'GEOFENCE', 'ACCESS', 'BREACH', 'INTRUSION',
            'SUSPICIOUS', 'UNAUTHORIZED', 'PHANTOM', 'ABANDONMENT'
        ],

        # Operational patterns
        'OPERATIONAL': [
            'SLA', 'TASK', 'OVERDUE', 'DELAYED', 'BACKLOG', 'STORM',
            'PRODUCTIVITY', 'SCHEDULE', 'COVERAGE', 'STAFFING', 'SILENT_SITE'
        ],

        # Device health patterns
        'DEVICE_HEALTH': [
            'DEVICE', 'GPS', 'PHONE', 'BATTERY', 'OFFLINE', 'CONNECTIVITY',
            'SIGNAL', 'HARDWARE', 'LOCATION_UPDATES', 'PHONE_EVENTS'
        ],

        # Compliance patterns
        'COMPLIANCE': [
            'REPORT', 'ATTENDANCE', 'LEGAL', 'REGULATION', 'AUDIT',
            'DOCUMENTATION', 'PAYROLL', 'PF', 'ESIC'
        ],
    }

    SEVERITY_RULES = {
        'CRITICAL': [
            'PANIC', 'DURESS', 'EMERGENCY', 'SILENT_SITE', 'STORM',
            'GUARD_DOWN', 'NO_RESPONSE', 'COMPLIANCE_REPORT_NEVER_GENERATED'
        ],
        'HIGH': [
            'TOUR_OVERDUE', 'ABANDONMENT', 'GEOFENCE_BREACH', 'SLA_BREACH',
            'DEVICE_FAILURE', 'MISSING_PATROL', 'CRITICAL_SIGNAL_LOW'
        ],
        'MEDIUM': [
            'DELAYED', 'BACKLOG', 'ANOMALY', 'PHANTOM', 'LOW_COVERAGE',
            'DAILY_REPORT_MISSING'
        ],
        'LOW': [
            'MINOR', 'OPTIMIZATION', 'RECOMMENDATION', 'INFORMATIONAL'
        ],
    }

    @classmethod
    def categorize_finding(cls, finding_type: str, context: dict = None) -> Tuple[str, str]:
        """
        Categorize a finding and determine severity.

        Args:
            finding_type: String finding type (e.g., 'TOUR_OVERDUE')
            context: Optional context dict with additional info

        Returns:
            tuple: (category, severity)
        """
        try:
            category = cls._determine_category(finding_type)
            severity = cls._determine_severity(finding_type, context or {})

            logger.debug(f"Categorized {finding_type}: {category}/{severity}")
            return category, severity

        except (ValueError, AttributeError) as e:
            logger.error(f"Categorization error for {finding_type}: {e}", exc_info=True)
            return 'OPERATIONAL', 'MEDIUM'  # Safe defaults

    @classmethod
    def _determine_category(cls, finding_type: str) -> str:
        """
        Determine category based on finding type keywords.

        Args:
            finding_type: String finding type

        Returns:
            str: Category (SAFETY/SECURITY/OPERATIONAL/DEVICE_HEALTH/COMPLIANCE)
        """
        finding_upper = finding_type.upper()

        # Check each category's keywords
        for category, keywords in cls.CATEGORY_RULES.items():
            for keyword in keywords:
                if keyword in finding_upper:
                    return category

        # Default to OPERATIONAL
        return 'OPERATIONAL'

    @classmethod
    def _determine_severity(cls, finding_type: str, context: dict) -> str:
        """
        Determine severity based on finding type and context.

        Args:
            finding_type: String finding type
            context: Context dict with additional info

        Returns:
            str: Severity (CRITICAL/HIGH/MEDIUM/LOW)
        """
        finding_upper = finding_type.upper()

        # Check for critical keywords
        for keyword in cls.SEVERITY_RULES['CRITICAL']:
            if keyword in finding_upper:
                return 'CRITICAL'

        # Check for high severity keywords
        for keyword in cls.SEVERITY_RULES['HIGH']:
            if keyword in finding_upper:
                return 'HIGH'

        # Check for medium severity keywords
        for keyword in cls.SEVERITY_RULES['MEDIUM']:
            if keyword in finding_upper:
                return 'MEDIUM'

        # Context-based severity adjustments
        severity = cls._adjust_severity_by_context(finding_type, context)
        if severity:
            return severity

        # Default to MEDIUM
        return 'MEDIUM'

    @classmethod
    def _adjust_severity_by_context(cls, finding_type: str, context: dict) -> str:
        """
        Adjust severity based on contextual factors.

        Args:
            finding_type: String finding type
            context: Context dict

        Returns:
            str: Adjusted severity or None
        """
        try:
            # Anomaly findings - severity based on z-score
            if 'ANOMALY' in finding_type:
                z_score = abs(context.get('z_score', 0))
                if z_score >= 3.0:
                    return 'CRITICAL'
                elif z_score >= 2.5:
                    return 'HIGH'
                elif z_score >= 2.0:
                    return 'MEDIUM'
                else:
                    return 'LOW'

            # Tour overdue - severity based on delay
            if 'TOUR_OVERDUE' in finding_type:
                overdue_minutes = context.get('overdue_minutes', 0)
                if overdue_minutes >= 120:  # 2+ hours
                    return 'CRITICAL'
                elif overdue_minutes >= 60:  # 1+ hour
                    return 'HIGH'
                elif overdue_minutes >= 30:  # 30+ minutes
                    return 'MEDIUM'

            # Task overdue - severity based on priority and delay
            if 'TASK_OVERDUE' in finding_type or 'SLA_BREACH' in finding_type:
                priority = context.get('priority', 'MEDIUM')
                overdue_minutes = context.get('overdue_minutes', 0)

                if priority == 'CRITICAL' and overdue_minutes > 30:
                    return 'CRITICAL'
                elif priority == 'HIGH' and overdue_minutes > 60:
                    return 'HIGH'

            # Silent site - always critical if confirmed
            if 'SILENT_SITE' in finding_type:
                window_minutes = context.get('window_minutes', 0)
                if window_minutes >= 120:  # 2+ hours of silence
                    return 'CRITICAL'

            return None

        except (ValueError, KeyError) as e:
            logger.error(f"Context-based severity adjustment error: {e}", exc_info=True)
            return None

    @classmethod
    def get_category_description(cls, category: str) -> str:
        """Get human-readable description of category."""
        descriptions = {
            'SAFETY': 'Guard safety and emergency response',
            'SECURITY': 'Site security and access control',
            'OPERATIONAL': 'Operational efficiency and SLA compliance',
            'DEVICE_HEALTH': 'Device and connectivity issues',
            'COMPLIANCE': 'Legal and regulatory compliance',
        }
        return descriptions.get(category, 'General operational issue')

    @classmethod
    def get_severity_description(cls, severity: str) -> str:
        """Get human-readable description of severity."""
        descriptions = {
            'CRITICAL': 'Immediate action required - life safety or critical security risk',
            'HIGH': 'Urgent action within 2 hours - significant operational impact',
            'MEDIUM': 'Action within 24 hours - moderate operational impact',
            'LOW': 'Action within 1 week - minor issue or optimization opportunity',
        }
        return descriptions.get(severity, 'Requires attention')
