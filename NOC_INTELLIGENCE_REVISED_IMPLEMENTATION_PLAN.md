# NOC Intelligence - Revised Implementation Plan

**Based On**: ML codebase investigation (November 2, 2025)
**Key Finding**: Team has already implemented 70% of ML infrastructure with XGBoost
**Revised Completion**: 50% → 100% (28-32 hours remaining)

---

## IMPLEMENTATION TASKS (15 Tasks)

### TASK 1: Create ML Model Directories
**Effort**: 15 minutes
**Dependencies**: None
**Files**: Create directories, .gitkeep files

**What to do**:
```bash
mkdir -p media/ml_models media/ml_training_data
touch media/ml_models/.gitkeep
touch media/ml_training_data/.gitkeep
echo "*.joblib" >> media/ml_models/.gitignore
echo "*.csv" >> media/ml_training_data/.gitignore
```

**Verification**:
```bash
ls -la media/ml_models
ls -la media/ml_training_data
```

---

### TASK 2: Gap #6 - Modify AnomalyDetector for Dynamic Thresholds
**Effort**: 1 hour
**Dependencies**: TASK 1 complete
**Files**: `apps/noc/security_intelligence/services/anomaly_detector.py`

**What to do**:
1. Read current `is_anomalous()` method
2. Modify to use `baseline_profile.dynamic_threshold` instead of fixed 3.0
3. Add logic for stable baselines (sample_count > 100 → threshold 2.5)
4. Add logic for high FP rate (false_positive_rate > 0.3 → threshold 4.0)

**Code change**:
```python
def is_anomalous(self, value, baseline_profile):
    """Detect anomaly using dynamic threshold from baseline."""
    if not baseline_profile or baseline_profile.sample_count < 30:
        return False, 0.0, 0.0

    # Use dynamic threshold (was: fixed 3.0)
    z_threshold = baseline_profile.dynamic_threshold

    # More sensitive for stable baselines
    if baseline_profile.sample_count > 100:
        z_threshold = 2.5

    # Less sensitive for high false positive rate
    if baseline_profile.false_positive_rate > 0.3:
        z_threshold = 4.0

    z_score = (value - baseline_profile.mean) / baseline_profile.std_dev
    is_anomalous = abs(z_score) > z_threshold

    return is_anomalous, z_score, z_threshold
```

**Tests**:
- Unit test: stable baseline uses 2.5 threshold
- Unit test: high FP rate uses 4.0 threshold
- Unit test: normal baseline uses dynamic_threshold value

**Verification**:
```python
from apps.noc.security_intelligence.models import BaselineProfile
bp = BaselineProfile.objects.first()
bp.sample_count = 150
bp.dynamic_threshold = 3.0
result = AnomalyDetector().is_anomalous(100, bp)
# Verify threshold used is 2.5 (not 3.0)
```

---

### TASK 3: Gap #6 - Create Baseline Threshold Update Task
**Effort**: 2 hours
**Dependencies**: TASK 2 complete
**Files**: Create `apps/noc/tasks/baseline_tasks.py`

**What to do**:
Create Celery task that:
1. Queries all active BaselineProfile records
2. For each, calculates rolling 30-day false positive rate from NOCAlertEvent resolutions
3. Updates false_positive_rate and dynamic_threshold fields
4. Logs statistics

