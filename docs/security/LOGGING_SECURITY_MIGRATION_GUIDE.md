# Logging Security Migration Guide

## Overview

This guide provides step-by-step instructions for migrating existing code to use secure, sanitized logging that complies with **Rule #15: Logging Data Sanitization**.

**Why This Matters:**
- **Security:** Prevents password, token, and API key exposure in logs
- **Privacy:** Protects PII (emails, phones, SSNs) from log files
- **Compliance:** Meets GDPR, HIPAA, PCI-DSS requirements
- **Liability:** Reduces risk of data breach and regulatory fines

## Quick Start

### 1. Use Sanitized Logger (Recommended)

**❌ BEFORE (Insecure):**
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"User login: {user.email} with IP {ip_address}")
logger.error(f"Auth failed for {username} with password {password}")
```

**✅ AFTER (Secure):**
```python
from apps.core.middleware import get_sanitized_logger

logger = get_sanitized_logger(__name__)

logger.info(
    "User login attempt",
    extra={
        'user_id': user.id,
        'ip_address': ip_address,
        'correlation_id': request.correlation_id
    }
)
logger.error(
    "Authentication failed",
    extra={
        'username': username,
        'correlation_id': request.correlation_id
    }
)
```

### 2. Use Structured Logging with Extra Fields

**❌ BEFORE:**
```python
logger.info(f"Processing payment for {user.email}, card: {card_number}")
```

**✅ AFTER:**
```python
logger.info(
    "Processing payment",
    extra={
        'user_id': user.id,
        'correlation_id': request.correlation_id,
        'payment_method': 'credit_card'
    }
)
```

### 3. Log User References Safely

**❌ BEFORE:**
```python
logger.info(f"User: {user.email}, Mobile: {user.mobno}")
```

**✅ AFTER:**
```python
logger.info(
    "User action",
    extra={
        'user_ref': request.safe_user_ref,
        'user_id': user.id,
        'correlation_id': request.correlation_id
    }
)
```

## Common Patterns

### Pattern 1: Authentication Logging

**❌ INSECURE:**
```python
logger.info(f"Login failed for {loginid} with password {password}")
```

**✅ SECURE:**
```python
logger.warning(
    "Login attempt failed",
    extra={
        'username': loginid[:3] + '***',
        'ip_address': get_client_ip(request),
        'correlation_id': request.correlation_id
    }
)
```

### Pattern 2: Email Notifications

**❌ INSECURE:**
```python
logger.info(f"Sending email to {user.email}")
```

**✅ SECURE:**
```python
logger.info(
    "Email notification sent",
    extra={
        'user_id': user.id,
        'notification_type': 'password_reset',
        'correlation_id': request.correlation_id
    }
)
```

### Pattern 3: Form Data Logging

**❌ INSECURE:**
```python
logger.debug(f"POST data: {dict(request.POST)}")
logger.debug(f"Form data: {form.cleaned_data}")
```

**✅ SECURE:**
```python
from apps.core.services.pii_detection_service import PIIDetectionService

pii_service = PIIDetectionService()
safe_data = pii_service.analyze_content_for_logging(form.cleaned_data)

logger.debug(
    "Form submitted",
    extra={
        'form_class': form.__class__.__name__,
        'field_count': len(form.cleaned_data),
        'correlation_id': request.correlation_id
    }
)
```

### Pattern 4: Exception Logging

**❌ INSECURE:**
```python
except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
```

**✅ SECURE:**
```python
except (ValueError, TypeError) as e:
    logger.error(
        f"{type(e).__name__} in operation",
        extra={
            'operation': 'user_registration',
            'error_type': type(e).__name__,
            'correlation_id': request.correlation_id
        }
    )
