# Celery Configuration Guide

> **Complete guide to Celery task configuration, organization, and best practices**

---

## 🔧 Critical: Read Before Creating/Modifying Any Celery Task

This guide contains mandatory standards for all Celery task development. Non-compliance will result in PR rejection.

---

## Single Source of Truth

### Main Configuration (ONLY)

- **`intelliwiz_config/celery.py`** - Celery app instance and beat schedule
- **`apps/core/tasks/celery_settings.py`** - Reusable config components

### Forbidden

- ❌ Creating new `celery.py` files
- ❌ Defining beat schedules outside main config
- ❌ Importing `from intelliwiz_config.celery import app` (except in services)

**Reference:** `CELERY_REFACTORING_PROGRESS_SUMMARY.md`, `CELERY_TASK_INVENTORY_REPORT.md`

---

## Task Decorator Standards

### ✅ REQUIRED: Use @shared_task

```python
from celery import shared_task

@shared_task(name="send_reminder_email")
def send_reminder_email(user_id):
    """Send reminder email to user"""
    pass
```

### ❌ FORBIDDEN: Direct @app.task import

```python
from intelliwiz_config.celery import app  # ❌ WRONG

@app.task(name="send_reminder_email")  # ❌ WRONG
def send_reminder_email(user_id):
    pass
```

### Exception: Only use @app.task in

- `apps/service/services/*` legacy mutation tasks
- Must have explicit justification and team approval

---

## Task Naming Conventions

### ✅ CORRECT: Task name without parentheses

```python
@shared_task(name="create_job")  # ✅ Correct
def create_job(jobids=None):
    pass
```

### ❌ FORBIDDEN: Task name with parentheses

```python
@shared_task(name="create_job()")  # ❌ WRONG - Beat won't find it
def create_job(jobids=None):
    pass
```

### Best Practice: Task name should match function name

```python
@shared_task  # ✅ Auto-uses function name
def send_reminder_email(user_id):
    pass
```

---

## Task File Organization

### Location Rules

```text
background_tasks/
├── email_tasks.py        # All email-related tasks
├── media_tasks.py        # Media processing tasks
├── report_tasks.py       # Report generation tasks
├── job_tasks.py          # Job/tour management tasks
├── ticket_tasks.py       # Ticketing tasks
├── tasks.py              # Import aggregator ONLY (legacy compatibility)
└── [NEW FILES ONLY]      # Never add to tasks.py

apps/[app_name]/services/
└── *_service.py          # Domain-specific service tasks
```

### ❌ FORBIDDEN

- Adding new task definitions to `background_tasks/tasks.py` (2,320 lines god file)
- Creating duplicate task implementations
- Mixing `@app.task` and `@shared_task` in same file

---

## Task Base Classes (Recommended)

### Use built-in base classes

From `apps/core/tasks/base.py`:

```python
from celery import shared_task
from apps.core.tasks.base import IdempotentTask, EmailTask

# With idempotency protection
@shared_task(base=IdempotentTask, bind=True)
def auto_close_jobs(self):
    """Automatically close expired jobs (with duplicate prevention)"""
    pass

# Email-specific retry policy
@shared_task(base=EmailTask, bind=True)
def send_reminder_email(self, user_id):
    """Send reminder with email-specific error handling"""
    pass
```

### Available Base Classes

- `IdempotentTask` - Prevents duplicate execution
- `EmailTask` - Email-specific retries and error handling
- `ReportTask` - Report generation with longer timeouts
- `MaintenanceTask` - Low-priority cleanup tasks
- `ExternalAPITask` - API call retries with backoff

---

## Duplicate Task Prevention

### Before creating a new task

```bash
# Check if task already exists
python scripts/audit_celery_tasks.py --duplicates-only

# View full inventory
python scripts/audit_celery_tasks.py --generate-report
```

### If duplicate found

1. Use existing implementation from modern file (not `tasks.py`)
2. If both in god file and modern file → keep modern file version
3. Update imports to reference canonical implementation

---

## Beat Schedule Integration

### Add to intelliwiz_config/celery.py beat_schedule ONLY

```python
app.conf.beat_schedule = {
    "send_reminder_emails": {
        'task': 'send_reminder_email',  # ✅ Must match task name exactly
        'schedule': crontab(hour='*/8', minute='10'),
        'options': {
            'expires': 28800,  # 8 hours
            'queue': 'email',  # Route to appropriate queue
        }
    },
}
```

### Verify beat schedule

```bash
python manage.py validate_schedules --verbose
python scripts/audit_celery_tasks.py --generate-report  # Check for orphaned tasks
```

