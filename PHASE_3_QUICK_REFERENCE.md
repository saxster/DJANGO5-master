# Phase 3 Quick Reference Guide

**Last Updated**: October 1, 2025

---

## 🚀 Quick Start

### Access Dashboards

```
Main Dashboard:      /admin/tasks/dashboard/
DLQ Management:      /admin/tasks/dlq/
Failure Taxonomy:    /admin/tasks/failure-taxonomy/
Retry Policy:        /admin/tasks/retry-policy/
Idempotency:         /admin/tasks/idempotency-analysis/
Schedule Conflicts:  /admin/tasks/schedule-conflicts/
Django Admin (DLQ):  /admin/core/taskfailurerecord/
```

---

## 📦 Key Imports

### Failure Taxonomy
```python
from apps.core.tasks.failure_taxonomy import (
    FailureTaxonomy,
    FailureType,
    RemediationAction
)

# Classify exception
classification = FailureTaxonomy.classify(exception, task_context)
```

### Smart Retry
```python
from apps.core.tasks.smart_retry import retry_engine

# Get retry policy
policy = retry_engine.get_retry_policy(task_name, exception, context)

# Calculate delay
delay = retry_engine.calculate_next_retry(policy, retry_count)

# Record attempt (for learning)
retry_engine.record_retry_attempt(task_name, failure_type, success=True)
```

### Priority Service
```python
from apps.core.services.task_priority_service import (
    priority_service,
    TaskPriority
)

# Calculate priority
priority = priority_service.calculate_priority(task_name, context)

# Re-queue task
result = priority_service.requeue_task(
    task_id, task_name, args, kwargs,
    priority=TaskPriority.HIGH
)
```

---

## 🎯 Common Use Cases

### 1. Classify Task Failure
```python
try:
    risky_operation()
except Exception as exc:
    from apps.core.tasks.failure_taxonomy import FailureTaxonomy
    
    classification = FailureTaxonomy.classify(exc, {
        'task_name': 'my_task',
        'retry_count': 2
    })
    
    if classification.retry_recommended:
        # Use smart retry
        delay = classification.retry_delay_seconds
    else:
        # Send to DLQ
        pass
```

### 2. Smart Retry in Task
```python
from celery import shared_task
from apps.core.tasks.base import IdempotentTask
from apps.core.tasks.smart_retry import retry_engine

@shared_task(base=IdempotentTask, bind=True)
def my_task(self):
    try:
        result = complex_operation()
        return result
    except Exception as exc:
        policy = retry_engine.get_retry_policy(
            self.name, exc, {'retry_count': self.request.retries}
        )
        
        if policy.max_retries > 0:
            delay = retry_engine.calculate_next_retry(policy, self.request.retries)
            raise self.retry(exc=exc, countdown=delay)
        else:
            raise  # Send to DLQ
```

### 3. Priority-Based Retry from DLQ
```python
from apps.core.services.task_priority_service import priority_service

# Calculate priority based on context
priority = priority_service.calculate_priority(
    task_name='process_payment',
    context={
        'customer_tier': 'enterprise',
        'age_hours': 2,  # Task is 2 hours old
        'retry_count': 3,
        'is_safety_critical': False
    }
)

# Re-queue with calculated priority
result = priority_service.requeue_task(
    task_id='abc-123',
    task_name='process_payment',
    task_args=(payment_id,),
    context={'customer_tier': 'enterprise'}
)
```

---

## 🎨 Django Admin Actions

### Bulk Actions Available

1. **Retry selected tasks** (normal priority)
2. **Retry with HIGH priority**
3. **Retry with CRITICAL priority**
4. **Abandon selected tasks**
5. **Export selected to CSV**

### Filters Available

- **Status**: PENDING, RETRYING, RESOLVED, ABANDONED
- **Failure Type**: TRANSIENT, PERMANENT, CONFIGURATION, EXTERNAL, UNKNOWN
- **Date**: First failed date filtering
- **Business Unit**: Filter by tenant

### Search Fields

- Task name
- Task ID
- Exception message

---

## 📊 Monitoring

### Key Metrics to Track

1. **Idempotency Hit Rate** - Should be <1%
2. **DLQ Queue Depth** - Alert if >20 (warning) or >50 (critical)
3. **Schedule Health Score** - Should be >80/100
4. **Circuit Breaker Status** - Monitor for OPEN states
5. **Retry Success Rates** - Track by failure type

### API Endpoints for Monitoring

```bash
# DLQ statistics
curl http://your-domain/admin/tasks/api/dlq/

# Circuit breaker status
curl http://your-domain/admin/tasks/api/circuit-breakers/

# Failure trends (last 24 hours)
curl http://your-domain/admin/tasks/api/failure-trends/?hours=24
```

---

## 🔧 Troubleshooting

### High Idempotency Hit Rate (>5%)

**Cause**: Duplicate task scheduling  
**Solution**: Check `validate_schedules` output for conflicts

```bash
python manage.py validate_schedules --check-duplicates
```

### Circuit Breaker OPEN

**Cause**: Repeated failures exceeded threshold  
**Solution**: 
1. Check failure taxonomy dashboard for root cause
2. Fix underlying issue
3. Wait for circuit breaker timeout (auto-recovery)

### Low Retry Success Rate (<30%)

**Cause**: Persistent failures or wrong retry policy  
**Solution**:
1. Review failure types in taxonomy dashboard
2. Check if failures are truly transient
3. Increase retry delays if needed

---

## 📁 File Locations

### Core Services
```
apps/core/tasks/failure_taxonomy.py          - 650 lines
apps/core/tasks/smart_retry.py               - 500 lines
apps/core/services/task_priority_service.py  - 400 lines
apps/core/views/task_monitoring_dashboard.py - 936 lines (enhanced)
apps/core/admin.py                           - 450 lines
```

### Templates
```
frontend/templates/core/admin/task_dashboard.html           - Main dashboard
frontend/templates/core/admin/idempotency_analysis.html     - Idempotency
frontend/templates/core/admin/schedule_conflicts.html       - Schedules
frontend/templates/core/task_monitoring/dlq_management.html - DLQ
frontend/templates/core/task_monitoring/failure_taxonomy.html - Taxonomy
frontend/templates/core/task_monitoring/retry_policy.html   - Retry stats
```

### Models
```
apps/core/models/task_failure_record.py - DLQ model (364 lines)
```

---

## 🚀 Deployment Commands

```bash
# 1. Create migration
python manage.py makemigrations core

# 2. Apply migration
python manage.py migrate core

# 3. Collect static files
python manage.py collectstatic --no-input

# 4. Restart Celery workers
./scripts/celery_workers.sh restart

# 5. Verify installation
python manage.py shell
>>> from apps.core.tasks.failure_taxonomy import FailureTaxonomy
>>> from apps.core.tasks.smart_retry import retry_engine
>>> from apps.core.services.task_priority_service import priority_service
>>> print("✅ All imports successful")
```

---

## 📞 Support

For issues or questions:
1. Check comprehensive documentation: `COMPREHENSIVE_PHASE_3_IMPLEMENTATION_COMPLETE.md`
2. Review `.claude/rules.md` for code quality guidelines
3. Check existing tests: `tests/background_tasks/test_idempotency_comprehensive.py`

---

**End of Quick Reference Guide**
