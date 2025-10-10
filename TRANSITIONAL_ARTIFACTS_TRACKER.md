# Transitional Artifacts Tracker

> **Purpose**: Track all backward compatibility shims, deprecated code, transitional wrappers, and feature flags to ensure systematic cleanup and prevent technical debt accumulation.
>
> **Created**: 2025-10-10
> **Review Cycle**: Bi-weekly (every 2 weeks)
> **Retention Policy**: Artifacts are kept for 2 sprints (4 weeks) unless critical dependencies exist

---

## 📊 Summary Dashboard

| Category | Count | Removal Target | Status |
|----------|-------|----------------|--------|
| **Compatibility Shims** | 2 | 2025-12-10 | 🟡 Tracked |
| **Deprecated Functions** | 6 | 2025-12-10 | 🟡 Tracked |
| **Feature Flags** | 2 | 2025-11-10 | 🟢 Active |
| **Legacy URL Patterns** | 8 | TBD | 🟡 Monitored |
| **Placeholder Views** | 8 | 2025-11-24 | 🟢 Active |
| **Archive Directories** | 4 | 2025-11-10 | 🟢 Active |

**Legend**:
- 🟢 Active - In use, monitored
- 🟡 Tracked - Removal date set
- 🔴 Overdue - Past removal date, needs action
- ⚪ Removed - Successfully cleaned up

---

## 🔄 Compatibility Shims

### 1. apps/reports/views_compat.py

**Type**: File/Package Name Collision Fix
**Created**: 2025-10-10
**Target Removal**: 2025-12-10 (2 sprints)
**Status**: 🟡 Tracked
**Dependencies**: Legacy imports using `from apps.reports import views`

**Description**:
Renamed from `views.py` to `views_compat.py` to resolve naming collision with `apps/reports/views/` package directory. Provides 100% backward compatibility for legacy code.

**Migration Path**:
```python
# OLD (deprecated):
from apps.reports import views_compat
views_compat.DownloadReports.as_view()

# NEW (correct):
from apps.reports.views.generation_views import DownloadReports
```

**Cleanup Actions**:
1. Search codebase for `import views_compat` or `from apps.reports import views`
2. Replace with direct imports from `apps.reports.views.{module}`
3. Remove `views_compat.py` file
4. Update any external documentation

**Blocker**: None identified

---

### 2. apps/service/utils.py

**Type**: Service Extraction Compatibility Shim
**Created**: 2025-09-30
**Target Removal**: 2025-12-10 (2 sprints)
**Status**: 🟡 Tracked
**Dependencies**: Legacy imports using `from apps.service import utils`

**Description**:
Re-exports all functions from `apps.service.services.*` for backward compatibility after god file refactoring.

**Migration Path**:
```python
# OLD (deprecated):
from apps.service.utils import insertrecord_json
from apps.service import utils as sutils

# NEW (correct):
from apps.service.services.database_service import insertrecord_json
from apps.service.services import database_service
```

**Cleanup Actions**:
1. Search for `from apps.service import utils` or `from apps.service.utils import`
2. Replace with `from apps.service.services.{specific_module} import`
3. Remove `utils.py` file after all imports updated

**Blocker**: Widespread usage - requires comprehensive codebase search

---

## 🚫 Deprecated Functions

### 1. Frappe ERP Wrapper Functions (generation_views.py)

**Functions**: `getClient()`, `getCustomer()`, `getPeriod()`, `getCustomersSites()`, `getAllUAN()`, `get_frappe_data()`
**File**: `apps/reports/views/generation_views.py` (lines 520-663)
**Created**: 2025-10-10
**Target Removal**: 2025-12-10 (2 sprints)
**Status**: 🟡 Tracked
**Replacement**: `FrappeService` class in `apps/reports/services/frappe_service.py`

**Description**:
Legacy standalone functions replaced with comprehensive `FrappeService` class. Backward compatibility wrappers emit `DeprecationWarning` and delegate to new service.