```

### Pattern 5: API Request Logging

**❌ INSECURE:**
```python
logger.info(f"API request: {request.GET}, Headers: {request.META}")
```

**✅ SECURE:**
```python
logger.info(
    "API request received",
    extra={
        'path': request.path,
        'method': request.method,
        'user_id': request.user.id if request.user.is_authenticated else None,
        'correlation_id': request.correlation_id
    }
)
```

## Automatic Sanitization

**Good News:** Even if you forget to use sanitized logging, the system now has multiple layers of protection:

1. **LogSanitizationMiddleware** - Request-level sanitization
2. **SanitizingFilter** - Django logging framework integration
3. **Real-time Scanner** - Detects violations and alerts

However, **you should still use best practices** to avoid logging sensitive data in the first place.

## Migration Checklist

### Step 1: Update Imports
```python
from apps.core.middleware import get_sanitized_logger, sanitized_info, sanitized_error
from apps.core.services.pii_detection_service import PIIDetectionService
```

### Step 2: Replace Logger Initialization
```python
logger = get_sanitized_logger(__name__)
```

### Step 3: Update Logging Statements
- Use structured logging with `extra={}` parameter
- Log user_id instead of email/phone
- Use correlation_id for request tracking
- Use safe_user_ref from request

### Step 4: Test Your Changes
```python
python -m pytest apps/core/tests/test_logging_sanitization_middleware.py -v
```

### Step 5: Run Security Audit
```bash
python manage.py audit_logging_security --path apps/your_app/
```

## Prohibited Patterns

### NEVER Log These Fields:
- ❌ `password`, `passwd`, `pwd`
- ❌ `token`, `access_token`, `api_key`
- ❌ `secret`, `secret_key`
- ❌ `credit_card`, `cc_number`, `cvv`
- ❌ `ssn`, `social_security_number`
- ❌ Full `email` addresses
- ❌ `mobno`, `phone_number` (unless sanitized)

### ALWAYS Use These Instead:
- ✅ `user_id` (numeric ID)
- ✅ `correlation_id` (from request)
- ✅ `safe_user_ref` (from request)
- ✅ `ip_address` (without reverse lookup)
- ✅ `operation_type` (descriptive string)

## Tools and Commands

### Audit Existing Logging
```bash
python manage.py audit_logging_security
python manage.py audit_logging_security --path apps/peoples/
python manage.py audit_logging_security --fix
```

### Check Compliance
```bash
curl http://localhost:8000/security/logging/compliance/gdpr/
curl http://localhost:8000/security/logging/compliance/hipaa/
```

### Monitor Real-time Violations
Access the compliance dashboard at `/security/logging/compliance/dashboard/`

## FAQ

**Q: Will this slow down my application?**
A: The sanitization filter adds < 5ms overhead. Performance impact is negligible.

**Q: What if I need to log debugging information?**
A: Use structured logging with `extra={}` and limit what you log. Use correlation IDs to trace requests.

**Q: Can I temporarily disable sanitization for debugging?**
A: **NO**. Sanitization should NEVER be disabled. Use correlation IDs and grep logs instead.

**Q: What about third-party library logs?**
A: The SanitizingFilter applies to ALL loggers, including third-party libraries.

## Examples from This Codebase

### Example 1: Authentication Service (Fixed)
**apps/peoples/services/authentication_service.py:90**

BEFORE:
```python
"auth-error": "Authentication failed for user %s with password %s"
```

AFTER:
```python
"auth-error": "Authentication failed"
```

### Example 2: Background Tasks (Fixed)
**background_tasks/tasks.py:928**

BEFORE:
```python
logger.info(f"Sending Email to {p['email'] = }")
```

AFTER:
```python
logger.info("Sending email to user", extra={'user_id': p['id']})
```

### Example 3: Form Debugging (Fixed)
**apps/schedhuler/views_legacy.py:2236**

BEFORE:
```python
logger.info(f"Raw request.POST keys: {list(request.POST.keys())}")
```

AFTER:
```python
logger.info(
    "Form data received",
    extra={
        'correlation_id': request.correlation_id,
        'post_keys_count': len(list(request.POST.keys()))
    }
)
```

## Pre-commit Hook

A pre-commit hook has been added to prevent insecure logging patterns from being committed:

```bash
scripts/setup-git-hooks.sh
```

This hook will reject commits that contain:
- Password logging patterns
- Email in log strings
- request.POST/GET dictionary logging
- Token/secret logging

## Support

For questions or issues:
1. Review `.claude/rules.md` Rule #15
2. Check compliance dashboard: `/security/logging/compliance/dashboard/`
3. Run audit: `python manage.py audit_logging_security`
4. Contact security team: security@youtility.in

---

**Remember:** When in doubt, use `get_sanitized_logger()` and structured logging with `extra={}`. Never log raw user input, form data, or sensitive fields.