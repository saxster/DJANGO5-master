# Multi-Tenancy Security Hardening Audit Report
**Date**: November 3, 2025
**Auditor**: Claude Code (Phase 1: Security Hardening)
**Scope**: TenantAwareModel Manager Usage, Cache Isolation, Migration Guards

---

## Executive Summary

**Overall Assessment**: 🟡 **MEDIUM RISK** - Architecture is sound, but implementation has critical gaps

### Key Findings:
- ✅ **Strong Foundation**: TenantAwareManager + middleware isolation architecture is excellent
- ❌ **Critical Gap**: 113 models inherit TenantAwareModel but **only 1 file** declares TenantAwareManager
- ⚠️ **Cache Risk**: 241 files use cache.get/set without tenant isolation (tenant_cache exists but unused)
- ⚠️ **Migration Bypass**: TODO hack in TenantDbRouter allows all migrations on 'default' database

### Risk Assessment:
| Category | Risk Level | Impact | Likelihood |
|----------|-----------|---------|-----------|
| Cross-tenant ORM queries | 🔴 HIGH | Data breach | HIGH (no manager = no filtering) |
| Cache key collisions | 🟡 MEDIUM | Data leakage | MEDIUM (tenant_cache exists but not used) |
| Migration safety | 🟡 MEDIUM | Data corruption | LOW (requires specific conditions) |

---

## 1. TenantAwareModel Manager Adoption Audit

### Problem Statement:
The `TenantAwareModel` abstract base class provides a `tenant` ForeignKey but **does not declare a default manager**. This means child models must explicitly add:

```python
objects = TenantAwareManager()
```

**If they don't**, queries will use Django's default manager which **does NOT filter by tenant**.

### Findings:

#### Total Scope:
- **113 model files** inherit from `TenantAwareModel`
- **Only 1 file** (`apps/tenants/managers.py`) contains TenantAwareManager declaration
- **112+ models** potentially vulnerable to cross-tenant data access

#### Sample Vulnerable Models:

```python
# apps/helpbot/models.py:21
class HelpBotSession(BaseModel, TenantAwareModel):
    # ❌ NO manager declared - uses default manager
    # ❌ Queries will NOT filter by tenant automatically
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    # ... rest of model
```

**Impact**: Any query like `HelpBotSession.objects.all()` will return sessions from ALL tenants, not just the current one.

#### Files Requiring Manager Addition (Sample):
1. `apps/helpbot/models.py` - HelpBotSession, HelpBotMessage, HelpBotKnowledge
2. `apps/help_center/models.py` - HelpCenterArticle, HelpCenterCategory
3. `apps/help_center/memory_models.py` - ConversationMemory, UserInteractionMemory
4. `apps/help_center/gamification_models.py` - UserPoints, Achievements
5. `apps/y_helpdesk/models/__init__.py` - Multiple ticket-related models
6. `apps/noc/models/*.py` - 20+ models (Incident, Alert, PlaybookExecution, etc.)
7. `apps/work_order_management/models.py` - WorkOrder models
8. `apps/attendance/models.py` - PeopleEventlog, AttendanceRecord
9. `apps/journal/models.py` - JournalEntry
10. `apps/ml_training/models.py` - Dataset, TrainingJob
11. `apps/face_recognition/models.py` - FaceRecognition models
12. `apps/wellness/models.py` - WellnessContent, UserProgress
13. `apps/voice_recognition/models.py` - VoiceEnrollment, BiometricLog
14. `apps/core/models/*.py` - AuditLog, APIDeprecation, FeatureFlag
15. `apps/onboarding/models/*.py` - 10+ models
16. `apps/peoples/models/*.py` - Capability, DeviceRegistry, Membership
17. `apps/activity/models/*.py` - Asset, Job, Question, VehicleEntry
18. `apps/search/models.py` - SearchIndexMetadata

... and **95+ more** across the codebase.

---

## 2. Cache Isolation Audit

### Problem Statement:
The codebase has an **excellent tenant-aware caching utility** (`apps/core/cache/tenant_aware.py`), but it's not being used consistently. Most code directly imports Django's cache, which has no tenant isolation.

### Findings:

#### Tenant-Aware Cache (GOOD):
**File**: `apps/core/cache/tenant_aware.py`

```python
class TenantAwareCache:
    """Automatically prefixes all cache keys with tenant context"""

    def set(self, key, value, timeout):
        tenant = get_current_db_name()
        tenant_key = f"tenant:{tenant}:{key}"
        return self.cache.set(tenant_key, value, timeout)
```

