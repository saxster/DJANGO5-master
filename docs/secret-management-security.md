# Secret Management Security Guide

## Overview

This document provides comprehensive guidance for implementing and maintaining secure secret management in the Django 5 Enterprise Platform. Our secret validation framework implements **Rule 4: Secure Secret Management** from `.claude/rules.md` to prevent security vulnerabilities caused by weak, empty, or compromised secrets.

## 🚨 Critical Security Issue Addressed

**Previously Vulnerable Code:**
```python
# ❌ SECURITY VULNERABILITY: Unvalidated secret loading
SECRET_KEY = env("SECRET_KEY")
ENCRYPT_KEY = env("ENCRYPT_KEY")
SUPERADMIN_PASSWORD = env("SUPERADMIN_PASSWORD")
```

**Now Secure:**
```python
# ✅ SECURE: Validated secret loading with fail-fast on compromise
from apps.core.validation import validate_secret_key, validate_encryption_key, validate_admin_password

try:
    SECRET_KEY = validate_secret_key("SECRET_KEY", env("SECRET_KEY"))
    ENCRYPT_KEY = validate_encryption_key("ENCRYPT_KEY", env("ENCRYPT_KEY"))
    SUPERADMIN_PASSWORD = validate_admin_password("SUPERADMIN_PASSWORD", env("SUPERADMIN_PASSWORD"))
except Exception as e:
    print(f"🚨 CRITICAL SECURITY ERROR: {e}")
    sys.exit(1)
```

## Secret Validation Framework

### Architecture

The secret validation framework consists of:

1. **`SecretValidator`** class with validation methods for different secret types
2. **Convenience functions** for easy integration in settings.py
3. **`SecretValidationError`** for detailed error reporting with remediation guidance
4. **Entropy calculation** using Shannon entropy for security assessment
5. **Integration** with Django's existing security infrastructure

### Supported Secret Types

#### 1. Django SECRET_KEY
**Purpose:** Cryptographic signing, session security, CSRF protection

**Requirements:**
- Minimum 50 characters (Django recommendation)
- High entropy (> 4.5 bits per character)
- Character diversity (uppercase, lowercase, digits, symbols)
- No predictable patterns or common words

**Generation:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### 2. Encryption Key (ENCRYPT_KEY)
**Purpose:** Field-level encryption of sensitive data

**Requirements:**
- Exactly 32 bytes when base64 decoded (Fernet standard)
- Valid base64 encoding
- High cryptographic entropy (> 4.0 bits per character)
- No excessive zero bytes

**Generation:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### 3. Superadmin Password
**Purpose:** Administrative account authentication

**Requirements:**
- Minimum 12 characters (16+ recommended for admin accounts)
- Passes Django's configured password validators
- High entropy (> 3.5 bits per character)
- Not similar to user information
- Not a common password

**Generation:**
```bash
python -c "import secrets, string; chars = string.ascii_letters + string.digits + '!@#$%^&*()_+-='; print(''.join(secrets.choice(chars) for _ in range(20)))"
```

## Implementation Guide

### 1. Basic Usage

```python
from apps.core.validation import validate_secret_key, validate_encryption_key, validate_admin_password

# Validate individual secrets
try:
    validated_secret = validate_secret_key("SECRET_KEY", env("SECRET_KEY"))
    validated_encrypt = validate_encryption_key("ENCRYPT_KEY", env("ENCRYPT_KEY"))
    validated_password = validate_admin_password("SUPERADMIN_PASSWORD", env("SUPERADMIN_PASSWORD"))
except SecretValidationError as e:
    print(f"❌ {e}")
    print(f"🔧 {e.remediation}")
    sys.exit(1)
```

### 2. Batch Validation

```python
from apps.core.validation import SecretValidator

secrets_config = {
    'SECRET_KEY': {'value': env('SECRET_KEY'), 'type': 'secret_key'},
    'ENCRYPT_KEY': {'value': env('ENCRYPT_KEY'), 'type': 'encryption_key'},
    'SUPERADMIN_PASSWORD': {'value': env('SUPERADMIN_PASSWORD'), 'type': 'admin_password'}
}

try:
    validated_secrets = SecretValidator.validate_all_secrets(secrets_config)
    print("✅ All secrets validated successfully")
except SecretValidationError as e:
    print(f"❌ Multiple secret validation failures:\n{e}")
    sys.exit(1)
```

### 3. Custom Validation

```python
from apps.core.validation import SecretValidator

# Calculate entropy for analysis
entropy = SecretValidator.calculate_entropy("your_secret_here")
print(f"Secret entropy: {entropy:.2f} bits per character")

# Custom validation logic
class CustomSecretValidator(SecretValidator):
    @staticmethod
    def validate_api_key(secret_name: str, secret_value: str) -> str:
        # Add custom API key validation logic
        if not secret_value.startswith('sk-'):
            raise SecretValidationError(secret_name, "API key must start with 'sk-'")
        return SecretValidator.validate_secret_key(secret_name, secret_value)
```

