# Decision Tree: Which Celery Decorator?

**Quick guide for choosing the right task decorator**

---

## Decision Flow

```
┌─────────────────────────────┐
│  Creating a new Celery task? │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ Step 1: Check if task already exists        │
│                                              │
│ Command:                                     │
│   python scripts/audit_celery_tasks.py \    │
│          --duplicates-only                   │
└──────────────┬──────────────────────────────┘
               │
               ▼
       ┌───────┴───────┐
       │               │
       ▼               ▼
 Duplicate found?   Not found
       │               │
       │               ▼
       │      ┌─────────────────────┐
       │      │ Step 2: Need         │
       │      │ idempotency?         │
       │      └──────┬──────────────┘
       │             │
       │      ┌──────┴──────┐
       │      │             │
       │      ▼             ▼
       │    YES           NO
       │     │             │
       │     │             │
       ▼     ▼             ▼
   ┌─────────────┐  ┌────────────┐
   │ Use existing│  │ @shared_   │
   │ implementa- │  │  task(     │
   │ tion from   │  │   base=    │
   │ modern file │  │   Idempotent│
   │             │  │   Task)     │
   └─────────────┘  └─────┬──────┘
                          │
                          └──────────┐
                                     │
                          ┌──────────▼─────────┐
                          │  @shared_task      │
                          │  (standard)        │
                          └────────────────────┘
```

## Quick Reference Table

| Scenario | Decorator | Example |
|----------|-----------|---------|
| **Standard task** | `@shared_task` | Email sending, notifications |
| **Prevent duplicates** | `@shared_task(base=IdempotentTask)` | Auto-close jobs, scheduled reports |
| **Email-specific** | `@shared_task(base=EmailTask)` | Email with retry policy |
| **Long-running report** | `@shared_task(base=ReportTask)` | ML processing, analytics |
| **Low-priority cleanup** | `@shared_task(base=MaintenanceTask)` | Cache warming, old data cleanup |
| **External API call** | `@shared_task(base=ExternalAPITask)` | Third-party webhooks |

## Code Examples

### Standard Task

```python
from celery import shared_task

@shared_task
def send_notification(user_id, message):
    """Send notification to user"""
    # Implementation
    pass
```

### Idempotent Task (Prevent Duplicates)

```python
from celery import shared_task
from apps.core.tasks.base import IdempotentTask

@shared_task(base=IdempotentTask, bind=True)
def auto_close_jobs(self):
    """Auto-close expired jobs (runs every 4h, prevent duplicates)"""
    # Automatic duplicate prevention via idempotency framework
    pass
```

### Email Task (Special Retry Policy)

```python
from celery import shared_task
from apps.core.tasks.base import EmailTask

@shared_task(base=EmailTask, bind=True)
def send_reminder_email(self, user_id):
    """Send reminder with email-specific error handling"""
    # 5 retries, short backoff
    pass
```

## Common Mistakes

### ❌ Mistake 1: Using @app.task

```python
from intelliwiz_config.celery import app  # ❌ WRONG

@app.task  # ❌ WRONG - couples to specific app
def my_task():
    pass
```

**Fix:** Use `@shared_task` instead

### ❌ Mistake 2: Task Name with Parentheses

```python
@shared_task(name="create_job()")  # ❌ Beat won't find it
def create_job():
    pass
```

**Fix:** Remove parentheses: `name="create_job"`

### ❌ Mistake 3: Not Checking for Duplicates

**Before creating:** Always run audit script!

```bash
python scripts/audit_celery_tasks.py --duplicates-only
```

---

**See also:** [CELERY.md](../CELERY.md) - Complete Celery configuration guide
