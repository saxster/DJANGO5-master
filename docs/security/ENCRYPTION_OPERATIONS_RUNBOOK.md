# Encryption Operations & Security Runbook

**Version:** 1.0
**Last Updated:** September 27, 2025
**Owner:** Security Operations Team
**Related:** ENCRYPTION_SECURITY_AUDIT.md, FIPS_COMPLIANCE_GUIDE.md

---

## Executive Summary

This runbook provides operational procedures for encryption system management, covering:
- Key escrow and backup procedures
- Disaster recovery for lost encryption keys
- Incident response for encryption failures
- Emergency decryption procedures
- Security monitoring and alerting

**Purpose:** Ensure business continuity and data recoverability while maintaining security.

---

## 1. Key Escrow Procedures

### 1.1 Overview

**Key Escrow** is the secure backup of encryption keys to enable data recovery in case of:
- Catastrophic system failure
- Accidental key deletion
- Employee departure (key holder unavailable)
- Legal/compliance requirements (lawful access)

### 1.2 Key Escrow Strategy

**Multi-Layer Protection:**

```
┌─────────────────────────────────────────────┐
│ SECRET_KEY (Master Key)                     │
│ ├─ Encrypted Backup (Escrow File)          │
│ ├─ Split Key Shares (3-of-5 Shamir)        │
│ └─ Offline Backup (Hardware Token)         │
└─────────────────────────────────────────────┘
```

### 1.3 Escrow Implementation

#### Step 1: Create Key Escrow File

```bash
# Run on secure admin workstation (NOT production server)
python manage.py shell

from django.conf import settings
from apps.core.services.secure_encryption_service import SecureEncryptionService
import json
from datetime import datetime

escrow_data = {
    'secret_key': settings.SECRET_KEY,
    'created_at': datetime.now().isoformat(),
    'created_by': 'security_admin',
    'purpose': 'Key escrow for disaster recovery',
    'environment': 'production'
}

escrow_encrypted = SecureEncryptionService.encrypt(json.dumps(escrow_data))

with open('/secure/escrow/encryption_key_escrow.enc', 'w') as f:
    f.write(escrow_encrypted)

print("✅ Key escrow file created")
```

#### Step 2: Split Key Using Shamir's Secret Sharing

```python
# Install: pip install secretsharing

from secretsharing import PlaintextToHexSecretSharer

# Split SECRET_KEY into 5 shares (need 3 to recover)
shares = PlaintextToHexSecretSharer.split_secret(
    settings.SECRET_KEY,
    threshold=3,
    num_shares=5
)

# Distribute shares to different custodians
custodians = {
    'CTO': shares[0],
    'CISO': shares[1],
    'Lead DevOps': shares[2],
    'Security Manager': shares[3],
    'Compliance Officer': shares[4]
}

for role, share in custodians.items():
    print(f"Share for {role}: {share[:20]}...")
```

#### Step 3: Create Offline Backup

```bash
# Store on encrypted USB drive or hardware security token

# 1. Export SECRET_KEY to secure file
echo "$SECRET_KEY" | gpg --symmetric --armor > secret_key_backup.gpg

# 2. Store on offline media
cp secret_key_backup.gpg /Volumes/SECURE_USB/backups/

# 3. Store in physical safe with access log
# Document in Physical Security Log
```

### 1.4 Escrow Access Controls

**Access Requirements:**
- **Production Keys:** Requires 2 of 3 senior leadership approval
- **Staging Keys:** Requires 1 security team member approval
- **Development Keys:** No escrow required (environment-specific)

**Access Log:**
```
Date        | Accessor          | Reason                    | Approvers
------------|-------------------|---------------------------|-------------------
2025-09-27  | security_admin    | Disaster recovery test    | CTO, CISO
```

---

## 2. Disaster Recovery Procedures

### 2.1 Scenario 1: SECRET_KEY Lost or Corrupted

**Impact:** All encrypted data becomes inaccessible