✅ **Features**:
- Automatic tenant prefix: `tenant:intelliwiz_django:key`
- Thread-local context integration
- Audit logging for sensitive keys
- Full Django cache API compatibility

#### Cache Usage (NOT GOOD):
- **283 files** import `from django.core.cache import cache`
- **241 files** use `cache.get()` or `cache.set()`
- **0 files** import or use `tenant_cache` from `apps.core.cache.tenant_aware`

#### Risk:
Without tenant-scoped keys, cache entries could collide between tenants:

```python
# Tenant A sets: cache.set('user:123:profile', data_A)
# Tenant B reads: cache.get('user:123:profile')  # Gets Tenant A's data!
```

#### Files Requiring Cache Update (Sample - Top 20):
1. `apps/core/middleware/multi_tenant_url.py:74-75` - Tenant lookup cache
2. `apps/core/caching/utils.py` - Cache utility functions
3. `apps/core/services/*.py` - 15+ service files using cache
4. `apps/noc/services/query_cache.py` - Query result caching
5. `apps/helpbot/services/conversation_service.py` - Conversation caching
6. `apps/search/services/unified_semantic_search_service.py` - Search result caching
7. `apps/y_helpdesk/services/ticket_translation_service.py` - Translation caching
8. `apps/peoples/services/people_caching_service.py` - People data caching
9. `apps/face_recognition/ai_enhanced_engine.py` - Face recognition caching
10. `apps/core/middleware/api_authentication.py` - API key caching
11. `apps/core/views/*.py` - 20+ dashboard views caching metrics
12. `apps/scheduler/services/*.py` - Schedule caching
13. `apps/onboarding_api/services/*.py` - 15+ services using cache
14. `apps/reports/api/viewsets.py` - Report caching
15. `apps/core/management/commands/warm_caches.py` - Cache warming
16. `apps/core/decorators.py` - Cache decorators
17. `apps/core/health_checks/cache.py` - Cache health monitoring
18. `apps/core/middleware/smart_caching_middleware.py` - Response caching
19. `apps/ml/services/*.py` - ML inference caching
20. `apps/noc/consumers/*.py` - WebSocket data caching

... and **221+ more** files.

---

## 3. Migration Guard Bypass Audit

### Problem Statement:
The `TenantDbRouter.allow_migrate()` method has a hardcoded bypass for the 'default' database with a TODO comment to remove it.

**File**: `apps/tenants/middlewares.py:212-215`

```python
def allow_migrate(self, db, app_label, model_name=None, **hints):
    # TEMPORARY FIX: Bypass migration guard for default database during initial setup
    # TODO: Remove this bypass after initial migrations are complete
    if db == 'default':
        return True  # ⚠️ ALLOWS ALL MIGRATIONS
```

### Risk:
This bypass defeats the migration guard's purpose. Migrations intended for tenant-specific databases could accidentally run on 'default', causing:
- Schema mismatches between databases
- Data corruption if tenant-specific columns added to shared tables
- Silent failures during multi-tenant migrations

### Recommendation:
**Remove immediately** or replace with allowlist:

```python
# Option 1: Remove entirely (if initial setup complete)
# if db == 'default':
#     return True

# Option 2: Allowlist core apps only
CORE_APPS = {'auth', 'contenttypes', 'sessions', 'admin', 'tenants'}
if db == 'default' and app_label in CORE_APPS:
    return True
```

---

## 4. TenantAwareModel Base Class Hardening

### Current Implementation:

**File**: `apps/tenants/models.py:16-20`

```python
class TenantAwareModel(models.Model):
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        abstract = True
```

### Issues:

1. **No Default Manager**: Child classes must remember to add `objects = TenantAwareManager()`
2. **Nullable Tenant**: `null=True, blank=True` allows records without tenant association
3. **No Pre-Save Validation**: No hook ensures tenant is always set before saving
4. **No Unique Constraints**: Common fields (e.g., name, code) may need `unique_together = ['tenant', 'name']`

### Recommendations:

```python
class TenantAwareModel(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        null=False,  # ✅ Make required
        blank=False,  # ✅ Make required in forms
        on_delete=models.CASCADE
    )

    objects = TenantAwareManager()  # ✅ Declare default manager

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """✅ Pre-save validation"""
        if not self.tenant_id:
            from apps.core.utils_new.db_utils import get_current_db_name
            # Attempt to auto-set tenant from context
            # Or raise ValidationError if missing
            raise ValidationError("Tenant is required for all TenantAwareModel instances")
        super().save(*args, **kwargs)
```

---

## 5. Remediation Plan

### Phase 1: Critical Fixes (Week 1)

#### 1.1 Add TenantAwareManager to All Models ✅
**Estimated Time**: 2-3 hours (automated script)

