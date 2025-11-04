# Biometric Template Encryption - Deployment Guide

## Overview

This guide covers the deployment of field-level encryption for biometric templates in the attendance system. This critical security enhancement protects sensitive biometric data at rest in the database.

**Status**: Phase 1.1 Complete
**Priority**: CRITICAL (Security)
**Compliance**: Data Protection Best Practices, OWASP Top 10 2024
**Date**: November 3, 2025

---

## What Changed

### Security Enhancement
- **Before**: Biometric templates stored as plaintext JSON in database
- **After**: Biometric templates encrypted using Fernet (AES-128-CBC + HMAC)

### Technical Changes
1. **New Encryption Service**: `apps/core/encryption/biometric_encryption.py`
2. **Custom Field Type**: `apps/core/fields/encrypted_json_field.py`
3. **Model Update**: `PeopleEventlog.peventlogextras` now uses `EncryptedJSONField`
4. **Migration**: `0022_encrypt_biometric_templates.py`
5. **Data Migration Tool**: `encrypt_existing_biometric_data` management command

---

## Pre-Deployment Checklist

### 1. Generate Encryption Key

**CRITICAL**: Generate a strong encryption key and store it securely.

```bash
# Generate key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Output example:
# dGhpc19pc19hX3NlY3VyZV9rZXlfZm9yX3Byb2R1Y3Rpb25f...
```

### 2. Secure Key Storage

**Production environments MUST use secure key management:**

#### Option A: Environment Variable (Minimum Security)
```bash
export BIOMETRIC_ENCRYPTION_KEY="your-generated-key-here"
```

#### Option B: AWS Systems Manager Parameter Store (Recommended)
```bash
aws ssm put-parameter \
    --name "/intelliwiz/production/biometric-encryption-key" \
    --value "your-generated-key-here" \
    --type "SecureString" \
    --key-id "alias/aws/ssm"
```

#### Option C: HashiCorp Vault (Enterprise)
```bash
vault kv put secret/intelliwiz/biometric-encryption-key \
    value="your-generated-key-here"
```

#### Option D: Azure Key Vault
```bash
az keyvault secret set \
    --vault-name "intelliwiz-keyvault" \
    --name "biometric-encryption-key" \
    --value "your-generated-key-here"
```

### 3. Backup Database

**REQUIRED**: Create a full database backup before deployment.

```bash
# PostgreSQL backup
pg_dump -h localhost -U postgres -d intelliwiz_db \
    --format=custom \
    --file=backup_pre_encryption_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
pg_restore --list backup_pre_encryption_*.dump | head -20
```

### 4. Test in Staging

Deploy to staging environment first and verify:
- [ ] Encryption key loaded correctly
- [ ] Existing records can be encrypted
- [ ] Face recognition still works
- [ ] API endpoints function normally
- [ ] Performance acceptable (<50ms overhead)

---

## Deployment Steps

### Step 1: Deploy Code Changes

```bash
# Pull latest code
git pull origin feature/biometric-encryption

# Install dependencies (already in requirements/encryption.txt)
pip install cryptography>=44.0.1 django-fernet-fields>=0.6

# Verify imports work
python -c "from apps.core.encryption import BiometricEncryptionService; print('✓ OK')"
```

### Step 2: Set Encryption Key

```bash
# Production
export BIOMETRIC_ENCRYPTION_KEY="your-secure-production-key"

# Verify key is loaded
python manage.py shell -c "from django.conf import settings; print('Key loaded:', bool(settings.BIOMETRIC_ENCRYPTION_KEY))"
```

### Step 3: Run Database Migration

```bash
# Apply schema migration
python manage.py migrate attendance 0022

# Verify migration applied
python manage.py showmigrations attendance | grep 0022
```

### Step 4: Encrypt Existing Data

**IMPORTANT**: This is a one-time operation. Run with `--dry-run` first!