**Implementation**:
```python
from apps.core.tasks.base import IdempotentTask
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger('noc.baseline_tasks')

@shared_task(base=IdempotentTask, bind=True)
class UpdateBaselineThresholdsTask(IdempotentTask):
    name = 'noc.baseline.update_thresholds'
    idempotency_ttl = 3600

    def run(self):
        """Update dynamic thresholds based on 30-day FP rate."""
        from apps.noc.security_intelligence.models import BaselineProfile
        from apps.noc.models import NOCAlertEvent
        from django.conf import settings

        baselines = BaselineProfile.objects.filter(is_stable=True)
        updated_count = 0

        for baseline in baselines:
            cutoff = timezone.now() - timedelta(days=30)

            # Get alerts linked to this baseline
            alerts = NOCAlertEvent.objects.filter(
                created_at__gte=cutoff,
                site=baseline.site,
                metadata__baseline_id=baseline.id
            )

            total_alerts = alerts.count()
            if total_alerts == 0:
                continue

            # Count false positives
            false_positives = alerts.filter(
                resolution='FALSE_POSITIVE'
            ).count()

            # Update FP rate
            baseline.false_positive_rate = false_positives / total_alerts

            # Adjust threshold based on NOC_CONFIG
            config = settings.NOC_CONFIG
            if baseline.false_positive_rate > config['BASELINE_FP_THRESHOLD']:
                baseline.dynamic_threshold = config['BASELINE_CONSERVATIVE_THRESHOLD']
            elif baseline.sample_count > config['BASELINE_STABLE_SAMPLE_COUNT']:
                baseline.dynamic_threshold = config['BASELINE_SENSITIVE_THRESHOLD']
            else:
                baseline.dynamic_threshold = config['BASELINE_DEFAULT_THRESHOLD']

            baseline.last_threshold_update = timezone.now()
            baseline.save(update_fields=[
                'false_positive_rate',
                'dynamic_threshold',
                'last_threshold_update'
            ])
            updated_count += 1

        logger.info(f"Updated {updated_count} baseline thresholds")
        return {'updated': updated_count}
```

**Tests**:
- Unit test: FP rate calculation
- Unit test: Threshold adjustment logic
- Integration test: Task execution

**Verification**:
```python
from apps.noc.tasks.baseline_tasks import UpdateBaselineThresholdsTask
result = UpdateBaselineThresholdsTask().run()
assert result['updated'] >= 0
```

---

### TASK 4: Gap #7 - Migrate Background Task to FraudModelTrainer
**Effort**: 2 hours
**Dependencies**: None (parallel with TASK 2-3)
**Files**: `apps/noc/security_intelligence/tasks.py`

**What to do**:
Modify `train_ml_models_daily()` function (lines 240-306) to use FraudModelTrainer instead of GoogleMLIntegrator.

**Code change** (replace lines 288-303):
```python
def _train_models_for_tenant(tenant):
    """Train models for tenant (called by train_ml_models_daily)."""
    from apps.noc.security_intelligence.ml.fraud_model_trainer import FraudModelTrainer
    from apps.noc.management.commands.train_fraud_model import Command as TrainCommand
    from apps.noc.security_intelligence.models import FraudDetectionModel

    # Update behavioral profiles (keep existing code)
    profiles_updated = 0
    active_guards = People.objects.filter(
        tenant=tenant,
        isactive=True,
        peopleorganizational__isnull=False
    )[:100]

    for guard in active_guards:
        try:
            profile = BehavioralProfiler.create_or_update_profile(guard, days=90)
            if profile:
                profiles_updated += 1
        except Exception as e:
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
            except Exception as e:
                logger.error(f"❌ XGBoost training failed for {tenant.schema_name}: {e}")
        else:
            logger.warning(
                f"Insufficient training data for {tenant.schema_name}: "
                f"{export_result.get('record_count', 0)} records (need 100+)"
            )
```

**Tests**:
- Unit test: Behavioral profile update works
- Unit test: Retraining triggered weekly
- Integration test: Full training cycle

**Verification**:
```python
from apps.noc.security_intelligence.tasks import train_ml_models_daily
result = train_ml_models_daily()
# Check logs for "XGBoost training completed"
```

---

### TASK 5: Deprecate GoogleMLIntegrator
**Effort**: 30 minutes
**Dependencies**: TASK 4 complete
**Files**: `apps/noc/security_intelligence/ml/google_ml_integrator.py`

**What to do**:
Add deprecation warnings and documentation.

