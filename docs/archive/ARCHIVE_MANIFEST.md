# Archive Manifest

**Archive Date:** 2025-10-29
**Reason:** CLAUDE.md optimization project (See: docs/plans/2025-10-29-claude-md-optimization-design.md)

---

## Archived Content

### 1. Original CLAUDE.md Backup
**Location:** `docs/archive/CLAUDE.md.2025-10-29.backup` (to be created during Phase 6)
**Size:** 1,653 lines
**Reason:** Preservation before optimization
**Restore Command:** `cp docs/archive/CLAUDE.md.2025-10-29.backup CLAUDE.md`
**Status:** Pending (will be created during migration phase)

### 2. GraphQL Migration Content
**Location:** `docs/archive/graphql-migration/`
**Reason:** REST migration completed October 29, 2025
**Content:**
- GraphQL configuration sections
- GraphQL security patterns
- GraphQL → REST migration guides
**Restore:** Not recommended (deprecated technology)
**Reference:** See REST_API_MIGRATION_COMPLETE.md for context

### 3. Completed Migrations
**Location:** `docs/archive/migrations/`
**Reason:** Implementation complete, >6 months old, historical reference only
**Content:**
- DateTime refactoring details
- Select2 PostgreSQL migration details
- Other completed database/code migrations
**Restore:** Unlikely needed (final patterns retained in main docs)

### 4. Refactoring Details
**Location:** `docs/archive/refactorings/`
**Reason:** Refactoring complete, historical reference only
**Content:**
- God file refactoring phase details
- schedhuler→scheduler rename details (after deprecation period)
- Code restructuring implementation notes
**Restore:** Historical reference only

---

## Restoration Policy

### When to Restore
- **Never**: GraphQL content (deprecated)
- **Rarely**: Migration details (patterns already in main docs)
- **Emergency Only**: Original CLAUDE.md (rollback scenario)

### How to Restore
Each archived item includes specific restore commands in its directory README.

### Retention Policy
- Archive maintained for **1 year** after archival date
- After 1 year: Team review for permanent deletion
- Critical backups (original CLAUDE.md): Retained indefinitely

---

## Archive Tracking

| Item | Archived Date | Size | Location | Restore Risk |
|------|--------------|------|----------|--------------|
| Original CLAUDE.md | 2025-10-29 | 1,653 lines | CLAUDE.md.2025-10-29.backup | Low |
| GraphQL content | 2025-10-29 | ~60 lines | graphql-migration/ | None |
| Migrations | 2025-10-29 | ~100 lines | migrations/ | Low |
| Refactorings | 2025-10-29 | ~80 lines | refactorings/ | Low |

---

**Maintained By:** Development Team
**Review Cycle:** Annually
**Next Review:** 2026-10-29
