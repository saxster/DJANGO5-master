# Tenant Middleware Migration Guide
**From**: Dual Middleware → **To**: UnifiedTenantMiddleware
**Date**: November 3, 2025
**Impact**: Breaking change - requires configuration update

---

## Overview

This guide helps you migrate from the old dual-middleware setup to the new unified middleware that consolidates all tenant handling into a single source of truth.

### Why Migrate?

**Old Setup Problems**:
- Two middlewares with overlapping responsibilities
- Unclear which one sets what (THREAD_LOCAL.DB vs request.tenant)
- No guaranteed thread-local cleanup
- Cache collision risks
- Code duplication

**New Setup Benefits**:
- Single middleware sets both DB routing AND request context
- Guaranteed cleanup in finally block
- Inactive tenant handling built-in
- Tenant-aware caching
- Comprehensive audit logging
- Type hints throughout

---

## Migration Steps

### Step 1: Update MIDDLEWARE Setting

**File**: `intelliwiz_config/settings/base.py` (or wherever MIDDLEWARE is defined)

**OLD Configuration** (REMOVE):
```python
MIDDLEWARE = [
    # ... other middleware
    'apps.tenants.middlewares.TenantMiddleware',  # ← REMOVE
    'apps.core.middleware.multi_tenant_url.MultiTenantURLMiddleware',  # ← REMOVE
    # ... other middleware
]
```

**NEW Configuration** (ADD):
```python
MIDDLEWARE = [
    # ... other middleware
    'apps.tenants.middleware_unified.UnifiedTenantMiddleware',  # ← ADD THIS
    # ... other middleware
]
```

**Placement Recommendations**:
- **After**: `SecurityMiddleware`, `SessionMiddleware`, `AuthenticationMiddleware`
- **Before**: Application-specific middleware that needs tenant context
- **Before**: View middleware that filters by tenant

---

### Step 2: Update Configuration (Optional)

The UnifiedTenantMiddleware uses the same configuration as the old middlewares:

```python
# settings.py

# Strict mode (default: True in production, False in development)
TENANT_STRICT_MODE = True  # Reject unknown hostnames

# Tenant identification mode
MULTI_TENANT_MODE = 'hostname'  # Options: 'hostname', 'path', 'header', 'jwt', 'auto'

# Require tenant for all requests
MULTI_TENANT_REQUIRE = False  # If True, requests without tenant get 403

# Environment variable for tenant mappings (production)
# TENANT_MAPPINGS='{"prod.example.com": "prod_db", "staging.example.com": "staging_db"}'
```

---

### Step 3: Update Code That Accesses Tenant Context

**Good news**: The new middleware is backward compatible!

**request.tenant** still works exactly as before:
```python
# Views
def my_view(request):
    if request.tenant:
        print(f"Current tenant: {request.tenant.tenant_slug}")

# Templates
{% if request.tenant %}
    <p>Logged in to: {{ request.tenant.tenant_name }}</p>
{% endif %}
```

**THREAD_LOCAL.DB** still works for database routing:
```python
from apps.core.utils_new.db_utils import get_current_db_name

db = get_current_db_name()  # Returns 'intelliwiz_django' etc.
```

---

### Step 4: Run Migrations (if needed)

The new middleware requires `is_active` field on Tenant model:

```bash
# Generate migration
python manage.py makemigrations tenants

# Review migration (should add is_active, suspended_at, suspension_reason)
cat apps/tenants/migrations/0003_add_tenant_state_management.py

# Run migration
python manage.py migrate tenants

# Verify all existing tenants are active
python manage.py shell
>>> from apps.tenants.models import Tenant
>>> Tenant.objects.filter(is_active=False).count()
0  # Should be 0 (all active by default)
```

---

### Step 5: Test Thoroughly

#### Unit Tests:
```bash
# Run tenant tests
pytest apps/tenants/tests/ -v

# Run edge case tests
pytest apps/tenants/tests/test_edge_cases.py -v

# Run cache security tests
pytest apps/core/tests/test_cache_security_comprehensive.py -v
```

#### Manual Testing:
```bash
# Start development server
python manage.py runserver

# Test 1: Valid hostname
curl -H "Host: intelliwiz.youtility.local" http://localhost:8000/api/health/
# Should work

# Test 2: Unknown hostname (strict mode)
curl -H "Host: unknown.example.com" http://localhost:8000/api/health/
# Should return 403 Forbidden

# Test 3: Tenant headers
curl -H "X-Tenant-Slug: intelliwiz-django" http://localhost:8000/api/health/
# Should work if MULTI_TENANT_MODE includes 'header'
```

#### Check Response Headers:
```bash
curl -I -H "Host: intelliwiz.youtility.local" http://localhost:8000/
# Should include:
# X-Tenant-Slug: intelliwiz-django
# X-Tenant-ID: 1
# X-DB-Alias: intelliwiz_django
```

---

## Breaking Changes

### 1. Tenant Context Always Set (if middleware matches)

**OLD**: `request.tenant` might be None even for valid tenants
**NEW**: `request.tenant` is TenantContext object OR None (explicit)

