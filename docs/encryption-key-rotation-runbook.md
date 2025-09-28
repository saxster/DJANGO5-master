# Encryption Key Rotation Runbook

## Quick Reference

| Task | Command | Duration |
|------|---------|----------|
| Check key status | `python manage.py shell` + `EncryptionKeyManager.get_key_status()` | 30 sec |
| Dry run rotation | `python manage.py rotate_encryption_keys --dry-run` | 2-5 min |
| Perform rotation | `python manage.py rotate_encryption_keys` | 15-60 min |
| Verify rotation | Check `EncryptionKeyMetadata` table | 1 min |

## Pre-Rotation Checklist

- [ ] **Database backup completed** (< 1 hour old)
- [ ] **Current key age checked** (>= 76 days or approaching expiration)
- [ ] **Dry run completed** successfully
- [ ] **Maintenance window scheduled** (if needed)
- [ ] **Team notified** of rotation schedule
- [ ] **Monitoring dashboards** open and ready
- [ ] **Rollback plan reviewed**

## Standard Rotation Procedure

### Phase 1: Pre-Flight Checks (10 minutes)

#### 1.1 Check Current System Status

```bash
# Database connection
python manage.py dbshell

# Exit: \q

# Application health
curl http://localhost:8000/health/

# Expected: HTTP 200, all checks passing
```

#### 1.2 Check Current Key Status

```bash
python manage.py shell
```

```python
from apps.core.services.encryption_key_manager import EncryptionKeyManager
from apps.core.models import EncryptionKeyMetadata

# Initialize
EncryptionKeyManager.initialize()

# Check status
status = EncryptionKeyManager.get_key_status()
print(f"Current Key: {status['current_key_id']}")
print(f"Active Keys: {status['active_keys_count']}")

# Check current key details
current = EncryptionKeyMetadata.get_current_key()
print(f"Age: {current.age_days} days")
print(f"Expires in: {current.expires_in_days} days")
print(f"Needs rotation: {current.needs_rotation}")

# Exit shell
exit()
```

**Criteria to proceed:**
- ✅ Current key exists
- ✅ Key age >= 76 days OR expires_in_days < 14
- ✅ No keys stuck in 'rotating' status

#### 1.3 Create Database Backup

```bash
# PostgreSQL backup
pg_dump -h localhost -U postgres -d intelliwiz > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql
```

#### 1.4 Run Dry-Run Rotation

```bash
python manage.py rotate_encryption_keys --dry-run
```

**Review output:**
- Total records to migrate
- Estimated duration
- Any warnings or errors

### Phase 2: Execute Rotation (15-60 minutes depending on data size)

#### 2.1 Start Rotation

```bash
# Standard rotation
python manage.py rotate_encryption_keys

# For large datasets (>100K records), use larger batch size
python manage.py rotate_encryption_keys --batch-size 500

# Log output to file for audit trail
python manage.py rotate_encryption_keys 2>&1 | tee rotation_$(date +%Y%m%d_%H%M%S).log
```

#### 2.2 Monitor Progress

Watch for these progress indicators:

```
1️⃣  Creating new encryption key...
   ✅ New key created: key_20250927_153045_b7c2

2️⃣  Marking current key for rotation...
   ✅ Current key marked for rotation

3️⃣  Migrating encrypted data...
   📊 Progress: 1,000 / 15,420 (6.5%)
   📊 Progress: 5,000 / 15,420 (32.4%)
   📊 Progress: 10,000 / 15,420 (64.9%)
   📊 Progress: 15,000 / 15,420 (97.3%)
   ✅ Migrated 15,420 records

4️⃣  Activating new key...
   ✅ New key activated

5️⃣  Retiring old key...
   ✅ Old key retired

✅ KEY ROTATION COMPLETE
```

**Monitor for:**
- ⚠️ Warnings: Check logs, but process continues
- ❌ Errors: Process stops, automatic rollback initiated

#### 2.3 Handle Rotation Failure

If rotation fails:

```bash
# Automatic rollback happens, but verify
python manage.py shell
```

```python
from apps.core.models import EncryptionKeyMetadata

# Check for keys stuck in 'rotating' status
stuck = EncryptionKeyMetadata.objects.filter(rotation_status='rotating')
print(f"Stuck keys: {stuck.count()}")

# Manual rollback if needed
for key in stuck:
    key.rotation_status = 'created'
    key.save()
    print(f"Reset {key.key_id} to 'created' status")

# Reactivate previous key
prev_active = EncryptionKeyMetadata.objects.filter(
    rotation_status='active'
).order_by('-activated_at').first()

if prev_active:
    prev_active.is_active = True
    prev_active.save()
    print(f"Reactivated {prev_active.key_id}")

exit()
```

