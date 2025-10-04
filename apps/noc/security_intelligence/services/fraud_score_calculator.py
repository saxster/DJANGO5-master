"""
Fraud Score Calculator Service.

Unified fraud risk scoring across all detection methods.
Combines biometric, GPS, attendance, and behavioral signals.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.utils import timezone

logger = logging.getLogger('noc.security_intelligence')


class FraudScoreCalculator:
    """Calculates unified fraud risk scores."""

    WEIGHT_BIOMETRIC_CONCURRENT = 0.35
    WEIGHT_GPS_SPOOFING = 0.30
    WEIGHT_GEOFENCE_VIOLATION = 0.15
    WEIGHT_LOW_QUALITY = 0.10
    WEIGHT_PATTERN_ANOMALY = 0.10

    @classmethod
    def calculate_fraud_score(cls, detection_results):
        """
        Calculate unified fraud score from all detections.

        Args:
            detection_results: dict with detection results from all detectors

        Returns:
            dict: Fraud score and risk level
        """
        try:
            score = 0.0
            fraud_types = []
            evidence = {}

            if detection_results.get('buddy_punching'):
                score += cls.WEIGHT_BIOMETRIC_CONCURRENT
                fraud_types.append('BUDDY_PUNCHING')
                evidence['concurrent_usage'] = detection_results['buddy_punching']

            if detection_results.get('gps_spoofing'):
                score += cls.WEIGHT_GPS_SPOOFING
                fraud_types.append('GPS_SPOOFING')
                evidence['impossible_speed'] = detection_results['gps_spoofing']

            if detection_results.get('geofence_violation'):
                score += cls.WEIGHT_GEOFENCE_VIOLATION
                fraud_types.append('GEOFENCE_VIOLATION')
                evidence['location_mismatch'] = detection_results['geofence_violation']

            if detection_results.get('low_biometric_quality'):
                score += cls.WEIGHT_LOW_QUALITY
                fraud_types.append('LOW_QUALITY_BIOMETRIC')
                evidence['quality_issue'] = detection_results['low_biometric_quality']

            if detection_results.get('pattern_anomaly'):
                score += cls.WEIGHT_PATTERN_ANOMALY
                fraud_types.append('PATTERN_ANOMALY')
                evidence['suspicious_pattern'] = detection_results['pattern_anomaly']

            risk_level = cls._determine_risk_level(score)

            return {
                'fraud_score': round(score, 2),
                'risk_level': risk_level,
                'fraud_types': fraud_types,
                'evidence': evidence,
                'requires_action': score >= 0.7,
                'requires_investigation': score >= 0.5,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Fraud score calculation error: {e}", exc_info=True)
            return {
                'fraud_score': 0.0,
                'risk_level': 'UNKNOWN',
                'fraud_types': [],
                'evidence': {},
            }

    @staticmethod
    def _determine_risk_level(score):
        """Determine risk level from fraud score."""
        if score >= 0.8:
            return 'CRITICAL'
        elif score >= 0.6:
            return 'HIGH'
        elif score >= 0.4:
            return 'MEDIUM'
        elif score >= 0.2:
            return 'LOW'
        else:
            return 'MINIMAL'

    @classmethod
    def calculate_person_fraud_history_score(cls, person, days=30):
        """
        Calculate historical fraud score for person.

        Args:
            person: People instance
            days: Days to analyze

        Returns:
            dict: Historical fraud metrics
        """
        from apps.noc.security_intelligence.models import (
            BiometricVerificationLog,
            GPSValidationLog,
            AttendanceAnomalyLog,
        )

        try:
            since = timezone.now() - timezone.timedelta(days=days)

            biometric_flags = BiometricVerificationLog.objects.filter(
                person=person,
                verified_at__gte=since,
                fraud_score__gte=0.5
            ).count()

            gps_flags = GPSValidationLog.objects.filter(
                person=person,
                validated_at__gte=since,
                fraud_score__gte=0.5
            ).count()

            attendance_anomalies = AttendanceAnomalyLog.objects.filter(
                person=person,
                detected_at__gte=since,
                status='CONFIRMED'
            ).count()

            total_flags = biometric_flags + gps_flags + attendance_anomalies

            history_score = min(total_flags / 10.0, 1.0)

            return {
                'history_score': round(history_score, 2),
                'biometric_flags': biometric_flags,
                'gps_flags': gps_flags,
                'confirmed_anomalies': attendance_anomalies,
                'total_flags': total_flags,
                'risk_level': cls._determine_risk_level(history_score),
                'period_days': days,
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"History score calculation error: {e}", exc_info=True)
            return {
                'history_score': 0.0,
                'risk_level': 'UNKNOWN',
            }

    @classmethod
    def should_auto_disable_biometric(cls, fraud_score, history_score):
        """
        Determine if biometric should be auto-disabled.

        Args:
            fraud_score: Current fraud score
            history_score: Historical fraud score

        Returns:
            bool: True if should disable
        """
        if fraud_score >= 0.95:
            return True

        if fraud_score >= 0.8 and history_score >= 0.6:
            return True

        return False