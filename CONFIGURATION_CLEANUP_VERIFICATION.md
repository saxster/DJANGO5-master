# Configuration Cleanup - Verification Guide

**Date**: November 1, 2025
**Status**: Implementation Complete - Verification Pending
**Related**: See REMOVED_CODE_INVENTORY.md for complete removal details

---

## Summary of Changes

### ✅ Completed

1. **INSTALLED_APPS Consolidation**
   - Added `'apps.ontology'` to base.py INSTALLED_APPS (line 40)
   - Deleted `intelliwiz_config/settings/installed_apps.py` (133 lines dead code)
   - Single source of truth: `intelliwiz_config/settings/base.py`

2. **Mentor Module Complete Removal**
   - Deleted `apps/mentor_api/` directory (6 files, 52KB)
   - Removed URL routes from `urls_optimized.py` (2 routes)
   - Removed conditional loading from `settings/development.py`
   - Removed mypy config from `mypy.ini`
   - Fixed 2 test files (removed broken imports + test methods)

3. **ML Training Activation**
   - Added `'apps.ml_training'` to base.py INSTALLED_APPS (line 44)
   - Created URL route at `/ml-training/` in `urls_optimized.py`
   - App now accessible: dataset management, labeling interface, active learning

4. **Dead Code Removal**
   - Deleted `issue_tracker/` (top-level, 20KB, 7 files)
   - Deleted `intelliwiz_config/settings_local.py` (24 lines)

5. **Documentation**
   - Created `REMOVED_CODE_INVENTORY.md` (comprehensive removal tracking)
   - Updated `CLAUDE.md` (ml_training in business domains, URL structure, recent changes)

### ⚠️ Pending Verification (Requires Virtual Environment)

6. **Database Migrations**
   - Run migrations for `apps.ontology`
   - Run migrations for `apps.ml_training`

7. **Testing & Validation**
   - Run full test suite
   - Run Django configuration checks
   - Verify Celery ml_training queue routing

---

## Verification Steps

### Prerequisites

```bash
# Activate virtual environment (adjust path as needed)
source venv/bin/activate  # or wherever venv is located

# Verify Python version (should be 3.11.9 per CLAUDE.md)
python --version
```

### Step 1: Django Configuration Checks

```bash
# Check for configuration errors
python manage.py check

# Check with deployment settings
python manage.py check --deploy

# Verify all apps load correctly
python manage.py diffsettings | grep INSTALLED_APPS
```

**Expected Results**:
- ✅ Zero errors from `manage.py check`
- ✅ `apps.ontology` appears in INSTALLED_APPS
- ✅ `apps.ml_training` appears in INSTALLED_APPS
- ✅ No references to `apps.mentor` or `apps.mentor_api`

### Step 2: Database Migrations

```bash
# Check migration status
python manage.py showmigrations ontology
python manage.py showmigrations ml_training

# Create migrations if needed
python manage.py makemigrations ontology
python manage.py makemigrations ml_training

# Apply migrations
python manage.py migrate ontology
python manage.py migrate ml_training

# Verify migrations applied
python manage.py showmigrations | grep -E "(ontology|ml_training)"
```

**Expected Results**:
- ✅ Ontology migrations created and applied successfully
- ✅ ML training migrations created and applied successfully
- ✅ Database tables created for both apps
- ✅ No migration conflicts

### Step 3: Import Validation

```bash
# Verify no import errors for removed modules
python -c "
import django
django.setup()
print('✅ Django setup successful')

# Verify ontology app loads
from apps.ontology.apps import OntologyConfig
print('✅ Ontology app imports successfully')

# Verify ml_training app loads
from apps.ml_training.apps import MlTrainingConfig
print('✅ ML training app imports successfully')

# Verify mentor modules are gone (should fail)
try:
    import apps.mentor
    print('❌ ERROR: apps.mentor still exists')
except ModuleNotFoundError:
    print('✅ apps.mentor correctly removed')

try:
    import apps.mentor_api
    print('❌ ERROR: apps.mentor_api still exists')
except ModuleNotFoundError:
    print('✅ apps.mentor_api correctly removed')
"
```

**Expected Results**:
- ✅ Django setup successful
- ✅ Ontology app imports successfully
- ✅ ML training app imports successfully
- ✅ apps.mentor correctly removed (ModuleNotFoundError)
- ✅ apps.mentor_api correctly removed (ModuleNotFoundError)

### Step 4: URL Configuration Tests

```bash
# Verify URL routing
python manage.py show_urls | grep -E "(ml-training|mentor)"

# Expected: Only /ml-training/ routes, NO /mentor/ routes
```

**Expected Results**:
- ✅ `/ml-training/` routes present (dataset_list, dataset_create, labeling_dashboard, etc.)
- ✅ NO `/mentor/` routes
- ✅ NO `/api/v1/mentor/` routes

### Step 5: Admin Interface Verification

```bash
# Verify admin registration
python manage.py shell -c "
from django.contrib import admin
registered_apps = [m.__module__ for m in admin.site._registry.values()]

# Check ml_training is registered
ml_registered = any('ml_training' in app for app in registered_apps)
print(f'ML Training admin registered: {ml_registered}')

# Check mentor is NOT registered
mentor_registered = any('mentor' in app for app in registered_apps)
print(f'Mentor admin registered: {mentor_registered} (should be False)')
"
```

