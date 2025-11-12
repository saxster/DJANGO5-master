# Removed Code Inventory

**Purpose**: Track significant code removals to prevent confusion and document decisions.

**Last Updated**: November 11, 2025

---

## November 2025 - Code Quality Remediation (Ultrathink Observations)

### 2025-11-11: MFA Placeholder Removal

**Files Removed:**
- `apps/core/auth/mfa.py` (88 lines)
- `django_otp` from INSTALLED_APPS
- `django-otp==1.5.4` from requirements/base.txt

**Reason**: Incomplete implementation (only TODO docstrings and empty classes)

**Impact**: No MFA capability in system until properly implemented

**Documentation**: `docs/reference/security/MFA_REMOVAL_DECISION.md`

**Commit**: [TBD - add commit hash]

---

### 2025-11-11: Client Onboarding Backup File Removal

**Files Removed:**
- `apps/client_onboarding/views.py.backup` (440+ lines, 16KB)

**Reason**:
- Git-tracked backup file (violates git hygiene)
- Contains broken import statement (syntax error at line 33)
- Actual code refactored into `apps/client_onboarding/views/` directory
- All imports now reference the views module (not the backup)

**Impact**: None - code already refactored and working from `views/` directory

**Verification**:
```bash
grep -r "client_onboarding.views" apps/
# Returns: views/__init__.py exports (SuperTypeAssist, MODEL_RESOURCE_MAP)
```

**Commit**: [TBD - add commit hash]

---

### 2025-11-11: Face Recognition Backup File Removal

**Files Removed:**
- `apps/face_recognition/services/challenge_response_service.py.bak` (376 lines, 13KB)

**Reason**:
- Git-tracked backup file (violates git hygiene)
- Contains inferior code (uses `except Exception` instead of specific exceptions)
- Current file properly uses DATABASE_EXCEPTIONS and BUSINESS_LOGIC_EXCEPTIONS
- Backup likely created before exception handling remediation work

**Impact**: None - current version is superior and fully functional

**Verification**:
```bash
diff challenge_response_service.py challenge_response_service.py.bak
# Shows 7 locations where current file uses specific exceptions
# while backup uses generic `except Exception`
```

**Commit**: [TBD - add commit hash]

---

### 2025-11-11: Clientbilling Stub App Removal

**Files Removed:**
- `apps/clientbilling/` (entire directory)
  - `__init__.py` (20 bytes)
  - `urls.py` (228 bytes, single route to static template)
- URL route removed from `intelliwiz_config/urls_optimized.py:193`

**Reason**:
- Unused stub app with no implementation
- No models, views, tests, or admin
- Single route to non-existent template: `path('features/', TemplateView...)`
- Not in INSTALLED_APPS (never activated)
- Taking up namespace that might be needed later
- Violates architecture standards (apps must have tests)

**Impact**: None - app was never functional or used

**Verification**:
```bash
# Confirmed NOT in INSTALLED_APPS
grep "clientbilling" intelliwiz_config/settings/base_apps.py
# Returns: no matches

# Confirmed no imports
grep -r "clientbilling" apps/
# Returns: no matches
```

**Commit**: [TBD - add commit hash]

---

### 2025-11-11: Additional Backup Files (Final Verification)

**Files Removed:**
- `apps/peoples/forms.py.backup` (26KB)
- `apps/reports/forms.py.backup` (21KB)

**Reason**:
- Stale backup files from Phase 1-6 refactoring work
- Current code refactored into `forms/` directories
- Both apps now use modular forms structure
- Git-tracked backups violate git hygiene

**Impact**: None - code successfully refactored into directory structure

**Verification**:
```bash
# Current structure
ls apps/peoples/forms/  # Directory with multiple form files
ls apps/reports/forms/  # Directory with multiple form files
```

**Discovered During**: Final verification (Task 8) - cleanup sweep for backup files

**Commit**: [TBD - add commit hash]

---

## Guidelines for This File

### When to Add Entries

Add entries when removing:
- Entire apps or modules
- Placeholder/stub implementations
- Dead code (>50 lines)
- Deprecated APIs or features
- Git-tracked backup files (.backup, .bak, .old)

### Entry Format

```markdown
### YYYY-MM-DD: Brief Title

**Files Removed:**
- path/to/file.py (line count)

**Reason**: Why this code was removed

**Impact**: What this means for the system

**Documentation**: Link to decision records if applicable

**Commit**: Git commit hash or "TBD"
```

### What NOT to Track

- Routine refactoring (file moves, renames)
- Individual function removals
- Comment removals
- Import statement changes
- Temporary files never committed

---

## Archive (Pre-Nov 2025)

Previous removals documented in git history. See:
- `git log --grep="remove\|delete" --oneline`
- Phase 1-6 refactoring commits