**Code change** (add at top of class):
```python
import warnings

class GoogleMLIntegrator:
    """
    Google ML Integrator (DEPRECATED).

    ⚠️ DEPRECATION WARNING ⚠️
    This class is deprecated and returns placeholder values only.

    MIGRATION PATH:
    - For training: Use FraudModelTrainer + train_fraud_model management command
    - For prediction: Use PredictiveFraudDetector.predict_attendance_fraud()
    - For export: Use FraudModelTrainer.export_training_data()

    REMOVAL DATE: December 31, 2025

    RATIONALE:
    BigQuery ML integration replaced with local XGBoost training for:
    - Zero cloud dependencies
    - Lower latency (no network calls)
    - Better control over model lifecycle
    - Imbalanced class handling with scale_pos_weight
    """

    def __init__(self):
        warnings.warn(
            "GoogleMLIntegrator is deprecated. "
            "Use FraudModelTrainer for training and PredictiveFraudDetector for prediction.",
            DeprecationWarning,
            stacklevel=2
        )
```

**Tests**:
- Unit test: Deprecation warning raised

**Verification**:
```python
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    integrator = GoogleMLIntegrator()
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
```

---

### TASK 6: NEW - Integrate PredictiveFraudDetector with Orchestrator
**Effort**: 8 hours
**Dependencies**: TASK 4, TASK 5 complete
**Files**: `apps/noc/security_intelligence/services/security_anomaly_orchestrator.py`

**What to do**:
Add ML prediction to attendance event processing pipeline.

**Integration point**: After line 45 (after getting config)

**Code to add**:
```python
# Predictive ML fraud detection
from apps.noc.security_intelligence.ml.predictive_fraud_detector import PredictiveFraudDetector

ml_prediction_result = None
if config and getattr(config, 'predictive_fraud_enabled', True):
    try:
        ml_prediction_result = PredictiveFraudDetector.predict_attendance_fraud(
            person=person,
            site=site,
            attendance_time=attendance_event.punchintime
        )

        # Log prediction for feedback loop
        PredictiveFraudDetector.log_prediction(
            person=person,
            site=site,
            attendance_time=attendance_event.punchintime,
            prediction_result=ml_prediction_result
        )

        logger.info(
            f"ML fraud prediction for {person.peoplename}: "
            f"{ml_prediction_result['fraud_probability']:.2%} "
            f"({ml_prediction_result['risk_level']})"
        )

        # Create preemptive alert for high-risk predictions
        if ml_prediction_result['risk_level'] in ['HIGH', 'CRITICAL']:
            cls._create_ml_prediction_alert(
                attendance_event=attendance_event,
                prediction=ml_prediction_result,
                config=config
            )

    except Exception as e:
        logger.warning(f"ML prediction failed for {person.peoplename}: {e}")
        # Continue with heuristic fraud detection
```

**Add new method** (after `_create_fraud_alert`):
```python
@classmethod
def _create_ml_prediction_alert(cls, attendance_event, prediction, config):
    """Create alert for high ML fraud prediction."""
    from apps.noc.services import AlertCorrelationService

    alert = AlertCorrelationService.process_alert(
        tenant=attendance_event.tenant,
        alert_type='ML_FRAUD_PREDICTION',
        severity='HIGH' if prediction['risk_level'] == 'HIGH' else 'CRITICAL',
        message=f"ML model predicts {prediction['fraud_probability']:.1%} fraud probability",
        entity_type='ATTENDANCE',
        entity_id=attendance_event.id,
        person=attendance_event.people,
        site=attendance_event.bu,
        metadata={
            'ml_prediction': prediction,
            'model_version': prediction.get('model_version'),
            'features': prediction.get('features', {})
        }
    )

    logger.info(f"Created ML prediction alert {alert.id}")
    return alert
```

**Tests**:
- Unit test: ML prediction called for attendance event
- Unit test: High-risk prediction creates alert
- Integration test: Prediction → Log → Alert → Anomaly check
- E2E test: Complete fraud detection pipeline

