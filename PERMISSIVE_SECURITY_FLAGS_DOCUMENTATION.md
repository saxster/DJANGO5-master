# Permissive Security Flags Requiring Production Overrides

**Purpose:** Document all security settings in `base.py` that are permissive by default and MUST be overridden in production
**Date:** 2025-01-30
**Critical Level:** 🔴 HIGH - Misconfiguration can lead to security vulnerabilities

---

## 🎯 Overview

The Django 5 project uses a **layered settings architecture**:
- `base.py` - Common settings (development-friendly defaults)
- `development.py` - Development overrides (relaxed security for local work)
- `production.py` - Production overrides (strict security enforcement)

**CRITICAL:** Several settings in `base.py` are **intentionally permissive** to support development workflows. These MUST be overridden in production to maintain security.

---

## 🚨 CRITICAL FLAGS (Must Override in Production)

### 1. Language Cookie Security

**Location:** `intelliwiz_config/settings/base.py:131`

**Base Configuration:**
```python
LANGUAGE_COOKIE_SECURE = False  # Set to True in production with HTTPS
```

**Why Permissive:** Allows language switching over HTTP during local development

**Security Risk:** 🟡 **MEDIUM**
- Language preference cookie can be intercepted over HTTP
- Potential for session fixation attacks
- OWASP: A02:2021 - Cryptographic Failures

**Production Override Required:**
```python
# intelliwiz_config/settings/production.py:115
LANGUAGE_COOKIE_SECURE = True  # ✅ ALREADY IMPLEMENTED
```

**Validation:**
```bash
# Check production setting
python manage.py shell
>>> from django.conf import settings
>>> assert settings.LANGUAGE_COOKIE_SECURE == True, "Must be True in production!"
```

**Status:** ✅ **FIXED** - Production override added in security audit (2025-01-30)

---

### 2. JWT Token Expiration

**Location:** `intelliwiz_config/settings/base.py:164-169`

**Base Configuration:**
```python
GRAPHQL_JWT = {
    "JWT_VERIFY_EXPIRATION": True,  # NOW ENABLED ✅
    "JWT_EXPIRATION_DELTA": timedelta(hours=8),  # Development: 8 hours
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=2),
    "JWT_LONG_RUNNING_REFRESH_TOKEN": True
}
```

**Why Permissive:** 8-hour tokens reduce re-authentication friction during development

**Security Risk:** 🟡 **MEDIUM**
- Longer token lifetime increases window for token theft
- If token is compromised, attacker has 8 hours of access
- OWASP: A07:2021 - Identification and Authentication Failures

**Production Override Required:**
```python
# intelliwiz_config/settings/production.py:118-123
GRAPHQL_JWT = {
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_EXPIRATION_DELTA": timedelta(hours=2),  # ✅ Stricter: 2 hours
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=2),
    "JWT_LONG_RUNNING_REFRESH_TOKEN": True
}
```

**Best Practice:** Production tokens should expire every 1-2 hours maximum

**Status:** ✅ **FIXED** - Production override added with 2-hour expiration

---

### 3. Auto-Reload Templates

**Location:** `intelliwiz_config/settings/base.py:77`

**Base Configuration:**
```python
"OPTIONS": {
    "extensions": ["jinja2.ext.loopcontrols"],
    "autoescape": True,
    "auto_reload": True,  # ← Should be False in production
    "undefined": "jinja2.StrictUndefined",
}
```

**Why Permissive:** Auto-reloading templates speeds up development (no server restart needed)

**Security Risk:** 🟢 **LOW** (Performance Impact)
- No direct security vulnerability
- Performance overhead: template file system checks on every request
- Can expose template paths in error messages

**Production Override Recommended:**
```python
# intelliwiz_config/settings/production.py (ADD THIS)
TEMPLATES = [
    # Django templates (unchanged)
    settings.TEMPLATES[0],
    # Jinja2 with auto_reload disabled
    {
        **settings.TEMPLATES[1],
        'OPTIONS': {
            **settings.TEMPLATES[1]['OPTIONS'],
            'auto_reload': False,  # Disable in production
        }
    }
]
```

