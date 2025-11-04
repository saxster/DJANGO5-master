"""
Predictive Alerting Service.

Unified service for proactive incident prevention through ML predictions.
Part of Enhancement #5: Predictive Alerting Engine from NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md.

Orchestrates 3 predictors:
- SLA Breach (2-hour window)
- Device Failure (1-hour window)
- Staffing Gap (4-hour window)

Target: 40-60% incident prevention rate.

Follows .claude/rules.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management

@ontology(
    domain="noc",
    purpose="Unified predictive alerting service for proactive incident prevention",
    predictors=["SLABreachPredictor", "DeviceFailurePredictor", "StaffingGapPredictor"],
    prevention_target="40-60% incident prevention rate",
    criticality="critical",
    integration_points=["AlertCorrelationService", "WebSocket broadcast", "NOC dashboard"],
    tags=["noc", "ml", "predictive-analytics", "proactive-prevention"]
)
"""

import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import timedelta
from django.db import transaction, DatabaseError
from django.utils import timezone
from apps.core.utils_new.db_utils import get_current_db_name
from ..models import NOCAlertEvent, PredictiveAlertTracking
from ..ml.predictive_models.sla_breach_predictor import SLABreachPredictor
from ..ml.predictive_models.device_failure_predictor import DeviceFailurePredictor
from ..ml.predictive_models.staffing_gap_predictor import StaffingGapPredictor

logger = logging.getLogger('noc.predictive_alerting')

__all__ = ['PredictiveAlertingService']


