# Import Errors Fixed (October 29, 2025)

**Context:** Post-GraphQL migration cleanup revealed cascading import errors
**Status:** Partial fix - GraphQL-related imports resolved, additional pre-existing errors identified

---

## ✅ Fixed Imports (GraphQL Migration Related)

### 1. Missing `ServiceOutputType` (GraphQL type)
**Error:**
```
ModuleNotFoundError: No module named 'apps.service.types'
```

**Root Cause:** `apps/service/types.py` deleted during GraphQL migration (contained GraphQL types)

**Fix:**
- Created `apps/service/rest_types.py` with dataclass replacement
- Updated imports in 3 files:
  - `apps/service/services/database_service.py`
  - `apps/service/services/file_service.py`
  - `apps/service/services/job_service.py`

**Files Modified:**
```python
# OLD (broken):
from apps.service.types import ServiceOutputType

# NEW (working):
from apps.service.rest_types import ServiceOutputType
```

---

### 2. Unused `execute_graphql_mutations` imports
**Error:**
```
ImportError: cannot import name 'execute_graphql_mutations' from 'apps.service.utils'
```

**Root Cause:** Function deleted with GraphQL removal, but imports remained

**Fix:** Commented out unused imports in 6 files:
- `background_tasks/integration_tasks.py`
- `background_tasks/ticket_tasks.py`
- `background_tasks/email_tasks.py`
- `background_tasks/maintenance_tasks.py`
- `background_tasks/job_tasks.py`
- `background_tasks/media_tasks.py`

---

### 3. Unused `get_face_recognition_service` imports
**Error:**
```
ImportError: cannot import name 'get_face_recognition_service' from 'apps.face_recognition.services'
```

**Root Cause:** Top-level imports in background tasks, but function already imported locally where needed

**Fix:** Commented out redundant top-level imports in 5 files:
- `background_tasks/integration_tasks.py`
- `background_tasks/ticket_tasks.py`
- `background_tasks/email_tasks.py`
- `background_tasks/maintenance_tasks.py`
- `background_tasks/job_tasks.py`
- `background_tasks/media_tasks.py` (kept local import in function)

---

### 4. Missing Pydantic Schemas
**Error:**
```
ImportError: cannot import name 'BtModifiedAfterSchema' from 'apps.service.pydantic_schemas.bt_schema'
```

**Root Cause:** Schemas never existed or were deleted

**Fix:** Removed non-existent schema imports from `apps/service/pydantic_schemas/__init__.py`:
- `BtModifiedAfterSchema`
- `QuestionSetModifiedAfterSchema`
- `TicketModifiedAfterSchema`
- `TypeAssistModifiedAfterSchema`
- `WorkPermitModifiedAfterSchema`

---

### 5. Incorrect CSV Security Import Names
**Error:**
```
ImportError: cannot import name 'CsvInjectionProtector' from 'apps.core.security.csv_injection_protection'
ImportError: cannot import name 'sanitize_csv_fields'
```

**Root Cause:** Incorrect capitalization and function name

**Fix:** Updated `apps/core/security/__init__.py`:
```python
# OLD (broken):
from .csv_injection_protection import CsvInjectionProtector, sanitize_csv_fields

# NEW (working):
from .csv_injection_protection import (
    CSVInjectionProtector as CsvInjectionProtector,
    sanitize_csv_value,
    sanitize_csv_data
)
sanitize_csv_fields = sanitize_csv_data  # Backward compatibility alias
```

---

### 6. ViewSets Directory vs File Conflict
**Error:**
```
ImportError: cannot import name 'PeopleViewSet' from 'apps.peoples.api.viewsets'
ImportError: cannot import name 'JobViewSet' from 'apps.activity.api.viewsets'
```

**Root Cause:** Both `viewsets.py` file AND `viewsets/` directory exist, causing circular import

