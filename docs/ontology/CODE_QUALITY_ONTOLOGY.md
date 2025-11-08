# Code Quality Ontology

**Comprehensive knowledge base of code quality patterns, refactoring practices, and validation tools.**

**Created**: November 6, 2025  
**Total Components**: 51 registered patterns and tools  
**Integration**: Automatically loaded on Django startup

---

## Overview

The Code Quality Ontology captures all exception handling, refactoring, and code quality patterns from our Phase 1-6 improvement work. This knowledge is now queryable through the ontology system and available to LLM assistants.

## Categories

### 1. Exception Handling Patterns (12 components)

#### Core Exception Pattern Constants

| Pattern | Purpose | Criticality |
|---------|---------|-------------|
| `DATABASE_EXCEPTIONS` | Database-specific exceptions (IntegrityError, OperationalError, etc.) | High |
| `NETWORK_EXCEPTIONS` | Network errors (ConnectionError, Timeout, RequestException) | High |
| `BUSINESS_LOGIC_EXCEPTIONS` | Validation errors (ValidationError, PermissionDenied) | Medium |
| `FILE_EXCEPTIONS` | File I/O errors (FileNotFoundError, PermissionError, OSError) | Medium |
| `PARSING_EXCEPTIONS` | Data parsing errors (JSONDecodeError, ValueError) | Medium |

**Location**: `apps.core.exceptions.patterns`  
**Documentation**: `docs/quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md`

#### Anti-Patterns (Forbidden)

| Anti-Pattern | Why Forbidden | Remediation |
|--------------|---------------|-------------|
| Broad Exception Catching | Hides real errors, masks security issues | Use specific exception tuples |
| Missing Network Timeout | Workers hang indefinitely | Always use `timeout=(connect, read)` |

**Enforcement**: Pre-commit hooks, CI/CD validation

#### Best Practices

- **Specific Exception Types** - Always catch specific exceptions, never broad `Exception`
- **Exception Logging with Context** - Log with `exc_info=True` to capture stack traces
- **Re-raise After Logging** - Log and re-raise to preserve error propagation

**Example**:
```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f'Database error saving user {user.id}', exc_info=True)
    raise
```

#### Deliverables

- ✅ **100% Remediation** - 554 violations → 0 violations (Nov 5, 2025)
- ✅ **Automation** - `scripts/validate_exception_handling.py`
- 📖 **Documentation** - `EXCEPTION_HANDLING_PART3_COMPLETE.md`

---

### 2. Refactoring Patterns (15 components)

#### Core Refactoring Patterns

| Pattern | Purpose | Documentation |
|---------|---------|---------------|
| **God File Refactoring** | Split oversized files into focused modules | [REFACTORING_PATTERNS.md](../architecture/REFACTORING_PATTERNS.md) |
| **Service Layer Pattern** | ADR 003 - Business logic in service classes | [ADR 003](../architecture/adr/003-service-layer-organization.md) |
| **Single Responsibility** | Each module has one clear responsibility | [REFACTORING_PATTERNS.md](../architecture/REFACTORING_PATTERNS.md) |
| **Deep Nesting Flattening** | Flatten nested conditionals with guard clauses | [DEEP_NESTING_REFACTORING_COMPLETE.md](../../DEEP_NESTING_REFACTORING_COMPLETE.md) |

#### Architecture Limits (Enforced)

| Component | Limit | Enforcement |
|-----------|-------|-------------|
| Settings files | < 200 lines | Pre-commit, CI/CD |
| Model classes | < 150 lines | Pre-commit, CI/CD |
| View methods | < 30 lines | Pre-commit, CI/CD |
| Form classes | < 100 lines | Pre-commit, CI/CD |
| Utility functions | < 50 lines | Pre-commit, CI/CD |

**Validation Tool**: `scripts/check_file_sizes.py --verbose`  
**Documentation**: [ADR 001](../architecture/adr/001-file-size-limits.md)

#### God File Refactoring Process

**8-Step Pattern**:

1. **Identify** - Find god file (>150 lines model, >200 lines settings)
2. **Analyze** - Map responsibilities and dependencies
3. **Create** - New focused modules (models/, managers/, services/)
4. **Move** - Transfer code with backward compatibility
5. **Deprecate** - Add warnings to old imports
6. **Update** - Fix internal imports
7. **Validate** - Run test suite
8. **Monitor** - Watch 1-2 releases before removal

**Examples**:
- `apps/attendance/models.py` (1200 lines) → 8 focused files
- `apps/activity/models.py` (900 lines) → 6 focused files

**Playbook**: [REFACTORING_PLAYBOOK.md](../architecture/REFACTORING_PLAYBOOK.md)

#### Deep Nesting Flattening Techniques

- **Guard Clauses** - Early validation and exit
- **Early Returns** - Return immediately when possible
- **Extract Conditions** - Move complex conditions to helper functions
- **Strategy Pattern** - For complex branching logic