**Recovery Procedure:**

#### Option A: Restore from Key Escrow

```bash
# 1. Retrieve escrow file
cd /secure/escrow

# 2. Decrypt escrow file
python manage.py shell

from apps.core.services.secure_encryption_service import SecureEncryptionService
import json

with open('encryption_key_escrow.enc', 'r') as f:
    escrow_encrypted = f.read()

escrow_data = json.loads(SecureEncryptionService.decrypt(escrow_encrypted))
recovered_secret_key = escrow_data['secret_key']

# 3. Update environment
# Edit .env.production:
SECRET_KEY=<recovered_secret_key>

# 4. Restart application
sudo systemctl restart django-app

# 5. Validate encryption works
python manage.py shell
from apps.core.services.secure_encryption_service import SecureEncryptionService
result = SecureEncryptionService.validate_encryption_setup()
print(f"Validation: {'✅ PASSED' if result else '❌ FAILED'}")
```

#### Option B: Reconstruct from Shamir Shares

```python
# Require 3 of 5 key custodians

from secretsharing import PlaintextToHexSecretSharer

# Collect 3 shares from custodians
shares = [
    'share_from_cto',
    'share_from_ciso',
    'share_from_devops_lead'
]

# Reconstruct SECRET_KEY
reconstructed_key = PlaintextToHexSecretSharer.recover_secret(shares)

# Update environment and restart
```

#### Option C: Re-encrypt All Data (Last Resort)

```bash
# If no escrow available - generate NEW SECRET_KEY and re-encrypt

# 1. Generate new SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 2. Old data becomes unrecoverable - restore from database backup if needed

# 3. Re-encrypt all user data
python manage.py migrate_secure_encryption --force-reencrypt

# WARNING: Only use if escrow options exhausted
```

### 2.2 Scenario 2: Database Corruption

**Impact:** Encrypted data may be corrupted

**Recovery Procedure:**

```bash
# 1. Assess corruption extent
python manage.py shell

from apps.peoples.models import People

total_users = People.objects.count()
corrupted_users = 0

for user in People.objects.iterator(chunk_size=100):
    try:
        if user.email:
            email = user.email
    except Exception:
        corrupted_users += 1

print(f"Corrupted records: {corrupted_users}/{total_users}")

# 2. Restore from backup if > 1% corruption
if corrupted_users / total_users > 0.01:
    # Restore from last known good backup
    pg_restore -d intelliwiz_db /backups/intelliwiz_db_backup.dump

# 3. Validate encryption after restore
python -m pytest apps/core/tests/test_secure_encryption_service.py -v
```

### 2.3 Scenario 3: Encryption Service Failure

**Impact:** Cannot encrypt/decrypt data

**Recovery Procedure:**

```bash
# 1. Check FIPS validation status
python manage.py verify_fips

# 2. If FIPS tests fail, check OpenSSL
openssl version -a

# 3. Reinstall cryptography library
pip install --force-reinstall cryptography==44.0.0

# 4. Clear cached Fernet instances
python manage.py shell
from apps.core.services.secure_encryption_service import SecureEncryptionService
SecureEncryptionService._fernet_instance = None
SecureEncryptionService._key_derivation_salt = None

# 5. Validate encryption
python -m pytest apps/core/tests/test_secure_encryption_service.py -v
```

---

## 3. Incident Response Procedures

### 3.1 Incident Types

| Incident | Severity | Response Time | Escalation |
|----------|----------|---------------|------------|
| **Key Compromise Suspected** | CRITICAL | < 1 hour | CISO, CTO |
| **Encryption Service Down** | HIGH | < 2 hours | DevOps Lead |
| **Key Expiration** | MEDIUM | < 24 hours | Security Team |
| **Decryption Failures** | HIGH | < 4 hours | DevOps Lead |
| **FIPS Validation Failure** | MEDIUM | < 8 hours | Security Team |

### 3.2 Incident: Suspected Key Compromise

