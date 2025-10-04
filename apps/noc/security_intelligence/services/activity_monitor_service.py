"""
Activity Monitor Service.

Multi-signal inactivity detection for night shift guards.
Uses phone activity, movement, tasks, and tours to detect sleeping guards.

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


class ActivityMonitorService:
    """Monitors guard activity for inactivity detection."""

    def __init__(self, config):
        """
        Initialize monitor with configuration.

        Args:
            config: SecurityAnomalyConfig instance
        """
        self.config = config

    def analyze_guard_activity(self, person, site, tracking_window):
        """
        Analyze guard activity across multiple signals.

        Args:
            person: People instance
            site: Bt instance
            tracking_window: GuardActivityTracking instance

        Returns:
            dict: Analysis result with inactivity score
        """
        try:
            signals = self._collect_activity_signals(tracking_window)

            inactivity_score = self._calculate_inactivity_score(
                signals,
                tracking_window.is_deep_night
            )

            is_inactive = inactivity_score >= self.config.inactivity_score_threshold

            return {
                'inactivity_score': inactivity_score,
                'is_inactive': is_inactive,
                'signals': signals,
                'duration_minutes': self.config.inactivity_window_minutes,
                'is_deep_night': tracking_window.is_deep_night,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Activity analysis error: {e}", exc_info=True)
            return {'inactivity_score': 0.0, 'is_inactive': False}

    def _collect_activity_signals(self, tracking):
        """Collect activity signals from tracking record."""
        return {
            'phone_events': tracking.phone_events_count,
            'location_updates': tracking.location_updates_count,
            'movement_meters': tracking.movement_distance_meters,
            'tasks_completed': tracking.tasks_completed_count,
            'tour_scans': tracking.tour_checkpoints_scanned,
        }

    def _calculate_inactivity_score(self, signals, is_deep_night):
        """
        Calculate weighted inactivity score.

        Args:
            signals: dict of activity signals
            is_deep_night: bool indicating deep night hours

        Returns:
            float: Inactivity score (0-1)
        """
        weights = self._get_signal_weights(is_deep_night)

        score = 0.0

        if signals['phone_events'] == 0:
            score += weights['phone']

        if signals['movement_meters'] < 10:
            score += weights['movement']

        if signals['tasks_completed'] == 0:
            score += weights['tasks']

        if signals['tour_scans'] == 0:
            score += weights['tours']

        if is_deep_night:
            score = min(score * 1.2, 1.0)

        return round(score, 2)

    def _get_signal_weights(self, is_deep_night):
        """Get signal weights based on time of day."""
        if is_deep_night:
            return {
                'phone': 0.3,
                'movement': 0.4,
                'tasks': 0.25,
                'tours': 0.3,
            }
        else:
            return {
                'phone': 0.2,
                'movement': 0.3,
                'tasks': 0.25,
                'tours': 0.25,
            }

    @transaction.atomic
    def create_inactivity_alert(self, tracking, analysis):
        """
        Create inactivity alert.

        Args:
            tracking: GuardActivityTracking instance
            analysis: dict from analyze_guard_activity

        Returns:
            InactivityAlert instance
        """
        from apps.noc.security_intelligence.models import InactivityAlert

        try:
            severity = self._determine_severity(analysis['inactivity_score'], analysis['is_deep_night'])

            alert = InactivityAlert.objects.create(
                tenant=tracking.tenant,
                person=tracking.person,
                site=tracking.site,
                activity_tracking=tracking,
                detected_at=timezone.now(),
                severity=severity,
                inactivity_score=analysis['inactivity_score'],
                inactivity_duration_minutes=analysis['duration_minutes'],
                no_phone_activity=analysis['signals']['phone_events'] == 0,
                no_movement=analysis['signals']['movement_meters'] < 10,
                no_tasks_completed=analysis['signals']['tasks_completed'] == 0,
                no_tour_scans=analysis['signals']['tour_scans'] == 0,
                is_deep_night=analysis['is_deep_night'],
                evidence_data=analysis['signals'],
            )

            tracking.alert_generated = True
            tracking.save(update_fields=['alert_generated'])

            logger.info(f"Created inactivity alert: {alert}")
            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"Alert creation error: {e}", exc_info=True)
            return None

    def _determine_severity(self, score, is_deep_night):
        """Determine alert severity based on score."""
        if score >= 0.9:
            return 'CRITICAL'
        elif score >= 0.8:
            return 'HIGH'
        elif score >= 0.6:
            return 'MEDIUM'
        else:
            return 'LOW'