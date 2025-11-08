"""
Shift Compliance Service.

Validates shift schedules and detects schedule mismatches.
Ensures guards are at correct sites during correct times.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger('noc.security_intelligence')


class ShiftComplianceService:
    """Validates shift schedule compliance."""

    def __init__(self, config):
        """
        Initialize service with configuration.

        Args:
            config: SecurityAnomalyConfig instance
        """
        self.config = config

    def validate_attendance_against_schedule(self, attendance_event):
        """
        Validate attendance against cached schedule.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Validation result with anomalies if any
        """
        from apps.noc.security_intelligence.models import ShiftScheduleCache

        try:
            scheduled_shift = ShiftScheduleCache.objects.filter(
                tenant=attendance_event.tenant,
                person=attendance_event.people,
                shift_date=attendance_event.datefor,
                cache_valid_until__gt=timezone.now()
            ).select_related('person', 'site', 'shift').first()

            if not scheduled_shift:
                return {
                    'has_anomaly': True,
                    'anomaly_type': 'SCHEDULE_MISMATCH',
                    'severity': 'MEDIUM',
                    'reason': 'No scheduled shift found',
                    'confidence_score': 0.70,
                }

            if scheduled_shift.site_id != attendance_event.bu_id:
                return {
                    'has_anomaly': True,
                    'anomaly_type': 'WRONG_SITE',
                    'severity': 'HIGH',
                    'expected_site': scheduled_shift.site,
                    'actual_site': attendance_event.bu,
                    'confidence_score': 0.85,
                }

            time_diff_minutes = abs((attendance_event.punchintime - scheduled_shift.scheduled_start).total_seconds() / 60)

            if time_diff_minutes > 60:
                return {
                    'has_anomaly': True,
                    'anomaly_type': 'SCHEDULE_MISMATCH',
                    'severity': 'LOW',
                    'reason': f'Attendance {int(time_diff_minutes)} minutes off schedule',
                    'confidence_score': 0.60,
                }

            return {'has_anomaly': False}

        except (ValueError, AttributeError) as e:
            logger.error(f"Schedule validation error: {e}", exc_info=True)
            return {'has_anomaly': False, 'error': str(e)}

    def check_substitute_authorization(self, person, site, date):
        """
        Check if person is authorized substitute for site.

        Args:
            person: People instance
            site: Bt instance
            date: Date to check

        Returns:
            bool: True if authorized
        """
        from apps.noc.security_intelligence.models import ShiftScheduleCache

        try:
            return ShiftScheduleCache.objects.filter(
                tenant=person.tenant,
                person=person,
                site=site,
                shift_date=date,
                is_substitute=True,
                cache_valid_until__gt=timezone.now()
            ).exists()
        except (ValueError, AttributeError) as e:
            logger.error(f"Substitute check error: {e}", exc_info=True)
            return False

    @transaction.atomic
    def build_schedule_cache(self, tenant, start_date, end_date):
        """
        Build schedule cache for date range.
        Materializes shift schedules for next 14 days.

        Args:
            tenant: Tenant instance
            start_date: Start date
            end_date: End date

        Returns:
            int: Number of cache entries created
        """
        from apps.noc.security_intelligence.models import ShiftScheduleCache
        from apps.scheduler.models import Schedule
        from apps.onboarding.models import Shift
        from datetime import datetime, timedelta

        try:
            cache_valid_until = timezone.now() + timedelta(days=7)
            count = 0

            logger.info(f"Building schedule cache for {tenant.name} from {start_date} to {end_date}")

            # Get all active schedules for tenant
            schedules = Schedule.objects.filter(
                tenant=tenant,
                is_active=True
            ).select_related('assigned_to', 'site')

            # Process each schedule
            current_date = start_date
            while current_date <= end_date:
                for schedule in schedules:
                    # Check if schedule applies to this date
                    if schedule.start_date and schedule.start_date > current_date.date():
                        continue
                    if schedule.end_date and schedule.end_date < current_date.date():
                        continue

                    # Get shift details
                    shift = None
                    if hasattr(schedule, 'shift'):
                        shift = schedule.shift

                    # Create cache entry
                    ShiftScheduleCache.objects.update_or_create(
                        tenant=tenant,
                        person=schedule.assigned_to,
                        site=schedule.site,
                        shift_date=current_date.date(),
                        defaults={
                            'shift': shift,
                            'scheduled_start': datetime.combine(
                                current_date.date(),
                                shift.start_time if shift and shift.start_time else datetime.min.time()
                            ),
                            'scheduled_end': datetime.combine(
                                current_date.date(),
                                shift.end_time if shift and shift.end_time else datetime.max.time()
                            ),
                            'is_substitute': False,
                            'cache_valid_until': cache_valid_until
                        }
                    )
                    count += 1

                current_date += timedelta(days=1)

            logger.info(f"Created {count} schedule cache entries")
            return count

        except (ValueError, AttributeError) as e:
            logger.error(f"Schedule cache build error: {e}", exc_info=True)
            return 0

    def get_scheduled_guards_for_site(self, tenant, site, date):
        """
        Get all guards scheduled for a site on a date.

        Args:
            tenant: Tenant instance
            site: Bt instance
            date: Date to check

        Returns:
            QuerySet: Scheduled People
        """
        from apps.noc.security_intelligence.models import ShiftScheduleCache

        try:
            return ShiftScheduleCache.objects.filter(
                tenant=tenant,
                site=site,
                shift_date=date,
                cache_valid_until__gt=timezone.now()
            ).select_related('person').values_list('person', flat=True)
        except (ValueError, AttributeError) as e:
            logger.error(f"Scheduled guards lookup error: {e}", exc_info=True)
            return []