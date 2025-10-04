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
    """
    from apps.noc.security_intelligence.ml import (
        BehavioralProfiler,
        GoogleMLIntegrator
    )
    from apps.peoples.models import People
    from apps.tenants.models import Tenant

    try:
        logger.info("Starting daily ML training cycle")

        for tenant in Tenant.objects.filter(is_active=True):
            _train_models_for_tenant(tenant)

    except (ValueError, AttributeError) as e:
        logger.error(f"ML training task error: {e}", exc_info=True)


def _train_models_for_tenant(tenant):
    """Train models for a tenant."""
    from apps.noc.security_intelligence.ml import (
        BehavioralProfiler,
        GoogleMLIntegrator
    )
    from apps.peoples.models import People

    try:
        logger.info(f"Training models for {tenant.name}")

        active_guards = People.objects.filter(
            tenant=tenant,
            enable=True,
            isverified=True
        )[:1000]

        profiles_updated = 0
        for guard in active_guards:
            profile = BehavioralProfiler.create_or_update_profile(guard, days=90)
            if profile:
                profiles_updated += 1

        logger.info(f"Updated {profiles_updated} behavioral profiles for {tenant.name}")

        export_result = GoogleMLIntegrator.export_training_data(tenant, days=90)

        if export_result.get('success'):
            from apps.noc.security_intelligence.models import MLTrainingDataset

            dataset = MLTrainingDataset.objects.filter(
                tenant=tenant,
                status='EXPORTED'
            ).order_by('-cdtz').first()

            if dataset:
                training_result = GoogleMLIntegrator.train_fraud_model(dataset)

                if training_result.get('success'):
                    logger.info(f"Model training completed for {tenant.name}")
                    logger.info(f"Metrics: {training_result['metrics']}")

    except (ValueError, AttributeError) as e:
        logger.error(f"Tenant ML training error for {tenant.name}: {e}", exc_info=True)


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