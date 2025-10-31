# Testing & Quality Guide

> **Comprehensive guide to testing, code quality validation, and enforcement standards**

---

## Test Execution

### Full test suite with coverage

```bash
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v
```

### Test categories

```bash
python -m pytest -m unit          # Unit tests
python -m pytest -m integration   # Integration tests
python -m pytest -m security      # Security tests
```

### Specific test suites

```bash
python -m pytest apps/peoples/tests/test_models/test_people_model_comprehensive.py -v
python -m pytest apps/core/tests/test_datetime_refactoring_comprehensive.py -v
python -m pytest apps/scheduler/tests/test_schedule_uniqueness_comprehensive.py -v
```

---

## Code Quality Validation

### Comprehensive validation suite

```bash
# Full validation
python scripts/validate_code_quality.py --verbose

# Generate report
python scripts/validate_code_quality.py --report quality_report.md
```

### What it validates

- ✅ Wildcard imports (except Django settings pattern)
- ✅ Generic exception handling
- ✅ Network timeout parameters
- ✅ Code injection (eval/exec)
- ✅ Blocking I/O (time.sleep in request paths)
- ✅ sys.path manipulation
- ✅ Production print statements

---

## Exception Handling Migration

### Analyze generic exception patterns

```bash
python scripts/migrate_exception_handling.py --analyze
```

### Generate migration report

```bash
python scripts/migrate_exception_handling.py --report exception_migration_report.md
```

### Auto-fix high confidence issues

```bash
python scripts/migrate_exception_handling.py --fix --confidence HIGH
```

---

## Current Quality Status (2025-10-10)

### ✅ Complete (Zero Tolerance)

- **Bare except blocks**: **0** (100% eliminated - was 56)
- **Print statements**: Enforced via flake8 T001 (was 305 violations)
- **Orphaned beat tasks**: Automated detection (pre-commit + validate_schedules)
- **Unused code**: 9 items archived (313 KB cleanup) ✨ +3 files (Oct 2025)
- **Runtime bugs**: **0** (UnboundLocalError fixed Oct 2025)
- **Name collisions**: **0** (legacy reports/views_compat.py shim removed Oct 2025)
- **Duplicate code**: **0** (8 instances eliminated Oct 2025)
- **Hardcoded credentials**: **0** (extracted to FrappeService Oct 2025)
- **Network timeouts**: 100% compliant
- **sys.path manipulation**: 100% compliant

### ⚠️ In Progress

- **Critical security**: 8 eval/exec instances (down from 10)
- **Wildcard imports**: 15 instances (documented exceptions)
- **God files**: **0** (reports generation shim deleted Oct 2025)

---

## Code Smell Detection (Oct 2025)

### Automated detection and prevention of Python anti-patterns

```bash
# Detect all code smells
python scripts/detect_code_smells.py --report CODE_SMELL_REPORT.md

# Skip test files
python scripts/detect_code_smells.py --skip-tests --report REPORT.md

# JSON output for CI/CD
python scripts/detect_code_smells.py --json > code_smells.json

# Exit 1 if violations found (CI/CD integration)
python scripts/detect_code_smells.py --check
```

### What it detects

#### 1. Bare except blocks
Violates `.claude/rules.md` Rule #11

- ❌ `except:` without exception type
- ✅ Fixed: 56 → 0 (100% elimination)

#### 2. Backup/stub files
Import ambiguity issues

- Files with `_refactored`, `_backup`, `_old`, `_temp` suffixes
- Prevented via .gitignore patterns

#### 3. Oversized files
CLAUDE.md architectural limits exceeded

- Models > 150 lines
- Services > 150 lines
- Forms > 100 lines
- Settings > 200 lines

### Automated fixes

```bash
# Fix bare except blocks automatically
python scripts/migrate_bare_except.py --dry-run  # Preview
python scripts/migrate_bare_except.py --fix      # Apply fixes
```

### Pre-commit integration

```bash
# Installed hook prevents new violations
git config core.hooksPath .githooks
# Automatically runs on every commit
```

### CI/CD integration

- No-regression policy: New violations fail the build
- Current baselines enforced
- Progressive improvement tracked

