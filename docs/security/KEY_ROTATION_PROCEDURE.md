# Encryption Key Rotation Procedure

**Version:** 1.0
**Last Updated:** November 5, 2025
**Owner:** Security Team
**Review Cycle:** Quarterly

---

## Purpose

This document outlines the procedure for rotating encryption keys used by `SecureEncryptionService`. Regular key rotation limits the impact of potential key compromise and is a security best practice.

---

## Rotation Schedule

### Standard Rotation

**Frequency:** Every 90 days (quarterly)

**Scheduled Dates:**
- Q1: February 1
- Q2: May 1
- Q3: August 1
- Q4: November 1

### Emergency Rotation

**Immediate rotation required if:**
- Key compromise suspected or confirmed
- Employee with key access leaves organization
- Security incident involving encrypted data
- Cryptographic library vulnerability disclosure
- Compliance audit requirement

**Timeline:** Within 24 hours of trigger event

---

## Prerequisites

### Required Access

- [ ] Production environment access (AWS/GCP/Azure admin)
- [ ] Database admin access (PostgreSQL superuser)
- [ ] Secret management system (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] Application deployment permissions
- [ ] Backup restoration permissions

### Required Tools

```bash
# Install required tools
pip install cryptography django

# Verify encryption service
python manage.py shell
>>> from apps.core.services.secure_encryption_service import SecureEncryptionService
>>> SecureEncryptionService.validate_encryption_setup()
True
```

### Pre-Rotation Checklist

- [ ] Full database backup completed
- [ ] Backup verified and restorable
- [ ] Rollback plan documented
- [ ] Maintenance window scheduled
- [ ] Stakeholders notified
- [ ] Monitoring alerts configured

---

## Rotation Procedure

### Phase 1: Generate New Key (15 minutes)

#### Step 1.1: Generate New SECRET_KEY

```bash
# Generate cryptographically secure random key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Output:** `django-insecure-abc123...` (50+ characters)

**CRITICAL:** Store this in secure vault immediately. Do NOT commit to version control.

#### Step 1.2: Store New Key in Secret Manager

**AWS Secrets Manager:**
```bash
# Create new secret version
aws secretsmanager put-secret-value \
    --secret-id django-secret-key \
    --secret-string "django-insecure-new-key-abc123..."
```

**Environment Variable (Development):**
```bash
# Add to .env (DO NOT COMMIT)
SECRET_KEY_NEW="django-insecure-new-key-abc123..."
```

#### Step 1.3: Validate New Key

```python
# Django shell
from apps.core.services.secure_encryption_service import SecureEncryptionService

# Test with new key (set SECRET_KEY_NEW in settings temporarily)
test_data = "rotation_test_data"
encrypted = SecureEncryptionService.encrypt(test_data)
decrypted = SecureEncryptionService.decrypt(encrypted)

assert decrypted == test_data, "New key validation failed"
print("✅ New key validated successfully")
```

---

### Phase 2: Dual-Key Deployment (30 minutes)

#### Step 2.1: Update Settings for Dual-Key Support

```python
# intelliwiz_config/settings/security/encryption.py

import os
from django.conf import settings

# Primary key (current)
SECRET_KEY = os.environ.get('SECRET_KEY')

# New key (for rotation)
SECRET_KEY_NEW = os.environ.get('SECRET_KEY_NEW', None)

# Rotation mode flag
ENCRYPTION_ROTATION_ACTIVE = SECRET_KEY_NEW is not None
```

#### Step 2.2: Deploy Dual-Key Code (No Data Migration Yet)

```bash
# Deploy updated settings
git add intelliwiz_config/settings/security/encryption.py
git commit -m "feat: Add dual-key support for encryption rotation"
git push origin main

# Deploy to staging first
./deploy.sh staging

# Verify deployment
curl https://staging.example.com/health/
```

#### Step 2.3: Verify Dual-Key Mode

```python
# Django shell (staging)
from django.conf import settings

assert hasattr(settings, 'SECRET_KEY_NEW'), "SECRET_KEY_NEW not configured"
assert settings.ENCRYPTION_ROTATION_ACTIVE is True, "Rotation mode not active"

print("✅ Dual-key mode active")
```

---

### Phase 3: Data Re-Encryption (1-4 hours, depending on data volume)

#### Step 3.1: Create Rotation Management Command

**File:** `apps/core/management/commands/rotate_encryption_keys.py`

```python
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.peoples.models import People
from apps.core.services.secure_encryption_service import SecureEncryptionService
import logging

logger = logging.getLogger('key_rotation')