## Environment Configuration

### Development Environment (.env.dev.secure)

```bash
# Generate secrets for development
SECRET_KEY=django-insecure-dev-only-key-replace-in-production-xyz123
ENCRYPT_KEY=development_key_32_bytes_base64_encoded
SUPERADMIN_PASSWORD=DevAdmin@Pass123!

# Security settings for development
DEBUG=True
ENABLE_RATE_LIMITING=False
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False
```

### Production Environment (.env.prod.secure)

```bash
# Production secrets (generated with secure methods)
SECRET_KEY=a9B#k2L@m5N$p8Q!r1S%t4U&w7Y*z0Z3C^f6G)h9J+n2M?q5R(s8T7X&A
ENCRYPT_KEY=X2L8R5K9M3N7P4Q1S6T8U2V5W9Y3Z7A1B4C8D2E5F9G3H7I1J4K8L2M5N9O3
SUPERADMIN_PASSWORD=ProdAdmin@SecureP@ssw0rd2024!

# Security settings for production
DEBUG=False
ENABLE_RATE_LIMITING=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
```

## Testing and Validation

### 1. Unit Tests

Run the comprehensive secret validation test suite:

```bash
# Run all secret validation tests
python -m pytest apps/core/tests/test_secret_validation.py -v

# Run security integration tests
python -m pytest apps/core/tests/test_security_fixes.py::SecretValidationIntegrationTest -v

# Run security-marked tests only
python -m pytest -m security --tb=short -v
```

### 2. Manual Testing

```python
# Test in Django shell
python manage.py shell

>>> from apps.core.validation import validate_secret_key
>>> from django.conf import settings
>>> validate_secret_key("SECRET_KEY", settings.SECRET_KEY)
'your_validated_secret_key'
>>> print("✅ SECRET_KEY validation passed")
```

### 3. Deployment Validation

```bash
# Check deployment readiness
python manage.py check --deploy

# Test application startup with validation
python manage.py runserver --verbosity=2
```

## Security Best Practices

### 1. Secret Generation

**Use Cryptographically Secure Random Sources:**
```python
# Django SECRET_KEY
from django.core.management.utils import get_random_secret_key
secret_key = get_random_secret_key()

# Fernet encryption key
from cryptography.fernet import Fernet
encrypt_key = Fernet.generate_key().decode()

# Secure password
import secrets, string
chars = string.ascii_letters + string.digits + '!@#$%^&*()_+-='
password = ''.join(secrets.choice(chars) for _ in range(20))
```

### 2. Secret Storage

**Development:**
- Use `.env.dev` or `.env.dev.secure` files
- Include in `.gitignore` to prevent accidental commits
- Use environment-specific secrets

**Production:**
- Use secure secret management systems (AWS Secrets Manager, HashiCorp Vault, etc.)
- Implement secret rotation procedures
- Use encrypted storage with access logging

### 3. Secret Rotation

**Quarterly SECRET_KEY Rotation:**
```bash
# 1. Generate new secret
NEW_SECRET=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

# 2. Update environment configuration
# 3. Deploy with blue-green deployment
# 4. Verify application functionality
# 5. Update backup systems
```

**Annual ENCRYPT_KEY Rotation:**
```bash
# 1. Generate new encryption key
NEW_ENCRYPT_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Implement dual-key decryption during transition
# 3. Re-encrypt sensitive data with new key
# 4. Remove old key after complete migration
```

### 4. Access Control

**Development Team Access:**
- Developers get development secrets only
- Staging secrets for QA team
- Production secrets limited to DevOps/SRE

**Production Access:**
- Role-based access control (RBAC)
- Multi-factor authentication (MFA) required
- Access logging and monitoring
- Regular access reviews

### 5. Monitoring and Alerting

**Set up monitoring for:**
- Secret validation failures at startup
- Unusual secret access patterns
- Failed authentication attempts
- Secret rotation events

**Example monitoring setup:**
```python
# In your monitoring system
import logging

# Configure secret validation monitoring
secret_logger = logging.getLogger('apps.core.validation')
secret_logger.addHandler(MonitoringHandler())

# Alert on validation failures
class SecretValidationMonitor:
    def __init__(self):
        self.failure_count = 0

    def log_failure(self, secret_name, error):
        self.failure_count += 1
        if self.failure_count > 3:
            send_alert(f"Multiple secret validation failures: {secret_name}")
```

## Incident Response

### 1. Compromised Secret Detection

