# Encryption Key Rotation Guide

## Overview

This guide documents the encryption key rotation system implemented to address the **CVSS 7.5 security vulnerability** where no key rotation mechanism existed.

### Security Issues Resolved

1. **Deprecated insecure "encryption" blocked in production** - zlib compression functions now raise `RuntimeError` in production
2. **Bare exception handlers replaced** - All encryption code now uses specific exception types per `.claude/rules.md` Rule 11
3. **Key rotation mechanism implemented** - Complete infrastructure for safe key rotation with zero data loss
4. **Key age tracking** - Automatic monitoring and alerts for keys approaching expiration

## Architecture

### Components

#### 1. EncryptionKeyManager Service
**Location:** `apps/core/services/encryption_key_manager.py`

Multi-key encryption manager that supports:
- Concurrent encryption with current key
- Decryption with any active key (current + historical)
- Key versioning: `FERNET_V2:key_id:encrypted_payload`
- Thread-safe key management

#### 2. EncryptionKeyMetadata Model
**Location:** `apps/core/models.py`

Tracks key lifecycle:
- Key creation, activation, expiration, rotation dates
- Rotation status (created, active, rotating, retired, expired)
- Audit trail with rotation notes
- Usage statistics

#### 3. Management Command
**Location:** `apps/core/management/commands/rotate_encryption_keys.py`

Safe rotation with:
- Dry-run mode for testing
- Batch processing for large datasets
- Progress tracking and reporting
- Automatic rollback on failure

## Key Rotation Process

### Automatic Rotation Timeline

```
Day 0:   New key created (expires in 90 days)
Day 76:  Warning: Key expires in 14 days (needs_rotation = True)
Day 90:  Key expires (status = 'expired', is_active = False)
```

### Manual Rotation Steps

#### 1. Check Current Key Status

```bash
python manage.py shell

from apps.core.models import EncryptionKeyMetadata
from apps.core.services.encryption_key_manager import EncryptionKeyManager

# Initialize manager
EncryptionKeyManager.initialize()

# Check status
status = EncryptionKeyManager.get_key_status()
print(status)
```

**Output:**
```python
{
    'current_key_id': 'key_20250927_142030_a3f4',
    'active_keys_count': 2,
    'keys': [
        {
            'key_id': 'key_20250927_142030_a3f4',
            'is_current': True,
            'age_days': 76,
            'expires_in_days': 14,
            'rotation_status': 'active',
            'needs_rotation': True  # ⚠️ Warning!
        }
    ]
}
```

#### 2. Test Rotation (Dry Run)

```bash
python manage.py rotate_encryption_keys --dry-run
```

**Sample Output:**
```
🔄 ENCRYPTION KEY ROTATION
============================================================
✅ Key manager initialized

📊 Current Key Status:
  Key ID: key_20250927_142030_a3f4
  Age: 76 days
  Expires in: 14 days
  Status: active

📊 Analyzing encrypted data...

📊 MIGRATION STATISTICS (Estimated)
============================================================
Total Users: 15,420
Users with Email: 15,420
Users with Mobile: 14,892

ENCRYPTION FORMAT DISTRIBUTION:
  📦 V2 Format (Current): 10,234
  📜 V1 Format (Legacy): 5,186
  📝 Plaintext: 0

🔄 RECORDS NEEDING MIGRATION: 5,186

✅ DRY RUN COMPLETE - No changes made
```

#### 3. Perform Rotation

```bash
# Standard rotation
python manage.py rotate_encryption_keys

# With custom batch size for large datasets
python manage.py rotate_encryption_keys --batch-size 500

# Force rotation (even if not near expiration)
python manage.py rotate_encryption_keys --force
```

