# God File Refactoring Patterns

**Purpose:** Standard patterns for splitting large Python files into maintainable modules

**Status:** Active - Use this guide for all refactoring work

**Last Updated:** 2025-11-04

---

## Table of Contents

- [Overview](#overview)
- [When to Refactor](#when-to-refactor)
- [Successful Refactoring Examples](#successful-refactoring-examples)
- [Standard Refactoring Pattern](#standard-refactoring-pattern)
- [Pattern Variations](#pattern-variations)
- [Common Pitfalls](#common-pitfalls)
- [Validation Checklist](#validation-checklist)

---

## Overview

This document codifies the refactoring patterns successfully used to split "god files" (monolithic Python modules) into maintainable, focused modules following SOLID principles.

**Architecture Limits (from `.claude/rules.md`):**

| File Type | Line Limit | Rule Reference |
|-----------|------------|----------------|
| Settings files | < 200 lines | Rule #6 |
| Model files | < 150 lines | Rule #7 |
| View methods | < 30 lines | Rule #8 |
| Form files | < 100 lines | Rule #13 |
| Utility functions | < 50 lines | General guideline |

---

## When to Refactor

### File Size Triggers

Run the validation script to identify violations:

```bash
python scripts/check_file_sizes.py --path apps/your_app --verbose
```

Refactor when:
- ✅ File exceeds line limits by >20%
- ✅ File has >3 distinct responsibilities
- ✅ File causes merge conflicts frequently
- ✅ Tests are difficult to write/maintain
- ✅ New features require scrolling >200 lines

### Complexity Triggers

Refactor when encountering:
- Multiple unrelated model classes in one file
- Business logic mixed with data definitions
- Circular import workarounds
- Difficulty naming a single responsibility
- High cyclomatic complexity (>10)

---

## Successful Refactoring Examples

### Case Study 1: Attendance Models (1,200+ lines → 15 focused modules)

**Before:**
```
apps/attendance/models.py  (1,200+ lines)
```

**After:**
```
apps/attendance/
├── models/
│   ├── __init__.py                    # Backward-compatible exports
│   ├── people_eventlog.py             # Core attendance tracking
│   ├── geofence.py                    # Location boundaries
│   ├── tracking.py                    # GPS tracking
│   ├── test_geo.py                    # Test utilities
│   ├── audit_log.py                   # Audit & compliance
│   ├── consent.py                     # Consent management
│   ├── post.py                        # Post definitions
│   ├── post_assignment.py             # Post assignments
│   ├── post_order_acknowledgement.py  # Order acknowledgements
│   ├── approval_workflow.py           # Approval processes
│   ├── alert_monitoring.py            # Alert rules & monitoring
│   ├── fraud_alert.py                 # Fraud detection
│   ├── user_behavior_profile.py       # Behavioral analytics
│   ├── attendance_photo.py            # Photo captures
│   └── sync_conflict.py               # Conflict resolution
└── models_deprecated.py               # Original file (safety)
```

**Key Pattern:**
1. Split by domain/responsibility
2. Each file < 150 lines
3. Backward-compatible imports in `__init__.py`
4. Keep original file as `*_deprecated.py` for safety

---

### Case Study 2: Face Recognition Models (669 lines → 8 focused modules)

**Before:**
```
apps/face_recognition/models.py  (669 lines)
```

**After:**
```
apps/face_recognition/
├── models/
│   ├── __init__.py                    # Clean exports with __all__
│   ├── enums.py                       # Shared enumerations
│   ├── face_recognition_model.py      # Core model
│   ├── face_embedding.py              # Vector embeddings
│   ├── face_verification_log.py       # Verification logging
│   ├── anti_spoofing_model.py         # Anti-spoofing
│   ├── face_recognition_config.py     # Configuration
│   ├── face_quality_metrics.py        # Quality metrics
│   ├── biometric_consent_log.py       # Consent tracking
│   └── biometric_audit_log.py         # Audit trail
└── models_deprecated.py               # Safety backup
```

**Key Pattern:**
1. Extract enums first (shared across models)
2. Group by technical domain (embeddings, verification, audit)
3. Each file focuses on single model class
4. Comprehensive `__all__` exports

---

### Case Study 3: Journal Models (698 lines → 4 focused modules)

**Before:**
```
apps/journal/models.py  (698 lines)
```

**After:**
```
apps/journal/
├── models/
│   ├── __init__.py           # Backward-compatible exports
│   ├── enums.py              # JournalPrivacyScope, JournalEntryType, JournalSyncStatus
│   ├── entry.py              # JournalEntry (core model)
│   ├── media.py              # JournalMediaAttachment + upload functions
│   └── privacy.py            # JournalPrivacySettings
└── models_deprecated.py      # Original backup
```

**Key Pattern:**
1. Minimal splitting (4 modules vs. 15+ in attendance)
2. Clear separation: enums, core entry, media, privacy
3. Upload helper functions in same file as model
4. All models < 150 lines

---

### Case Study 4: Help Center Models (554 lines → 6 focused modules)

**Before:**
```
apps/help_center/models.py  (554 lines)
```

**After:**
```
apps/help_center/
├── models/
│   ├── __init__.py                # Documentation + exports
│   ├── tag.py                     # HelpTag (simple tagging)
│   ├── category.py                # HelpCategory (hierarchical)
│   ├── article.py                 # HelpArticle (FTS + pgvector)
│   ├── search_history.py          # HelpSearchHistory (analytics)
│   ├── interaction.py             # HelpArticleInteraction (engagement)
│   └── ticket_correlation.py      # HelpTicketCorrelation (effectiveness)
└── models_deprecated.py           # Safety backup
```

**Key Pattern:**
1. One model per file
2. Clear business domain separation
3. Each file includes related signals/helpers
4. Comprehensive docstring in `__init__.py`

---

## Standard Refactoring Pattern

### The 7-Step Process

This is the battle-tested pattern used for attendance, face_recognition, help_center, journal, issue_tracker, and work_order_management refactorings.

#### Step 1: Analyze Current Structure

```bash
# Check file size and complexity
wc -l apps/your_app/models.py
python scripts/detect_god_files.py --path apps/your_app

# Identify distinct responsibilities
grep "^class " apps/your_app/models.py
```

**Questions to ask:**
- What are the distinct business domains?
- Which models are related/coupled?
- Are there shared enums or constants?
- Which models have complex relationships?

#### Step 2: Create Module Directory

```bash
cd apps/your_app
mkdir models
```

#### Step 3: Extract and Split by Domain

**Start with enums/constants if they exist:**

```python
# models/enums.py
from django.db import models

class YourStatusEnum(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'

class YourTypeEnum(models.IntegerChoices):
    TYPE_A = 1, 'Type A'
    TYPE_B = 2, 'Type B'
```

**Create focused model files:**

```python
# models/your_core_model.py
from django.db import models
from apps.core.models import TenantAwareModel

class YourCoreModel(TenantAwareModel):
    """
    Core model docstring.

    Related: See YourRelatedModel for additional context
    """
    name = models.CharField(max_length=100)
    # ... fields (aim for < 150 lines total)

    class Meta:
        db_table = 'your_core_model'
        verbose_name = 'Your Core Model'
        indexes = [...]  # Query optimization
```

#### Step 4: Create Backward-Compatible `__init__.py`

This is **critical** for maintaining existing imports throughout the codebase.

```python
# models/__init__.py
"""
Your App Models Package

Refactored from monolithic models.py (XXX lines) on YYYY-MM-DD.

Backward compatibility maintained - all imports work unchanged.

Models:
- YourCoreModel: Core business logic
- YourRelatedModel: Related functionality
- YourAuditModel: Audit trail

Following CLAUDE.md:
- Rule #7: Each model < 150 lines
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes
- Multi-tenant isolation via TenantAwareModel
"""

# Import order: enums first, then models by dependency
from .enums import YourStatusEnum, YourTypeEnum
from .your_core_model import YourCoreModel
from .your_related_model import YourRelatedModel
from .your_audit_model import YourAuditModel

__all__ = [
    # Enums
    'YourStatusEnum',
    'YourTypeEnum',
    # Models
    'YourCoreModel',
    'YourRelatedModel',
    'YourAuditModel',
]
```

**Key requirements:**
- ✅ Docstring explaining refactoring and date
- ✅ List all models with brief descriptions
- ✅ Reference CLAUDE.md rules followed
- ✅ Explicit `__all__` for wildcard import control
- ✅ Import order: enums → models by dependency

#### Step 5: Create Safety Backup

```bash
# Rename original file for safety
mv models.py models_deprecated.py
```

**Add deprecation warning to top of file:**

```python
# models_deprecated.py
"""
DEPRECATED: This file has been refactored into models/ directory.

DO NOT USE THIS FILE. Use:
    from apps.your_app.models import YourModel

This file kept for:
1. Emergency rollback capability
2. Reference during transition period
3. Will be deleted after 2 release cycles

Refactored: YYYY-MM-DD
Planned deletion: YYYY-MM-DD + 60 days
"""
# ... original content
```

#### Step 6: Update Internal Imports

Find and update all internal imports in the app:

```bash
# Find all imports of the refactored models
cd apps/your_app
grep -r "from .models import" .
grep -r "from apps.your_app.models import" .
```

**Update imports (usually these don't need changes due to backward compatibility):**

```python
# These still work due to __init__.py exports:
from apps.your_app.models import YourModel  # ✅ Still works
from .models import YourModel                # ✅ Still works

# If you need to import from specific module (rare):
from apps.your_app.models.your_core_model import YourModel  # ✅ Explicit
```

#### Step 7: Verify and Test

```bash
# Run migrations (should be no-op if no schema changes)
python manage.py makemigrations your_app
python manage.py migrate

# Run tests
python -m pytest apps/your_app/tests/ -v

# Check for import errors
python manage.py check

# Validate file sizes
python scripts/check_file_sizes.py --path apps/your_app --verbose

# Run full test suite
python -m pytest --tb=short -v
```

---

## Pattern Variations

### Variation 1: Minimal Split (3-5 modules)

**Use when:**
- Original file is 400-700 lines
- Clear domain separation exists
- Limited interdependencies

**Example:** Journal models (4 modules)

```
models/
├── __init__.py
├── enums.py       # Shared enumerations
├── entry.py       # Core model
├── media.py       # Media attachments
└── privacy.py     # Privacy settings
```

### Variation 2: Medium Split (6-10 modules)

**Use when:**
- Original file is 700-1000 lines
- Multiple business domains
- Some shared utilities

**Example:** Help Center models (6 modules)

```
models/
├── __init__.py
├── tag.py
├── category.py
├── article.py
├── search_history.py
├── interaction.py
└── ticket_correlation.py
```

### Variation 3: Extensive Split (10+ modules)

**Use when:**
- Original file is 1000+ lines (god file)
- Many distinct business domains
- Complex relationships

**Example:** Attendance models (15 modules)

```
models/
├── __init__.py
├── people_eventlog.py
├── geofence.py
├── tracking.py
├── test_geo.py
├── audit_log.py
├── consent.py
├── post.py
├── post_assignment.py
├── post_order_acknowledgement.py
├── approval_workflow.py
├── alert_monitoring.py
├── fraud_alert.py
├── user_behavior_profile.py
├── attendance_photo.py
└── sync_conflict.py
```

### Variation 4: Hierarchical Split (Subdirectories)

**Use when:**
- Multiple nested concerns
- Large app with distinct modules

**Example:** NOC security intelligence

```
apps/noc/
├── models/
│   ├── __init__.py
│   ├── noc_event_log.py
│   └── dashboard_config.py
└── security_intelligence/
    ├── models/
    │   ├── __init__.py
    │   ├── behavioral_profile.py
    │   ├── finding_runbook.py
    │   └── ml_training_dataset.py
    └── ivr/
        └── models/
            ├── __init__.py
            ├── ivr_provider_config.py
            ├── voice_script_template.py
            └── ivr_response.py
```

---

## Common Pitfalls

### Pitfall 1: Breaking Backward Compatibility

❌ **WRONG:**
```python
# __init__.py - Missing exports
from .your_model import YourModel
# Other code that does "from app.models import OtherModel" breaks!
```

✅ **CORRECT:**
```python
# __init__.py - Export everything
from .your_model import YourModel
from .other_model import OtherModel

__all__ = ['YourModel', 'OtherModel']
```

### Pitfall 2: Circular Import Dependencies

❌ **WRONG:**
```python
# models/model_a.py
from .model_b import ModelB  # Circular!

class ModelA(models.Model):
    related = models.ForeignKey(ModelB)

# models/model_b.py
from .model_a import ModelA  # Circular!

class ModelB(models.Model):
    related = models.ForeignKey(ModelA)
```

✅ **CORRECT:**
```python
# models/model_a.py
from django.db import models

class ModelA(models.Model):
    related = models.ForeignKey('your_app.ModelB')  # String reference!

# models/model_b.py
from django.db import models

class ModelB(models.Model):
    related = models.ForeignKey('your_app.ModelA')  # String reference!
```

### Pitfall 3: Forgetting Migration Generation

Even if no schema changes, Django may generate migrations for moved models.

```bash
# Always run after refactoring
python manage.py makemigrations your_app

# If you see unwanted migrations, use --dry-run to check
python manage.py makemigrations --dry-run
```

### Pitfall 4: Not Testing External Imports

Other apps may import your models:

```bash
# Search entire codebase for imports
grep -r "from apps.your_app.models import" .
grep -r "from apps.your_app import models" .
```

### Pitfall 5: Incomplete `__all__` Declarations

Missing items from `__all__` breaks wildcard imports:

```python
# models/some_model.py
class SomeModel(models.Model):
    pass

def helper_function():  # Helper functions too!
    pass

# models/__init__.py
__all__ = [
    'SomeModel',
    # 'helper_function',  # ❌ Missing! Breaks imports
]
```

### Pitfall 6: Over-Splitting

❌ **WRONG:**
```
models/
├── user_name.py       # 20 lines - too granular
├── user_email.py      # 15 lines - too granular
├── user_profile.py    # 25 lines - too granular
└── user_settings.py   # 18 lines - too granular
```

✅ **CORRECT:**
```
models/
├── user.py            # 80 lines - cohesive user model
└── user_settings.py   # 45 lines - separate concerns
```

**Guideline:** Don't split below 50 lines unless there's a strong domain boundary.

---

## Validation Checklist

Use this checklist after every refactoring:

### Pre-Refactoring

- [ ] File size exceeds limits (run `check_file_sizes.py`)
- [ ] Identified distinct responsibilities
- [ ] Documented current import usage
- [ ] Created backup branch: `git checkout -b refactor/your-app-models`
- [ ] All tests passing before refactoring

### During Refactoring

- [ ] Created `models/` directory
- [ ] Extracted enums/constants first
- [ ] Split models by domain (not arbitrary line count)
- [ ] Each file < 150 lines
- [ ] Created comprehensive `__init__.py` with `__all__`
- [ ] Renamed original file to `*_deprecated.py`
- [ ] Added deprecation docstring to old file
- [ ] Used string references for ForeignKey to avoid circular imports

### Post-Refactoring

- [ ] `python manage.py check` passes
- [ ] `python manage.py makemigrations` (no unwanted migrations)
- [ ] `python manage.py migrate` succeeds
- [ ] All tests pass: `python -m pytest apps/your_app/tests/ -v`
- [ ] File size validation: `python scripts/check_file_sizes.py --path apps/your_app`
- [ ] No import errors in dependent apps
- [ ] Documentation updated (docstrings, this file)
- [ ] Committed with descriptive message

### Verification Commands

```bash
# 1. Check for errors
python manage.py check

# 2. Validate migrations
python manage.py makemigrations --dry-run

# 3. Run tests
python -m pytest apps/your_app/tests/ -v --tb=short

# 4. Check file sizes
python scripts/check_file_sizes.py --path apps/your_app --verbose

# 5. Search for old imports (should use new structure)
grep -r "from apps.your_app.models_deprecated import" .

# 6. Verify backward compatibility
python -c "from apps.your_app.models import YourModel; print('✅ Import works')"

# 7. Full test suite (if critical app)
python -m pytest --cov=apps.your_app --cov-report=term-missing
```

---

## Emergency Rollback

If refactoring causes critical issues:

```bash
# Restore original file
mv models_deprecated.py models.py

# Remove new directory
rm -rf models/

# Rollback migrations (if any)
python manage.py migrate your_app <previous_migration_number>

# Verify
python manage.py check
python -m pytest apps/your_app/tests/ -v
```

---

## Related Documentation

- [.claude/rules.md](../../.claude/rules.md) - Architecture limits and rules
- [GOD_FILE_REFACTORING_GUIDE.md](GOD_FILE_REFACTORING_GUIDE.md) - Historical refactoring guide
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Overall system architecture
- [docs/architecture/adr/](adr/) - Architecture Decision Records

---

## Refactoring History

| Date | App | Lines Before | Modules After | Engineer |
|------|-----|--------------|---------------|----------|
| 2025-11-04 | work_order_management | 800+ | 12 | Agent 3 |
| 2025-11-04 | issue_tracker | 600+ | 10 | Agent 3 |
| 2025-11-04 | journal | 698 | 4 | Agent 3 |
| 2025-11-04 | help_center | 554 | 6 | Agent 2 |
| 2025-11-04 | face_recognition | 669 | 8 | Agent 2 |
| 2025-11-04 | attendance | 1,200+ | 15 | Agent 1 |

---

**Last Updated:** 2025-11-04
**Maintainer:** Development Team
**Review Cycle:** Update after each major refactoring
