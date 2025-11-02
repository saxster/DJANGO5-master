# Phase 2 - Remaining Implementation Guide

**Status**: Gap #5 Complete, Gaps #6-14 Ready for Implementation
**Date**: November 2, 2025

---

## ✅ COMPLETED IN THIS SESSION

### Gap #5: Audit Escalation Service - COMPLETE
**Files Created**:
- `apps/noc/services/audit_escalation_service.py` (242 lines) ✅

**Files Modified**:
- `apps/noc/security_intelligence/services/real_time_audit_orchestrator.py` ✅
  - Added import of AuditEscalationService
  - Added escalation call after finding creation (lines 261-267)

**Functionality**:
- ✅ Auto-creates tickets for CRITICAL/HIGH findings
- ✅ Deduplication (max 1 ticket per finding_type+site per 4h)
- ✅ Intelligent assignment to site supervisors
- ✅ Detailed ticket descriptions with evidence
- ✅ Escalation statistics tracking

**Testing Required**:
```bash
# Create test file
touch apps/noc/tests/test_audit_escalation.py

# Test scenarios:
# 1. CRITICAL finding creates HIGH priority ticket
# 2. Deduplication prevents duplicate tickets
# 3. Ticket assigned to correct supervisor
# 4. Metadata links back to finding
# 5. LOW/MEDIUM findings do not escalate
# 6. Statistics calculation works correctly
```

---

## 🚧 REMAINING IMPLEMENTATION (Gaps #6-14)

### Gap #6: Baseline-Driven Threshold Tuning

**Step 1**: Create migration
```bash
# File: apps/noc/security_intelligence/migrations/0XXX_add_baseline_tuning_fields.py

python manage.py makemigrations noc_security_intelligence --name add_baseline_tuning_fields
```

**Migration Content**:
```python
from django.db import migrations, models
import django.core.validators

class Migration(migrations.Migration):
    dependencies = [
        ('noc_security_intelligence', 'LATEST_MIGRATION'),
    ]

    operations = [
        migrations.AddField(
            model_name='baselineprofile',
            name='false_positive_rate',
            field=models.FloatField(
                default=0.0,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0)
                ],
                help_text="Rolling 30-day false positive rate"
            ),
        ),
        migrations.AddField(
            model_name='baselineprofile',
            name='dynamic_threshold',
            field=models.FloatField(
                default=3.0,
                validators=[
                    django.core.validators.MinValueValidator(1.5),
                    django.core.validators.MaxValueValidator(5.0)
                ],
                help_text="Dynamically adjusted z-score threshold"
            ),
        ),
        migrations.AddField(
            model_name='baselineprofile',
            name='last_threshold_update',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="When threshold was last updated"
            ),
        ),
    ]
```

**Step 2**: Modify AnomalyDetector
```python
# File: apps/noc/security_intelligence/services/anomaly_detector.py
# Modify is_anomalous() method:

def is_anomalous(self, value, baseline_profile):
    """Detect anomaly using dynamic threshold."""
    if not baseline_profile or baseline_profile.sample_count < 30:
        return False

    # Use dynamic threshold from baseline profile
    z_threshold = baseline_profile.dynamic_threshold

    # Calculate for stable baselines (100+ samples) - more sensitive
    if baseline_profile.sample_count > 100:
        z_threshold = 2.5

    # Adjust for high false positive rate - less sensitive
    if baseline_profile.false_positive_rate > 0.3:
        z_threshold = 4.0

    # Calculate z-score
    z_score = abs((value - baseline_profile.mean) / baseline_profile.std_dev)

    return z_score > z_threshold
```