class Command(BaseCommand):
    help = 'Rotate encryption keys for all encrypted fields'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate rotation without committing changes'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process per batch'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        self.stdout.write("Starting encryption key rotation...")

        # Get all models with encrypted fields
        models_to_rotate = [
            (People, ['email', 'mobno']),  # Example encrypted fields
            # Add other models here
        ]

        total_rotated = 0

        for model_class, encrypted_fields in models_to_rotate:
            self.stdout.write(f"\nProcessing {model_class.__name__}...")

            queryset = model_class.objects.all()
            total = queryset.count()

            for offset in range(0, total, batch_size):
                batch = queryset[offset:offset + batch_size]

                with transaction.atomic():
                    for obj in batch:
                        for field_name in encrypted_fields:
                            encrypted_value = getattr(obj, field_name)

                            if encrypted_value and not SecureEncryptionService.is_securely_encrypted(encrypted_value):
                                # Decrypt with OLD key, encrypt with NEW key
                                try:
                                    decrypted = SecureEncryptionService.decrypt(encrypted_value)
                                    re_encrypted = SecureEncryptionService.encrypt(decrypted)

                                    if not dry_run:
                                        setattr(obj, field_name, re_encrypted)

                                    total_rotated += 1

                                except ValueError as e:
                                    logger.error(f"Failed to rotate {model_class.__name__}.{field_name} for object {obj.id}: {e}")

                        if not dry_run:
                            obj.save(update_fields=encrypted_fields)

                    self.stdout.write(f"  Processed {offset + len(batch)}/{total} records")

        self.stdout.write(self.style.SUCCESS(f"\n✅ Rotation complete: {total_rotated} fields rotated"))
```

#### Step 3.2: Run Rotation in Dry-Run Mode

```bash
# Test rotation without committing
python manage.py rotate_encryption_keys --dry-run --batch-size=100

# Expected output:
# Starting encryption key rotation...
# Processing People...
#   Processed 100/5000 records
#   Processed 200/5000 records
#   ...
# ✅ Rotation complete: 5000 fields rotated (DRY RUN)
```

#### Step 3.3: Execute Actual Rotation

```bash
# Take application offline (optional, depending on volume)
# OR run during low-traffic period

# Execute rotation
python manage.py rotate_encryption_keys --batch-size=1000 > rotation.log 2>&1

# Monitor progress
tail -f rotation.log
```

**Expected Duration:**
- 1,000 records: ~5 minutes
- 10,000 records: ~30 minutes
- 100,000 records: ~2 hours
- 1,000,000 records: ~4 hours

#### Step 3.4: Verify Rotation Success

```python
# Django shell
from apps.peoples.models import People
from apps.core.services.secure_encryption_service import SecureEncryptionService

# Check sample records
people = People.objects.filter(email__isnull=False).first()

# Verify encryption format
assert SecureEncryptionService.is_securely_encrypted(people.email), "Email not securely encrypted"

# Verify decryption works
decrypted = SecureEncryptionService.decrypt(people.email)
print(f"✅ Decryption successful: {decrypted[:10]}...")  # Show first 10 chars only

# Verify all records encrypted with new key
total_people = People.objects.count()
encrypted_people = People.objects.filter(email__startswith="FERNET_V1:").count()

print(f"Total people: {total_people}, Encrypted with new key: {encrypted_people}")
```

---

### Phase 4: Key Promotion (30 minutes)

#### Step 4.1: Promote New Key to Primary

```bash
# Update environment variables
# OLD: SECRET_KEY = "old-key-abc"
#      SECRET_KEY_NEW = "new-key-xyz"

# NEW: SECRET_KEY = "new-key-xyz"
#      SECRET_KEY_OLD = "old-key-abc"  # Keep for rollback
#      SECRET_KEY_NEW = None
```

**AWS Secrets Manager:**
```bash
# Backup old key
aws secretsmanager put-secret-value \
    --secret-id django-secret-key-old \
    --secret-string "old-key-abc..."

# Promote new key to primary
aws secretsmanager put-secret-value \
    --secret-id django-secret-key \
    --secret-string "new-key-xyz..."
```

#### Step 4.2: Deploy Key Promotion

```bash
# Deploy updated secrets
./deploy.sh production

# Restart application
kubectl rollout restart deployment/django-app  # Kubernetes
# OR
supervisorctl restart django  # Traditional deployment
```

#### Step 4.3: Verify Application Health

```bash
# Health check
curl https://api.example.com/health/

