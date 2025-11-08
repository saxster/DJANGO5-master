"""
Security Intelligence Background Tasks.

Periodic monitoring tasks for activity detection.
Uses PostgreSQL task queue system.

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from apps.core.exceptions.patterns import FILE_EXCEPTIONS


logger = logging.getLogger('noc.security_intelligence')


def monitor_night_shift_activity():
    """
    Monitor night shift guard activity (runs every 5 minutes).

    Checks all active night shifts for inactivity.
    Creates alerts for guards with high inactivity scores.
    """
    from apps.noc.security_intelligence.models import (
        SecurityAnomalyConfig,
        GuardActivityTracking,
    )
    from apps.noc.security_intelligence.services import (
        ActivityMonitorService,
        ActivitySignalCollector,
    )
    from apps.noc.services import AlertCorrelationService

    try:
        now = timezone.now()
        hour = now.hour

        if not (20 <= hour or hour <= 6):
            logger.debug("Not night shift hours, skipping activity monitoring")
            return

        active_configs = SecurityAnomalyConfig.objects.filter(
            is_active=True,
            inactivity_detection_enabled=True
        )

        for config in active_configs:
            _process_tenant_activity_monitoring(config)

    except (ValueError, AttributeError) as e:
        logger.error(f"Activity monitoring task error: {e}", exc_info=True)


def _process_tenant_activity_monitoring(config):
    """Process activity monitoring for a tenant."""
    from apps.noc.security_intelligence.models import GuardActivityTracking
    from apps.noc.security_intelligence.services import (
        ActivityMonitorService,
        ActivitySignalCollector,
    )
    from apps.attendance.models import PeopleEventlog

    now = timezone.now()
    window_start = now - timedelta(minutes=config.inactivity_window_minutes)

    active_shifts = PeopleEventlog.objects.filter(
        tenant=config.tenant,
        datefor=now.date(),
        punchintime__isnull=False,
        punchouttime__isnull=True,
        punchintime__gte=now - timedelta(hours=12)
    ).select_related('people', 'bu')

    logger.info(f"Monitoring {active_shifts.count()} active shifts for {config.tenant.name}")

    monitor_service = ActivityMonitorService(config)

    for shift in active_shifts:
        _monitor_guard_shift(shift, config, monitor_service, window_start, now)


@transaction.atomic
def _monitor_guard_shift(shift, config, monitor_service, window_start, now):
    """Monitor individual guard shift."""
    from apps.noc.security_intelligence.models import GuardActivityTracking
    from apps.noc.security_intelligence.services import ActivitySignalCollector

    try:
        tracking = GuardActivityTracking.objects.filter(
            tenant=shift.tenant,
            person=shift.people,
            site=shift.bu,
            tracking_start__gte=window_start,
            tracking_end__lte=now
        ).first()

        if not tracking:
            tracking = _create_tracking_window(shift, window_start, now)

        signals = ActivitySignalCollector.collect_all_signals(
            shift.people,
            shift.bu,
            config.inactivity_window_minutes
        )

        for signal_type, value in signals.items():
            setattr(tracking, signal_type, value)

        analysis = monitor_service.analyze_guard_activity(
            shift.people,
            shift.bu,
            tracking
        )

        tracking.inactivity_score = analysis['inactivity_score']
        tracking.is_inactive = analysis['is_inactive']

        if analysis['is_inactive'] and not tracking.alert_generated:
            tracking.consecutive_inactive_windows += 1

            alert = monitor_service.create_inactivity_alert(tracking, analysis)

            if alert:
                _create_noc_alert_for_inactivity(alert, config)

        tracking.save()

    except (ValueError, AttributeError) as e:
        logger.error(f"Guard monitoring error for {shift.people.peoplename}: {e}", exc_info=True)


def _create_tracking_window(shift, start_time, end_time):
    """Create new tracking window."""
    from apps.noc.security_intelligence.models import GuardActivityTracking

    hour = start_time.hour
    shift_type = 'NIGHT' if (20 <= hour or hour <= 6) else 'DAY'

    return GuardActivityTracking.objects.create(
        tenant=shift.tenant,
        person=shift.people,
        site=shift.bu,
        tracking_start=start_time,
        tracking_end=end_time,
        shift_type=shift_type
    )


def _create_noc_alert_for_inactivity(inactivity_alert, config):
    """Create NOC alert for inactivity."""
    from apps.noc.services import AlertCorrelationService

    try:
        alert_data = {
            'tenant': inactivity_alert.tenant,
            'client': inactivity_alert.site.get_client_parent(),
            'bu': inactivity_alert.site,
            'alert_type': 'SECURITY_ANOMALY',
            'severity': inactivity_alert.severity,
            'message': f"Guard {inactivity_alert.person.peoplename} inactive for {inactivity_alert.inactivity_duration_minutes} minutes (score: {inactivity_alert.inactivity_score:.2f})",
            'entity_type': 'inactivity_alert',
            'entity_id': inactivity_alert.id,
            'metadata': {
                'anomaly_subtype': 'GUARD_INACTIVITY',
                'person_id': inactivity_alert.person.id,
                'person_name': inactivity_alert.person.peoplename,
                'inactivity_score': inactivity_alert.inactivity_score,
                'is_deep_night': inactivity_alert.is_deep_night,
                'no_phone_activity': inactivity_alert.no_phone_activity,
                'no_movement': inactivity_alert.no_movement,
                'no_tasks': inactivity_alert.no_tasks_completed,
                'no_tours': inactivity_alert.no_tour_scans,
            }
        }

        noc_alert = AlertCorrelationService.process_alert(alert_data)

        inactivity_alert.noc_alert = noc_alert
        inactivity_alert.save(update_fields=['noc_alert'])

        logger.info(f"Created NOC alert for inactivity: {noc_alert}")

    except (ValueError, AttributeError) as e:
        logger.error(f"NOC alert creation error: {e}", exc_info=True)


def monitor_task_tour_compliance():
    """
    Monitor critical task and tour compliance (runs every 15 minutes).

    Checks for overdue critical tasks and missed mandatory tours.
    Creates alerts for SLA breaches.
    """
    from apps.noc.security_intelligence.models import TaskComplianceConfig
    from apps.noc.security_intelligence.services import TaskComplianceMonitor
    from apps.tenants.models import Tenant

    try:
        active_configs = TaskComplianceConfig.objects.filter(
            is_active=True
        ).select_related('tenant')

        for config in active_configs:
            _process_compliance_monitoring(config)

    except (ValueError, AttributeError) as e:
        logger.error(f"Compliance monitoring task error: {e}", exc_info=True)


def _process_compliance_monitoring(config):
    """Process compliance monitoring for a tenant."""
    from apps.noc.security_intelligence.services import TaskComplianceMonitor

    monitor = TaskComplianceMonitor(config)

    try:
        task_violations = monitor.check_critical_tasks(config.tenant, lookback_hours=1)

        for violation in task_violations:
            monitor.create_task_alert(violation)

        if task_violations:
            logger.info(f"Found {len(task_violations)} task violations for {config.tenant.name}")

        tour_violations = monitor.check_tour_compliance(config.tenant)

        for violation in tour_violations:
            monitor.create_tour_alert(violation)

        if tour_violations:
            logger.info(f"Found {len(tour_violations)} tour violations for {config.tenant.name}")

    except (ValueError, AttributeError) as e:
        logger.error(f"Compliance processing error for {config.tenant.name}: {e}", exc_info=True)


def train_ml_models_daily():
    """
    Train ML models daily (runs once per day).

    Updates behavioral profiles and trains fraud detection models.
    XGBoost models are retrained weekly (checked daily).
    """
    from apps.tenants.models import Tenant

    try:
        logger.info("Starting daily ML training cycle")

        for tenant in Tenant.objects.filter(is_active=True):
            _train_models_for_tenant(tenant)

    except (ValueError, AttributeError) as e:
        logger.error(f"ML training task error: {e}", exc_info=True)


def _train_models_for_tenant(tenant):
    """Train models for a tenant (called by train_ml_models_daily)."""
    from apps.noc.security_intelligence.ml import BehavioralProfiler
    from apps.noc.security_intelligence.ml.fraud_model_trainer import FraudModelTrainer
    from apps.noc.management.commands.train_fraud_model import Command as TrainCommand
    from apps.noc.security_intelligence.models import FraudDetectionModel
    from apps.peoples.models import People

    try:
        logger.info(f"Training models for {tenant.schema_name}")

        # Update behavioral profiles (keep existing code)
        active_guards = People.objects.filter(
            tenant=tenant,
            enable=True,
            isverified=True
        )[:100]

        profiles_updated = 0
        for guard in active_guards:
            try:
                profile = BehavioralProfiler.create_or_update_profile(guard, days=90)
                if profile:
                    profiles_updated += 1
            except FILE_EXCEPTIONS as e:
                logger.error(f"Profile update failed for {guard.peoplename}: {e}")

        logger.info(f"Updated {profiles_updated} behavioral profiles for {tenant.schema_name}")

        # XGBoost fraud model retraining (weekly check)
        active_model = FraudDetectionModel.get_active_model(tenant) if FraudDetectionModel.objects.filter(tenant=tenant).exists() else None
        should_retrain = (
            not active_model or
            (timezone.now() - active_model.activated_at).days >= 7
        )

        if should_retrain:
            logger.info(f"Triggering XGBoost retraining for {tenant.schema_name}")

            # Export training data
            export_result = FraudModelTrainer.export_training_data(tenant, days=180)

            if export_result['success'] and export_result['record_count'] >= 100:
                # Train new model via management command
                trainer = TrainCommand()
                try:
                    trainer.handle(tenant=tenant.id, days=180, test_size=0.2, verbose=False)
                    logger.info(f"✅ XGBoost training completed for {tenant.schema_name}")
                except (ValueError, TypeError, AttributeError) as e:
                    logger.error(f"❌ XGBoost training failed for {tenant.schema_name}: {e}")
            else:
                logger.warning(
                    f"Insufficient training data for {tenant.schema_name}: "
                    f"{export_result.get('record_count', 0)} records (need 100+)"
                )

    except (ValueError, AttributeError) as e:
        logger.error(f"Tenant ML training error for {tenant.schema_name}: {e}", exc_info=True)


def update_behavioral_profiles_weekly():
    """
    Update behavioral profiles weekly.

    Refreshes profiles for all active guards.
    """
    from apps.noc.security_intelligence.ml import BehavioralProfiler
    from apps.peoples.models import People
    from apps.tenants.models import Tenant

    try:
        for tenant in Tenant.objects.filter(is_active=True):
            guards = People.objects.filter(
                tenant=tenant,
                enable=True,
                isverified=True
            )

            for guard in guards[:1000]:
                BehavioralProfiler.create_or_update_profile(guard, days=90)

            logger.info(f"Updated profiles for {guards.count()} guards in {tenant.name}")

    except (ValueError, AttributeError) as e:
        logger.error(f"Profile update error: {e}", exc_info=True)


def track_fraud_prediction_outcomes():
    """
    Track fraud prediction outcomes (runs daily).

    Reviews high-risk predictions after 30 days and marks false positives.
    Updates actual fraud outcomes for model feedback loop.
    """
    from apps.noc.security_intelligence.models import FraudPredictionLog
    from apps.tenants.models import Tenant

    try:
        now = timezone.now()
        review_cutoff = now - timedelta(days=30)

        logger.info("Starting fraud prediction outcome tracking")

        for tenant in Tenant.objects.filter(is_active=True):
            _track_outcomes_for_tenant(tenant, review_cutoff)

    except (ValueError, AttributeError) as e:
        logger.error(f"Fraud outcome tracking error: {e}", exc_info=True)


@transaction.atomic
def _track_outcomes_for_tenant(tenant, review_cutoff):
    """Track fraud outcomes for a tenant."""
    from apps.noc.security_intelligence.models import (
        FraudPredictionLog,
        AttendanceAnomalyLog
    )

    try:
        # Get high-risk predictions needing review (older than 30 days, no outcome)
        pending_predictions = FraudPredictionLog.objects.filter(
            tenant=tenant,
            predicted_at__lte=review_cutoff,
            actual_fraud_detected__isnull=True,
            risk_level__in=['HIGH', 'CRITICAL']
        ).select_related('person', 'site', 'actual_attendance_event')

        marked_count = 0
        fraud_confirmed_count = 0

        for prediction in pending_predictions:
            # Check if attendance event exists
            if not prediction.actual_attendance_event:
                # No attendance occurred - mark as prevented or false positive
                prediction.actual_fraud_detected = False
                prediction.actual_fraud_score = 0.0
                prediction.prediction_accuracy = 1.0 - prediction.fraud_probability
                prediction.save(update_fields=[
                    'actual_fraud_detected',
                    'actual_fraud_score',
                    'prediction_accuracy'
                ])
                marked_count += 1
                continue

            # Check if fraud was confirmed via anomaly log
            fraud_confirmed = AttendanceAnomalyLog.objects.filter(
                attendance_event=prediction.actual_attendance_event,
                status='CONFIRMED'
            ).exists()

            if fraud_confirmed:
                prediction.actual_fraud_detected = True
                prediction.actual_fraud_score = 1.0
                fraud_confirmed_count += 1
            else:
                # No fraud report after 30 days = false positive
                prediction.actual_fraud_detected = False
                prediction.actual_fraud_score = 0.0

            # Calculate accuracy
            prediction_diff = abs(prediction.fraud_probability - prediction.actual_fraud_score)
            prediction.prediction_accuracy = 1.0 - min(prediction_diff, 1.0)

            prediction.save(update_fields=[
                'actual_fraud_detected',
                'actual_fraud_score',
                'prediction_accuracy'
            ])
            marked_count += 1

        if marked_count > 0:
            logger.info(
                f"Tenant {tenant.schema_name}: Marked {marked_count} predictions "
                f"({fraud_confirmed_count} confirmed fraud, "
                f"{marked_count - fraud_confirmed_count} false positives)"
            )

    except (ValueError, AttributeError) as e:
        logger.error(f"Outcome tracking error for {tenant.schema_name}: {e}", exc_info=True)