# Multi-Tenancy Developer Quick Reference
**Last Updated**: November 3, 2025
**Version**: 2.0 (Post-Comprehensive Resolution)

---

## 🚀 **Quick Start** (30 seconds)

### Creating a Tenant-Aware Model:

```python
from django.db import models
from apps.tenants.models import TenantAwareModel
from apps.tenants.managers import TenantAwareManager

class MyModel(TenantAwareModel):
    objects = TenantAwareManager()  # ← REQUIRED!

    name = models.CharField(max_length=100)

    class Meta:
        unique_together = [('tenant', 'name')]  # Recommended
```

**⚠️ CRITICAL**: Always declare `objects = TenantAwareManager()` or queries won't filter by tenant!

---

## 📖 **Common Patterns**

### Pattern 1: Accessing Current Tenant

```python
# In views
def my_view(request):
    if request.tenant:
        print(f"Current tenant: {request.tenant.tenant_slug}")
        print(f"Tenant name: {request.tenant.tenant_name}")
        print(f"Tenant PK: {request.tenant.tenant_pk}")

# In models/services
from apps.tenants.utils import get_tenant_from_context

tenant = get_tenant_from_context()
if tenant:
    my_object.tenant = tenant
```

### Pattern 2: Tenant-Aware Caching

```python
# ✅ CORRECT: Use tenant_cache
from apps.core.cache.tenant_aware import tenant_cache

tenant_cache.set('user:123:profile', data, timeout=3600)
value = tenant_cache.get('user:123:profile')

# ❌ WRONG: Don't use raw cache (cross-tenant collision risk)
from django.core.cache import cache  # NO!
cache.set('user:123:profile', data)  # Keys not tenant-scoped!
```

### Pattern 3: Cross-Tenant Queries (Rare)

```python
# Cross-tenant queries are AUDIT LOGGED
from apps.helpbot.models import HelpBotSession

# Only for admin/reporting - logged with stack trace
all_sessions = HelpBotSession.objects.cross_tenant_query()

# Explicit tenant filtering
tenant_a_sessions = HelpBotSession.objects.for_tenant(tenant_pk=1)
```

### Pattern 4: Saving Without Tenant (Global Records)

```python
# For global/system records only
from apps.core.models import GlobalConfig

config = GlobalConfig(setting='value')
config.save(skip_tenant_validation=True)
```

---

## 🔧 **Utilities Reference**

### Conversion Functions:

```python
from apps.tenants.utils import db_alias_to_slug, slug_to_db_alias

# Underscore → Hyphen
db_alias_to_slug('intelliwiz_django')  # Returns: 'intelliwiz-django'

# Hyphen → Underscore
slug_to_db_alias('intelliwiz-django')  # Returns: 'intelliwiz_django'
```

### Tenant Lookup Functions:

```python
from apps.tenants.utils import (
    get_tenant_from_context,
    get_current_tenant_cached,
    get_tenant_by_slug,
    get_tenant_by_pk
)

# From thread-local context (current request)
tenant = get_tenant_from_context()

# Cached version (better performance)
tenant = get_current_tenant_cached()

# By slug
tenant = get_tenant_by_slug('intelliwiz-django')

# By primary key
tenant = get_tenant_by_pk(1)

# Include inactive tenants (admin only)
tenant = get_tenant_by_slug('suspended-tenant', include_inactive=True)
```

### Validation Functions:

```python
from apps.tenants.utils import is_valid_tenant_slug

if is_valid_tenant_slug('my-tenant-123'):
    # Valid: lowercase, numbers, hyphens only
    pass
```

---

## 🏗️ **Middleware Configuration**

### Option 1: Unified Middleware (RECOMMENDED)

```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.tenants.middleware_unified.UnifiedTenantMiddleware',  # ← ADD THIS
    # ... rest of middleware
]

# Configuration
MULTI_TENANT_MODE = 'hostname'  # or 'path', 'header', 'jwt', 'auto'
TENANT_STRICT_MODE = True  # Reject unknown hostnames in production
```

### Option 2: Dual Middleware (Legacy)

```python
# If not ready to migrate to unified
MIDDLEWARE = [
    # ...
    'apps.tenants.middlewares.TenantMiddleware',
    'apps.core.middleware.multi_tenant_url.MultiTenantURLMiddleware',
    # ...
]
```

---

## 🧪 **Testing Patterns**

### Testing Tenant-Aware Code:

```python
import pytest
from apps.tenants.models import Tenant
from apps.core.utils_new.db_utils import set_db_for_router
from apps.tenants.utils import cleanup_tenant_context

@pytest.fixture
def tenant_context(db):
    """Fixture to set tenant context for tests."""
    tenant = Tenant.objects.create(
        tenantname="Test Tenant",
        subdomain_prefix="test-tenant"
    )
    set_db_for_router('test_tenant')
    yield tenant
    cleanup_tenant_context()

def test_my_feature(tenant_context):
    """Test with tenant context set."""
    from apps.helpbot.models import HelpBotSession

    # Queries automatically filtered by tenant
    sessions = HelpBotSession.objects.all()
    assert sessions.count() == 0  # Only this tenant's sessions
```