**Verification**:
```python
# Trigger attendance event
event = create_test_attendance_event()
SecurityAnomalyOrchestrator.process_attendance_event(event)
# Verify FraudPredictionLog has entry
# Verify alert created if high risk
```

---

### TASK 7: Gap #9 - Add Fraud Score Ticket Auto-Creation
**Effort**: 1 hour
**Dependencies**: TASK 6 complete
**Files**: `apps/noc/security_intelligence/services/security_anomaly_orchestrator.py`

**What to do**:
Add ticket creation after line 80 (after creating alert) for fraud_score >= 0.80.

**Code to add** (after alert creation at line 162):
```python
# Auto-create ticket for high fraud scores (Gap #9)
from django.conf import settings

fraud_threshold = settings.NOC_CONFIG.get('FRAUD_SCORE_TICKET_THRESHOLD', 0.80)

if fraud_score >= fraud_threshold:
    from apps.y_helpdesk.services.ticket_workflow_service import TicketWorkflowService
    from apps.y_helpdesk.models import Ticket

    # Deduplication check
    dedup_hours = settings.NOC_CONFIG.get('FRAUD_DEDUPLICATION_HOURS', 24)
    recent_cutoff = timezone.now() - timedelta(hours=dedup_hours)
    fraud_type = anomaly.anomaly_types[0] if anomaly.anomaly_types else 'UNKNOWN'

    existing_ticket = Ticket.objects.filter(
        person=person,
        category='SECURITY_FRAUD',
        metadata__fraud_type=fraud_type,
        created_at__gte=recent_cutoff,
        status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']
    ).exists()

    if not existing_ticket:
        try:
            # Determine assigned_to
            assigned_to = None
            if hasattr(site, 'security_manager'):
                assigned_to = site.security_manager
            elif hasattr(site, 'site_manager'):
                assigned_to = site.site_manager

            ticket = TicketWorkflowService.create_ticket(
                title=f"[FRAUD ALERT] {person.peoplename} - {fraud_type}",
                description=f"High Fraud Probability Detected\\n\\n"
                           f"Fraud Score: {fraud_score:.2%}\\n"
                           f"Detection Methods: {', '.join(detection_reasons)}\\n\\n"
                           f"Anomaly Details:\\n{anomaly.evidence}",
                priority='HIGH',
                category='SECURITY_FRAUD',
                assigned_to=assigned_to,
                site=site,
                person=person,
                metadata={
                    'anomaly_log_id': str(anomaly.id),
                    'fraud_score': fraud_score,
                    'fraud_type': fraud_type,
                    'auto_created': True,
                    'created_by': 'SecurityAnomalyOrchestrator'
                }
            )
            logger.info(f"Auto-created fraud ticket {ticket.id} for {person.peoplename}")
        except Exception as e:
            logger.error(f"Failed to create fraud ticket: {e}", exc_info=True)
```

**Tests**:
- Unit test: High score (0.85) creates ticket
- Unit test: Deduplication prevents duplicate tickets
- Integration test: Fraud detection → Alert → Ticket workflow

**Verification**:
```python
# Create high-fraud-score anomaly
# Verify ticket created
from apps.y_helpdesk.models import Ticket
ticket = Ticket.objects.filter(category='SECURITY_FRAUD').first()
assert ticket is not None
assert ticket.metadata['fraud_score'] >= 0.80
```

---

### TASK 8: Gap #10 - Create Fraud Dashboard API
**Effort**: 3 hours
**Dependencies**: None (parallel with other tasks)
**Files**: Create `apps/noc/api/v2/fraud_views.py`, modify `apps/noc/api/v2/urls.py`

**What to do**:
Create 4 REST API endpoints for fraud intelligence dashboard.

