# Middleware Ordering Guide

**Critical**: Middleware ordering is **MANDATORY** for security and functionality.
**Version**: 2.0
**Last Updated**: 2025-10-01

---

## 🚨 Executive Summary

Django middleware executes in **strict order**. Incorrect ordering can result in:
- **Security bypasses** (e.g., authentication before rate limiting)
- **Missing data** (e.g., using correlation_id before it's set)
- **Performance issues** (e.g., cache checks after expensive operations)
- **Functional failures** (e.g., CSRF validation before session)

**DO NOT change middleware order without security team approval.**

---

## 📊 Current Middleware Stack

```python
# intelliwiz_config/settings/middleware.py
MIDDLEWARE = [
    # Layer 1: Core Security (MUST BE FIRST)
    "django.middleware.security.SecurityMiddleware",

    # Layer 2: Request Tracking and Logging
    "apps.core.error_handling.CorrelationIDMiddleware",          # Sets correlation_id
    "apps.core.middleware.logging_sanitization.LogSanitizationMiddleware",
    "apps.core.middleware.api_deprecation.APIDeprecationMiddleware",

    # Layer 3: Rate Limiting and DoS Protection
    "apps.core.middleware.path_based_rate_limiting.PathBasedRateLimitMiddleware",
    "apps.core.middleware.graphql_rate_limiting.GraphQLRateLimitingMiddleware",
    "apps.core.middleware.graphql_complexity_validation.GraphQLComplexityValidationMiddleware",
    "apps.core.middleware.path_based_rate_limiting.RateLimitMonitoringMiddleware",

    # Layer 3.5: Origin Validation (Cross-Origin Attack Prevention)
    "apps.core.middleware.graphql_origin_validation.GraphQLOriginValidationMiddleware",

    # Layer 4: Input Validation and Attack Prevention
    "apps.core.sql_security.SQLInjectionProtectionMiddleware",
    "apps.core.xss_protection.XSSProtectionMiddleware",
    "apps.core.middleware.graphql_csrf_protection.GraphQLCSRFProtectionMiddleware",
    "apps.core.middleware.graphql_csrf_protection.GraphQLSecurityHeadersMiddleware",

    # Layer 5: Session and Multi-Tenancy
    "django.contrib.sessions.middleware.SessionMiddleware",      # Creates session
    "apps.tenants.middlewares.TenantMiddleware",                 # Uses session
    "django.middleware.locale.LocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.onboarding.middlewares.TimezoneMiddleware",

    # Layer 6: Content Security and Static Files
    "apps.core.middleware.csp_nonce.CSPNonceMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # Layer 7: CSRF Protection
    "django.middleware.csrf.CsrfViewMiddleware",                 # Needs session

    # Layer 8: File Upload Security
    "apps.core.middleware.file_upload_security_middleware.FileUploadSecurityMiddleware",

    # Layer 9: Authentication and Authorization
    "django.contrib.auth.middleware.AuthenticationMiddleware",   # Needs session
    "apps.onboarding_api.middleware.OnboardingAPIMiddleware",
    "apps.onboarding_api.middleware.OnboardingAuditMiddleware",

    # Layer 10: Application Middleware
    "django.contrib.messages.middleware.MessageMiddleware",      # Needs session & auth
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'apps.core.xss_protection.CSRFHeaderMiddleware',

    # Layer 11: Error Handling (MUST BE LAST)
    "apps.core.error_handling.GlobalExceptionMiddleware",        # Catch-all
]
```

---

## 🔗 Dependency Chain

### Critical Dependencies

| Middleware | Depends On | Reason |
|------------|------------|--------|
| **LogSanitizationMiddleware** | CorrelationIDMiddleware | Uses `request.correlation_id` |
| **Rate Limiting** | CorrelationIDMiddleware | Logs violations with correlation_id |
| **Origin Validation** | Rate Limiting | After rate limit but before SQL checks |
| **SQL/XSS Protection** | Origin Validation | After origin checks, before CSRF |
| **CSRF Protection** | SessionMiddleware | Needs session for token storage |
| **TenantMiddleware** | SessionMiddleware | Loads tenant from session |
| **Authentication** | SessionMiddleware + CSRF | Needs session and CSRF validation |
| **Messages** | SessionMiddleware + Authentication | Stores messages in session |
| **GlobalException** | ALL | Catches errors from all middleware |

### Data Flow

```
Request
  ↓
1. SecurityMiddleware (sets security headers)
  ↓
2. CorrelationIDMiddleware (sets correlation_id)
  ↓
3. LogSanitizationMiddleware (uses correlation_id)
  ↓
4. Rate Limiting (uses correlation_id, logs violations)
  ↓
5. Origin Validation (checks Origin/Referer headers)
  ↓
6. SQL/XSS Protection (validates input)
  ↓
7. CSRF Protection (validates CSRF token)
  ↓
8. SessionMiddleware (creates/loads session)
  ↓
9. TenantMiddleware (loads tenant from session)
  ↓
10. Authentication (loads user from session)
  ↓
11. Application Logic (views/GraphQL)
  ↓
12. GlobalExceptionMiddleware (error handling)
  ↓
Response
```

---

## ⚠️ Critical Ordering Rules

### Rule 1: SecurityMiddleware MUST be first
**Why**: Sets security headers that protect all subsequent processing
```python
✅ CORRECT ORDER:
1. SecurityMiddleware
2. Everything else

❌ WRONG:
1. Something else
2. SecurityMiddleware  # Too late - headers already sent
```

### Rule 2: CorrelationIDMiddleware MUST be second
**Why**: All middleware needs correlation_id for tracking and logging
```python
✅ CORRECT ORDER:
1. SecurityMiddleware
2. CorrelationIDMiddleware
3. LogSanitizationMiddleware (uses correlation_id)

❌ WRONG:
1. SecurityMiddleware
2. LogSanitizationMiddleware
3. CorrelationIDMiddleware  # Too late - already used
```

### Rule 3: Rate Limiting BEFORE Origin Validation
**Why**: Block excessive requests before expensive origin checks
```python
✅ CORRECT ORDER:
1. RateLimitMiddleware (fast rejection)
2. OriginValidationMiddleware (more expensive)

❌ WRONG:
1. OriginValidationMiddleware (expensive check first)
2. RateLimitMiddleware (too late for DoS protection)
```

### Rule 4: Origin Validation BEFORE SQL/XSS Protection
**Why**: Reject foreign origins before processing their input
```python
✅ CORRECT ORDER:
1. OriginValidationMiddleware (reject untrusted origins)
2. SQLInjectionProtectionMiddleware (validate trusted input)

❌ WRONG:
1. SQLInjectionProtectionMiddleware (processes malicious input)
2. OriginValidationMiddleware (too late - already processed)
```

### Rule 5: SessionMiddleware BEFORE TenantMiddleware
**Why**: Tenant info is stored in session
```python
✅ CORRECT ORDER:
1. SessionMiddleware (creates session)
2. TenantMiddleware (reads tenant from session)

❌ WRONG:
1. TenantMiddleware (session doesn't exist yet)
2. SessionMiddleware (too late)
```

### Rule 6: CSRF BEFORE Authentication
**Why**: Validate CSRF token before loading user
```python
✅ CORRECT ORDER:
1. SessionMiddleware
2. CsrfViewMiddleware (validate token)
3. AuthenticationMiddleware (load user)

❌ WRONG:
1. SessionMiddleware
2. AuthenticationMiddleware (user loaded)
3. CsrfViewMiddleware (too late - user already trusted)
```

### Rule 7: GlobalExceptionMiddleware MUST be last
**Why**: Needs to catch exceptions from ALL other middleware
```python
✅ CORRECT ORDER:
1. All other middleware
2. GlobalExceptionMiddleware (catch-all)

❌ WRONG:
1. GlobalExceptionMiddleware
2. Other middleware (exceptions not caught)
```

---

## 🧪 Testing Middleware Ordering

### Automated Tests

```python
# apps/core/tests/test_middleware_ordering.py
def test_middleware_ordering():
    """Verify critical middleware ordering."""
    from django.conf import settings

    middleware = settings.MIDDLEWARE

    # Test: SecurityMiddleware is first
    assert middleware[0] == "django.middleware.security.SecurityMiddleware"

    # Test: CorrelationIDMiddleware is second
    assert "CorrelationIDMiddleware" in middleware[1]

    # Test: GlobalExceptionMiddleware is last
    assert "GlobalExceptionMiddleware" in middleware[-1]

    # Test: SessionMiddleware before TenantMiddleware
    session_idx = next(i for i, m in enumerate(middleware) if 'SessionMiddleware' in m)
    tenant_idx = next(i for i, m in enumerate(middleware) if 'TenantMiddleware' in m)
    assert session_idx < tenant_idx

    # Test: Rate limiting before origin validation
    rate_idx = next(i for i, m in enumerate(middleware) if 'RateLimitMiddleware' in m)
    origin_idx = next(i for i, m in enumerate(middleware) if 'OriginValidationMiddleware' in m)
    assert rate_idx < origin_idx
```

### Manual Verification

```bash
# Check middleware ordering
python manage.py shell

>>> from django.conf import settings
>>> for i, m in enumerate(settings.MIDDLEWARE):
...     print(f"{i:2d}. {m}")
```

---

## 🔍 Debugging Middleware Issues

### Issue: "correlation_id not found"

**Symptom**: Middleware tries to use `request.correlation_id` but it doesn't exist

**Cause**: CorrelationIDMiddleware not running or running too late

**Fix**: Ensure CorrelationIDMiddleware is second in the stack

### Issue: "Session not found"

**Symptom**: TenantMiddleware or AuthenticationMiddleware can't access session

**Cause**: SessionMiddleware not running or running too late

**Fix**: Ensure SessionMiddleware runs before tenant/auth middleware

### Issue: "CSRF validation failed"

**Symptom**: Valid requests fail CSRF validation

**Cause**: CsrfViewMiddleware running before SessionMiddleware

**Fix**: Move CsrfViewMiddleware after SessionMiddleware

### Issue: "Rate limit not working"

**Symptom**: Requests not being rate-limited

**Cause**: Rate limiting middleware too late in stack

**Fix**: Move rate limiting middleware early (Layer 3)

---

## 📋 Middleware Modification Checklist

Before modifying middleware order, verify:

- [ ] **Read this guide completely**
- [ ] **Understand dependencies** of the middleware you're moving
- [ ] **Check data dependencies** (what data does it need/provide?)
- [ ] **Review security implications** (does order affect security?)
- [ ] **Run all tests** (`python -m pytest`)
- [ ] **Test in staging** with realistic traffic
- [ ] **Get security team approval** (for security-related middleware)
- [ ] **Document the change** (update this guide)
- [ ] **Monitor production** after deployment

---

## 🚨 Emergency Rollback

If middleware ordering breaks production:

```bash
# 1. Identify the issue
tail -f /var/log/youtility4/django.log | grep "ERROR"

# 2. Rollback to previous middleware configuration
git checkout HEAD~1 intelliwiz_config/settings/middleware.py

# 3. Restart application
sudo systemctl restart gunicorn
sudo systemctl restart celery-workers

# 4. Verify fix
curl -I https://django5.youtility.in/health/

# 5. Monitor logs
tail -f /var/log/youtility4/django.log
```

---

## 📞 Support

- **Questions**: engineering@youtility.in
- **Security Issues**: security@youtility.in
- **Emergency**: On-call engineer (see PagerDuty)

---

## 📚 References

- Django Middleware Documentation: https://docs.djangoproject.com/en/5.0/topics/http/middleware/
- Security Best Practices: https://docs.djangoproject.com/en/5.0/topics/security/
- Middleware Implementation: `intelliwiz_config/settings/middleware.py`

---

**Document Status**: ACTIVE
**Compliance**: Required for all deployments
**Review Cycle**: Quarterly
**Next Review**: 2026-01-01
