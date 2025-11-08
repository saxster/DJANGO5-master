# Print Statement Removal Guide

> **Purpose**: Automated detection and removal of production `print()` statements, replacing them with proper logging calls.

---

## Table of Contents

- [Overview](#overview)
- [Why Remove Print Statements](#why-remove-print-statements)
- [Available Scripts](#available-scripts)
- [Usage Workflow](#usage-workflow)
- [Example Transformations](#example-transformations)
- [Safety Features](#safety-features)
- [Troubleshooting](#troubleshooting)

---

## Overview

Found 251 `print()` statements in production code across the codebase. These should be replaced with `logger.info()` or `logger.debug()` calls for proper production logging.

**Current Status**:
- **173 print statements** detected in production code (excluding tests, migrations, scripts)
- **19 files** identified for modification
- **16 files** have syntax errors and need manual fixing first
- **2 files** are safe to modify immediately

---

## Why Remove Print Statements

### Problems with Print Statements

1. **No Log Levels**: Can't distinguish between debug, info, warning, or error messages
2. **No Structured Logging**: Can't parse or filter messages programmatically
3. **No Context**: Missing timestamps, module names, correlation IDs
4. **Performance**: Blocking I/O operations in production
5. **Lost Messages**: STDOUT not captured in production environments
6. **No Rotation**: No log file management or archival
7. **Security**: May expose sensitive data without audit trail

### Benefits of Proper Logging

1. **Configurable Levels**: Control verbosity per environment
2. **Structured Output**: JSON formatting for log aggregation
3. **Context-Rich**: Automatic timestamps, module names, stack traces
4. **Centralized**: Integration with ELK, Datadog, CloudWatch
5. **Auditable**: Proper audit trails for compliance
6. **Searchable**: Easy querying and filtering
7. **Performant**: Async handlers, buffering, rotation

---

## Available Scripts

### 1. Syntax Error Checker (`check_syntax_errors.py`)

**Purpose**: Identify files with existing syntax errors that must be fixed first.

```bash
# Check for syntax errors
python scripts/check_syntax_errors.py

# Verbose mode
python scripts/check_syntax_errors.py --verbose

# Check specific directory
python scripts/check_syntax_errors.py --directory apps/core
```

**Output Example**:
```
================================================================================
PYTHON SYNTAX ERROR REPORT
================================================================================

STATISTICS
--------------------------------------------------------------------------------
Total files scanned:  2753
Files skipped:        0
Valid files:          2737
Files with errors:    16

FILES WITH SYNTAX ERRORS
--------------------------------------------------------------------------------

Invalid Syntax (7 files):
--------------------------------------------------------------------------------
  /path/to/file.py
    Line 167: invalid syntax. Maybe you meant '==' or ':=' instead of '='?
```

### 2. Print Statement Remover (`remove_production_prints.py`)

**Purpose**: Automatically detect and replace print() statements with logger calls.

```bash
# Preview changes (dry run - safe, no modifications)
python scripts/remove_production_prints.py --dry-run

# Preview with detailed report
python scripts/remove_production_prints.py --dry-run --report /tmp/print_report.txt

# Apply changes (after reviewing dry run)
python scripts/remove_production_prints.py --apply

# Apply with report
python scripts/remove_production_prints.py --apply --report /tmp/print_report.txt

# Validate syntax after changes
python scripts/remove_production_prints.py --validate

# Rollback changes if issues found
python scripts/remove_production_prints.py --rollback

# Clean up backup files after successful changes
python scripts/remove_production_prints.py --cleanup-backups

# Scan specific directory
python scripts/remove_production_prints.py --dry-run --directory apps/core
```

---

## Usage Workflow

### Phase 1: Initial Assessment

```bash
# Step 1: Check for syntax errors
python scripts/check_syntax_errors.py

# Step 2: Preview print statement changes
python scripts/remove_production_prints.py --dry-run --report /tmp/print_report.txt

# Step 3: Review the report
cat /tmp/print_report.txt
```

### Phase 2: Fix Syntax Errors (if any)

If `check_syntax_errors.py` found issues:

1. **Review the syntax error report**
2. **Fix each file manually** (sorted by error type for easier triage)
3. **Re-run syntax checker** to verify fixes

```bash
# After fixing syntax errors, verify
python scripts/check_syntax_errors.py
```

### Phase 3: Apply Print Statement Removal

Once all syntax errors are fixed:

```bash
# Step 1: Final dry run to confirm changes
python scripts/remove_production_prints.py --dry-run

# Step 2: Apply changes
python scripts/remove_production_prints.py --apply --report /tmp/final_report.txt

# Step 3: Validate syntax of modified files
python scripts/remove_production_prints.py --validate

# Step 4: Run tests to verify no breakage
python -m pytest apps/ --tb=short -v

# Step 5: If all tests pass, clean up backups
python scripts/remove_production_prints.py --cleanup-backups
```

### Phase 4: Handle Rollback (if needed)

If issues are detected after applying changes:

```bash
# Rollback all changes using backup files
python scripts/remove_production_prints.py --rollback

# Fix issues manually

# Re-run from Phase 3
```

---

## Example Transformations

### Simple String Literal

**Before**:
```python
print("Processing user data")
```

**After**:
```python
import logging

logger = logging.getLogger(__name__)

logger.info("Processing user data")
```

### F-String with Variable

**Before**:
```python
print(f"Task completed: {task_id}")
```

**After**:
```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Task completed: {task_id}")
```

### Multiple Arguments

**Before**:
```python
print("Processing user", user.id, "status:", status)
```

**After**:
```python
import logging

logger = logging.getLogger(__name__)

logger.info("Processing user %s status: %s", user.id, status)
```

### Exception Handling

**Before**:
```python
try:
    process_data()
except Exception as e:
    print(f"Error: {e}")
```

**After**:
```python
import logging

logger = logging.getLogger(__name__)

try:
    process_data()
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
```

### Debug Information

**Before**:
```python
print(f"[DEBUG] Query returned {len(results)} results")
```

**After**:
```python
import logging

logger = logging.getLogger(__name__)

logger.debug(f"Query returned {len(results)} results")
```

---

## Safety Features

### Automatic Backups

- Creates `.bak` files before any modifications
- Preserves original file permissions and timestamps
- Can be rolled back with `--rollback` command

### Syntax Validation

- Validates generated code with AST parser
- Rejects changes that produce invalid syntax
- Reports validation errors before applying

### Skip Patterns

Automatically skips:
- Test files (`test_*.py`, `*_test.py`, `tests/`)
- Migration files (`migrations/`)
- Scripts directory (`scripts/`)
- Virtual environments (`venv/`, `.venv/`)
- Hidden directories (`.git/`, etc.)

### Logging Import Management

- Detects existing `logging` imports
- Adds imports only if missing
- Inserts at proper location (after module docstring and other imports)
- Preserves existing logging configuration

---

## Files Identified for Modification

### Production Code (Safe to Modify)

Once syntax errors are fixed, these files can be safely modified:

1. `apps/activity/managers/job/list_view_manager.py` - 1 print
2. `apps/client_onboarding/management/commands/init_intelliwiz.py` - 6 prints
3. `apps/client_onboarding/managers.py` - 1 print
4. `apps/core/management/commands/analyze_imports.py` - 5 prints
5. `apps/core/management/commands/rate_limit_report.py` - 1 print
6. `apps/core/management/commands/validate_ia.py` - 1 print
7. `apps/core/middleware/ia_tracking.py` - 10 prints
8. `apps/core/services/sql_injection_scanner.py` - 7 prints
9. `apps/core/testing/sync_test_framework.py` - 5 prints
10. `apps/core/utils_new/key_strength_analyzer.py` - 16 prints
11. `apps/core/utils_new/query_optimizer.py` - 5 prints
12. `apps/core/utils_new/security/entropy.py` - 16 prints
13. `apps/core/validate_queries.py` - 64 prints (utility script)
14. `apps/help_center/verify_deployment.py` - 19 prints (deployment script)
15. `apps/noc/nl_query_examples.py` - 5 prints
16. `apps/onboarding_api/utils/logging_validation.py` - 2 prints
17. `apps/ontology/mcp/run_server.py` - 1 print
18. `apps/streamlab/views.py` - 2 prints
19. `apps/y_helpdesk/helpdesk_nl_query_examples.py` - 6 prints

### Files Needing Manual Fix First

**Invalid Syntax (7 files)**:
- `apps/core/services/redis_backup_service.py` - Line 167
- `apps/core/services/sync_metrics_collector.py` - Line 108
- `apps/core/startup_checks.py` - Line 151
- `apps/core/views/database_performance_dashboard.py` - Line 45
- `apps/helpbot/signals.py` - Line 37
- `apps/ml_training/views.py` - Line 33
- `apps/noc/services/query_cache.py` - Line 136

**F-string Errors (2 files)**:
- `apps/activity/views/vehicle_entry_views.py` - Line 121
- `apps/activity/views/meter_reading_views.py` - Line 122

**Indentation Errors (6 files)**:
- `apps/attendance/services/bulk_roster_service.py` - Line 181
- `apps/core/tests/test_transaction_management.py` - Line 93
- `apps/core/tests/test_transaction_race_conditions.py` - Line 80
- `apps/core/utils_new/data_extractors/bu_extractor.py` - Line 11
- `apps/core/utils_new/data_extractors/questionset_extractor.py` - Line 12
- `apps/core/utils_new/data_extractors/typeassist_extractor.py` - Line 11

**Expected Token Missing (1 file)**:
- `apps/core/views/celery_monitoring_views.py` - Line 428

---

## Troubleshooting

### Issue: Script Reports Syntax Errors

**Symptom**: `check_syntax_errors.py` finds files with syntax errors.

**Solution**:
1. Review the error report to see error types
2. Fix each file manually (errors are grouped by type for easier triage)
3. Re-run syntax checker to verify fixes
4. Once all syntax errors are fixed, proceed with print removal

### Issue: Generated Code Has Invalid Syntax

**Symptom**: Script reports "Generated invalid syntax" during dry run.

**Cause**: File has complex print statements or existing syntax issues.

**Solution**:
1. Script automatically skips these files
2. Review the file manually
3. Fix syntax issues first
4. Re-run the script

### Issue: Changes Break Tests

**Symptom**: Tests fail after applying print removal.

**Solution**:
1. Rollback changes: `python scripts/remove_production_prints.py --rollback`
2. Review failing test output
3. Fix underlying issues
4. Re-run from Phase 3

### Issue: Backup Files Not Cleaned

**Symptom**: `.bak` files remain after successful changes.

**Solution**:
```bash
# Clean up backup files
python scripts/remove_production_prints.py --cleanup-backups

# Or manually
find apps -name "*.py.bak" -delete
```

### Issue: Need to Modify Specific Files Only

**Symptom**: Want to target specific files/directories.

**Solution**:
```bash
# Target specific directory
python scripts/remove_production_prints.py --dry-run --directory apps/core

# For single file, edit manually
```

---

## Best Practices

### 1. Always Run Dry Run First

```bash
# ALWAYS preview changes before applying
python scripts/remove_production_prints.py --dry-run
```

### 2. Fix Syntax Errors First

```bash
# Check for syntax errors before print removal
python scripts/check_syntax_errors.py
```

### 3. Run Tests After Changes

```bash
# Verify no breakage
python -m pytest apps/ --tb=short -v
```

### 4. Review Report Before Applying

```bash
# Save report for review
python scripts/remove_production_prints.py --dry-run --report /tmp/report.txt
cat /tmp/report.txt
```

### 5. Keep Backups Until Tests Pass

```bash
# Only cleanup after verifying tests pass
python -m pytest apps/
python scripts/remove_production_prints.py --cleanup-backups
```

---

## Next Steps

1. **Run syntax checker** to identify files needing manual fixes
2. **Fix syntax errors** in the 16 files identified
3. **Re-run syntax checker** to verify fixes
4. **Run print remover in dry-run mode** to preview changes
5. **Apply changes** once confident
6. **Validate and test** to ensure no breakage
7. **Clean up backups** after successful verification

---

**Last Updated**: November 5, 2025
**Maintainer**: Development Team
**Related Docs**:
- `.claude/rules.md` - Code quality standards
- `docs/testing/TESTING_AND_QUALITY_GUIDE.md` - Testing standards
- `docs/architecture/REFACTORING_PATTERNS.md` - Refactoring guidelines
