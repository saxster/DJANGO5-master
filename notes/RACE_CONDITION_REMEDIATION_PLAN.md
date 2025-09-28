# Race Condition Remediation Plan - Attendance System
## CVSS 8.5 - Critical Severity

## Executive Summary

**Vulnerability:** Race conditions in face recognition verification updates can lead to:
- Lost verification data (verified_in/verified_out corruption)
- Counter corruption in verification statistics
- Data integrity violations (multiple primary embeddings)
- Inconsistent behavioral analytics
- Security bypass potential

**Impact:**
- High data corruption risk under concurrent load
- Verification results can be silently overwritten
- Statistics (verification counts, success rates) become unreliable
- Compliance issues with audit trail integrity

**Solution Approach:**
1. Database-level locking with `select_for_update()`
2. Atomic operations with F() expressions
3. Optimistic locking with version fields
4. Redis distributed locks for complex multi-model operations
5. Database constraints for invariant enforcement

---

## Vulnerability Analysis

### 1. PeopleEventlog.peventlogextras Race Condition
**File:** `apps/attendance/managers.py:121-219`
**CVSS Component:** 8.5

#### Current Vulnerable Code:
```python
def update_fr_results(self, result, uuid, peopleid, db):
    if obj := self.filter(uuid=uuid).using(db):  # No lock
        extras = obj[0].peventlogextras  # Read without lock

        if obj[0].punchintime and extras["distance_in"] is None:
            extras["verified_in"] = bool(result["verified"])
            extras["distance_in"] = result["distance"]
        elif obj[0].punchouttime and extras["distance_out"] is None:
            extras["verified_out"] = bool(result["verified"])
            extras["distance_out"] = result["distance"]

        obj[0].peventlogextras = extras  # Write without lock
        obj[0].save()  # Last write wins!
```

#### Attack Scenario:
```
Time  Thread A (Punch-in)              Thread B (Punch-out)
-------------------------------------------------------------------
T0    Read extras = {                  -
        "verified_in": False,
        "distance_in": None,
        "verified_out": False,
        "distance_out": None
      }

T1    -                                 Read extras = {
                                          "verified_in": False,
                                          "distance_in": None,
                                          "verified_out": False,
                                          "distance_out": None
                                        }

T2    extras["verified_in"] = True     -
      extras["distance_in"] = 0.2

T3    -                                 extras["verified_out"] = True
                                        extras["distance_out"] = 0.3

T4    Save: {                          -
        "verified_in": True,
        "distance_in": 0.2,
        "verified_out": False,
        "distance_out": None
      }

T5    -                                 Save: {
                                          "verified_in": False,  # LOST!
                                          "distance_in": None,   # LOST!
                                          "verified_out": True,
                                          "distance_out": 0.3
                                        }

Result: Thread A's verification data completely overwritten!
```

#### Root Causes:
1. **Check-Then-Act Pattern:** Reading and writing in separate steps
2. **No Row-Level Locking:** Concurrent reads see same initial state
3. **Optimistic Updates:** Assumes no concurrent modifications
4. **JSON Field Semantics:** Entire JSON replaced on save

---

### 2. FaceVerificationLog Counter Corruption
**File:** `apps/face_recognition/signals.py:104-140`
**CVSS Component:** 7.5

#### Current Vulnerable Code:
```python
@receiver(post_save, sender=FaceVerificationLog)
def handle_verification_logged(sender, instance, created, **kwargs):
    if created:
        if instance.verification_model:
            model = instance.verification_model
            model.verification_count = models.F('verification_count') + 1

            if instance.result == 'SUCCESS':  # Race here!
                model.successful_verifications = models.F('successful_verifications') + 1

            model.last_used = timezone.now()
            model.save(update_fields=['verification_count', 'successful_verifications', 'last_used'])
```

#### Problem:
While F() expressions are atomic for individual fields, the **conditional update** creates inconsistency:

```
Thread A: SUCCESS result
  - Prepares update_fields = ['verification_count', 'successful_verifications', 'last_used']
  - verification_count += 1, successful_verifications += 1

Thread B: FAILED result
  - Prepares update_fields = ['verification_count', 'last_used']
  - verification_count += 1

Both execute:
  - Thread A: UPDATE model SET verification_count = verification_count + 1,
                              successful_verifications = successful_verifications + 1,
                              last_used = '2025-09-27 10:00:00'
  - Thread B: UPDATE model SET verification_count = verification_count + 1,
                              last_used = '2025-09-27 10:00:01'

Result: last_used from Thread B overwrites Thread A's timestamp!
        Statistics may be off if save operations interleave incorrectly.
```

---

### 3. Primary Embedding TOCTOU (Time-Of-Check-Time-Of-Use)
**File:** `apps/face_recognition/signals.py:54-77`
**CVSS Component:** 7.0

#### Current Vulnerable Code:
```python
@receiver(post_save, sender=FaceEmbedding)
def handle_face_embedding_updated(sender, instance, created, **kwargs):
    if created:
        existing_primary = FaceEmbedding.objects.filter(
            user=instance.user,
            is_primary=True
        ).exclude(id=instance.id).exists()  # Check

        if not existing_primary:
            instance.is_primary = True
            instance.save(update_fields=['is_primary'])  # Act
```

#### Attack Scenario:
```
Thread A: Create embedding E1 for user U
Thread B: Create embedding E2 for user U

T0: A checks: no primary exists → False
T1: B checks: no primary exists → False
T2: A saves: E1.is_primary = True
T3: B saves: E2.is_primary = True

Result: User U has TWO primary embeddings!
```

This violates the **business invariant**: "Each user has exactly ONE primary embedding per model type"

---

### 4. UserBehaviorProfile Concurrent Updates
**File:** `apps/face_recognition/integrations.py:168-313`
**CVSS Component:** 7.5

#### Vulnerable Pattern:
```python
profile, created = UserBehaviorProfile.objects.get_or_create(...)

# Multiple field updates without locking
updates = {}
updates['fraud_risk_score'] = ...  # Weighted average calculation
updates['anomaly_history'] = ...    # Append to list
updates['frequent_locations'] = ... # Update location counts

for field, value in updates.items():
    setattr(profile, field, value)

profile.save()  # Lost updates possible!
```

#### Problem:
Complex calculation → update pattern without atomicity leads to lost updates when multiple attendance events process simultaneously.

---

## Solution Architecture

### Layer 1: Database-Level Locking
**Purpose:** Prevent concurrent reads of data being modified

```python
from django.db import transaction

# Pessimistic locking for critical sections
with transaction.atomic():
    obj = PeopleEventlog.objects.select_for_update().get(uuid=uuid)
    # Modifications here are exclusive
    obj.peventlogextras['verified_in'] = True
    obj.save()
```

**When to Use:**
- Short critical sections
- High contention expected
- Must guarantee consistency

**Trade-offs:**
- Blocks other transactions (reduces concurrency)
- Risk of deadlocks if not careful
- Performance impact under high load

---

### Layer 2: Atomic Field Updates with F()
**Purpose:** Server-side atomic operations without read-modify-write

```python
# Instead of:
model.count = model.count + 1  # Race condition!
model.save()

# Use:
model.count = F('count') + 1  # Atomic SQL: UPDATE ... SET count = count + 1
model.save(update_fields=['count'])
```

**When to Use:**
- Simple counter increments/decrements
- Timestamp updates
- Numeric calculations

**Limitations:**
- Cannot use for conditional logic on same field
- Requires refresh_from_db() to read new value
- Not suitable for JSON field modifications

---

### Layer 3: Optimistic Locking with Version Fields
**Purpose:** Detect concurrent modifications and retry

```python
class PeopleEventlog(models.Model):
    version = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if self.pk:
            # Check version hasn't changed
            updated = PeopleEventlog.objects.filter(
                pk=self.pk,
                version=self.version
            ).update(
                version=F('version') + 1,
                # ... other fields
            )
            if updated == 0:
                raise ConcurrentModificationError("Record was modified by another transaction")
            self.version += 1
        else:
            super().save(*args, **kwargs)
```

