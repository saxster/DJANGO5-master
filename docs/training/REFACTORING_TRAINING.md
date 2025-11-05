# Refactoring Training Guide

**Audience:** Developers who will refactor god files into modular structures

**Prerequisites:** [Quality Standards Training](QUALITY_STANDARDS_TRAINING.md)

**Duration:** 3 hours (self-paced) + 4 hours hands-on practice

**Last Updated:** November 5, 2025

---

## Table of Contents

1. [Introduction](#introduction)
2. [When to Refactor](#when-to-refactor)
3. [The Refactoring Process](#the-refactoring-process)
4. [Choosing a Pattern](#choosing-a-pattern)
5. [Common Pitfalls](#common-pitfalls)
6. [Hands-On Lab](#hands-on-lab)
7. [Assessment](#assessment)

---

## Introduction

### What You'll Learn

By the end of this training, you will be able to:
- Identify god files that need refactoring
- Choose the appropriate refactoring pattern
- Execute refactoring safely with 100% backward compatibility
- Validate refactoring success
- Handle common challenges

### Real-World Success

**Phases 1-6 Results:**
- 16 apps refactored
- 80+ god files eliminated
- Average file size: 1,200 → 300 lines (75% reduction)
- 0 production incidents
- 100% backward compatibility maintained

---

## When to Refactor

### Automated Detection

```bash
# Find god files in your app
python scripts/detect_god_files.py --path apps/your_app

# Check specific file
python scripts/check_file_sizes.py --path apps/your_app/models.py

# Check entire codebase
python scripts/check_file_sizes.py --verbose
```

### Manual Detection Signs

**Refactor when you see:**

✅ **File exceeds limits**
- Models: >150 lines
- Settings: >200 lines
- Forms: >100 lines

✅ **Multiple responsibilities**
- "User AND Invoice AND Payment in same file"
- Can't name the file's single purpose

✅ **Merge conflict hell**
- >5 conflicts per quarter on same file
- Multiple developers editing simultaneously

✅ **Navigation difficulty**
- Scrolling >200 lines to find code
- IDE slow to index/autocomplete

✅ **Testing pain**
- Hard to write focused unit tests
- Tests cover unrelated functionality

### Don't Refactor When

❌ File <100 lines and focused
❌ Clear single responsibility
❌ App scheduled for deprecation
❌ Critical deadline approaching
❌ No test coverage (add tests first!)

---

## The Refactoring Process

### Phase 0: Preparation (30 minutes)

#### 1. Create Safety Branch

```bash
git checkout -b refactor/your-app-models
git status  # Ensure clean working directory
```

#### 2. Verify Tests Pass

```bash
python -m pytest apps/your_app/tests/ -v
```

**If tests fail, fix them first before refactoring!**

#### 3. Document Current State

```bash
# Count lines
wc -l apps/your_app/models.py

# Identify classes/functions
grep "^class \|^def " apps/your_app/models.py

# Find dependencies
grep -r "from apps.your_app.models import" . | wc -l
```

**Create analysis document:**

```markdown
## Pre-Refactoring Analysis

**File:** apps/your_app/models.py
**Size:** 655 lines
**Models:** 4 (User, Profile, Settings, AuditLog)
**External dependencies:** 23 files import from this module
**Risk:** Medium
**Estimated time:** 2 days
```

---

### Phase 1: Planning (1 hour)

#### 1. Identify Domain Boundaries

**Questions:**
- What are the distinct business domains?
- Which models are tightly coupled? (keep together)
- Which models are independent? (can separate)
- Are there shared enums? (extract first)
- Any circular dependencies? (use string references)

**Example Analysis:**

```
apps/attendance/models.py (1,200 lines)

Domains identified:
1. Core Attendance (PeopleEventlog) - 150 lines
2. Geofencing (Geofence, Tracking) - 120 lines
3. Post Management (Post, PostAssignment) - 250 lines
4. Compliance (AuditLog, Consent) - 180 lines
5. Security (FraudAlert, BehaviorProfile) - 200 lines
6. Workflow (ApprovalWorkflow) - 180 lines
7. Monitoring (AlertMonitoring) - 120 lines

Plan: Extensive split (15 modules)
```

#### 2. Choose Refactoring Pattern

| Original Size | Pattern | Modules | Example |
|---------------|---------|---------|---------|
| 400-700 lines | Minimal Split | 3-5 | Journal (4) |
| 700-1000 lines | Medium Split | 6-10 | Help Center (6) |
| 1000+ lines | Extensive Split | 10+ | Attendance (15) |

**See:** `docs/architecture/REFACTORING_PATTERNS.md` for detailed patterns

---

### Phase 2: Execution (1-3 days)

#### Step 1: Create Module Directory

```bash
cd apps/your_app
mkdir models
```

#### Step 2: Extract Enums (if present)

**Why first?** Enums are imported by multiple models.

```python
# models/enums.py
"""Shared enumerations for your_app."""

from django.db import models


class StatusEnum(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'


class TypeEnum(models.IntegerChoices):
    TYPE_A = 1, 'Type A'
    TYPE_B = 2, 'Type B'
```

**Test immediately:**

```bash
python -c "from apps.your_app.models.enums import StatusEnum; print('✅')"
```

#### Step 3: Extract Helpers (if present)

```python
# models/helpers.py
"""Helper functions for JSONField defaults."""


def default_metadata():
    """Default metadata structure."""
    return {'version': 1, 'notes': ''}
```

#### Step 4: Split Models by Domain

**Template:**

```python
# models/your_core_model.py
"""
YourCoreModel: [Brief purpose]

Related Models:
- YourRelatedModel: [relationship]

Business Rules:
- [Key rule 1]
- [Key rule 2]
"""

from django.db import models
from apps.core.models import TenantAwareModel
from .enums import StatusEnum


class YourCoreModel(TenantAwareModel):
    """[Detailed description]"""

    name = models.CharField(max_length=100, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=StatusEnum.choices,
        default=StatusEnum.ACTIVE
    )

    # Use string reference for ForeignKey to avoid circular imports
    related = models.ForeignKey(
        'your_app.YourRelatedModel',  # String reference!
        on_delete=models.CASCADE,
        related_name='core_models'
    )

    class Meta:
        db_table = 'your_app_core_model'
        verbose_name = 'Core Model'
        indexes = [
            models.Index(fields=['name', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
```

**Test each model:**

```bash
python -c "from apps.your_app.models.your_core_model import YourCoreModel; print('✅')"
```

#### Step 5: Create Backward-Compatible `__init__.py`

**This is CRITICAL!**

```python
# models/__init__.py
"""
Your App Models Package

Refactored from monolithic models.py (655 lines) on 2025-11-05.

Backward Compatibility Maintained:
    from apps.your_app.models import YourModel  # ✅ Still works

Module Organization:
- enums.py: Shared enumerations
- helpers.py: Default value factories
- core_model.py: Primary business entity
- related_model.py: Related functionality

Following CLAUDE.md:
- Rule #7: Each model < 150 lines
- Multi-tenant isolation via TenantAwareModel
"""

# Import order: enums → helpers → models
from .enums import StatusEnum, TypeEnum
from .helpers import default_metadata
from .core_model import YourCoreModel
from .related_model import YourRelatedModel

__all__ = [
    'StatusEnum',
    'TypeEnum',
    'default_metadata',
    'YourCoreModel',
    'YourRelatedModel',
]
```

**Critical checks:**

```bash
# Test backward compatibility
python -c "from apps.your_app.models import YourCoreModel; print('✅')"

# Test wildcard import
python -c "from apps.your_app.models import *; print('✅')"
```

#### Step 6: Preserve Original File

```bash
mv models.py models_deprecated.py
```

**Add deprecation header:**

```python
# models_deprecated.py
"""
⛔ DEPRECATED: Refactored into models/ package on 2025-11-05.

DO NOT USE THIS FILE. Use: from apps.your_app.models import YourModel

Kept for:
1. Emergency rollback
2. Reference during transition
3. Will be deleted after 60 days

Planned deletion: 2026-01-05
"""
# ... original content
```

---

### Phase 3: Validation (1 day)

#### Automated Checks

```bash
# 1. Django checks
python manage.py check

# 2. Migrations (should be no-op)
python manage.py makemigrations your_app --dry-run

# 3. File size validation
python scripts/check_file_sizes.py --path apps/your_app --verbose

# 4. App tests
python -m pytest apps/your_app/tests/ -v

# 5. Full test suite
python -m pytest --tb=short -v

# 6. Import validation
python -c "from apps.your_app.models import *; print('✅ All imports work')"
```

#### Manual Smoke Tests

1. **Django Admin**
   ```bash
   python manage.py runserver
   # Visit http://localhost:8000/admin/your_app/
   # Verify all models appear
   ```

2. **API Endpoints**
   ```bash
   curl http://localhost:8000/api/v1/your-app/
   ```

3. **Celery Tasks** (if applicable)
   ```python
   from apps.your_app.tasks import your_task
   your_task.delay()
   ```

---

## Choosing a Pattern

### Pattern 1: Minimal Split (400-700 lines)

**When:** Clear domain separation, limited interdependencies

**Structure:**

```
models/
├── __init__.py
├── enums.py       # Shared enums
├── entry.py       # Core model
├── media.py       # Media/attachments
└── config.py      # Settings/config
```

**Example:** Journal models (698 → 4 modules)

**Time:** 1-2 days

---

### Pattern 2: Medium Split (700-1000 lines)

**When:** Multiple business domains, some shared dependencies

**Structure:**

```
models/
├── __init__.py
├── enums.py
├── helpers.py
├── core.py
├── related_a.py
├── related_b.py
├── audit.py
└── config.py
```

**Example:** Help Center (554 → 6 modules), Work Order (655 → 7 modules)

**Time:** 2-3 days

---

### Pattern 3: Extensive Split (1000+ lines)

**When:** God file with many distinct domains

**Structure:**

```
models/
├── __init__.py
├── [10-15 focused modules, one per domain]
└── test_utilities.py  # If test models exist
```

**Example:** Attendance (1,200 → 15 modules), Face Recognition (669 → 9 modules)

**Time:** 3-5 days

---

## Common Pitfalls

### Pitfall 1: Circular Imports

**Problem:**

```python
# models/model_a.py
from .model_b import ModelB  # ❌ Circular!

class ModelA(models.Model):
    related_b = models.ForeignKey(ModelB, ...)
```

**Solution: String References**

```python
# models/model_a.py
from django.db import models  # No import of ModelB!

class ModelA(models.Model):
    related_b = models.ForeignKey(
        'your_app.ModelB',  # ✅ String reference
        on_delete=models.CASCADE
    )
```

---

### Pitfall 2: Missing Exports

**Problem:**

```python
# models/__init__.py
from .core import CoreModel
# Forgot to add to __all__!

# In other file:
from apps.your_app.models import CoreModel  # ImportError!
```

**Solution:**

```python
# models/__init__.py
from .core import CoreModel

__all__ = [
    'CoreModel',  # MUST be in __all__!
]
```

---

### Pitfall 3: Over-Splitting

**Problem:**

```
models/
├── user_name.py      # 20 lines - too granular!
├── user_email.py     # 15 lines
├── user_profile.py   # 25 lines
└── user_settings.py  # 18 lines
```

**Solution: Cohesive Modules**

```
models/
├── user.py           # 80 lines - cohesive
└── user_settings.py  # 45 lines - separate concern
```

**Guideline:** Don't split below 50 lines without strong domain boundary.

---

### Pitfall 4: Breaking Tests

**Problem:** Tests import from specific module path

```python
# Test was:
from apps.your_app.models import YourModel  # ✅ Works

# But some tests had:
from apps.your_app.models.old_location import YourModel  # ❌ Breaks
```

**Solution:** Always use package-level imports in tests:

```python
from apps.your_app.models import YourModel  # ✅ Correct
```

---

## Hands-On Lab

### Lab 1: Minimal Split (2 hours)

**Scenario:** You have `apps/blog/models.py` (520 lines) with:
- Post model (180 lines)
- Comment model (120 lines)
- Tag model (80 lines)
- Category model (90 lines)
- PostStatus enum (20 lines)
- Helper functions (30 lines)

**Task:** Split into 5-6 modules following Minimal Split pattern

**Steps:**

1. Create `apps/blog/models/` directory
2. Extract enums → `enums.py`
3. Extract helpers → `helpers.py`
4. Split models: `post.py`, `comment.py`, `tag.py`, `category.py`
5. Create `__init__.py` with all exports
6. Preserve `models_deprecated.py`
7. Test: `python -m pytest apps/blog/tests/`
8. Validate: `python scripts/check_file_sizes.py --path apps/blog`

**Success Criteria:**
- All files < 150 lines
- All tests passing
- Imports work: `from apps.blog.models import Post`

---

### Lab 2: Handle Circular Imports (1 hour)

**Scenario:** Two models with mutual ForeignKeys

```python
class Author(models.Model):
    favorite_post = models.ForeignKey(Post, ...)  # Circular!

class Post(models.Model):
    author = models.ForeignKey(Author, ...)  # Circular!
```

**Task:** Refactor to avoid circular imports

**Solution:**

```python
# models/author.py
class Author(models.Model):
    favorite_post = models.ForeignKey(
        'blog.Post',  # String reference
        null=True,
        on_delete=models.SET_NULL
    )

# models/post.py
class Post(models.Model):
    author = models.ForeignKey(
        'blog.Author',  # String reference
        on_delete=models.CASCADE
    )
```

---

### Lab 3: Real Refactoring (4 hours)

**Task:** Pick a real god file from the codebase and refactor it

```bash
# 1. Find god files
python scripts/detect_god_files.py --path apps/

# 2. Pick one >200 lines
# 3. Follow refactoring process (Phase 0-3)
# 4. Create completion report
# 5. Submit PR for review
```

**Deliverables:**
- Refactored modules (all < 150 lines)
- All tests passing
- `YOUR_APP_REFACTORING_COMPLETE.md` report
- PR description with before/after metrics

---

## Assessment

### Knowledge Check

1. **What are the 3 refactoring patterns?**
   - Minimal (3-5), Medium (6-10), Extensive (10+)

2. **What should you extract first?**
   - Enums (imported by multiple models)

3. **How do you avoid circular imports?**
   - Use string references for ForeignKey: `'app.Model'`

4. **What goes in `__all__`?**
   - All models, enums, and helpers you want to export

5. **What do you do with the original file?**
   - Preserve as `models_deprecated.py` with deprecation notice

### Practical Assessment

**Complete a real refactoring:**

1. Find a god file: `python scripts/detect_god_files.py --path apps/`
2. Complete Phases 0-3 (preparation, planning, execution, validation)
3. Create completion report
4. Pass code review

**Success Criteria:**
- [ ] All files < 150 lines
- [ ] 100% backward compatibility
- [ ] All tests passing
- [ ] No import errors
- [ ] Completion report created
- [ ] Code review approved

---

## Resources

### Documentation

- **[REFACTORING_PLAYBOOK.md](../architecture/REFACTORING_PLAYBOOK.md)** - Complete reference
- **[REFACTORING_PATTERNS.md](../architecture/REFACTORING_PATTERNS.md)** - Quick patterns
- **[ADR 001](../architecture/adr/001-file-size-limits.md)** - File size limits

### Example Refactorings

- `ATTENDANCE_MODELS_REFACTORING_COMPLETE.md` - Extensive split (15 modules)
- `FACE_RECOGNITION_REFACTORING_COMPLETE.md` - Medium split (9 modules)
- `JOURNAL_MODELS_REFACTORING_COMPLETE.md` - Minimal split (4 modules)

### Tools

```bash
python scripts/detect_god_files.py --path apps/your_app
python scripts/check_file_sizes.py --path apps/your_app --verbose
python scripts/verify_attendance_models_refactoring.py  # Example verification
```

---

## Next Steps

1. Complete [Service Layer Training](SERVICE_LAYER_TRAINING.md)
2. Complete [Testing Training](TESTING_TRAINING.md)
3. Apply refactoring to a real god file
4. Help team members with their refactorings
5. Update this guide with lessons learned

---

**Training Complete! 🎓**

You can now safely refactor god files into maintainable modules. Remember:
- Split by domain, not lines
- Test relentlessly
- Maintain backward compatibility
- Document everything

**Questions?** Review REFACTORING_PLAYBOOK.md or ask in #engineering

---

**Last Updated:** November 5, 2025

**Maintainer:** Development Team