class PredictiveAlertingService:
    """
    Unified service for predictive alerting.

    Creates proactive alerts based on ML predictions to prevent:
    - SLA breaches (2 hours advance)
    - Device failures (1 hour advance)
    - Staffing gaps (4 hours advance)
    """

    # Alert type mappings
    ALERT_TYPE_MAP = {
        'sla_breach': 'PREDICTIVE_SLA_BREACH',
        'device_failure': 'PREDICTIVE_DEVICE_FAILURE',
        'staffing_gap': 'PREDICTIVE_STAFFING_GAP',
    }

    # Severity thresholds based on confidence
    SEVERITY_THRESHOLDS = {
        'CRITICAL': 0.9,   # >90% confidence
        'HIGH': 0.75,      # 75-90% confidence
        'MEDIUM': 0.6,     # 60-75% confidence
    }

    @classmethod
    def predict_sla_breaches(cls, tenant) -> List[PredictiveAlertTracking]:
        """
        Scan all open tickets and predict SLA breaches.

        Args:
            tenant: Tenant instance

        Returns:
            List of predictions created
        """
        from apps.y_helpdesk.models import Ticket

        predictions = []

        # Get all open tickets with SLA policies
        open_tickets = Ticket.objects.filter(
            tenant=tenant,
            status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS'],
            sla_policy__isnull=False
        ).select_related('sla_policy', 'bu', 'client')

        logger.info(f"Scanning {open_tickets.count()} tickets for SLA breach prediction")

        for ticket in open_tickets:
            try:
                probability, features = SLABreachPredictor.predict_breach(ticket)

                if SLABreachPredictor.should_alert(probability):
                    prediction = cls.create_predictive_alert(
                        prediction_type='sla_breach',
                        entity_type='ticket',
                        entity=ticket,
                        probability=probability,
                        features=features,
                        validation_hours=2
                    )
                    predictions.append(prediction)

            except (ValueError, DatabaseError) as e:
                logger.error(f"Error predicting SLA breach for ticket {ticket.id}: {e}")

        logger.info(f"Created {len(predictions)} SLA breach predictions")
        return predictions

    @classmethod
    def predict_device_failures(cls, tenant) -> List[PredictiveAlertTracking]:
        """
        Scan all devices and predict failures.

        Args:
            tenant: Tenant instance

        Returns:
            List of predictions created
        """
        from apps.monitoring.models import Device

        predictions = []

        # Get all active devices
        try:
            devices = Device.objects.filter(
                tenant=tenant,
                is_active=True
            ).select_related('site', 'client')

            logger.info(f"Scanning {devices.count()} devices for failure prediction")

            for device in devices:
                try:
                    probability, features = DeviceFailurePredictor.predict_failure(device)

                    if DeviceFailurePredictor.should_alert(probability):
                        prediction = cls.create_predictive_alert(
                            prediction_type='device_failure',
                            entity_type='device',
                            entity=device,
                            probability=probability,
                            features=features,
                            validation_hours=1
                        )
                        predictions.append(prediction)

                except ValueError as e:
                    logger.error(f"Error predicting device failure for device {device.id}: {e}")

        except Exception as e:
            logger.warning(f"Device model not available or error accessing: {e}")

        logger.info(f"Created {len(predictions)} device failure predictions")
        return predictions

    @classmethod
    def predict_staffing_gaps(cls, tenant) -> List[PredictiveAlertTracking]:
        """
        Scan next 4 hours of shifts and predict staffing gaps.

        Args:
            tenant: Tenant instance

        Returns:
            List of predictions created
        """
        from apps.scheduler.models import Schedule
        from apps.client_onboarding.models import Bt

        predictions = []

        now = timezone.now()
        four_hours_ahead = now + timedelta(hours=4)

        # Get all sites with shifts in next 4 hours
        try:
            upcoming_shifts = Schedule.objects.filter(
                tenant=tenant,
                start_time__gte=now,
                start_time__lte=four_hours_ahead
            ).values('bu').distinct()

            sites = Bt.objects.filter(
                id__in=[s['bu'] for s in upcoming_shifts]
            )

            logger.info(f"Scanning {sites.count()} sites for staffing gap prediction")

            for site in sites:
                # Get shifts for this site
                site_shifts = Schedule.objects.filter(
                    bu=site,
                    start_time__gte=now,
                    start_time__lte=four_hours_ahead
                ).order_by('start_time')

                for shift in site_shifts[:5]:  # Limit to next 5 shifts per site
                    try:
                        probability, features = StaffingGapPredictor.predict_gap(site, shift.start_time)

                        if StaffingGapPredictor.should_alert(probability):
                            prediction = cls.create_predictive_alert(
                                prediction_type='staffing_gap',
                                entity_type='shift',
                                entity=shift,
                                probability=probability,
                                features=features,
                                validation_hours=4
                            )
                            predictions.append(prediction)

                    except ValueError as e:
                        logger.error(f"Error predicting staffing gap for shift {shift.id}: {e}")

        except Exception as e:
            logger.warning(f"Schedule model not available or error accessing: {e}")

        logger.info(f"Created {len(predictions)} staffing gap predictions")
        return predictions

    @classmethod
    def create_predictive_alert(
        cls,
        prediction_type: str,
        entity_type: str,
        entity: Any,
        probability: float,
        features: Dict[str, Any],
        validation_hours: int
    ) -> PredictiveAlertTracking:
        """
        Create predictive alert and tracking record.

        Args:
            prediction_type: sla_breach, device_failure, or staffing_gap
            entity_type: ticket, device, shift, etc.
            entity: Entity instance
            probability: Prediction probability 0.0-1.0
            features: Feature values used for prediction
            validation_hours: Hours until validation deadline

        Returns:
            PredictiveAlertTracking instance
        """
        try:
            with transaction.atomic(using=get_current_db_name()):
                # Determine severity based on probability
                severity = cls._calculate_severity(probability)

                # Determine confidence bucket
                confidence_bucket = cls._get_confidence_bucket(probability)

                # Create alert event
                alert_data = {
                    'tenant': entity.tenant,
                    'client': getattr(entity, 'client', None),
                    'bu': getattr(entity, 'bu', None) or getattr(entity, 'site', None),
                    'alert_type': cls.ALERT_TYPE_MAP[prediction_type],
                    'severity': severity,
                    'message': cls._generate_alert_message(prediction_type, entity, probability, features),
                    'entity_type': entity_type,
                    'entity_id': entity.id,
                    'metadata': {
                        'prediction_type': prediction_type,
                        'probability': probability,
                        'features': features,
                        'is_predictive': True,
                    }
                }

                # Use existing AlertCorrelationService to create alert with deduplication
                from .correlation_service import AlertCorrelationService
                alert = AlertCorrelationService.process_alert(alert_data)

                if not alert:  # Alert was suppressed
                    return None

                # Create tracking record
                prediction = PredictiveAlertTracking.objects.create(
                    prediction_type=prediction_type,
                    tenant=entity.tenant,
                    predicted_probability=probability,
                    entity_type=entity_type,
                    entity_id=entity.id,
                    entity_metadata=cls._snapshot_entity(entity),
                    feature_values=features,
                    validation_deadline=timezone.now() + timedelta(hours=validation_hours),
                    confidence_bucket=confidence_bucket,
                    alert=alert
                )

                logger.info(
                    f"Created predictive alert: {prediction_type} for {entity_type}:{entity.id} "
                    f"(probability={probability:.2f}, severity={severity})"
                )

                return prediction

        except DatabaseError as e:
            logger.error(f"Error creating predictive alert: {e}", exc_info=True)
            raise

    @classmethod
    def validate_prediction_outcome(cls, prediction_id: uuid.UUID, actual_outcome: bool, preventive_action_taken: bool = False) -> None:
        """
        Validate prediction outcome for accuracy tracking.

        Args:
            prediction_id: Prediction UUID
            actual_outcome: Whether predicted event actually occurred
            preventive_action_taken: Whether preventive action was taken

        Raises:
            PredictiveAlertTracking.DoesNotExist: If prediction not found
        """
        try:
            prediction = PredictiveAlertTracking.objects.get(prediction_id=prediction_id)
            prediction.validate_outcome(actual_outcome, preventive_action_taken)

            logger.info(
                f"Validated prediction {prediction_id}: outcome={actual_outcome}, "
                f"correct={prediction.prediction_correct}, preventive_action={preventive_action_taken}"
            )

        except PredictiveAlertTracking.DoesNotExist:
            logger.error(f"Prediction {prediction_id} not found for validation")
            raise

    @classmethod
    def _calculate_severity(cls, probability: float) -> str:
        """Calculate alert severity based on prediction probability."""
        if probability >= cls.SEVERITY_THRESHOLDS['CRITICAL']:
            return 'CRITICAL'
        elif probability >= cls.SEVERITY_THRESHOLDS['HIGH']:
            return 'HIGH'
        else:
            return 'MEDIUM'

    @classmethod
    def _get_confidence_bucket(cls, probability: float) -> str:
        """Get confidence bucket for probability."""
        if probability >= 0.9:
            return 'very_high'
        elif probability >= 0.75:
            return 'high'
        elif probability >= 0.6:
            return 'medium'
        else:
            return 'low'

    @classmethod
    def _generate_alert_message(cls, prediction_type: str, entity: Any, probability: float, features: Dict) -> str:
        """Generate human-readable alert message."""
        messages = {
            'sla_breach': f"PREDICTIVE: Ticket #{entity.ticketno} likely to breach SLA in 2 hours ({probability:.0%} confidence)",
            'device_failure': f"PREDICTIVE: Device {entity.device_id} likely to go offline in 1 hour ({probability:.0%} confidence)",
            'staffing_gap': f"PREDICTIVE: Site {entity.bu.buname if hasattr(entity, 'bu') else 'Unknown'} likely understaffed in 4 hours ({probability:.0%} confidence)",
        }
        return messages.get(prediction_type, f"Predictive alert: {prediction_type} ({probability:.0%})")

    @classmethod
    def _snapshot_entity(cls, entity: Any) -> Dict[str, Any]:
        """Create snapshot of entity state for debugging."""
        snapshot = {
            'id': entity.id,
            'type': entity.__class__.__name__,
            'snapshot_time': timezone.now().isoformat(),
        }

        # Add relevant fields based on entity type
        if hasattr(entity, 'status'):
            snapshot['status'] = entity.status
        if hasattr(entity, 'priority'):
            snapshot['priority'] = entity.priority
        if hasattr(entity, 'assignee_id'):
            snapshot['assignee_id'] = entity.assignee_id

        return snapshot