**Migration Path**:
```python
# OLD (deprecated):
from apps.reports.views.generation_views import getClient, getAllUAN
client = getClient("SPS")
payroll_data = getAllUAN("SPS", "CUST001", "SITE001", ["2024-01"], "PF")

# NEW (correct):
from apps.reports.services import FrappeService, FrappeCompany, PayrollDocumentType
service = FrappeService()
client = service.get_client(FrappeCompany.SPS)
payroll_data = service.get_payroll_data(
    company=FrappeCompany.SPS,
    customer_code="CUST001",
    site_code="SITE001",
    periods=["2024-01"],
    document_type=PayrollDocumentType.PF
)
```

**Benefits of New Implementation**:
- ✅ Type hints (compile-time safety)
- ✅ Environment-based configuration (no hardcoded credentials)
- ✅ Connection pooling (performance)
- ✅ Comprehensive error handling
- ✅ Testable design
- ✅ Logging and monitoring

**Cleanup Actions**:
1. Search for: `getClient(`, `getCustomer(`, `getPeriod(`, `getCustomersSites(`, `getAllUAN(`, `get_frappe_data(`
2. Replace with `FrappeService` equivalents
3. Remove wrapper functions from generation_views.py (lines 520-663)

**Usage Stats** (to be monitored):
- getClient: TBD
- getAllUAN: 15+ usages in GeneratePdf, GenerateLetter views
- get_frappe_data: Called by all other wrappers

**Blocker**: Moderate usage in PDF generation views - requires careful migration

---

## 🚩 Feature Flags

### 1. USE_DJANGO_ORM_FOR_ASSETS

**File**: `apps/service/queries/asset_queries_with_fallback.py`
**Purpose**: Control migration from PostgreSQL functions to Django ORM
**Default**: `false` (uses Django ORM)
**Target Removal**: 2025-11-10 (1 month)
**Status**: 🟢 Active

**Description**:
Feature flag to support gradual migration from PostgreSQL stored procedures to Django ORM for asset queries. Both paths currently execute the same Django ORM code.

**Cleanup Actions**:
1. Remove feature flag check (line 38)
2. Remove `if use_django_orm` conditional block
3. Simplify to single code path
4. Update documentation

**Monitoring**: No usage of `USE_DJANGO_ORM_FOR_ASSETS=true` detected in logs

---

### 2. ENABLE_LEGACY_URLS

**File**: `intelliwiz_config/urls_optimized.py`
**Purpose**: Control legacy URL pattern inclusion during domain-driven architecture migration
**Default**: `True`
**Target Removal**: TBD (pending OptimizedURLRouter analytics)
**Status**: 🟡 Monitored

**Description**:
Controls inclusion of LEGACY_PATTERNS (lines 165-182) which provide backward compatibility for old URL structure during migration to domain-driven URLs.

**Legacy Patterns**:
- `/onboarding/` → `/people/onboarding/`
- `/schedhuler/` → `/operations/scheduler/`
- `/y_helpdesk/` → `/help-desk/`
- `/activity/` → `/operations/`
- `/attendance/` → `/people/attendance/`
- 3 more patterns

**Cleanup Actions**:
1. Review OptimizedURLRouter analytics for 404s on new URLs
2. When 404 rate < 1%, set `ENABLE_LEGACY_URLS = False`
3. Monitor for 1 sprint
4. Remove LEGACY_PATTERNS block entirely

**Blocker**: Requires OptimizedURLRouter to be re-enabled (currently disabled due to scheduler issues)

---

## 📁 Archive Directories

### 1. .archive/duplicate_placeholders_20251010/

**Created**: 2025-10-10
**Target Deletion**: 2025-11-10 (1 month)
**Size**: 6.1 KB
**Status**: 🟢 Active

**Contents**:
- `views_missing.py_archived_20251010` (175 lines)

**Restoration Procedure**: Copy back to `apps/onboarding/views_missing.py` if needed

---

### 2. .archive/dead_code_20251010/

**Created**: 2025-10-10
**Target Deletion**: 2025-11-10 (1 month)
**Size**: 98 bytes
**Status**: 🟢 Active

**Contents**:
- `service_views.py_archived_20251010` (0 bytes)
- `urls_clean.py_archived_20251010` (98 bytes)

**Restoration Procedure**: Not recommended - these files were unused

---

### 3. .archive/llm_refactoring_20251010/

**Created**: 2025-10-10
**Target Deletion**: 2025-11-24 (6 weeks - extended for safety)
**Status**: 🟢 Active
**Note**: Contains LLM service refactoring backups

