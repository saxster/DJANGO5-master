"""
DST (Daylight Saving Time) Validator Service

Proactive detection and validation of schedules that may be affected by DST transitions.

Features:
- Detect DST transition dates for any timezone
- Validate schedule safety around DST boundaries
- Provide actionable recommendations for DST-safe times
- Cache DST transition data for performance (1 year cache)
- Support for multiple timezones

DST Transition Issues:
1. **Spring Forward** (DST starts, clock jumps ahead):
   - 2:00 AM → 3:00 AM instantly
   - Any schedule at 2:00-3:00 AM will be skipped
   - Example: Daily 2:30 AM backup won't run on DST start day

2. **Fall Back** (DST ends, clock falls back):
   - 2:00 AM → 1:00 AM (happens twice)
   - Any schedule at 1:00-2:00 AM will run TWICE
   - Example: Hourly cleanup at 1:30 AM runs twice on DST end day

Usage:
    from apps.schedhuler.services.dst_validator import DSTValidator

    validator = DSTValidator()

    # Validate schedule for DST safety
    result = validator.validate_schedule_dst_safety(
        cron_expression='0 2 * * *',  # Daily at 2 AM
        timezone_name='US/Eastern'
    )

    if result['has_issues']:
        print(result['recommendations'])

    # Get DST transitions for a year
    transitions = validator.get_dst_transitions(2025, 'US/Eastern')

Compliance:
- Rule #7: Single responsibility (DST validation only)
- Rule #11: Specific exception handling (no generic Exception)
- Rule #12: Database query optimization (cached results)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from functools import lru_cache

from django.core.cache import cache
from django.utils import timezone
import pytz

from apps.core.services.base_service import BaseService
from apps.core.constants.datetime_constants import SECONDS_IN_DAY, SECONDS_IN_HOUR


logger = logging.getLogger(__name__)


class DSTValidator(BaseService):
    """
    Service for validating schedules against DST transitions.

    Provides:
    - DST transition detection for any timezone
    - Schedule risk assessment
    - Alternative time recommendations
    - Performance: Cached results (1 year validity)
    """

    # Cache configuration
    CACHE_PREFIX = 'dst_validator'
    CACHE_TTL = SECONDS_IN_DAY * 365  # 1 year (DST dates don't change retroactively)

    # Risk hours (local time) - typically 1 AM - 3 AM
    DST_RISK_HOURS = [1, 2, 3]

    # Safe alternative hours
    SAFE_HOURS = [4, 5, 6, 22, 23]  # Late night / early morning but not DST hours

    def validate_schedule_dst_safety(
        self,
        cron_expression: str,
        timezone_name: str = 'UTC'
    ) -> Dict[str, Any]:
        """
        Validate if a cron schedule is safe regarding DST transitions.

        Args:
            cron_expression: Cron expression to validate (e.g., '0 2 * * *')
            timezone_name: Timezone name (e.g., 'US/Eastern', 'Europe/London')

        Returns:
            Dictionary containing:
                - has_issues: Boolean indicating if DST issues detected
                - risk_level: 'none', 'low', 'medium', 'high'
                - problematic_times: List of risky execution times
                - recommendations: List of suggested alternatives
                - dst_transition_dates: List of relevant DST dates

        Example:
            {
                'has_issues': True,
                'risk_level': 'high',
                'problematic_times': ['02:00'],
                'recommendations': [
                    'Change schedule to 03:00 or later',
                    'Avoid hours 1-3 AM during DST transitions'
                ],
                'dst_transition_dates': [
                    {'date': '2025-03-09', 'type': 'spring_forward'},
                    {'date': '2025-11-02', 'type': 'fall_back'}
                ]
            }
        """
        try:
            # UTC has no DST
            if timezone_name == 'UTC':
                return {
                    'has_issues': False,
                    'risk_level': 'none',
                    'problematic_times': [],
                    'recommendations': [],
                    'dst_transition_dates': [],
                    'message': 'UTC timezone has no DST transitions'
                }

            # Get timezone
            tz = pytz.timezone(timezone_name)

            # Check if timezone has DST
            if not self._has_dst_transitions(tz):
                return {
                    'has_issues': False,
                    'risk_level': 'none',
                    'problematic_times': [],
                    'recommendations': [],
                    'dst_transition_dates': [],
                    'message': f'{timezone_name} has no DST transitions'
                }

            # Parse cron expression to extract hours
            risky_hours = self._extract_risky_hours_from_cron(cron_expression)

            if not risky_hours:
                return {
                    'has_issues': False,
                    'risk_level': 'low',
                    'problematic_times': [],
                    'recommendations': [],
                    'dst_transition_dates': self._format_dst_transitions(tz),
                    'message': 'Schedule does not run during DST risk hours'
                }

            # Get DST transitions for current and next year
            current_year = datetime.now().year
            transitions = []
            transitions.extend(self.get_dst_transitions(current_year, timezone_name))
            transitions.extend(self.get_dst_transitions(current_year + 1, timezone_name))

            # Assess risk level
            risk_level = self._assess_risk_level(risky_hours)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                risky_hours,
                cron_expression,
                risk_level
            )

            return {
                'has_issues': True,
                'risk_level': risk_level,
                'problematic_times': [f"{hour:02d}:00" for hour in risky_hours],
                'recommendations': recommendations,
                'dst_transition_dates': self._format_dst_transitions(tz),
                'message': f'Schedule runs during DST risk hours: {risky_hours}'
            }

        except pytz.exceptions.UnknownTimeZoneError as e:
            logger.error(f"Invalid timezone: {timezone_name}")
            return {
                'has_issues': False,
                'error': f'Invalid timezone: {timezone_name}',
                'risk_level': 'unknown'
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Validation error: {e}")
            return {
                'has_issues': False,
                'error': str(e),
                'risk_level': 'unknown'
            }

    def get_dst_transitions(
        self,
        year: int,
        timezone_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get DST transition dates for a specific year and timezone.

        Args:
            year: Year to check (e.g., 2025)
            timezone_name: Timezone name (e.g., 'US/Eastern')

        Returns:
            List of DST transitions with metadata

        Example:
            [
                {
                    'date': datetime(2025, 3, 9, 2, 0),
                    'type': 'spring_forward',
                    'description': 'Clock jumps from 2:00 AM to 3:00 AM',
                    'impact': 'Schedules at 2:00-3:00 AM will be skipped'
                },
                {
                    'date': datetime(2025, 11, 2, 2, 0),
                    'type': 'fall_back',
                    'description': 'Clock falls back from 2:00 AM to 1:00 AM',
                    'impact': 'Schedules at 1:00-2:00 AM will run twice'
                }
            ]
        """
        # Check cache first
        cache_key = f"{self.CACHE_PREFIX}:transitions:{timezone_name}:{year}"
        cached = cache.get(cache_key)

        if cached:
            logger.debug(f"Cache hit for DST transitions: {timezone_name} {year}")
            return cached

        try:
            tz = pytz.timezone(timezone_name)

            transitions = []

            # Scan the year for DST transitions
            # Check first day of each month for DST changes
            for month in range(1, 13):
                try:
                    # Create datetime at start of month
                    dt = tz.localize(datetime(year, month, 1, 0, 0))

                    # Check days around typical DST dates
                    for day_offset in range(0, 31):
                        try:
                            check_date = dt + timedelta(days=day_offset)

                            # Compare offset before and after
                            before = check_date - timedelta(hours=1)
                            after = check_date + timedelta(hours=1)

                            before_offset = before.utcoffset()
                            after_offset = after.utcoffset()

                            if before_offset != after_offset:
                                transition_type = (
                                    'spring_forward' if after_offset > before_offset
                                    else 'fall_back'
                                )

                                transitions.append({
                                    'date': check_date,
                                    'type': transition_type,
                                    'description': self._get_transition_description(transition_type),
                                    'impact': self._get_transition_impact(transition_type),
                                    'before_offset': str(before_offset),
                                    'after_offset': str(after_offset)
                                })

                                break  # Found transition for this month

                        except (ValueError, OverflowError):
                            continue

                except (ValueError, OverflowError):
                    continue

            # Cache the results
            cache.set(cache_key, transitions, timeout=self.CACHE_TTL)

            logger.info(f"Found {len(transitions)} DST transitions for {timezone_name} {year}")
            return transitions

        except pytz.exceptions.UnknownTimeZoneError as e:
            logger.error(f"Invalid timezone: {timezone_name}")
            return []

    def recommend_dst_safe_alternative(
        self,
        problematic_hour: int,
        timezone_name: str
    ) -> List[Dict[str, str]]:
        """
        Recommend DST-safe alternative times.

        Args:
            problematic_hour: Hour that falls in DST risk window (0-23)
            timezone_name: Timezone name

        Returns:
            List of recommended alternative times with reasoning

        Example:
            [
                {
                    'time': '04:00',
                    'reason': 'Safe: 2 hours after typical DST transition',
                    'priority': 'high'
                },
                {
                    'time': '23:00',
                    'reason': 'Safe: 1 hour before DST risk window',
                    'priority': 'medium'
                }
            ]
        """
        alternatives = []

        # Add safe hours with reasoning
        for safe_hour in self.SAFE_HOURS:
            if safe_hour > problematic_hour:
                offset = safe_hour - problematic_hour
                reason = f"Safe: {offset} hours after DST risk window"
                priority = 'high' if offset >= 2 else 'medium'
            else:
                offset = problematic_hour - safe_hour
                reason = f"Safe: {offset} hours before DST risk window"
                priority = 'medium'

            alternatives.append({
                'time': f"{safe_hour:02d}:00",
                'reason': reason,
                'priority': priority,
                'timezone': timezone_name
            })

        # Sort by priority (high first)
        alternatives.sort(key=lambda x: (x['priority'] != 'high', x['time']))

        return alternatives[:3]  # Return top 3 alternatives

    # Private helper methods

    def _has_dst_transitions(self, tz: pytz.timezone) -> bool:
        """Check if timezone has DST transitions"""
        try:
            # Check if timezone has transition times
            if not hasattr(tz, '_utc_transition_times'):
                return False

            # Some timezones exist but have no transitions (e.g., Asia/Kolkata)
            # Check by looking at a known DST-affected date
            test_date = datetime(2025, 3, 15, 2, 0)
            localized = tz.localize(test_date)

            # Check 6 months later
            later_date = datetime(2025, 9, 15, 2, 0)
            later_localized = tz.localize(later_date)

            # If offsets differ, timezone has DST
            return localized.utcoffset() != later_localized.utcoffset()

        except (AttributeError, ValueError):
            return False

    def _extract_risky_hours_from_cron(self, cron_expression: str) -> List[int]:
        """Extract hours from cron expression that fall in DST risk window"""
        try:
            parts = cron_expression.split()

            if len(parts) < 5:
                return []

            # Cron format: minute hour day month dow
            hour_field = parts[1]

            risky_hours = []

            if hour_field == '*':
                # Every hour - includes risky hours
                risky_hours = self.DST_RISK_HOURS
            elif '/' in hour_field:
                # Step values (e.g., */2 or 0-23/3)
                step = int(hour_field.split('/')[1])
                all_hours = list(range(0, 24, step))
                risky_hours = [h for h in all_hours if h in self.DST_RISK_HOURS]
            elif ',' in hour_field:
                # Comma-separated (e.g., 1,2,3)
                hours = [int(h) for h in hour_field.split(',')]
                risky_hours = [h for h in hours if h in self.DST_RISK_HOURS]
            elif '-' in hour_field:
                # Range (e.g., 1-5)
                start, end = map(int, hour_field.split('-'))
                hours = list(range(start, end + 1))
                risky_hours = [h for h in hours if h in self.DST_RISK_HOURS]
            else:
                # Single hour
                hour = int(hour_field)
                if hour in self.DST_RISK_HOURS:
                    risky_hours = [hour]

            return risky_hours

        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing cron expression: {e}")
            return []

    def _assess_risk_level(self, risky_hours: List[int]) -> str:
        """Assess risk level based on risky hours"""
        if not risky_hours:
            return 'none'

        # Hour 2 is highest risk (center of DST transition)
        if 2 in risky_hours:
            return 'high'

        # Hours 1 or 3 are medium risk (adjacent to transition)
        if any(h in [1, 3] for h in risky_hours):
            return 'medium'

        return 'low'

    def _generate_recommendations(
        self,
        risky_hours: List[int],
        cron_expression: str,
        risk_level: str
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        if risk_level == 'high':
            recommendations.append(
                f"⚠️ HIGH RISK: Schedule at {risky_hours} falls exactly on DST transition hour (2 AM)"
            )
            recommendations.append(
                "RECOMMENDED: Change schedule to 4:00 AM or later to avoid DST issues"
            )
        elif risk_level == 'medium':
            recommendations.append(
                f"⚠️ MEDIUM RISK: Schedule at {risky_hours} is adjacent to DST transition"
            )
            recommendations.append(
                "RECOMMENDED: Change schedule to 4:00 AM or use 23:00 (11 PM)"
            )

        recommendations.append(
            "Alternative: Use UTC timezone if local time doesn't matter"
        )

        # Add specific alternatives
        for hour in risky_hours:
            alternatives = self.recommend_dst_safe_alternative(hour, 'UTC')
            if alternatives:
                alt_times = ', '.join([a['time'] for a in alternatives[:2]])
                recommendations.append(
                    f"Safe alternatives for {hour:02d}:00 → {alt_times}"
                )

        return recommendations

    def _format_dst_transitions(self, tz: pytz.timezone) -> List[Dict[str, str]]:
        """Format DST transitions for display"""
        transitions = []

        current_year = datetime.now().year

        for year in [current_year, current_year + 1]:
            year_transitions = self.get_dst_transitions(year, str(tz))

            for trans in year_transitions:
                transitions.append({
                    'date': trans['date'].strftime('%Y-%m-%d'),
                    'type': trans['type'],
                    'description': trans['description']
                })

        return transitions

    def _get_transition_description(self, transition_type: str) -> str:
        """Get human-readable transition description"""
        if transition_type == 'spring_forward':
            return 'Clock jumps from 2:00 AM to 3:00 AM (skips 1 hour)'
        else:
            return 'Clock falls back from 2:00 AM to 1:00 AM (repeats 1 hour)'

    def _get_transition_impact(self, transition_type: str) -> str:
        """Get impact description for transition"""
        if transition_type == 'spring_forward':
            return 'Schedules at 2:00-3:00 AM will be SKIPPED on this date'
        else:
            return 'Schedules at 1:00-2:00 AM will run TWICE on this date'

    def get_service_name(self) -> str:
        """Return service name for monitoring"""
        return "DSTValidator"