**Indicators:**
- Unauthorized access to SECRET_KEY environment variables
- Suspicious encryption/decryption operations
- Unexpected key rotation requests
- Security alert from monitoring

**Immediate Response (< 1 hour):**

```bash
# 1. Alert security team
# Send to: security@company.com, ciso@company.com

# 2. Assess scope
python manage.py shell

from apps.core.models import EncryptionKeyMetadata
from django.utils import timezone

# Check recent key operations
recent_ops = EncryptionKeyMetadata.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=24)
)

for key in recent_ops:
    print(f"{key.key_id}: {key.rotation_status} at {key.created_at}")

# 3. IMMEDIATE key rotation (don't wait for schedule)
python manage.py rotate_encryption_keys --force --batch-size 1000

# 4. Generate new SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 5. Update environment (coordinated deployment)
# Update .env.production with new SECRET_KEY

# 6. Restart all application servers
sudo systemctl restart django-app

# 7. Monitor for 48 hours
tail -f /var/log/django/security.log | grep -i encryption
```

**Post-Incident Actions:**
- [ ] Review access logs for unauthorized access
- [ ] Rotate all API keys and tokens
- [ ] Audit trail review (who accessed when)
- [ ] Update key escrow with new SECRET_KEY
- [ ] Document incident in security log
- [ ] Conduct post-mortem within 72 hours

### 3.3 Incident: Encryption Service Failure

**Symptoms:**
- Decryption errors increase suddenly
- Users cannot log in (email decryption fails)
- Error logs show "Decryption failed" messages

**Response Procedure:**

```bash
# 1. Check encryption health
python manage.py shell

from apps.core.services.secure_encryption_service import SecureEncryptionService

try:
    result = SecureEncryptionService.validate_encryption_setup()
    print(f"Encryption health: {'✅ OK' if result else '❌ FAILED'}")
except Exception as e:
    print(f"❌ Encryption error: {e}")

# 2. Check FIPS compliance
python manage.py verify_fips

# 3. Check for library corruption
pip install --force-reinstall cryptography

# 4. Clear cached instances
python manage.py shell
from apps.core.services.secure_encryption_service import SecureEncryptionService
SecureEncryptionService._fernet_instance = None
SecureEncryptionService._key_derivation_salt = None

# 5. Run full test suite
python -m pytest apps/core/tests/test_secure_encryption_service.py -v

# 6. If tests pass, restart application
sudo systemctl restart django-app
```

### 3.4 Incident: Mass Decryption Failures

**Symptoms:**
- Multiple users report login issues
- Decryption error rate > 5%
- Specific error: "Invalid token" or "Corrupted data"

**Root Cause Analysis:**

```python
# Check encryption format distribution
from apps.peoples.models import People
from apps.core.services.secure_encryption_service import SecureEncryptionService

total_users = People.objects.count()
v1_format = 0
v2_format = 0
plaintext = 0
corrupted = 0

for user in People.objects.iterator(chunk_size=100):
    try:
        email = user.email
        if email:
            if SecureEncryptionService.is_securely_encrypted(f"FERNET_V1:{email}"):
                v1_format += 1
    except Exception:
        corrupted += 1

print(f"V1 Format: {v1_format}")
print(f"V2 Format: {v2_format}")
print(f"Corrupted: {corrupted}")
print(f"Corruption Rate: {corrupted/total_users:.2%}")
```

**Resolution:**
- If corruption < 1%: Restore affected records from backup
- If corruption > 1%: Full database restore from last good backup
- If corruption > 10%: Critical incident - engage disaster recovery team

---

## 4. Emergency Decryption Procedures

### 4.1 When Emergency Decryption Needed

**Scenarios:**
- Legal requirement (court order)
- Data migration to new system
- Audit requirement (compliance investigation)
- System decommissioning

### 4.2 Emergency Decryption Process

**⚠️ REQUIRES APPROVAL:** CISO + Legal Team

