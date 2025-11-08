# Print Statement Removal - Quick Reference

## Quick Start

```bash
# 1. Check for syntax errors first
python scripts/check_syntax_errors.py

# 2. Preview changes (safe, no modifications)
python scripts/remove_production_prints.py --dry-run

# 3. Apply changes (after review)
python scripts/remove_production_prints.py --apply

# 4. Validate syntax
python scripts/remove_production_prints.py --validate

# 5. Run tests
python -m pytest apps/ --tb=short -v

# 6. Clean up backups (after tests pass)
python scripts/remove_production_prints.py --cleanup-backups
```

## Common Commands

### Syntax Checking
```bash
# Check entire apps/ directory
python scripts/check_syntax_errors.py

# Check specific directory
python scripts/check_syntax_errors.py --directory apps/core

# Verbose output
python scripts/check_syntax_errors.py --verbose
```

### Print Removal
```bash
# Dry run with report
python scripts/remove_production_prints.py --dry-run --report /tmp/report.txt

# Apply changes with report
python scripts/remove_production_prints.py --apply --report /tmp/report.txt

# Rollback changes
python scripts/remove_production_prints.py --rollback

# Validate modified files
python scripts/remove_production_prints.py --validate

# Clean up backup files
python scripts/remove_production_prints.py --cleanup-backups
```

## Current Status

**Total print statements found**: 173 (in production code)
**Files to modify**: 19
**Files with syntax errors**: 16 (need manual fixing first)
**Safe to modify now**: 2 files

### Files Safe to Modify Now

1. `apps/streamlab/views.py` - 2 prints
2. `apps/core/management/commands/validate_ia.py` - 1 print

### Files Needing Manual Fix First

**Syntax Errors (16 files)**:
- 7 files with invalid syntax (mostly walrus operator issues)
- 2 files with f-string errors
- 6 files with indentation errors
- 1 file with missing except/finally block

See full list in `/tmp/print_removal_report.txt`

## Safety Features

- ✅ **Automatic backups** (`.bak` files)
- ✅ **Syntax validation** (AST parser)
- ✅ **Rollback capability** (`--rollback`)
- ✅ **Dry-run mode** (preview before applying)
- ✅ **Skip patterns** (tests, migrations, scripts)

## What It Does

Transforms:
```python
# BEFORE
print(f"Processing user {user_id}")

# AFTER
import logging
logger = logging.getLogger(__name__)
logger.info(f"Processing user {user_id}")
```

## Documentation

Full documentation: `docs/tools/PRINT_STATEMENT_REMOVAL_GUIDE.md`

## Workflow

1. **Check syntax** → Fix errors if found
2. **Dry run** → Review changes
3. **Apply** → Make changes
4. **Validate** → Check syntax
5. **Test** → Run test suite
6. **Cleanup** → Remove backups

## Help

```bash
python scripts/check_syntax_errors.py --help
python scripts/remove_production_prints.py --help
```
