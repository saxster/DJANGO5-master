# apps.onboarding_api - Orphaned Application (November 11, 2025)

## Status: ORPHANED - Middleware Active, App Not Installed

### Critical Finding

**Inconsistent State Detected:**
- ✅ Middleware loaded: `intelliwiz_config/settings/middleware.py:80`
- ❌ App NOT in `INSTALLED_APPS`
- ❌ URLs NOT mounted in root URLconf
- ❌ Models NOT migrated to database

This creates a **partial activation** state where middleware runs but has no endpoints to protect.

---

## Security Impact Analysis

### Middleware Scope Issue (Original Observation)

`OnboardingAPIMiddleware` only protects `/api/v1/onboarding/`:

```python
# apps/onboarding_api/middleware.py:39-41
self.onboarding_api_paths = [
    '/api/v1/onboarding/',  # ← Only V1 protected
]
```

**Bypassed Endpoints (if app were activated):**
- `/api/v2/onboarding/*` - Rate limiting bypassed
- `/api/v2/client-onboarding/*` - No audit logging
- `/api/v2/site-onboarding/*` - No correlation IDs
- `/api/v2/conversation/*` - No performance metrics

**Current Risk:** ZERO - App is not active, URLs don't exist

---

## Investigation Results

### URL Configuration Check

```bash
# Searched for apps.onboarding_api.urls in root URLconf
grep -r "onboarding_api" intelliwiz_config/urls*.py
# Result: No matches found
```

**Conclusion:** URLs are NOT mounted, endpoints don't exist in production.

### App Registration Check

```python
# intelliwiz_config/settings/base.py - INSTALLED_APPS
# Result: 'apps.onboarding_api' is ABSENT
```

**Conclusion:** App is not registered, models not available.

### Middleware Registration Check

```python
# intelliwiz_config/settings/middleware.py:80
"apps.onboarding_api.middleware.OnboardingAPIMiddleware",  # ← ACTIVE!
```

**Conclusion:** Middleware IS loaded but has nothing to do (no matching URLs).

---

## Historical Context

**Purpose:** Phase 1 MVP of conversational onboarding API (client, site, worker onboarding via AI assistant).

**Timeline:**
- **Created**: Early 2025 (conversational onboarding initiative)
- **Partially Implemented**: Middleware, URLs, views exist
- **Never Activated**: App not added to INSTALLED_APPS
- **Superseded**: Modern onboarding apps (client_onboarding, site_onboarding, people_onboarding)

**Why Orphaned:**
- Onboarding was split into 3 separate bounded contexts (client, site, people)
- Each context got its own dedicated app
- Original unified `onboarding_api` app was abandoned mid-development
- Middleware was left in settings but app was never fully activated

---

## Recommended Actions

### Option 1: Complete Removal (RECOMMENDED)

**Pros:**
- Eliminates orphaned code
- Removes middleware overhead (negligible, but unnecessary)
- Cleans up inconsistent state
- No production impact (app not active)

**Steps:**
1. Remove middleware from `intelliwiz_config/settings/middleware.py`
2. Delete `apps/onboarding_api/` directory
3. Create deprecation notice (this file)

### Option 2: Full Activation (NOT RECOMMENDED)

**Only if business needs unified onboarding API:**
1. Add `'apps.onboarding_api'` to INSTALLED_APPS
2. Mount URLs in root URLconf
3. Fix middleware scope to cover V2 endpoints
4. Run migrations
5. Test all endpoints

**Why Not Recommended:**
- Modern onboarding apps (client_onboarding, site_onboarding, people_onboarding) are fully functional
- Unified API creates tight coupling between bounded contexts
- Requires significant effort to complete and test
- No clear business requirement

---

## Middleware Scope Fix (If Activation Needed)

### Current Implementation (Hardcoded Paths)

```python
# apps/onboarding_api/middleware.py:39-41
self.onboarding_api_paths = [
    '/api/v1/onboarding/',
]
```

### Fixed Implementation (Namespace-Based)

```python
# apps/onboarding_api/middleware.py
def _is_onboarding_api_request(self, request: HttpRequest) -> bool:
    """Check if request is for onboarding API endpoints"""
    try:
        resolved_url = resolve(request.path)
        # Check namespace
        onboarding_namespaces = [
            'onboarding_api',
            'client_onboarding',
            'site_onboarding',
            'people_onboarding',
        ]
        return resolved_url.namespace in onboarding_namespaces
    except (Resolver404, ValueError):
        # Fallback to prefix matching
        return any(request.path.startswith(path) for path in self.onboarding_api_paths)
```

**Pros:** Resilient to URL structure changes, covers all versions
**Cons:** Slight performance overhead from `resolve()` call

---

## Migration Path (If Removal Chosen)

**No code changes needed** - Onboarding functionality exists in:
- `apps.client_onboarding` - Client onboarding flows
- `apps.site_onboarding` - Site survey and risk assessment
- `apps.people_onboarding` - Worker onboarding lifecycle
- `apps.core_onboarding` - Shared models (ConversationSession, AIChangeSet)

All have their own APIs, services, and middleware.

---

## Decision: REMOVE (November 11, 2025)

**Rationale:**
1. App is not active (zero production usage)
2. Modern bounded context apps are fully functional
3. Middleware has no endpoints to protect
4. Creates confusion (orphaned state)

**Action Plan:**
1. ✅ Document findings (this notice)
2. ⏳ Remove middleware from settings
3. ⏳ Archive app directory to `.deprecated/`
4. ⏳ Update CLAUDE.md with removal details

**Scheduled Removal Date:** November 11, 2025 (Ultrathink Phase 6)

---

## Related Documentation

- `apps/client_onboarding/README.md` - Active client onboarding
- `apps/site_onboarding/README.md` - Active site onboarding
- `apps/people_onboarding/README.md` - Active people onboarding
- `apps/core_onboarding/README.md` - Shared onboarding infrastructure
- `apps/onboarding/__init__.py` - Deprecated shim (March 2026 removal)

---

**Last Updated:** November 11, 2025
**Author:** Ultrathink Phase 6 Remediation
**Status:** Pending Removal
