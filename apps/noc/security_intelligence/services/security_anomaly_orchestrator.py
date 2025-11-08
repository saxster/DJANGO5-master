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
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


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

            # Predictive ML fraud detection
            from apps.noc.security_intelligence.ml.predictive_fraud_detector import PredictiveFraudDetector

            ml_prediction_result = None
            if config and getattr(config, 'predictive_fraud_enabled', True):
                try:
                    person = attendance_event.people
                    site = attendance_event.bu
                    ml_prediction_result = PredictiveFraudDetector.predict_attendance_fraud(
                        person=person,
                        site=site,
                        scheduled_time=attendance_event.punchintime
                    )

                    # Log prediction for feedback loop
                    PredictiveFraudDetector.log_prediction(
                        person=person,
                        site=site,
                        scheduled_time=attendance_event.punchintime,
                        prediction_result=ml_prediction_result
                    )

                    # Log with confidence interval info if available
                    interval_info = ""
                    if 'confidence_interval_width' in ml_prediction_result:
                        interval_info = f", CI width: {ml_prediction_result['confidence_interval_width']:.3f}"

                    logger.info(
                        f"ML fraud prediction for {person.peoplename}: "
                        f"{ml_prediction_result['fraud_probability']:.2%} "
                        f"({ml_prediction_result['risk_level']}){interval_info}"
                    )

                    # Confidence-aware escalation (Phase 1)
                    # High-risk predictions with narrow intervals → auto-ticket
                    # High-risk predictions with wide intervals → alert for human review
                    if ml_prediction_result['risk_level'] in ['HIGH', 'CRITICAL']:
                        is_narrow = ml_prediction_result.get('is_narrow_interval', False)

                        if is_narrow:
                            # High confidence: Create ticket for immediate action
                            cls._create_ml_fraud_ticket(
                                attendance_event=attendance_event,
                                prediction=ml_prediction_result,
                                config=config
                            )
                        else:
                            # Low confidence: Create alert for human review
                            cls._create_ml_prediction_alert(
                                attendance_event=attendance_event,
                                prediction=ml_prediction_result,
                                config=config
                            )

                except DATABASE_EXCEPTIONS as e:
                    logger.warning(f"ML prediction failed for {attendance_event.people.peoplename}: {e}")
                    # Continue with heuristic fraud detection

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

                    # Real-time WebSocket broadcast (Gap #11)
                    from apps.noc.services.websocket_service import NOCWebSocketService
                    NOCWebSocketService.broadcast_anomaly(log)

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
        from django.conf import settings
        from datetime import timedelta

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

            # Auto-create ticket for high fraud scores (Gap #9)
            fraud_score = fraud_score_result['fraud_score']
            fraud_threshold = settings.NOC_CONFIG.get('FRAUD_SCORE_TICKET_THRESHOLD', 0.80)

            if fraud_score >= fraud_threshold:
                cls._create_fraud_ticket(
                    attendance_event=attendance_event,
                    fraud_score_result=fraud_score_result,
                    alert=alert
                )

            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"Fraud alert creation error: {e}", exc_info=True)
            return None

    @classmethod
    def _create_fraud_ticket(cls, attendance_event, fraud_score_result, alert):
        """
        Create ticket for high fraud score detections.

        Args:
            attendance_event: PeopleEventlog instance
            fraud_score_result: dict from FraudScoreCalculator
            alert: NOCAlertEvent instance

        Returns:
            Ticket instance or None
        """
        from apps.y_helpdesk.models import Ticket
        from django.conf import settings
        from datetime import timedelta

        try:
            person = attendance_event.people
            site = attendance_event.bu
            fraud_score = fraud_score_result['fraud_score']
            fraud_types = fraud_score_result['fraud_types']
            evidence = fraud_score_result['evidence']

            # Deduplication check (max 1 ticket per person per 24h per fraud type)
            dedup_hours = settings.NOC_CONFIG.get('FRAUD_DEDUPLICATION_HOURS', 24)
            recent_cutoff = timezone.now() - timedelta(hours=dedup_hours)
            fraud_type = fraud_types[0] if fraud_types else 'UNKNOWN'

            # Check for existing fraud tickets in deduplication window
            from django.db.models import Q
            existing_ticket = Ticket.objects.filter(
                Q(ticketdesc__icontains=person.peoplename) & Q(ticketdesc__icontains='FRAUD ALERT'),
                assignedtopeople__isnull=False,  # Only check assigned tickets
                bu=site,
                status__in=['NEW', 'OPEN', 'ASSIGNED', 'IN_PROGRESS'],
                cdtz__gte=recent_cutoff
            ).first()

            if existing_ticket:
                # Get workflow to check metadata
                workflow = existing_ticket.get_or_create_workflow()
                workflow_fraud_type = workflow.workflow_data.get('fraud_type')

                if workflow_fraud_type == fraud_type:
                    logger.info(
                        f"Skipping duplicate fraud ticket for {person.peoplename} "
                        f"(type: {fraud_type}, existing: {existing_ticket.id})"
                    )
                    return None

            # Determine assigned_to
            assigned_to = None
            if hasattr(site, 'security_manager') and site.security_manager:
                assigned_to = site.security_manager
            elif hasattr(site, 'site_manager') and site.site_manager:
                assigned_to = site.site_manager

            # Format detection reasons
            detection_reasons = []
            if 'buddy_punching' in evidence:
                detection_reasons.append('Buddy Punching')
            if 'gps_spoofing' in evidence:
                detection_reasons.append('GPS Spoofing')
            if 'geofence_violation' in evidence:
                detection_reasons.append('Geofence Violation')

            # Create ticket
            ticket = Ticket.objects.create(
                ticketdesc=f"[FRAUD ALERT] {person.peoplename} - {fraud_type}\n\n"
                          f"High Fraud Probability Detected\n\n"
                          f"Fraud Score: {fraud_score:.2%}\n"
                          f"Detection Methods: {', '.join(detection_reasons)}\n\n"
                          f"Evidence:\n{evidence}",
                assignedtopeople=assigned_to,
                identifier=Ticket.Identifier.TICKET,
                client=site.get_client_parent() if hasattr(site, 'get_client_parent') else None,
                bu=site,
                priority=Ticket.Priority.HIGH,
                status=Ticket.Status.NEW,
                ticketsource=Ticket.TicketSource.SYSTEMGENERATED,
                tenant=attendance_event.tenant,
                cuser=assigned_to,
                muser=assigned_to,
            )

            # Add metadata to workflow
            workflow = ticket.get_or_create_workflow()
            workflow.workflow_data.update({
                'alert_id': str(alert.id) if alert else None,
                'fraud_score': fraud_score,
                'fraud_type': fraud_type,
                'fraud_types': fraud_types,
                'auto_created': True,
                'created_by': 'SecurityAnomalyOrchestrator',
                'person_id': person.id,
                'person_name': person.peoplename,
                'attendance_event_id': attendance_event.id,
                'evidence': evidence,
            })
            workflow.save(update_fields=['workflow_data'])

            logger.info(
                f"Auto-created fraud ticket {ticket.id} for {person.peoplename} "
                f"(score: {fraud_score:.2%}, type: {fraud_type})"
            )
            return ticket

        except (ValueError, AttributeError) as e:
            logger.error(f"Fraud ticket creation error: {e}", exc_info=True)
            return None

    @classmethod
    @transaction.atomic
    def _create_ml_prediction_alert(cls, attendance_event, prediction, config):
        """
        Create alert for high ML fraud prediction.

        Args:
            attendance_event: PeopleEventlog instance
            prediction: dict from PredictiveFraudDetector
            config: SecurityAnomalyConfig instance

        Returns:
            NOCAlertEvent instance or None
        """
        from apps.noc.services import AlertCorrelationService

        try:
            fraud_probability = prediction['fraud_probability']
            risk_level = prediction['risk_level']

            alert_data = {
                'tenant': attendance_event.tenant,
                'client': attendance_event.bu.get_client_parent(),
                'bu': attendance_event.bu,
                'alert_type': 'ML_FRAUD_PREDICTION',
                'severity': 'HIGH' if risk_level == 'HIGH' else 'CRITICAL',
                'message': f"ML model predicts {fraud_probability:.1%} fraud probability for {attendance_event.people.peoplename}",
                'entity_type': 'attendance_prediction',
                'entity_id': attendance_event.id,
                'metadata': {
                    'ml_prediction': prediction,
                    'model_version': prediction.get('model_version'),
                    'features': prediction.get('features', {}),
                    'person_id': attendance_event.people.id,
                    'person_name': attendance_event.people.peoplename,
                    'prediction_method': prediction.get('prediction_method'),
                    'behavioral_risk': prediction.get('behavioral_risk', 0.0),
                }
            }

            alert = AlertCorrelationService.process_alert(alert_data)
            logger.info(f"Created ML prediction alert {alert.id} for {attendance_event.people.peoplename}")
            return alert

        except (ValueError, AttributeError) as e:
            logger.error(f"ML prediction alert creation error: {e}", exc_info=True)
            return None

    @classmethod
    @transaction.atomic
    def _create_ml_fraud_ticket(cls, attendance_event, prediction, config):
        """
        Create ticket for high-confidence ML fraud predictions (Phase 1).

        Only called for HIGH/CRITICAL risk with narrow confidence intervals.
        Enables human-out-of-loop automation with high certainty.

        Args:
            attendance_event: PeopleEventlog instance
            prediction: dict from PredictiveFraudDetector with confidence intervals
            config: SecurityAnomalyConfig instance

        Returns:
            Ticket instance or None
        """
        from apps.y_helpdesk.models import Ticket
        from django.conf import settings
        from datetime import timedelta

        try:
            person = attendance_event.people
            site = attendance_event.bu
            fraud_probability = prediction['fraud_probability']
            risk_level = prediction['risk_level']

            # Deduplication: max 1 ML fraud ticket per person per 24h
            dedup_hours = settings.NOC_CONFIG.get('FRAUD_DEDUPLICATION_HOURS', 24)
            recent_cutoff = timezone.now() - timedelta(hours=dedup_hours)

            from django.db.models import Q
            existing_ticket = Ticket.objects.filter(
                tenant=person.tenant,
                people=person,
                created__gte=recent_cutoff,
                workflow_data__created_by='MLFraudDetector',
                status__in=[Ticket.Status.NEW, Ticket.Status.PENDINGACTION]
            ).first()

            if existing_ticket:
                logger.info(
                    f"Skipping ML fraud ticket for {person.peoplename} "
                    f"- existing ticket #{existing_ticket.id} within {dedup_hours}h window"
                )
                return None

            # Ticket assignment logic
            assigned_to = None
            # Try to assign to site security manager
            if site and hasattr(site, 'securitymanager') and site.securitymanager:
                assigned_to = site.securitymanager
            # Fallback to site manager
            elif site and hasattr(site, 'sitesupervisor') and site.sitesupervisor:
                assigned_to = site.sitesupervisor

            # Create ticket
            ticket = Ticket.objects.create(
                tenant=person.tenant,
                client=site.get_client_parent() if site else None,
                site=site,
                people=person,
                subject=f"High-Confidence ML Fraud Prediction: {person.peoplename}",
                description=(
                    f"ML model detected high fraud probability ({fraud_probability:.1%}) "
                    f"with high confidence (narrow prediction interval).\n\n"
                    f"Risk Level: {risk_level}\n"
                    f"Model Version: {prediction.get('model_version')}\n"
                    f"Confidence Interval: [{prediction.get('prediction_lower_bound', 'N/A'):.3f}, "
                    f"{prediction.get('prediction_upper_bound', 'N/A'):.3f}]\n"
                    f"Interval Width: {prediction.get('confidence_interval_width', 'N/A'):.3f}\n\n"
                    f"This ticket was auto-created due to high prediction confidence. "
                    f"Please investigate the attendance event and take appropriate action."
                ),
                status=Ticket.Status.NEW,
                priority=Ticket.Priority.HIGH,
                source=Ticket.TicketSource.SYSTEMGENERATED,
                assigned_to=assigned_to,
                workflow_id='ml_fraud_investigation',
            )

            # Store workflow metadata
            workflow = ticket.workflow_data_model or ticket
            workflow.workflow_data.update({
                'auto_created': True,
                'created_by': 'MLFraudDetector',
                'prediction': {
                    'fraud_probability': fraud_probability,
                    'risk_level': risk_level,
                    'confidence_interval_width': prediction.get('confidence_interval_width'),
                    'model_version': prediction.get('model_version'),
                    'is_narrow_interval': prediction.get('is_narrow_interval'),
                },
                'person_id': person.id,
                'person_name': person.peoplename,
                'attendance_event_id': attendance_event.id,
                'site_id': site.id if site else None,
                'features': prediction.get('features', {}),
            })
            workflow.save(update_fields=['workflow_data'])

            logger.info(
                f"Auto-created ML fraud ticket {ticket.id} for {person.peoplename} "
                f"(probability: {fraud_probability:.2%}, CI width: {prediction.get('confidence_interval_width', 0):.3f})"
            )
            return ticket

        except (ValueError, AttributeError) as e:
            logger.error(f"ML fraud ticket creation error: {e}", exc_info=True)
            return None