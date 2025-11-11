# Deprecated Tenant Middleware

**Date Deprecated**: 2025-11-11
**Replaced By**: `apps.tenants.middleware_unified.UnifiedTenantMiddleware`
**Status**: Backward compatibility shim in place

---

## Summary

The original `apps/tenants/middlewares.py` (247 lines) has been deprecated in favor of the comprehensive `apps/tenants/middleware_unified.py` (421 lines).

The old middleware file has been archived to `.deprecated/tenants/middlewares.py` for historical reference.

---

## What Changed

### Old Implementation (`middlewares.py`)

**Components:**
- `TenantMiddleware` - Basic tenant routing via hostname
- `TenantDbRouter` - Database routing based on thread-local context

**Features:**
- Single resolution strategy (hostname mapping only)
- Basic 403 Forbidden for unknown hostnames
- No request.tenant attribute
- No caching
- No inactive tenant handling

**Limitations:**
- Only supports hostname-based tenant identification
- No path-based routing (`/t/{tenant_slug}/`)
- No header-based routing (`X-Tenant-ID`, `X-Tenant-Slug`)
- No JWT claim support
- Limited debugging capabilities
- No differentiation between "tenant not found" vs "tenant suspended"

### New Implementation (`middleware_unified.py`)

**Components:**
- `UnifiedTenantMiddleware` - Comprehensive tenant context management
- `TenantContext` - Structured tenant information container
- `TenantDbRouter` - Unchanged (still used for database routing)

**Enhanced Features:**
1. **Multiple Resolution Strategies:**
   - Hostname mapping (original behavior)
   - URL path extraction (`/t/{tenant_slug}/`)
   - HTTP headers (`X-Tenant-ID`, `X-Tenant-Slug`)
   - JWT claims (`tenant_id`, `tenant_slug`)

2. **Request Context Injection:**
   - Sets `request.tenant` attribute for views/templates
   - Provides `TenantContext` object with pk, slug, name, db_alias

3. **Comprehensive Caching:**
   - 1-hour tenant lookup cache
   - Reduces database queries for tenant resolution
   - Cache key includes hostname for uniqueness

4. **Better Inactive Tenant Handling:**
   - Returns `410 Gone` for suspended tenants (not 403)
   - Includes suspension reason and timestamp in logs
   - Differentiates "not found" from "suspended"

5. **Debugging Features:**
   - Response headers: `X-Tenant-Slug`, `X-Tenant-ID`, `X-DB-Alias`
   - Comprehensive audit logging
   - Security event tracking

6. **Configuration Options:**
   - `TENANT_STRICT_MODE` - Reject unknown hostnames (default: True in production)
   - `MULTI_TENANT_MODE` - Resolution strategy ('hostname', 'path', 'header', 'jwt', 'auto')
   - `MULTI_TENANT_REQUIRE` - Require tenant context for all requests (default: False)

---

## Migration Path

### Settings Update

**Before:**
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.tenants.middlewares.TenantMiddleware',  # OLD
    # ... other middleware
]
```

**After:**
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.tenants.middleware_unified.UnifiedTenantMiddleware',  # NEW
    # ... other middleware
]
```

**Database Router (No Change Required):**
```python
DATABASE_ROUTERS = ["apps.tenants.middlewares.TenantDbRouter"]
```
The deprecation shim re-exports `TenantDbRouter`, so no settings changes needed.

### Code Updates

**Before:**
```python
from apps.tenants.middlewares import TenantMiddleware
```

**After:**
```python
from apps.tenants.middleware_unified import UnifiedTenantMiddleware
```

**Accessing Tenant in Views:**

**New capability (not available in old middleware):**
```python
def my_view(request):
    if hasattr(request, 'tenant'):
        tenant_slug = request.tenant.tenant_slug
        tenant_name = request.tenant.tenant_name
        db_alias = request.tenant.db_alias
```

---

## Backward Compatibility

### Deprecation Shim

A compatibility shim has been placed at `apps/tenants/middlewares.py` that:
1. Emits a `DeprecationWarning` when imported
2. Re-exports `UnifiedTenantMiddleware` as `TenantMiddleware`
3. Re-exports `TenantDbRouter` (unchanged)
4. Re-exports `THREAD_LOCAL` from `apps.core.utils_new.db_utils`

This ensures existing code continues to work without modification.

### Test Compatibility

The following test files currently import the old middleware:
- `apps/core/tests/test_multi_tenant_integration.py`
- `apps/tenants/tests/test_admin.py`
- `apps/tenants/tests/test_security_penetration.py`
- `apps/tenants/tests/test_tenant_isolation.py`
- `apps/tenants/tests/test_models.py`
- `apps/tenants/tests/test_edge_cases.py`
- `apps/tenants/tests/test_middlewares.py`
- `apps/tenants/tests.py`

These imports will continue to work but will emit deprecation warnings. Tests should be updated to import from `middleware_unified.py` in future refactoring.

---

## Removal Timeline

**Phase 1 (Current)**: Deprecation shim in place, warnings emitted
**Phase 2 (Q1 2026)**: Update all test imports to use `middleware_unified`
**Phase 3 (Q2 2026)**: Remove deprecation shim, force migration

---

## Historical Context

### Why Was This Middleware Created?

The original `TenantMiddleware` was created to support multi-tenant database routing based on hostname mappings. It worked well for simple hostname-based tenant identification but lacked flexibility for:
- Multi-region deployments (path-based routing)
- API integrations (header-based routing)
- Mobile apps (JWT-based routing)
- Debugging and monitoring
- Graceful handling of suspended/inactive tenants

### Why Was It Replaced?

The `UnifiedTenantMiddleware` was created as part of the "Multi-Tenancy Hardening - Comprehensive Resolution" initiative (2025-11-03) to:
1. Consolidate two separate middleware classes (`TenantMiddleware` + `MultiTenantURLMiddleware`)
2. Add support for multiple tenant resolution strategies
3. Improve debugging capabilities with request attributes and response headers
4. Better handle edge cases (suspended tenants, inactive tenants, unknown tenants)
5. Add caching to reduce database load
6. Provide more configuration options for different deployment scenarios

---

## References

- **New Implementation**: `apps/tenants/middleware_unified.py`
- **Archived Implementation**: `.deprecated/tenants/middlewares.py`
- **Deprecation Shim**: `apps/tenants/middlewares.py`
- **Database Router**: Still uses `TenantDbRouter` (unchanged)
- **Settings Reference**: `intelliwiz_config/settings/middleware.py`

---

**Last Updated**: 2025-11-11
**Maintainer**: Development Team
**Related ADRs**: None (pre-dates ADR process)
