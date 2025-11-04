# God File Refactoring Guide

**Status:** Active Remediation Guide
**Priority:** High (7 files violating 150-line limit by 200-365%)
**Related:** Ultrathink Code Review Phase 3 - Architecture Refactoring

---

## Overview

This guide provides a systematic approach to refactoring god files (models >150 lines) into focused, maintainable modules following Django best practices and the patterns established in `apps/peoples/models/`.

## Files Requiring Refactoring

| File | Current Lines | Over Limit | Priority |
|------|--------------|------------|----------|
| `apps/wellness/models.py` | 697 | 365% | HIGH |
| `apps/journal/models.py` | 697 | 365% | HIGH |
| `apps/face_recognition/models.py` | 669 | 346% | HIGH |
| `apps/work_order_management/models.py` | 655 | 337% | MEDIUM |
| `apps/issue_tracker/models.py` | 639 | 326% | MEDIUM |
| `apps/attendance/models.py` | 596 | 297% | MEDIUM |
| `apps/help_center/models.py` | 554 | 269% | MEDIUM |

---

## Refactoring Pattern (Proven from `apps/peoples/`)

### Step 1: Analyze Current Structure

```bash
# Identify all classes
grep -n "^class " apps/wellness/models.py

# Check imports
head -25 apps/wellness/models.py

# Identify relationships (ForeignKey, ManyToMany)
grep -n "ForeignKey\|ManyToMany" apps/wellness/models.py
```

### Step 2: Create Module Structure

```python
apps/wellness/
├── models/
│   ├── __init__.py          # Backward compatibility exports
│   ├── content.py           # WellnessContent model (<150 lines)
│   ├── progress.py          # WellnessUserProgress model (<150 lines)
│   ├── interaction.py       # WellnessContentInteraction model (<150 lines)
│   └── enums.py            # Choice classes (ContentCategory, DeliveryContext, etc.)
└── models.py               # DEPRECATED - imports from models/ for compatibility
```

### Step 3: Split Models by Responsibility

**Rule:** One model per file, shared utilities in separate files

**Example for Wellness:**

```python
# apps/wellness/models/enums.py
"""Wellness content classification enums."""

from django.db import models

class WellnessContentCategory(models.TextChoices):
    """Evidence-based content categories."""
    STRESS_MANAGEMENT = 'stress', 'Stress Management'
    # ... rest of choices

class WellnessDeliveryContext(models.TextChoices):
    # ...

# Export all for convenience
__all__ = ['WellnessContentCategory', 'WellnessDeliveryContext', 'EvidenceLevel']
```

```python
# apps/wellness/models/content.py
"""WellnessContent model - evidence-based wellness content."""

from django.db import models
from apps/tenants.models import TenantAwareModel
from .enums import WellnessContentCategory, WellnessDeliveryContext, EvidenceLevel

class WellnessContent(TenantAwareModel):
    """
    Evidence-based wellness content with scientific backing.

    Compliance: WHO evidence standards, CDC guidelines
    """
    # ... model definition (should be <150 lines)

__all__ = ['WellnessContent']
```

### Step 4: Create Backward Compatibility Shim

```python
# apps/wellness/models/__init__.py
"""
Wellness Models Package

REFACTORING NOTE: Models split from monolithic models.py (697 lines)
into focused modules for maintainability.

Pattern: Follows apps/peoples/models/ refactoring (completed Oct 2025)
Timeline: Backward compatibility maintained until March 2026
"""

# Import all models for backward compatibility
from .enums import *
from .content import WellnessContent
from .progress import WellnessUserProgress
from .interaction import WellnessContentInteraction

# Explicit __all__ for clarity
__all__ = [
    # Enums
    'WellnessContentCategory',
    'WellnessDeliveryContext',
    'WellnessContentLevel',
    'EvidenceLevel',
    # Models
    'WellnessContent',
    'WellnessUserProgress',
    'WellnessContentInteraction',
]
```

```python
# apps/wellness/models.py (deprecated shim)
"""
DEPRECATION NOTICE:
This file is deprecated. Models have been split into apps/wellness/models/
for better maintainability.

Timeline: This shim maintained until March 2026
Migration Guide: Update imports from:
    from apps.wellness.models import WellnessContent
To:
    from apps.wellness.models import WellnessContent  # Still works!
Or explicitly:
    from apps.wellness.models.content import WellnessContent

Related: God File Refactoring (ARCH-001)
"""

# Re-export everything from models package
from .models import *  # noqa: F401, F403

__all__ = [
    'WellnessContent',
    'WellnessUserProgress',
    'WellnessContentInteraction',
    # ... all exports
]
```

### Step 5: Update Tests