```python
# apps/core/management/commands/emergency_decrypt.py

from django.core.management.base import BaseCommand
from apps.peoples.models import People
from apps.core.services.secure_encryption_service import SecureEncryptionService
import csv

class Command(BaseCommand):
    help = "Emergency decryption of user data (REQUIRES AUTHORIZATION)"

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, required=True)
        parser.add_argument('--auth-token', type=str, required=True)

    def handle(self, *args, **options):
        auth_token = options['auth_token']

        if not self.validate_authorization(auth_token):
            self.stdout.write(self.style.ERROR(
                "❌ AUTHORIZATION REQUIRED - Contact CISO"
            ))
            return

        output_file = options['output']

        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['PeopleCode', 'Name', 'Email', 'Mobile'])

            for user in People.objects.iterator(chunk_size=100):
                writer.writerow([
                    user.peoplecode,
                    user.peoplename,
                    user.email,
                    user.mobno or ''
                ])

        self.stdout.write(self.style.SUCCESS(
            f"✅ Emergency decryption complete: {output_file}"
        ))

        from apps.core.models import AuditLog
        AuditLog.objects.create(
            event_type='EMERGENCY_DECRYPTION',
            user=self.request.user if hasattr(self, 'request') else None,
            details=f"Emergency decryption to {output_file}",
            severity='CRITICAL'
        )

    def validate_authorization(self, token):
        import hashlib
        expected_token = hashlib.sha256(
            f"{settings.SECRET_KEY}:emergency_decrypt".encode()
        ).hexdigest()[:32]

        return token == expected_token
```

**Usage:**
```bash
# Generate auth token (by CISO)
python -c "import hashlib; from django.conf import settings; print(hashlib.sha256(f'{settings.SECRET_KEY}:emergency_decrypt'.encode()).hexdigest()[:32])"

# Run emergency decryption
python manage.py emergency_decrypt \
    --output /secure/exports/emergency_decrypt_2025-09-27.csv \
    --auth-token <generated_token>
```

---

## 5. Key Backup & Recovery

### 5.1 Automated Daily Backup

```bash
# Add to cron: daily at 2 AM
0 2 * * * /app/scripts/backup_encryption_keys.sh

# backup_encryption_keys.sh
#!/bin/bash

BACKUP_DIR="/secure/backups/encryption"
DATE=$(date +%Y-%m-%d)

# Backup SECRET_KEY (encrypted)
echo "$SECRET_KEY" | gpg --symmetric --armor > "$BACKUP_DIR/secret_key_$DATE.gpg"

# Backup encryption key metadata
python manage.py dumpdata core.EncryptionKeyMetadata > "$BACKUP_DIR/key_metadata_$DATE.json"

# Encrypt backup
gpg --symmetric --armor "$BACKUP_DIR/key_metadata_$DATE.json"

# Upload to secure cloud storage (S3 with SSE-KMS)
aws s3 cp "$BACKUP_DIR/secret_key_$DATE.gpg" \
    s3://company-encryption-backups/production/ \
    --sse aws:kms \
    --sse-kms-key-id alias/encryption-backup-key

# Cleanup old backups (keep 90 days)
find "$BACKUP_DIR" -name "*.gpg" -mtime +90 -delete

echo "✅ Encryption key backup complete: $DATE"
```

### 5.2 Key Recovery Testing

**Test quarterly (every 90 days):**

```bash
# 1. Download backup from S3
aws s3 cp s3://company-encryption-backups/production/secret_key_2025-09-27.gpg \
    /tmp/recovery_test.gpg

# 2. Decrypt backup
gpg --decrypt /tmp/recovery_test.gpg

# 3. Verify key format
# Should be 50+ characters

# 4. Test encryption with recovered key
# (In staging environment only!)
export SECRET_KEY_TEST="<recovered_key>"
python manage.py shell
# Run validation tests

# 5. Document test results
echo "Recovery test passed: $(date)" >> /var/log/recovery_tests.log
```

---

## 6. Security Monitoring & Alerting

