# Code Quality Ontology - Quick Reference

**51 registered patterns** | **Auto-loaded** | **Queryable via Registry/Claude/MCP**

---

## Quick Queries

```python
from apps.ontology.registry import OntologyRegistry

# Exception handling patterns
OntologyRegistry.get_by_domain("code_quality.exception_handling")  # 12 components

# Refactoring patterns
OntologyRegistry.get_by_domain("code_quality.refactoring")  # 15 components

# Constants patterns
OntologyRegistry.get_by_domain("code_quality.constants")  # 8 components

# Architecture patterns
OntologyRegistry.get_by_domain("code_quality.architecture")  # 6 components

# All validation tools
OntologyRegistry.get_by_type("tool")  # 10 tools

# All best practices
OntologyRegistry.get_by_tag("best-practice")

# All anti-patterns (forbidden)
OntologyRegistry.get_by_tag("anti-pattern")  # 2 forbidden patterns

# Specific pattern
OntologyRegistry.get("pattern.god_file_refactoring")
```

---

## Exception Handling Patterns

### Constants
```python
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,      # IntegrityError, OperationalError, etc.
    NETWORK_EXCEPTIONS,       # ConnectionError, Timeout, RequestException
    BUSINESS_LOGIC_EXCEPTIONS, # ValidationError, PermissionDenied
    FILE_EXCEPTIONS,          # FileNotFoundError, PermissionError
    PARSING_EXCEPTIONS        # JSONDecodeError, ValueError
)
```

### ✅ Correct Pattern
```python
try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f'Database error: {e}', exc_info=True)
    raise
```

### ❌ Forbidden
```python
try:
    user.save()
except Exception as e:  # TOO BROAD - FORBIDDEN
    logger.error(f'Error: {e}')
```

**Query**: `OntologyRegistry.get("anti_pattern.broad_exception_catching")`

---

## Refactoring Patterns

### God File Refactoring (8 Steps)
```python
pattern = OntologyRegistry.get("pattern.god_file_refactoring")
print(pattern["steps"])
```

1. Identify god file (>150 lines model, >200 lines settings)
2. Analyze responsibilities
3. Create focused modules
4. Move code with backward compatibility
5. Add deprecation warnings
6. Update internal imports
7. Validate with tests
8. Monitor 1-2 releases

**Playbook**: `docs/architecture/REFACTORING_PLAYBOOK.md` ⚠️ **MANDATORY**

### Architecture Limits (Enforced)
- Settings files: **< 200 lines**
- Model classes: **< 150 lines**
- View methods: **< 30 lines**
- Form classes: **< 100 lines**
- Utility functions: **< 50 lines**

**Validation**: `python scripts/check_file_sizes.py --verbose`

### Service Layer Pattern (ADR 003)
```python
# Location: apps/{app}/services/
# Naming: {domain}_service.py
# Class: {Domain}Service

from apps.peoples.services.attendance_service import AttendanceService

service = AttendanceService()
result = service.process_check_in(user_id, location)
```

**Query**: `OntologyRegistry.get("pattern.service_layer_pattern")`

### Deep Nesting Flattening
```python
# ❌ Before: Deep nesting (3+ levels)
if user:
    if user.is_active:
        if user.has_perm():
            process_user(user)

# ✅ After: Guard clauses
if not user:
    return
if not user.is_active:
    return
if not user.has_perm():
    return
process_user(user)
```

**Max nesting**: 3 levels

---

## Constants Patterns

### DateTime Constants (Python 3.12 Compatible)
```python
from apps.core.constants.datetime_constants import (
    SECONDS_IN_MINUTE,  # 60
    SECONDS_IN_HOUR,    # 3600
    SECONDS_IN_DAY,     # 86400
    SECONDS_IN_WEEK     # 604800
)

# ❌ Magic number
if elapsed > 3600:
    pass

# ✅ Named constant
if elapsed > SECONDS_IN_HOUR:
    pass
```

