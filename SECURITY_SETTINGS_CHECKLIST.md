# 🔒 Security Settings Deployment Checklist

**Purpose:** Ensure all security-critical settings are properly configured before production deployment
**Last Updated:** 2025-01-30
**Version:** 1.0

---

## 📋 Pre-Deployment Validation

### Automated Checks ✅

The application now includes **automatic startup validation** via `apps/core/startup_checks.py`.
These checks will **block production startup** if critical security settings are misconfigured.

**To manually run validation:**
```bash
python manage.py shell
>>> from apps.core.startup_checks import SecurityStartupValidator
>>> validator = SecurityStartupValidator(environment='production')
>>> passed, results = validator.validate_all(fail_fast=False)
>>> for r in results:
...     print(f"{r.check_name}: {'✅' if r.passed else '❌'} {r.message}")
```

---

## 🚨 CRITICAL Security Settings (Must Be Correct)

### 1. Jinja2 Autoescape Protection

**Setting:** `TEMPLATES` configuration in `base.py`
**Required Value:** `"autoescape": True`
**Risk if Wrong:** 🔴 **CRITICAL** - XSS vulnerabilities across all templates

**Validation:**
```python
# In Django shell:
from django.conf import settings
jinja_config = [t for t in settings.TEMPLATES if 'jinja2' in t['BACKEND'].lower()][0]
assert jinja_config['OPTIONS']['autoescape'] == True, "Autoescape must be enabled!"
```

**Deployment Check:**
- [ ] `intelliwiz_config/settings/base.py:77` has `"autoescape": True`
- [ ] No templates rely on disabled autoescape (use `|safe` filter if needed)
- [ ] XSS injection tests pass (see `SECURITY_FIXES_CRITICAL.md`)

---

### 2. JWT Token Expiration

**Setting:** `GRAPHQL_JWT` configuration
**Required Values:**
- Base (dev): `JWT_EXPIRATION_DELTA: timedelta(hours=8)`
- Production: `JWT_EXPIRATION_DELTA: timedelta(hours=2)` ← **Stricter**
**Risk if Wrong:** 🔴 **CRITICAL** - Permanent access tokens

**Validation:**
```python
from django.conf import settings
jwt_config = settings.GRAPHQL_JWT
assert jwt_config['JWT_VERIFY_EXPIRATION'] == True, "JWT expiration must be verified!"
assert jwt_config['JWT_EXPIRATION_DELTA'].total_seconds() <= 7200, "Production tokens must expire in ≤2 hours!"
```

**Deployment Check:**
- [ ] `intelliwiz_config/settings/base.py:165` has `JWT_VERIFY_EXPIRATION: True`
- [ ] `intelliwiz_config/settings/production.py:117` overrides with 2-hour expiry
- [ ] Frontend handles 401 errors and redirects to login
- [ ] Mobile app implements token refresh logic

---

### 3. DEBUG Mode

**Setting:** `DEBUG`
**Required Value:** `False` in production
**Risk if Wrong:** 🔴 **CRITICAL** - Information disclosure, stack traces exposed

**Validation:**
```python
from django.conf import settings
assert settings.DEBUG == False, "DEBUG must be False in production!"
```

**Deployment Check:**
- [ ] `intelliwiz_config/settings/production.py:24` has `DEBUG = False`
- [ ] Production settings file includes safety check (line 27-28)
- [ ] Error templates (403, 404, 500) are production-ready

---

### 4. SECRET_KEY Strength

**Setting:** `SECRET_KEY`
**Required:**
- Length ≥ 50 characters
- Not a default value
- Stored in environment variables (never in code)

**Validation:**
```python
from django.conf import settings
assert len(settings.SECRET_KEY) >= 50, "SECRET_KEY too short!"
assert 'django-insecure' not in settings.SECRET_KEY, "Using default SECRET_KEY!"
```

**Deployment Check:**
- [ ] `.env.prod.secure` contains strong SECRET_KEY
- [ ] SECRET_KEY passes validation function in `apps/core/validation.py`
- [ ] SECRET_KEY is rotated regularly (every 90 days recommended)

---

## 🔐 HIGH Priority Security Settings

### 5. HTTPS & Cookie Security

**Settings:**
```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
LANGUAGE_COOKIE_SECURE = True  # NEW - Added in security fixes
```

**Deployment Check:**
- [ ] All four settings are `True` in `production.py`
- [ ] Production server uses valid SSL certificate
- [ ] HTTP traffic redirects to HTTPS (test: `curl -I http://domain.com`)
- [ ] Cookies have `Secure` flag (inspect in browser DevTools)