### 6.1 Encryption Health Monitoring

**Metrics to Monitor:**

| Metric | Threshold | Alert Level | Action |
|--------|-----------|-------------|--------|
| Decryption error rate | > 0.1% | WARNING | Investigate |
| Decryption error rate | > 1% | CRITICAL | Immediate response |
| Key age | > 76 days | WARNING | Schedule rotation |
| Key age | > 85 days | CRITICAL | Rotate immediately |
| FIPS self-test failure | Any | CRITICAL | Stop operations |
| Encryption service latency | > 100ms | WARNING | Performance review |

### 6.2 Monitoring Implementation

```python
# apps/core/management/commands/monitor_encryption_health.py

from django.core.management.base import BaseCommand
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.core.services.encryption_key_manager import EncryptionKeyManager
from apps.core.services.fips_validator import FIPSValidator
import time

class Command(BaseCommand):
    help = "Monitor encryption system health"

    def handle(self, *args, **options):
        health_status = {
            'timestamp': time.time(),
            'checks': {}
        }

        health_status['checks']['encryption_validation'] = \
            SecureEncryptionService.validate_encryption_setup()

        health_status['checks']['fips_validation'] = \
            FIPSValidator.validate_fips_mode()

        EncryptionKeyManager.initialize()
        key_status = EncryptionKeyManager.get_key_status()
        health_status['checks']['key_rotation_needed'] = any(
            key.get('needs_rotation', False)
            for key in key_status.get('keys', [])
        )

        test_data = "health_check_test"
        start_time = time.time()
        try:
            encrypted = SecureEncryptionService.encrypt(test_data)
            decrypted = SecureEncryptionService.decrypt(encrypted)
            latency = (time.time() - start_time) * 1000
            health_status['checks']['encryption_latency_ms'] = latency

            if latency > 100:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  High encryption latency: {latency:.2f}ms"
                ))

        except Exception as e:
            health_status['checks']['encryption_latency_ms'] = None
            health_status['checks']['encryption_error'] = str(e)
            self.stdout.write(self.style.ERROR(
                f"❌ Encryption health check failed: {e}"
            ))

        for check, result in health_status['checks'].items():
            if isinstance(result, bool):
                status = '✅' if result else '❌'
                self.stdout.write(f"{status} {check}: {result}")
            else:
                self.stdout.write(f"ℹ️  {check}: {result}")

        if not all(v for v in health_status['checks'].values() if isinstance(v, bool)):
            self.stdout.write(self.style.ERROR(
                "\n❌ ENCRYPTION HEALTH CHECK FAILED - INVESTIGATE IMMEDIATELY"
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            "\n✅ All encryption health checks passed"
        ))
```

**Schedule:**
```bash
# Add to cron: every 15 minutes
*/15 * * * * python manage.py monitor_encryption_health >> /var/log/encryption_health.log
```

### 6.3 Alert Configuration

```python
# Alert thresholds in settings
ENCRYPTION_MONITORING = {
    'decryption_error_threshold': 0.001,  # 0.1%
    'key_rotation_warning_days': 14,
    'encryption_latency_threshold_ms': 100,
    'alert_email': 'security-alerts@company.com',
    'pagerduty_integration': True,
}

# Alert when thresholds exceeded
def send_encryption_alert(alert_type, details):
    import requests

    if settings.ENCRYPTION_MONITORING.get('pagerduty_integration'):
        requests.post(
            'https://events.pagerduty.com/v2/enqueue',
            json={
                'routing_key': settings.PAGERDUTY_KEY,
                'event_action': 'trigger',
                'payload': {
                    'summary': f"Encryption Alert: {alert_type}",
                    'severity': 'critical',
                    'source': 'django-encryption-monitor',
                    'custom_details': details
                }
            }
        )
```

---

## 7. Compliance Auditing

### 7.1 Monthly Compliance Check

