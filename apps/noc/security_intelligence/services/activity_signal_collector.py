"""
Activity Signal Collector Service.

Collects activity signals from multiple data sources.
Aggregates phone events, GPS updates, task completions, tour scans.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

logger = logging.getLogger('noc.security_intelligence')


class ActivitySignalCollector:
    """Collects activity signals from various sources."""

    @classmethod
    def collect_phone_activity(cls, person, start_time, end_time):
        """
        Collect phone/app activity events.

        Args:
            person: People instance
            start_time: Start of window
            end_time: End of window

        Returns:
            int: Count of phone events
        """
        from apps.activity.models import DeviceEventlog

        try:
            return DeviceEventlog.objects.filter(
                people=person,
                created_at__gte=start_time,
                created_at__lte=end_time
            ).count()
        except (ValueError, AttributeError) as e:
            logger.error(f"Phone activity collection error: {e}", exc_info=True)
            return 0

    @classmethod
    def collect_location_updates(cls, person, start_time, end_time):
        """
        Collect GPS location updates.

        Args:
            person: People instance
            start_time: Start of window
            end_time: End of window

        Returns:
            tuple: (update_count, total_movement_meters)
        """
        from apps.activity.models import Location

        try:
            locations = Location.objects.filter(
                people=person,
                cdtz__gte=start_time,
                cdtz__lte=end_time,
                gpslocation__isnull=False
            ).order_by('cdtz')

            count = locations.count()

            if count < 2:
                return count, 0.0

            total_distance = 0.0
            locations_list = list(locations.values('gpslocation'))

            for loc1_data, loc2_data in zip(locations_list, locations_list[1:]):
                loc1 = loc1_data['gpslocation']
                loc2 = loc2_data['gpslocation']

                if loc1 and loc2:
                    distance = loc1.distance(loc2)
                    total_distance += distance

            return count, total_distance

        except (ValueError, AttributeError) as e:
            logger.error(f"Location collection error: {e}", exc_info=True)
            return 0, 0.0

    @classmethod
    def collect_task_completions(cls, person, start_time, end_time):
        """
        Collect completed tasks.

        Args:
            person: People instance
            start_time: Start of window
            end_time: End of window

        Returns:
            int: Count of completed tasks
        """
        from apps.activity.models import Jobneed

        try:
            return Jobneed.objects.filter(
                people=person,
                mdtz__gte=start_time,
                mdtz__lte=end_time,
                status='COMPLETED'
            ).count()
        except (ValueError, AttributeError) as e:
            logger.error(f"Task collection error: {e}", exc_info=True)
            return 0

    @classmethod
    def collect_tour_checkpoints(cls, person, start_time, end_time):
        """
        Collect tour checkpoint scans.

        Counts completed checkpoint Jobneeds for tours assigned to the person.
        A checkpoint is considered "scanned" when its Jobneed has endtime set
        (indicating completion).

        Args:
            person: People instance
            start_time: Start of window
            end_time: End of window

        Returns:
            int: Count of checkpoint scans
        """
        try:
            from apps.activity.models.job_model import Jobneed

            # Count completed checkpoint jobneeds within time window
            # Checkpoints are Jobneeds with parent__isnull=False (child jobneeds)
            # Assigned to this person and completed in the time window
            checkpoint_count = Jobneed.objects.filter(
                people=person,
                parent__isnull=False,  # Child jobneed (checkpoint, not parent tour)
                endtime__gte=start_time,
                endtime__lte=end_time,
                endtime__isnull=False  # Must have been completed
            ).count()

            logger.debug(
                f"Collected {checkpoint_count} tour checkpoints for {person.peoplename} "
                f"in window {start_time} to {end_time}"
            )

            return checkpoint_count

        except (ValueError, AttributeError) as e:
            logger.error(f"Tour collection error: {e}", exc_info=True)
            return 0

    @classmethod
    def collect_all_signals(cls, person, site, window_minutes=120):
        """
        Collect all activity signals for time window.

        Args:
            person: People instance
            site: Bt instance
            window_minutes: Time window in minutes

        Returns:
            dict: All activity signals
        """
        end_time = timezone.now()
        start_time = end_time - timedelta(minutes=window_minutes)

        try:
            phone_events = cls.collect_phone_activity(person, start_time, end_time)
            location_count, movement_meters = cls.collect_location_updates(person, start_time, end_time)
            tasks_completed = cls.collect_task_completions(person, start_time, end_time)
            tour_scans = cls.collect_tour_checkpoints(person, start_time, end_time)

            return {
                'phone_events_count': phone_events,
                'location_updates_count': location_count,
                'movement_distance_meters': movement_meters,
                'tasks_completed_count': tasks_completed,
                'tour_checkpoints_scanned': tour_scans,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Signal collection error: {e}", exc_info=True)
            return {
                'phone_events_count': 0,
                'location_updates_count': 0,
                'movement_distance_meters': 0.0,
                'tasks_completed_count': 0,
                'tour_checkpoints_scanned': 0,
            }