**Rotation Process:**
```
1️⃣  Creating new encryption key...
   ✅ New key created: key_20250927_153045_b7c2

2️⃣  Marking current key for rotation...
   ✅ Current key marked for rotation

3️⃣  Migrating encrypted data...
   📊 Progress: 1,000 / 5,186 (19.3%)
   📊 Progress: 2,000 / 5,186 (38.6%)
   📊 Progress: 3,000 / 5,186 (57.9%)
   📊 Progress: 4,000 / 5,186 (77.1%)
   📊 Progress: 5,000 / 5,186 (96.4%)
   ✅ Migrated 5,186 records

4️⃣  Activating new key...
   ✅ New key activated

5️⃣  Retiring old key...
   ✅ Old key retired

✅ KEY ROTATION COMPLETE
   New Key ID: key_20250927_153045_b7c2
   Old Key ID: key_20250927_142030_a3f4 (retired)
```

#### 4. Verify Rotation

```bash
python manage.py shell

from apps.core.models import EncryptionKeyMetadata

# Check new key is active
current = EncryptionKeyMetadata.get_current_key()
print(f"Current key: {current.key_id}")
print(f"Status: {current.rotation_status}")
print(f"Expires in: {current.expires_in_days} days")

# Verify old key is retired
retired_keys = EncryptionKeyMetadata.objects.filter(rotation_status='retired')
for key in retired_keys:
    print(f"Retired: {key.key_id} (rotated {key.rotated_at})")
```

## Security Enhancements

### 1. Production Enforcement

Deprecated insecure functions now **block execution in production**:

```python
# apps/core/utils_new/string_utils.py

def encrypt(data):
    if not settings.DEBUG:
        raise RuntimeError(
            "SECURITY ERROR: Deprecated insecure encrypt() cannot be used in production"
        )
```

**Result:** Attempting to use deprecated functions in production logs security violation and raises exception.

### 2. Specific Exception Handling

Replaced bare exception handlers per `.claude/rules.md` Rule 11:

```python
# ❌ BEFORE (Rule Violation)
try:
    migration_successful, result = migrate_legacy_data(value)
except:
    pass  # Hides all errors

# ✅ AFTER (Compliant)
except (ValueError, TypeError, UnicodeDecodeError, AttributeError) as e:
    logger.debug(f"Migration failed: {type(e).__name__}")
```

### 3. Key Versioning

New format includes key ID for precise decryption:

```
# Old Format (V1)
FERNET_V1:gAAAAABhPQRa7x...

# New Format (V2)
FERNET_V2:key_20250927_153045_b7c2:gAAAAABhPQRa7x...
         └─────────┬─────────┘
                   └─ Key ID enables multi-key support
```

## Backward Compatibility

The system maintains **full backward compatibility**:

1. **V1 format** (legacy without key ID) - Tries all active keys
2. **V2 format** (current with key ID) - Direct key lookup
3. **Unversioned** (very old) - Tries all keys as fallback

**Example:**
```python
# All formats decrypt successfully
v1_data = "FERNET_V1:gAAAAABhPQRa..."
v2_data = "FERNET_V2:key_123:gAAAAABhPQRa..."
old_data = "gAAAAABhPQRa..."  # Very old format

EncryptionKeyManager.decrypt(v1_data)  # ✅ Works
EncryptionKeyManager.decrypt(v2_data)  # ✅ Works
EncryptionKeyManager.decrypt(old_data)  # ✅ Works
```

## Monitoring & Alerts

### Health Checks

```python
from apps.core.services.encryption_key_manager import EncryptionKeyManager

# Check encryption health
try:
    EncryptionKeyManager.initialize()
    test_data = "health_check_test"
    encrypted = EncryptionKeyManager.encrypt(test_data)
    decrypted = EncryptionKeyManager.decrypt(encrypted)
    assert decrypted == test_data
    print("✅ Encryption health check passed")
except Exception as e:
    print(f"❌ Encryption health check failed: {e}")
```

### Key Expiration Monitoring

```python
from apps.core.models import EncryptionKeyMetadata

# Get keys needing rotation (< 14 days to expiration)
keys_needing_rotation = EncryptionKeyMetadata.get_keys_needing_rotation()

for key in keys_needing_rotation:
    print(f"⚠️  Key {key.key_id} expires in {key.expires_in_days} days")
    # Send alert to ops team
```

### Automated Alerts

Add to your monitoring system:

```python
# apps/core/management/commands/check_encryption_health.py

def check_encryption_keys():
    """Run daily health check for encryption keys."""
    keys_needing_rotation = EncryptionKeyMetadata.get_keys_needing_rotation()

    if keys_needing_rotation.exists():
        send_alert(
            title="Encryption Key Rotation Required",
            message=f"{keys_needing_rotation.count()} keys need rotation",
            severity="warning"
        )
```

## Troubleshooting

### Issue: "Could not decrypt data with any available key"

**Cause:** Data encrypted with a key that's no longer active

**Solution:**
```bash
# Check active keys
from apps.core.models import EncryptionKeyMetadata
active_keys = EncryptionKeyMetadata.objects.filter(is_active=True)
print([k.key_id for k in active_keys])

# Reactivate old key if needed
old_key = EncryptionKeyMetadata.objects.get(key_id="missing_key_id")
old_key.is_active = True
old_key.save()
```

### Issue: "Key rotation failed mid-process"

**Cause:** Error during data migration

**Solution:** Rollback is automatic, but verify:
```bash
python manage.py shell

from apps.core.models import EncryptionKeyMetadata

# Check for stuck 'rotating' status
stuck_keys = EncryptionKeyMetadata.objects.filter(rotation_status='rotating')
if stuck_keys.exists():
    # Reset to 'created' status
    for key in stuck_keys:
        key.rotation_status = 'created'
        key.save()
```

### Issue: "Performance degradation after rotation"

**Cause:** Too many active keys slowing down decryption

**Solution:** Clean up retired keys:
```python
from apps.core.models import EncryptionKeyMetadata

# Cleanup keys retired > 1 year ago
deleted = EncryptionKeyMetadata.cleanup_old_keys(days=365)
print(f"Deleted {deleted} retired keys")
```

## Testing

### Run All Encryption Tests

```bash
# All encryption tests
python -m pytest apps/core/tests/test_encryption_key_rotation.py -v

# Specific test categories
python -m pytest apps/core/tests/test_encryption_key_rotation.py::EncryptionKeyManagerTest -v
python -m pytest apps/core/tests/test_encryption_key_rotation.py::DeprecatedEncryptionBlockingTest -v

# Security-marked tests only
python -m pytest -m security apps/core/tests/test_encryption_key_rotation.py -v
```

### Expected Test Coverage

- ✅ Multi-key encryption/decryption
- ✅ V1/V2 format compatibility
- ✅ Key rotation workflow
- ✅ Rollback scenarios
- ✅ Production blocking of deprecated functions
- ✅ Exception handling compliance

## Best Practices

### 1. Schedule Regular Rotations

Rotate keys **every 90 days** or when:
- Key approaches expiration (< 14 days)
- Security incident suspected
- Compliance requirements change
- Team member with key access leaves

### 2. Test Before Production

**Always run dry-run first:**
```bash
python manage.py rotate_encryption_keys --dry-run
```

### 3. Monitor Key Age

Set up automated monitoring:
```bash
# Add to cron: daily at 9 AM
0 9 * * * cd /app && python manage.py check_encryption_health
```

### 4. Maintain Key Audit Trail

All rotation events are logged in `EncryptionKeyMetadata.rotation_notes`:
```python
key = EncryptionKeyMetadata.objects.get(key_id="...")
print(key.rotation_notes)
# Output: Full history of rotation events
```

### 5. Keep Retired Keys Active

**Do not deactivate retired keys immediately** - they're needed to decrypt old data. Clean up after 1+ years:

```python
# Safe: Cleanup keys retired over 1 year ago
EncryptionKeyMetadata.cleanup_old_keys(days=365)
```

## Security Compliance

This implementation addresses:

- ✅ **CVSS 7.5**: No key rotation mechanism
- ✅ **CWE-320**: Key Management Errors
- ✅ **OWASP A02:2021**: Cryptographic Failures
- ✅ **PCI-DSS 3.6.4**: Key rotation requirements

## References

- [NIST SP 800-57](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final) - Key Management Recommendations
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- `.claude/rules.md` - Project code quality rules