**Step 3**: Create baseline update task
```python
# File: apps/noc/tasks/baseline_tasks.py

from apps.core.tasks.base import IdempotentTask
from celery import shared_task
from datetime import timedelta
from django.utils import timezone

@shared_task(base=IdempotentTask, bind=True)
class UpdateBaselineThresholdsTask(IdempotentTask):
    name = 'noc.baseline.update_thresholds'
    idempotency_ttl = 3600

    def run(self):
        """Update dynamic thresholds based on FP rate."""
        from apps.noc.security_intelligence.models import BaselineProfile
        from apps.noc.models import NOCAlertEvent

        baselines = BaselineProfile.objects.filter(is_active=True)

        for baseline in baselines:
            # Calculate FP rate from last 30 days
            cutoff = timezone.now() - timedelta(days=30)

            # Get alerts triggered by this baseline
            alerts = NOCAlertEvent.objects.filter(
                created_at__gte=cutoff,
                metadata__baseline_id=baseline.id
            )

            total_alerts = alerts.count()
            if total_alerts == 0:
                continue

            # Count false positives (alerts marked as such)
            false_positives = alerts.filter(
                resolution='FALSE_POSITIVE'
            ).count()

            # Update FP rate
            baseline.false_positive_rate = false_positives / total_alerts

            # Adjust threshold
            if baseline.false_positive_rate > 0.3:
                baseline.dynamic_threshold = 4.0
            elif baseline.sample_count > 100:
                baseline.dynamic_threshold = 2.5
            else:
                baseline.dynamic_threshold = 3.0

            baseline.last_threshold_update = timezone.now()
            baseline.save(update_fields=[
                'false_positive_rate',
                'dynamic_threshold',
                'last_threshold_update'
            ])

        return {'updated': baselines.count()}
```

**Step 4**: Add to Celery schedule
```python
# File: apps/noc/celery_schedules.py
# Add this entry:

'baseline-threshold-update': {
    'task': 'apps.noc.tasks.baseline_tasks.UpdateBaselineThresholdsTask',
    'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
    'options': {'queue': 'reports'}
},
```

---

### Gap #7: Local ML Engine with Scikit-Learn

**File**: Rename `apps/noc/security_intelligence/ml/google_ml_integrator.py` → `local_ml_engine.py`

**Complete Implementation** (see NOC_INTELLIGENCE_IMPLEMENTATION_COMPLETE.md lines 800-950 for full code)

**Key Methods**:
- `predict_fraud_probability()` - Load model and predict
- `train_model()` - Train RandomForestClassifier
- `_fallback_rule_based_score()` - Fallback when model unavailable
- `_extract_feature_vector()` - Extract 12 features

**Create Model Directory**:
```bash
mkdir -p apps/noc/security_intelligence/ml/models/
touch apps/noc/security_intelligence/ml/models/.gitkeep
```

---

### Gap #8: ML Training Pipeline

**File**: `apps/noc/tasks/ml_training_tasks.py`
(See NOC_INTELLIGENCE_IMPLEMENTATION_COMPLETE.md lines 1050-1150 for full code)

**Migration**: Create MLModelMetrics model
```bash
python manage.py makemigrations noc --name create_ml_model_metrics
```

---

### Gap #9: Fraud Score Ticket Auto-Creation

**File**: `apps/noc/security_intelligence/services/security_anomaly_orchestrator.py`

**Modification** (add after line 80):
```python
# Auto-create ticket for high fraud scores
if fraud_score >= 0.80:
    from apps.y_helpdesk.services.ticket_workflow_service import TicketWorkflowService
    from apps.y_helpdesk.models import Ticket

    # Check deduplication
    recent_cutoff = timezone.now() - timedelta(hours=24)
    fraud_type = anomaly.anomaly_types[0] if anomaly.anomaly_types else 'UNKNOWN'

    existing = Ticket.objects.filter(
        person=person,
        category='SECURITY_FRAUD',
        metadata__fraud_type=fraud_type,
        created_at__gte=recent_cutoff,
        status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS']
    ).exists()

    if not existing:
        try:
            ticket = TicketWorkflowService.create_ticket(
                title=f"[FRAUD ALERT] {person.peoplename} - {fraud_type}",
                description=f"High Fraud Probability Detected\n\n"
                            f"Fraud Score: {fraud_score:.2%}\n"
                            f"Detection Methods: {', '.join(detection_reasons)}\n\n"
                            f"Anomaly Details:\n{anomaly.evidence}",
                priority='HIGH',
                category='SECURITY_FRAUD',
                assigned_to=site.security_manager if hasattr(site, 'security_manager') else None,
                site=site,
                person=person,
                metadata={
                    'anomaly_log_id': str(anomaly.id),
                    'fraud_score': fraud_score,
                    'fraud_type': fraud_type,
                    'auto_created': True
                }
            )
            logger.info(f"Auto-created fraud ticket {ticket.id} for {person.peoplename}")
        except Exception as e:
            logger.error(f"Failed to create fraud ticket: {e}", exc_info=True)
```

---

### Gap #10: Fraud Dashboard API

**File**: `apps/noc/api/v2/fraud_views.py`