### Phase 3: Post-Rotation Verification (5 minutes)

#### 3.1 Verify New Key is Active

```bash
python manage.py shell
```

```python
from apps.core.models import EncryptionKeyMetadata
from apps.core.services.encryption_key_manager import EncryptionKeyManager

# Check current key
current = EncryptionKeyMetadata.get_current_key()
print(f"✅ Current Key: {current.key_id}")
print(f"   Status: {current.rotation_status}")
print(f"   Active: {current.is_active}")
print(f"   Expires in: {current.expires_in_days} days")

# Check old key is retired
retired = EncryptionKeyMetadata.objects.filter(rotation_status='retired')
print(f"\n📦 Retired Keys: {retired.count()}")
for key in retired:
    print(f"   {key.key_id} (retired {key.rotated_at})")

exit()
```

#### 3.2 Test Encryption/Decryption

```bash
python manage.py shell
```

```python
from apps.core.services.encryption_key_manager import EncryptionKeyManager

# Initialize
EncryptionKeyManager.initialize()

# Test encryption with new key
test_data = "post_rotation_test_data"
encrypted = EncryptionKeyManager.encrypt(test_data)
decrypted = EncryptionKeyManager.decrypt(encrypted)

assert decrypted == test_data, "❌ Encryption test failed!"
print("✅ Encryption/decryption test passed")

# Verify format is V2 with new key
assert encrypted.startswith("FERNET_V2:"), "❌ Wrong encryption format!"
print("✅ Using V2 format with key ID")

exit()
```

#### 3.3 Verify Application Health

```bash
# Health check
curl http://localhost:8000/health/

# Check logs for errors
tail -n 100 logs/django.log | grep -i error

# Check encryption-specific logs
tail -n 50 logs/django.log | grep -i encryption
```

#### 3.4 Sample Data Verification

```bash
python manage.py shell
```

```python
from apps.peoples.models import People
import random

# Sample 10 random users
sample_users = random.sample(list(People.objects.all()[:1000]), 10)

print("Testing decryption of user data...")
for user in sample_users:
    try:
        # Access encrypted fields (triggers decryption)
        email = user.email
        mobile = user.mobno

        print(f"✅ User {user.id}: Email and mobile accessible")
    except Exception as e:
        print(f"❌ User {user.id}: Decryption failed - {e}")

exit()
```

### Phase 4: Post-Rotation Tasks (10 minutes)

#### 4.1 Document Rotation

```bash
# Save rotation log
cp rotation_*.log /path/to/audit/logs/

# Update rotation documentation
echo "$(date): Key rotation completed - new key: $(current_key_id)" >> rotation_history.txt
```

#### 4.2 Update Monitoring

```python
from apps.core.models import EncryptionKeyMetadata

current = EncryptionKeyMetadata.get_current_key()

# Add to monitoring dashboard
print(f"Next rotation due: {current.expires_at}")
print(f"Set alert for: {current.expires_at - timedelta(days=14)}")
```

#### 4.3 Clean Up Old Keys (Optional)

```bash
python manage.py shell
```

```python
from apps.core.models import EncryptionKeyMetadata
from datetime import timedelta
from django.utils import timezone

# Only cleanup keys retired > 1 year ago
very_old_retired = EncryptionKeyMetadata.objects.filter(
    rotation_status='retired',
    rotated_at__lt=timezone.now() - timedelta(days=365)
)

print(f"Keys eligible for cleanup: {very_old_retired.count()}")

# Uncomment to actually delete (BE CAREFUL!)
# deleted = EncryptionKeyMetadata.cleanup_old_keys(days=365)
# print(f"Deleted {deleted} old keys")

exit()
```

#### 4.4 Notify Team

Send notification:

```
Subject: Encryption Key Rotation Complete

Rotation Details:
- Date: [DATE]
- Old Key: [OLD_KEY_ID]
- New Key: [NEW_KEY_ID]
- Records Migrated: [COUNT]
- Duration: [MINUTES]
- Status: ✅ Success

Next rotation due: [EXPIRATION_DATE - 14 days]
```

## Emergency Rollback Procedure

### When to Rollback

- ❌ Post-rotation decryption failures
- ❌ Application errors related to encryption
- ❌ Data integrity issues
- ❌ Performance degradation > 50%

### Rollback Steps

#### 1. Stop Application (if needed)

```bash
# Stop application servers
supervisorctl stop all
```

#### 2. Revert to Previous Key

