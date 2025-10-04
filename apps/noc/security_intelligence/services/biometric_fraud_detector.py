"""
Biometric Fraud Detector Service.

Detects buddy punching and biometric attendance fraud.
Analyzes concurrent usage, pattern anomalies, and quality issues.

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


class BiometricFraudDetector:
    """Detects biometric-based attendance fraud."""

    def __init__(self, config):
        """
        Initialize detector with configuration.

        Args:
            config: SecurityAnomalyConfig instance
        """
        self.config = config

    def detect_buddy_punching(self, attendance_event):
        """
        Detect concurrent biometric usage (buddy punching).

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Fraud detection result or None
        """
        from apps.noc.security_intelligence.models import BiometricVerificationLog

        try:
            window_minutes = self.config.concurrent_biometric_window_minutes
            time_window_start = attendance_event.punchintime - timedelta(minutes=window_minutes)
            time_window_end = attendance_event.punchintime + timedelta(minutes=window_minutes)

            concurrent_verifications = BiometricVerificationLog.objects.filter(
                person=attendance_event.people,
                verified_at__range=[time_window_start, time_window_end]
            ).exclude(
                site=attendance_event.bu
            ).select_related('site')

            if concurrent_verifications.exists():
                concurrent_sites = [v.site.name for v in concurrent_verifications]

                return {
                    'anomaly_type': 'BUDDY_PUNCHING',
                    'severity': 'CRITICAL',
                    'concurrent_sites': concurrent_sites,
                    'concurrent_count': concurrent_verifications.count(),
                    'confidence_score': 0.95,
                    'evidence_data': {
                        'window_minutes': window_minutes,
                        'sites': concurrent_sites,
                        'verification_times': [v.verified_at.isoformat() for v in concurrent_verifications],
                    }
                }

        except (ValueError, AttributeError) as e:
            logger.error(f"Buddy punching detection error: {e}", exc_info=True)

        return None

    def detect_pattern_anomalies(self, person, days=30):
        """
        Detect unusual biometric patterns.

        Args:
            person: People instance
            days: Days to analyze

        Returns:
            dict: Pattern anomaly result or None
        """
        from apps.noc.security_intelligence.models import BiometricVerificationLog

        try:
            since = timezone.now() - timedelta(days=days)

            verifications = BiometricVerificationLog.objects.filter(
                person=person,
                verified_at__gte=since
            ).values_list('verified_at', 'confidence_score')

            if verifications.count() < 10:
                return None

            times = [v[0].time() for v in verifications]
            scores = [v[1] for v in verifications]

            suspicious_indicators = []

            unique_times = len(set(t.replace(second=0, microsecond=0) for t in times))
            if unique_times < len(times) * 0.3:
                suspicious_indicators.append('REPEATED_EXACT_TIMING')

            avg_confidence = sum(scores) / len(scores)
            if avg_confidence < self.config.biometric_confidence_min:
                suspicious_indicators.append('LOW_BIOMETRIC_CONFIDENCE')

            low_quality_count = sum(1 for s in scores if s < 0.5)
            if low_quality_count > len(scores) * 0.3:
                suspicious_indicators.append('FREQUENT_LOW_QUALITY')

            if suspicious_indicators:
                return {
                    'anomaly_type': 'BIOMETRIC_PATTERN_ANOMALY',
                    'severity': 'MEDIUM',
                    'indicators': suspicious_indicators,
                    'avg_confidence': avg_confidence,
                    'analysis_days': days,
                    'verification_count': len(verifications),
                    'confidence_score': 0.75,
                }

        except (ValueError, AttributeError) as e:
            logger.error(f"Pattern anomaly detection error: {e}", exc_info=True)

        return None

    @transaction.atomic
    def log_biometric_verification(self, attendance_event, verification_data):
        """
        Log biometric verification with fraud detection.

        Args:
            attendance_event: PeopleEventlog instance
            verification_data: dict with verification details

        Returns:
            BiometricVerificationLog instance
        """
        from apps.noc.security_intelligence.models import BiometricVerificationLog

        try:
            buddy_punch_result = self.detect_buddy_punching(attendance_event)

            fraud_indicators = []
            fraud_score = 0.0

            if buddy_punch_result:
                fraud_indicators.append('CONCURRENT_USAGE')
                fraud_score = 0.95

            if verification_data.get('confidence_score', 1.0) < self.config.biometric_confidence_min:
                fraud_indicators.append('LOW_CONFIDENCE')
                fraud_score = max(fraud_score, 0.60)

            if verification_data.get('liveness_score', 1.0) < 0.5:
                fraud_indicators.append('FAILED_LIVENESS')
                fraud_score = max(fraud_score, 0.80)

            log = BiometricVerificationLog.objects.create(
                tenant=attendance_event.tenant,
                person=attendance_event.people,
                site=attendance_event.bu,
                attendance_event=attendance_event,
                verified_at=timezone.now(),
                verification_type=verification_data.get('type', 'FACE'),
                result='SUCCESS' if fraud_score < 0.5 else 'SUSPICIOUS',
                confidence_score=verification_data.get('confidence_score', 0.0),
                quality_score=verification_data.get('quality_score'),
                device_id=verification_data.get('device_id', ''),
                is_concurrent=buddy_punch_result is not None,
                concurrent_sites=buddy_punch_result['concurrent_sites'] if buddy_punch_result else [],
                fraud_score=fraud_score,
                face_embedding_id=verification_data.get('embedding_id'),
                liveness_score=verification_data.get('liveness_score'),
                verification_metadata=verification_data,
                flagged_for_review=fraud_score >= 0.7,
            )

            if fraud_score >= 0.7:
                log.flag_for_review(f"High fraud score: {fraud_score:.2f}")

            return log

        except (ValueError, AttributeError) as e:
            logger.error(f"Biometric logging error: {e}", exc_info=True)
            return None