```python
# Tests continue to work with no changes!
from apps.wellness.models import WellnessContent  # ✅ Still works

# Or update to explicit imports
from apps.wellness.models.content import WellnessContent  # ✅ Also works
```

### Step 6: Verify No Breaking Changes

```bash
# Run full test suite
pytest apps/wellness/tests/ -v

# Check migrations still work
python manage.py makemigrations --check

# Verify imports
python -c "from apps.wellness.models import WellnessContent; print('✅ Imports working')"
```

---

## Automated Refactoring Script

```python
#!/usr/bin/env python3
"""
God File Refactoring Automation Script

Usage:
    python scripts/refactor_god_file.py apps/wellness/models.py

This script:
1. Analyzes the god file
2. Identifies model classes
3. Creates focused module structure
4. Generates backward compatibility shim
5. Updates __init__.py
"""

import os
import re
import sys
from pathlib import Path

def analyze_models_file(filepath):
    """Extract classes and their line ranges."""
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    classes = []
    current_class = None
    indent_stack = []

    for i, line in enumerate(lines, 1):
        # Detect class definition
        if re.match(r'^class\s+(\w+)', line):
            if current_class:
                current_class['end_line'] = i - 1
                classes.append(current_class)

            match = re.match(r'^class\s+(\w+)', line)
            current_class = {
                'name': match.group(1),
                'start_line': i,
                'content_start': i
            }

    # Close last class
    if current_class:
        current_class['end_line'] = len(lines)
        classes.append(current_class)

    return classes, lines

def create_module_structure(app_path, classes):
    """Create models/ directory with split files."""
    models_dir = Path(app_path) / 'models'
    models_dir.mkdir(exist_ok=True)

    # Create __init__.py
    init_content = generate_init_file(classes)
    (models_dir / '__init__.py').write_text(init_content)

    print(f"✅ Created models/ directory")
    print(f"✅ Created __init__.py with backward compatibility")
    print(f"\nNext steps:")
    print(f"1. Move model classes to individual files in models/")
    print(f"2. Add enums.py for choice classes")
    print(f"3. Create models.py shim for backward compatibility")
    print(f"4. Run tests: pytest {app_path}/tests/ -v")

def generate_init_file(classes):
    """Generate __init__.py content."""
    imports = "\n".join([f"from .{cls['name'].lower()} import {cls['name']}"
                         for cls in classes if not cls['name'].endswith('Choices')])

    all_exports = ", ".join([f"'{cls['name']}'" for cls in classes])

    return f'''"""
Models Package - Refactored from monolithic models.py

Backward compatibility maintained. All imports continue to work.
"""

{imports}

__all__ = [{all_exports}]
'''

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python refactor_god_file.py <path_to_models.py>")
        sys.exit(1)

    filepath = sys.argv[1]
    app_path = Path(filepath).parent

    classes, lines = analyze_models_file(filepath)

    print(f"Found {len(classes)} classes:")
    for cls in classes:
        lines_count = cls['end_line'] - cls['start_line']
        print(f"  - {cls['name']}: {lines_count} lines")

    create_module_structure(app_path, classes)
```

---

## Testing Checklist

After refactoring each god file:

- [ ] All tests pass: `pytest apps/{app}/tests/ -v`
- [ ] No migration changes: `python manage.py makemigrations --check`
- [ ] Imports work: `python -c "from apps.{app}.models import Model; print('✅')"`
- [ ] Admin continues to work (if applicable)
- [ ] API serializers work (if applicable)
- [ ] No circular import errors

---

## Rollback Plan

If issues arise:

```bash
# 1. Revert changes
git checkout apps/{app}/models.py
rm -rf apps/{app}/models/

# 2. Test that everything still works
pytest apps/{app}/tests/
```

---

## Priority Order for Refactoring

1. **Week 1:** `apps/wellness/models.py` (697 lines) - HIGH
2. **Week 2:** `apps/journal/models.py` (697 lines) - HIGH
3. **Week 3:** `apps/face_recognition/models.py` (669 lines) - HIGH
4. **Week 4-5:** Remaining 4 files (MEDIUM priority)

**Total Effort:** 4-6 weeks (1 file per week with testing)

---

## Success Metrics

- ✅ All model files <150 lines
- ✅ No test regressions
- ✅ Backward compatibility maintained
- ✅ Code review approval
- ✅ Zero production incidents

---

## Related Documentation

- `.claude/rules.md` - Rule #7 (Model Complexity Limits)
- `apps/peoples/models/` - Reference implementation
- `docs/architecture/SYSTEM_ARCHITECTURE.md` - Architecture guidelines

---

**Last Updated:** 2025-11-04
**Owner:** Engineering Team
**Status:** Ready for Implementation
