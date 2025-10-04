"""
Pattern Analyzer Service.

Analyzes attendance patterns and detects behavioral anomalies.
Learns normal behavior baselines for anomaly detection.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, StdDev
import statistics

logger = logging.getLogger('noc.security_intelligence.ml')


class PatternAnalyzer:
    """Analyzes behavioral patterns for anomaly detection."""

    @classmethod
    def analyze_temporal_patterns(cls, person, days=90):
        """
        Analyze temporal attendance patterns.

        Args:
            person: People instance
            days: Days to analyze

        Returns:
            dict: Temporal pattern analysis
        """
        from apps.attendance.models import PeopleEventlog

        try:
            since = timezone.now() - timedelta(days=days)

            events = PeopleEventlog.objects.filter(
                people=person,
                datefor__gte=since.date(),
                punchintime__isnull=False
            )

            if events.count() < 10:
                return None

            punch_hours = [e.punchintime.hour for e in events]
            work_days = [e.datefor.weekday() for e in events]

            return {
                'typical_hours': cls._get_mode_values(punch_hours),
                'hour_variance': statistics.stdev(punch_hours) if len(punch_hours) > 1 else 0,
                'typical_days': cls._get_mode_values(work_days),
                'total_observations': events.count(),
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Temporal pattern analysis error: {e}", exc_info=True)
            return None

    @classmethod
    def analyze_site_patterns(cls, person, days=90):
        """
        Analyze site attendance patterns.

        Args:
            person: People instance
            days: Days to analyze

        Returns:
            dict: Site pattern analysis
        """
        from apps.attendance.models import PeopleEventlog

        try:
            since = timezone.now() - timedelta(days=days)

            site_stats = PeopleEventlog.objects.filter(
                people=person,
                datefor__gte=since.date(),
                bu__isnull=False
            ).values('bu__name').annotate(
                count=Count('id')
            ).order_by('-count')

            if not site_stats:
                return None

            total = sum(s['count'] for s in site_stats)
            primary_sites = [
                {'site': s['bu__name'], 'frequency': s['count'] / total}
                for s in site_stats[:3]
            ]

            return {
                'primary_sites': primary_sites,
                'site_variety_score': len(site_stats) / max(total, 1),
                'total_sites': len(site_stats),
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Site pattern analysis error: {e}", exc_info=True)
            return None

    @classmethod
    def analyze_biometric_patterns(cls, person, days=90):
        """
        Analyze biometric verification patterns.

        Args:
            person: People instance
            days: Days to analyze

        Returns:
            dict: Biometric pattern analysis
        """
        from apps.noc.security_intelligence.models import BiometricVerificationLog

        try:
            since = timezone.now() - timedelta(days=days)

            verifications = BiometricVerificationLog.objects.filter(
                person=person,
                verified_at__gte=since
            )

            if verifications.count() < 5:
                return None

            stats = verifications.aggregate(
                avg_confidence=Avg('confidence_score'),
                stddev_confidence=StdDev('confidence_score'),
                avg_quality=Avg('quality_score'),
            )

            return {
                'avg_confidence': stats['avg_confidence'] or 0,
                'confidence_variance': stats['stddev_confidence'] or 0,
                'avg_quality': stats['avg_quality'] or 0,
                'total_verifications': verifications.count(),
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Biometric pattern analysis error: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_mode_values(values):
        """Get most common values from list."""
        if not values:
            return []

        from collections import Counter
        counter = Counter(values)
        return [item for item, count in counter.most_common(3)]

    @classmethod
    def detect_behavioral_drift(cls, person, current_event, profile):
        """
        Detect deviation from behavioral baseline.

        Args:
            person: People instance
            current_event: Current attendance event
            profile: BehavioralProfile instance

        Returns:
            dict: Drift analysis or None
        """
        try:
            drift_indicators = []
            drift_score = 0.0

            hour = current_event.punchintime.hour
            if hour not in profile.typical_punch_in_hours:
                drift_indicators.append('UNUSUAL_TIME')
                drift_score += 0.3

            day = current_event.datefor.weekday()
            if day not in profile.typical_work_days:
                drift_indicators.append('UNUSUAL_DAY')
                drift_score += 0.2

            if profile.primary_sites:
                site_ids = [s['site_id'] for s in profile.primary_sites]
                if current_event.bu_id not in site_ids:
                    drift_indicators.append('UNUSUAL_SITE')
                    drift_score += 0.3

            if drift_score >= profile.anomaly_detection_threshold:
                return {
                    'has_drift': True,
                    'drift_score': drift_score,
                    'indicators': drift_indicators,
                }

            return {'has_drift': False}

        except (ValueError, AttributeError) as e:
            logger.error(f"Drift detection error: {e}", exc_info=True)
            return {'has_drift': False}