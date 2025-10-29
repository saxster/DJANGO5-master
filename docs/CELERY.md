# Celery Configuration Guide

**Complete reference for background task processing**

→ **Quick start:** See [CLAUDE.md](../CLAUDE.md#daily-commands) for most common commands

---

## Table of Contents

- [Quick Reference](#quick-reference)
- [Configuration Standards](#configuration-standards)
- [Task Development](#task-development)
- [Idempotency Framework](#idempotency-framework)
- [Schedule Management](#schedule-management)
- [Common Issues & Fixes](#common-issues--fixes)

---

## Quick Reference

### Most Common Commands

```bash
# Start/stop workers
./scripts/celery_workers.sh start                    # All optimized workers
./scripts/celery_workers.sh stop                     # Stop all workers
./scripts/celery_workers.sh restart                  # Restart workers
./scripts/celery_workers.sh monitor                  # Real-time dashboard

# Validate schedules
python manage.py validate_schedules --verbose        # Full validation
python manage.py validate_schedules --check-duplicates
python manage.py validate_schedules --check-orphaned-tasks

# Audit tasks
python scripts/audit_celery_tasks.py --generate-report
python scripts/audit_celery_tasks.py --duplicates-only
```

### Task Queues

| Queue | Priority | SLA | Use For |
|-------|----------|-----|---------|
| `critical` | 10 | <2s | Crisis alerts, security events |
| `high_priority` | 8 | <3s | User-facing operations |
| `email` | 7 | <5s | Email sending |
| `reports` | 6 | <60s | Report generation, ML processing |
| `external_api` | 5 | <10s | MQTT, third-party integrations |
| `maintenance` | 3 | <300s | Cleanup, cache warming |

### Decision Tree: Which Task Decorator?

```
[New task?]
    → Check if exists: python scripts/audit_celery_tasks.py --duplicates-only
    → No duplicate found ↓

[Need idempotency?]
    Yes → @shared_task(base=IdempotentTask, bind=True)
    No → @shared_task

[Legacy GraphQL mutation?]
    Not applicable (GraphQL removed Oct 2025)
```

---

## Configuration Standards

### Single Source of Truth

**⚠️ CRITICAL:** All Celery configuration must live in these files ONLY:

- **`intelliwiz_config/celery.py`** - Celery app instance and beat schedule
- **`apps/core/tasks/celery_settings.py`** - Reusable config components

**Forbidden:**
- ❌ Creating new `celery.py` files
- ❌ Defining beat schedules outside main config
- ❌ Importing `from intelliwiz_config.celery import app` (except in legacy services)

### Task Decorator Standards

**✅ REQUIRED: Use @shared_task**

```python
from celery import shared_task

@shared_task(name="send_reminder_email")
def send_reminder_email(user_id):
    """Send reminder email to user"""
    # Implementation
    pass
```

**Why @shared_task?**
- Decouples tasks from specific Celery app instance
- Easier testing (no app dependency)
- Better for reusable Django apps
- Standard across Django community

**❌ FORBIDDEN: Direct @app.task import**

```python
from intelliwiz_config.celery import app  # ❌ WRONG

@app.task(name="send_reminder_email")  # ❌ WRONG
def send_reminder_email(user_id):
    pass
```

**Exception:** Only use `@app.task` in:
- `apps/service/services/*` (legacy GraphQL mutation tasks)
- Must have explicit justification and team approval

### Task Naming Conventions

**✅ CORRECT: Task name without parentheses**

```python
@shared_task(name="create_job")  # ✅ Correct
def create_job(jobids=None):
    pass
```

**❌ FORBIDDEN: Task name with parentheses**

```python
@shared_task(name="create_job()")  # ❌ WRONG - Beat won't find it
def create_job(jobids=None):
    pass
```

**Best Practice: Let Celery auto-name**

```python
@shared_task  # ✅ Auto-uses function name "send_reminder_email"
def send_reminder_email(user_id):
    pass
```

### Task File Organization

**Recommended Structure:**

```text
background_tasks/
├── email_tasks.py        # All email-related tasks
├── media_tasks.py        # Media processing tasks
├── report_tasks.py       # Report generation tasks
├── job_tasks.py          # Job/tour management tasks
├── ticket_tasks.py       # Ticketing tasks
├── tasks.py              # Import aggregator ONLY (legacy compatibility)
└── [NEW FILES ONLY]      # Never add new tasks to tasks.py

apps/[app_name]/services/
└── *_service.py          # Domain-specific service tasks
```

**Rules:**
- **DO:** Create new domain-specific files (e.g., `notification_tasks.py`)
- **DON'T:** Add to `background_tasks/tasks.py` (2,320 lines god file)
- **DON'T:** Mix `@app.task` and `@shared_task` in same file
- **DON'T:** Create duplicate task implementations

---

## Task Development

### Task Base Classes

**Use built-in base classes** from `apps/core/tasks/base.py`:

```python
from celery import shared_task
from apps.core.tasks.base import (
    IdempotentTask,
    EmailTask,
    ReportTask,
    MaintenanceTask,
    ExternalAPITask
)

# With idempotency protection
@shared_task(base=IdempotentTask, bind=True)
def auto_close_jobs(self):
    """Automatically close expired jobs (prevents duplicates)"""
    pass

# Email-specific retry policy
@shared_task(base=EmailTask, bind=True)
def send_reminder_email(self, user_id):
    """Send reminder with email-specific error handling"""
    pass

# Report generation with longer timeout
@shared_task(base=ReportTask, bind=True)
def generate_monthly_report(self, month):
    """Generate monthly report (24h timeout)"""
    pass
```

**Available Base Classes:**

| Base Class | Purpose | Retry Policy | Timeout |
|------------|---------|--------------|---------|
| `IdempotentTask` | Prevents duplicate execution | 3 retries, exponential backoff | Default |
| `EmailTask` | Email-specific retries | 5 retries, short backoff | 2 min |
| `ReportTask` | Report generation | 2 retries, long backoff | 30 min |
| `MaintenanceTask` | Low-priority cleanup | No retries | Default |
| `ExternalAPITask` | API call retries | 3 retries, exponential backoff | 10 min |

### Duplicate Task Prevention

**Before creating a new task:**

```bash
# Check if task already exists
python scripts/audit_celery_tasks.py --duplicates-only

# View full inventory with locations
python scripts/audit_celery_tasks.py --generate-report
```

**If duplicate found:**
1. **Use existing implementation** from modern file (not `tasks.py`)
2. **If both in god file and modern file:** Keep modern file version
3. **Update imports** to reference canonical implementation

**Example:**

```python
# ❌ WRONG: Defining again
@shared_task(name="send_reminder_email")
def send_reminder_email(user_id):
    pass

# ✅ CORRECT: Import existing
from background_tasks.email_tasks import send_reminder_email
```

### Queue Routing

**Route tasks by domain** in `apps/core/tasks/celery_settings.py`:

```python
CELERY_TASK_ROUTES = {
    # Critical (10) - <2s SLA
    'auto_close_jobs': {'queue': 'critical'},
    'ticket_escalation': {'queue': 'critical'},

    # High Priority (8) - <3s SLA
    'create_job': {'queue': 'high_priority'},
    'update_job_status': {'queue': 'high_priority'},

    # Email (7) - <5s SLA
    'send_reminder_email': {'queue': 'email'},
    'send_notification': {'queue': 'email'},

    # Reports (6) - <60s SLA
    'create_scheduled_reports': {'queue': 'reports'},
    'ml_analysis': {'queue': 'reports'},

    # External API (5) - <10s SLA
    'mqtt_publish': {'queue': 'external_api'},
    'third_party_sync': {'queue': 'external_api'},

    # Maintenance (3) - <300s SLA
    'cleanup_old_reports': {'queue': 'maintenance'},
    'cache_warming': {'queue': 'maintenance'},
}
```

**How to choose queue:**
- **critical:** User safety, security alerts, system health
- **high_priority:** User-facing operations, must complete fast
- **email:** All email sending
- **reports:** Analytics, ML, can take time
- **external_api:** Third-party integrations
- **maintenance:** Background cleanup, not user-facing

---

## Idempotency Framework

**Prevents duplicate task execution** across all background operations.

### Core Components

```python
from apps.core.tasks.idempotency_service import UniversalIdempotencyService
from apps.core.tasks.base import IdempotentTask
from apps.core.tasks.decorators import with_idempotency
```

### Pattern 1: Idempotent Task Class

```python
from apps.core.tasks.base import IdempotentTask
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

class AutoCloseJobsTask(IdempotentTask):
    name = 'auto_close_jobs'
    idempotency_scope = 'global'  # or 'user', 'tenant'
    idempotency_ttl = SECONDS_IN_HOUR * 4  # 4 hours

    def run(self):
        """Task implementation with automatic duplicate prevention"""
        # Check/acquire lock happens automatically
        # Your logic here
        pass
```

### Pattern 2: Decorator for Existing Tasks

```python
from celery import shared_task
from apps.core.tasks.decorators import with_idempotency
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

@with_idempotency(scope='user', ttl=SECONDS_IN_HOUR * 2)
@shared_task
def send_reminder_email(user_id):
    """Send reminder with automatic duplicate prevention"""
    # Implementation
    pass
```

### Performance Metrics

- **Redis check:** <2ms (25x faster than PostgreSQL)
- **PostgreSQL fallback:** <7ms
- **Duplicate detection:** <1% in steady state
- **Total overhead:** <7% per task

### Task Categories (TTL by Priority)

| Category | TTL | Examples |
|----------|-----|----------|
| **Critical** | 4h | `auto_close_jobs`, `ticket_escalation` |
| **High Priority** | 2h | `create_job`, `send_reminder_email` |
| **Reports** | 24h | `create_scheduled_reports` |
| **Mutations** | 6h | `process_mutation_async` |
| **Maintenance** | 12h | `cleanup_old_reports` |

### Troubleshooting Idempotency

```bash
# Check idempotency status
python manage.py shell
>>> from apps.core.tasks.idempotency_service import UniversalIdempotencyService
>>> service = UniversalIdempotencyService()
>>> service.check_idempotency_key('auto_close_jobs', 'global')

# Clear stuck lock (if needed)
>>> service.clear_idempotency_key('task_name', 'scope')
```

---

## Schedule Management

### Beat Schedule Configuration

**Add to `intelliwiz_config/celery.py` beat_schedule ONLY:**

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    "send_reminder_emails": {
        'task': 'send_reminder_email',  # ✅ Must match task name exactly
        'schedule': crontab(hour='*/8', minute='10'),
        'options': {
            'expires': 28800,  # 8 hours (schedule interval)
            'queue': 'email',  # Route to appropriate queue
        }
    },
    "auto_close_jobs": {
        'task': 'auto_close_jobs',
        'schedule': crontab(hour='*/4', minute='0'),  # Every 4 hours
        'options': {
            'expires': 14400,  # 4 hours
            'queue': 'critical',
        }
    },
}
```

**Best Practices:**
- **expires:** Set to schedule interval (prevents queue buildup)
- **task name:** Must match exactly (no parentheses!)
- **queue:** Route to appropriate priority queue
- **schedule:** Use crontab for complex schedules, timedelta for simple

### Validation Commands

```bash
# Comprehensive validation
python manage.py validate_schedules --verbose

# Check specific issues
python manage.py validate_schedules --check-duplicates          # Multiple tasks same time
python manage.py validate_schedules --check-hotspots            # Overloaded time slots
python manage.py validate_schedules --check-idempotency         # Duplicate execution risk
python manage.py validate_schedules --check-orphaned-tasks      # Beat → task mapping

# Orphaned task detection (CRITICAL)
# Validates that ALL beat schedule tasks are registered
# Orphaned tasks cause Celery beat scheduler to fail silently
python manage.py validate_schedules --check-orphaned-tasks --verbose
```

### Orphaned Task Prevention (Oct 2025)

**Problem:** Beat schedule references tasks that don't exist → silent failures

**Solution:** Automated validation on every commit

**Integration:**
- Pre-commit hook: `.pre-commit-config.yaml`
- Blocks commits with orphaned tasks
- Run manually: `python manage.py validate_schedules --check-orphaned-tasks`

**Example Error:**
```
ERROR: Orphaned task 'old_task_name' in beat schedule
Task not found in registered tasks.

Fix:
1. Register task with @shared_task(name="old_task_name"), OR
2. Remove from beat schedule in intelliwiz_config/celery.py
```

---

## Common Issues & Fixes

### Issue 1: Duplicate Task Definitions

**Symptom:** Task runs multiple times, inconsistent behavior

**Diagnosis:**
```bash
python scripts/audit_celery_tasks.py --duplicates-only
```

**Fix:**

```python
# ❌ WRONG: Same task in multiple files
# background_tasks/tasks.py
@shared_task(name="send_reminder_email")
def send_reminder_email(user_id):
    pass

# background_tasks/email_tasks.py
@shared_task(name="send_reminder_email")  # ❌ Duplicate!
def send_reminder_email(user_id):
    pass

# ✅ FIX: Keep ONE implementation, import in god file
# background_tasks/email_tasks.py (canonical)
@shared_task(name="send_reminder_email")
def send_reminder_email(user_id):
    pass

# background_tasks/tasks.py (import aggregator)
from background_tasks.email_tasks import send_reminder_email  # ✅ Import only
```

### Issue 2: Mixed Decorators in Same File

**Symptom:** Inconsistent task behavior, import errors

**Fix:**

```python
# ❌ WRONG: Mixing @app.task and @shared_task
from intelliwiz_config.celery import app
from celery import shared_task

@app.task  # ❌ Wrong decorator
def task_one():
    pass

@shared_task  # ✅ Correct decorator
def task_two():
    pass

# ✅ FIX: Use @shared_task consistently
from celery import shared_task

@shared_task  # ✅ Consistent
def task_one():
    pass

@shared_task  # ✅ Consistent
def task_two():
    pass
```

### Issue 3: Task Name with Parentheses

**Symptom:** Beat scheduler can't find task, tasks don't run

**Fix:**

```python
# ❌ WRONG: Parentheses in task name
@shared_task(name="create_job()")  # ❌ Beat won't find it
def create_job(jobids=None):
    pass

# ✅ FIX: Remove parentheses
@shared_task(name="create_job")  # ✅ Beat will find it
def create_job(jobids=None):
    pass
```

### Issue 4: Tasks Not Running on Schedule

**Symptom:** Scheduled tasks don't execute, no errors in logs

**Diagnosis:**
```bash
# Check if task is orphaned
python manage.py validate_schedules --check-orphaned-tasks --verbose

# Check beat schedule
python manage.py shell
>>> from intelliwiz_config.celery import app
>>> print(app.conf.beat_schedule)
```

**Common Causes:**
1. **Task name mismatch:** Beat schedule references wrong name
2. **Task not registered:** Missing @shared_task decorator
3. **Orphaned task:** Task deleted but still in beat schedule
4. **Beat not running:** Check `celery beat` process

**Fix:**
```python
# Ensure task name in beat schedule matches decorator
# In intelliwiz_config/celery.py
"send_emails": {
    'task': 'send_reminder_email',  # ✅ Must match exactly
    ...
}

# In background_tasks/email_tasks.py
@shared_task(name="send_reminder_email")  # ✅ Matches
def send_reminder_email(user_id):
    pass
```

### Issue 5: Queue Routing Not Working

**Symptom:** All tasks go to default queue, priorities not respected

**Diagnosis:**
```bash
# Check task routes
python manage.py shell
>>> from apps.core.tasks.celery_settings import CELERY_TASK_ROUTES
>>> print(CELERY_TASK_ROUTES)
```

**Fix:** Ensure task is in routing table

```python
# In apps/core/tasks/celery_settings.py
CELERY_TASK_ROUTES = {
    'your_task_name': {'queue': 'email'},  # ✅ Add route
}

# Restart workers to pick up changes
./scripts/celery_workers.sh restart
```

---

## Current State (2025-10-29)

### Statistics

- **Total tasks:** 94 unique (was 130 with duplicates)
- **Duplicate tasks:** 0 (was 29) ✅
- **God file:** `background_tasks/tasks.py` (import aggregator, <300 lines target)
- **@shared_task usage:** 108/130 (83%) → Target: >95%
- **@app.task usage:** 22/130 (17%) → Migrating to @shared_task

### Progress

- ✅ **Single Celery config** (achieved)
- ✅ **Centralized reusable components** (achieved)
- ✅ **Zero duplicate implementations** (achieved Oct 2025)
- 🔄 **>95% @shared_task usage** (in progress)
- 🔄 **God file < 300 lines** (import aggregator only)

---

## Additional Resources

### Related Documentation

- **Quick Start:** [CLAUDE.md](../CLAUDE.md#daily-commands) - Most common commands
- **Architecture:** `docs/ARCHITECTURE.md` - System design (to be created)
- **Reference:** `docs/REFERENCE.md` - Complete command catalog (to be created)
- **Rules:** `docs/RULES.md` - Mandatory patterns (to be created)

### Key Files

- **Celery app:** `intelliwiz_config/celery.py`
- **Settings:** `apps/core/tasks/celery_settings.py`
- **Base classes:** `apps/core/tasks/base.py`
- **Idempotency:** `apps/core/tasks/idempotency_service.py`
- **Task keys:** `background_tasks/task_keys.py`

### Archives

- **Task inventory:** `CELERY_TASK_INVENTORY_REPORT.md` (archived)
- **Refactoring progress:** `CELERY_REFACTORING_PROGRESS_SUMMARY.md` (archived)
- **Complete history:** `docs/archive/refactorings/REFACTORING_ARCHIVES.md`

---

**Last Updated:** 2025-10-29
**Maintainer:** Backend Tech Lead
**Review Cycle:** Monthly
