# Archived Scripts

## Purpose

This directory contains scripts that have completed their purpose but are preserved for reference or historical value.

## Directory Structure

### 2025-11-obsolete/
**One-time migration scripts that have completed their purpose.**

Scripts in this directory:
- Exception handling migrations (Phase 1-3 complete - 100% remediation)
- IA database migrations (deprecated architecture)
- Database cleanup scripts (migrations applied)
- Legacy deployment scripts (replaced by current workflows)

**Retention Policy**: Safe to delete after 90 days (March 2026) if no issues arise.

### 2025-11-reference/
**Completed migrations kept for reference patterns.**

Scripts in this directory:
- Code quality migration patterns (magic numbers, nesting, N+1 optimization)
- Form refactoring scripts (god file splitting examples)
- Feature validation scripts (features now in production)
- Admin optimization patterns
- Testing framework examples

**Retention Policy**: Keep indefinitely - valuable patterns for future work.

## Why Archive Instead of Delete?

1. **Historical Context**: Understand what changes were made and why
2. **Pattern Reference**: Reusable patterns for future migrations
3. **Troubleshooting**: Reference if similar issues arise
4. **Audit Trail**: Complete record of system evolution

## Archive Criteria

Scripts are archived when they meet ALL these criteria:
- Purpose completed (migration done, feature validated, etc.)
- No longer referenced in active code or documentation
- Not used in CI/CD pipelines
- Historical or reference value for future work

## Restoration

If you need to restore a script from archive:
```bash
# Move back to scripts/
mv scripts/.archive/[subdirectory]/[script_name] scripts/

# Update any documentation references
# Verify script still works with current codebase
```

---

**Archive Created**: November 11, 2025
**Archived By**: Comprehensive Cruft Removal - Phase 3
**Total Scripts Archived**: 11 scripts