```bash
# Dry run (preview changes)
python manage.py encrypt_existing_biometric_data --dry-run

# Review output, then run for real
python manage.py encrypt_existing_biometric_data \
    --batch-size=1000 \
    --backup-file=/var/backups/biometric_backup_$(date +%Y%m%d).json \
    --skip-encrypted

# Expected output:
# Total attendance records: 45,823
# Records already encrypted: 0
# Records needing encryption: 12,456
#
# Processing batch 1 (1000 records)...
#   Encrypted 1000 records...
# ...
# ✓ Database updated successfully
```

### Step 5: Verify Encryption

```bash
# Check database - data should be encrypted
python manage.py dbshell -c "
SELECT
    id,
    LENGTH(peventlogextras) as encrypted_length,
    LEFT(peventlogextras, 20) as encrypted_prefix
FROM peopleeventlog
WHERE peventlogextras IS NOT NULL
LIMIT 5;
"

# Expected: encrypted_prefix should start with 'gAAAAA' (Fernet signature)
```

### Step 6: Test Face Recognition

```bash
# Test API endpoint
curl -X POST http://localhost:8000/api/v1/attendance/clock-in/ \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "lat": 37.7749,
        "lng": -122.4194,
        "face_image": "base64_encoded_image_here"
    }'

# Verify response includes face recognition status
# Check logs for encryption/decryption operations
```

### Step 7: Monitor Performance

```bash
# Check encryption overhead
python manage.py shell << EOF
from django.test.utils import override_settings
from django.utils import timezone
import time

# Measure clock-in with encryption
start = time.time()
# ... perform clock-in test ...
duration = time.time() - start

print(f"Clock-in with encryption: {duration*1000:.2f}ms")
# Expected: <300ms p95
EOF
```

---

## Rollback Procedure

If encryption causes issues, follow this rollback:

### Option 1: Revert to Plaintext (NOT RECOMMENDED - Security Risk)

```bash
# 1. Restore database backup
pg_restore -h localhost -U postgres -d intelliwiz_db \
    --clean --if-exists backup_pre_encryption_*.dump

# 2. Revert code changes
git revert <commit-hash>

# 3. Run migrations backward
python manage.py migrate attendance 0021
```

### Option 2: Fix Forward (Recommended)

```bash
# 1. Check logs for specific error
tail -f /var/log/intelliwiz/app.log | grep -i "encryption\|biometric"

# 2. Verify encryption key
python manage.py shell -c "from apps.core.encryption import BiometricEncryptionService; print(BiometricEncryptionService.get_encryption_key()[:10])"

# 3. Re-run data migration if needed
python manage.py encrypt_existing_biometric_data --skip-encrypted
```

---

## Post-Deployment Verification

### 1. Functional Tests

- [ ] Clock-in with face recognition works
- [ ] Clock-out with face recognition works
- [ ] Attendance history displays correctly
- [ ] Face recognition verification status visible
- [ ] Admin interface shows attendance records
- [ ] Mobile API endpoints function normally

### 2. Security Validation

```bash
# Verify data is encrypted in database
python manage.py dbshell -c "
SELECT COUNT(*) as total,
       COUNT(CASE WHEN peventlogextras LIKE 'gAAAAA%' THEN 1 END) as encrypted
FROM peopleeventlog
WHERE peventlogextras IS NOT NULL;
"

# Expected: encrypted = total (100% encryption rate)
```

### 3. Performance Monitoring

Monitor these metrics for 24-48 hours:

- **API Latency**: Should remain <300ms p95
- **Encryption Overhead**: <50ms per operation
- **Database CPU**: Should not increase >5%
- **Error Rate**: Should be <0.1%

---

## Troubleshooting

### Issue: "Invalid BIOMETRIC_ENCRYPTION_KEY format"

**Cause**: Encryption key not set or malformed
**Solution**:
```bash
# Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in environment
export BIOMETRIC_ENCRYPTION_KEY="newly-generated-key"

# Restart application
systemctl restart intelliwiz
```

### Issue: "Decryption failed: Invalid token"

