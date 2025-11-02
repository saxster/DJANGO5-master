# Removed Code Inventory

**Purpose**: Track all deleted code to prevent reintroduction and document cleanup decisions.

**Last Updated**: November 1, 2025

---

## November 1, 2025 - Configuration Cleanup (Comprehensive)

### Issue Resolution: Configuration Drift and Dead Code Elimination

**Context**: Completed incomplete Phase 5 cleanup from Oct 31, 2025. Resolved 5 critical configuration issues causing INSTALLED_APPS drift, import failures, and technical debt.

### 1. Mentor Module Complete Removal

**Decision**: Delete (mentor moved to separate service that was never created)

#### Deleted:
- `apps/mentor_api/` directory (6 Python files, 52KB)
  - `views.py` (14 import failures to non-existent apps.mentor.*)
  - `urls.py`, `apps.py`, `models.py`, `tests.py`, `__init__.py`
- URL routes in `intelliwiz_config/urls_optimized.py` (lines 133-134)
  - `path('mentor/', ...)` - Web interface route
  - `path('api/v1/mentor/', ...)` - API route
- Conditional app loading in `intelliwiz_config/settings/development.py` (lines 46-49)
  - Removed `MENTOR_ENABLED` environment variable check
  - Removed `INSTALLED_APPS.extend(["apps.mentor", "apps.mentor_api"])`
- MyPy configuration in `mypy.ini` (line 207-210)
  - `[mypy-apps.mentor.*]` section
- Test code in 2 files:
  - `apps/core/tests/test_sql_injection_penetration.py`:
    - Removed import: `from apps.mentor.storage.index_db import MentorIndexDB`
    - Removed test method: `test_mentor_index_db_security()` (35 lines)
  - `apps/core/tests/test_comprehensive_sql_security_integration.py`:
    - Removed import: `from apps.mentor.storage.index_db import MentorIndexDB`
    - Removed test method: `test_mentor_index_db_security_integration()` (40 lines)

**Rationale**:
- apps.mentor/ was deleted Oct 31, 2025 (commit 3d952ff) with note "moved to separate service"
- No separate service was ever created (checked parent directories, documentation)
- apps.mentor_api/ was orphaned REST API layer with 14 broken imports
- Keeping API without backend = guaranteed ModuleNotFoundError on all /mentor/ requests
- Completed the incomplete Phase 5 cleanup

**Impact**:
- Eliminated 14 import errors that would crash on runtime
- Removed 2 URL namespaces that led to non-existent endpoints
- Cleaned up 75 lines of test code testing non-existent components
- Reduced configuration complexity

### 2. INSTALLED_APPS Consolidation

**Decision**: Use base.py as single source of truth, delete installed_apps.py

#### Deleted:
- `intelliwiz_config/settings/installed_apps.py` (133 lines, entire file)
  - Canonical INSTALLED_APPS list with 36 apps (including duplicates)
  - AUTH_USER_MODEL setting (duplicated from base.py)
  - Complete module that was NEVER imported anywhere

#### Added:
- `'apps.ontology'` to `intelliwiz_config/settings/base.py` (line 40)
  - Previously only in installed_apps.py, now in runtime configuration
  - Enables ontology models, migrations, and LLM-assisted development features

**Rationale**:
- Two INSTALLED_APPS definitions had diverged (apps.ontology missing from runtime)
- installed_apps.py was 100% dead code - created but never imported by any settings module
- Configuration drift: 29 apps in base.py vs 29 in installed_apps.py with different contents
- Single source of truth prevents future drift and reduces maintenance burden

**Impact**:
- Ontology app now loads correctly (models, migrations, admin)
- Eliminated 133 lines of dead code
- Prevented future configuration drift
- Simplified settings architecture

### 3. Top-Level issue_tracker/ Removal

**Decision**: Delete duplicate top-level package, keep apps/issue_tracker/

#### Deleted:
- `issue_tracker/` directory (7 files, 20KB)
  - `apps.py` with `name = 'issue_tracker'` (wrong app label)
  - Empty `models.py`, `views.py`, `admin.py`, `tests.py`
  - `migrations/` directory (empty except __init__)
  - `__init__.py`