```bash
# Run first Monday of each month

# 1. Generate compliance report
python manage.py generate_compliance_report --output /reports/compliance_$(date +%Y-%m).pdf

# 2. Verify key rotation schedule
python manage.py shell

from apps.core.services.encryption_key_manager import EncryptionKeyManager
status = EncryptionKeyManager.get_key_status()

for key in status['keys']:
    if key.get('needs_rotation'):
        print(f"⚠️  Key {key['key_id']} needs rotation: {key['expires_in_days']} days remaining")

# 3. Check encryption test suite
python -m pytest apps/core/tests/test_fips_compliance.py \
                 apps/core/tests/test_encryption_regulatory_compliance.py \
                 -v --tb=short

# 4. Verify documentation current
git log --since="30 days ago" -- docs/security/ENCRYPTION*.md
```

### 7.2 Quarterly Security Review

```bash
# Every 90 days (aligned with key rotation)

# 1. Full encryption audit
python -m pytest -m security apps/core/tests/ -v --cov=apps.core.services

# 2. Performance validation
python -m pytest apps/core/tests/test_secure_encryption_service.py::ConcurrencyAndPerformanceTest -v

# 3. Update security audit document
# Review: docs/security/ENCRYPTION_SECURITY_AUDIT.md

# 4. Key rotation
python manage.py rotate_encryption_keys --dry-run
python manage.py rotate_encryption_keys

# 5. Update compliance certification
# Generate new certificate with updated dates
```

---

## 8. Emergency Contacts

### 8.1 Escalation Matrix

| Issue Severity | Primary Contact | Secondary Contact | Escalation |
|----------------|----------------|-------------------|------------|
| **CRITICAL** | CISO | CTO | CEO (if > 4 hours) |
| **HIGH** | Security Lead | DevOps Lead | CISO (if > 8 hours) |
| **MEDIUM** | DevOps Engineer | Security Engineer | Security Lead (if > 24 hours) |
| **LOW** | On-call Engineer | DevOps Team | Team Lead (if > 48 hours) |

### 8.2 Contact Information

```
CISO:                ciso@company.com        +1-555-0100
CTO:                 cto@company.com         +1-555-0101
Security Lead:       security@company.com    +1-555-0102
DevOps Lead:         devops@company.com      +1-555-0103
24/7 Hotline:        +1-555-0199

PagerDuty:           https://company.pagerduty.com
Incident Tracker:    https://jira.company.com/secure/
Documentation:       https://docs.company.com/security/
```

---

## 9. Preventive Maintenance

### 9.1 Daily Tasks

```bash
# Automated via cron

# Check encryption health (every 15 min)
*/15 * * * * python manage.py monitor_encryption_health

# Backup encryption keys (daily at 2 AM)
0 2 * * * /app/scripts/backup_encryption_keys.sh

# Check for expiring keys (daily at 9 AM)
0 9 * * * python manage.py check_key_expiration --alert
```

### 9.2 Weekly Tasks

```bash
# Every Monday at 10 AM

# 1. Review encryption logs
tail -1000 /var/log/django/security.log | grep -i encryption

# 2. Check decryption error rate
python manage.py shell
from django.db.models import Count
from apps.core.models import ErrorLog

errors = ErrorLog.objects.filter(
    created_at__gte=timezone.now() - timedelta(days=7),
    error_type__icontains='decrypt'
).count()

print(f"Decryption errors (7 days): {errors}")

# 3. Verify backups
aws s3 ls s3://company-encryption-backups/production/ | tail -10

# 4. Test key recovery (in staging)
# Run recovery procedure in staging environment
```

### 9.3 Monthly Tasks

```bash
# First Monday of each month

# 1. Full compliance validation
python -m pytest apps/core/tests/test_encryption_regulatory_compliance.py -v

# 2. Generate compliance report
python manage.py generate_compliance_report

# 3. Review key inventory
python manage.py shell
from apps.core.services.encryption_key_manager import EncryptionKeyManager
print(EncryptionKeyManager.get_key_status())

# 4. Update documentation if needed
git log --since="30 days ago" -- apps/core/services/*encryption*.py
```