**Expected Results**:
- ✅ ML Training admin registered: True
- ✅ Mentor admin registered: False

### Step 6: Test Suite Execution

```bash
# Run full test suite
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v

# Run only SQL injection tests (we modified these)
python -m pytest apps/core/tests/test_sql_injection_penetration.py -v
python -m pytest apps/core/tests/test_comprehensive_sql_security_integration.py -v
```

**Expected Results**:
- ✅ All tests pass
- ✅ No import errors for mentor modules
- ✅ SQL injection tests run successfully (mentor test methods removed)
- ✅ No test failures related to configuration changes

### Step 7: Celery Queue Verification

```bash
# Check Celery configuration
python -c "
from apps.core.tasks.celery_settings import CELERY_QUEUES
ml_queue = [q for q in CELERY_QUEUES if q.name == 'ml_training']
print(f'ML training queue configured: {len(ml_queue) > 0}')
print(f'Queue details: {ml_queue[0] if ml_queue else \"Not found\"}')
"

# Start Celery worker (optional - just to verify it starts)
# celery -A intelliwiz_config worker -Q ml_training --loglevel=info
```

**Expected Results**:
- ✅ ML training queue configured: True
- ✅ Celery worker starts without errors
- ✅ ml_training queue appears in active queues

### Step 8: Development Server Test

```bash
# Start development server
python manage.py runserver

# In browser, navigate to:
# http://localhost:8000/ml-training/        (should load ML training dashboard)
# http://localhost:8000/mentor/             (should return 404)
# http://localhost:8000/admin/ml_training/  (should show ML training models)
```

**Expected Results**:
- ✅ Server starts without errors
- ✅ `/ml-training/` loads successfully
- ✅ `/mentor/` returns 404 Not Found
- ✅ `/admin/ml_training/` shows dataset management interface

---

## Rollback Instructions (If Needed)

If verification fails and rollback is required:

```bash
# Restore from git (before this cleanup)
git diff HEAD intelliwiz_config/settings/base.py
git diff HEAD intelliwiz_config/urls_optimized.py
git diff HEAD intelliwiz_config/settings/development.py
git diff HEAD mypy.ini

# Restore specific files
git checkout HEAD~1 -- intelliwiz_config/settings/base.py
# ... etc for each modified file

# Restore deleted files
git checkout HEAD~1 -- intelliwiz_config/settings/installed_apps.py
git checkout HEAD~1 -- issue_tracker/
git checkout HEAD~1 -- intelliwiz_config/settings_local.py
git checkout HEAD~1 -- apps/mentor_api/
```

---

## Success Criteria Checklist

- [ ] Django `manage.py check` passes with zero errors
- [ ] Ontology app migrations created and applied
- [ ] ML training app migrations created and applied
- [ ] No import errors for apps.mentor or apps.mentor_api (ModuleNotFoundError expected)
- [ ] `/ml-training/` URL routes active and functional
- [ ] NO `/mentor/` or `/api/v1/mentor/` routes (404 expected)
- [ ] ML training admin interface accessible
- [ ] Full test suite passes without regressions
- [ ] SQL injection tests pass (mentor test methods removed)
- [ ] Celery ml_training queue configured and accessible
- [ ] Development server starts without errors
- [ ] Code quality validation passes: `python scripts/validate_code_quality.py --verbose`

---

## Known Limitations

1. **Virtual Environment Required**: All verification steps require an active Python virtual environment with Django installed
2. **Database Required**: Migration steps require PostgreSQL/PostGIS database configured
3. **Redis Optional**: Some tests may require Redis for caching (not critical for verification)
4. **Celery Optional**: Worker verification optional but recommended for completeness

---

## Next Steps After Verification

1. Commit changes with comprehensive message:
   ```bash
   git add -A
   git commit -m "refactor: comprehensive configuration cleanup (Phase 5 completion)

   INSTALLED_APPS consolidation:
   - Add apps.ontology to runtime configuration
   - Delete dead installed_apps.py (133 lines)
   - Single source of truth in base.py

   Mentor module complete removal:
   - Delete orphaned apps/mentor_api/ (6 files, 52KB)
   - Remove URL routes, settings, mypy config
   - Fix test imports (2 files, 75 lines removed)

   ML Training activation:
   - Add apps.ml_training to INSTALLED_APPS
   - Create URL route at /ml-training/
   - Enable dataset management, labeling, active learning

   Dead code removal:
   - Delete top-level issue_tracker/ (20KB)
   - Delete unused settings_local.py (24 lines)

   Total cleanup: 15 files removed, ~250 lines dead code eliminated, 14 import errors fixed

   See REMOVED_CODE_INVENTORY.md for complete details."
   ```

2. Run code quality validation:
   ```bash
   python scripts/validate_code_quality.py --verbose
   ```

3. Update project metrics/dashboards if applicable

4. Create PR if using feature branch workflow

---

**Author**: Claude Code
**Verification Status**: ⚠️ PENDING (awaits virtual environment setup)
