# Race Condition - Command Reference Card

**Quick reference for testing, validation, and deployment**

---

## 🧪 Testing Commands

### Validate All Fixes
```bash
python3 validate_race_condition_fixes.py
```
**Expected:** 21/21 checks PASSED

---

### Run Race Condition Tests
```bash
# All race condition tests
python3 -m pytest -k "race" -v

# Background task tests
python3 -m pytest apps/core/tests/test_background_task_race_conditions.py -v

# Ticket escalation tests
python3 -m pytest apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py -v

# JSON field update tests
python3 -m pytest apps/core/tests/test_atomic_json_field_updates.py -v

# Job workflow tests (existing)
python3 -m pytest apps/activity/tests/test_job_race_conditions.py -v

# Attendance tests (existing)
python3 -m pytest apps/attendance/tests/test_race_conditions.py -v
```
**Expected:** 41 tests total, all PASSED

---

### Run Penetration Tests
```bash
# All attack scenarios
python3 comprehensive_race_condition_penetration_test.py --scenario all

# Individual scenarios
python3 comprehensive_race_condition_penetration_test.py --scenario autoclose
python3 comprehensive_race_condition_penetration_test.py --scenario checkpoints
python3 comprehensive_race_condition_penetration_test.py --scenario escalation
python3 comprehensive_race_condition_penetration_test.py --scenario ticket_log
python3 comprehensive_race_condition_penetration_test.py --scenario json_updates
python3 comprehensive_race_condition_penetration_test.py --scenario combined
```
**Expected:** All scenarios PASSED, 0 errors

---

## 🗄️ Migration Commands

### Apply Migrations (IN ORDER!)
```bash
# Step 1: Jobneed version field
python3 manage.py migrate activity 0010_add_version_field_jobneed

# Step 2: Ticket version field
python3 manage.py migrate y_helpdesk 0002_add_version_field_ticket

# Step 3: Audit log table
python3 manage.py migrate activity 0011_add_job_workflow_audit_log
```

### Check Migration Status
```bash
python3 manage.py showmigrations activity y_helpdesk
```

### View Migration SQL
```bash
python3 manage.py sqlmigrate activity 0010
python3 manage.py sqlmigrate y_helpdesk 0002
python3 manage.py sqlmigrate activity 0011
```

### Rollback (Emergency Only!)
```bash
python3 manage.py migrate activity 0009
python3 manage.py migrate y_helpdesk 0001
```

---

## 📝 Documentation Commands

### View Summary Banner
```bash
cat RACE_CONDITION_COMPLETION_BANNER.txt
```

### List All Documentation
```bash
ls -1 RACE_CONDITION*.md docs/RACE_CONDITION*.md
```

### Quick Reference
```bash
# 5-minute quick start
less RACE_CONDITION_QUICK_START.md

# Complete developer guide
less docs/RACE_CONDITION_PREVENTION_GUIDE.md

# Deployment checklist
less RACE_CONDITION_DEPLOYMENT_CHECKLIST.md
```

---

## 🔍 Verification Commands

### Check File Existence
```bash
# New utilities
test -f apps/core/utils_new/atomic_json_updater.py && echo "✓ AtomicJSONFieldUpdater"
test -f apps/core/utils_new/retry_mechanism.py && echo "✓ Retry Mechanism"
test -f apps/core/mixins/optimistic_locking.py && echo "✓ Optimistic Locking"

# New services
test -f apps/y_helpdesk/services/ticket_workflow_service.py && echo "✓ TicketWorkflowService"
test -f apps/activity/models/job_workflow_audit_log.py && echo "✓ JobWorkflowAuditLog"

# Migrations
test -f apps/activity/migrations/0010_add_version_field_jobneed.py && echo "✓ Jobneed version"
test -f apps/y_helpdesk/migrations/0002_add_version_field_ticket.py && echo "✓ Ticket version"
test -f apps/activity/migrations/0011_add_job_workflow_audit_log.py && echo "✓ Audit log"
```

### Count Lines of Code
```bash
wc -l apps/core/utils_new/atomic_json_updater.py \
      apps/core/utils_new/retry_mechanism.py \
      apps/core/mixins/optimistic_locking.py \
      apps/y_helpdesk/services/ticket_workflow_service.py \
      apps/activity/models/job_workflow_audit_log.py
```

---

## 🛠️ Development Commands

### Use AtomicJSONFieldUpdater
```python
from apps.core.utils_new.atomic_json_updater import AtomicJSONFieldUpdater

AtomicJSONFieldUpdater.update_json_field(
    model_class=Jobneed,
    instance_id=job_id,
    field_name='other_info',
    updates={'processed': True}
)
```

### Use JobWorkflowService
```python
from apps.activity.services import JobWorkflowService

JobWorkflowService.transition_jobneed_status(
    jobneed_id=job_id,
    new_status='COMPLETED',
    user=request.user
)
```

### Use TicketWorkflowService
```python
from apps.y_helpdesk.services import TicketWorkflowService

TicketWorkflowService.escalate_ticket(
    ticket_id=ticket_id,
    user=request.user
)
```

### Use Retry Mechanism
```python
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(max_retries=3, retry_policy='LOCK_ACQUISITION')
def my_function():
    # Automatically retries on failure
    pass
```

---

## 📊 Monitoring Commands (Future)

### Check Audit Log
```python
from apps.activity.models import JobWorkflowAuditLog

# Recent status changes
JobWorkflowAuditLog.objects.filter(
    operation_type='STATUS_CHANGE'
).order_by('-change_timestamp')[:10]

# Slow lock acquisitions
JobWorkflowAuditLog.objects.filter(
    lock_acquisition_time_ms__gte=100
).order_by('-lock_acquisition_time_ms')[:10]
```

### Check Lock Stats
```python
from apps.core.utils_new.distributed_locks import LockMonitor

LockMonitor.get_lock_stats()
```

---

## 🎯 Quick Validation

**One-Line Validation:**
```bash
python3 validate_race_condition_fixes.py && echo "✅ ALL CHECKS PASSED"
```

**One-Line Test:**
```bash
python3 -m pytest -k "race" -v --tb=short || echo "❌ TESTS FAILED"
```

**One-Line Migration Check:**
```bash
python3 manage.py showmigrations activity y_helpdesk | grep -E "(0010|0011|0002)"
```

---

## 📞 Quick Help

**I want to:**
- **Understand race conditions** → Read `RACE_CONDITION_QUICK_START.md`
- **Deploy fixes** → Follow `RACE_CONDITION_DEPLOYMENT_CHECKLIST.md`
- **Write safe code** → Use utilities in `apps/core/utils_new/`
- **Debug issues** → Query `JobWorkflowAuditLog` model
- **Run tests** → `python3 -m pytest -k "race" -v`

---

**Reference Card Version:** 1.0
**Last Updated:** 2025-09-27