**Status:** ⚠️ **NEEDS IMPLEMENTATION** - Add to production.py

---

### 4. Session Expiration Time

**Location:** `intelliwiz_config/settings/base.py:207-208`

**Base Configuration:**
```python
SESSION_COOKIE_AGE = 2 * 60 * 60  # 2 hours
SESSION_SAVE_EVERY_REQUEST = True  # Security first (Rule #10)
```

**Why This Setting:** Based on enterprise security requirements

**Security Consideration:** 🟢 **ACCEPTABLE**
- 2 hours is already strict for enterprise applications
- SESSION_SAVE_EVERY_REQUEST ensures sliding window (session extends on activity)
- Complies with Rule #10 (Session Security Standards)

**Production Override:** ⚠️ **CONSIDER**
For high-security applications, consider shortening:
```python
# intelliwiz_config/settings/production.py (OPTIONAL)
SESSION_COOKIE_AGE = 1 * 60 * 60  # 1 hour for highly sensitive applications
```

**Status:** ✅ **ACCEPTABLE** - Current 2-hour setting is reasonable

---

### 5. CORS Allowed Origins

**Location:** `intelliwiz_config/settings/base.py` (not explicitly set)

**Inherited From:** Django defaults (no CORS in base.py)

**Production Configuration:**
```python
# intelliwiz_config/settings/production.py:89-95
CORS_ALLOWED_ORIGINS = ["https://django5.youtility.in"]
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://\w+\.youtility\.in$"]
CORS_ALLOW_CREDENTIALS = True
```

**Why Permissive in Development:** Development.py should allow localhost
```python
# intelliwiz_config/settings/development.py (SHOULD ADD)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React dev server
    "http://127.0.0.1:8000",  # Django dev server
]
```

**Security Risk:** 🔴 **HIGH** if misconfigured
- Wildcard CORS (`*`) allows any site to make requests
- Can lead to CSRF attacks and data theft
- OWASP: A01:2021 - Broken Access Control

**Status:** ✅ **ACCEPTABLE** - Production already strict, development could be more explicit

---

## 🟡 MEDIUM PRIORITY FLAGS

### 6. GraphQL Introspection in Production

**Location:** `intelliwiz_config/settings/base.py:176`

**Base Configuration:**
```python
GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION = True  # ✅ Good default
```

**Security Assessment:** ✅ **SECURE**
- Introspection reveals schema structure to attackers
- Disabled in production by default
- No override needed

**Status:** ✅ **SECURE** - No changes required

---

### 7. GraphQL Origin Validation

**Location:** `intelliwiz_config/settings/base.py:174`

**Base Configuration:**
```python
GRAPHQL_STRICT_ORIGIN_VALIDATION = False  # ← Should be True in production
```

**Why Permissive:** Allows GraphQL queries from any origin during development (useful for GraphiQL, Postman, etc.)

**Security Risk:** 🟡 **MEDIUM**
- Without strict validation, any website can query your GraphQL API
- Can lead to data exfiltration
- Should be paired with CORS for defense-in-depth

**Production Override Recommended:**
```python
# intelliwiz_config/settings/production.py (ADD THIS)
GRAPHQL_STRICT_ORIGIN_VALIDATION = True
```

**Status:** ⚠️ **NEEDS IMPLEMENTATION**

---

### 8. Rate Limiting Window

**Location:** `intelliwiz_config/settings/production.py:151-153`

**Production Configuration:**
```python
RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_MAX_ATTEMPTS = 5
```

**Security Assessment:** 🟢 **GOOD**
- 5 attempts per 15 minutes is reasonable for login endpoints
- May need adjustment based on usage patterns

**Recommendation:** Monitor and adjust based on:
- False positive lockouts (legitimate users blocked)
- Brute force attempts in logs
- User feedback