---

## Queue Routing

### Task queues defined in apps/core/tasks/celery_settings.py

| Queue | Priority | Use For |
|-------|----------|---------|
| `critical` | 10 | Crisis alerts, security events |
| `high_priority` | 8 | User-facing operations |
| `email` | 7 | Email sending |
| `reports` | 6 | Report generation |
| `maintenance` | 3 | Cleanup, cache warming |

### Route tasks by domain

```python
# In celery_settings.py (already configured)
CELERY_TASK_ROUTES = {
    'send_reminder_email': {'queue': 'email'},
    'create_scheduled_reports': {'queue': 'reports'},
    'auto_close_jobs': {'queue': 'critical'},
}
```

---

## Verification Commands

### Audit all tasks for duplicates and issues

```bash
python scripts/audit_celery_tasks.py --generate-report --output CELERY_TASK_INVENTORY_REPORT.md
```

### Show only duplicates

```bash
python scripts/audit_celery_tasks.py --duplicates-only
```

### Validate beat schedule (comprehensive)

```bash
python manage.py validate_schedules --verbose
```

### Check for specific issues

```bash
python manage.py validate_schedules --check-duplicates          # Duplicate schedules
python manage.py validate_schedules --check-hotspots            # Overloaded time slots
python manage.py validate_schedules --check-idempotency         # Duplicate execution
python manage.py validate_schedules --check-orphaned-tasks      # Beat → task mapping ✨ NEW
```

### Orphaned task detection (prevents runtime failures)

```bash
# Validates that ALL beat schedule tasks are registered
# CRITICAL: Orphaned tasks cause Celery beat scheduler to fail silently
python manage.py validate_schedules --check-orphaned-tasks --verbose
```

---

## Orphaned Task Prevention (Oct 2025)

### Problem
Beat schedule references tasks that don't exist → silent failures

### Solution
Automated validation on every commit (pre-commit hook)

### Command
```bash
python manage.py validate_schedules --check-orphaned-tasks
```

### Integration
`.pre-commit-config.yaml` blocks commits with orphaned tasks

---

## Common Violations and Fixes

### 1. Duplicate Task Definitions

**❌ WRONG: Same task in multiple files**

```python
# background_tasks/tasks.py
@shared_task(name="send_reminder_email")
def send_reminder_email(user_id):
    pass

# background_tasks/email_tasks.py
@shared_task(name="send_reminder_email")  # ❌ Duplicate!
def send_reminder_email(user_id):
    pass
```

**✅ FIX: Keep ONE implementation, import in god file**

```python
# background_tasks/email_tasks.py (canonical)
@shared_task(name="send_reminder_email")
def send_reminder_email(user_id):
    pass

# background_tasks/tasks.py (import aggregator)
from background_tasks.email_tasks import send_reminder_email  # ✅ Import only
```

### 2. Mixed Decorators in Same File

**❌ WRONG: Mixing @app.task and @shared_task**

```python
from intelliwiz_config.celery import app
from celery import shared_task

@app.task  # ❌ Wrong decorator
def task_one():
    pass

@shared_task  # ✅ Correct decorator
def task_two():
    pass
```

**✅ FIX: Use @shared_task consistently**

```python
from celery import shared_task

@shared_task  # ✅ Consistent
def task_one():
    pass

@shared_task  # ✅ Consistent
def task_two():
    pass
```

### 3. Task Name with Parentheses

**❌ WRONG: Parentheses in task name**

```python
@shared_task(name="create_job()")  # ❌ Beat won't find it
def create_job(jobids=None):
    pass
```

**✅ FIX: Remove parentheses**

```python
@shared_task(name="create_job")  # ✅ Beat will find it
def create_job(jobids=None):
    pass
```

---

## Current State (2025-10-10)

### Statistics

- Total tasks: 94 unique (130 definitions)
- Duplicates: 29 tasks with multiple implementations
- God file: `background_tasks/tasks.py` (2,320 lines, 26/34 duplicates)
- @shared_task usage: 108/130 (83%)
- @app.task usage: 22/130 (17% - needs migration)

### Target State

- ✅ Single Celery config (achieved)
- ✅ Centralized reusable components (achieved)
- 🔄 Zero duplicate implementations (in progress)
- 🔄 >95% @shared_task usage (in progress)
- 🔄 God file < 300 lines (import aggregator only)

---

**Last Updated**: October 29, 2025
**Maintainer**: Backend Team
**Related**: [Idempotency Framework](IDEMPOTENCY_FRAMEWORK.md), [Background Processing](BACKGROUND_PROCESSING.md)