**When to Use:**
- Long-running transactions
- Low contention expected
- UI-driven updates

**Trade-offs:**
- Requires retry logic in application
- Version field overhead
- Better for low-conflict scenarios

---

### Layer 4: Redis Distributed Locks
**Purpose:** Coordinate across multiple models/processes

```python
from django.core.cache import cache
import time

def with_redis_lock(lock_key, timeout=10):
    def decorator(func):
        def wrapper(*args, **kwargs):
            lock_id = f"lock:{lock_key}:{args[1]}"  # e.g., "lock:fr_update:uuid123"

            # Try to acquire lock
            acquired = cache.add(lock_id, True, timeout)
            if not acquired:
                raise LockAcquisitionError(f"Could not acquire lock: {lock_id}")

            try:
                return func(*args, **kwargs)
            finally:
                cache.delete(lock_id)
        return wrapper
    return decorator

@with_redis_lock('fr_update')
def update_fr_results(self, result, uuid, peopleid, db):
    # Protected by distributed lock
    ...
```

**When to Use:**
- Operations spanning multiple models
- Need coordination across app servers
- Celery task synchronization

**Trade-offs:**
- Requires Redis dependency
- Network latency
- Must handle lock timeouts

---

### Layer 5: Database Constraints
**Purpose:** Enforce invariants at database level

```sql
-- Ensure only one primary embedding per user per model type
CREATE UNIQUE INDEX idx_one_primary_per_user_model
ON face_embedding (user_id, extraction_model_id)
WHERE is_primary = TRUE;
```

**When to Use:**
- Critical business invariants
- Defense-in-depth strategy
- Catch application-level bugs

**Trade-offs:**
- Database-specific SQL
- Migration complexity
- Error handling in application

---

## Implementation Plan

### Phase 1: Critical Path - Attendance Verification (Priority: CRITICAL)

#### 1.1 Fix update_fr_results with Row Locking
**File:** `apps/attendance/managers.py`

**Changes:**
```python
from django.db import transaction
from django.core.cache import cache
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

@contextmanager
def attendance_update_lock(uuid, timeout=10):
    """Distributed lock for attendance updates"""
    lock_key = f"attendance_update:{uuid}"
    acquired = cache.add(lock_key, True, timeout)

    if not acquired:
        raise ValueError(f"Another verification is in progress for {uuid}")

    try:
        yield
    finally:
        cache.delete(lock_key)

def update_fr_results(self, result, uuid, peopleid, db):
    """Update face recognition results with proper locking"""
    logger.info("update_fr_results started results:%s", result)

    try:
        with attendance_update_lock(uuid), transaction.atomic():
            # Row-level lock to prevent concurrent modifications
            obj = self.select_for_update().filter(uuid=uuid).using(db).first()

            if not obj:
                logger.warning(f"No attendance record found for uuid: {uuid}")
                return False

            logger.info(
                "Retrieved locked obj punchintime: %s punchouttime: %s peopleid: %s",
                obj.punchintime, obj.punchouttime, peopleid
            )

            # Work with local copy to minimize lock time
            extras = dict(obj.peventlogextras)

            # Update punch-in verification
            if obj.punchintime and extras.get("distance_in") is None:
                extras["verified_in"] = bool(result["verified"])
                extras["distance_in"] = result["distance"]
                obj.facerecognitionin = extras["verified_in"]

            # Update punch-out verification
            elif obj.punchouttime and extras.get("distance_out") is None:
                extras["verified_out"] = bool(result["verified"])
                extras["distance_out"] = result["distance"]
                obj.facerecognitionout = extras["verified_out"]

            # Geofence validation (keeping existing logic)
            # ... [rest of geofence code]

            # Atomic update
            obj.peventlogextras = extras
            obj.save(update_fields=['peventlogextras', 'facerecognitionin', 'facerecognitionout'])

            logger.info(f"Successfully updated attendance {obj.id} with FR results")
            return True

    except Exception as e:
        logger.error(f"Error updating FR results for {uuid}: {str(e)}", exc_info=True)
        raise
```

