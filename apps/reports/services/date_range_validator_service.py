"""
Report Date Range Validation Service

Provides comprehensive validation for report date ranges to prevent
oversized reports, invalid date selections, and performance issues.

Key Features:
- Future date detection and rejection
- Business day calculations
- Record count estimation
- Large range warnings with user confirmation
- Historical data validation
- Holiday calendar support (optional)

Complies with Rule #13 from .claude/rules.md
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

logger = logging.getLogger("django.reports")


class ReportDateRangeValidator:
    """
    Service for validating report date ranges.

    Prevents generation of oversized reports and provides
    intelligent validation with business logic.
    """

    # Configuration limits
    MAX_DAYS_STANDARD = 90  # Standard limit for most reports
    MAX_DAYS_EXTENDED = 365  # Extended limit with confirmation
    MAX_DAYS_ABSOLUTE = 730  # Absolute maximum (2 years)

    # Warning thresholds
    WARN_DAYS_THRESHOLD = 30  # Warn if > 30 days
    WARN_RECORD_THRESHOLD = 10000  # Warn if estimated > 10k records

    def __init__(self, report_type: str):
        """
        Initialize validator for specific report type.

        Args:
            report_type: Type of report to validate for
        """
        self.report_type = report_type
        self.validation_log = []

    def validate_date_range(
        self,
        from_date: date,
        to_date: date,
        user_confirmed_large: bool = False
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Comprehensive validation of date range.

        Args:
            from_date: Start date of range
            to_date: End date of range
            user_confirmed_large: Whether user confirmed large range warning

        Returns:
            Tuple of (is_valid, error_message, validation_info)
        """
        try:
            validation_info = {
                'is_valid': True,
                'warnings': [],
                'info': {},
                'requires_confirmation': False
            }

            # Validate date types
            if not isinstance(from_date, (date, datetime)):
                return False, "Invalid from_date type", validation_info

            if not isinstance(to_date, (date, datetime)):
                return False, "Invalid to_date type", validation_info

            # Convert datetime to date if needed
            if isinstance(from_date, datetime):
                from_date = from_date.date()
            if isinstance(to_date, datetime):
                to_date = to_date.date()

            # Validation 1: Future date check
            is_valid, error = self._validate_not_future(from_date, to_date)
            if not is_valid:
                return False, error, validation_info

            # Validation 2: Chronological order
            if from_date > to_date:
                return False, "From date cannot be later than to date", validation_info

            # Validation 3: Calculate range
            day_count = (to_date - from_date).days + 1
            validation_info['info']['day_count'] = day_count

            # Validation 4: Check against absolute maximum
            if day_count > self.MAX_DAYS_ABSOLUTE:
                return (
                    False,
                    f"Date range exceeds maximum of {self.MAX_DAYS_ABSOLUTE} days",
                    validation_info
                )

            # Validation 5: Check against standard limit
            if day_count > self.MAX_DAYS_STANDARD:
                if day_count <= self.MAX_DAYS_EXTENDED:
                    # Requires user confirmation
                    validation_info['requires_confirmation'] = True
                    validation_info['warnings'].append(
                        f"Large date range ({day_count} days). "
                        "This may take several minutes to generate."
                    )

                    if not user_confirmed_large:
                        return (
                            False,
                            f"Date range of {day_count} days requires confirmation",
                            validation_info
                        )
                else:
                    return (
                        False,
                        f"Date range exceeds extended limit of {self.MAX_DAYS_EXTENDED} days",
                        validation_info
                    )

            # Validation 6: Estimate record count
            estimated_records = self._estimate_record_count(
                from_date,
                to_date,
                self.report_type
            )
            validation_info['info']['estimated_records'] = estimated_records

            if estimated_records > self.WARN_RECORD_THRESHOLD:
                validation_info['warnings'].append(
                    f"Estimated {estimated_records:,} records. "
                    "Large report may take several minutes."
                )

            # Validation 7: Business day calculation (if needed)
            business_days = self._calculate_business_days(from_date, to_date)
            validation_info['info']['business_days'] = business_days

            # Add additional info
            validation_info['info']['from_date'] = from_date.isoformat()
            validation_info['info']['to_date'] = to_date.isoformat()

            logger.info(
                "Date range validation passed",
                extra={
                    'report_type': self.report_type,
                    'day_count': day_count,
                    'estimated_records': estimated_records
                }
            )

            return True, None, validation_info

        except (ValueError, TypeError, AttributeError) as e:
            error_msg = f"Date validation error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, validation_info

    def _validate_not_future(self, from_date: date, to_date: date) -> Tuple[bool, Optional[str]]:
        """
        Validate dates are not in the future.

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            Tuple of (is_valid, error_message)
        """
        today = timezone.now().date()

        if from_date > today:
            return False, f"From date cannot be in the future (today is {today})"

        if to_date > today:
            # Allow to_date to be today or past only
            return False, f"To date cannot be in the future (today is {today})"

        return True, None

    def _estimate_record_count(
        self,
        from_date: date,
        to_date: date,
        report_type: str
    ) -> int:
        """
        Estimate number of records for given date range.

        Uses heuristics based on report type and historical averages.

        Args:
            from_date: Start date
            to_date: End date
            report_type: Type of report

        Returns:
            Estimated record count
        """
        day_count = (to_date - from_date).days + 1

        # Heuristic multipliers per report type
        # These should be calibrated based on actual data
        RECORD_MULTIPLIERS = {
            'TASKSUMMARY': 50,  # ~50 tasks per day average
            'TOURSUMMARY': 20,  # ~20 tours per day
            'LISTOFTASKS': 100,  # ~100 task records per day
            'LISTOFTOURS': 40,
            'LISTOFTICKETS': 30,
            'ATTENDANCE': 200,  # ~200 attendance records per day
            'SITEREPORT': 10,
            'DEFAULT': 50
        }

        multiplier = RECORD_MULTIPLIERS.get(report_type, RECORD_MULTIPLIERS['DEFAULT'])
        estimated = day_count * multiplier

        return estimated

    def _calculate_business_days(self, from_date: date, to_date: date) -> int:
        """
        Calculate number of business days in range.

        Excludes weekends (Saturday, Sunday).

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            Number of business days
        """
        business_days = 0
        current_date = from_date

        while current_date <= to_date:
            # Monday = 0, Sunday = 6
            if current_date.weekday() < 5:  # Monday through Friday
                business_days += 1
            current_date += timedelta(days=1)

        return business_days

    def validate_business_day_range(
        self,
        from_date: date,
        business_days: int
    ) -> Tuple[date, Dict[str, Any]]:
        """
        Calculate to_date for "last N business days" filter.

        Args:
            from_date: Start date
            business_days: Number of business days desired

        Returns:
            Tuple of (to_date, validation_info)
        """
        if business_days <= 0:
            raise ValidationError("Business days must be positive")

        if business_days > 250:  # ~1 year of business days
            raise ValidationError("Business days cannot exceed 250 (approx 1 year)")

        # Calculate to_date by adding business days
        current_date = from_date
        days_added = 0

        while days_added < business_days:
            current_date += timedelta(days=1)
            if current_date.weekday() < 5:  # Weekday
                days_added += 1

        validation_info = {
            'from_date': from_date.isoformat(),
            'to_date': current_date.isoformat(),
            'business_days': business_days,
            'calendar_days': (current_date - from_date).days + 1
        }

        logger.info(
            "Business day range calculated",
            extra=validation_info
        )

        return current_date, validation_info

    def get_recommended_range(self, report_type: str) -> Dict[str, date]:
        """
        Get recommended date range for report type.

        Args:
            report_type: Type of report

        Returns:
            Dictionary with recommended from_date and to_date
        """
        today = timezone.now().date()

        # Different recommendations per report type
        RECOMMENDED_DAYS = {
            'TASKSUMMARY': 30,  # Last 30 days
            'TOURSUMMARY': 30,
            'ATTENDANCE': 7,  # Last week
            'LISTOFTASKS': 14,  # Last 2 weeks
            'DEFAULT': 30
        }

        days = RECOMMENDED_DAYS.get(report_type, RECOMMENDED_DAYS['DEFAULT'])
        from_date = today - timedelta(days=days - 1)

        return {
            'from_date': from_date,
            'to_date': today,
            'reason': f'Recommended {days}-day range for {report_type}'
        }


def validate_report_date_range(
    from_date: date,
    to_date: date,
    report_type: str,
    user_confirmed: bool = False
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Convenience function for validating report date ranges.

    Args:
        from_date: Start date
        to_date: End date
        report_type: Type of report
        user_confirmed: Whether user confirmed large range

    Returns:
        Tuple of (is_valid, error_message, validation_info)
    """
    validator = ReportDateRangeValidator(report_type)
    return validator.validate_date_range(from_date, to_date, user_confirmed)


def get_last_n_business_days(
    n_days: int,
    end_date: Optional[date] = None
) -> Tuple[date, date]:
    """
    Get date range for last N business days.

    Args:
        n_days: Number of business days
        end_date: End date (default: today)

    Returns:
        Tuple of (from_date, to_date)
    """
    if end_date is None:
        end_date = timezone.now().date()

    # Work backwards to find N business days
    business_days_found = 0
    current_date = end_date

    while business_days_found < n_days:
        if current_date.weekday() < 5:  # Weekday
            business_days_found += 1
        if business_days_found < n_days:
            current_date -= timedelta(days=1)

    return current_date, end_date