**Cause**: Data encrypted with different key than currently configured
**Solution**:
```bash
# Check if backup key exists
echo $BIOMETRIC_ENCRYPTION_KEY_BACKUP

# If yes, try key rotation
python manage.py rotate_encryption_keys \
    --old-key=$BIOMETRIC_ENCRYPTION_KEY_BACKUP \
    --new-key=$BIOMETRIC_ENCRYPTION_KEY
```

### Issue: "Face recognition not working after encryption"

**Cause**: Encrypted data may be corrupted
**Solution**:
```bash
# Verify specific record
python manage.py shell << EOF
from apps.attendance.models import PeopleEventlog
record = PeopleEventlog.objects.first()
print("Extras:", record.peventlogextras)
print("Status:", record.get_face_recognition_status())
EOF

# If corrupted, restore from backup
python manage.py restore_from_backup --backup-file=/var/backups/biometric_backup_*.json
```

### Issue: "Performance degradation after encryption"

**Cause**: Encryption overhead or database load
**Solution**:
```bash
# Check slow query log
cat /var/log/postgresql/postgresql-*.log | grep "duration: [0-9][0-9][0-9][0-9]"

# Analyze query performance
python manage.py benchmark_encryption_performance

# Consider caching if needed
python manage.py cache_warm --model=attendance
```

---

## Security Best Practices

### Key Rotation Schedule

**Recommended**: Rotate encryption keys every 90 days

```bash
# Generate new key
NEW_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Rotate all encrypted data
python manage.py rotate_encryption_keys \
    --old-key=$BIOMETRIC_ENCRYPTION_KEY \
    --new-key=$NEW_KEY \
    --batch-size=1000

# Update environment
export BIOMETRIC_ENCRYPTION_KEY_BACKUP=$BIOMETRIC_ENCRYPTION_KEY
export BIOMETRIC_ENCRYPTION_KEY=$NEW_KEY

# Restart application
systemctl restart intelliwiz
```

### Access Control

```bash
# Encryption key should only be accessible to:
# - Application runtime user
# - DevOps/SRE team (break-glass access)

# File permissions (if using file-based key)
chmod 400 /etc/intelliwiz/encryption.key
chown intelliwiz:intelliwiz /etc/intelliwiz/encryption.key

# AWS IAM policy (if using Parameter Store)
{
  "Effect": "Allow",
  "Action": ["ssm:GetParameter"],
  "Resource": "arn:aws:ssm:*:*:parameter/intelliwiz/*/biometric-encryption-key"
}
```

### Audit Logging

```bash
# Enable encryption audit logging in settings
ENCRYPTION_AUDIT_LOGGING = True

# Monitor audit logs
tail -f /var/log/intelliwiz/encryption_audit.log

# Review monthly
python manage.py generate_encryption_audit_report --month=11 --year=2025
```

---

## Success Metrics

After deployment, you should achieve:

✅ **100% of biometric templates encrypted at rest**
✅ **<50ms encryption/decryption overhead**
✅ **Zero plaintext biometric data in database**
✅ **Face recognition accuracy unchanged**
✅ **Compliance with data protection standards**

---

## Support & Escalation

**Issues during deployment?**

1. **Check logs first**: `/var/log/intelliwiz/app.log`
2. **Review troubleshooting section** above
3. **Rollback if critical**: Follow rollback procedure
4. **Escalate to security team** if data breach suspected

**Emergency Contacts:**
- Security Team: security@intelliwiz.com
- DevOps On-Call: +1-XXX-XXX-XXXX
- Database Team: dba@intelliwiz.com

---

## Additional Resources

- **Fernet Specification**: https://github.com/fernet/spec/
- **OWASP Cryptographic Storage**: https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- **Django Field Encryption**: https://django-fernet-fields.readthedocs.io/

---

**Document Version**: 1.0
**Last Updated**: November 3, 2025
**Maintained By**: Security Engineering Team
**Review Cycle**: Quarterly
