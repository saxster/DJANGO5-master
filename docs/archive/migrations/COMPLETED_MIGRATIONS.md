# Completed Migrations Archive

**Archive Date:** 2025-10-29
**Reason:** Implementation complete (>6 months old)
**Status:** Historical reference only

---

## Archived Migrations

### 1. DateTime Refactoring (Sep 2025)

**Completion:** September 2025
**Duration:** ~6 months
**Impact:** Python 3.12+ compatibility

#### What Changed
- Replaced `datetime.utcnow()` with `timezone.now()`
- Imported from `django.utils import timezone` (not `datetime.timezone`)
- Used constants from `datetime_constants.py` (e.g., `SECONDS_IN_DAY`)
- Centralized datetime utilities in `datetime_utilities.py`

#### Final Pattern (Retained in Main Docs)
```python
# ✅ CORRECT
from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

# Model fields
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
event_time = models.DateTimeField(default=timezone.now)

# ❌ FORBIDDEN
datetime.utcnow()  # Deprecated in Python 3.12
```

#### Reference
- **Full details:** `DATETIME_REFACTORING_COMPLETE.md` (root directory, to be archived)
- **Standards:** `docs/DATETIME_FIELD_STANDARDS.md` (current)

---

### 2. Select2 PostgreSQL Migration (Oct 2025)

**Completion:** October 2025
**Duration:** ~2 months
**Impact:** Removed Redis dependency for dropdowns

#### What Changed
- Select2 cache backend: Redis → PostgreSQL materialized views
- Created `MaterializedViewSelect2Cache` backend
- Materialized views: `mv_people_dropdown`, `mv_location_dropdown`, `mv_asset_dropdown`
- Architecture simplification (one less Redis database)

#### Final Pattern (Retained in Main Docs)
```python
# Select2 cache configuration
CACHES['select2'] = {
    'BACKEND': 'apps.core.cache.materialized_view_select2.MaterializedViewSelect2Cache',
    'LOCATION': '',  # No Redis needed
    'OPTIONS': {
        'MAX_ENTRIES': 10000,
        'CULL_FREQUENCY': 3,
    },
}
```

#### Performance Impact
- 20ms latency trade-off (Redis <5ms → PostgreSQL ~20ms)
- Acceptable for dropdown use case
- Benefit: Architectural simplicity, one less Redis DB

#### Reference
- **Implementation:** `apps/core/cache/materialized_view_select2.py`
- **Migration notes:** Removed from CLAUDE.md during optimization

---

### 3. God File Refactoring (Sep 2025)

**Completion:** September 2025
**Duration:** ~4 months
**Impact:** Eliminated monolithic files, improved maintainability

#### What Changed
- **Reports Views:** 2,070 lines → 5 modules (base, template, configuration, generation, init)
- **Onboarding Admin:** 1,796 lines → 9 modules (base, typeassist, business_unit, shift, conversation, changeset, knowledge, init)
- **Service Layer:** 31 functions → 6 modules (database, file, geospatial, job, crisis, graphql)

#### Architectural Limits Established
| Component | Max Size | Enforcement |
|-----------|----------|-------------|
| Model classes | 150 lines | Lint check |
| View methods | 30 lines | Complexity check |
| Service files | 150 lines | Lint check |
| Settings files | 200 lines | Lint check |

#### Reference
- **Full phases:** `GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md` (root, to be archived)
- **Current structure:** Documented in docs/ARCHITECTURE.md

---

### 4. schedhuler → scheduler Rename (Oct 2025)

**Completion:** October 2025
**Duration:** 1 sprint
**Impact:** Corrected naming typo throughout codebase

#### What Changed
- App directory: `apps/schedhuler/` → `apps/scheduler/`
- URL patterns: `/schedhuler/` → `/scheduler/` (with backwards compat redirects)
- Templates: `frontend/templates/schedhuler/` → `frontend/templates/scheduler/`
- 719 occurrences across 157 files renamed

#### Backwards Compatibility
- Legacy `/schedhuler/` URLs redirect to `/scheduler/`
- 6-month deprecation period (until January 2026)
- Mobile apps work with both URLs during transition

#### Reference
- **Complete details:** `SCHEDHULER_TO_SCHEDULER_RENAME_COMPLETE.md` (root, to be archived)
- **After Jan 2026:** Remove legacy redirects

---

### 5. Custom User Model Split (Sep 2025)

**Completion:** September 2025
**Duration:** ~2 months
**Impact:** Reduced model complexity below 150-line limit

#### What Changed
- Single `People` model (450 lines) → 3 models:
  - `People` (178 lines) - Core authentication
  - `PeopleProfile` (117 lines) - Personal info
  - `PeopleOrganizational` (177 lines) - Company data
- Backward compatibility via `PeopleCompatibilityMixin`
- Optimized query helper: `People.objects.with_full_details()`

#### Final Pattern (Retained in Main Docs)
```python
# Access works via property accessor
user.profile_image  # Works (property on People model)

# Optimized queries
users = People.objects.with_full_details()  # Includes profile + org
```

#### Reference
- **Implementation:** `apps/peoples/models/` directory
- **Migration guide:** Removed from CLAUDE.md during optimization

---

## Restoration Policy

**When to Restore:**
- **Never:** Final patterns already in main docs
- **Historical reference only:** If need to understand migration process

**How to Restore:**
- Check git history: `git log --all --full-history -- path/to/file`
- Original completion documents in root directory (to be archived)

---

## Current Location of Final Patterns

These migrations are complete. Final patterns documented in:

1. **DateTime Standards:** `docs/RULES.md#datetime-standards`
2. **Select2 Config:** `docs/REFERENCE.md#caching-strategy`
3. **Architecture:** `docs/ARCHITECTURE.md#refactored-architecture`
4. **Scheduler URLs:** `docs/ARCHITECTURE.md#url-design`
5. **User Model:** `docs/ARCHITECTURE.md#data-architecture`

---

**Archived By:** AI Assistant (Claude Code)
**Retention:** 1 year (until 2026-10-29)
**Next Review:** 2026-10-29
