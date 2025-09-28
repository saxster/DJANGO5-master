# ClamAV Malware Scanning Integration Guide

## Overview

This guide details the setup and configuration of ClamAV antivirus for the Django 5 Enterprise Platform's file upload security system.

**Integration Point:** `apps/core/services/advanced_file_validation_service.py`
**Compliance:** Rule #14 - File Upload Security (`.claude/rules.md`)
**Security Enhancement:** CVSS 7.5 → 9.2 with malware scanning

---

## Prerequisites

- Python 3.10+
- PostgreSQL 14.2+
- Django 5.2.1
- Root or sudo access for installation
- Network access for signature updates

---

## Installation

### macOS (Homebrew)

```bash
brew install clamav

freshclam
sudo freshclam

launchctl load ~/Library/LaunchAgents/homebrew.mxcl.clamav.plist
```

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y clamav clamav-daemon clamav-freshclam

sudo systemctl stop clamav-freshclam
sudo freshclam

sudo systemctl enable clamav-daemon
sudo systemctl enable clamav-freshclam
sudo systemctl start clamav-daemon
sudo systemctl start clamav-freshclam
```

### Red Hat/CentOS/Fedora

```bash
sudo yum install -y epel-release
sudo yum install -y clamav clamav-update clamd

sudo freshclam

sudo systemctl enable clamd@scan
sudo systemctl start clamd@scan
```

### Docker (Production Recommended)

```dockerfile
FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y clamav clamav-daemon && \
    freshclam && \
    rm -rf /var/lib/apt/lists/*

CMD ["clamd"]
```

---

## Configuration

### 1. Update Virus Signature Database

```bash
sudo freshclam
```

**Automatic Updates (Recommended):**

**Linux systemd:**
```bash
sudo systemctl enable clamav-freshclam
sudo systemctl start clamav-freshclam
```

**macOS launchd:**
```bash
sudo launchctl load -w /Library/LaunchDaemons/org.clamav.freshclam.plist
```

**Cron (Fallback):**
```bash
sudo crontab -e

0 */6 * * * /usr/bin/freshclam --quiet
```

### 2. Django Settings Configuration

**File:** `intelliwiz_config/settings/security/file_upload.py`

```python
FILE_UPLOAD_CONTENT_SECURITY = {
    'ENABLE_MAGIC_NUMBER_VALIDATION': True,
    'ENABLE_FILENAME_SANITIZATION': True,
    'ENABLE_PATH_TRAVERSAL_PROTECTION': True,
    'ENABLE_MALWARE_SCANNING': True,
    'QUARANTINE_SUSPICIOUS_FILES': True,
}

CLAMAV_SETTINGS = {
    'ENABLED': True,
    'SCAN_TIMEOUT': 30,
    'QUARANTINE_DIR': '/var/quarantine/uploads/',
    'ALERT_ON_INFECTION': True,
    'BLOCK_ON_SCAN_FAILURE': True,
    'MAX_FILE_SIZE': 100 * 1024 * 1024,
}
```

### 3. Environment Variables

Add to `.env.dev.secure` or `.env.production`:

```bash
ENABLE_MALWARE_SCANNING=true

CLAMAV_SCAN_TIMEOUT=30

QUARANTINE_DIR=/var/quarantine/uploads/

CLAMAV_ALERT_EMAIL=security@yourcompany.com
```

### 4. Create Quarantine Directory

```bash
sudo mkdir -p /var/quarantine/uploads/
sudo chown -R www-data:www-data /var/quarantine/uploads/
sudo chmod 750 /var/quarantine/uploads/
```

---

## Verification

### Test ClamAV Installation

```bash
echo "X5O!P%@AP[4\PZX54(P^)7CC)7}\$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!\$H+H*" > /tmp/eicar.txt
clamscan /tmp/eicar.txt
rm /tmp/eicar.txt
```

**Expected Output:**
```
/tmp/eicar.txt: Eicar-Test-Signature FOUND
```

### Test Django Integration

```bash
python manage.py shell

from apps.core.services.advanced_file_validation_service import AdvancedFileValidationService
AdvancedFileValidationService._is_clamav_available()
```

**Expected:** `True`

### Test File Upload with Malware Scanning

```python
import io
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.core.services.advanced_file_validation_service import AdvancedFileValidationService

test_file = SimpleUploadedFile(
    "test.jpg",
    b"\xff\xd8\xff\xe0",
    content_type="image/jpeg"
)

result = AdvancedFileValidationService.validate_and_scan_file(
    test_file,
    'image',
    {'people_id': '123', 'folder_type': 'test'}
)

print(f"Scan Result: {result['malware_scan']['scan_result']}")
print(f"Threat Level: {result['risk_assessment']['threat_level']}")
```

---

## Monitoring & Alerting

### 1. ClamAV Log Monitoring

**Log Locations:**
- Ubuntu/Debian: `/var/log/clamav/freshclam.log`
- macOS: `/usr/local/var/log/clamav/freshclam.log`
- Docker: `/var/log/clamav/`

### 2. Application Logs

Check Django logs for malware scanning events:

```bash
grep "malware" /path/to/logs/django.log
grep "INFECTED" /path/to/logs/django.log
grep "QUARANTINE" /path/to/logs/django.log
```

### 3. Automated Alerts

The system automatically logs malware detection events with:
- Correlation ID for tracking
- User ID and IP address
- File hash and metadata
- Scan results and threat level

**Alert Triggers:**
- Malware detected (`threat_level = CRITICAL`)
- Scan failures (`scan_result = ERROR`)
- High anomaly scores (`anomaly_score > 50`)

---

## Troubleshooting

### ClamAV Not Found

**Symptom:** `clamscan: command not found`

**Solution:**
```bash
which clamscan
export PATH="/usr/local/bin:$PATH"