```bash
python manage.py shell
```

```python
from apps.core.models import EncryptionKeyMetadata
from apps.core.services.encryption_key_manager import EncryptionKeyManager

# Find the most recent retired key
previous_key = EncryptionKeyMetadata.objects.filter(
    rotation_status='retired'
).order_by('-rotated_at').first()

if previous_key:
    # Reactivate previous key
    previous_key.is_active = True
    previous_key.rotation_status = 'active'
    previous_key.save()

    # Deactivate current key
    current = EncryptionKeyMetadata.get_current_key()
    if current:
        current.is_active = False
        current.rotation_status = 'created'
        current.save()

    # Reload key manager
    EncryptionKeyManager.initialize()
    EncryptionKeyManager.activate_key(previous_key.key_id)

    print(f"✅ Rolled back to {previous_key.key_id}")
else:
    print("❌ No previous key found for rollback!")

exit()
```

#### 3. Verify Rollback

```bash
python manage.py shell
```

```python
from apps.core.models import EncryptionKeyMetadata

current = EncryptionKeyMetadata.get_current_key()
print(f"Current key after rollback: {current.key_id}")
print(f"Status: {current.rotation_status}")

# Test encryption/decryption
from apps.core.services.encryption_key_manager import EncryptionKeyManager

EncryptionKeyManager.initialize()
test = "rollback_test"
enc = EncryptionKeyManager.encrypt(test)
dec = EncryptionKeyManager.decrypt(enc)

assert dec == test
print("✅ Encryption working after rollback")

exit()
```

#### 4. Restart Application

```bash
supervisorctl start all

# Verify health
curl http://localhost:8000/health/
```

## Troubleshooting Guide

### Issue 1: "Could not decrypt data with any available key"

**Symptoms:**
- Users can't access encrypted fields
- Decryption errors in logs

**Diagnosis:**
```python
from apps.core.models import EncryptionKeyMetadata

# Check active keys
active = EncryptionKeyMetadata.objects.filter(is_active=True)
print(f"Active keys: {[k.key_id for k in active]}")

# Check specific record
from apps.peoples.models import People
from django.db import connection

user = People.objects.first()
with connection.cursor() as cursor:
    cursor.execute("SELECT email FROM people WHERE id = %s", [user.id])
    raw_email = cursor.fetchone()[0]
    print(f"Raw email format: {raw_email[:50]}")
```

**Solution:**
Reactivate retired key temporarily to decrypt old data.

### Issue 2: Rotation Stuck at "Migrating Data"

**Symptoms:**
- Rotation process hangs
- No progress updates

**Diagnosis:**
- Check database connections: `SELECT count(*) FROM pg_stat_activity;`
- Check disk space: `df -h`
- Check process: `ps aux | grep manage.py`

**Solution:**
1. Kill stuck process (rotation auto-rollbacks)
2. Check system resources
3. Retry with smaller batch size: `--batch-size 50`

### Issue 3: Performance Degradation After Rotation

**Symptoms:**
- Slower response times
- Increased database load

**Diagnosis:**
```python
from apps.core.services.encryption_key_manager import EncryptionKeyManager

status = EncryptionKeyManager.get_key_status()
print(f"Active keys: {status['active_keys_count']}")
```

**Solution:**
If too many active keys (> 5), clean up old retired keys:
```python
EncryptionKeyMetadata.cleanup_old_keys(days=365)
```

## Appendix: Command Reference

### Management Commands

```bash
# Rotation
python manage.py rotate_encryption_keys [--dry-run] [--batch-size N] [--force]

# Migration verification
python manage.py migrate_secure_encryption --dry-run

# Health checks
python manage.py check_encryption_health
```

### Shell Helpers

```python
from apps.core.services.encryption_key_manager import EncryptionKeyManager
from apps.core.models import EncryptionKeyMetadata

# Quick status
def quick_status():
    EncryptionKeyManager.initialize()
    return EncryptionKeyManager.get_key_status()

# Find keys needing rotation
def check_rotation_needed():
    return EncryptionKeyMetadata.get_keys_needing_rotation()

# Encryption test
def test_encryption():
    EncryptionKeyManager.initialize()
    test = "test_data"
    enc = EncryptionKeyManager.encrypt(test)
    dec = EncryptionKeyManager.decrypt(enc)
    return dec == test
```

## Contacts

**Security Team:** security@example.com
**DevOps On-Call:** +1-XXX-XXX-XXXX
**Escalation:** CTO / Security Lead

---

**Last Updated:** 2025-09-27
**Document Version:** 1.0
**Owner:** Security & Platform Team