Create script `scripts/add_tenant_managers.py`:
```python
# Scan all 113 model files
# Insert `objects = TenantAwareManager()` after model definition
# Handle imports automatically
```

#### 1.2 Replace Cache Imports ✅
**Estimated Time**: 3-4 hours (automated script + manual review)

Create script `scripts/migrate_to_tenant_cache.py`:
```python
# Replace: from django.core.cache import cache
# With:    from apps.core.cache.tenant_aware import tenant_cache as cache
# Run tests after each file modification
```

#### 1.3 Remove Migration Bypass ✅
**Estimated Time**: 30 minutes

Edit `apps/tenants/middlewares.py:212-215`:
```python
# Remove or replace with core apps allowlist
```

### Phase 2: Validation & Safety (Week 2)

#### 2.1 Add Pre-Save Validation ✅
**Estimated Time**: 1-2 hours

Update `TenantAwareModel.save()` to enforce tenant is set.

#### 2.2 Make Tenant Non-Nullable ⚠️
**Estimated Time**: 4-6 hours (requires migration + data backfill)

**WARNING**: This requires careful migration:
```bash
# 1. Backfill any NULL tenant values
python manage.py backfill_null_tenants

# 2. Generate migration
python manage.py makemigrations

# 3. Run on staging first
python manage.py migrate --database=staging

# 4. Validate no NULL tenants remain
python manage.py validate_tenant_data
```

#### 2.3 Run Security Test Suite ✅
**Estimated Time**: 1 hour

```bash
pytest apps/tenants/tests/test_security_penetration.py -v
pytest apps/tenants/tests/test_tenant_isolation.py -v
pytest apps/core/tests/test_cache_security_comprehensive.py -v
```

---

## 6. Verification Checklist

After implementing fixes, verify:

- [ ] All TenantAwareModel subclasses have `objects = TenantAwareManager()`
- [ ] Grep confirms: `grep -r "class.*TenantAwareModel" apps/ | wc -l` == `grep -r "objects = TenantAwareManager" apps/ | wc -l`
- [ ] All cache usage goes through `tenant_cache` wrapper
- [ ] Migration bypass removed or restricted to core apps
- [ ] Pre-save validation prevents NULL tenant
- [ ] All tests pass: `pytest apps/ -k tenant`
- [ ] Manual penetration test: Attempt cross-tenant access via API
- [ ] Cache penetration test: Verify keys are tenant-scoped in Redis

---

## 7. Long-Term Recommendations

### 7.1 Enforce at CI/CD Level
Add pre-commit hook:
```bash
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: check-tenant-manager
      name: Check TenantAwareManager usage
      entry: scripts/check_tenant_managers.sh
      language: script
```

### 7.2 Database Row-Level Security (Optional)
For defense-in-depth, add PostgreSQL RLS policies:
```sql
CREATE POLICY tenant_isolation ON helpbot_session
  USING (tenant_id = current_setting('app.current_tenant_id')::int);
```

### 7.3 Admin Interface Hardening
Ensure Django Admin filters by tenant:
```python
class HelpBotSessionAdmin(admin.ModelAdmin):
    list_filter = ['tenant', 'session_type']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(tenant=request.user.tenant)
        return qs
```

---

## Appendix A: Full List of Affected Model Files

<details>
<summary>Click to expand (113 files)</summary>

```
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/help_center/memory_models.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/help_center/gamification_models.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/y_helpdesk/models/__init__.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/help_center/models.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/noc/security_intelligence/models/fraud_prediction_log.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/noc/models/predictive_alert_tracking.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/noc/models/incident_context.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/noc/models/incident.py
/Users/amar/Desktop/MyCode/DJANGO5-master/apps/noc/models/alert_event.py
... (see grep output for complete list)
```
</details>

---

## Appendix B: Industry Best Practices Compliance

| Best Practice | Current Status | Remediation |
|---------------|---------------|-------------|
| Automatic ORM filtering | ⚠️ Partial | Add managers to all models |
| Tenant-scoped caching | ⚠️ Utility exists but unused | Migrate cache usage |
| Migration safety guards | ⚠️ Bypass present | Remove TODO hack |
| Pre-save validation | ❌ Missing | Add save() hook |
| Non-nullable tenant FK | ❌ Currently nullable | Migration + validation |
| Audit logging | ✅ Excellent | No changes needed |
| File access control | ✅ Excellent (6 layers) | No changes needed |
| Thread-local isolation | ✅ Excellent | No changes needed |

---

**Report Status**: DRAFT - Awaiting Phase 1 Implementation
**Next Review**: After Phase 1 fixes completed