---

### 4. .archive/stale_god_files_20251010/

**Created**: 2025-10-10
**Target Deletion**: 2025-11-24 (6 weeks - extended for safety)
**Status**: 🟢 Active
**Note**: Contains archived god file implementations before refactoring

---

## 🔧 Settings & Configuration Wrappers

### intelliwiz_config/settings_ia.py

**Type**: Settings Import Wrapper (Suspected)
**Status**: ⚪ Under Investigation
**Action Required**: Verify if fully merged into main settings

**Investigation Tasks**:
1. Search for imports of `settings_ia`
2. If unused, add to dead code removal list
3. If used, document purpose and migration path

---

## 🌐 API Placeholders

### apps/service/rest_service/v2/

**Type**: API v2 Placeholder Endpoints
**Created**: 2025-09-30
**Status**: 🟢 Active (Development in progress)
**Target**: Full implementation by 2025-11-30

**Description**:
Type-safe REST API v2 endpoints with Pydantic validation. Currently includes status endpoint and foundation for mobile sync endpoints.

**Action**: Monitor development progress, no removal planned (active feature)

---

## 📈 Monitoring & Analytics

### Tracking Commands

```bash
# Check for deprecated function usage
grep -r "getClient\|getCustomer\|getPeriod\|getCustomersSites\|getAllUAN" apps/ \
  --include="*.py" \
  --exclude-dir=".archive" \
  | grep -v "def get" \
  | wc -l

# Check for legacy URL usage (requires logs)
grep "schedhuler\|y_helpdesk" logs/access.log | wc -l

# Check archive age
find .archive -type d -mtime +30 -name "*_202510*"

# List all deprecation warnings in logs
grep "DeprecationWarning" logs/django.log | cut -d':' -f2 | sort | uniq -c
```

### Automated Checks (Pre-Commit)

```bash
# Add to .pre-commit-config.yaml
- id: check-deprecated-imports
  name: Check for deprecated imports
  entry: python scripts/check_deprecated_imports.py
  language: python

- id: check-archive-age
  name: Check for old archives
  entry: python scripts/check_archive_age.py --max-age 60
  language: python
```

---

## 🗓️ Removal Schedule