**Max Nesting**: 3 levels

**Example**:
```python
# ❌ Before: Deep nesting
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

#### Deliverables

- ✅ **Phase 1-6 Complete** - 16 apps refactored, 80+ god files eliminated (100% backward compatible)
- ✅ **Refactoring Playbook** - Complete guide for future work
- ✅ **5 ADRs** - Architectural decision records
- 📖 **Training Materials** - 4 comprehensive guides in `docs/training/`

---

### 3. Constants & Magic Numbers (8 components)

#### Magic Number Extraction Pattern

**Purpose**: Replace magic numbers with named constants for readability and maintainability.

**Example**:
```python
# ❌ Before: Magic numbers
if elapsed > 3600:  # What is 3600?
    time.sleep(300)  # What is 300?

# ✅ After: Named constants
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_5_MINUTES

if elapsed > SECONDS_IN_HOUR:
    time.sleep(SECONDS_IN_5_MINUTES)
```

#### Constant Organization Structure

**Location**: `apps/core/constants/`

| Module | Purpose | Examples |
|--------|---------|----------|
| `datetime_constants.py` | Time-related constants | `SECONDS_IN_DAY = 86400` |
| `status_constants.py` | Status enums | `TASK_STATUS_PENDING = 'pending'` |
| `permission_constants.py` | Permission strings | `PERM_VIEW_REPORTS = 'reports.view'` |
| `config_constants.py` | Configuration defaults | `DEFAULT_PAGE_SIZE = 25` |

#### DateTime Constants (Python 3.12 Compatible)

**Module**: `apps/core/constants/datetime_constants.py`

**Exports**:
- `SECONDS_IN_MINUTE = 60`
- `SECONDS_IN_HOUR = 3600`
- `SECONDS_IN_DAY = 86400`
- `SECONDS_IN_WEEK = 604800`
- `MILLISECONDS_IN_SECOND = 1000`

**Correct Imports** (Python 3.12+):
```python
from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
from apps.core.utils_new.datetime_utilities import get_current_utc
```

**Forbidden**:
```python
datetime.utcnow()  # ❌ Deprecated in Python 3.12
from datetime import timezone  # ❌ Conflicts with django.utils.timezone
```

**Documentation**: [DATETIME_FIELD_STANDARDS.md](../DATETIME_FIELD_STANDARDS.md)

#### Deliverables

- ✅ **Magic Numbers Remediation** - Complete extraction (Nov 5, 2025)
- ✅ **DateTime Migration** - All datetime magic numbers to constants
- 📖 **Quick Reference** - `CONSTANTS_QUICK_REFERENCE.md`

---

### 4. Architectural Patterns (6 components)

#### Circular Dependency Resolution

**Techniques**:

1. **Late Imports** - Import inside function to break circular dependencies
   ```python
   def process_data():
       from apps.other.models import OtherModel  # Late import
       return OtherModel.objects.all()
   ```

2. **Dependency Inversion** - Depend on abstractions, not concrete implementations
   - Create abstract base class or protocol
   - Concrete implementations depend on abstraction

3. **Django Signals** - Event-driven architecture for loose coupling
   - `post_save` signal for notifications
   - `pre_delete` signal for cleanup
   - ⚠️ Caution: Don't overuse - makes code flow harder to trace

4. **Service Layer Extraction** - Move shared logic to service classes

**Documentation**: [ADR 002](../architecture/adr/002-circular-dependency-resolution.md)

#### Deliverables

- ✅ **Circular Dependency Remediation** - Complete resolution (Nov 5, 2025)
- 📖 **Fix Summary** - `CIRCULAR_DEPENDENCY_FIX_SUMMARY.md`
- 📖 **Bounded Contexts** - Domain-driven design analysis

---

### 5. Validation Tools (10 components)

#### Core Validation Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| **check_file_sizes.py** | Validate file sizes against architecture limits | `python scripts/check_file_sizes.py --verbose` |
| **detect_god_files.py** | Identify refactoring candidates | `python scripts/detect_god_files.py --path apps/your_app` |
| **verify_refactoring.py** | Verify model refactorings and import chains | `python scripts/verify_attendance_models_refactoring.py` |
| **validate_code_quality.py** | Comprehensive code quality validation | `python scripts/validate_code_quality.py --verbose` |
| **validate_exception_handling.py** | Verify exception handling patterns | `python scripts/validate_exception_handling.py --strict` |
| **validate_datetime_usage.sh** | Check Python 3.12 datetime compliance | `./validate_datetime_changes.sh` |

#### Comprehensive Code Quality Validation

**Script**: `scripts/validate_code_quality.py --verbose`

**Validates**:
- File size limits
- Exception handling patterns
- Deep nesting
- Import organization
- Code smells

**Enforcement**:
- Pre-commit hooks
- CI/CD pipeline
- Automated PR checks

---

## Querying the Ontology

### Using the Registry

```python
from apps.ontology.registry import OntologyRegistry

