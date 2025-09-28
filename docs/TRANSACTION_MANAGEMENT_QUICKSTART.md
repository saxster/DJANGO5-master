# Transaction Management Quick Start Guide

Quick reference for implementing atomic transactions in Django views.

**Compliance:** .claude/rules.md - Rule #17

---

## 🚀 Quick Patterns

### Pattern 1: Simple Form Save (90% of cases)

```python
from django.db import transaction
from apps.core.utils_new.db_utils import get_current_db_name

def handle_valid_form(self, form, request, create):
    try:
        with transaction.atomic(using=get_current_db_name()):
            obj = form.save()
            putils.save_userinfo(obj, request.user, request.session)
            return JsonResponse({'pk': obj.id})
    except IntegrityError:
        return handle_intergrity_error("ModelName")
```

### Pattern 2: Multi-Step Operation

```python
def handle_valid_form(self, form, request, create):
    try:
        with transaction.atomic(using=get_current_db_name()):
            # Step 1: Save main object
            obj = form.save(commit=False)
            obj.uuid = request.POST.get("uuid")

            # Step 2: Save user info
            obj = putils.save_userinfo(obj, request.user, request.session)

            # Step 3: Create related records
            for item in data_list:
                RelatedModel.objects.create(parent=obj, **item)

            # Step 4: Add audit trail
            obj.add_history()

            # Success log BEFORE commit
            logger.info(f"Object created: {obj.id}")

            # Celery tasks AFTER commit
            send_notification.delay(obj.id)

            return JsonResponse({'pk': obj.id})
    except IntegrityError:
        return handle_intergrity_error("ModelName")
```

### Pattern 3: With Distributed Lock (concurrent access)

```python
from apps.core.utils_new.distributed_locks import with_lock_and_transaction

@with_lock_and_transaction('JOB_WORKFLOW_UPDATE', 'job_id')
def update_job_status(self, job_id, new_status):
    job = Job.objects.select_for_update().get(id=job_id)
    job.status = new_status
    job.save()
    # Lock + transaction handled automatically
```

---

## ✅ Checklist

For every `handle_valid_form` method:

- [ ] Imports `transaction` and `get_current_db_name`
- [ ] Wraps all database operations in `transaction.atomic()`
- [ ] Uses correct database alias: `using=get_current_db_name()`
- [ ] Has try/except with specific exception types
- [ ] Logs success BEFORE transaction commits
- [ ] Schedules async tasks AFTER transaction logic
- [ ] Returns proper error response on IntegrityError

---

## ❌ Common Mistakes

### Mistake 1: Missing transaction wrapper
```python
def handle_valid_form(self, form, request, create):
    obj = form.save()
    putils.save_userinfo(obj, request.user, request.session)
    return JsonResponse({'pk': obj.id})
```

**Problem:** If save_userinfo fails, obj remains in database without user metadata.

### Mistake 2: Wrong database alias
```python
with transaction.atomic():  # ❌ Uses 'default', not tenant database
    obj.save()
```

**Fix:**
```python
with transaction.atomic(using=get_current_db_name()):  # ✅ Correct
    obj.save()
```

### Mistake 3: Logging after transaction
```python
with transaction.atomic(using=get_current_db_name()):
    obj.save()
logger.info(f"Object created: {obj.id}")  # ❌ After transaction
```

**Fix:**
```python
with transaction.atomic(using=get_current_db_name()):
    obj.save()
    logger.info(f"Object created: {obj.id}")  # ✅ Before commit
```

### Mistake 4: Celery task inside transaction
```python
with transaction.atomic(using=get_current_db_name()):
    obj.save()
    send_email.delay(obj.id)  # ❌ Email sent even if transaction rolls back
```

**Fix:**
```python
with transaction.atomic(using=get_current_db_name()):
    obj.save()
    logger.info(f"Object created: {obj.id}")
send_email.delay(obj.id)  # ✅ After transaction commits
```

---

## 🔧 Troubleshooting

### Pre-commit Hook Blocks Commit

**Error:**
```
❌ TRANSACTION VALIDATION FAILED
apps/myapp/views.py:142 - handle_valid_form must use transaction.atomic
```

**Fix:**
1. Open the file and go to the line number
2. Wrap the method body with `transaction.atomic`
3. Add imports at top of file
4. Re-stage and commit

### Transaction Deadlock

**Error:**
```
DeadlockDetected: deadlock detected
```

**Fix:**
```python
# Always acquire locks in consistent order
lock_keys = sorted([lock_key_1, lock_key_2])  # Sort to ensure order
for key in lock_keys:
    with distributed_lock(key):
        # Critical section
```

### Nested Transaction Overhead

**Issue:** Too many savepoints slow down operation

**Fix:**
```python
# Don't add transaction.atomic if already inside one
# Check if in transaction first
from django.db import connection
if connection.in_atomic_block:
    obj.save()
else:
    with transaction.atomic(using=get_current_db_name()):
        obj.save()
```

---

## 📚 Resources

**Documentation:**
- `TRANSACTION_MANAGEMENT_REMEDIATION_COMPLETE.md` - Full implementation details
- `.claude/rules.md` - Rule #17: Transaction Management
- `apps/core/services/transaction_manager.py` - Transaction utilities

**Tests:**
- `apps/core/tests/test_transaction_management.py` - Rollback tests
- `apps/core/tests/test_transaction_race_conditions.py` - Concurrency tests

**Monitoring:**
- Dashboard: `/admin/transaction-health/`
- API: `/api/transaction-health/?action=health_summary`

**Support:**
- Check transaction health dashboard for failures
- Review `TransactionFailureLog` for error details
- Use correlation_id to trace failures end-to-end

---

**Last Updated:** September 27, 2025
**Version:** 1.0