# Test encryption/decryption
python manage.py shell
>>> from apps.core.services.secure_encryption_service import SecureEncryptionService
>>> SecureEncryptionService.validate_encryption_setup()
True
```

---

### Phase 5: Monitoring & Validation (24 hours)

#### Step 5.1: Monitor Error Logs

```bash
# Check for decryption errors
grep "Decryption failed" /var/log/django/*.log

# Check correlation IDs
grep "InvalidToken" /var/log/django/*.log
```

#### Step 5.2: Run Validation Checks

```python
# apps/core/management/commands/validate_encryption.py
from django.core.management.base import BaseCommand
from apps.peoples.models import People

class Command(BaseCommand):
    def handle(self, *args, **options):
        total = 0
        errors = 0

        for person in People.objects.all():
            if person.email:
                try:
                    from apps.core.services.secure_encryption_service import SecureEncryptionService
                    decrypted = SecureEncryptionService.decrypt(person.email)
                    total += 1
                except ValueError:
                    errors += 1
                    self.stdout.write(f"❌ Failed to decrypt email for person {person.id}")

        self.stdout.write(f"✅ Validated {total} encrypted fields, {errors} errors")
```

```bash
# Run validation
python manage.py validate_encryption
```

#### Step 5.3: Monitor Performance Metrics

- Database query latency
- Application response times
- Error rates
- CPU/memory usage

**No degradation expected** - encryption operations should have identical performance.

---

### Phase 6: Old Key Retirement (30 days later)

#### Step 6.1: Verify No Old Key Usage

```bash
# Search codebase for old key references
grep -r "SECRET_KEY_OLD" .

# Check logs for decryption errors (should be zero)
grep "Decryption failed" /var/log/django/*.log | wc -l
# Expected: 0
```

#### Step 6.2: Remove Old Key

```bash
# Remove from environment
unset SECRET_KEY_OLD

# Remove from secret manager
aws secretsmanager delete-secret \
    --secret-id django-secret-key-old \
    --recovery-window-in-days 30  # 30-day grace period
```

#### Step 6.3: Update Documentation

- [ ] Update this document with rotation date
- [ ] Update ENCRYPTION_AUDIT.md with new key date
- [ ] Archive rotation logs
- [ ] Schedule next rotation (90 days)

---

## Rollback Procedure

**If rotation fails, rollback within 1 hour:**

### Step 1: Restore Old Key

```bash
# Restore SECRET_KEY to old value
aws secretsmanager put-secret-value \
    --secret-id django-secret-key \
    --secret-string "old-key-abc..."
```

### Step 2: Restart Application

```bash
./deploy.sh production
kubectl rollout restart deployment/django-app
```

### Step 3: Verify Rollback

```python
# Django shell
from apps.core.services.secure_encryption_service import SecureEncryptionService

test_data = "rollback_test"
encrypted = SecureEncryptionService.encrypt(test_data)
decrypted = SecureEncryptionService.decrypt(encrypted)

assert decrypted == test_data, "Rollback failed"
print("✅ Rollback successful")
```

### Step 4: Restore Database (If Needed)

```bash
# Only if data corruption occurred
pg_restore -d production_db backup_pre_rotation.dump
```

---

## Testing Checklist

### Pre-Production Testing

- [ ] Test rotation in development environment
- [ ] Test rotation in staging environment
- [ ] Verify all encrypted fields decryptable after rotation
- [ ] Performance testing (no degradation)
- [ ] Rollback testing (restore old key works)

### Production Validation

- [ ] Dry-run completed successfully
- [ ] Backup verified and restorable
- [ ] All stakeholders notified
- [ ] Maintenance window confirmed
- [ ] Monitoring dashboards ready

---

## Troubleshooting

### Common Issues

**Issue 1: Decryption fails after rotation**

**Cause:** New key not properly deployed
**Solution:**
```bash
# Verify SECRET_KEY_NEW is set
echo $SECRET_KEY_NEW

# Restart application
supervisorctl restart django
```

**Issue 2: Some records still use old encryption**

**Cause:** Rotation command didn't process all records
**Solution:**
```bash
# Re-run rotation for missed records
python manage.py rotate_encryption_keys --batch-size=100
```

**Issue 3: InvalidToken errors in logs**

**Cause:** Mixed encryption keys in database
**Solution:**
```python
# Identify problematic records
from apps.peoples.models import People

for person in People.objects.all():
    if person.email:
        try:
            SecureEncryptionService.decrypt(person.email)
        except ValueError:
            print(f"Re-encrypt needed for person {person.id}")
```

---

## Audit Trail

### Rotation History

| Date | Type | Trigger | Duration | Records | Status |
|------|------|---------|----------|---------|--------|
| Nov 5, 2025 | Initial | Procedure creation | N/A | N/A | Documented |
| Feb 1, 2026 | Scheduled | Q1 rotation | TBD | TBD | Planned |

---

## Contact Information

**Security Team:** security@example.com
**On-Call:** +1-555-SECURITY
**Escalation:** CTO

---

**Document Version:** 1.0
**Last Rotation:** Not yet performed
**Next Rotation:** February 1, 2026
**Procedure Owner:** Security Team