---

### 6. HSTS (HTTP Strict Transport Security)

**Settings:**
```python
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

**Deployment Check:**
- [ ] HSTS settings configured in `production.py`
- [ ] Test response headers: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- [ ] Domain submitted to [HSTS Preload List](https://hstspreload.org/) (optional but recommended)

---

### 7. ALLOWED_HOSTS

**Setting:** `ALLOWED_HOSTS`
**Required:** Specific hostnames only (NO wildcards `*`)

**Deployment Check:**
- [ ] `production.py` has specific hosts: `["django5.youtility.in", "127.0.0.1"]`
- [ ] Test invalid host: `curl -H "Host: evil.com" https://django5.youtility.in` → Should return 400

---

### 8. Database Connection Security

**Settings:**
```python
DATABASES['default']['OPTIONS']['sslmode'] = 'require'  # PostgreSQL SSL
CONN_HEALTH_CHECKS = True
```

**Deployment Check:**
- [ ] PostgreSQL connection uses SSL (`sslmode: require`)
- [ ] Database credentials stored in `.env.prod.secure` (not in code)
- [ ] Connection pooling configured (`CONN_MAX_AGE`)
- [ ] Health checks enabled

---

## 🟡 MEDIUM Priority Security Settings

### 9. CORS Configuration

**Settings:**
```python
CORS_ALLOWED_ORIGINS = ["https://django5.youtility.in"]
CORS_ALLOW_CREDENTIALS = True
```

**Deployment Check:**
- [ ] Only trusted origins listed (no wildcards)
- [ ] CORS regex patterns match expected subdomains
- [ ] Test cross-origin requests from unauthorized domain → Should be blocked

---

### 10. Content Security Policy (CSP)

**Settings:**
```python
# Via CSPNonceMiddleware in base.py:50
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
```

**Deployment Check:**
- [ ] CSP headers present in responses
- [ ] Test XSS injection → Should be blocked
- [ ] Test iframe embedding → Should be denied
- [ ] CSP violation reports logged to `CSPViolation` model

---

### 11. Rate Limiting

**Settings:**
```python
ENABLE_RATE_LIMITING = True
RATE_LIMIT_MAX_ATTEMPTS = 5  # Per 15-minute window
RATE_LIMIT_PATHS = ["/login/", "/api/", "/graphql/", ...]
```

**Deployment Check:**
- [ ] Rate limiting enabled in `production.py`
- [ ] Test: 6+ login attempts → Should return 429 Too Many Requests
- [ ] GraphQL rate limiting active (`GRAPHQL_RATE_LIMIT_MAX = 100`)

---

### 12. Email Configuration (AWS SES)

**Settings:**
```python
EMAIL_USE_TLS = True
EMAIL_HOST = "email-smtp.us-east-1.amazonaws.com"
```

**Deployment Check:**
- [ ] AWS SES credentials in `.env.prod.secure`
- [ ] Test email sending works
- [ ] FROM address verified in AWS SES
- [ ] Email token expiration configured (`EMAIL_TOKEN_LIFE = 3600`)

---

## 📊 Raw SQL Security Checklist

### 13. Raw Query Wrappers

**New Security Feature:** Tenant-aware raw query utilities

**Deployment Check:**
- [ ] `apps/core/db/raw_query_utils.py` exists and is importable
- [ ] All new raw queries use `execute_raw_query()` or `execute_read_query()`
- [ ] Legacy queries documented in `RAW_SQL_SECURITY_AUDIT_REPORT.md`
- [ ] Migration plan exists for high-priority raw queries

**Example Migration:**
```python
# OLD (direct cursor usage - NOT RECOMMENDED):
with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM people WHERE client_id = %s", [client_id])
    results = cursor.fetchall()

# NEW (secure wrapper):
from apps.core.db import execute_tenant_query
result = execute_tenant_query(
    "SELECT * FROM people WHERE client_id = %s",
    params=[client_id],
    tenant_id=tenant_id
)
```

---

## 🧪 Post-Deployment Testing

### Automated Security Tests

Run the full security test suite before deployment:

```bash
# Critical security fixes validation
python -m pytest -m security --tb=short -v

# JWT expiration tests
python -m pytest apps/core/tests/test_security_fixes.py::test_jwt_expiration -v

# XSS protection tests
python -m pytest apps/core/tests/test_security_fixes.py::test_jinja_autoescape -v

# Startup validation tests
python -m pytest apps/core/tests/test_startup_checks.py -v
```

