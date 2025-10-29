# GraphQL Content Archive

**Archive Date:** 2025-10-29
**Reason:** REST migration completed October 29, 2025
**Related:** REST_API_MIGRATION_COMPLETE.md

---

## Why Archived

The project completed its migration from GraphQL to REST APIs on October 29, 2025. All GraphQL endpoints, middleware, and configuration have been removed from the codebase. This content is preserved for historical reference only.

## What Was Removed

### From CLAUDE.md
- GraphQL configuration sections (~21 references)
- GraphQL security patterns (~60 lines)
- GraphQL validation commands

### From Codebase
- `apps/api/graphql/` directory (complete removal)
- `apps/core/graphql/` directory (complete removal)
- `apps/core/middleware/graphql_*.py` files (6 files)
- `apps/core/management/commands/audit_graphql_security.py`
- `apps/core/management/commands/monitor_graphql_authorization.py`
- `apps/core/management/commands/validate_graphql_config.py`

### Key Removed Middleware
1. `graphql_complexity_validation.py` - Query depth/complexity limits
2. `graphql_csrf_protection.py` - CSRF protection for mutations
3. `graphql_deprecation_tracking.py` - Deprecation monitoring
4. `graphql_origin_validation.py` - Origin header validation
5. `graphql_otel_tracing.py` - OpenTelemetry tracing
6. `graphql_rate_limiting.py` - Rate limiting

## Migration Highlights

### Before (GraphQL)
- Endpoint: `/api/graphql/`
- Multiple queries in single request
- Complex nested queries required depth/complexity validation
- Custom middleware for security

### After (REST)
- Endpoints: `/api/v1/` and `/api/v2/`
- Standard HTTP methods (GET, POST, PUT, DELETE)
- DRF security (throttling, permissions)
- OpenAPI schema generation
- Type-safe contracts with Pydantic

## References in Current CLAUDE.md (To Be Removed)

These sections mention GraphQL and should be removed during optimization:

1. **Line 3**: Context description mentions "GraphQL/REST APIs"
2. **Lines 210-231**: GraphQL Security section (22 lines)
3. **Various**: Scattered mentions throughout (~21 total)

## Restoration

**DO NOT RESTORE.** GraphQL is deprecated technology for this project.

If absolutely needed for historical reference:
```bash
git log --all --full-history -- "**/graphql*"
```

## Current REST API Documentation

See current documentation:
- **OpenAPI Schema:** `http://localhost:8000/api/schema/swagger.json`
- **Interactive Docs:** `http://localhost:8000/api/schema/swagger/`
- **Type-Safe Contracts:** `docs/api-contracts/`
- **Migration Guide:** `REST_API_MIGRATION_COMPLETE.md`

---

**Archived By:** AI Assistant (Claude Code)
**Review Date:** 2026-10-29 (1 year retention)
**Permanent Deletion:** After team review in 2026