**Endpoints**:
1. `GET /api/v2/noc/security/fraud-scores/live/` - High-risk persons (score >0.5)
2. `GET /api/v2/noc/security/fraud-scores/history/<person_id>/` - 30-day trend
3. `GET /api/v2/noc/security/fraud-scores/heatmap/` - Site-level aggregation
4. `GET /api/v2/noc/security/ml-models/performance/` - Current model metrics

**Implementation pattern** (follow telemetry_views.py structure):
- Use @require_capability('security:fraud:view')
- Redis caching with 5-minute TTL
- Pagination for large datasets
- Error handling with specific exceptions

**Tests**:
- 4 endpoint tests (one per endpoint)
- Caching test
- RBAC test
- Performance test (<500ms)

**Verification**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v2/noc/security/fraud-scores/live/ | jq
```

---

### TASK 9: Gap #11 - Add Anomaly WebSocket Broadcasts
**Effort**: 2 hours
**Dependencies**: None (parallel)
**Files**:
- `apps/noc/services/websocket_service.py`
- `apps/noc/security_intelligence/services/security_anomaly_orchestrator.py`
- `apps/noc/consumers/noc_dashboard_consumer.py`

**What to do**:
1. Add `broadcast_anomaly()` method to NOCWebSocketService
2. Call it from SecurityAnomalyOrchestrator after line 105
3. Add `anomaly_detected()` handler to NOCDashboardConsumer

**Implementation** (websocket_service.py):
```python
@staticmethod
def broadcast_anomaly(anomaly):
    """Broadcast attendance anomaly detection."""
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        anomaly_data = {
            "type": "anomaly_detected",
            "anomaly_id": str(anomaly.id),
            "person_id": anomaly.person.id,
            "person_name": anomaly.person.peoplename,
            "site_id": anomaly.site.id,
            "site_name": anomaly.site.name,
            "anomaly_type": anomaly.anomaly_types[0] if anomaly.anomaly_types else 'UNKNOWN',
            "fraud_score": anomaly.fraud_score,
            "severity": anomaly.severity,
            "timestamp": anomaly.detected_at.isoformat()
        }

        async_to_sync(channel_layer.group_send)(
            f"noc_tenant_{anomaly.tenant_id}",
            anomaly_data
        )

        logger.info(f"Anomaly broadcast sent: {anomaly.id}")

    except Exception as e:
        logger.error(f"Failed to broadcast anomaly: {e}")
```

**Tests**:
- Unit test: Broadcast method works
- Unit test: Latency <200ms
- Integration test: Anomaly created → Broadcast sent → Consumer receives

**Verification**:
Connect WebSocket in browser, create test anomaly, verify message received.

---

### TASK 10: Gap #13 - Add Ticket State Change Broadcasts
**Effort**: 2 hours
**Dependencies**: None (parallel)
**Files**:
- Create/modify `apps/y_helpdesk/signals.py`
- `apps/noc/services/websocket_service.py`
- `apps/y_helpdesk/apps.py`
- `apps/noc/consumers/noc_dashboard_consumer.py`

**What to do**:
1. Create Django signal handler for Ticket post_save
2. Add `broadcast_ticket_update()` to NOCWebSocketService
3. Wire signal in y_helpdesk/apps.py
4. Add `ticket_updated()` handler to consumer

**Implementation** (signals.py):
```python
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.y_helpdesk.models import Ticket
from apps.noc.services.websocket_service import NOCWebSocketService
import logging

logger = logging.getLogger('y_helpdesk.signals')

# Track original status before save
@receiver(pre_save, sender=Ticket)
def track_ticket_status_change(sender, instance, **kwargs):
    """Track original status before save."""
    if instance.pk:
        try:
            original = Ticket.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Ticket.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None

@receiver(post_save, sender=Ticket)
def broadcast_ticket_state_change(sender, instance, created, **kwargs):
    """Broadcast ticket state changes via WebSocket."""
    if not created and hasattr(instance, '_original_status'):
        old_status = instance._original_status
        if old_status and old_status != instance.status:
            logger.info(f"Ticket {instance.id} status changed: {old_status} → {instance.status}")
            NOCWebSocketService.broadcast_ticket_update(instance, old_status)