**Testing:**
```python
# Concurrent update test
import threading

def test_concurrent_fr_updates():
    attendance = create_test_attendance()

    results = []
    def update_punch_in():
        manager.update_fr_results(
            {"verified": True, "distance": 0.2},
            attendance.uuid, attendance.people_id, 'default'
        )

    def update_punch_out():
        manager.update_fr_results(
            {"verified": True, "distance": 0.3},
            attendance.uuid, attendance.people_id, 'default'
        )

    t1 = threading.Thread(target=update_punch_in)
    t2 = threading.Thread(target=update_punch_out)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    attendance.refresh_from_db()
    assert attendance.peventlogextras["verified_in"] == True
    assert attendance.peventlogextras["distance_in"] == 0.2
    assert attendance.peventlogextras["verified_out"] == True
    assert attendance.peventlogextras["distance_out"] == 0.3
```

---

### Phase 2: Atomic Counter Updates (Priority: HIGH)

#### 2.1 Fix FaceVerificationLog Signal Handler
**File:** `apps/face_recognition/signals.py`

**Changes:**
```python
from django.db import transaction
from django.db.models import F

@receiver(post_save, sender=FaceVerificationLog)
def handle_verification_logged(sender, instance, created, **kwargs):
    """Handle face verification log creation with atomic updates"""
    if not created:
        return

    try:
        logger.info(f"Face verification logged: {instance.id}")

        # Update model statistics atomically
        if instance.verification_model:
            with transaction.atomic():
                model = instance.verification_model

                # Prepare atomic updates
                update_fields = {}
                update_fields['verification_count'] = F('verification_count') + 1
                update_fields['last_used'] = timezone.now()

                if instance.result == 'SUCCESS':
                    update_fields['successful_verifications'] = F('successful_verifications') + 1

                # Single atomic update
                FaceRecognitionModel.objects.filter(pk=model.pk).update(**update_fields)

        # Update embedding statistics atomically
        if instance.matched_embedding:
            with transaction.atomic():
                embedding = instance.matched_embedding

                update_fields = {}
                update_fields['verification_count'] = F('verification_count') + 1
                update_fields['last_used'] = timezone.now()

                if instance.result == 'SUCCESS':
                    update_fields['successful_matches'] = F('successful_matches') + 1

                # Single atomic update
                FaceEmbedding.objects.filter(pk=embedding.pk).update(**update_fields)

        # Clear cache
        if instance.user_id:
            cache_key = f"user_verification_stats_{instance.user_id}"
            cache.delete(cache_key)

    except Exception as e:
        logger.error(f"Error handling verification log: {str(e)}", exc_info=True)
```

---

#### 2.2 Fix Primary Embedding Selection
**File:** `apps/face_recognition/signals.py`

**Changes:**
```python
from django.db import transaction, IntegrityError

@receiver(post_save, sender=FaceEmbedding)
def handle_face_embedding_updated(sender, instance, created, **kwargs):
    """Handle face embedding creation/updates with proper locking"""
    if not created:
        return

    try:
        logger.info(f"New face embedding created for user {instance.user_id}")

        # Set as primary using database constraint for enforcement
        with transaction.atomic():
            # Lock all embeddings for this user
            user_embeddings = FaceEmbedding.objects.select_for_update().filter(
                user=instance.user,
                extraction_model__model_type=instance.extraction_model.model_type
            ).order_by('id')

            primary_exists = user_embeddings.filter(is_primary=True).exclude(id=instance.id).exists()

            if not primary_exists:
                # Set this as primary
                instance.is_primary = True
                try:
                    instance.save(update_fields=['is_primary'])
                except IntegrityError:
                    # Another transaction won the race - acceptable
                    logger.info(f"Another embedding became primary for user {instance.user_id}")

        # Clear cache
        cache_key = f"user_embeddings_{instance.user_id}"
        cache.delete(cache_key)

    except Exception as e:
        logger.error(f"Error handling face embedding update: {str(e)}", exc_info=True)
```