**Rationale**:
- INSTALLED_APPS loads `'apps.issue_tracker'` (correct app)
- Top-level issue_tracker/ never imported (grep found 0 references)
- Namespace confusion: Two apps with same logical name
- Left over from old project structure before apps/ directory organization

**Impact**:
- Eliminated namespace confusion
- Removed 20KB of dead scaffolding code
- Prevented potential import conflicts
- Cleaned up project root directory

### 4. Unused settings_local.py Removal

**Decision**: Delete unused local settings module

#### Deleted:
- `intelliwiz_config/settings_local.py` (24 lines)
  - `ONDEMAND_REPORTS_GENERATED` path override
  - `TEMP_REPORTS_GENERATED` path override
  - `os.makedirs()` calls that run on import
  - Print statements for local development

**Rationale**:
- Never imported by any settings module (grep found 0 references)
- Creates directories on import (side effects in module-level code)
- Report path overrides should be in development.py if needed
- Unclear purpose, no documentation

**Impact**:
- Removed inert code with potential filesystem side effects
- If report path customization needed, will be reimplemented properly in development.py

### 5. ML Training App Activation

**Decision**: Activate complete but unloaded app

#### Added:
- `'apps.ml_training'` to `intelliwiz_config/settings/base.py` (line 44)
- URL route in `intelliwiz_config/urls_optimized.py` (line 133):
  - `path('ml-training/', include('apps.ml_training.urls'))`

**Rationale**:
- apps.ml_training/ was complete (models, views, admin, URLs, templates) but never loaded
- 12 Python files, 8 HTML templates, full admin interface - all functional code
- apps.noc/ references ml_training models, but they weren't available
- Celery queue provisioned (`ml_training` queue) but no app to use it
- 17KB models.py, 19KB views.py - substantial working code

**Impact**:
- ML Training Data Platform now accessible at `/ml-training/`
- Dataset management, labeling interface, active learning features available
- Admin interface registered
- Database tables will be created on migration
- Celery queue now has corresponding app

---

## Summary Statistics - Nov 1, 2025 Cleanup

### Deleted:
- **Files removed**: 15 files (mentor_api/ + issue_tracker/ + installed_apps.py + settings_local.py)
- **Code removed**: ~250 lines of dead/broken code
- **Disk space freed**: ~72KB
- **Import errors eliminated**: 14 (all in mentor_api/views.py)
- **URL routes removed**: 2 (both leading to ModuleNotFoundError)

### Added:
- **Apps activated**: 2 (`apps.ontology`, `apps.ml_training`)
- **URL routes added**: 1 (`/ml-training/`)
- **Configuration fixes**: INSTALLED_APPS consolidated to single source of truth

### Risk Assessment:
- **Zero functional impact**: All removed code was dead/broken/orphaned
- **Positive impact**: Eliminated import errors, activated working features
- **Migration required**: ml_training and ontology need `makemigrations` + `migrate`
- **Testing required**: Full test suite + Django checks to verify no regressions

---

## Related Commits

- **Oct 31, 2025** (3d952ff): Phase 5 cleanup - deleted apps.mentor/ (incomplete - left orphans)
- **Nov 1, 2025** (pending): Comprehensive configuration cleanup - completed Phase 5

---

## Lessons Learned

1. **Incomplete cleanup is worse than no cleanup**: Phase 5 deleted apps.mentor/ but left apps.mentor_api/, URL routes, tests, and settings referencing it
2. **Configuration drift detection**: Need automated checks for INSTALLED_APPS consistency across settings modules
3. **Import validation in CI/CD**: Should catch "import from non-existent module" before merge
4. **Dead code accumulation**: Top-level issue_tracker/ and settings_local.py sat unused for months
5. **Hidden gems**: Complete, working apps (ml_training) not loaded due to configuration oversight

---

## Future Prevention

- [ ] Add pre-commit hook to validate all imports resolve
- [ ] Add CI check for INSTALLED_APPS consistency (no duplicate lists)
- [ ] Add CI check for orphaned directories in project root
- [ ] Document all "moved to separate service" decisions with issue tracker links
- [ ] Quarterly dead code scan using static analysis tools