**Status:** ✅ **ACCEPTABLE** - Monitor in production

---

## 🟢 LOW PRIORITY (Informational)

### 9. Email Verification Token Lifetime

**Location:** `intelliwiz_config/settings/production.py:126-127`

**Configuration:**
```python
EMAIL_TOKEN_LIFE = 60**2  # 1 hour
EMAIL_MAIL_TOKEN_LIFE = 60**2  # 1 hour
```

**Security Assessment:** ✅ **SECURE**
- 1-hour expiration is standard for email verification
- Balances security with user experience

**Status:** ✅ **ACCEPTABLE**

---

### 10. Feature Flags (Conservative Defaults)

**Location:** `intelliwiz_config/settings/production.py:155-180`

**Configuration:**
```python
PERSONALIZATION_FEATURE_FLAGS = {
    'enable_hot_path_precompute': env.bool('FF_HOT_PATH_PRECOMPUTE', default=False),
    'enable_streaming_responses': env.bool('FF_STREAMING_RESPONSES', default=False),
    # ... most features enabled by default
}
```

**Security Assessment:** ✅ **SECURE**
- Experimental features disabled by default
- Requires explicit environment variable to enable
- Good practice for gradual rollout

**Status:** ✅ **ACCEPTABLE**

---

## 📋 Quick Reference Table

| Setting | Base Value | Production Value | Risk | Status |
|---------|-----------|------------------|------|--------|
| LANGUAGE_COOKIE_SECURE | ❌ False | ✅ True | 🟡 Medium | ✅ Fixed |
| JWT_EXPIRATION_DELTA | 8 hours | 2 hours | 🟡 Medium | ✅ Fixed |
| Jinja auto_reload | ✅ True | ❌ False (recommended) | 🟢 Low | ⚠️ TODO |
| SESSION_COOKIE_AGE | 2 hours | 2 hours (acceptable) | 🟢 Low | ✅ OK |
| CORS_ALLOWED_ORIGINS | (none) | Strict whitelist | 🔴 High | ✅ Secure |
| GRAPHQL_DISABLE_INTROSPECTION | ✅ True | ✅ True | 🟢 Low | ✅ Secure |
| GRAPHQL_STRICT_ORIGIN_VALIDATION | ❌ False | ✅ True (should add) | 🟡 Medium | ⚠️ TODO |
| RATE_LIMIT_MAX_ATTEMPTS | (none) | 5 per 15min | 🟢 Low | ✅ OK |

---

## 🔧 Implementation Checklist

### Immediate Actions (Phase 3 Completion)

**1. Add GraphQL Strict Origin Validation**
```python
# File: intelliwiz_config/settings/production.py
# Add after line 123 (after GRAPHQL_JWT)

# GraphQL origin validation (production security)
GRAPHQL_STRICT_ORIGIN_VALIDATION = True
```

**2. Disable Jinja2 Auto-Reload in Production**
```python
# File: intelliwiz_config/settings/production.py
# Add after line 123

# Template performance optimization (production)
from copy import deepcopy
TEMPLATES = deepcopy(TEMPLATES)
if len(TEMPLATES) > 1:  # Jinja2 template config
    TEMPLATES[1]['OPTIONS']['auto_reload'] = False
```

**3. Update Startup Validation**
Add checks for these settings in `apps/core/startup_checks.py`:
```python
def _validate_graphql_origin_security(self) -> ValidationResult:
    """Validate GraphQL origin validation is enabled in production"""
    if self.environment == 'production':
        strict_validation = getattr(settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION', False)
        if not strict_validation:
            return ValidationResult(
                passed=False,
                check_name="GraphQL Origin Validation",
                severity="MEDIUM",
                message="⚠️ GraphQL strict origin validation disabled in production",
                remediation="Set GRAPHQL_STRICT_ORIGIN_VALIDATION = True in production.py"
            )
    return ValidationResult(
        passed=True,
        check_name="GraphQL Origin Validation",
        severity="MEDIUM",
        message="✅ GraphQL origin validation configured correctly"
    )
```