---

### Phase 3: Optimistic Locking (Priority: MEDIUM)

#### 3.1 Add Version Field to PeopleEventlog
**Migration:** `apps/attendance/migrations/0009_add_version_field.py`

```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0008_add_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='peopleeventlog',
            name='version',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='peopleeventlog',
            name='last_modified_by',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
```

#### 3.2 Implement Optimistic Locking Mixin
**File:** `apps/core/models/optimistic_locking.py`

```python
from django.db import models, transaction
from django.db.models import F

class ConcurrentModificationError(Exception):
    """Raised when optimistic lock fails"""
    pass

class OptimisticLockMixin:
    """Mixin to add optimistic locking to models"""

    def save(self, *args, **kwargs):
        """Save with optimistic lock check"""
        if self.pk and hasattr(self, 'version'):
            with transaction.atomic():
                # Try to update with version check
                updated = self.__class__.objects.filter(
                    pk=self.pk,
                    version=self.version
                ).update(
                    version=F('version') + 1,
                    **{f.name: getattr(self, f.name) for f in self._meta.fields
                       if f.name not in ['id', 'version']}
                )

                if updated == 0:
                    raise ConcurrentModificationError(
                        f"{self.__class__.__name__} with pk={self.pk} was modified by another transaction"
                    )

                self.version += 1
                self.refresh_from_db()
        else:
            super().save(*args, **kwargs)
```

---

### Phase 4: Database Constraints (Priority: HIGH)

#### 4.1 Unique Primary Embedding Constraint
**Migration:** `apps/face_recognition/migrations/0003_add_unique_primary_constraint.py`

```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('face_recognition', '0002_previous_migration'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX idx_one_primary_per_user_model
                ON face_embedding (user_id, extraction_model_id)
                WHERE is_primary = TRUE;
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_one_primary_per_user_model;
            """
        ),
    ]
```

---

## Testing Strategy

### Test 1: Concurrent Verification Updates
**File:** `apps/attendance/tests/test_race_conditions.py`

```python
import pytest
import threading
from apps.attendance.models import PeopleEventlog

@pytest.mark.django_db(transaction=True)
def test_concurrent_fr_updates_no_data_loss():
    """Test concurrent punch-in and punch-out updates"""
    attendance = create_test_attendance()

    errors = []

    def update_in():
        try:
            PeopleEventlog.objects.update_fr_results(
                {"verified": True, "distance": 0.2},
                attendance.uuid, attendance.people_id, 'default'
            )
        except Exception as e:
            errors.append(e)

    def update_out():
        try:
            time.sleep(0.01)  # Slight delay to ensure overlap
            PeopleEventlog.objects.update_fr_results(
                {"verified": True, "distance": 0.3},
                attendance.uuid, attendance.people_id, 'default'
            )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=update_in), threading.Thread(target=update_out)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors occurred: {errors}"

    attendance.refresh_from_db()
    extras = attendance.peventlogextras

    # Both updates should be present
    assert extras["verified_in"] == True, "Punch-in verification lost"
    assert extras["distance_in"] == 0.2, "Punch-in distance lost"
    assert extras["verified_out"] == True, "Punch-out verification lost"
    assert extras["distance_out"] == 0.3, "Punch-out distance lost"
```

### Test 2: Counter Integrity
```python
@pytest.mark.django_db(transaction=True)
def test_concurrent_counter_updates_accuracy():
    """Test that concurrent verifications update counters correctly"""
    model = FaceRecognitionModel.objects.create(name="TestModel")
    initial_count = model.verification_count

    num_threads = 10
    threads = []

    def create_verification():
        FaceVerificationLog.objects.create(
            user=test_user,
            verification_model=model,
            result='SUCCESS'
        )

    for _ in range(num_threads):
        t = threading.Thread(target=create_verification)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    model.refresh_from_db()
    assert model.verification_count == initial_count + num_threads
```