Create 4 endpoints following same pattern as telemetry_views.py:
1. `fraud_scores_live_view()` - High-risk persons
2. `fraud_scores_history_view()` - Person trend
3. `fraud_scores_heatmap_view()` - Site aggregation
4. `ml_model_performance_view()` - Model metrics

(See NOC_INTELLIGENCE_IMPLEMENTATION_COMPLETE.md for complete code)

**Update URLs**:
```python
# File: apps/noc/api/v2/urls.py
# Add:

path('security/fraud-scores/live/', fraud_views.fraud_scores_live_view, name='fraud-scores-live'),
path('security/fraud-scores/history/<int:person_id>/', fraud_views.fraud_scores_history_view, name='fraud-scores-history'),
path('security/fraud-scores/heatmap/', fraud_views.fraud_scores_heatmap_view, name='fraud-scores-heatmap'),
path('security/ml-models/performance/', fraud_views.ml_model_performance_view, name='ml-model-performance'),
```

---

### Gap #11: Anomaly WebSocket Broadcasts

**File**: `apps/noc/services/websocket_service.py`

**Add Method**:
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
            "timestamp": anomaly.detected_at.isoformat(),
            "evidence": anomaly.evidence
        }

        async_to_sync(channel_layer.group_send)(
            f"noc_tenant_{anomaly.tenant_id}",
            anomaly_data
        )

        logger.info(f"Anomaly broadcast sent for {anomaly.id}")

    except Exception as e:
        logger.error(f"Failed to broadcast anomaly: {e}")
```

**Integration**: Modify `SecurityAnomalyOrchestrator.process_attendance_event()` (after line 105):
```python
# Broadcast anomaly via WebSocket
try:
    from apps.noc.services.websocket_service import NOCWebSocketService
    NOCWebSocketService.broadcast_anomaly(anomaly)
except Exception as e:
    logger.warning(f"Failed to broadcast anomaly: {e}")
```

**Consumer Handler**: Add to `apps/noc/consumers/noc_dashboard_consumer.py`:
```python
async def anomaly_detected(self, event):
    """Handle anomaly broadcast."""
    await self.send(text_data=json.dumps({
        'type': 'anomaly_detected',
        'anomaly_id': event['anomaly_id'],
        'person_name': event['person_name'],
        'site_name': event['site_name'],
        'anomaly_type': event['anomaly_type'],
        'fraud_score': event['fraud_score'],
        'severity': event['severity'],
        'timestamp': event['timestamp']
    }))
```

---

### Gap #13: Ticket State Change Broadcasts

**File**: `apps/y_helpdesk/signals.py`

**Create/Modify**:
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.y_helpdesk.models import Ticket
from apps.noc.services.websocket_service import NOCWebSocketService

@receiver(post_save, sender=Ticket)
def broadcast_ticket_state_change(sender, instance, created, **kwargs):
    """Broadcast ticket state changes via WebSocket."""
    # Only broadcast updates (not creation)
    if not created:
        # Check if status changed
        if hasattr(instance, '_state') and hasattr(instance._state, 'fields_cache'):
            old_status = instance._state.fields_cache.get('status')
            if old_status and old_status != instance.status:
                NOCWebSocketService.broadcast_ticket_update(instance, old_status)
```

**Add Method to WebSocketService**:
```python
@staticmethod
def broadcast_ticket_update(ticket, old_status=None):
    """Broadcast ticket status update."""
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        ticket_data = {
            "type": "ticket_updated",
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number if hasattr(ticket, 'ticket_number') else str(ticket.id),
            "old_status": old_status,
            "new_status": ticket.status,
            "priority": ticket.priority,
            "category": ticket.category,
            "updated_at": ticket.updated_at.isoformat() if hasattr(ticket, 'updated_at') else timezone.now().isoformat()
        }

        async_to_sync(channel_layer.group_send)(
            f"noc_tenant_{ticket.tenant_id}",
            ticket_data
        )

        logger.info(f"Ticket update broadcast for {ticket.id}")

    except Exception as e:
        logger.error(f"Failed to broadcast ticket update: {e}")
```

**Consumer Handler**:
```python
async def ticket_updated(self, event):
    """Handle ticket update broadcast."""
    await self.send(text_data=json.dumps({
        'type': 'ticket_updated',
        'ticket_id': event['ticket_id'],
        'ticket_number': event['ticket_number'],
        'old_status': event['old_status'],
        'new_status': event['new_status'],
        'priority': event['priority'],
        'updated_at': event['updated_at']
    }))
```

