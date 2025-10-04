# Secret Validation Logging - Security Guide

**Status:** ✅ IMPLEMENTED
**Last Updated:** 2025-10-01
**Compliance:** Rule 15 - Logging Data Sanitization

---

## Overview

This document describes the secure logging infrastructure for secret validation in the Django 5 IntelliWiz application. The implementation prevents sensitive information leakage through console output and log files while maintaining debuggability through correlation IDs.

## Problem Statement

**Original Issue:** Secret validation results were printed to stdout using `print()` statements, creating security risks:

- Console output may be captured by log aggregators, CI/CD systems, or container orchestrators
- Remediation details exposed validation requirements to potential attackers
- No structured logging or correlation IDs for debugging
- Violated Rule 15: Logging Data Sanitization

**Risk Level:** MEDIUM to HIGH

**Affected Files:**
- `intelliwiz_config/settings/development.py` (lines 44, 47-49)
- `intelliwiz_config/settings/production.py` (lines 38, 41-43)

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Startup                       │
│            (development.py / production.py)                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ validate_secret_key()
                  │ validate_encryption_key()
                  │ validate_admin_password()
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              SecretValidator (validation.py)                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  - Validates secret strength                        │   │
│  │  - Calculates entropy                               │   │
│  │  - Checks character diversity                       │   │
│  └─────────────────┬───────────────────────────────────┘   │
└────────────────────┼───────────────────────────────────────┘
                     │
                     │ SecretValidationLogger.log_*()
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         SecretValidationLogger (validation.py)               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  - Sanitizes all messages                           │   │
│  │  - Removes secret values from logs                  │   │
│  │  - Generates correlation IDs                        │   │
│  │  - Logs to structured logger                        │   │
│  └─────────────────┬───────────────────────────────────┘   │
└────────────────────┼───────────────────────────────────────┘
                     │
                     │ logging.getLogger('security.secret_validation')
                     ▼
┌─────────────────────────────────────────────────────────────┐
│        Logging Configuration (logging.py)                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Development: File logging only (not console)       │   │
│  │  Production: Security file + mail admins            │   │
│  │  Sanitization filter applied automatically          │   │
│  └─────────────────┬───────────────────────────────────┘   │
└────────────────────┼───────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Log Files                                 │
│  Development: /tmp/youtility4_logs/django_dev.log           │
│  Production:  /var/log/youtility4/security.log              │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. SecretValidationLogger Class

**Location:** `apps/core/validation.py`

**Key Methods:**

#### `log_validation_success()`
Logs successful secret validation with safe metadata only.

```python
SecretValidationLogger.log_validation_success(
    secret_name='SECRET_KEY',
    secret_type='secret_key',
    metadata={'length': 50, 'entropy': 4.8, 'char_types_count': 4}
)
```

**Logged Information:**
- ✅ Secret name (e.g., 'SECRET_KEY')
- ✅ Secret type (e.g., 'secret_key', 'encryption_key', 'admin_password')
- ✅ Safe metadata (length, entropy - numeric values only)
- ❌ **NEVER** the actual secret value

#### `log_validation_error()`
Logs validation failures with correlation IDs for debugging.

```python
SecretValidationLogger.log_validation_error(
    secret_name='SECRET_KEY',
    secret_type='secret_key',
    error_category='length',
    correlation_id='abc-123-def-456'
)
```

**Logged Information:**
- ✅ Secret name
- ✅ Generic error category (length, entropy, format, missing)
- ✅ Correlation ID for debugging
- ✅ Generic remediation guidance only
- ❌ **NEVER** specific validation requirements
- ❌ **NEVER** the actual secret value

#### `_sanitize_message()`
Removes potential secret values from messages before logging.

**Patterns Sanitized:**
- Quoted strings longer than 8 characters
- Base64-like strings (32+ characters)
- Long alphanumeric strings (50+ characters)

### 2. Settings File Implementation

#### Development Environment

**File:** `intelliwiz_config/settings/development.py`

**Before (INSECURE):**
```python
print("✅ All secrets validated successfully in development environment")
print(f"🔧 REMEDIATION: {e.remediation}")  # Exposes validation logic!
```

**After (SECURE):**
```python
from apps.core.validation import SecretValidationLogger, SecretValidationError
import logging

secret_logger = logging.getLogger("security.secret_validation")

try:
    # Validation happens here
    secret_logger.info("All secrets validated successfully",
                      extra={'environment': 'development', 'status': 'startup_success'})
except SecretValidationError as e:
    correlation_id = str(uuid.uuid4())

    SecretValidationLogger.log_validation_error(
        e.secret_name, 'unknown', 'validation_failed', correlation_id
    )

    # Console output: Generic guidance only
    print(f"\n🚨 CRITICAL: Secret validation failed (correlation_id: {correlation_id})")
    print("📋 Check logs for details: /tmp/youtility4_logs/django_dev.log")
```

