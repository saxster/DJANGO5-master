# Refactoring Playbook: The Complete Guide

**Purpose:** Comprehensive, battle-tested guide for refactoring god files into maintainable modules

**Status:** Active - Mandatory reading for all refactoring work

**Based on:** Phase 1-6 refactoring experiences (16 apps, 80+ god files eliminated)

**Last Updated:** November 5, 2025

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [When to Refactor](#when-to-refactor)
3. [The Complete Refactoring Process](#the-complete-refactoring-process)
4. [Pattern Library](#pattern-library)
5. [Real-World Case Studies](#real-world-case-studies)
6. [Common Challenges and Solutions](#common-challenges-and-solutions)
7. [Quality Assurance](#quality-assurance)
8. [Emergency Procedures](#emergency-procedures)

---

## Executive Summary

This playbook consolidates lessons from Phases 1-6 of our god file refactoring initiative, where we successfully split 80+ monolithic files across 16 Django apps while maintaining 100% backward compatibility.

### Key Principles

1. **Split by domain, not lines** - Respect business boundaries
2. **Backward compatibility is non-negotiable** - All existing imports must work
3. **Safety first** - Always preserve the original file
4. **Test relentlessly** - Verify at every step
5. **Document everything** - Future maintainers will thank you

### Success Metrics (Phases 1-6)

| Metric | Achievement |
|--------|-------------|
| Apps Refactored | 16 apps |
| God Files Eliminated | 80+ files |
| Average File Size Reduction | 75% (1,200 → 300 lines avg) |
| Backward Compatibility | 100% maintained |
| Test Failures from Refactoring | 0 (after fixes) |
| Production Incidents | 0 |

---

## When to Refactor

### File Size Triggers

Run the automated detection tool:

```bash
# Check entire codebase
python scripts/check_file_sizes.py --verbose

# Check specific app
python scripts/check_file_sizes.py --path apps/your_app --verbose

# Find god file candidates
python scripts/detect_god_files.py --path apps/your_app
```

**Refactor when:**

| Condition | Threshold | Action Required |
|-----------|-----------|-----------------|
| File exceeds architecture limit | >150 lines (models), >200 lines (settings) | Mandatory refactoring |
| File has multiple concerns | >3 distinct domains | High priority refactoring |
| Merge conflicts frequent | >5 per quarter | Recommended refactoring |
| New features require scrolling | >200 lines to find code | Consider refactoring |

### Complexity Triggers

Beyond file size, refactor when you see:

- ✅ **Multiple unrelated model classes** (e.g., User + Invoice in same file)
- ✅ **Business logic mixed with data definitions** (e.g., validation in model file)
- ✅ **Circular import workarounds** (`import` inside function to avoid cycles)
- ✅ **Difficulty naming the file's single responsibility** (if you can't, it has multiple!)
- ✅ **High cyclomatic complexity** (>10 per function)

### Don't Refactor When

- ❌ File is <100 lines and focused
- ❌ File has clear single responsibility
- ❌ Refactoring would create artificial splits
- ❌ App is scheduled for deprecation/rewrite
- ❌ Critical production deadline approaching

---

## The Complete Refactoring Process

### Phase 0: Pre-Refactoring (1 day)

#### Step 0.1: Create Safety Branch

```bash
# Create feature branch
git checkout -b refactor/your-app-models

# Ensure clean working directory
git status

# Ensure tests pass before refactoring
python -m pytest apps/your_app/tests/ -v
```

#### Step 0.2: Analyze Current Structure

```bash
# Count lines
wc -l apps/your_app/models.py

# Identify classes
grep "^class " apps/your_app/models.py

# Find dependencies
grep -r "from apps.your_app.models import" . | grep -v __pycache__
```

**Document findings:**

```markdown
# Pre-Refactoring Analysis: your_app.models

## Current State
- **File size:** XXX lines
- **Model count:** X models
- **External imports:** Y files import from this module

## Distinct Responsibilities Identified
1. Core domain models (User, Profile)
2. Audit/logging models (AuditLog)
3. Helper utilities (JSONField defaults)
4. Enumerations (Status choices)

## Refactoring Strategy
- Split into X modules
- Estimated time: Y days
- Risk level: Medium (Z external dependencies)
```

#### Step 0.3: Validate Prerequisites

**Checklist:**

- [ ] All tests passing
- [ ] No pending migrations
- [ ] Clean git status
- [ ] Team notified of refactoring
- [ ] Feature freeze on this app (if critical)
- [ ] Backup plan documented

---

### Phase 1: Structure Planning (2 hours)

#### Step 1.1: Identify Domain Boundaries

**Questions to ask:**

1. What are the distinct business domains? (e.g., authentication, audit, configuration)
2. Which models are tightly coupled? (keep together)
3. Which models are independent? (can be separated)
4. Are there shared enums or constants? (extract first)
5. Are there circular dependencies? (needs string references)

**Planning template:**

```
apps/your_app/models/
├── __init__.py              # Exports (always required)
├── enums.py                 # Shared enumerations (if >3 enums)
├── helpers.py               # Default factories, utilities
├── core_model.py            # Primary business entity
├── related_model.py         # Related to core model
├── audit_model.py           # Audit/logging concerns
└── config_model.py          # Configuration/settings
```

#### Step 1.2: Choose Refactoring Pattern

Based on original file size:

| Original Size | Pattern | Example | Modules |
|---------------|---------|---------|---------|
| 400-700 lines | **Minimal Split** | Journal (698→4) | 3-5 modules |
| 700-1000 lines | **Medium Split** | Help Center (554→6) | 6-10 modules |
| 1000+ lines | **Extensive Split** | Attendance (1200→15) | 10+ modules |

**Refer to:** `docs/architecture/REFACTORING_PATTERNS.md` for detailed patterns

---

### Phase 2: Execution (1-3 days)

#### Step 2.1: Create Module Directory

```bash
cd apps/your_app
mkdir models

# Verify creation
ls -la
```

#### Step 2.2: Extract Shared Enumerations (if present)

**Why first?** Enums are imported by multiple models, so extract them before models.

```python
# models/enums.py
"""
Shared enumerations for your_app.

Centralized choice fields for consistency across models.
"""

from django.db import models


class YourStatusEnum(models.TextChoices):
    """Status choices for YourModel."""
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    PENDING = 'pending', 'Pending'


class YourTypeEnum(models.IntegerChoices):
    """Type choices for YourModel."""
    TYPE_A = 1, 'Type A'
    TYPE_B = 2, 'Type B'
```

**Test immediately:**

```bash
python -c "from apps.your_app.models.enums import YourStatusEnum; print('✅ Enums work')"
```

#### Step 2.3: Extract Helper Functions (if present)

```python
# models/helpers.py
"""
Helper functions for JSONField defaults and utilities.

These provide default values and utility functions used across models.
"""


def default_metadata():
    """Default metadata structure for JSONField."""
    return {
        'created_by': None,
        'notes': '',
        'version': 1
    }


def default_geojson():
    """Default GeoJSON structure."""
    return {
        'type': 'Point',
        'coordinates': [0.0, 0.0]
    }
```

#### Step 2.4: Split Models by Domain

**Template for each model file:**

```python
# models/your_core_model.py
"""
YourCoreModel: [Brief description of purpose]

Related Models:
- YourRelatedModel: [relationship]
- YourAuditModel: [audit trail]

Business Rules:
- [Key rule 1]
- [Key rule 2]
"""

from django.db import models
from apps.core.models import TenantAwareModel
from .enums import YourStatusEnum  # Local import
from .helpers import default_metadata


class YourCoreModel(TenantAwareModel):
    """
    [Detailed model description]

    Attributes:
        name: Human-readable name
        status: Current status (see YourStatusEnum)
        metadata: JSONField with additional data

    Related:
        See YourRelatedModel for [relationship description]
    """

    # Fields
    name = models.CharField(max_length=100, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=YourStatusEnum.choices,
        default=YourStatusEnum.ACTIVE
    )
    metadata = models.JSONField(default=default_metadata, blank=True)

    # Foreign keys (use string reference if circular)
    related = models.ForeignKey(
        'your_app.YourRelatedModel',  # String reference!
        on_delete=models.CASCADE,
        related_name='core_models'
    )

    class Meta:
        db_table = 'your_app_core_model'
        verbose_name = 'Core Model'
        verbose_name_plural = 'Core Models'
        indexes = [
            models.Index(fields=['name', 'status']),  # Composite index
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    # Business logic methods (if needed)
    def activate(self):
        """Activate this model instance."""
        self.status = YourStatusEnum.ACTIVE
        self.save(update_fields=['status', 'updated_at'])
```

**Test each model immediately:**

```bash
python -c "from apps.your_app.models.your_core_model import YourCoreModel; print('✅ Model imports')"
```

#### Step 2.5: Create Backward-Compatible `__init__.py`

**This is CRITICAL for maintaining existing imports!**

```python
# models/__init__.py
"""
Your App Models Package

Refactored from monolithic models.py (XXX lines) on YYYY-MM-DD.

**Backward Compatibility Maintained** - All imports work unchanged:
    from apps.your_app.models import YourModel  # ✅ Still works

**Module Organization:**

Core Models:
    - YourCoreModel: Primary business entity
    - YourRelatedModel: Related functionality

Supporting Models:
    - YourAuditModel: Audit trail and compliance
    - YourConfigModel: Configuration settings

Enumerations:
    - YourStatusEnum: Status choices
    - YourTypeEnum: Type choices

**Following CLAUDE.md Rules:**
- Rule #7: Each model < 150 lines
- Rule #11: Specific exception handling
- Rule #12: Query optimization with indexes
- Multi-tenant isolation via TenantAwareModel

**Refactoring Details:**
- Original file: models.py (XXX lines)
- Split into: X focused modules
- Total lines: YYY lines (with documentation)
- Models per file: 1-2 (single responsibility)

**Related Documentation:**
- See: docs/architecture/REFACTORING_PATTERNS.md
- See: docs/architecture/REFACTORING_PLAYBOOK.md (this guide)
"""

# Import order: enums → helpers → models (by dependency)

# Enumerations (shared across models)
from .enums import (
    YourStatusEnum,
    YourTypeEnum,
)

# Helper functions
from .helpers import (
    default_metadata,
    default_geojson,
)

# Models (alphabetical order)
from .your_audit_model import YourAuditModel
from .your_config_model import YourConfigModel
from .your_core_model import YourCoreModel
from .your_related_model import YourRelatedModel

# Explicit exports (controls wildcard imports)
__all__ = [
    # Enums
    'YourStatusEnum',
    'YourTypeEnum',
    # Helpers
    'default_metadata',
    'default_geojson',
    # Models
    'YourAuditModel',
    'YourConfigModel',
    'YourCoreModel',
    'YourRelatedModel',
]
```

**Critical checks:**

```bash
# Test backward compatibility
python -c "from apps.your_app.models import YourCoreModel; print('✅ Backward compatible')"

# Test wildcard import
python -c "from apps.your_app.models import *; print('✅ Wildcard works')"

# Test __all__ completeness
python -c "from apps.your_app import models; print(dir(models))"
```

#### Step 2.6: Preserve Original File

```bash
# Rename original file for safety
mv models.py models_deprecated.py
```

**Add deprecation header:**

```python
# models_deprecated.py
"""
⛔ DEPRECATED: This file has been refactored into models/ package.

DO NOT USE THIS FILE FOR NEW CODE.

**Use instead:**
    from apps.your_app.models import YourModel

**This file is kept for:**
1. Emergency rollback capability
2. Reference during transition period (60 days)
3. Comparison during testing

**Refactoring Details:**
- Refactored: YYYY-MM-DD
- New location: apps/your_app/models/ (package)
- Modules created: X focused files
- Backward compatibility: 100% maintained

**Planned Deletion:** YYYY-MM-DD + 60 days

**Related Documentation:**
- Refactoring report: <link to refactoring completion doc>
- ADR: docs/architecture/adr/001-file-size-limits.md
"""

# Original content below...
```

---

### Phase 3: Validation (1 day)

#### Step 3.1: Run Django Checks

```bash
# Check for configuration errors
python manage.py check

# Check for model issues
python manage.py check --deploy
```

**Expected output:** `System check identified no issues (0 silenced).`

#### Step 3.2: Generate and Review Migrations

```bash
# Generate migrations (should be no-op if no schema changes)
python manage.py makemigrations your_app --dry-run

# If migrations generated, review carefully
python manage.py makemigrations your_app
```

**Expected:** No migrations if only refactoring structure.

**If migrations appear:**
- Review carefully - ensure they're expected
- Test migration on dev database first
- Document why migrations were needed

```bash
# Apply migrations
python manage.py migrate your_app
```

#### Step 3.3: Validate File Sizes

```bash
# Check all new files comply with limits
python scripts/check_file_sizes.py --path apps/your_app --verbose
```

**Expected:** All files < 150 lines (models) or < 200 lines (settings)

#### Step 3.4: Run App-Specific Tests

```bash
# Run tests for the refactored app
python -m pytest apps/your_app/tests/ -v --tb=short

# Check test coverage
python -m pytest apps/your_app/tests/ --cov=apps.your_app --cov-report=term-missing
```

**Target:** 100% test pass rate, no coverage reduction

#### Step 3.5: Run Full Test Suite

```bash
# Run all tests to catch cross-app issues
python -m pytest --tb=short -v

# Or just run tests that import from your_app
python -m pytest -k "your_app" -v
```

#### Step 3.6: Check for Import Errors Across Codebase

```bash
# Find all files that import from your models
grep -r "from apps.your_app.models import" . --include="*.py" | grep -v __pycache__ | grep -v ".pyc"

# Find relative imports
grep -r "from .models import" apps/your_app/ --include="*.py"

# Test each importing file
python -c "import apps.your_app.views; print('✅ Views import OK')"
python -c "import apps.your_app.admin; print('✅ Admin import OK')"
python -c "import apps.your_app.serializers; print('✅ Serializers import OK')"
```

#### Step 3.7: Manual Smoke Testing

**Critical paths to test:**

1. **Django Admin:**
   ```bash
   python manage.py runserver
   # Visit http://localhost:8000/admin/your_app/
   # Verify all models appear
   # Try creating/editing a model instance
   ```

2. **API Endpoints:**
   ```bash
   # Test API endpoints that use the models
   curl http://localhost:8000/api/v1/your-app/ -H "Authorization: Token <token>"
   ```

3. **Celery Tasks (if applicable):**
   ```bash
   # Check Celery tasks that import models
   python manage.py shell
   >>> from apps.your_app.tasks import your_task
   >>> your_task.delay()
   ```

---

### Phase 4: Documentation (2 hours)

#### Step 4.1: Create Refactoring Completion Report

```markdown
# Your App Models Refactoring - COMPLETE

**Date**: YYYY-MM-DD
**Status**: ✅ Complete
**Pattern**: [Minimal/Medium/Extensive] Split

## Executive Summary

Successfully refactored your_app models from XXX lines to Y focused modules.

## Before/After

| Metric | Before | After |
|--------|--------|-------|
| Total Lines | XXX | YYY |
| Files | 1 | Y |
| Models per File | X | 1-2 |
| Largest File | XXX lines | ZZZ lines |

## Modules Created

1. **enums.py** - Shared enumerations
2. **core_model.py** - Primary business logic
3. **audit_model.py** - Audit trail
...

## Validation Results

- ✅ All tests passing
- ✅ No migrations required
- ✅ All imports working
- ✅ File size limits met
- ✅ Django admin working
- ✅ API endpoints functional

## Lessons Learned

- [Lesson 1]
- [Lesson 2]
```

Save as: `YOUR_APP_REFACTORING_COMPLETE.md` in project root

#### Step 4.2: Update Module Docstrings

Ensure every new module has comprehensive docstrings (see Step 2.5 for template).

#### Step 4.3: Update Architecture Documentation

If refactoring affects architecture:

```markdown
# Update docs/architecture/SYSTEM_ARCHITECTURE.md

## Refactored Modules (November 2025)

- **your_app.models**: Split from 655 lines → 7 focused modules (Nov 2025)
  - Following: ADR 001 (File Size Limits)
  - Pattern: Medium Split (6-10 modules)
  - Backward compatibility: 100% maintained
```

---

### Phase 5: Peer Review (1 day)

#### Step 5.1: Create Pull Request

```bash
# Push branch
git push origin refactor/your-app-models

# Create PR (or use GitHub CLI)
gh pr create --title "refactor(your_app): Split models into focused modules" \
  --body "$(cat <<'EOF'
## Summary

Refactored `apps/your_app/models.py` (XXX lines) into Y focused modules following ADR 001 file size limits.

## Changes

- Split into Y modules (enums, core, audit, config)
- Each file < 150 lines (ADR 001 compliance)
- 100% backward compatibility maintained
- All tests passing

## Modules Created

1. **enums.py** - Shared enumerations
2. **core_model.py** - Primary business entity
3. **audit_model.py** - Audit trail
...

## Testing

- ✅ All unit tests passing
- ✅ Integration tests passing
- ✅ Django admin working
- ✅ API endpoints functional
- ✅ File size validation passing

## Backward Compatibility

All existing imports work unchanged:
```python
from apps.your_app.models import YourModel  # ✅ Works
```

## Documentation

- [x] Refactoring completion report created
- [x] Module docstrings added
- [x] Architecture docs updated
- [x] REFACTORING_PATTERNS.md examples added

## Checklist

- [x] All tests pass
- [x] No migrations required (or migrations reviewed)
- [x] File size limits met
- [x] Backward compatibility verified
- [x] Documentation updated
- [x] Original file preserved as models_deprecated.py

## Related

- ADR: docs/architecture/adr/001-file-size-limits.md
- Pattern: docs/architecture/REFACTORING_PATTERNS.md
- Playbook: docs/architecture/REFACTORING_PLAYBOOK.md

EOF
)"
```

#### Step 5.2: Address Review Feedback

**Common feedback items:**

1. **"Why split this way?"**
   - Explain domain boundaries
   - Reference business logic separation
   - Cite similar patterns (wellness, journal, attendance)

2. **"Are imports still working?"**
   - Share test results
   - Show `__all__` exports
   - Demonstrate backward compatibility tests

3. **"What about migrations?"**
   - Explain why no migrations (structure only)
   - Or justify why migrations needed
   - Show migration review

---

### Phase 6: Deployment (1 day)

#### Step 6.1: Merge to Main

```bash
# Squash commits if desired
git rebase -i HEAD~N

# Merge PR (via GitHub or command line)
git checkout main
git pull
git merge refactor/your-app-models
```

#### Step 6.2: Deploy to Staging

```bash
# Deploy to staging environment
./deploy_staging.sh

# Or via CI/CD
git push origin main  # Triggers CI/CD
```

#### Step 6.3: Smoke Test Staging

**Repeat critical tests:**

1. Django admin for affected models
2. API endpoints using models
3. Celery tasks importing models
4. Any cron jobs or scheduled tasks

#### Step 6.4: Deploy to Production

```bash
# Deploy to production
./deploy_production.sh

# Monitor logs for import errors
tail -f /var/log/django/production.log | grep "ImportError\|ModuleNotFoundError"
```

#### Step 6.5: Monitor for 24 Hours

**Watch for:**

- Import errors in logs
- Increased error rates
- Performance degradation
- User reports of issues

**Rollback plan:** Revert to pre-refactoring commit if critical issues

---

## Pattern Library

### Pattern 1: Minimal Split (3-5 modules)

**Use when:** 400-700 lines, clear domain separation

**Example:** Journal models (698 lines → 4 modules)

```
models/
├── __init__.py
├── enums.py       # Shared enumerations
├── entry.py       # Core model
├── media.py       # Media attachments
└── privacy.py     # Privacy settings
```

**Characteristics:**
- Simple, focused split
- Minimal inter-module dependencies
- Easy to understand structure
- Quick refactoring (1-2 days)

---

### Pattern 2: Medium Split (6-10 modules)

**Use when:** 700-1000 lines, multiple business domains

**Example:** Help Center models (554 lines → 6 modules)

```
models/
├── __init__.py
├── tag.py                 # Tagging system
├── category.py            # Hierarchical categories
├── article.py             # Knowledge base articles
├── search_history.py      # Search analytics
├── interaction.py         # User engagement
└── ticket_correlation.py  # Ticket effectiveness
```

**Characteristics:**
- Moderate complexity
- Clear domain boundaries
- Some shared dependencies (tags, categories)
- Standard refactoring (2-3 days)

---

### Pattern 3: Extensive Split (10+ modules)

**Use when:** 1000+ lines (god file), many distinct domains

**Example:** Attendance models (1200+ lines → 15 modules)

```
models/
├── __init__.py
├── people_eventlog.py          # Core attendance
├── geofence.py                 # Location boundaries
├── tracking.py                 # GPS tracking
├── test_geo.py                 # Test utilities
├── audit_log.py                # Audit & compliance
├── consent.py                  # Consent management
├── post.py                     # Post definitions
├── post_assignment.py          # Roster management
├── post_order_acknowledgement.py  # Digital orders
├── approval_workflow.py        # Approval processes
├── alert_monitoring.py         # Alert rules
├── fraud_alert.py              # Fraud detection
├── user_behavior_profile.py    # Behavioral analytics
├── attendance_photo.py         # Photo captures
└── sync_conflict.py            # Conflict resolution
```

**Characteristics:**
- High complexity
- Many independent domains
- Complex relationships
- Extended refactoring (3-5 days)

---

### Pattern 4: Hierarchical Split (Subdirectories)

**Use when:** Very large apps with nested concerns

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
    │   └── ml_training_dataset.py
    └── ivr/
        └── models/
            ├── __init__.py
            ├── ivr_provider_config.py
            └── voice_script_template.py
```

**Characteristics:**
- Very high complexity
- Nested submodules
- Clear architectural boundaries
- Complex refactoring (5+ days)

---

## Real-World Case Studies

### Case Study 1: Attendance Models

**Challenge:** 1,200+ line god file with 20+ model classes

**Solution:** Extensive split (15 modules)

**Key Decisions:**

1. **Split by business domain:**
   - Core attendance (people_eventlog.py)
   - Geofencing (geofence.py, tracking.py)
   - Post management (post.py, post_assignment.py)
   - Compliance (audit_log.py, consent.py)
   - Security (fraud_alert.py, user_behavior_profile.py)

2. **Preserved geospatial dependencies:**
   - All PostGIS imports in geofence.py
   - Centralized location utilities

3. **Maintained complex relationships:**
   - Used string references for ForeignKeys
   - Carefully ordered imports in `__init__.py`

**Results:**
- 615 → 5,232 lines (with comprehensive docs)
- 0 test failures
- 100% backward compatibility
- 15 focused modules (avg 349 lines each)

**Lessons Learned:**
- Start with enums and helpers
- Keep tightly coupled models together
- Use string references for circular FKs
- Test after each module extraction

---

### Case Study 2: Face Recognition Models

**Challenge:** 669 line file with ML model registry + embeddings

**Solution:** Medium split (9 modules)

**Key Decisions:**

1. **Separate ML concerns:**
   - Model registry (face_recognition_model.py)
   - Embeddings (face_embedding.py)
   - Anti-spoofing (anti_spoofing_model.py)
   - Quality metrics (face_quality_metrics.py)

2. **Isolate compliance:**
   - Biometric consent (biometric_consent_log.py)
   - Audit trail (biometric_audit_log.py)

3. **Extract verification:**
   - Separate verification logs (face_verification_log.py)

**Results:**
- 669 → 799 lines (with docs)
- 9 focused modules (avg 89 lines each)
- Clear separation of ML vs compliance concerns
- Easy to audit biometric compliance

**Lessons Learned:**
- Group by technical domain (ML, compliance, audit)
- Extract enums early (BiometricConsentType, etc.)
- Keep embedding logic self-contained

---

### Case Study 3: Work Order Management

**Challenge:** 655 line file with complex workflow models

**Solution:** Medium split (7 modules)

**Key Decisions:**

1. **Extract enumerations first:**
   - 8 different TextChoices → enums.py (86 lines)

2. **Separate concerns:**
   - Vendor management (vendor.py)
   - Core work order (work_order.py)
   - Checklist details (wom_details.py)
   - Approval workflow (approver.py)

3. **Helper functions:**
   - JSONField defaults → helpers.py

**Results:**
- 655 → 843 lines (with docs)
- 7 focused modules
- Largest file: 426 lines (work_order.py with @ontology decorators)
- Single responsibility per module

**Lessons Learned:**
- Enums first, always
- Helper functions in separate file
- Keep complex decorators with model (@ontology)

---

## Common Challenges and Solutions

### Challenge 1: Circular Import Errors

**Symptom:**

```
ImportError: cannot import name 'ModelA' from partially initialized module 'apps.your_app.models.model_a'
```

**Cause:** Direct imports create circular dependency

```python
# models/model_a.py
from .model_b import ModelB  # ❌ Circular!

class ModelA(models.Model):
    related_b = models.ForeignKey(ModelB, ...)

# models/model_b.py
from .model_a import ModelA  # ❌ Circular!

class ModelB(models.Model):
    related_a = models.ForeignKey(ModelA, ...)
```

**Solution:** Use string references for ForeignKey

```python
# models/model_a.py
from django.db import models  # No import of ModelB!

class ModelA(models.Model):
    related_b = models.ForeignKey(
        'your_app.ModelB',  # ✅ String reference
        on_delete=models.CASCADE
    )

# models/model_b.py
from django.db import models  # No import of ModelA!

class ModelB(models.Model):
    related_a = models.ForeignKey(
        'your_app.ModelA',  # ✅ String reference
        on_delete=models.CASCADE
    )
```

**Additional tips:**
- Always use string references for same-app ForeignKeys
- Import types only for type hints: `from typing import TYPE_CHECKING`
- Avoid importing models in method definitions

---

### Challenge 2: Missing Exports in `__init__.py`

**Symptom:**

```python
from apps.your_app.models import YourModel
# ImportError: cannot import name 'YourModel'
```

**Cause:** Forgot to export from `__init__.py`

**Solution:** Complete `__all__` declaration

```python
# models/__init__.py

from .your_model import YourModel
from .other_model import OtherModel

__all__ = [
    'YourModel',
    'OtherModel',  # Add ALL models, enums, helpers!
]
```

**Validation:**

```bash
# Test all expected imports
python -c "from apps.your_app.models import YourModel, OtherModel; print('✅')"

# Check __all__ completeness
python -c "from apps.your_app import models; print(models.__all__)"
```

---

### Challenge 3: Unexpected Migrations Generated

**Symptom:**

```bash
python manage.py makemigrations your_app
# Migrations for 'your_app':
#   0042_auto_20251105_1234.py
#     - Alter field related on yourmodel
```

**Cause:** Django detected model changes due to:
- Reordered model definitions
- Changed import paths (in Meta.db_table or related_name)

**Solution:**

**Option 1: Accept migration if harmless**

```bash
# Review migration file
cat apps/your_app/migrations/0042_auto_20251105_1234.py

# If it's truly no-op (e.g., just reordering)
python manage.py migrate your_app
```

**Option 2: Prevent migration with --check**

```bash
# Check what migrations would be created
python manage.py makemigrations --dry-run --verbosity 2
```

**Option 3: Fake migration if truly no schema change**

```bash
python manage.py migrate your_app 0042 --fake
```

---

### Challenge 4: Test Failures After Refactoring

**Symptom:**

```
FAILED tests/test_models.py::TestYourModel::test_creation
ImportError: cannot import name 'YourModel'
```

**Cause:** Tests have hardcoded import paths

**Solution:** Update test imports

```python
# ❌ Before (hardcoded)
from apps.your_app.models.your_model import YourModel

# ✅ After (use package import)
from apps.your_app.models import YourModel  # Works via __init__.py
```

**If many tests affected:**

```bash
# Find all test imports
grep -r "from apps.your_app.models." apps/your_app/tests/

# Use sed to bulk update (careful!)
sed -i '' 's/from apps\.your_app\.models\.\w\+ import/from apps.your_app.models import/g' apps/your_app/tests/*.py
```

---

### Challenge 5: Over-Splitting (Too Many Small Files)

**Symptom:**
- 20+ tiny files (<30 lines each)
- Constant switching between files
- Unclear module boundaries

**Cause:** Splitting by line count instead of domain

**Solution:** Merge related concerns

**❌ Wrong: Over-split**

```
models/
├── user_name.py       # 20 lines
├── user_email.py      # 15 lines
├── user_profile.py    # 25 lines
└── user_settings.py   # 18 lines
```

**✅ Right: Cohesive modules**

```
models/
├── user.py            # 80 lines - cohesive user model
└── user_settings.py   # 45 lines - separate concerns
```

**Guideline:** Don't split below 50 lines unless strong domain boundary exists.

---

## Quality Assurance

### QA Checklist

**Before refactoring:**

- [ ] All tests passing
- [ ] No pending migrations
- [ ] Clean git status
- [ ] Team notified
- [ ] Backup branch created

**During refactoring:**

- [ ] Enums extracted first
- [ ] Helpers extracted second
- [ ] Models split by domain (not arbitrary)
- [ ] String references used for ForeignKeys
- [ ] Comprehensive `__init__.py` with `__all__`
- [ ] Original file preserved as `*_deprecated.py`
- [ ] Deprecation docstring added to old file

**After refactoring:**

- [ ] `python manage.py check` passes
- [ ] `python manage.py makemigrations` (reviewed)
- [ ] All tests pass (app-specific)
- [ ] Full test suite passes
- [ ] File size limits met (`check_file_sizes.py`)
- [ ] Imports work from other apps
- [ ] Django admin functional
- [ ] API endpoints working
- [ ] Refactoring completion report created
- [ ] Documentation updated

---

### Automated Validation

**Run all validation scripts:**

```bash
#!/bin/bash
# validate_refactoring.sh

APP_NAME=$1

echo "🔍 Validating refactoring for $APP_NAME..."

# 1. Django checks
echo "1️⃣ Running Django checks..."
python manage.py check || exit 1

# 2. File size limits
echo "2️⃣ Checking file sizes..."
python scripts/check_file_sizes.py --path apps/$APP_NAME --verbose || exit 1

# 3. Import validation
echo "3️⃣ Testing imports..."
python -c "from apps.$APP_NAME import models; print('✅ Package imports')" || exit 1

# 4. Model imports
echo "4️⃣ Testing individual model imports..."
python -c "from apps.$APP_NAME.models import *; print('✅ Wildcard imports')" || exit 1

# 5. App tests
echo "5️⃣ Running app tests..."
python -m pytest apps/$APP_NAME/tests/ -v --tb=short || exit 1

# 6. Full test suite
echo "6️⃣ Running full test suite..."
python -m pytest --tb=short -x || exit 1

echo "✅ All validation checks passed!"
```

**Usage:**

```bash
chmod +x validate_refactoring.sh
./validate_refactoring.sh your_app
```

---

## Emergency Procedures

### Emergency Rollback (Production)

**If refactoring causes critical production issues:**

#### Step 1: Immediate Rollback

```bash
# 1. Revert to pre-refactoring commit
git log --oneline | grep "refactor(your_app)"  # Find commit hash
git revert <commit-hash>

# 2. Deploy immediately
./deploy_production.sh --emergency

# 3. Verify rollback
curl https://production.example.com/api/v1/health/
```

#### Step 2: Restore Original File

```bash
# In rolled-back code
cd apps/your_app

# If models_deprecated.py exists
mv models_deprecated.py models.py
rm -rf models/  # Remove package directory

# Deploy
git add .
git commit -m "emergency: Rollback your_app refactoring"
git push
./deploy_production.sh
```

#### Step 3: Investigate Root Cause

```bash
# Check production logs
tail -f /var/log/django/production.log | grep "your_app"

# Common issues:
# - Missing import in __init__.py
# - Circular import not caught in tests
# - Migration not applied
# - Celery task import error
```

#### Step 4: Fix and Redeploy

```bash
# Fix issue in separate branch
git checkout -b hotfix/your-app-refactoring-fix

# Apply fix (e.g., add missing export)
# ... make changes ...

# Test thoroughly
python -m pytest apps/your_app/tests/ -v
python -m pytest --tb=short -v

# Deploy to staging first
git push origin hotfix/your-app-refactoring-fix
./deploy_staging.sh

# Smoke test staging
# ...

# If OK, deploy to production
./deploy_production.sh
```

---

### Emergency Rollback (Development)

**If refactoring breaks development environment:**

#### Option 1: Restore from Deprecated File

```bash
cd apps/your_app

# Remove new package
rm -rf models/

# Restore original
mv models_deprecated.py models.py

# Verify
python manage.py check
python -m pytest apps/your_app/tests/ -v
```

#### Option 2: Git Revert

```bash
# Find refactoring commit
git log --oneline apps/your_app/

# Revert specific commit
git revert <commit-hash>

# Or reset if not pushed
git reset --hard HEAD~1
```

---

## Appendix: Quick Reference

### Essential Commands

```bash
# Pre-refactoring analysis
wc -l apps/your_app/models.py
grep "^class " apps/your_app/models.py
python scripts/detect_god_files.py --path apps/your_app

# During refactoring
mkdir apps/your_app/models
mv apps/your_app/models.py apps/your_app/models_deprecated.py

# Validation
python manage.py check
python manage.py makemigrations your_app --dry-run
python -m pytest apps/your_app/tests/ -v
python scripts/check_file_sizes.py --path apps/your_app --verbose

# Import testing
python -c "from apps.your_app.models import YourModel; print('✅')"
grep -r "from apps.your_app.models import" . --include="*.py" | grep -v __pycache__

# Emergency rollback
mv models_deprecated.py models.py
rm -rf models/
```

---

### File Templates

**See also:**
- `docs/architecture/REFACTORING_PATTERNS.md` - Pattern examples
- `docs/architecture/adr/001-file-size-limits.md` - Architecture decision
- Individual refactoring reports: `*_REFACTORING_COMPLETE.md`

---

## Success Stories

### By The Numbers (Phases 1-6)

| App | Lines Before | Modules After | Time Spent | Production Incidents |
|-----|--------------|---------------|------------|----------------------|
| attendance | 1,200+ | 15 | 3 days | 0 |
| face_recognition | 669 | 9 | 2 days | 0 |
| work_order_management | 655 | 7 | 2 days | 0 |
| issue_tracker | 600+ | 10 | 2 days | 0 |
| journal | 698 | 4 | 1 day | 0 |
| help_center | 554 | 6 | 2 days | 0 |
| wellness | 450+ | 5 | 1.5 days | 0 |

**Total:** 16 apps refactored, 80+ god files eliminated, 0 production incidents

---

## Conclusion

Refactoring god files is a critical investment in code maintainability. By following this playbook's proven patterns from Phases 1-6, you can safely split monolithic files into focused modules while maintaining 100% backward compatibility.

**Remember:**
1. **Split by domain, not lines** - Respect business boundaries
2. **Test relentlessly** - Verify at every step
3. **Maintain backward compatibility** - All imports must work
4. **Document everything** - Future you will be grateful

**Next Steps:**
1. Identify your next refactoring candidate (`detect_god_files.py`)
2. Follow this playbook step-by-step
3. Document your refactoring (completion report)
4. Share lessons learned with team
5. Update this playbook with new patterns

---

**Last Updated:** November 5, 2025

**Maintainer:** Development Team

**Questions?** See `docs/architecture/adr/001-file-size-limits.md` or ask in #architecture Slack channel

**Related Documentation:**
- [REFACTORING_PATTERNS.md](REFACTORING_PATTERNS.md) - Quick pattern reference
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Overall architecture
- [ADR 001: File Size Limits](adr/001-file-size-limits.md) - Architecture decision
- [PROJECT_RETROSPECTIVE.md](../PROJECT_RETROSPECTIVE.md) - Phase 1-6 journey