**Migration**: No code changes needed (already checking `if request.tenant`)

### 2. Inactive Tenants Return 410 Gone

**OLD**: Inactive tenants might still work (no validation)
**NEW**: Inactive tenants return `410 Gone` HTTP status

**Impact**: Clients must handle 410 status code
**Migration**: Add client-side handling:
```javascript
if (response.status === 410) {
    alert("Your account has been suspended. Please contact support.");
}
```

### 3. Thread-Local Always Cleaned Up

**OLD**: Thread-local might leak between requests
**NEW**: Cleanup guaranteed in finally block

**Impact**: More predictable behavior in production
**Migration**: No code changes needed

---

## Rollback Procedure

If you need to rollback to old middlewares:

```python
# settings.py
MIDDLEWARE = [
    # Restore old middlewares
    'apps.tenants.middlewares.TenantMiddleware',
    'apps.core.middleware.multi_tenant_url.MultiTenantURLMiddleware',
]
```

**Note**: The old middlewares still work but don't have the improvements.

---

## Feature Comparison

| Feature | Old (Dual Middleware) | New (Unified) |
|---------|----------------------|---------------|
| Sets THREAD_LOCAL.DB | ✅ TenantMiddleware only | ✅ Always |
| Sets request.tenant | ✅ MultiTenantURL only | ✅ Always |
| Thread-local cleanup | ❌ Not guaranteed | ✅ Always (finally block) |
| Inactive tenant handling | ❌ No | ✅ 410 Gone response |
| Tenant-aware caching | ⚠️ Partial | ✅ Full |
| Multiple ID strategies | ⚠️ Scattered | ✅ Unified |
| Audit logging | ⚠️ Inconsistent | ✅ Comprehensive |
| Type hints | ❌ No | ✅ Yes |
| Cache collision prevention | ❌ Possible | ✅ Prevented |

---

## Advanced Configuration

### Multiple Tenant Identification Strategies

Set `MULTI_TENANT_MODE = 'auto'` to try all strategies in order:

```python
# settings.py
MULTI_TENANT_MODE = 'auto'  # Try hostname → path → header → JWT

# Priority order:
# 1. Hostname mapping (e.g., tenant1.example.com)
# 2. URL path (e.g., /t/tenant1/operations/)
# 3. HTTP header (X-Tenant-Slug)
# 4. JWT claim (tenant_slug)
```

### Custom Tenant Resolution

If you need custom tenant resolution logic:

```python
# apps/tenants/middleware_custom.py
from apps.tenants.middleware_unified import UnifiedTenantMiddleware

class CustomTenantMiddleware(UnifiedTenantMiddleware):
    def _extract_tenant(self, request):
        # Your custom logic here
        # Example: Extract from API key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            # Look up tenant from API key
            pass

        # Fallback to parent implementation
        return super()._extract_tenant(request)
```

---

## Troubleshooting

### Issue: 403 Forbidden on valid hostnames

**Cause**: Hostname not in TENANT_MAPPINGS

**Solution**:
```bash
# Add to environment variable
export TENANT_MAPPINGS='{"yourhost.example.com": "your_db_alias", ...}'

# Or add to allowlist for development
export TENANT_UNKNOWN_HOST_ALLOWLIST="yourhost.example.com,localhost"
```

### Issue: 410 Gone unexpectedly

**Cause**: Tenant was suspended

**Solution**:
```python
# Reactivate tenant
python manage.py shell
>>> from apps.tenants.models import Tenant
>>> tenant = Tenant.objects.get(subdomain_prefix='yourslug', is_active=False)
>>> tenant.activate()
```

### Issue: Import errors

**Cause**: Circular dependency in old code

**Solution**:
```python
# Use lazy imports in models/managers
from django.apps import apps as django_apps
Tenant = django_apps.get_model('tenants', 'Tenant')
```

---

## Verification Checklist

After migration, verify:

- [ ] Middleware in correct order in settings.py
- [ ] Old middlewares removed from MIDDLEWARE list
- [ ] `python manage.py check` passes
- [ ] Migration created and applied for is_active field
- [ ] Tests passing: `pytest apps/tenants/tests/ -v`
- [ ] Manual testing with different hostnames works
- [ ] Response headers include X-Tenant-* headers
- [ ] Thread-local cleaned up (check with debugger)
- [ ] Cache keys are tenant-prefixed (check Redis)
- [ ] Inactive tenants return 410 Gone

---

## Support

**Questions?**
- Check: `MULTI_TENANCY_COMPREHENSIVE_RESOLUTION_STATUS.md`
- Review: `MULTI_TENANCY_SECURITY_AUDIT_REPORT.md`
- See: `apps/tenants/middleware_unified.py` source code

**Issues?**
- Rollback to old middlewares
- Check logs: `tail -f /var/log/django/tenants.log`
- Run verification script: `python scripts/verify_tenant_setup.py`

---

**Migration Guide Version**: 1.0
**Last Updated**: 2025-11-03
**Next Review**: After production deployment
