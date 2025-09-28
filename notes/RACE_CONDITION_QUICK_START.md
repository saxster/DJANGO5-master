# Race Condition Prevention - Quick Start Guide

**5-Minute Guide for Developers**

---

## 🚀 TL;DR

**Rule:** Never modify objects without proper locking in concurrent environments.

**Solution:** Use our utilities (it's easier than doing it wrong!).

---

## ⚡ Quick Examples

### Scenario 1: Update JSON Field

**❌ DON'T:**
```python
job = Jobneed.objects.get(pk=job_id)
job.other_info['processed'] = True  # RACE CONDITION!
job.save()
```

**✅ DO:**
```python
from apps.core.utils_new.atomic_json_updater import AtomicJSONFieldUpdater

AtomicJSONFieldUpdater.update_json_field(
    Jobneed, job_id, 'other_info', {'processed': True}
)
```

---

### Scenario 2: Change Job Status

**❌ DON'T:**
```python
job = Jobneed.objects.get(pk=job_id)
job.jobstatus = 'COMPLETED'  # RACE CONDITION!
job.save()
```

**✅ DO:**
```python
from apps.activity.services import JobWorkflowService

JobWorkflowService.transition_jobneed_status(
    job_id, 'COMPLETED', request.user
)
```

---

### Scenario 3: Increment Counter

**❌ DON'T:**
```python
ticket = Ticket.objects.get(pk=ticket_id)
ticket.level += 1  # RACE CONDITION!
ticket.save()
```

**✅ DO:**
```python
from django.db.models import F

Ticket.objects.filter(pk=ticket_id).update(
    level=F('level') + 1
)
```

---

### Scenario 4: Append to History Log

**❌ DON'T:**
```python
ticket = Ticket.objects.get(pk=ticket_id)
ticket.ticketlog['history'].append(item)  # RACE CONDITION!
ticket.save()
```

**✅ DO:**
```python
from apps.y_helpdesk.services import TicketWorkflowService

TicketWorkflowService.append_history_entry(
    ticket_id, history_item
)
```

---

## 🛠️ When Do I Need Protection?

### ✅ YES - You Need Locking:

- Modifying JSONField values (`other_info`, `ticketlog`, `peventlogextras`)
- Changing status fields (`jobstatus`, `ticket.status`)
- Updating parent AND child records together
- Incrementing counters (`level`, `counter`, `count`)
- Appending to JSON arrays
- Multi-step operations that must succeed together

### ❌ NO - Simple Operations:

- Read-only queries (`filter()`, `get()`, `values()`)
- Single atomic update with F(): `Model.objects.filter(...).update(field=F('field') + 1)`
- Creating new records (if no duplicate checking needed)
- Simple field updates with no related changes

---

## 🎯 Which Tool Do I Use?

```
┌─────────────────────────────────────────┬──────────────────────────┐
│ Operation Type                          │ Tool to Use              │
├─────────────────────────────────────────┼──────────────────────────┤
│ Update JSON field                       │ AtomicJSONFieldUpdater   │
│ Change job/jobneed status               │ JobWorkflowService       │
│ Change ticket status                    │ TicketWorkflowService    │
│ Escalate ticket                         │ TicketWorkflowService    │
│ Update parent + child together          │ JobWorkflowService       │
│ Append to history/audit log             │ TicketWorkflowService    │
│ Increment counter                       │ F() expression           │
│ Custom complex operation                │ distributed_lock + ...   │
│ Retry on failures                       │ @with_retry              │
└─────────────────────────────────────────┴──────────────────────────┘
```

---

## 📝 Code Templates

### Template 1: Safe JSON Update
```python
from apps.core.utils_new.atomic_json_updater import AtomicJSONFieldUpdater

def update_job_metadata(job_id):
    AtomicJSONFieldUpdater.update_json_field(
        model_class=Jobneed,
        instance_id=job_id,
        field_name='other_info',
        updates={
            'processed': True,
            'processed_at': str(timezone.now()),
            'processed_by': user.id
        }
    )
```

---

### Template 2: Safe Status Transition
```python
from apps.activity.services import JobWorkflowService

def complete_job(job_id, user):
    job = JobWorkflowService.transition_jobneed_status(
        jobneed_id=job_id,
        new_status='COMPLETED',
        user=user,
        validate_transition=True  # Ensures valid state machine
    )
    return job
```

---

### Template 3: Safe Escalation
```python
from apps.y_helpdesk.services import TicketWorkflowService

def escalate_to_manager(ticket_id, manager_id, user):
    ticket = TicketWorkflowService.escalate_ticket(
        ticket_id=ticket_id,
        assigned_person_id=manager_id,
        user=user
    )
    return ticket
```

---

### Template 4: Custom Operation with Locking
```python
from django.db import transaction
from apps.core.utils_new.distributed_locks import distributed_lock

def custom_operation(resource_id):
    lock_key = f"operation:{resource_id}"

    with distributed_lock(lock_key, timeout=10):
        with transaction.atomic():
            obj = Model.objects.select_for_update().get(pk=resource_id)

            # Your custom logic here
            obj.field1 = calculate_value()
            obj.field2 = another_value()

            obj.save(update_fields=['field1', 'field2'])

            return obj
```

---

### Template 5: With Automatic Retry
```python
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(max_retries=3, retry_policy='LOCK_ACQUISITION')
def reliable_update(resource_id):
    # This will automatically retry if lock acquisition fails
    with distributed_lock(f"resource:{resource_id}"):
        # Your update logic
        pass
```

---

## 🧪 Testing Template

```python
import pytest
import threading
from django.test import TransactionTestCase

@pytest.mark.django_db(transaction=True)
class TestMyRaceCondition(TransactionTestCase):

    def test_concurrent_updates(self):
        # Setup
        obj = MyModel.objects.create(...)

        errors = []

        def worker(worker_id):
            try:
                # Your concurrent operation
                update_function(obj.id)
            except Exception as e:
                errors.append((worker_id, e))

        # Execute
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        obj.refresh_from_db()
        self.assertEqual(obj.field, expected_value)
```

---

## 🎓 Learn More

**Essential Reading:**
1. `docs/RACE_CONDITION_PREVENTION_GUIDE.md` - Complete developer guide (30 min read)
2. `.claude/rules.md` - Code quality and security rules (15 min read)

**Code Examples:**
1. `background_tasks/utils.py` - See fixed functions for real-world examples
2. `apps/y_helpdesk/services/ticket_workflow_service.py` - Service layer pattern
3. `apps/core/utils_new/atomic_json_updater.py` - Utility usage examples

**Test Examples:**
1. `apps/core/tests/test_background_task_race_conditions.py` - Test patterns
2. `comprehensive_race_condition_penetration_test.py` - Attack scenarios

---

## ⚠️ Common Mistakes

### Mistake 1: "It's a quick update, I don't need locking"
**Reality:** Race conditions happen in microseconds, not minutes.
**Fix:** Always use proper locking, performance overhead is minimal (<10ms).

### Mistake 2: "I'll just use filter().update(), it's atomic"
**Reality:** filter().update() is atomic for single field, but not for complex logic.
**Fix:** Use service layer or distributed lock + select_for_update.

### Mistake 3: "I tested it and it works"
**Reality:** Race conditions are timing-dependent, may not appear in single-threaded tests.
**Fix:** Write tests with 10+ concurrent threads.

### Mistake 4: "Transactions are enough"
**Reality:** Transactions prevent corruption but don't prevent concurrent modifications.
**Fix:** Use locks + transactions together.

---

## 🏁 Checklist Before Committing

When modifying job/ticket workflow code, verify:

- [ ] No direct modification of JSON fields without `AtomicJSONFieldUpdater`
- [ ] No `obj.counter += 1` patterns (use `F('counter') + 1`)
- [ ] Status changes use service layer (JobWorkflowService or TicketWorkflowService)
- [ ] Multi-step operations wrapped in `transaction.atomic()`
- [ ] Critical sections use `distributed_lock()` + `select_for_update()`
- [ ] Specific exception handling (no bare `except Exception:`)
- [ ] Tests include concurrent scenario (10+ threads)
- [ ] Docstring explains locking strategy

---

## 💬 Quick Q&A

**Q: What if I get LockAcquisitionError?**
A: Normal under heavy load. Use `@with_retry` decorator to auto-retry.

**Q: What if I get StaleObjectError?**
A: Another process modified the object. Use `@with_optimistic_lock` to auto-retry.

**Q: Do I always need distributed locks?**
A: For cross-process coordination (background tasks, multi-server), yes. For single-process, row-level locking may be sufficient.

**Q: Can I use filter().update() instead of save()?**
A: Yes, for simple atomic updates. But for complex logic or JSON fields, use the utilities.

**Q: How do I debug lock issues?**
A: Query `JobWorkflowAuditLog` for operation history and lock acquisition times.

---

**Remember:** When in doubt, use the utilities. They're easier than getting it wrong!

---

**Quick Start Guide v1.0**
**Last Updated:** 2025-09-27