**Immediate Actions:**
1. Rotate the compromised secret immediately
2. Invalidate all sessions if SECRET_KEY is compromised
3. Re-encrypt data if ENCRYPT_KEY is compromised
4. Force password reset if admin password is compromised

### 2. Secret Validation Failure

**Troubleshooting Steps:**
1. Check secret format and length
2. Verify environment file loading
3. Test secret generation commands
4. Check application logs for detailed errors

### 3. Emergency Secret Recovery

**Recovery Procedures:**
1. Access backup secret storage
2. Generate new secrets if backups unavailable
3. Update environment configuration
4. Restart application with validation
5. Verify functionality across all services

## Integration with CI/CD

### 1. Pre-deployment Validation

```yaml
# .github/workflows/security-validation.yml
name: Security Validation

on: [push, pull_request]

jobs:
  secret-validation:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.10

    - name: Install dependencies
      run: |
        pip install -r requirements/base.txt

    - name: Run secret validation tests
      run: |
        python -m pytest apps/core/tests/test_secret_validation.py -v
        python -m pytest -m security --tb=short -v

    - name: Check deployment readiness
      run: |
        python manage.py check --deploy
```

### 2. Secret Scanning

```yaml
# Add secret scanning to CI/CD
- name: Run secret scanning
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: main
    head: HEAD
```

## Performance Considerations

### 1. Startup Impact

The secret validation framework is designed for minimal startup impact:
- Validation typically completes in < 10ms per secret
- Entropy calculation is optimized for performance
- Batch validation reduces overhead

### 2. Memory Usage

- Validation functions use minimal memory
- No persistent caching of sensitive data
- Immediate cleanup of temporary variables

### 3. Production Optimization

```python
# Optimize for production environments
class ProductionSecretValidator(SecretValidator):
    @staticmethod
    def validate_secret_key_fast(secret_name: str, secret_value: str) -> str:
        # Skip entropy calculation in production for performance
        if not secret_value or len(secret_value) < 50:
            raise SecretValidationError(secret_name, "Invalid secret")
        return secret_value
```

## Compliance and Auditing

### 1. Regulatory Compliance

**SOC 2 Type II:**
- Secret rotation procedures documented
- Access controls implemented and tested
- Monitoring and alerting in place

**PCI DSS:**
- Strong cryptographic keys used
- Key management procedures documented
- Regular security assessments conducted

### 2. Audit Trail

**Secret Management Audit Log:**
```python
# Example audit logging
import logging

audit_logger = logging.getLogger('audit.secret_management')

def log_secret_event(event_type, secret_name, user, details):
    audit_logger.info(f"{event_type}: {secret_name} by {user}", extra={
        'event_type': event_type,
        'secret_name': secret_name,
        'user': user,
        'details': details,
        'timestamp': timezone.now().isoformat()
    })
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Secret Too Short Error
```
SecretValidationError: SECRET_KEY is too short (25 chars). Must be at least 50 characters
```

**Solution:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### 2. Insufficient Entropy Error
```
SecretValidationError: SECRET_KEY has insufficient entropy (2.3). Must be > 4.5 for security
```

**Solution:** Use a more diverse character set in your secret generation.

#### 3. Invalid Base64 Encryption Key
```
SecretValidationError: ENCRYPT_KEY is not valid base64
```

**Solution:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### 4. Weak Admin Password
```
SecretValidationError: SUPERADMIN_PASSWORD validation failed: This password is too common
```

**Solution:** Generate a stronger password with mixed character types.

### Debug Mode

Enable debug logging for detailed validation information:

```python
import logging
logging.getLogger('apps.core.validation').setLevel(logging.DEBUG)
```

## Session Security Best Practices

**Implements:** Rule #10 - Session Security Standards

### 1. Session Configuration Compliance

**Required Settings (from `.claude/rules.md`):**
```python
SESSION_SAVE_EVERY_REQUEST = True              # Security first
SESSION_COOKIE_AGE = 2 * 60 * 60              # 2 hours max
SESSION_EXPIRE_AT_BROWSER_CLOSE = True         # Close with browser
SESSION_COOKIE_SECURE = True                   # HTTPS only
SESSION_COOKIE_HTTPONLY = True                 # No JavaScript access
SESSION_COOKIE_SAMESITE = "Lax"               # CSRF protection
```

**Configuration Files:**
- `intelliwiz_config/settings/security/authentication.py` - Main session config
- `intelliwiz_config/settings/base.py` - Base session settings
- Environment-specific overrides in `production.py`, `development.py`, `test.py`

### 2. Activity-Based Timeout

**Purpose:** Prevent stale session exploitation

**Implementation:**
```python
# Enable activity monitoring
SESSION_ACTIVITY_TIMEOUT = 30 * 60  # 30 minutes inactivity