**Key Changes:**
- ✅ Uses structured logger instead of print
- ✅ Correlation IDs for debugging
- ✅ Generic console messages (no sensitive details)
- ✅ Detailed logs go to files only

#### Production Environment

**File:** `intelliwiz_config/settings/production.py`

**Differences from Development:**
- Even more minimal console output
- No remediation hints in console
- Logs to secure file with restricted permissions
- Email alerts for critical errors

---

## Logging Configuration

**File:** `intelliwiz_config/settings/logging.py`

### Development Configuration

```python
"security.secret_validation": {
    "handlers": ["app_file"],        # File only, NOT console
    "level": "INFO",
    "propagate": False,
    "filters": ["sanitize"]          # Automatic sanitization
}
```

**Log File:** `/tmp/youtility4_logs/django_dev.log`

### Production Configuration

```python
"security.secret_validation": {
    "handlers": ["security_file", "mail_admins"],
    "level": "INFO",
    "propagate": False,
    "filters": ["sanitize"]
}
```

**Log Files:**
- `/var/log/youtility4/security.log` (90 day retention)
- Email alerts to admins for CRITICAL errors

---

## Security Guarantees

### What is NEVER Logged

❌ **Actual secret values** (SECRET_KEY, ENCRYPT_KEY, SUPERADMIN_PASSWORD)
❌ **Specific validation requirements** (e.g., "must be 50 characters")
❌ **Detailed remediation steps** (exposes validation logic)
❌ **Secret patterns or formats** (helps attackers guess valid formats)
❌ **Partial secret values** (even first/last characters)

### What IS Logged

✅ **Secret names** (e.g., 'SECRET_KEY', 'ENCRYPT_KEY')
✅ **Generic status** ('validated', 'validation_failed')
✅ **Safe metadata** (length, entropy - numeric values only)
✅ **Correlation IDs** (for debugging, UUID format)
✅ **Environment** ('development', 'production')
✅ **Timestamps** (for audit trail)

### Message Sanitization

All log messages pass through `_sanitize_message()` which removes:
- Quoted strings > 8 characters
- Base64 patterns (32+ alphanumeric characters)
- Long alphanumeric strings (50+ characters)
- Potential secret values in any format

---

## Usage Examples

### Successful Validation

```python
from apps.core.validation import validate_secret_key

SECRET_KEY = validate_secret_key('SECRET_KEY', env('SECRET_KEY'))
```

**Console Output:** (None - goes to log file only)

**Log File Entry:**
```
2025-10-01 10:15:23 | security.secret_validation | INFO | Secret validation passed: SECRET_KEY
Extra: {'secret_name': 'SECRET_KEY', 'secret_type': 'secret_key', 'status': 'validated',
        'length': 50, 'entropy': 4.8, 'char_types_count': 4}
```

### Failed Validation (Development)

**Console Output:**
```
🚨 CRITICAL: Secret validation failed (correlation_id: abc-123-def-456)
📋 Check logs for details: /tmp/youtility4_logs/django_dev.log
🔧 Review environment file: intelliwiz_config/envs/.env.dev.secure
📖 Documentation: docs/security/secret-validation-logging.md
```

**Log File Entry:**
```
2025-10-01 10:15:23 | security.secret_validation | ERROR | Secret validation failed: SECRET_KEY (length)
Extra: {'secret_name': 'SECRET_KEY', 'secret_type': 'secret_key', 'error_category': 'length',
        'status': 'validation_failed', 'correlation_id': 'abc-123-def-456',
        'remediation': 'Generate a new SECRET_KEY using Django utilities'}
```

### Failed Validation (Production)

**Console Output:**
```
🚨 CRITICAL: Invalid secret configuration detected
🔐 Correlation ID: abc-123-def-456
📋 Review secure logs: /var/log/youtility4/security.log
🚨 Production startup aborted for security
```

**Log File Entry:** Same as development, plus email alert sent to admins.

---

## Debugging Guide

### Using Correlation IDs

When a validation error occurs, a correlation ID is generated:

```
correlation_id: abc-123-def-456
```

**Steps to Debug:**

1. **Find the correlation ID** in console output
2. **Search log files** for that ID:
   ```bash
   # Development
   grep "abc-123-def-456" /tmp/youtility4_logs/django_dev.log

   # Production
   sudo grep "abc-123-def-456" /var/log/youtility4/security.log
   ```
3. **Review detailed error** in log file (includes error category, remediation)
4. **Fix the issue** based on log details
5. **Restart application** to retry validation

### Common Error Categories

| Category | Meaning | Action |
|----------|---------|--------|
| `missing` | Secret not found in environment | Add to `.env.*.secure` file |
| `length` | Secret too short | Generate longer secret |
| `entropy` | Secret not random enough | Use cryptographic random generator |
| `format` | Invalid format (e.g., not base64) | Regenerate with correct format |
| `diversity` | Lacks character variety | Include uppercase, lowercase, digits, symbols |

---

## Testing

### Test Suite

**Location:** `tests/security/test_secret_validation_logging.py`

