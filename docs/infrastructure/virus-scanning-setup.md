# Virus Scanning Setup Guide

This guide covers the installation and configuration of ClamAV virus scanning for file uploads.

## Overview

The platform integrates ClamAV virus scanning to prevent malware distribution through file uploads (CVSS 8.6 mitigation). All uploaded files are scanned in real-time before being stored.

## ClamAV Installation

### macOS

```bash
# Install ClamAV via Homebrew
brew install clamav

# Start ClamAV daemon
brew services start clamav

# Verify installation
clamdscan --version
```

### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt-get update

# Install ClamAV and daemon
sudo apt-get install clamav clamav-daemon

# Update virus definitions
sudo freshclam

# Start ClamAV daemon
sudo systemctl start clamav-daemon
sudo systemctl enable clamav-daemon

# Verify installation
clamdscan --version
```

### Linux (RHEL/CentOS)

```bash
# Install EPEL repository (if not already installed)
sudo yum install epel-release

# Install ClamAV
sudo yum install clamav clamav-daemon

# Update virus definitions
sudo freshclam

# Start ClamAV daemon
sudo systemctl start clamd@scan
sudo systemctl enable clamd@scan
```

## Python Library Installation

The `pyclamd` library is included in the base requirements:

```bash
# Activate your virtual environment
source venv/bin/activate

# Install requirements (includes pyclamd==0.4.0)
pip install -r requirements/base-macos.txt  # macOS
# OR
pip install -r requirements/base-linux.txt  # Linux
```

## Configuration

### Environment Variables

Edit your `.env` file:

```bash
# Enable virus scanning for file uploads
FILE_UPLOAD_VIRUS_SCANNING=True

# Optional: Disable if ClamAV not available
# FILE_UPLOAD_VIRUS_SCANNING=False
```

### Django Settings

The virus scanning configuration is in `intelliwiz_config/settings/security/file_upload.py`:

```python
# Virus Scanning Configuration
FILE_UPLOAD_VIRUS_SCANNING = env.bool('FILE_UPLOAD_VIRUS_SCANNING', default=True)

VIRUS_SCANNER_CONFIG = {
    'ENABLE': FILE_UPLOAD_VIRUS_SCANNING,
    'ENGINE': 'clamav',
    'CLAMAV_SOCKET': '/var/run/clamav/clamd.ctl',  # Unix socket path
    'MAX_FILE_SIZE_MB': 50,
    'QUARANTINE_DIR': '/tmp/claude/quarantine/uploads/',
    'FAIL_OPEN': True,  # Allow uploads if scanner unavailable
}
```

### ClamAV Socket Path

The default socket path varies by OS:

- **macOS (Homebrew)**: `/opt/homebrew/var/run/clamav/clamd.sock` or `/usr/local/var/run/clamav/clamd.sock`
- **Ubuntu/Debian**: `/var/run/clamav/clamd.ctl`
- **RHEL/CentOS**: `/var/run/clamd.scan/clamd.sock`

If you need to customize the socket path, edit `/etc/clamav/clamd.conf` (Linux) or `/opt/homebrew/etc/clamav/clamd.conf` (macOS).

## Verification

### Verify ClamAV is Running

```bash
# Check daemon status
# macOS
brew services list | grep clamav

# Linux
sudo systemctl status clamav-daemon  # Ubuntu/Debian
sudo systemctl status clamd@scan     # RHEL/CentOS
```

### Verify Django Integration

```bash
# Activate virtual environment
source venv/bin/activate

# Test import
python manage.py shell -c "from apps.core.security.virus_scanner import VirusScannerService; print('✅ Virus scanner ready' if VirusScannerService else '❌ Import failed')"
```

Expected output: `✅ Virus scanner ready`

### Test with EICAR File

The EICAR test file is a standard malware test file that all antivirus software should detect:

```bash
# Create EICAR test file
echo 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' > eicar.com

# Upload via API (requires authentication)
curl -X POST http://localhost:8000/api/upload/ \
  -F "file=@eicar.com" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected response:**

```json
{
  "error": "Security threat detected",
  "message": "File contains potentially malicious content",
  "code": "MALWARE_DETECTED"
}
```