| Date | Action | Items |
|------|--------|-------|
| **2025-11-10** | Archive Cleanup | Delete .archive/*_20251010/ directories |
| **2025-11-10** | Feature Flag | Remove USE_DJANGO_ORM_FOR_ASSETS |
| **2025-11-24** | Placeholder Review | Assess onboarding placeholder views for implementation |
| **2025-12-10** | Compat Shims | Remove views_compat.py, utils.py (service) |
| **2025-12-10** | Frappe Wrappers | Remove deprecated Frappe functions from generation_views.py |
| **TBD** | Legacy URLs | Disable ENABLE_LEGACY_URLS (pending analytics) |

---

## ⚠️ Risks & Blockers

### High Risk Items

1. **apps/service/utils.py Removal**
   - **Risk**: Widespread usage across codebase
   - **Mitigation**: Comprehensive grep search + gradual migration
   - **Timeline**: 2 sprints minimum

2. **Legacy URL Patterns**
   - **Risk**: External mobile apps may use old URLs
   - **Mitigation**: Keep redirects active until mobile app v2.0 release
   - **Blocker**: OptimizedURLRouter disabled (scheduler compatibility)

### Medium Risk Items

3. **Frappe Function Wrappers**
   - **Risk**: Embedded in PDF generation workflows
   - **Mitigation**: Gradual replacement with unit test coverage
   - **Test Coverage**: Add tests before removal

---

## 📝 Adding New Artifacts

When creating new transitional code, follow this checklist:

1. ✅ Add `DEPRECATED` comment or `DeprecationWarning`
2. ✅ Set explicit removal date (2 sprints from creation)
3. ✅ Document in this tracker immediately
4. ✅ Add migration path in comments
5. ✅ Create tracking issue/TODO
6. ✅ Add automated detection if possible

### Template for New Entry

```markdown
### [Artifact Name]

**File**: path/to/file.py
**Created**: YYYY-MM-DD
**Target Removal**: YYYY-MM-DD (X sprints)
**Status**: 🟡 Tracked
**Dependencies**: [List dependencies]

**Description**: [What it does, why it exists]

**Migration Path**:
\`\`\`python
# OLD:
[old code]

# NEW:
[new code]
\`\`\`

**Cleanup Actions**:
1. [Step 1]
2. [Step 2]

**Blocker**: [Any blockers to removal]
```

---

## 🔍 Automated Detection Scripts

### scripts/audit_transitional_artifacts.py

**Status**: 📝 To be created
**Purpose**: Automated detection of transitional code

**Detection Rules**:
- Files with `_compat`, `_legacy`, `_wrapper` suffixes
- Functions with `DEPRECATED` in docstring
- Code emitting `DeprecationWarning`
- Feature flags with boolean toggle
- Archive directories older than 60 days

**Usage**:
```bash
python scripts/audit_transitional_artifacts.py --report ARTIFACTS_AUDIT_REPORT.md
python scripts/audit_transitional_artifacts.py --check-overdue
python scripts/audit_transitional_artifacts.py --generate-removal-pr
```

---

## 📖 Best Practices

### Creating Transitional Code

**DO**:
- ✅ Always set explicit removal dates
- ✅ Emit warnings (DeprecationWarning, logger.warning)
- ✅ Document migration path clearly
- ✅ Add to this tracker immediately
- ✅ Create unit tests for new implementation before deprecating old
- ✅ Use feature flags for large migrations

**DON'T**:
- ❌ Create "temporary" code without removal date
- ❌ Hardcode credentials in compatibility shims
- ❌ Leave orphaned wrappers after migration complete
- ❌ Forget to update this tracker
- ❌ Create transitional code for trivial changes

### Removing Transitional Code

**Checklist**:
1. ✅ Search for all usages (grep, IDE search)
2. ✅ Run full test suite after removal
3. ✅ Archive removed code to `.archive/`
4. ✅ Update this tracker (mark as ⚪ Removed)
5. ✅ Update REMOVED_CODE_INVENTORY.md
6. ✅ Create PR with detailed description
7. ✅ Update documentation

---

## 🎯 Sprint Goals

### Sprint 11 (Current - Oct 2025)
- [x] Create transitional artifacts tracker
- [x] Document all existing artifacts
- [ ] Migrate 50% of `service/utils.py` imports
- [ ] Create audit script

### Sprint 12 (Nov 2025)
- [ ] Complete `service/utils.py` migration
- [ ] Remove USE_DJANGO_ORM_FOR_ASSETS flag
- [ ] Delete October archives
- [ ] Implement automated detection

### Sprint 13 (Dec 2025)
- [ ] Remove Frappe function wrappers
- [ ] Remove `views_compat.py`
- [ ] Remove `service/utils.py`
- [ ] Full cleanup validation

---

## 📊 Impact Metrics

### Code Quality Improvements (Oct 2025)

**Technical Debt Eliminated**:
- ✅ Name collision: 1 → 0
- ✅ Duplicate placeholders: 1 → 0
- ✅ Dead code files: 2 → 0
- ✅ Duplicate functions: 2 `get_col_widths()` → 1 centralized
- ✅ Frappe integration: 6 scattered functions → 1 service class
- ✅ Exception handling: 84 overlapping lines → 30 clean lines

**File Size Reductions**:
- `generation_views.py`: 1,186 → 1,101 lines (-85 lines, -7%)
- `onboarding/views.py`: 438 → 362 lines (-76 lines, -17%)
- `urls_optimized.py`: 3 GraphQL routes → 2 (-33%)

**New Technical Debt Created (Managed)**:
- Compatibility shims: 2 (with removal dates)
- Deprecated functions: 6 (with deprecation warnings)
- Archive directories: 4 (with retention policy)

**Net Impact**: -181 lines of production code, +285 lines of well-structured services

---

## 🔗 Related Documentation

- **Code Quality**: `PYTHON_CODE_QUALITY_FINAL_SUMMARY.md`
- **Removed Code**: `REMOVED_CODE_INVENTORY.md`
- **God File Refactoring**: `GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md`
- **Celery Refactoring**: `CELERY_REFACTORING_PROGRESS_SUMMARY.md`

---

**Last Updated**: 2025-10-10
**Next Review**: 2025-10-24 (bi-weekly)
**Owner**: Development Team