# Get specific pattern
pattern = OntologyRegistry.get("pattern.god_file_refactoring")
print(pattern["purpose"])
print(pattern["documentation"])

# Find all exception handling components
exception_patterns = OntologyRegistry.get_by_domain("code_quality.exception_handling")

# Find all validation tools
tools = OntologyRegistry.get_by_type("tool")

# Find all best practices
best_practices = OntologyRegistry.get_by_tag("best-practice")

# Find all anti-patterns (forbidden)
anti_patterns = OntologyRegistry.get_by_tag("anti-pattern")

# Get statistics
stats = OntologyRegistry.get_statistics()
print(f"Total code quality components: {stats['total_components']}")
```

### Using Claude Code `/ontology` Command

```
/ontology exception handling      # Load exception handling patterns
/ontology refactoring             # Load refactoring patterns
/ontology code quality            # Load all code quality knowledge
/ontology validation              # Load validation tools
```

### Using MCP Server

**Tools**:
```json
{
  "name": "ontology_query",
  "arguments": {
    "domain": "code_quality.exception_handling"
  }
}
```

**Resources**:
- `ontology://domain/code_quality.exception_handling`
- `ontology://domain/code_quality.refactoring`
- `ontology://domain/code_quality.constants`

---

## Integration with Development Workflow

### Pre-Commit Hooks

All validation tools run automatically on commit:
- File size validation
- Exception handling validation
- Code quality checks

### CI/CD Pipeline

```yaml
- name: Validate Code Quality
  run: python scripts/validate_code_quality.py --verbose

- name: Check Architecture Limits
  run: python scripts/check_file_sizes.py --strict
```

### Training Materials

New developers should review:
1. [Quality Standards Training](../training/QUALITY_STANDARDS_TRAINING.md)
2. [Refactoring Training](../training/REFACTORING_TRAINING.md)
3. [Service Layer Training](../training/SERVICE_LAYER_TRAINING.md)
4. [Testing Training](../training/TESTING_TRAINING.md)

---

## Deliverables Summary

### Phase 1-6 Achievements (Nov 5, 2025)

| Category | Achievement | Impact |
|----------|-------------|--------|
| **Exception Handling** | 554 violations → 0 (100% remediation) | High reliability |
| **God File Refactoring** | 16 apps, 80+ files split | High maintainability |
| **Architecture Limits** | Enforced via automation | Prevention |
| **Deep Nesting** | 3+ levels flattened | High readability |
| **Magic Numbers** | Complete extraction | High clarity |
| **Circular Dependencies** | Complete resolution | High stability |

### Documentation Created

- ✅ 5 Architecture Decision Records (ADRs)
- ✅ Refactoring Playbook (complete guide)
- ✅ 4 Training Materials
- ✅ Project Retrospective (Phase 1-6 journey)
- ✅ Multiple quick reference guides

---

## Related Documentation

### Core Documentation
- [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md)
- [Refactoring Playbook](../architecture/REFACTORING_PLAYBOOK.md) ⚠️ **MANDATORY**
- [Project Retrospective](../PROJECT_RETROSPECTIVE.md)

### ADRs (Architecture Decision Records)
- [ADR 001: File Size Limits](../architecture/adr/001-file-size-limits.md)
- [ADR 002: Circular Dependency Resolution](../architecture/adr/002-circular-dependency-resolution.md)
- [ADR 003: Service Layer Organization](../architecture/adr/003-service-layer-organization.md)
- [ADR 004: Testing Strategy](../architecture/adr/004-testing-strategy.md)
- [ADR 005: Exception Handling Patterns](../architecture/adr/005-exception-handling-patterns.md)

### Quick References
- [Exception Handling Quick Reference](../quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md)
- [Constants Quick Reference](../../CONSTANTS_QUICK_REFERENCE.md)
- [N+1 Query Optimization Quick Reference](../../N1_OPTIMIZATION_QUICK_REFERENCE.md)

### Training
- [Quality Standards Training](../training/QUALITY_STANDARDS_TRAINING.md)
- [Refactoring Training](../training/REFACTORING_TRAINING.md)
- [Service Layer Training](../training/SERVICE_LAYER_TRAINING.md)
- [Testing Training](../training/TESTING_TRAINING.md)

---

## Contributing

When adding new code quality patterns:

1. Add entry to `apps/ontology/registrations/code_quality_patterns.py`
2. Include all metadata (domain, purpose, tags, criticality)
3. Link to documentation
4. Add examples (both correct and incorrect)
5. Specify enforcement mechanism
6. Update this documentation

---

**Last Updated**: November 6, 2025  
**Maintainer**: Development Team  
**Review Cycle**: Quarterly or on major pattern changes