```

**Tests**:
- Unit test: Signal handler detects status change
- Unit test: Broadcast called on status change
- Integration test: Ticket update → WebSocket → Consumer

**Verification**:
```python
ticket = Ticket.objects.first()
ticket.status = 'IN_PROGRESS'
ticket.save()
# Check WebSocket broadcast in logs
```

---

### TASK 11: Gap #14 - Create Consolidated NOC Event Feed
**Effort**: 4 hours
**Dependencies**: TASK 9, TASK 10 complete
**Files**:
- `apps/noc/services/websocket_service.py` (major refactor)
- `apps/noc/consumers/noc_dashboard_consumer.py` (major refactor)

**What to do**:
1. Add unified `broadcast_event()` method
2. Refactor existing broadcasts to use it
3. Add event logging to NOCEventLog
4. Refactor consumer with unified handler

**Implementation** (add to websocket_service.py):
```python
@staticmethod
def broadcast_event(event_type, event_data, tenant_id, site_id=None):
    """
    Unified event broadcast with audit logging.

    All NOC events route through this method.
    """
    try:
        import time
        start_time = time.time()

        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not configured")
            return

        # Create unified event structure
        unified_event = {
            "type": event_type,
            "timestamp": timezone.now().isoformat(),
            "tenant_id": tenant_id,
            **event_data
        }

        # Broadcast to tenant group
        async_to_sync(channel_layer.group_send)(
            f"noc_tenant_{tenant_id}",
            unified_event
        )

        # Broadcast to site group if applicable
        if site_id:
            async_to_sync(channel_layer.group_send)(
                f"noc_site_{site_id}",
                unified_event
            )

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log event to NOCEventLog
        from apps.noc.models import NOCEventLog
        NOCEventLog.objects.create(
            event_type=event_type,
            tenant_id=tenant_id,
            payload=event_data,
            broadcast_latency_ms=latency_ms,
            broadcast_success=True,
            alert_id=event_data.get('alert_id'),
            finding_id=event_data.get('finding_id'),
            ticket_id=event_data.get('ticket_id'),
            recipient_count=1  # TODO: Track actual WebSocket connection count
        )

        logger.info(f"Event broadcast: {event_type} ({latency_ms}ms)")

    except Exception as e:
        logger.error(f"Failed to broadcast event {event_type}: {e}")
        # Log failure
        try:
            from apps.noc.models import NOCEventLog
            NOCEventLog.objects.create(
                event_type=event_type,
                tenant_id=tenant_id,
                payload=event_data,
                broadcast_success=False,
                error_message=str(e)
            )
        except Exception:
            pass  # Best effort logging
```

**Refactor existing methods**:
```python
@staticmethod
def broadcast_alert(alert):
    """Broadcast new alert (refactored)."""
    NOCWebSocketService.broadcast_event(
        event_type='alert_created',
        event_data={
            'alert_id': alert.id,
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'message': alert.message,
        },
        tenant_id=alert.tenant_id,
        site_id=alert.bu_id if alert.bu else None
    )