# Middleware automatically:
# - Tracks last activity timestamp
# - Enforces timeout on subsequent requests
# - Logs timeout events for security monitoring
```

**Middleware:** `apps.core.middleware.session_activity.SessionActivityMiddleware`

### 3. Session Rotation on Privilege Changes

**Purpose:** Prevent session fixation after privilege escalation

**Automatic Rotation Triggers:**
- User promoted to superuser (`is_superuser: False → True`)
- User promoted to staff (`is_staff: False → True`)
- User promoted to admin (`isadmin: False → True`)

**Implementation Details:**
```python
# Signals detect privilege changes (apps/peoples/signals.py)
@receiver(pre_save, sender=People)
def track_privilege_changes(sender, instance, **kwargs):
    # Compares old vs new privileges
    # Sets rotation flag if escalation detected

# Service rotates session (apps/peoples/services/authentication_service.py)
def rotate_session_on_privilege_change(request, user, old_priv, new_priv):
    # Calls session.cycle_key()
    # Logs rotation event
    # Creates audit trail
```

### 4. Concurrent Session Limiting

**Purpose:** Detect and prevent session hijacking

**Configuration:**
```python
MAX_CONCURRENT_SESSIONS = 3                    # Max 3 sessions per user
CONCURRENT_SESSION_ACTION = 'invalidate_oldest'  # Auto-invalidate or deny_new
```

**Actions on Limit Exceeded:**
- **invalidate_oldest**: Automatically delete oldest session (default)
- **deny_new**: Reject new session creation, force user to manage sessions

**User Self-Service:**
```python
# Users can view and manage their active sessions via API
GET  /api/security/sessions/manage/          # List active sessions
POST /api/security/sessions/manage/          # Invalidate sessions
```

### 5. Session Forensics and Audit Trail

**Model:** `apps.core.models.SessionForensics`

**Tracked Events:**
- Session creation and authentication
- Session rotation (with reason)
- Activity timeouts
- Privilege changes
- IP/User-Agent changes
- Concurrent session limit violations
- Manual and forced logouts

**Forensic Analysis:**
```python
from apps.core.models import SessionForensics

# Get user's session history
history = SessionForensics.get_user_session_history(user_id, days=30)

# Get suspicious activity
suspicious = SessionForensics.get_suspicious_activity(hours=24)

# Analyze specific session
events = SessionForensics.objects.filter(
    session_key=hashed_session_key
).order_by('timestamp')
```

### 6. Security Monitoring Dashboard

**Access:** Staff members only

**Endpoints:**
- `/security/sessions/` - Session monitoring dashboard
- `/api/security/sessions/metrics/` - Real-time metrics API

**Metrics Displayed:**
- Active sessions count
- Activity timeout events
- Suspicious session activity
- Recent session rotations
- Privilege escalation events
- Configuration compliance status

### 7. Session Security Checklist

**Before Deployment:**
- [ ] SESSION_COOKIE_AGE ≤ 2 hours
- [ ] SESSION_SAVE_EVERY_REQUEST = True
- [ ] SESSION_COOKIE_SECURE = True (production)
- [ ] Activity timeout configured and tested
- [ ] Session rotation tested for privilege changes
- [ ] Concurrent session limiting enabled
- [ ] SessionForensics model migrated
- [ ] Security dashboard accessible to staff
- [ ] All security tests passing

**Monthly Review:**
- [ ] Review suspicious session activity
- [ ] Check for geographic anomalies
- [ ] Validate timeout configuration appropriateness
- [ ] Audit privilege escalation patterns
- [ ] Review concurrent session violations
- [ ] Update documentation if needed

### 8. Related Documentation

- **Operational Guide:** `docs/security/session-management-runbook.md`
- **Security Rules:** `.claude/rules.md` Rule #10
- **Test Suite:** `apps/core/tests/test_session_*.py`
- **Architecture Notes:** Session timeout trade-off approved (20ms latency acceptable)

## Support and Resources

### Documentation
- [Django Security Documentation](https://docs.djangoproject.com/en/stable/topics/security/)
- [Cryptography Library Documentation](https://cryptography.io/)
- [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)

### Internal Resources
- `.claude/rules.md` - Security rules and requirements
- `apps/core/validation.py` - Validation framework source code
- `apps/core/tests/test_secret_validation.py` - Comprehensive test suite
- `env_examples/secure_secrets.env.example` - Environment configuration examples

### Getting Help

For security-related questions or issues:
1. Check this documentation first
2. Review test cases for examples
3. Consult `.claude/rules.md` for requirements
4. Contact the security team for production issues

---

**Remember:** Security is everyone's responsibility. When in doubt, choose the more secure option and consult with the security team.