**Status code:** `403 Forbidden`

### Check Logs

Scan results are logged with structured metadata:

```bash
# Check logs for scan activity
tail -f logs/django.log | grep -i "virus\|malware\|scan"
```

**Clean file log:**
```
INFO File scan clean: document.pdf (filename='document.pdf', size_bytes=12345, scan_time_ms=23)
```

**Malware detection log:**
```
ERROR Malware detected in upload: Eicar-Test-Signature (filename='eicar.com', threat='Eicar-Test-Signature', scan_time_ms=45)
```

## Troubleshooting

### ClamAV Daemon Not Responding

**Symptom:** `ImproperlyConfigured: ClamAV daemon not responding`

**Solution:**

```bash
# Check if daemon is running
# macOS
brew services list | grep clamav

# Linux
sudo systemctl status clamav-daemon

# Restart daemon
# macOS
brew services restart clamav

# Linux
sudo systemctl restart clamav-daemon
```

### Socket Permission Denied

**Symptom:** `PermissionError: [Errno 13] Permission denied: '/var/run/clamav/clamd.ctl'`

**Solution:**

```bash
# Add your user to the clamav group
sudo usermod -a -G clamav $USER

# Restart session or run
newgrp clamav
```

### Virus Definitions Outdated

**Symptom:** ClamAV fails to detect known malware

**Solution:**

```bash
# Update virus definitions
sudo freshclam

# Restart daemon
# macOS
brew services restart clamav

# Linux
sudo systemctl restart clamav-daemon
```

### pyclamd Not Installed

**Symptom:** `WARNING: pyclamd not installed - virus scanning disabled`

**Solution:**

```bash
# Reinstall requirements
source venv/bin/activate
pip install pyclamd==0.4.0
```

## Fail-Open Mode

The virus scanner operates in **fail-open mode** by default:

- If ClamAV is unavailable, uploads are **allowed** (with warning logged)
- This prevents blocking legitimate users during infrastructure issues
- Suitable for development and most production environments

### Enable Fail-Closed Mode (Optional)

For high-security environments, you can reject uploads if scanning fails:

Edit `apps/core/security/virus_scanner.py`:

```python
if not HAS_CLAMAV:
    raise ImproperlyConfigured("ClamAV required but not available")
```

**Warning:** This will block all uploads if ClamAV is unavailable.

## Performance Considerations

### Scan Times

Typical scan times:
- Small files (<1MB): 10-50ms
- Medium files (1-10MB): 50-200ms
- Large files (10-50MB): 200-1000ms

### Async Scanning (Future)

For files >5MB, consider implementing async scanning:

1. Accept upload immediately
2. Queue scan job
3. Quarantine file until scan completes
4. Delete if malware detected

This is configured but not yet implemented:

```python
CLAMAV_SETTINGS = {
    'ASYNC_SCAN_THRESHOLD': 5 * 1024 * 1024,  # 5MB
}
```

## Security Best Practices

1. **Keep Definitions Updated**: Run `freshclam` daily via cron
2. **Monitor Scan Failures**: Alert on ClamAV unavailability
3. **Quarantine Malware**: Store detected files for analysis
4. **Log All Scans**: Maintain audit trail of scan results
5. **Test Regularly**: Use EICAR file to verify detection

## Production Deployment Checklist

- [ ] ClamAV daemon installed and running
- [ ] Virus definitions updated (`freshclam`)
- [ ] `pyclamd` installed in virtual environment
- [ ] `FILE_UPLOAD_VIRUS_SCANNING=True` in `.env`
- [ ] Socket path configured correctly
- [ ] Quarantine directory exists and is writable
- [ ] EICAR test passes (detects malware)
- [ ] Logs show scan activity
- [ ] Monitoring alerts configured for scan failures

## References

- [ClamAV Official Documentation](https://docs.clamav.net/)
- [pyclamd PyPI](https://pypi.org/project/pyclamd/)
- [EICAR Test File](https://www.eicar.org/download-anti-malware-testfile/)
- [OWASP File Upload Security](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)

---

**Last Updated:** November 11, 2025
**Maintainer:** Security Team