# Similar for broadcast_finding(), broadcast_anomaly(), broadcast_ticket_update()
```

**Tests**:
- Unit test: Unified broadcast works
- Unit test: Event logging persists
- Integration test: All event types route correctly
- Performance test: Latency tracking accurate

**Verification**:
```python
from apps.noc.models import NOCEventLog
# Create test event
# Verify logged to NOCEventLog with latency
logs = NOCEventLog.objects.filter(event_type='finding_created')
assert logs.exists()
assert logs.first().broadcast_latency_ms > 0
```

---

### TASK 12: Update Celery Schedules
**Effort**: 30 minutes
**Dependencies**: TASK 3 complete
**Files**: `apps/noc/celery_schedules.py`

**What to do**:
Add baseline threshold update task to Celery beat schedule.

**Code to add**:
```python
# Baseline threshold tuning (weekly)
'baseline-threshold-update': {
    'task': 'apps.noc.tasks.baseline_tasks.UpdateBaselineThresholdsTask',
    'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
    'options': {'queue': 'reports'}
},
```

**Note**: ML training task already exists in tasks.py line 240, just needs to be verified in schedules.

**Verification**:
```python
from django_celery_beat.models import PeriodicTask
task = PeriodicTask.objects.filter(name='baseline-threshold-update').first()
assert task is not None
assert task.enabled == True
```

---

### TASK 13: Apply All Database Migrations
**Effort**: 30 minutes
**Dependencies**: None (can be done anytime)
**Files**: Migrations created in previous session

**What to do**:
```bash
# Apply in order
python3 manage.py migrate activity 0002_add_checkpoint_query_index
python3 manage.py migrate noc 0002_add_intelligence_models
python3 manage.py migrate noc_security_intelligence 0002_add_intelligence_fields

# Verify all applied
python3 manage.py showmigrations noc noc_security_intelligence activity | grep "\[X\]"
```

**Verification**:
```python
from apps.noc.models import CorrelatedIncident, MLModelMetrics, NOCEventLog
from apps.noc.security_intelligence.models import BaselineProfile

# Verify new models accessible
assert CorrelatedIncident.objects.count() >= 0
assert MLModelMetrics.objects.count() >= 0
assert NOCEventLog.objects.count() >= 0

# Verify new fields exist
bp = BaselineProfile.objects.first()
assert hasattr(bp, 'false_positive_rate')
assert hasattr(bp, 'dynamic_threshold')
```

---

### TASK 14: Train Initial Fraud Models
**Effort**: 2 hours
**Dependencies**: TASK 13 complete (migrations applied)
**Files**: None (uses management command)

**What to do**:
```bash
# Create directories
mkdir -p media/ml_models media/ml_training_data

# Check if sufficient data exists
python3 manage.py shell
>>> from apps.attendance.models import PeopleEventlog
>>> from apps.noc.security_intelligence.models import FraudPredictionLog
>>> attendance_count = PeopleEventlog.objects.count()
>>> fraud_labels_count = FraudPredictionLog.objects.filter(actual_fraud_detected__isnull=False).count()
>>> print(f"Attendance events: {attendance_count}, Labeled fraud cases: {fraud_labels_count}")

# If sufficient data (100+ events):
python3 manage.py train_fraud_model --tenant=1 --days=180 --test-size=0.2

# Verify model created
ls -la media/ml_models/

# Activate model
python3 manage.py shell
>>> from apps.noc.security_intelligence.models import FraudDetectionModel
>>> model = FraudDetectionModel.objects.filter(tenant_id=1).order_by('-training_date').first()
>>> if model:
...     model.activate()
...     print(f"Activated model {model.model_version}")

# Test prediction
>>> from apps.noc.security_intelligence.ml.predictive_fraud_detector import PredictiveFraudDetector
>>> from apps.peoples.models import People
>>> from apps.onboarding.models import Bt
>>> person = People.objects.first()
>>> site = Bt.objects.first()
>>> result = PredictiveFraudDetector.predict_attendance_fraud(person, site, timezone.now())
>>> print(result)
```

**If insufficient data**:
- Skip model training
- System will use fallback heuristics
- Document in deployment notes

**Verification**:
- Model file exists in media/ml_models/
- FraudDetectionModel record created
- is_active=True for latest model
- Predictions return non-placeholder values

---

### TASK 15: Write Comprehensive Test Suite
**Effort**: 16 hours
**Dependencies**: TASK 1-11 complete
**Files**: Create multiple test files

**Test Files to Create**:

1. `apps/noc/tests/test_telemetry_api.py` (15 tests)
2. `apps/noc/tests/test_audit_escalation.py` (6 tests)
3. `apps/noc/security_intelligence/tests/test_baseline_tuning.py` (5 tests)
4. `apps/noc/security_intelligence/tests/test_ml_integration.py` (10 tests)
5. `apps/noc/security_intelligence/tests/test_fraud_ticket.py` (4 tests)
6. `apps/noc/api/v2/tests/test_fraud_api.py` (7 tests)
7. `apps/noc/tests/test_websocket_broadcasts.py` (10 tests)
8. `apps/noc/tests/test_consolidated_events.py` (5 tests)
9. `apps/noc/tests/integration/test_cross_track_workflows.py` (10 tests)
10. `apps/noc/tests/e2e/test_complete_workflows.py` (8 scenarios)

**Run Tests**:
```bash
pytest apps/noc/ -v --cov=apps/noc --cov-report=html --cov-report=term
# Target: >90% coverage
```

---

### TASK 16: Code Quality Validation
**Effort**: 2 hours
**Dependencies**: TASK 1-15 complete
**Files**: Run quality checks

**Commands**:
```bash
# Code quality
python scripts/validate_code_quality.py --verbose