### Manual Security Testing

After deployment to production:

1. **JWT Expiration Test:**
   ```bash
   # Get JWT token
   TOKEN=$(curl -X POST https://django5.youtility.in/graphql/ \
     -d '{"query": "mutation { tokenAuth(username:\"test\", password:\"test\") { token } }"}')

   # Wait 2+ hours (or adjust server time for testing)
   # Attempt request with expired token → Should return 401
   curl -H "Authorization: Bearer $TOKEN" https://django5.youtility.in/graphql/ \
     -d '{"query": "{ me { id } }"}'
   ```

2. **XSS Protection Test:**
   ```bash
   # Try injecting JavaScript in a form field
   # Should render as text, not execute
   Payload: <script>alert('XSS')</script>
   Expected: &lt;script&gt;alert('XSS')&lt;/script&gt;
   ```

3. **HTTPS Redirect Test:**
   ```bash
   curl -I http://django5.youtility.in
   # Should return 301/302 redirect to https://
   ```

4. **Cookie Security Test:**
   ```bash
   # Login and check cookies in browser DevTools
   # All cookies should have: Secure, HttpOnly, SameSite flags
   ```

---

## 📝 Deployment Sign-Off Template

```
DEPLOYMENT: Production Security Validation
DATE: _____________
ENVIRONMENT: Production
DEPLOYER: _____________

CRITICAL SETTINGS (All must be ✅):
[ ] Jinja2 autoescape enabled
[ ] JWT expiration enabled (2hr)
[ ] DEBUG = False
[ ] SECRET_KEY strong & rotated
[ ] HTTPS & secure cookies
[ ] HSTS configured
[ ] ALLOWED_HOSTS specific
[ ] Database SSL enabled

HIGH PRIORITY SETTINGS:
[ ] CORS properly configured
[ ] CSP headers active
[ ] Rate limiting enabled
[ ] Email configuration tested
[ ] Raw query wrappers in place

POST-DEPLOYMENT TESTS:
[ ] Automated security tests pass
[ ] Manual JWT expiration verified
[ ] XSS injection blocked
[ ] HTTPS redirect working
[ ] Cookie security verified
[ ] Startup validation passes

APPROVAL:
_______________ (DevOps Lead)
_______________ (Security Team)
_______________ (Tech Lead)

NOTES:
_____________________________________________
_____________________________________________
```

---

## 🔄 Regular Maintenance Schedule

### Weekly
- [ ] Review security logs for anomalies
- [ ] Check CSP violation reports
- [ ] Monitor rate limit breaches

### Monthly
- [ ] Review and update `ALLOWED_HOSTS` if needed
- [ ] Check for expired SSL certificates (30 days before expiry)
- [ ] Audit new raw SQL queries

### Quarterly (Every 90 Days)
- [ ] Rotate `SECRET_KEY` and `ENCRYPT_KEY`
- [ ] Review and update Django to latest security release
- [ ] Re-run full security audit (similar to this one)
- [ ] Update all Python dependencies

### Annually
- [ ] Full penetration testing
- [ ] Security policy review
- [ ] Compliance audit (if applicable)

---

## 📚 Related Documentation

- `SECURITY_FIXES_CRITICAL.md` - Details of critical security fixes
- `RAW_SQL_SECURITY_AUDIT_REPORT.md` - Raw SQL usage audit
- `apps/core/startup_checks.py` - Automatic validation implementation
- `.claude/rules.md` - Development security rules
- `CLAUDE.md` - Architecture and security strategy

---

## 🆘 Emergency Contacts

**If Security Issue Found in Production:**

1. **Immediate:** Alert on-call engineer
2. **Within 1 hour:** Notify security team
3. **Within 4 hours:** Deploy hotfix or rollback
4. **Within 24 hours:** Root cause analysis report

**Security Team Contacts:**
- Primary: [Security Lead Email]
- Secondary: [DevOps Lead Email]
- Emergency: [On-Call Phone]

---

## ✅ Checklist Version Control

| Version | Date | Changes | Approved By |
|---------|------|---------|-------------|
| 1.0 | 2025-01-30 | Initial checklist after security audit | Claude Code |
| | | | |
| | | | |

---

**NOTE:** This checklist must be completed and signed before EVERY production deployment.
Keep completed checklists for compliance and audit trail.