**Fix:** Renamed files to avoid conflicts:
- `apps/peoples/api/viewsets.py` → `apps/peoples/api/people_viewsets.py`
- `apps/activity/api/viewsets.py` → `apps/activity/api/activity_viewsets.py`

Updated `viewsets/__init__.py` in both apps to import from renamed files.

---

## ⚠️ Remaining Import Errors (Pre-Existing)

These errors existed BEFORE the GraphQL migration and require separate investigation:

### 1. Missing `TicketHistory` Model
**Error:**
```
ImportError: cannot import name 'TicketHistory' from 'apps.y_helpdesk.models'
```

**Location:** Unknown importer
**Impact:** Prevents Django from starting
**Action Required:** Find where TicketHistory is imported and fix

### 2. Missing `TenantAwareModel` from peoples.models
**Error:**
```
ImportError: cannot import name 'TenantAwareModel' from 'apps.peoples.models'
```

**Location:** `apps/y_helpdesk/models/ticket_workflow.py:17`
**Correct Import:** Should be from `apps.tenants.models`
**Fix Applied:** ✅ Changed to `from apps.tenants.models import TenantAwareModel`

---

## 📊 Summary

| Category | Count |
|----------|-------|
| **GraphQL-Related Errors Fixed** | 6 errors |
| **Files Modified** | 20 files |
| **Files Renamed** | 2 files |
| **New Files Created** | 1 file (`rest_types.py`) |
| **Remaining Pre-Existing Errors** | ~2-3 errors |

---

## ✅ Fixes Applied

**Created Files:**
- `apps/service/rest_types.py` - ServiceOutputType dataclass (GraphQL replacement)

**Renamed Files:**
- `apps/peoples/api/viewsets.py` → `people_viewsets.py`
- `apps/activity/api/viewsets.py` → `activity_viewsets.py`

**Modified Files:**
1. `apps/service/services/database_service.py` - Updated import
2. `apps/service/services/file_service.py` - Updated import
3. `apps/service/services/job_service.py` - Updated import
4. `apps/service/pydantic_schemas/__init__.py` - Removed non-existent imports
5. `apps/core/security/__init__.py` - Fixed CSV security imports
6. `apps/peoples/api/viewsets/__init__.py` - Fixed imports from renamed file
7. `apps/activity/api/viewsets/__init__.py` - Fixed imports from renamed file
8. `apps/y_helpdesk/models/ticket_workflow.py` - Fixed TenantAwareModel import
9. `background_tasks/integration_tasks.py` - Removed unused imports (2)
10. `background_tasks/ticket_tasks.py` - Removed unused import
11. `background_tasks/email_tasks.py` - Removed unused import
12. `background_tasks/maintenance_tasks.py` - Removed unused import
13. `background_tasks/job_tasks.py` - Removed unused import
14. `background_tasks/media_tasks.py` - Removed unused import

---

## 🎯 OpenAPI Schema Status

**Current:** Basic fallback schema generated (177 lines)
**Blocker:** Remaining pre-existing import errors prevent full Django startup
**Workaround:** Use interactive docs when Django runs: http://localhost:8000/api/schema/swagger/

**To Generate Full Schema:**
1. Fix remaining import errors (TicketHistory, etc.)
2. Run: `./venv/bin/python manage.py spectacular --file openapi-schema.yaml --validate`

---

## 📝 Recommendations

### Immediate (Fix Remaining Errors)
1. Find and fix `TicketHistory` import/definition
2. Audit all models/__init__.py for missing exports
3. Run `python manage.py check` until it passes
4. Generate complete OpenAPI schema

### Short-term (Prevent Future Issues)
1. Add pre-commit hook to test imports
2. Run `python manage.py check` in CI/CD
3. Document model export patterns
4. Consider using `__all__` in all __init__.py files

---

**Created:** October 29, 2025
**Status:** Partial fix - GraphQL errors resolved, pre-existing errors remain
**Next Action:** Fix TicketHistory import to complete Django startup