### Test 3: Primary Embedding Uniqueness
```python
@pytest.mark.django_db(transaction=True)
def test_only_one_primary_embedding():
    """Test that only one primary embedding can exist per user"""
    user = create_test_user()
    model = FaceRecognitionModel.objects.create(name="Test")

    def create_embedding():
        FaceEmbedding.objects.create(
            user=user,
            extraction_model=model,
            embedding_vector=[0.1] * 512,
            face_confidence=0.9
        )

    threads = [threading.Thread(target=create_embedding) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    primary_count = FaceEmbedding.objects.filter(
        user=user,
        extraction_model__model_type=model.model_type,
        is_primary=True
    ).count()

    assert primary_count == 1, f"Expected 1 primary embedding, found {primary_count}"
```

---

## Rollout Plan

### Phase 1: Staging Deployment (Week 1)
1. Deploy database constraints
2. Deploy locking mechanisms
3. Run load tests with 100 concurrent verifications
4. Monitor for deadlocks or performance issues

### Phase 2: Canary Deployment (Week 2)
1. Deploy to 10% of production traffic
2. Monitor error rates, latency, data integrity
3. Gradually increase to 50%

### Phase 3: Full Production (Week 3)
1. Deploy to 100% of production
2. Enable comprehensive monitoring
3. Document performance baselines

---

## Monitoring and Alerts

### Metrics to Track:
1. **Lock Acquisition Failures:** Alert if > 1% of operations fail to acquire lock
2. **Lock Wait Time:** Alert if average wait > 100ms
3. **Counter Discrepancies:** Periodic audit comparing actual vs expected counts
4. **Primary Embedding Violations:** Alert on any database constraint violations
5. **Optimistic Lock Conflicts:** Track retry rates

### Dashboard Queries:
```sql
-- Detect counter anomalies
SELECT
    model_id,
    verification_count,
    (SELECT COUNT(*) FROM face_verification_log WHERE verification_model_id = model_id) as actual_count,
    verification_count - (SELECT COUNT(*) FROM face_verification_log WHERE verification_model_id = model_id) as discrepancy
FROM face_recognition_model
WHERE verification_count != (SELECT COUNT(*) FROM face_verification_log WHERE verification_model_id = model_id);

-- Detect multiple primary embeddings (should be zero)
SELECT user_id, extraction_model_id, COUNT(*) as primary_count
FROM face_embedding
WHERE is_primary = TRUE
GROUP BY user_id, extraction_model_id
HAVING COUNT(*) > 1;
```

---

## Performance Impact Assessment

### Expected Overhead:
- **Row Locking:** +5-15ms per verification (acceptable for critical data)
- **Redis Locks:** +2-5ms network latency
- **F() Updates:** -10ms (faster than read-modify-write)
- **Constraints:** Negligible (<1ms)

### Mitigation Strategies:
1. Keep lock duration minimal (< 50ms)
2. Use Redis pipelining for multiple lock operations
3. Optimize database queries within locked sections
4. Consider lock timeout tuning (default: 10s)

---

## Success Criteria

1. **Zero Data Loss:** No verification data lost under concurrent load (verified via stress tests)
2. **Counter Accuracy:** 100% accuracy in verification counts (verified via audit queries)
3. **Constraint Enforcement:** Zero primary embedding violations (verified via database checks)
4. **Performance:** < 50ms p95 latency increase for verification operations
5. **Reliability:** < 0.1% lock acquisition failures under peak load

---

## Rollback Plan

If issues arise:
1. **Immediate:** Disable concurrent processing (queue all verifications)
2. **Short-term:** Roll back code changes, keep database constraints
3. **Long-term:** Analyze failure, fix issues, re-test in staging

---

## References

- [Django select_for_update](https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-for-update)
- [PostgreSQL Row-Level Locking](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)
- [Redis Distributed Locks](https://redis.io/topics/distlock)
- [Optimistic Locking Patterns](https://docs.microsoft.com/en-us/azure/architecture/patterns/optimistic-concurrency)