### 9.4 Quarterly Tasks

```bash
# Every 90 days (aligned with key rotation)

# 1. Key rotation
python manage.py rotate_encryption_keys --dry-run
python manage.py rotate_encryption_keys

# 2. Security audit review
# Update: docs/security/ENCRYPTION_SECURITY_AUDIT.md

# 3. Penetration testing
python -m pytest apps/core/tests/test_encryption_penetration.py -v

# 4. Disaster recovery drill
# Test key recovery procedures in staging
```

---

## 10. Compliance Documentation

### 10.1 Required Documentation

**Maintained Documents:**
- [ ] `docs/security/ENCRYPTION_SECURITY_AUDIT.md` - Security audit
- [ ] `docs/security/FIPS_COMPLIANCE_GUIDE.md` - FIPS procedures
- [ ] `docs/encryption-key-rotation-guide.md` - Rotation guide
- [ ] `docs/security/ENCRYPTION_OPERATIONS_RUNBOOK.md` - This document

**Audit Trail:**
- [ ] Key creation/rotation events (EncryptionKeyMetadata)
- [ ] Encryption health check results (/var/log/encryption_health.log)
- [ ] Security incident log (apps.core.models.AuditLog)
- [ ] Compliance test results (pytest reports)

### 10.2 Audit Preparation

**For SOC2/ISO27001 Audit:**

```bash
# 1. Generate evidence package
mkdir -p /tmp/audit_evidence_$(date +%Y-%m)

# 2. Export key metadata
python manage.py dumpdata core.EncryptionKeyMetadata > \
    /tmp/audit_evidence_$(date +%Y-%m)/key_metadata.json

# 3. Export test results
python -m pytest apps/core/tests/test_*compliance*.py \
    --junitxml=/tmp/audit_evidence_$(date +%Y-%m)/test_results.xml

# 4. Export compliance documentation
cp docs/security/*.md /tmp/audit_evidence_$(date +%Y-%m)/

# 5. Generate compliance matrix
python manage.py generate_compliance_report \
    --format pdf \
    --output /tmp/audit_evidence_$(date +%Y-%m)/compliance_report.pdf

# 6. Create evidence archive
tar czf audit_evidence_$(date +%Y-%m).tar.gz \
    /tmp/audit_evidence_$(date +%Y-%m)/

# 7. Upload to audit portal
# (Organization-specific process)
```

---

## 11. Troubleshooting Guide

### 11.1 Common Issues

#### Issue: "Decryption failed - invalid or corrupted data"

**Cause:** Data encrypted with different key or corrupted

**Resolution:**
```bash
# 1. Check if data uses old key
python manage.py shell

from apps.core.services.encryption_key_manager import EncryptionKeyManager
EncryptionKeyManager.initialize()

# Check active keys
status = EncryptionKeyManager.get_key_status()
print(f"Active keys: {status['active_keys_count']}")

# 2. If old key retired, reactivate temporarily
from apps.core.models import EncryptionKeyMetadata
old_key = EncryptionKeyMetadata.objects.get(key_id='<old_key_id>')
old_key.is_active = True
old_key.save()

# 3. Re-encrypt data with current key
python manage.py migrate_secure_encryption --key-id <old_key_id>
```

#### Issue: "Key rotation failed mid-process"

**Cause:** Error during data migration

**Resolution:**
```bash
# Rollback is automatic, but verify:
python manage.py shell

from apps.core.models import EncryptionKeyMetadata

stuck_keys = EncryptionKeyMetadata.objects.filter(rotation_status='rotating')

for key in stuck_keys:
    # Reset to 'created' status
    key.rotation_status = 'created'
    key.save()
    print(f"Reset {key.key_id} status")

# Retry rotation
python manage.py rotate_encryption_keys
```

#### Issue: "FIPS validation failed"

**Cause:** Non-FIPS OpenSSL or misconfiguration