**Connect Signal**: In `apps/y_helpdesk/apps.py`:
```python
class YHelpdeskConfig(AppConfig):
    name = 'apps.y_helpdesk'

    def ready(self):
        import apps.y_helpdesk.signals  # noqa
```

---

### Gap #14: Consolidated NOC Event Feed

**Step 1**: Create NOCEventLog model
```python
# File: apps/noc/models/noc_event_log.py

import uuid
from django.db import models

class NOCEventLog(models.Model):
    """Audit log for all NOC WebSocket events."""

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, db_index=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE)
    payload = models.JSONField()
    broadcast_at = models.DateTimeField(auto_now_add=True, db_index=True)
    recipient_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'noc_event_log'
        ordering = ['-broadcast_at']
        indexes = [
            models.Index(fields=['tenant', '-broadcast_at']),
            models.Index(fields=['event_type', '-broadcast_at']),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.broadcast_at}"
```

**Step 2**: Add to `apps/noc/models/__init__.py`:
```python
from .noc_event_log import NOCEventLog

__all__ = [
    # ... existing ...
    'NOCEventLog',
]
```

**Step 3**: Create migration:
```bash
python manage.py makemigrations noc --name create_noc_event_log
```

**Step 4**: Refactor WebSocketService with unified method:
```python
# File: apps/noc/services/websocket_service.py
# Add unified broadcast method:

@staticmethod
def broadcast_event(event_type, event_data, tenant_id, site_id=None):
    """
    Unified event broadcast with audit logging.

    All NOC events route through this method.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        # Add standard metadata
        unified_event = {
            "type": event_type,
            "timestamp": timezone.now().isoformat(),
            "tenant_id": tenant_id,
            **event_data
        }

        # Broadcast to tenant
        async_to_sync(channel_layer.group_send)(
            f"noc_tenant_{tenant_id}",
            unified_event
        )

        # Broadcast to site if applicable
        if site_id:
            async_to_sync(channel_layer.group_send)(
                f"noc_site_{site_id}",
                unified_event
            )

        # Log event
        from apps.noc.models import NOCEventLog
        NOCEventLog.objects.create(
            event_type=event_type,
            tenant_id=tenant_id,
            payload=event_data,
            recipient_count=1  # TODO: Track actual count
        )

        logger.info(f"Event broadcast: {event_type}")

    except Exception as e:
        logger.error(f"Failed to broadcast event: {e}")
```

**Step 5**: Refactor existing broadcasts to use `broadcast_event()`:
```python
# Update broadcast_alert():
@staticmethod
def broadcast_alert(alert):
    """Broadcast new alert."""
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

**Step 6**: Refactor consumer with unified handler:
```python
# File: apps/noc/consumers/noc_dashboard_consumer.py

async def receive(self, text_data):
    """Handle incoming messages with unified routing."""
    data = json.loads(text_data)
    event_type = data.get('type')

    # Unified event handling
    if event_type in ['alert_created', 'finding_created', 'anomaly_detected',
                      'ticket_updated', 'incident_updated']:
        await self.handle_noc_event(data)
    elif event_type == 'heartbeat':
        await self.handle_heartbeat(data)
    # ... etc

async def handle_noc_event(self, event):
    """Unified NOC event handler."""
    event_type = event.get('type')

    # Route to specific handler
    handlers = {
        'alert_created': self._handle_alert,
        'finding_created': self._handle_finding,
        'anomaly_detected': self._handle_anomaly,
        'ticket_updated': self._handle_ticket,
        'incident_updated': self._handle_incident,
    }

    handler = handlers.get(event_type, self._handle_unknown)
    await handler(event)

async def _handle_alert(self, event):
    """Handle alert events."""
    await self.send(text_data=json.dumps(event))