---

## 📊 Risk Assessment Matrix

### Critical Path to Production

```
Development → Staging → Production
    ↓           ↓           ↓
Permissive → Testing → Strict
```

**Development Environment:**
- All permissive flags acceptable
- Prioritize developer experience
- Security awareness (not enforcement)

**Staging Environment:**
- Mix of production-like settings with some debugging enabled
- Should match production security closely
- Use for security testing

**Production Environment:**
- ALL security flags at strictest values
- Zero tolerance for permissive settings
- Startup validation blocks deployment if misconfigured

---

## 🧪 Testing Permissive Flags

### Automated Detection Script

```python
# scripts/audit_permissive_flags.py
"""
Audit script to detect permissive security flags.
Run before production deployment.
"""

from django.conf import settings
import sys

def audit_security_flags():
    """Check all permissive flags are overridden in production"""

    issues = []

    # Check 1: Language cookie
    if not getattr(settings, 'LANGUAGE_COOKIE_SECURE', False):
        issues.append("LANGUAGE_COOKIE_SECURE is False")

    # Check 2: JWT expiration
    jwt_config = getattr(settings, 'GRAPHQL_JWT', {})
    if not jwt_config.get('JWT_VERIFY_EXPIRATION'):
        issues.append("JWT_VERIFY_EXPIRATION is disabled")

    jwt_expiry_hours = jwt_config.get('JWT_EXPIRATION_DELTA').total_seconds() / 3600
    if jwt_expiry_hours > 4:
        issues.append(f"JWT tokens expire after {jwt_expiry_hours} hours (too long)")

    # Check 3: GraphQL origin validation
    if not getattr(settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION', False):
        issues.append("GRAPHQL_STRICT_ORIGIN_VALIDATION is disabled")

    # Check 4: Jinja auto-reload
    templates = getattr(settings, 'TEMPLATES', [])
    for template in templates:
        if 'jinja2' in template.get('BACKEND', '').lower():
            if template['OPTIONS'].get('auto_reload', False):
                issues.append("Jinja2 auto_reload is enabled (performance impact)")

    if issues:
        print("🚨 PERMISSIVE SECURITY FLAGS DETECTED:")
        for issue in issues:
            print(f"  ❌ {issue}")
        return False
    else:
        print("✅ All security flags properly configured for production")
        return True

if __name__ == '__main__':
    import django
    django.setup()

    if not audit_security_flags():
        sys.exit(1)
```

**Usage:**
```bash
python scripts/audit_permissive_flags.py
# Exit code 0 = all good, 1 = issues found
```

---

## 📚 Related Documentation

- `SECURITY_SETTINGS_CHECKLIST.md` - Pre-deployment validation checklist
- `SECURITY_FIXES_CRITICAL.md` - Critical security fixes implemented
- `apps/core/startup_checks.py` - Automated startup validation
- `.claude/rules.md` - Security development rules

---

## 🔄 Review Schedule

**This document should be reviewed:**
- After every Django upgrade
- When adding new security-sensitive settings
- Quarterly as part of security audit
- Before major production deployments

**Last Reviewed:** 2025-01-30
**Next Review:** 2025-04-30
**Reviewer:** Security Team Lead

---

## ✅ Sign-Off

**Phase 3 Completion Status:**

✅ **Documented:**
- All permissive flags identified
- Risk assessments completed
- Override requirements specified

⚠️ **TODO (Immediate):**
- Implement GraphQL strict origin validation
- Disable Jinja2 auto-reload in production
- Add automated flag detection script

📋 **TODO (Short-term):**
- Add startup checks for new flags
- Create staging environment validation
- Monitor production for configuration drift

---

**Document Version:** 1.0
**Author:** Claude Code Security Audit
**Approved By:** [Pending]