sudo ln -s /usr/local/bin/clamscan /usr/bin/clamscan
```

### Permission Denied on Temp Files

**Symptom:** `Permission denied: /tmp/tmpXXXXXX`

**Solution:**
```bash
sudo chmod 1777 /tmp
mkdir -p /tmp/clamav_scan/
chmod 755 /tmp/clamav_scan/
```

### Signature Database Out of Date

**Symptom:** `WARNING: Current functionality level = X, required = Y`

**Solution:**
```bash
sudo freshclam
sudo systemctl restart clamav-daemon
```

### Scan Timeout

**Symptom:** `Scan timeout exceeded`

**Solution:** Increase timeout in settings:
```python
CLAMAV_SETTINGS = {
    'SCAN_TIMEOUT': 60,
}
```

---

## Performance Optimization

### 1. Clamd Daemon (Recommended for Production)

Using `clamd` daemon instead of `clamscan` improves performance significantly:

```python
import pyclamd

cd = pyclamd.ClamdUnixSocket()
if cd.ping():
    scan_result = cd.scan_file('/path/to/file')
```

**Installation:**
```bash
pip install pyClamd

sudo systemctl start clamav-daemon
```

### 2. Async Scanning

For large files, use async scanning:

```python
from background_tasks.tasks import scan_file_for_malware_async

scan_file_for_malware_async.delay(file_path, correlation_id)
```

### 3. Selective Scanning

Only scan high-risk file types:

```python
SCAN_FILE_TYPES = ['pdf', 'document', 'archive']

if file_type in SCAN_FILE_TYPES:
    malware_scan = AdvancedFileValidationService._scan_for_malware(...)
```

---

## Security Best Practices

### 1. Regular Signature Updates

```bash
sudo freshclam

cat /var/log/clamav/freshclam.log
```

### 2. Quarantine Management

```bash
ls -lh /var/quarantine/uploads/

find /var/quarantine/uploads/ -mtime +30 -delete
```

### 3. Scan Performance Monitoring

```bash
grep "scan_duration_ms" /path/to/logs/django.log | awk '{sum+=$NF} END {print "Average scan time: "sum/NR"ms"}'
```

### 4. False Positive Handling

If legitimate files are flagged:

1. Verify file is actually safe
2. Calculate file hash: `sha256sum file.pdf`
3. Add to ClamAV whitelist: `sudo clamscan --gen-json | grep hash`
4. Report to security team

---

## Integration with CI/CD

### GitHub Actions

```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  malware-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install ClamAV
        run: |
          sudo apt-get update
          sudo apt-get install -y clamav
          sudo freshclam

      - name: Scan Repository
        run: |
          clamscan -r --bell --infected .
```

### Pre-commit Hook Integration

Add to `.githooks/pre-commit`:

```bash
if command -v clamscan >/dev/null 2>&1; then
    staged_files=$(git diff --cached --name-only --diff-filter=ACM)
    for file in $staged_files; do
        if [ -f "$file" ]; then
            clamscan --quiet --no-summary "$file"
            if [ $? -eq 1 ]; then
                echo "❌ Malware detected in $file"
                exit 1
            fi
        fi
    done
fi
```

---

## Compliance & Audit

### SOC 2 Compliance

ClamAV malware scanning helps meet SOC 2 requirements:
- **CC6.1:** Malware protection controls
- **CC6.6:** Protection against malicious software
- **CC7.2:** System monitoring for security events

### Audit Logs

All scanning activity is logged with:
- Timestamp
- File hash
- Scan result
- User context
- Correlation ID

**Query Audit Logs:**
```python
from django.utils import timezone
from datetime import timedelta

recent_scans = AuditLog.objects.filter(
    event_type='FILE_UPLOAD_SCAN',
    timestamp__gte=timezone.now() - timedelta(days=7)
)

infected_count = recent_scans.filter(scan_result='INFECTED').count()
```

---

## Support & Maintenance

### Regular Maintenance Tasks

**Daily:**
- Monitor scan logs for infections
- Review quarantined files
- Check signature database freshness

**Weekly:**
- Analyze scan performance metrics
- Review false positive reports
- Update ClamAV if needed

**Monthly:**
- Audit quarantine directory size
- Review and purge old quarantined files
- Test disaster recovery procedures

### Getting Help

**ClamAV Community:**
- Documentation: https://docs.clamav.net/
- Forum: https://forums.clamav.net/
- GitHub: https://github.com/Cisco-Talos/clamav

**Django Integration:**
- Internal: Contact security@yourcompany.com
- Documentation: `docs/security/`

---

## Appendix: Sample Configuration Files

### `/etc/clamav/clamd.conf` (Production)

```conf
TCPSocket 3310
TCPAddr 127.0.0.1
MaxThreads 20
MaxConnectionQueueLength 200
StreamMaxLength 100M
MaxDirectoryRecursion 20
FollowDirectorySymlinks yes
FollowFileSymlinks yes
SelfCheck 3600
```

### `/etc/clamav/freshclam.conf` (Production)

```conf
DatabaseDirectory /var/lib/clamav
UpdateLogFile /var/log/clamav/freshclam.log
DatabaseOwner clamav
DatabaseMirror database.clamav.net
NotifyClamd /etc/clamav/clamd.conf
Checks 24
```

---

**Document Version:** 1.0
**Last Updated:** 2025-09-27
**Maintained By:** Security Team
**Next Review:** 2025-12-27