# Background Jobs Architecture

**Author:** Claude Code
**Date:** 2025-10-27
**Status:** Production-Ready

---

## Overview

The background jobs system uses **Celery** with **Redis** as the broker and result backend. The architecture is designed for:
- High reliability with idempotency guarantees
- Intelligent queue routing by priority
- Collision-free beat scheduling
- Comprehensive monitoring and metrics

---

## Architecture Components

### 1. Celery Configuration

**Location:** `intelliwiz_config/celery.py`

**Key Features:**
- 7 priority queues (critical → ml_training)
- Beat schedule with 15-min collision avoidance
- DST-safe UTC scheduling
- Automatic task discovery

### 2. Task Base Classes

**Location:** `apps/core/tasks/base.py`

**Available Classes:**
- `BaseTask` - Standard task with retry logic
- `IdempotentTask` - Prevents duplicate execution (<2ms overhead)
- `EmailTask` - Specialized for email operations
- `ExternalServiceTask` - Circuit breaker for external APIs
- `ReportTask` - Long-running report generation
- `MaintenanceTask` - Cleanup and batch processing

### 3. Queue Routing

| Queue | Priority | SLA | Use Cases |
|-------|----------|-----|-----------|
| critical | 10 | <2s | Crisis intervention, security alerts |
| high_priority | 8 | <3s | User-facing ops, biometrics |
| email | 7 | <5s | Email processing |
| reports | 6 | <60s | Analytics, ML |
| external_api | 5 | <10s | MQTT, third-party |
| maintenance | 3 | <300s | Cleanup, cache warming |

### 4. Beat Schedule Tasks

**Critical Tasks (every 30 min):**
- `auto_close_jobs` - Auto-close expired jobs
- `ticket_escalation` - SLA breach escalation

**Report Tasks:**
- `create_scheduled_reports` - Every 15 min (offset: :05, :20, :35, :50)
- `send_generated_report_on_mail` - Every 27 min

**Maintenance Tasks:**
- `create_ppm_job` - PPM generation (3:03 AM, 4:03 PM)
- `move_media_to_cloud_storage` - Weekly (Monday 12 AM)

---

## Idempotency Framework

**How It Works:**
1. Generate unique key from task name + arguments
2. Check Redis for existing execution (<2ms)
3. If duplicate → return cached result
4. If new → execute and cache result

**Configuration:**
```python
@shared_task(base=IdempotentTask)
def my_task(self):
    self.idempotency_ttl = 3600  # 1 hour
    self.idempotency_scope = 'global'  # or 'user', 'tenant'
    # Task logic...
```

---

## Monitoring

**Prometheus Metrics:**
- Task retry rates by reason
- Execution times
- Success/failure rates

**Dashboards:**
- Celery Health: `/admin/monitoring/celery/`
- Real-time metrics via API: `/admin/monitoring/celery/api/metrics/`

---

## Operations

**Start Workers:**
```bash
celery -A intelliwiz_config worker -Q critical,high_priority,email --loglevel=info
```

**Start Beat Scheduler:**
```bash
celery -A intelliwiz_config beat --loglevel=info
```

**Health Check:**
```bash
python manage.py validate_schedules --verbose
python scripts/audit_celery_tasks.py --generate-report
```

**Common Issues:**
1. **Queue buildup** → Check schedule offsets
2. **Duplicate execution** → Verify idempotency enabled
3. **Task not found** → Check `@shared_task` decorator

---

## References

- Configuration: `intelliwiz_config/celery.py`
- Base Classes: `apps/core/tasks/base.py`
- Task Audit: `scripts/audit_celery_tasks.py`
- Health Checks: `python manage.py validate_schedules`
