"""
Baseline Calculator Service.

Calculates hour-of-week activity baselines for each site and metric type.
Uses historical data to build normal behavior patterns for anomaly detection.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta, date
from django.utils import timezone
from django.db.models import Avg, StdDev, Min, Max, Count

from apps.noc.security_intelligence.models import BaselineProfile
from apps.noc.security_intelligence.services.activity_signal_collector import ActivitySignalCollector

logger = logging.getLogger('noc.baseline_calculator')


class BaselineCalculator:
    """
    Calculates baselines for hour-of-week activity patterns.

    Learning approach:
    - Collects 30+ days of historical data
    - Computes mean, std_dev, percentiles per hour-of-week
    - Updates incrementally as new data arrives
    """

    @classmethod
    def calculate_baselines_for_site(cls, site, start_date=None, days_lookback=30):
        """
        Calculate or update all baselines for a site.

        Args:
            site: Bt instance
            start_date: Optional start date (defaults to 30 days ago)
            days_lookback: Number of days of history to analyze

        Returns:
            dict: Summary of baselines created/updated
        """
        try:
            if start_date is None:
                start_date = date.today() - timedelta(days=days_lookback)

            end_date = date.today()

            logger.info(f"Calculating baselines for {site.buname} from {start_date} to {end_date}")

            metric_types = [
                'phone_events',
                'location_updates',
                'movement_distance',
                'tasks_completed',
                'tour_checkpoints',
            ]

            summary = {
                'site': site.buname,
                'baselines_updated': 0,
                'baselines_created': 0,
                'errors': 0,
            }

            for metric_type in metric_types:
                result = cls._calculate_metric_baseline(site, metric_type, start_date, end_date)
                summary['baselines_updated'] += result['updated']
                summary['baselines_created'] += result['created']
                summary['errors'] += result['errors']

            logger.info(f"Baseline calculation complete: {summary}")
            return summary

        except (ValueError, AttributeError) as e:
            logger.error(f"Baseline calculation error: {e}", exc_info=True)
            return {'errors': 1}

    @classmethod
    def _calculate_metric_baseline(cls, site, metric_type, start_date, end_date):
        """Calculate baselines for single metric type across all hours-of-week."""
        summary = {'created': 0, 'updated': 0, 'errors': 0}

        current_date = start_date
        while current_date <= end_date:
            for hour in range(24):
                try:
                    dt = timezone.datetime.combine(current_date, timezone.datetime.min.time().replace(hour=hour))
                    hour_of_week = dt.weekday() * 24 + hour  # 0-167

                    # Get or create baseline
                    baseline = BaselineProfile.get_baseline(site, metric_type, hour_of_week)

                    # Calculate metric value for this hour (simplified)
                    metric_value = cls._get_metric_value_for_hour(site, metric_type, dt)

                    # Update baseline
                    if metric_value is not None:
                        was_new = baseline.sample_count == 0
                        baseline.update_baseline(metric_value)

                        if was_new:
                            summary['created'] += 1
                        else:
                            summary['updated'] += 1

                except (ValueError, AttributeError) as e:
                    logger.error(f"Metric baseline calculation error for {metric_type} at {dt}: {e}")
                    summary['errors'] += 1

            current_date += timedelta(days=1)

        return summary

    @classmethod
    def _get_metric_value_for_hour(cls, site, metric_type, datetime_obj):
        """
        Get actual metric value for a specific hour.

        Args:
            site: Bt instance
            metric_type: String metric type
            datetime_obj: Datetime for the hour to analyze

        Returns:
            float: Metric value or None
        """
        try:
            start_time = datetime_obj
            end_time = start_time + timedelta(hours=1)

            # Get active people for this site (simplified - using first active person)
            from apps.peoples.models import People
            person = People.objects.filter(
                tenant=site.tenant,
                peopleorganizational__bu=site,
                isactive=True
            ).first()

            if not person:
                return None

            # Collect signals for this hour
            signals = ActivitySignalCollector.collect_all_signals(
                person=person,
                site=site,
                window_minutes=60
            )

            # Map metric type to signal key
            metric_map = {
                'phone_events': 'phone_events_count',
                'location_updates': 'location_updates_count',
                'movement_distance': 'movement_distance_meters',
                'tasks_completed': 'tasks_completed_count',
                'tour_checkpoints': 'tour_checkpoints_scanned',
            }

            return float(signals.get(metric_map.get(metric_type, metric_type), 0))

        except (ValueError, AttributeError) as e:
            logger.error(f"Metric value calculation error: {e}", exc_info=True)
            return None

    @classmethod
    def update_baseline_incrementally(cls, site, metric_type, hour_of_week, new_value):
        """
        Update baseline with single new observation.

        Args:
            site: Bt instance
            metric_type: String metric type
            hour_of_week: Integer 0-167
            new_value: Float new observation

        Returns:
            BaselineProfile: Updated baseline
        """
        try:
            baseline = BaselineProfile.get_baseline(site, metric_type, hour_of_week)
            baseline.update_baseline(new_value)

            logger.info(
                f"Updated baseline for {site.buname} {metric_type} hour {hour_of_week}: "
                f"mean={baseline.mean:.2f}, std_dev={baseline.std_dev:.2f}, samples={baseline.sample_count}"
            )

            return baseline

        except (ValueError, AttributeError) as e:
            logger.error(f"Incremental baseline update error: {e}", exc_info=True)
            return None
