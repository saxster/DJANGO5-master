"""
Behavioral Profiler Service.

Creates and updates behavioral profiles for guards.
Learns normal behavior patterns from historical data.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger('noc.security_intelligence.ml')


class BehavioralProfiler:
    """Creates and maintains behavioral profiles."""

    @classmethod
    @transaction.atomic
    def create_or_update_profile(cls, person, days=90):
        """
        Create or update behavioral profile.

        Args:
            person: People instance
            days: Days of history to analyze

        Returns:
            BehavioralProfile instance
        """
        from apps.noc.security_intelligence.models import BehavioralProfile
        from apps.noc.security_intelligence.ml import PatternAnalyzer

        try:
            temporal = PatternAnalyzer.analyze_temporal_patterns(person, days)
            site_patterns = PatternAnalyzer.analyze_site_patterns(person, days)
            biometric = PatternAnalyzer.analyze_biometric_patterns(person, days)

            if not temporal or not site_patterns:
                logger.warning(f"Insufficient data for {person.peoplename}")
                return None

            activity_stats = cls._analyze_activity_patterns(person, days)

            profile, created = BehavioralProfile.objects.update_or_create(
                tenant=person.tenant,
                person=person,
                defaults={
                    'profile_start_date': (timezone.now() - timedelta(days=days)).date(),
                    'profile_end_date': timezone.now().date(),
                    'total_observations': temporal['total_observations'],
                    'typical_punch_in_hours': temporal['typical_hours'],
                    'typical_work_days': temporal['typical_days'],
                    'primary_sites': site_patterns['primary_sites'],
                    'site_variety_score': site_patterns['site_variety_score'],
                    'avg_biometric_confidence': biometric['avg_confidence'] if biometric else 0,
                    'biometric_variance': biometric['confidence_variance'] if biometric else 0,
                    'avg_tasks_per_shift': activity_stats['avg_tasks_per_shift'],
                    'avg_tours_per_shift': activity_stats['avg_tours_per_shift'],
                    'night_shift_percentage': activity_stats['night_shift_percentage'],
                    'consistency_score': cls._calculate_consistency_score(temporal, site_patterns),
                    'last_trained_at': timezone.now(),
                }
            )

            logger.info(f"{'Created' if created else 'Updated'} profile for {person.peoplename}")
            return profile

        except (ValueError, AttributeError) as e:
            logger.error(f"Profile creation error: {e}", exc_info=True)
            return None

    @classmethod
    def _analyze_activity_patterns(cls, person, days):
        """Analyze task and tour activity patterns."""
        from apps.activity.models import Jobneed
        from apps.attendance.models import PeopleEventlog

        try:
            since = timezone.now() - timedelta(days=days)

            tasks_count = Jobneed.objects.filter(
                people=person,
                cdtz__gte=since,
                status='COMPLETED'
            ).count()

            shifts_count = PeopleEventlog.objects.filter(
                people=person,
                datefor__gte=since.date()
            ).count()

            night_shifts = PeopleEventlog.objects.filter(
                people=person,
                datefor__gte=since.date(),
                punchintime__hour__gte=20
            ).count() + PeopleEventlog.objects.filter(
                people=person,
                datefor__gte=since.date(),
                punchintime__hour__lte=6
            ).count()

            return {
                'avg_tasks_per_shift': tasks_count / max(shifts_count, 1),
                'avg_tours_per_shift': 0.0,
                'night_shift_percentage': night_shifts / max(shifts_count, 1) * 100,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Activity pattern analysis error: {e}", exc_info=True)
            return {
                'avg_tasks_per_shift': 0.0,
                'avg_tours_per_shift': 0.0,
                'night_shift_percentage': 0.0,
            }

    @staticmethod
    def _calculate_consistency_score(temporal_patterns, site_patterns):
        """Calculate overall consistency score."""
        try:
            hour_consistency = 1.0 - min(temporal_patterns.get('hour_variance', 0) / 12.0, 1.0)

            site_consistency = 1.0 - site_patterns.get('site_variety_score', 0)

            return (hour_consistency + site_consistency) / 2

        except (ValueError, AttributeError, ZeroDivisionError):
            return 0.5

    @classmethod
    def check_deviation_from_profile(cls, person, attendance_event):
        """
        Check if attendance deviates from profile.

        Args:
            person: People instance
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Deviation analysis
        """
        from apps.noc.security_intelligence.models import BehavioralProfile

        try:
            profile = BehavioralProfile.objects.filter(person=person).first()

            if not profile or not profile.is_sufficient_data:
                return {'has_deviation': False, 'reason': 'insufficient_profile_data'}

            from apps.noc.security_intelligence.ml import PatternAnalyzer
            drift = PatternAnalyzer.detect_behavioral_drift(person, attendance_event, profile)

            return drift

        except (ValueError, AttributeError) as e:
            logger.error(f"Deviation check error: {e}", exc_info=True)
            return {'has_deviation': False}