# Type checking
mypy apps/noc/ --config-file mypy.ini

# Linting
flake8 apps/noc/ --max-line-length=120

# Security audit
bandit -r apps/noc/ -ll -f json -o security_audit_noc.json
```

**Fix any issues found**.

---

### TASK 17: Create Documentation Updates
**Effort**: 3 hours
**Dependencies**: TASK 1-16 complete
**Files**: Create/update documentation

**Documents to Create**:
1. `docs/api/NOC_INTELLIGENCE_API.md` - All REST endpoints
2. `docs/api/NOC_WEBSOCKET_EVENTS.md` - WebSocket message types
3. `docs/deployment/NOC_INTELLIGENCE_DEPLOYMENT.md` - Deployment runbook
4. `docs/operations/NOC_INTELLIGENCE_OPERATIONS.md` - Monitoring guide

**Updates**:
5. `CLAUDE.md` - Add NOC Intelligence section
6. `README.md` - Update features list

---

## TOTAL REVISED EFFORT

| Phase | Original Estimate | Revised Estimate | Reason |
|-------|------------------|------------------|--------|
| Gap #6 | 3 hours | 3 hours | Unchanged |
| Gap #7 | 4 hours | 2 hours | Mostly done by team |
| Gap #8 | 3 hours | 0 hours | **Already done** |
| Gap #9 | 1 hour | 1 hour | Unchanged |
| Gap #10 | 3 hours | 3 hours | Unchanged |
| NEW Gap | 0 hours | 8 hours | ML predictor integration |
| Gap #11 | 2 hours | 2 hours | Unchanged |
| Gap #13 | 2 hours | 2 hours | Unchanged |
| Gap #14 | 4 hours | 4 hours | Unchanged |
| Model Training | 0 hours | 2 hours | Initial models |
| Testing | 16 hours | 16 hours | Unchanged |
| Quality/Docs | 5 hours | 5 hours | Unchanged |
| Deployment | 7 hours | 7 hours | Unchanged |
| **TOTAL** | **50 hours** | **55 hours** | **7 days** |

**BUT**: Your team already did ~20 hours of ML work, so NET remaining = **35 hours (4.5 days)**

---

## EXECUTION ORDER

**Parallel Track A** (Baseline):
- TASK 1 → TASK 2 → TASK 3 → TASK 12

**Parallel Track B** (ML):
- TASK 1 → TASK 4 → TASK 5 → TASK 6 → TASK 7 → TASK 14

**Parallel Track C** (Fraud API):
- TASK 8

**Parallel Track D** (WebSocket):
- TASK 9 → TASK 10 → TASK 11

**Sequential** (After all tracks):
- TASK 13 → TASK 15 → TASK 16 → TASK 17

**Parallelization possible for**: TASK 2-11 (9 tasks can run concurrently in 4 tracks)

---

**Plan Status**: Revised and ready for execution
**Next Action**: Begin task execution with subagents