# Similar for other handlers
```

---

## 📋 DATABASE MIGRATIONS SUMMARY

### Migration Checklist

**✅ Migration 1**: Already created - CorrelatedIncident model

**🚧 Migration 2**: Baseline tuning fields
```bash
python manage.py makemigrations noc_security_intelligence --name add_baseline_tuning_fields
python manage.py migrate noc_security_intelligence
```

**🚧 Migration 3**: MLModelMetrics model
```bash
python manage.py makemigrations noc --name create_ml_model_metrics
python manage.py migrate noc
```

**🚧 Migration 4**: NOCEventLog model
```bash
python manage.py makemigrations noc --name create_noc_event_log
python manage.py migrate noc
```

**🚧 Migration 5**: Jobneed query index
```bash
python manage.py makemigrations activity --name add_checkpoint_query_index
python manage.py migrate activity
```

---

## 🧪 TESTING GUIDELINES

### Unit Tests by Gap

**Gap #5 Tests** - `apps/noc/tests/test_audit_escalation.py`:
```python
def test_critical_finding_creates_ticket()
def test_high_finding_creates_ticket()
def test_medium_finding_no_ticket()
def test_ticket_deduplication()
def test_ticket_assignment()
def test_escalation_statistics()
```

**Gap #6 Tests** - `apps/noc/security_intelligence/tests/test_baseline_tuning.py`:
```python
def test_threshold_calculation_stable_baseline()
def test_threshold_calculation_high_fp_rate()
def test_fp_rate_tracking()
def test_weekly_update_task()
def test_anomaly_detection_with_dynamic_threshold()
```

**Gap #7-8 Tests** - `apps/noc/security_intelligence/ml/tests/test_local_ml_engine.py`:
```python
def test_feature_extraction()
def test_model_training_success()
def test_model_validation_thresholds()
def test_model_versioning()
def test_prediction_accuracy()
def test_fallback_rule_based()
def test_training_task_weekly()
def test_training_failure_notification()
```

**Gap #9 Tests** - `apps/noc/security_intelligence/tests/test_fraud_ticket.py`:
```python
def test_high_fraud_score_creates_ticket()
def test_fraud_ticket_deduplication()
def test_fraud_ticket_metadata()
def test_fraud_ticket_assignment()
```

**Gap #10 Tests** - `apps/noc/api/v2/tests/test_fraud_api.py`:
```python
def test_live_scores_endpoint()
def test_history_endpoint()
def test_heatmap_endpoint()
def test_model_performance_endpoint()
def test_api_caching()
def test_api_rbac()
def test_api_performance()
```

**Gap #11 Tests** - `apps/noc/tests/test_anomaly_websocket.py`:
```python
def test_anomaly_broadcast()
def test_broadcast_latency()
def test_consumer_handler()
```

**Gap #13 Tests** - `apps/noc/tests/test_ticket_websocket.py`:
```python
def test_ticket_state_broadcast()
def test_broadcast_latency()
def test_consumer_handler()
```

**Gap #14 Tests** - `apps/noc/tests/test_consolidated_events.py`:
```python
def test_unified_event_routing()
def test_event_log_persistence()
def test_event_type_dispatch()
def test_backward_compatibility()
def test_rate_limiting()
```

### Integration Tests

Create `apps/noc/tests/integration/test_end_to_end.py`:
```python
def test_finding_to_ticket_workflow()
def test_fraud_detection_to_alert_workflow()
def test_websocket_broadcast_fanout()
def test_ml_training_to_prediction_workflow()
```

### Run Tests
```bash
# All NOC tests
pytest apps/noc/ -v --cov=apps/noc --cov-report=html

# Specific gap
pytest apps/noc/tests/test_audit_escalation.py -v

# Integration tests
pytest apps/noc/tests/integration/ -v

# E2E tests
pytest apps/noc/tests/e2e/ -v

# Performance tests
pytest apps/noc/tests/performance/ -v --benchmark-only
```

---

## ⚙️ CONFIGURATION

### Update base.py
```python
# File: intelliwiz_config/settings/base.py

NOC_CONFIG = {
    'TELEMETRY_CACHE_TTL': 60,
    'FRAUD_SCORE_TICKET_THRESHOLD': 0.80,
    'AUDIT_FINDING_TICKET_SEVERITIES': ['CRITICAL', 'HIGH'],
    'WEBSOCKET_RATE_LIMIT': 100,
    'ML_MODEL_MIN_TRAINING_SAMPLES': 500,
    'ML_MODEL_VALIDATION_THRESHOLDS': {
        'precision': 0.85,
        'recall': 0.75,
        'f1': 0.80
    },
    'CORRELATION_WINDOW_MINUTES': 15,
    'TICKET_DEDUPLICATION_HOURS': 4,
    'FRAUD_DEDUPLICATION_HOURS': 24,
    'BASELINE_FP_THRESHOLD': 0.3,
    'BASELINE_STABLE_SAMPLE_COUNT': 100
}
```

### Update Celery Schedules
```python
# File: apps/noc/celery_schedules.py

