# Race Condition Prevention - Developer Guide

**Purpose:** Comprehensive guide for preventing race conditions in Django 5 enterprise platform
**Audience:** Backend developers, code reviewers, security team
**Last Updated:** 2025-09-27

---

## Table of Contents
1. [What Are Race Conditions?](#what-are-race-conditions)
2. [Common Race Condition Patterns](#common-patterns)
3. [Prevention Strategies](#prevention-strategies)
4. [Using the Framework](#using-the-framework)
5. [Testing for Race Conditions](#testing)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## What Are Race Conditions?

A **race condition** occurs when the correctness of a program depends on the relative timing of events, such as the order in which multiple threads or processes execute.

### Real-World Example from Our Codebase (BEFORE FIX):

```python
# VULNERABLE CODE - DO NOT USE
def update_job_status(job_id):
    job = Jobneed.objects.get(id=job_id)  # Thread 1 reads: status='ASSIGNED'
    # Thread 2 reads: status='ASSIGNED'
    # Thread 1 sets: status='INPROGRESS'
    job.jobstatus = 'INPROGRESS'
    # Thread 2 sets: status='COMPLETED' (overwrites Thread 1!)
    job.jobstatus = 'COMPLETED'
    job.save()  # Last write wins - Thread 1's update lost!
```

**Impact:** Lost status updates, data corruption, workflow failures.

---

## Common Race Condition Patterns

### Pattern 1: JSON Field Updates ⚠️ HIGH RISK

**Vulnerable:**
```python
obj = Jobneed.objects.get(pk=job_id)
obj.other_info['processed'] = True  # Read-modify-write!
obj.save()  # Concurrent updates will be lost
```

**Safe:**
```python
from apps.core.utils_new.atomic_json_updater import AtomicJSONFieldUpdater

AtomicJSONFieldUpdater.update_json_field(
    model_class=Jobneed,
    instance_id=job_id,
    field_name='other_info',
    updates={'processed': True}
)
```

---

### Pattern 2: Counter Increments ⚠️ HIGH RISK

**Vulnerable:**
```python
ticket = Ticket.objects.get(pk=ticket_id)
ticket.level = ticket.level + 1  # Not atomic!
ticket.save()
```

**Safe:**
```python
from django.db.models import F

Ticket.objects.filter(pk=ticket_id).update(
    level=F('level') + 1,  # Atomic!
    mdtz=timezone.now()
)
```

---

### Pattern 3: Status Transitions ⚠️ HIGH RISK

**Vulnerable:**
```python
job = Jobneed.objects.get(pk=job_id)
if job.status == 'ASSIGNED':  # TOCTOU vulnerability!
    job.status = 'INPROGRESS'
    job.save()
```

**Safe:**
```python
from apps.activity.services import JobWorkflowService

JobWorkflowService.transition_jobneed_status(
    jobneed_id=job_id,
    new_status='INPROGRESS',
    user=request.user,
    validate_transition=True
)
```

---

### Pattern 4: Parent-Child Updates ⚠️ CRITICAL

**Vulnerable:**
```python
child.expirytime = 45
child.save()

parent.mdtz = timezone.now()
parent.save()  # Race condition between these two saves!
```

**Safe:**
```python
from apps.activity.services import JobWorkflowService

JobWorkflowService.update_checkpoint_with_parent(
    child_id=child.id,
    updates={'expirytime': 45},
    parent_id=parent.id,
    user=request.user
)
```

---

## Prevention Strategies

### Strategy 1: Distributed Locks (Redis)

**When to Use:**
- Coordinating across multiple application servers
- JSON field updates
- Long-running operations

**How to Use:**
```python
from apps.core.utils_new.distributed_locks import distributed_lock

with distributed_lock(f"resource:{resource_id}", timeout=10):
    # Protected code
    update_resource(resource_id)
```

**Configuration:**
```python
from apps.core.utils_new.distributed_locks import LockRegistry

lock = LockRegistry.get_lock('ATTENDANCE_UPDATE', attendance_id)
with lock:
    # Protected code
```

---

### Strategy 2: Row-Level Locking (PostgreSQL)

**When to Use:**
- Within a single database transaction
- Ensuring exclusive access to specific rows
- Preventing dirty reads

**How to Use:**
```python
from django.db import transaction

with transaction.atomic():
    job = Jobneed.objects.select_for_update().get(pk=job_id)
    job.status = 'COMPLETED'
    job.save()  # No one else can modify this row during transaction
```

**Locking Modes:**
```python
# Exclusive lock (default)
obj = Model.objects.select_for_update().get(pk=id)

# Shared lock (allows other readers)
obj = Model.objects.select_for_update(of=('self',), nowait=False).get(pk=id)

# Fail fast if locked
obj = Model.objects.select_for_update(nowait=True).get(pk=id)
```

---

### Strategy 3: Optimistic Locking (Version Fields)

**When to Use:**
- Long-running user transactions
- Low contention scenarios
- When you want to detect conflicts rather than prevent them

**How to Use:**
```python
from apps.core.mixins.optimistic_locking import OptimisticLockingMixin, StaleObjectError

class MyModel(OptimisticLockingMixin, models.Model):
    version = models.IntegerField(default=0)
    # Other fields...

# Automatic version checking
try:
    obj = MyModel.objects.get(pk=id)
    obj.field = 'new value'
    obj.save()  # Raises StaleObjectError if modified concurrently
except StaleObjectError as e:
    # Retry or notify user
    pass
```

**With Automatic Retry:**
```python
from apps.core.mixins.optimistic_locking import with_optimistic_lock

@with_optimistic_lock
def update_model(model_id):
    obj = MyModel.objects.get(pk=model_id)
    obj.field = 'value'
    obj.save()  # Automatically retries on version conflict
```

---

### Strategy 4: Atomic F() Expressions

**When to Use:**
- Simple field updates
- Counter increments/decrements
- Timestamp updates

**Examples:**
```python
from django.db.models import F

# Counter increment (atomic)
Model.objects.filter(pk=id).update(
    counter=F('counter') + 1
)

# Conditional update (atomic)
Model.objects.filter(pk=id, status='PENDING').update(
    status='PROCESSING',
    started_at=timezone.now()
)

# Multiple field update (atomic)
Model.objects.filter(pk=id).update(
    processed=True,
    processed_at=timezone.now(),
    processed_by=F('assigned_to')
)
```

---

## Using the Framework

### Service Layer Pattern

**JobWorkflowService**
```python
from apps.activity.services import JobWorkflowService

# Status transition
JobWorkflowService.transition_jobneed_status(
    jobneed_id=job_id,
    new_status='COMPLETED',
    user=request.user
)

# Parent-child update
JobWorkflowService.update_checkpoint_with_parent(
    child_id=checkpoint_id,
    updates={'expirytime': 45},
    parent_id=parent_id,
    user=request.user
)

# Bulk updates
JobWorkflowService.bulk_update_child_checkpoints(
    parent_id=parent_id,
    child_updates=[{'id': 1, 'expirytime': 30}, ...],
    user=request.user
)
```

**TicketWorkflowService**
```python
from apps.y_helpdesk.services import TicketWorkflowService

# Status transition
TicketWorkflowService.transition_ticket_status(
    ticket_id=ticket_id,
    new_status='RESOLVED',
    user=request.user,
    comments='Issue resolved'
)

# Escalation
TicketWorkflowService.escalate_ticket(
    ticket_id=ticket_id,
    assigned_person_id=manager_id,
    user=request.user
)

# History update
TicketWorkflowService.append_history_entry(
    ticket_id=ticket_id,
    history_item={'action': 'updated', 'details': [...]}
)
```

---

### Atomic JSON Field Updates

**Simple Update:**
```python
from apps.core.utils_new.atomic_json_updater import AtomicJSONFieldUpdater

AtomicJSONFieldUpdater.update_json_field(
    model_class=Jobneed,
    instance_id=job_id,
    field_name='other_info',
    updates={'processed': True, 'count': 42}
)
```

**Append to Array:**
```python
AtomicJSONFieldUpdater.append_to_json_array(
    model_class=Ticket,
    instance_id=ticket_id,
    field_name='ticketlog',
    array_key='ticket_history',
    item={'action': 'updated', 'when': str(timezone.now())}
)
```

**Custom Update Function:**
```python
def complex_update(json_data):
    json_data['counter'] = json_data.get('counter', 0) + 1
    json_data['last_updated'] = str(timezone.now())
    if json_data['counter'] > 10:
        json_data['alert'] = True
    return json_data

AtomicJSONFieldUpdater.update_with_function(
    model_class=Jobneed,
    instance_id=job_id,
    field_name='other_info',
    update_func=complex_update
)
```

**Context Manager (Advanced):**
```python
from apps.core.utils_new.atomic_json_updater import update_json_field_safely

with update_json_field_safely(Jobneed, job_id, 'other_info') as json_data:
    json_data['processed'] = True
    json_data['metadata']['steps'].append('validation')
    json_data['counter'] += 1
# Changes automatically saved on context exit
```

---

### Retry Mechanism

**Basic Retry:**
```python
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(max_retries=3)
def update_critical_data(job_id):
    # Will automatically retry on transient errors
    job = Jobneed.objects.get(pk=job_id)
    job.status = 'COMPLETED'
    job.save()
```

**Lock-Specific Retry:**
```python
from apps.core.utils_new.retry_mechanism import retry_on_lock_failure

@retry_on_lock_failure(max_retries=4)
def acquire_and_update(resource_id):
    with distributed_lock(f"resource:{resource_id}"):
        # Will retry if lock acquisition fails
        update_resource(resource_id)
```

**Custom Retry Policy:**
```python
@with_retry(
    exceptions=(LockAcquisitionError, DatabaseError),
    max_retries=5,
    retry_policy='AGGRESSIVE'
)
def critical_operation():
    # Custom retry behavior
    pass
```

---

## Testing for Race Conditions

### Writing Race Condition Tests

**Basic Pattern:**
```python
import pytest
import threading
from django.test import TransactionTestCase

@pytest.mark.django_db(transaction=True)
class TestMyRaceCondition(TransactionTestCase):

    def test_concurrent_updates(self):
        # Create test data
        obj = MyModel.objects.create(...)

        errors = []

        def worker(worker_id):
            try:
                # Attempt concurrent operation
                update_function(obj.id)
            except Exception as e:
                errors.append((worker_id, e))

        # Spawn multiple threads
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors and correct final state
        self.assertEqual(len(errors), 0)
        obj.refresh_from_db()
        self.assertEqual(obj.expected_field, expected_value)
```

---

### Running Tests

**All Race Condition Tests:**
```bash
python -m pytest -m race_condition -v
```

**Specific Test Files:**
```bash
pytest apps/core/tests/test_background_task_race_conditions.py -v
pytest apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py -v
pytest apps/core/tests/test_atomic_json_field_updates.py -v
```

**Penetration Tests:**
```bash
python comprehensive_race_condition_penetration_test.py --scenario all
python comprehensive_race_condition_penetration_test.py --scenario autoclose
```

---

## Best Practices

### ✅ DO:

1. **Use Service Layer for Workflow Operations**
   ```python
   # Good
   JobWorkflowService.transition_jobneed_status(...)

   # Bad
   job.status = 'COMPLETED'
   job.save()
   ```

2. **Use Atomic Updates for JSON Fields**
   ```python
   # Good
   AtomicJSONFieldUpdater.update_json_field(...)

   # Bad
   obj.other_info['key'] = 'value'
   obj.save()
   ```

3. **Use F() Expressions for Counters**
   ```python
   # Good
   Model.objects.filter(pk=id).update(counter=F('counter') + 1)

   # Bad
   obj.counter += 1
   obj.save()
   ```

4. **Lock Critical Sections**
   ```python
   # Good
   with distributed_lock(f"operation:{id}"):
       with transaction.atomic():
           obj = Model.objects.select_for_update().get(pk=id)
           obj.update_critical_field()
           obj.save()
   ```

5. **Test Concurrent Scenarios**
   - Write tests with 10+ concurrent threads
   - Verify no data loss
   - Check for timing-dependent failures

---

### ❌ DON'T:

1. **Never Use filter().update() for Critical State**
   ```python
   # Dangerous
   Jobneed.objects.filter(pk=id).update(jobstatus='COMPLETED')
   # Use service layer instead
   ```

2. **Never Modify JSON Fields Directly**
   ```python
   # Dangerous
   obj.other_info['key'] = 'value'
   obj.save()
   # Use AtomicJSONFieldUpdater instead
   ```

3. **Never Increment Counters with Python**
   ```python
   # Dangerous
   obj.level += 1
   obj.save()
   # Use F() expression instead
   ```

4. **Never Assume Single-Threaded Execution**
   - Background tasks run concurrently
   - Multiple web servers handle requests
   - Mobile apps sync simultaneously

5. **Never Skip Locking for "Quick Updates"**
   - Race conditions happen in microseconds
   - Even simple updates need protection
   - Performance overhead is minimal (<10ms)

---

## Troubleshooting

### Symptom: Lock Acquisition Timeout

**Error:**
```
LockTimeoutError: Failed to acquire lock 'autoclose_job:123' within 10s
```

**Causes:**
1. Another process holding lock too long
2. Deadlock between locks
3. System under heavy load

**Solutions:**
```python
# Increase timeout
with distributed_lock(key, timeout=30):  # Longer timeout
    ...

# Use retry mechanism
@retry_on_lock_failure(max_retries=5)
def my_operation():
    ...

# Check lock monitor
from apps.core.utils_new.distributed_locks import LockMonitor
LockMonitor.get_lock_stats()
```

---

### Symptom: StaleObjectError (Optimistic Lock Conflict)

**Error:**
```
StaleObjectError: Jobneed(123) was modified concurrently. Expected version 5, found 7
```

**Cause:** Another process modified the object between read and save.

**Solutions:**
```python
# Automatic retry
from apps.core.mixins.optimistic_locking import with_optimistic_lock

@with_optimistic_lock  # Retries up to 3 times
def update_job(job_id):
    job = Jobneed.objects.get(pk=job_id)
    job.status = 'COMPLETED'
    job.save()

# Manual retry
max_retries = 3
for attempt in range(max_retries):
    try:
        obj = Model.objects.get(pk=id)
        obj.field = 'value'
        obj.save()
        break
    except StaleObjectError:
        if attempt == max_retries - 1:
            raise
        time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
```

---

### Symptom: Data Loss in JSON Fields

**Observation:** Updates to `other_info` or `ticketlog` occasionally missing.

**Cause:** Concurrent updates without locking.

**Solution:**
```python
# Before (VULNERABLE)
obj = Jobneed.objects.get(pk=id)
obj.other_info['key'] = 'value'
obj.save()

# After (SAFE)
AtomicJSONFieldUpdater.update_json_field(
    model_class=Jobneed,
    instance_id=id,
    field_name='other_info',
    updates={'key': 'value'}
)
```

---

### Symptom: Inconsistent Counter Values

**Observation:** Ticket level doesn't match escalation count.

**Cause:** Non-atomic increment.

**Solution:**
```python
# Before (VULNERABLE)
ticket.level = ticket.level + 1
ticket.save()

# After (SAFE)
Ticket.objects.filter(pk=ticket_id).update(level=F('level') + 1)
```

---

## Quick Reference

### Distributed Lock Configurations

| Operation | Timeout | Blocking Timeout | Use Case |
|-----------|---------|------------------|----------|
| ATTENDANCE_UPDATE | 10s | 5s | Attendance records |
| JOB_WORKFLOW_UPDATE | 15s | 10s | Job status changes |
| TICKET_ESCALATION | 15s | 10s | Ticket escalations |
| JSON_FIELD_UPDATE | 10s | 5s | Generic JSON updates |

### Retry Policies

| Policy | Max Retries | Initial Delay | Backoff | Max Delay |
|--------|-------------|---------------|---------|-----------|
| DEFAULT | 3 | 0.1s | 2.0x | 5.0s |
| AGGRESSIVE | 5 | 0.05s | 1.5x | 3.0s |
| CONSERVATIVE | 2 | 0.5s | 2.5x | 10.0s |
| LOCK_ACQUISITION | 4 | 0.1s | 1.5x | 2.0s |

---

## Code Review Checklist

When reviewing code, verify:

- [ ] No direct `.save()` on objects fetched without locking
- [ ] No `obj.json_field['key'] = value` patterns
- [ ] No `obj.counter += 1` patterns (use F() expressions)
- [ ] Service layer used for workflow operations
- [ ] Distributed locks used for cross-process coordination
- [ ] `select_for_update()` used for critical reads
- [ ] `transaction.atomic()` wraps multi-step operations
- [ ] Specific exception handling (no bare `except Exception:`)
- [ ] Tests include concurrent scenarios (10+ threads)

---

## Additional Resources

- **Live Examples:** See `apps/activity/services/job_workflow_service.py`
- **Test Patterns:** See `apps/core/tests/test_background_task_race_conditions.py`
- **Distributed Locks:** See `apps/core/utils_new/distributed_locks.py`
- **Penetration Tests:** `comprehensive_race_condition_penetration_test.py`
- **Architecture Rules:** `.claude/rules.md`

---

## Getting Help

**Questions?** Contact:
- Backend Team: Architecture and implementation
- Security Team: Vulnerability assessment
- DevOps Team: Monitoring and performance

**Issues?**
- Check locks: `LockMonitor.get_lock_stats()`
- Check audit log: `JobWorkflowAuditLog.objects.filter(...)`
- Review metrics: Grafana dashboard

---

**Last Updated:** 2025-09-27
**Version:** 1.0
**Maintained By:** Backend Security Team