### Correct DateTime Imports (Python 3.12+)
```python
from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from apps.core.utils_new.datetime_utilities import get_current_utc

# ❌ FORBIDDEN
datetime.utcnow()  # Deprecated
from datetime import timezone  # Conflicts with django.utils.timezone
```

---

## Architecture Patterns

### Circular Dependency Resolution
```python
# 1. Late import
def process_data():
    from apps.other.models import OtherModel  # Import inside function
    return OtherModel.objects.all()

# 2. Dependency inversion
# Create abstract base class, concrete implementations depend on it

# 3. Django signals
from django.db.models.signals import post_save

@receiver(post_save, sender=User)
def handle_user_save(sender, instance, **kwargs):
    # Event-driven, loose coupling
    pass
```

**Query**: `OntologyRegistry.get("pattern.circular_dependency_resolution")`

---

## Validation Tools

```bash
# File size validation
python scripts/check_file_sizes.py --verbose

# God file detection
python scripts/detect_god_files.py --path apps/your_app

# Refactoring verification
python scripts/verify_attendance_models_refactoring.py

# Code quality validation (all patterns)
python scripts/validate_code_quality.py --verbose

# Exception handling validation
python scripts/validate_exception_handling.py --strict

# DateTime usage validation
./validate_datetime_changes.sh

# Ontology verification
python scripts/verify_code_quality_ontology.py
```

**Query**: `OntologyRegistry.get_by_type("tool")`

---

## Claude Code Integration

```
/ontology exception handling      # Load exception patterns
/ontology refactoring             # Load refactoring patterns
/ontology code quality            # Load all patterns
/ontology validation              # Load validation tools
/ontology anti-pattern            # Load forbidden patterns
```

---

## MCP Server

```json
{
  "name": "ontology_query",
  "arguments": {
    "domain": "code_quality.refactoring",
    "tags": ["best-practice"]
  }
}
```

---

## Key Deliverables

| Deliverable | Status | Documentation |
|-------------|--------|---------------|
| Exception handling remediation | ✅ 554→0 violations | `EXCEPTION_HANDLING_PART3_COMPLETE.md` |
| God file refactoring | ✅ 16 apps, 80+ files | `GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md` |
| Refactoring playbook | ✅ Complete | `docs/architecture/REFACTORING_PLAYBOOK.md` |
| 5 ADRs | ✅ Complete | `docs/architecture/adr/` |
| 4 Training materials | ✅ Complete | `docs/training/` |
| Magic numbers extraction | ✅ Complete | `MAGIC_NUMBERS_EXTRACTION_COMPLETE.md` |
| Circular dependencies | ✅ Complete | `CIRCULAR_DEPENDENCY_FIX_SUMMARY.md` |

---

## Quick Links

### Documentation
- [Code Quality Ontology Guide](../ontology/CODE_QUALITY_ONTOLOGY.md)
- [CLAUDE.md Quick Reference](../../CLAUDE.md) ⚠️ **MANDATORY**
- [Refactoring Playbook](../architecture/REFACTORING_PLAYBOOK.md) ⚠️ **MANDATORY**
- [Exception Handling Quick Reference](EXCEPTION_HANDLING_QUICK_REFERENCE.md)

### Training
- [Quality Standards Training](../training/QUALITY_STANDARDS_TRAINING.md)
- [Refactoring Training](../training/REFACTORING_TRAINING.md)
- [Service Layer Training](../training/SERVICE_LAYER_TRAINING.md)
- [Testing Training](../training/TESTING_TRAINING.md)

### ADRs
- [001: File Size Limits](../architecture/adr/001-file-size-limits.md)
- [002: Circular Dependencies](../architecture/adr/002-circular-dependency-resolution.md)
- [003: Service Layer](../architecture/adr/003-service-layer-organization.md)
- [004: Testing Strategy](../architecture/adr/004-testing-strategy.md)
- [005: Exception Handling](../architecture/adr/005-exception-handling-patterns.md)

---

**Total Components**: 51 patterns + 38 improvements = **89 components**  
**Status**: ✅ **AUTO-LOADED ON DJANGO STARTUP**  
**Last Updated**: November 6, 2025
