# Universal Idempotency Framework

> **Prevents duplicate task execution across all background operations**

---

## Overview

The Universal Idempotency Framework (Oct 2025) ensures that background tasks execute exactly once, even when multiple workers or schedulers attempt to run the same task simultaneously.

---

## Core Components

### Import Core Services

```python
from apps.core.tasks.idempotency_service import UniversalIdempotencyService
from apps.core.tasks.base import IdempotentTask
from apps.core.tasks.decorators import with_idempotency
```

---

## Usage Patterns

### 1. Idempotent Task Class

**Recommended for new tasks**

```python
from apps.core.tasks.base import IdempotentTask
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

class AutoCloseJobsTask(IdempotentTask):
    name = 'auto_close_jobs'
    idempotency_scope = 'global'
    idempotency_ttl = SECONDS_IN_HOUR * 4  # 4 hours

    def run(self):
        # Automatic duplicate prevention
        # Task logic here
        pass
```

### 2. Decorator for Existing Tasks

**For migrating legacy tasks**

```python
from apps.core.tasks.decorators import with_idempotency
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR
from celery import shared_task

@with_idempotency(scope='user', ttl=SECONDS_IN_HOUR * 2)
@shared_task
def send_reminder_email(user_id):
    # Task logic here
    pass
```

---

## Performance

### Benchmarks

- **Redis check**: <2ms (25x faster than PostgreSQL)
- **PostgreSQL fallback**: <7ms
- **Duplicate detection rate**: <1% in steady state
- **Total overhead**: <7% per task

### Why it's fast

1. Redis-first strategy with in-memory checks
2. PostgreSQL fallback only when Redis unavailable
3. Minimal serialization overhead
4. Connection pooling

---

## Task Categories (TTL by Priority)

### Critical Tasks (4 hours)

- `auto_close_jobs` - Job lifecycle management
- `ticket_escalation` - SLA enforcement

### High Priority Tasks (2 hours)

- `create_job` - Job creation
- `send_reminder_email` - User notifications

### Report Tasks (24 hours)

- `create_scheduled_reports` - Report generation

### Maintenance (12 hours)

- `cleanup_reports_which_are_12hrs_old` - Cleanup operations

---

## Schedule Coordination

### Validate schedules for conflicts

```bash
# Comprehensive validation
python manage.py validate_schedules --verbose

# Check for duplicates
python manage.py validate_schedules --check-duplicates

# Dry run fix
python manage.py validate_schedules --fix --dry-run
```

### Analyze tasks for migration

```bash
# Full analysis
python scripts/migrate_to_idempotent_tasks.py --analyze

# Migrate specific task
python scripts/migrate_to_idempotent_tasks.py --task auto_close_jobs
```

---

## Monitoring

### Dashboards

| Dashboard | URL | Purpose |
|-----------|-----|---------|
| Task Dashboard | `/admin/tasks/dashboard` | Overall task metrics |
| Idempotency Analysis | `/admin/tasks/idempotency-analysis` | Duplicate detection stats |
| Schedule Conflicts | `/admin/tasks/schedule-conflicts` | Timing conflicts |

### Metrics Tracked

- Duplicate prevention rate
- Task execution latency
- Redis vs PostgreSQL usage
- Failed idempotency checks

---

## Reference Files

| File | Lines | Purpose |
|------|-------|---------|
| `apps/core/tasks/idempotency_service.py` | 430 | Core framework |
| `apps/core/tasks/base.py` | 185 | Base task classes |
| `background_tasks/task_keys.py` | 320 | Key generation |

---

## Configuration

### Idempotency Scopes

- **`global`** - One execution system-wide (e.g., `auto_close_jobs`)
- **`user`** - One execution per user (e.g., `send_reminder_email`)
- **`tenant`** - One execution per tenant (e.g., `generate_tenant_report`)
- **`custom`** - Custom key generation

### TTL Guidelines

| Priority | TTL | Use Case |
|----------|-----|----------|
| Critical | 4h | System-critical operations |
| High | 2h | User-facing operations |
| Reports | 24h | Analytics, batch jobs |
| Mutations | 6h | Data modifications |
| Maintenance | 12h | Cleanup, optimization |

---

## Best Practices

### ✅ DO

- Use Redis for production (fast checks)
- Set appropriate TTL based on task frequency
- Monitor idempotency metrics
- Use `global` scope for system tasks
- Use `user` scope for per-user tasks

### ❌ DON'T

- Set TTL shorter than task execution time
- Use idempotency for real-time tasks (<1s latency)
- Rely on idempotency for critical data integrity (use transactions)
- Mix idempotency scopes for same task

---

## Troubleshooting

### Duplicate tasks still running?

```bash
# Analyze current state
python scripts/migrate_to_idempotent_tasks.py --analyze

# Check schedule conflicts
python manage.py validate_schedules --check-duplicates
```

### Check idempotency logs

Visit dashboard: `/admin/tasks/idempotency-analysis`

### Redis connectivity issues?

Framework automatically falls back to PostgreSQL with <7ms latency.

---

**Last Updated**: October 29, 2025
**Maintainer**: Backend Team
**Related**: [Celery Configuration](CELERY_CONFIGURATION_GUIDE.md), [Background Processing](BACKGROUND_PROCESSING.md)