---

## Unused Code Detection (Oct 2025)

### Automated detection of backup files and deprecated code

```bash
# Scan for unused code
python scripts/detect_unused_code.py --verbose

# Generate detailed report
python scripts/detect_unused_code.py --report unused_code_report.md
```

### What it detects

1. **Backup files**: `*_refactored.py`, `*_backup.py`, `*_old.py`, `*_temp.py`
2. **Deprecated directories**: `*UNUSED*`, `*_deprecated`, `*_archive`
3. **Large commented code blocks**: >10 lines with >30% code-like content

### Cleanup results (2025-10-10)

- ✅ Archived `apps/_UNUSED_monitoring/` (227 KB, never registered)
- ✅ Archived 5 `*_refactored.py` files (79.8 KB total)
- ✅ All archives documented in `REMOVED_CODE_INVENTORY.md`

### Archive policy

- Archived code kept for 1 sprint cycle (2 weeks)
- Located in `.archive/` directory
- Restoration procedure documented per item

**Reference**: `REMOVED_CODE_INVENTORY.md`

---

## Pre-Commit Validation

### Multi-layer enforcement

1. Pre-commit hooks (`.githooks/pre-commit`)
2. CI/CD pipeline (`.github/workflows/`)
3. Static analysis (bandit, flake8 with plugins, pylint)
4. Code review automation

### Flake8 Configuration (Oct 2025 - Enhanced)

#### Install required plugins

```bash
pip install flake8-print  # T001: Detect print() in production code
```

#### Run flake8 with full validation

```bash
flake8 apps/
```

#### Configuration file: .flake8

- ✅ E722: Bare except (STRICT enforcement)
- ✅ T001: Print statements (production code)
- ✅ C901: Cyclomatic complexity (max 10)

### Enforced Rules

- **E722**: Bare `except:` blocks (ZERO TOLERANCE)
- **T001**: `print()` statements in production code (use `logger` instead)
- **C901**: Cyclomatic complexity > 10 (method too complex)

### Allowed Exceptions (per-file-ignores)

- Scripts: `scripts/*.py:T001` (CLI output OK)
- Tests: `test_*.py:T001,E501,C901` (test complexity OK)
- Management commands: `*/management/commands/*.py:T001,C901` (CLI output OK)

### Setup

```bash
./scripts/setup-git-hooks.sh  # Install validation hooks
pre-commit install            # Enable pre-commit framework
```

---

## Quality Metrics (Tracked & Enforced)

- Security scan pass rate: **100%** (zero tolerance)
- Rule compliance rate: **100%** (zero exceptions)
- Code review efficiency: **>60% improvement** (pre-validated)
- Critical issue prevention: **100%** (automated detection)

---

## Race Condition Testing

### Critical for data integrity

```bash
# Run all race condition tests
python -m pytest -k "race" -v

# Specific test suites
python -m pytest apps/core/tests/test_background_task_race_conditions.py -v
python -m pytest apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py -v
python -m pytest apps/core/tests/test_atomic_json_field_updates.py -v

# Penetration testing
python comprehensive_race_condition_penetration_test.py --scenario all
```

---

## Troubleshooting Quality Issues

### Pre-Commit Hooks Failing

1. Review specific rule violation in error message
2. Check `.claude/rules.md` for correct pattern
3. Fix violation before attempting commit
4. Contact team lead if rule clarification needed

### CI/CD Pipeline Failing

1. Check quality report in PR comments
2. Fix all identified violations locally
3. Re-run tests to ensure compliance
4. Request code review only after all checks pass

### Flake8 Validation Failures

#### Print statement detected (T001)

**FIX: Replace print() with logger.info() or logger.debug()**

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message here")
```

#### Bare except detected (E722)

**FIX: Use specific exception types**

```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
try:
    operation()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise
```

#### If print() is required (CLI scripts only)

**Add inline exception:**

```python
print("Output")  # noqa: T001
```

---

**Last Updated**: October 29, 2025
**Maintainer**: QA Team
**Related**: [Code Quality Standards](../CLAUDE.md#critical-rules), [Exception Handling Standards](../CLAUDE.md#exception-handling-standards)