---

## 🔍 **Debugging Guide**

### Check Current Tenant Context:

```python
# In Django shell or view
from apps.core.utils_new.db_utils import get_current_db_name, THREAD_LOCAL

# Check database alias
db = get_current_db_name()
print(f"Current DB: {db}")  # 'intelliwiz_django' or 'default'

# Check thread-local directly
if hasattr(THREAD_LOCAL, 'DB'):
    print(f"Thread-local DB: {THREAD_LOCAL.DB}")
else:
    print("No tenant context")

# Check request tenant
# In view:
print(f"Request tenant: {request.tenant}")
```

### Verify Manager is Set:

```python
from apps.helpbot.models import HelpBotSession

# Check manager class
manager_class = HelpBotSession.objects.__class__.__name__
print(f"Manager: {manager_class}")  # Should be 'TenantAwareManager'

# Verify filtering works
from apps.core.utils_new.db_utils import set_db_for_router

set_db_for_router('intelliwiz_django')
sessions = HelpBotSession.objects.all()
print(f"Query has tenant filter: {'tenant' in str(sessions.query)}")
```

### Check Cache Keys:

```bash
# In Redis CLI
redis-cli

# Check cache key format
KEYS tenant:*

# Should show:
# tenant:intelliwiz_django:user:123:profile
# tenant:intelliwiz_django:helpbot:session:abc123
```

---

## ⚠️ **Common Mistakes**

### ❌ Mistake 1: Forgetting Manager Declaration

```python
# WRONG
class MyModel(TenantAwareModel):
    name = models.CharField(max_length=100)
    # Missing: objects = TenantAwareManager()

# Queries will NOT filter by tenant!
MyModel.objects.all()  # Returns ALL tenants' data!
```

### ❌ Mistake 2: Using Raw Cache

```python
# WRONG
from django.core.cache import cache
cache.set('key', 'value')  # Not tenant-scoped!

# RIGHT
from apps.core.cache.tenant_aware import tenant_cache
tenant_cache.set('key', 'value')  # Tenant-scoped!
```

### ❌ Mistake 3: Direct Tenant Manipulation

```python
# WRONG - Don't set THREAD_LOCAL.DB manually
from apps.core.utils_new.db_utils import THREAD_LOCAL
THREAD_LOCAL.DB = 'other_tenant'  # Security violation!

# RIGHT - Let middleware handle it
# Or use set_db_for_router() in management commands only
```

### ❌ Mistake 4: Not Checking is_active

```python
# WRONG - Don't get tenant without checking active status
tenant = Tenant.objects.get(subdomain_prefix='slug')  # May be suspended!

# RIGHT - Use utility that checks is_active
from apps.tenants.utils import get_tenant_by_slug
tenant = get_tenant_by_slug('slug')  # Only returns active tenants
```

---

## 🛡️ **Security Checklist**

Before deploying new tenant-aware code:

- [ ] Model declares `objects = TenantAwareManager()`
- [ ] Caching uses `tenant_cache` not `cache`
- [ ] No manual `THREAD_LOCAL.DB` manipulation
- [ ] Tenant lookups check `is_active=True`
- [ ] Error handling doesn't leak cross-tenant data
- [ ] Tests verify tenant isolation
- [ ] Audit logging for security events
- [ ] File access uses SecureFileDownloadService

---

## 📞 **Need Help?**

### Common Questions:

**Q: How do I test tenant isolation locally?**
```bash
# Use different hostnames
curl -H "Host: tenant1.youtility.local" http://localhost:8000/api/endpoint/
curl -H "Host: tenant2.youtility.local" http://localhost:8000/api/endpoint/

# Or use tenant headers
curl -H "X-Tenant-Slug: tenant1" http://localhost:8000/api/endpoint/
```

**Q: How do I create a new tenant?**
```python
from apps.tenants.models import Tenant

tenant = Tenant.objects.create(
    tenantname="Acme Corporation",
    subdomain_prefix="acme-corp"  # lowercase, hyphens only
)
```

**Q: How do I suspend a tenant?**
```python
tenant = Tenant.objects.get(subdomain_prefix='acme-corp')
tenant.suspend(reason="Payment overdue")

# Reactivate later
tenant.activate()
```

**Q: How do I write cross-tenant admin queries?**
```python
# Use cross_tenant_query() - audit logged
all_data = MyModel.objects.cross_tenant_query()

# Or specify tenant explicitly
tenant_data = MyModel.objects.for_tenant(tenant_pk=1)
```

---

## 🔗 **Related Documentation**

- Migration Guide: `docs/TENANT_MIDDLEWARE_MIGRATION_GUIDE.md`
- Security Audit: `MULTI_TENANCY_SECURITY_AUDIT_REPORT.md`
- Final Report: `MULTI_TENANCY_ULTRATHINK_FINAL_REPORT.md`
- Verification: `python scripts/verify_tenant_setup.py --verbose`

---

**Remember**: When in doubt, use the utilities from `apps.tenants.utils` - they handle all edge cases!
