"""
Security Anomaly Orchestrator Service.

Coordinates all anomaly detection services and integrates with NOC alert system.
Main entry point for security intelligence module.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('noc.security_intelligence')


class SecurityAnomalyOrchestrator:
    """Orchestrates security anomaly detection and alerting."""

    @classmethod
    def process_attendance_event(cls, attendance_event):
        """
        Process attendance event for all security anomalies.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Created logs (anomalies, biometric, gps)
        """
        from apps.noc.security_intelligence.models import SecurityAnomalyConfig
        from apps.noc.security_intelligence.services import (
            AttendanceAnomalyDetector,
            BiometricFraudDetector,
            LocationFraudDetector,
            FraudScoreCalculator,
        )

        try:
            config = SecurityAnomalyConfig.get_config_for_site(
                tenant=attendance_event.tenant,
                site=attendance_event.bu
            )

            if not config or not config.is_active:
                return {'anomalies': [], 'biometric_logs': [], 'gps_logs': []}

            attendance_detector = AttendanceAnomalyDetector(config)
            biometric_detector = BiometricFraudDetector(config)
            location_detector = LocationFraudDetector(config)

            results = {'anomalies': [], 'biometric_logs': [], 'gps_logs': []}

            anomaly_checks = [
                attendance_detector.detect_wrong_person(attendance_event),
                attendance_detector.detect_unauthorized_site_access(attendance_event),
                attendance_detector.detect_impossible_back_to_back(attendance_event),
                attendance_detector.detect_overtime_violation(attendance_event),
            ]

            for anomaly in filter(None, anomaly_checks):
                log = cls._create_anomaly_log(attendance_event, anomaly, config)
                if log:
                    results['anomalies'].append(log)
                    cls._create_noc_alert(log, config)

            fraud_checks = {
                'buddy_punching': biometric_detector.detect_buddy_punching(attendance_event),
                'gps_spoofing': location_detector.detect_gps_spoofing(attendance_event),
                'geofence_violation': location_detector.detect_geofence_violation(attendance_event),
            }

            fraud_score_result = FraudScoreCalculator.calculate_fraud_score(fraud_checks)

            if fraud_score_result['fraud_score'] >= 0.5:
                cls._create_fraud_alert(attendance_event, fraud_score_result, config)

            return results

        except (ValueError, AttributeError) as e:
            logger.error(f"Attendance processing error: {e}", exc_info=True)
            return {'anomalies': [], 'biometric_logs': [], 'gps_logs': []}

    @classmethod
    @transaction.atomic
    def _create_anomaly_log(cls, attendance_event, anomaly_data, config):
        """
        Create attendance anomaly log entry.

        Args:
            attendance_event: PeopleEventlog instance
            anomaly_data: dict with anomaly details
            config: SecurityAnomalyConfig instance

        Returns:
            AttendanceAnomalyLog instance
        """
        from apps.noc.security_intelligence.models import AttendanceAnomalyLog

        try:
            log = AttendanceAnomalyLog.objects.create(
                tenant=attendance_event.tenant,
                anomaly_type=anomaly_data['anomaly_type'],
                severity=anomaly_data.get('severity', 'MEDIUM'),
                person=attendance_event.people,
                site=attendance_event.bu,
                attendance_event=attendance_event,
                detected_at=timezone.now(),
                confidence_score=anomaly_data.get('confidence_score', 0.8),
                expected_person=anomaly_data.get('expected_person'),
                distance_km=anomaly_data.get('distance_km'),
                time_available_minutes=anomaly_data.get('time_available_minutes'),
                time_required_minutes=anomaly_data.get('time_required_minutes'),
                continuous_work_hours=anomaly_data.get('continuous_work_hours'),
                evidence_data=anomaly_data.get('evidence_data', {}),
            )

            logger.info(f"Created anomaly log: {log}")
            return log

        except (ValueError, AttributeError) as e:
            logger.error(f"Anomaly log creation error: {e}", exc_info=True)
            return None

    @classmethod
    def _create_noc_alert(cls, anomaly_log, config):
        """
        Create NOC alert for anomaly.

        Args:
            anomaly_log: AttendanceAnomalyLog instance
            config: SecurityAnomalyConfig instance

        Returns:
            NOCAlertEvent instance or None
        """
        from apps.noc.services import AlertCorrelationService

        try:
            alert_data = {
                'tenant': anomaly_log.tenant,
                'client': anomaly_log.site.get_client_parent(),
                'bu': anomaly_log.site,
                'alert_type': 'SECURITY_ANOMALY',
                'severity': anomaly_log.severity,
                'message': cls._generate_alert_message(anomaly_log),
                'entity_type': 'attendance_anomaly',
                'entity_id': anomaly_log.id,
                'metadata': {
                    'anomaly_type': anomaly_log.anomaly_type,
                    'person_id': anomaly_log.person.id,
                    'person_name': anomaly_log.person.peoplename,
                    'confidence_score': anomaly_log.confidence_score,
                    'evidence': anomaly_log.evidence_data,
                }
            }

            alert = AlertCorrelationService.process_alert(alert_data)

            anomaly_log.noc_alert = alert
            anomaly_log.save(update_fields=['noc_alert'])

            logger.info(f"Created NOC alert: {alert}")
            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"NOC alert creation error: {e}", exc_info=True)
            return None

    @staticmethod
    def _generate_alert_message(anomaly_log):
        """Generate human-readable alert message."""
        messages = {
            'WRONG_PERSON': f"{anomaly_log.person.peoplename} marked attendance but {anomaly_log.expected_person.peoplename} was scheduled",
            'UNAUTHORIZED_SITE': f"{anomaly_log.person.peoplename} accessed unauthorized site {anomaly_log.site.name}",
            'IMPOSSIBLE_SHIFTS': f"{anomaly_log.person.peoplename} has impossible back-to-back shifts ({anomaly_log.distance_km:.1f}km in {anomaly_log.time_available_minutes:.0f}min)",
            'OVERTIME_VIOLATION': f"{anomaly_log.person.peoplename} worked {anomaly_log.continuous_work_hours:.1f} hours continuously",
        }

        return messages.get(
            anomaly_log.anomaly_type,
            f"Security anomaly detected for {anomaly_log.person.peoplename}"
        )

    @classmethod
    @transaction.atomic
    def _create_fraud_alert(cls, attendance_event, fraud_score_result, config):
        """
        Create consolidated fraud alert.

        Args:
            attendance_event: PeopleEventlog instance
            fraud_score_result: dict from FraudScoreCalculator
            config: SecurityAnomalyConfig instance

        Returns:
            NOCAlertEvent instance
        """
        from apps.noc.services import AlertCorrelationService

        try:
            fraud_types_str = ', '.join(fraud_score_result['fraud_types'])

            alert_data = {
                'tenant': attendance_event.tenant,
                'client': attendance_event.bu.get_client_parent(),
                'bu': attendance_event.bu,
                'alert_type': 'SECURITY_ANOMALY',
                'severity': fraud_score_result['risk_level'],
                'message': f"Fraud detected: {fraud_types_str} (score: {fraud_score_result['fraud_score']:.2f})",
                'entity_type': 'attendance_fraud',
                'entity_id': attendance_event.id,
                'metadata': {
                    'fraud_score': fraud_score_result['fraud_score'],
                    'risk_level': fraud_score_result['risk_level'],
                    'fraud_types': fraud_score_result['fraud_types'],
                    'evidence': fraud_score_result['evidence'],
                    'person_id': attendance_event.people.id,
                    'person_name': attendance_event.people.peoplename,
                }
            }

            alert = AlertCorrelationService.process_alert(alert_data)
            logger.info(f"Created fraud alert: {alert}")
            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"Fraud alert creation error: {e}", exc_info=True)
            return None