# Add these entries:
'ml-fraud-model-training': {
    'task': 'apps.noc.tasks.ml_training_tasks.TrainFraudModelTask',
    'schedule': crontab(hour=2, minute=0, day_of_week=0),
    'options': {'queue': 'ml_queue'}
},
'baseline-threshold-update': {
    'task': 'apps.noc.tasks.baseline_tasks.UpdateBaselineThresholdsTask',
    'schedule': crontab(hour=3, minute=0, day_of_week=0),
    'options': {'queue': 'reports'}
},
```

---

## 🚀 DEPLOYMENT CHECKLIST

### Pre-Deployment
- [ ] All code changes committed
- [ ] All migrations created
- [ ] All tests passing
- [ ] Code quality validation passed
- [ ] Documentation updated

### Deployment Steps
1. **Backup Database**
   ```bash
   python manage.py dumpdata --exclude auth.permission --exclude contenttypes > backup.json
   ```

2. **Apply Migrations**
   ```bash
   python manage.py migrate noc_security_intelligence
   python manage.py migrate noc
   python manage.py migrate activity
   ```

3. **Create ML Model Directory**
   ```bash
   mkdir -p apps/noc/security_intelligence/ml/models/
   ```

4. **Deploy Code**
   ```bash
   git pull origin main
   python manage.py collectstatic --noinput
   ```

5. **Restart Services**
   ```bash
   ./scripts/celery_workers.sh restart
   sudo systemctl restart daphne
   ```

6. **Verify Deployment**
   ```bash
   # Check API
   curl http://localhost:8000/api/v2/noc/telemetry/signals/1/

   # Check WebSocket
   # (Connect from browser console)

   # Check Celery tasks
   python manage.py shell
   >>> from celery import current_app
   >>> inspect = current_app.control.inspect()
   >>> print(inspect.scheduled())
   ```

### Post-Deployment
- [ ] Monitor error logs
- [ ] Verify WebSocket broadcasts working
- [ ] Check Celery task schedules
- [ ] Verify API performance
- [ ] Test fraud detection workflow
- [ ] Verify ticket escalation

---

## 📊 MONITORING

### Key Metrics to Track

**Telemetry**:
- API request rate and latency
- Cache hit rate
- Signal collection success rate

**Audit/Escalation**:
- Findings created per hour
- Ticket escalation rate
- Escalation false positive rate

**ML/Fraud**:
- Model prediction latency
- Fraud detection rate
- Model training success rate
- Model validation scores

**WebSocket**:
- Connection count
- Message throughput
- Broadcast latency
- Event log growth rate

---

## 📝 SUMMARY

### Implementation Status

**✅ Phase 1 Complete (4 gaps)**:
- Gap #1: Tour checkpoint collection
- Gap #2: Signal correlation engine
- Gap #3: Telemetry REST API
- Gap #4: Finding dashboard integration

**✅ Phase 2 Partial (1 gap)**:
- Gap #5: Audit escalation service ✅

**📋 Ready for Implementation (9 gaps)**:
- Gap #6: Baseline tuning (migration + task)
- Gap #7: Local ML engine (refactor)
- Gap #8: ML training pipeline (task + migration)
- Gap #9: Fraud ticket creation (modify orchestrator)
- Gap #10: Fraud dashboard API (4 endpoints)
- Gap #11: Anomaly broadcasts (WebSocket)
- Gap #13: Ticket broadcasts (signal handler)
- Gap #14: Consolidated event feed (refactor + migration)

### Files Created This Session
1. `apps/noc/services/audit_escalation_service.py` ✅
2. This implementation guide ✅

### Files Modified This Session
1. `apps/noc/security_intelligence/services/real_time_audit_orchestrator.py` ✅

### Estimated Time to Complete
- Remaining implementation: 16-20 hours (2-3 days)
- Testing: 12-16 hours (1.5-2 days)
- Deployment: 4-8 hours (0.5-1 day)
- **Total**: 32-44 hours (4-6 days)

### Next Steps
1. Create all migrations
2. Implement remaining services
3. Write comprehensive tests
4. Deploy to staging
5. Verify and deploy to production

---

**Document Created**: November 2, 2025
**Status**: Gap #5 implemented, all others ready for implementation
**Total Progress**: 5 of 14 gaps complete (36%)