**Coverage:**
- ✅ No print() statements used for secrets
- ✅ All logging uses structured logger
- ✅ No secret values in log output
- ✅ Remediation details sanitized
- ✅ Correlation IDs tracked properly
- ✅ Environment-specific behavior

### Running Tests

```bash
# Run all secret validation logging tests
python -m pytest tests/security/test_secret_validation_logging.py -v

# Run security-marked tests only
python -m pytest -m security tests/security/test_secret_validation_logging.py -v

# Run critical security tests
python -m pytest -m critical tests/security/test_secret_validation_logging.py -v
```

### Expected Output

```
tests/security/test_secret_validation_logging.py::TestSecretValidationLogger::test_log_validation_success_no_secret_values PASSED
tests/security/test_secret_validation_logging.py::TestSecretValidationLogger::test_log_validation_error_sanitized PASSED
tests/security/test_secret_validation_logging.py::TestSecretValidationLogger::test_sanitize_message_removes_secrets PASSED
tests/security/test_secret_validation_logging.py::TestSecretLeakagePrevention::test_no_print_statements_with_secrets PASSED
...
======================== 20 passed in 2.5s ========================
```

---

## Compliance

### Rule 15: Logging Data Sanitization

✅ **COMPLIANT** - Implementation follows all requirements:

- ✅ Uses structured logging with `logging.getLogger()`
- ✅ Correlation IDs for debugging (not secret values)
- ✅ All messages sanitized before output
- ✅ Logs to files only (not console) in production
- ❌ No `print()` statements for secret validation
- ❌ No actual secret values logged
- ❌ No detailed remediation exposing validation logic
- 📁 Dedicated logger with sanitization filters

### Security Audit Trail

| Date | Change | Reviewer |
|------|--------|----------|
| 2025-10-01 | Initial implementation | Security Team |
| 2025-10-01 | Comprehensive test suite | QA Team |
| 2025-10-01 | Documentation complete | Tech Writer |

---

## Migration Guide

### For Existing Code

**Pattern to Update:**

```python
# OLD (INSECURE)
print(f"✅ Secret validated: {secret_name}")
print(f"🔧 REMEDIATION: {error.remediation}")

# NEW (SECURE)
from apps.core.validation import SecretValidationLogger

SecretValidationLogger.log_validation_success(
    secret_name, secret_type, {'length': len(value), 'entropy': entropy}
)

# On error
SecretValidationLogger.log_validation_error(
    secret_name, secret_type, error_category, correlation_id
)
```

### For New Code

Always use `SecretValidationLogger` for any secret-related logging:

```python
from apps.core.validation import (
    validate_secret_key,
    SecretValidationLogger
)

# Validation functions handle logging automatically
SECRET_KEY = validate_secret_key('SECRET_KEY', env('SECRET_KEY'))

# Manual logging if needed
SecretValidationLogger.log_validation_success(
    'CUSTOM_SECRET', 'secret_key', {'length': 64}
)
```

---

## Best Practices

### DO ✅

- Use `SecretValidationLogger` for all secret-related logging
- Generate correlation IDs for error tracking
- Log to files only (not console) in production
- Use generic error messages in console output
- Provide correlation IDs to users for support
- Log safe metadata (length, entropy - numeric values)

### DON'T ❌

- Use `print()` for secret validation results
- Log actual secret values (even partially)
- Expose specific validation requirements
- Include detailed remediation in console output
- Log secret patterns or formats
- Bypass the sanitization filter

---

## Troubleshooting

### Issue: No log output

**Check:**
1. Logging configuration loaded: `python manage.py check`
2. Log directory exists and is writable
3. Logger level is INFO or lower

**Solution:**
```bash
# Ensure log directory exists
mkdir -p /tmp/youtility4_logs

# Check permissions
ls -la /tmp/youtility4_logs

# Verify logging config
python manage.py shell
>>> import logging
>>> logger = logging.getLogger('security.secret_validation')
>>> logger.info('test')
```

### Issue: Secrets appearing in logs

**This is a CRITICAL security issue!**

**Steps:**
1. Immediately stop application
2. Rotate affected log files
3. Investigate why sanitization failed
4. Run security test suite
5. Fix sanitization logic
6. Re-deploy with fix

---

## References

- **Rule 15:** `.claude/rules.md` - Logging Data Sanitization
- **Validation Module:** `apps/core/validation.py` - SecretValidator, SecretValidationLogger
- **Settings:** `intelliwiz_config/settings/development.py`, `production.py`
- **Logging Config:** `intelliwiz_config/settings/logging.py`
- **Tests:** `tests/security/test_secret_validation_logging.py`

---

## Support

For questions or issues:
- **Security Issues:** Contact security team immediately
- **Documentation:** This guide + inline code comments
- **Testing:** Run test suite to verify behavior
- **Debugging:** Use correlation IDs to trace errors

**Last Review:** 2025-10-01
**Next Review:** 2025-11-01 (or when secrets are rotated)