**Resolution:**
```bash
# 1. Check OpenSSL version
openssl version -a

# 2. Check FIPS module
python -c "import ssl; print(ssl.OPENSSL_VERSION)"

# 3. If FIPS required, reinstall FIPS OpenSSL
# See: FIPS_COMPLIANCE_GUIDE.md Section 3

# 4. If FIPS not required, disable FIPS checks
# Edit .env:
FIPS_MODE_ENABLED=false
```

---

## 12. Security Best Practices

### 12.1 Key Management

1. **Never commit keys to version control**
   ```bash
   # Verify .env files in .gitignore
   grep -r "SECRET_KEY" .env* || echo "No secrets in git"
   ```

2. **Rotate keys every 90 days**
   ```bash
   # Set calendar reminder
   # Run: python manage.py rotate_encryption_keys
   ```

3. **Test recovery procedures quarterly**
   ```bash
   # Recovery drill checklist:
   # [ ] Retrieve key from escrow
   # [ ] Restore from Shamir shares
   # [ ] Validate decryption works
   # [ ] Document lessons learned
   ```

4. **Monitor key expiration**
   ```bash
   # Daily check (automated)
   python manage.py check_key_expiration --alert
   ```

### 12.2 Incident Response

1. **Prepare runbooks** (this document)
2. **Test procedures** in staging quarterly
3. **Document all incidents** in security log
4. **Conduct post-mortems** within 72 hours
5. **Update procedures** based on lessons learned

### 12.3 Compliance Maintenance

1. **Run compliance tests** before each deployment
2. **Update documentation** when procedures change
3. **Generate compliance reports** monthly
4. **Conduct security reviews** quarterly

---

## 13. Appendix: Checklists

### 13.1 Key Rotation Checklist

- [ ] Key age > 76 days (approaching expiration)
- [ ] Run dry-run: `python manage.py rotate_encryption_keys --dry-run`
- [ ] Schedule maintenance window (2-4 hours)
- [ ] Notify stakeholders
- [ ] Backup current database
- [ ] Run rotation: `python manage.py rotate_encryption_keys`
- [ ] Verify success
- [ ] Update key escrow
- [ ] Document rotation in audit log
- [ ] Monitor for 48 hours post-rotation

### 13.2 Disaster Recovery Checklist

- [ ] Identify failure type (key loss, corruption, service failure)
- [ ] Escalate to appropriate team
- [ ] Attempt primary recovery (key escrow)
- [ ] If failed, attempt secondary recovery (Shamir shares)
- [ ] If failed, restore from database backup
- [ ] Validate encryption after recovery
- [ ] Run full test suite
- [ ] Document incident
- [ ] Update procedures if gaps found

### 13.3 Monthly Security Review Checklist

- [ ] Run encryption health monitor
- [ ] Check decryption error rate
- [ ] Review encryption logs
- [ ] Verify key backups exist
- [ ] Run compliance test suite
- [ ] Generate compliance report
- [ ] Check for security advisories
- [ ] Update documentation if needed

---

## 14. References

### Internal Documentation
- `docs/security/ENCRYPTION_SECURITY_AUDIT.md` - Security audit
- `docs/security/FIPS_COMPLIANCE_GUIDE.md` - FIPS procedures
- `docs/encryption-key-rotation-guide.md` - Key rotation
- `.claude/rules.md` - Rule #2 (Encryption audit requirement)

### External Standards
- [NIST SP 800-57](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final) - Key Management
- [NIST SP 800-88](https://csrc.nist.gov/publications/detail/sp/800-88/rev-1/final) - Media Sanitization
- [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)

### Emergency Procedures
- Physical Security: Contact Building Security +1-555-0200
- Cyber Insurance: Claim hotline +1-555-0300
- Legal Team: legal@company.com +1-555-0400

---

**Document Owner:** Security Operations Team
**Review Frequency:** Quarterly
**Next Review:** December 27, 2025
**Version:** 1.0