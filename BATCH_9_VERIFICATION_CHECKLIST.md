# Batch 9 Verification Checklist (Tasks 31-33)

**Branch**: `refactor/bounded-contexts-multimodal`
**Date**: 2025-11-04
**Status**: Implementation Complete - Verification Required

---

## Completed Tasks

### Task 31: Update INSTALLED_APPS ✅
**Commit**: `724d448`

Changes made to `intelliwiz_config/settings/base.py`:
- ❌ Removed: `'apps.onboarding'`
- ❌ Removed: `'apps.onboarding_api'`
- ✅ Added: `'apps.core_onboarding'`
- ✅ Added: `'apps.client_onboarding'`
- ✅ Added: `'apps.site_onboarding'`
- ℹ️ Kept: `'apps.people_onboarding'` (already present)

### Task 32: Update URL Routing ✅
**Commit**: `0468efc`

**Created URL Files:**
1. `apps/client_onboarding/urls.py`
   - App name: `client_onboarding`
   - Router: DefaultRouter (empty, ready for viewsets)
   - URL namespace ready

2. `apps/site_onboarding/urls.py`
   - App name: `site_onboarding`
   - Router: DefaultRouter (empty, ready for viewsets)
   - URL namespace ready

3. `apps/core_onboarding/urls.py`
   - App name: `core_onboarding`
   - Router: DefaultRouter (empty, ready for viewsets)
   - URL namespace ready

**Updated Main URLs** (`intelliwiz_config/urls_optimized.py`):

Removed:
- Line 90: `path('api/v1/onboarding/', include('apps.onboarding_api.urls'))`
- Line 167: `path('onboarding/', include('apps.onboarding.urls'))`
- Line 180: `'apps.onboarding'` from JavaScriptCatalog packages

Added (in API v2 section):
```python
# Bounded Context APIs (Multimodal Onboarding)
path('api/v2/client-onboarding/', include('apps.client_onboarding.urls')),
path('api/v2/site-onboarding/', include('apps.site_onboarding.urls')),
path('api/v2/worker-onboarding/', include('apps.people_onboarding.urls')),
path('api/v2/conversation/', include('apps.core_onboarding.urls')),
```

### Task 33: Verify Configuration ⏳
**Status**: Pending (requires Django environment)

---

## Verification Commands

### Required Checks (Run in main working directory with venv)

```bash
# 1. Verify Django settings load correctly
python3 manage.py check

# Expected output:
# System check identified no issues (0 silenced).

# 2. Verify URL patterns are registered
python3 manage.py show_urls | grep onboarding

# Expected output (new URLs):
# /api/v2/client-onboarding/...
# /api/v2/site-onboarding/...
# /api/v2/worker-onboarding/...
# /api/v2/conversation/...

# Expected output (should NOT appear):
# /api/v1/onboarding/...
# /onboarding/...

# 3. Verify installed apps
python3 manage.py shell -c "from django.conf import settings; print([app for app in settings.INSTALLED_APPS if 'onboarding' in app])"

# Expected output:
# ['apps.people_onboarding', 'apps.core_onboarding', 'apps.client_onboarding', 'apps.site_onboarding']

# Should NOT include:
# 'apps.onboarding'
# 'apps.onboarding_api'

# 4. Test URL reverse lookup
python3 manage.py shell -c "from django.urls import reverse; print('URLs OK')"

# Expected: No errors about missing URL patterns

# 5. Verify imports work
python3 -c "from apps.core_onboarding.models import ConversationSession; print('core_onboarding OK')"
python3 -c "from apps.client_onboarding.models import ClientOnboardingRequest; print('client_onboarding OK')"
python3 -c "from apps.site_onboarding.models import SiteSurveyRequest; print('site_onboarding OK')"
```

---

## Known Limitations

1. **URL files are minimal**: They only contain router setup. Viewsets will be added in later batches.

2. **No migrations yet**: Database schema changes will be handled in Batch 10.

3. **Legacy apps still exist**: The old `apps/onboarding` and `apps/onboarding_api` directories are still present but removed from configuration. They can be deleted after verification.

---

## Expected Errors During Verification

### If Django check fails with import errors:
This means migrations or model imports need attention. Check:
- Model imports in `__init__.py` files
- Foreign key references to old app labels

### If show_urls shows old patterns:
This means legacy URL patterns are still enabled. Check:
```python
# In urls_optimized.py
if getattr(settings, 'ENABLE_LEGACY_URLS', True):
```

Set to `False` in development.py to disable legacy URLs.

---

## Next Steps

After verification passes:

1. **Batch 10**: Create database migrations for all three bounded contexts
2. **Batch 11**: Add viewsets and API endpoints
3. **Batch 12**: Add tests for new URL routing
4. **Cleanup**: Remove old `apps/onboarding` and `apps/onboarding_api` directories

---

## Rollback Instructions

If verification fails and rollback is needed:

```bash
# Rollback to before Batch 9
git reset --hard 5dc31e4

# Or revert specific commits
git revert 0468efc  # URLs
git revert 724d448  # INSTALLED_APPS
```

---

## Sign-off

- [ ] Django check passes
- [ ] URL patterns verified via show_urls
- [ ] INSTALLED_APPS verified
- [ ] URL reverse lookup works
- [ ] Model imports work
- [ ] Ready for Batch 10

**Verified by**: _______________
**Date**: _______________
**Notes**: _______________
