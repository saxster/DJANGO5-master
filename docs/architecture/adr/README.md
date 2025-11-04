# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) documenting significant architectural decisions made for the Django 5 Enterprise Platform.

## What are ADRs?

Architecture Decision Records document the key decisions made during development, including:
- **Context:** Why the decision was needed
- **Decision:** What was decided
- **Consequences:** Trade-offs and impacts

## ADR Index

### Active ADRs

| ADR | Title | Status | Date | Summary |
|-----|-------|--------|------|---------|
| [001](001-file-size-limits.md) | File Size Limits | Accepted | 2025-11-04 | Enforce strict file size limits (Settings <200, Models <150, Views <30 lines) to prevent god files and improve maintainability |
| [002](002-no-circular-dependencies.md) | No Circular Dependencies | Accepted | 2025-11-04 | Prohibit circular dependencies using string references, TYPE_CHECKING, and dependency injection patterns |
| [003](003-service-layer-pattern.md) | Service Layer Pattern | Accepted | 2025-11-04 | Separate business logic (services) from HTTP handling (views) for testability and reusability |
| [004](004-test-coverage-requirements.md) | Test Coverage Requirements | Accepted | 2025-11-04 | Enforce minimum test coverage: Security-critical 90%, Business-critical 85%, User-facing 80% |
| [005](005-exception-handling-standards.md) | Exception Handling Standards | Accepted | 2025-11-04 | Require specific exception types (no generic `except Exception`) with proper logging and error handling |

## ADR Status

- **Proposed:** Under discussion
- **Accepted:** Approved and being implemented
- **Deprecated:** No longer valid
- **Superseded:** Replaced by another ADR

## Creating New ADRs

### When to Create an ADR

Create an ADR for:
- Significant architectural changes
- Technology choices (frameworks, libraries)
- Coding standards that impact the entire codebase
- Security or performance decisions
- Changes to development workflows

### ADR Template

```markdown
# ADR XXX: Title

**Status:** Proposed | Accepted | Deprecated | Superseded

**Date:** YYYY-MM-DD

**Deciders:** Team members involved

**Related:**
- Links to related ADRs, code, or documentation

---

## Context

What is the issue we're facing? What are the constraints?

## Decision

What decision did we make?

## Consequences

What are the positive and negative consequences of this decision?

### Positive
- ✅ Benefit 1
- ✅ Benefit 2

### Negative
- ❌ Trade-off 1
- ❌ Trade-off 2

### Mitigation Strategies
- How we address negative consequences

---

## References

- Links to relevant resources

---

**Last Updated:** YYYY-MM-DD
**Next Review:** YYYY-MM-DD
```

### ADR Numbering

- Use sequential numbers: 001, 002, 003, etc.
- Don't reuse numbers from deprecated ADRs
- Update this README when adding new ADRs

## Related Documentation

- [.claude/rules.md](../../../.claude/rules.md) - Coding rules and standards
- [REFACTORING_PATTERNS.md](../REFACTORING_PATTERNS.md) - God file refactoring patterns
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) - Overall system architecture
- [GOD_FILE_REFACTORING_GUIDE.md](../GOD_FILE_REFACTORING_GUIDE.md) - Historical refactoring guide

## Review Schedule

ADRs should be reviewed:
- When the decision is first implemented
- After 3 months of implementation
- When significant issues arise
- During quarterly architecture reviews

---

**Last Updated:** 2025-11-04
**Maintainer:** Development Team
