# Multi-Tenancy Deployment Checklist
**Purpose**: Step-by-step checklist for deploying multi-tenancy improvements
**Date**: November 3, 2025
**Status**: Ready for execution

---

## Pre-Deployment Checks

### Environment Verification
- [ ] Python version: 3.11.9
- [ ] Django check passes: `python manage.py check`
- [ ] All dependencies installed
- [ ] Git branch created for changes: `git checkout -b feature/multi-tenancy-hardening`

---

## Phase 1: Verification & Preparation (15 minutes)

### Step 1.1: Verify New Files Created
- [ ] `apps/tenants/constants.py` exists
- [ ] `apps/tenants/utils.py` exists
- [ ] `apps/tenants/middleware_unified.py` exists
- [ ] `apps/tenants/tests/test_edge_cases.py` exists
- [ ] `scripts/verify_tenant_setup.py` exists
- [ ] `scripts/add_tenant_managers.py` exists (created earlier)
- [ ] `scripts/migrate_to_tenant_cache.py` exists (created earlier)
- [ ] `docs/TENANT_MIDDLEWARE_MIGRATION_GUIDE.md` exists

### Step 1.2: Verify Modified Files
- [ ] `apps/tenants/models.py` - validation + state mgmt
- [ ] `apps/tenants/middlewares.py` - cleanup added
- [ ] `apps/core/middleware/multi_tenant_url.py` - tenant_cache + cleanup
- [ ] `apps/tenants/admin.py` - uses utilities
- [ ] `apps/tenants/managers.py` - uses utilities + error handling
- [ ] `apps/core/utils_new/db_utils.py` - type hints
- [ ] `intelliwiz_config/settings/tenants.py` - cleaned up defaults

### Step 1.3: Test Imports
```bash
python manage.py shell

>>> from apps.tenants.utils import get_tenant_from_context
>>> from apps.tenants.middleware_unified import UnifiedTenantMiddleware
>>> from apps.tenants.constants import TENANT_SLUG_PATTERN
>>> exit()
```
- [ ] All imports work without errors

---

## Phase 2: Database Migration (10 minutes)

### Step 2.1: Generate Migration
```bash
python manage.py makemigrations tenants
```

**Expected Migration**:
- [ ] Adds `is_active` field (BooleanField, default=True, db_index=True)
- [ ] Adds `suspended_at` field (DateTimeField, null=True)
- [ ] Adds `suspension_reason` field (TextField, blank=True)
- [ ] Adds validator to `subdomain_prefix`

### Step 2.2: Review Migration
```bash
# Read the migration file
cat apps/tenants/migrations/0003_*.py
```
- [ ] Migration looks safe
- [ ] No data deletion
- [ ] All new fields have defaults

### Step 2.3: Apply Migration (Staging First)
```bash
# Backup database first!
pg_dump intelliwiz_db > backup_before_tenant_migration.sql

# Apply migration
python manage.py migrate tenants

# Verify
python manage.py shell
>>> from apps.tenants.models import Tenant
>>> Tenant.objects.count()
>>> Tenant.objects.filter(is_active=False).count()  # Should be 0
```
- [ ] Migration applied successfully
- [ ] All existing tenants are `is_active=True`

---

## Phase 3: Code Updates (30-60 minutes)

### Step 3.1: Add TenantAwareManager to All Models

```bash
# DRY RUN FIRST (preview changes)
python scripts/add_tenant_managers.py --dry-run

# Review output:
# - Check which files will be modified
# - Verify no syntax errors
# - Confirm backups will be created
```
- [ ] Dry run output looks correct
- [ ] ~112 models will be updated

```bash
# EXECUTE (creates backups automatically)
python scripts/add_tenant_managers.py

# Verify
python scripts/add_tenant_managers.py --verify
```
- [ ] All TenantAwareModel subclasses now have TenantAwareManager
- [ ] Backups created in `backups/tenant_managers_*/`

### Step 3.2: Migrate Cache Usage

```bash
# DRY RUN FIRST
python scripts/migrate_to_tenant_cache.py --dry-run

# Review output
```
- [ ] Dry run output looks correct
- [ ] ~200+ files will be updated

```bash
# EXECUTE
python scripts/migrate_to_tenant_cache.py

# Verify
python scripts/migrate_to_tenant_cache.py --verify
```
- [ ] All cache usage now uses `tenant_cache`
- [ ] Backups created in `backups/cache_migration_*/`

---

## Phase 4: Middleware Update (5 minutes)

### Step 4.1: Choose Middleware Strategy

**Option A: Unified (RECOMMENDED)**
```python
# intelliwiz_config/settings/base.py
MIDDLEWARE = [
    # ...
    'apps.tenants.middleware_unified.UnifiedTenantMiddleware',
    # ...
]
```
- [ ] UnifiedTenantMiddleware added to MIDDLEWARE
- [ ] Old middlewares removed (TenantMiddleware, MultiTenantURLMiddleware)

**Option B: Keep Dual (with improvements)**
```python
# Keep existing (now with cleanup + tenant_cache)
MIDDLEWARE = [
    # ...
    'apps.tenants.middlewares.TenantMiddleware',
    'apps.core.middleware.multi_tenant_url.MultiTenantURLMiddleware',
    # ...
]
```
- [ ] Both old middlewares remain (now with improvements)

---

## Phase 5: Testing (30 minutes)

### Step 5.1: Run Unit Tests
```bash
# Tenant tests
pytest apps/tenants/tests/ -v

# Edge case tests
pytest apps/tenants/tests/test_edge_cases.py -v

# Cache security tests
pytest apps/core/tests/test_cache_security_comprehensive.py -v
```
- [ ] All tenant tests pass
- [ ] All edge case tests pass
- [ ] All cache security tests pass

### Step 5.2: Run Full Regression
```bash
# Full test suite
pytest apps/ --tb=short -v

# Or with coverage
pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v
```
- [ ] All tests pass (or failures unrelated to tenant changes)
- [ ] Code coverage maintained or improved

### Step 5.3: Run Verification Script
```bash
python scripts/verify_tenant_setup.py --verbose
```
- [ ] All checks pass (exit code 0)
- [ ] No critical issues
- [ ] All managers present
- [ ] All cache usage tenant-aware

---

## Phase 6: Manual Testing (20 minutes)

### Step 6.1: Start Development Server
```bash
python manage.py runserver
```

### Step 6.2: Test Valid Tenant Access
```bash
# Test with valid hostname
curl -I -H "Host: intelliwiz.youtility.local" http://localhost:8000/

# Check response headers
# Should include:
# X-Tenant-Slug: intelliwiz-django
# X-Tenant-ID: 1
# X-DB-Alias: intelliwiz_django
```
- [ ] Valid tenant access works
- [ ] Response headers include tenant info

### Step 6.3: Test Unknown Hostname (Strict Mode)
```bash
# Should return 403 Forbidden
curl -I -H "Host: unknown.example.com" http://localhost:8000/
```
- [ ] Unknown hostname returns 403 (if TENANT_STRICT_MODE=True)
- [ ] Or 200 with default tenant (if TENANT_STRICT_MODE=False)

### Step 6.4: Test Suspended Tenant
```python
# In Django shell
from apps.tenants.models import Tenant

tenant = Tenant.objects.first()
tenant.suspend(reason="Test suspension")

# Now try to access via that tenant's hostname
# Should return 410 Gone
```
- [ ] Suspended tenant returns 410 Gone
- [ ] Error message mentions suspension

### Step 6.5: Test Cache Isolation
```python
# In Django shell
from apps.core.cache.tenant_aware import tenant_cache
from apps.core.utils_new.db_utils import set_db_for_router
from apps.tenants.utils import cleanup_tenant_context

# Tenant A
set_db_for_router('tenant_a')
tenant_cache.set('test:key', 'value_a', 60)

# Tenant B
cleanup_tenant_context()
set_db_for_router('tenant_b')
value = tenant_cache.get('test:key')

print(value)  # Should be None (different tenant)
```
- [ ] Cache keys are tenant-isolated
- [ ] Tenant B doesn't see Tenant A's cache

---

## Phase 7: Staging Deployment (1-2 hours)

### Step 7.1: Deploy to Staging
```bash
# Commit changes
git add .
git commit -m "feat: comprehensive multi-tenancy hardening

- Add TenantAwareManager to 112+ models
- Migrate 241 files to tenant-aware cache
- Add thread-local cleanup
- Add tenant state management
- Create UnifiedTenantMiddleware
- Comprehensive test coverage
- Full type hints

Closes: #multi-tenancy-security"

# Push to staging
git push origin feature/multi-tenancy-hardening
```

### Step 7.2: Run Staging Tests
- [ ] All automated tests pass
- [ ] Manual smoke tests pass
- [ ] Performance tests show no regression
- [ ] Monitor logs for 24-48 hours

### Step 7.3: Staging Verification
```bash
# SSH to staging server
ssh staging

# Run verification
python scripts/verify_tenant_setup.py --verbose

# Check logs
tail -f /var/log/django/tenants.log
grep "CROSS_TENANT" /var/log/django/security.log  # Should be empty
```
- [ ] Verification script passes
- [ ] No security events in logs
- [ ] No errors or warnings

---

## Phase 8: Production Deployment (30-60 minutes)

### Step 8.1: Pre-Production Checks
- [ ] Staging tests passed
- [ ] No critical issues in staging logs
- [ ] Performance metrics acceptable
- [ ] Rollback plan prepared
- [ ] Maintenance window scheduled (low-traffic time)
- [ ] Team notified

### Step 8.2: Database Backup
```bash
# Full database backup
pg_dump production_db > production_backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
pg_restore --list production_backup_*.sql | head
```
- [ ] Backup completed
- [ ] Backup verified

### Step 8.3: Deploy Code
```bash
# Pull latest code
git checkout main
git pull origin feature/multi-tenancy-hardening

# Install dependencies (if any new)
pip install -r requirements/base-macos.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migration
python manage.py migrate tenants

# Run verification
python scripts/verify_tenant_setup.py
```
- [ ] Code deployed
- [ ] Migration applied
- [ ] Verification passes

### Step 8.4: Restart Services
```bash
# Restart application servers
systemctl restart gunicorn
systemctl restart celery-worker
systemctl restart celery-beat

# Verify services started
systemctl status gunicorn
systemctl status celery-worker
```
- [ ] All services restarted
- [ ] All services healthy

### Step 8.5: Post-Deployment Verification
```bash
# Health check
curl http://production-url/health/

# Tenant routing check
curl -I -H "Host: production.example.com" http://production-url/

# Check logs
tail -f /var/log/django/tenants.log
tail -f /var/log/django/security.log
```
- [ ] Health check passes
- [ ] Tenant routing works
- [ ] No errors in logs

---

## Phase 9: Monitoring (Ongoing)

### Step 9.1: Set Up Alerts

**Alert 1: Cross-Tenant Access**
- Monitor: `security_event:CROSS_TENANT_ACCESS`
- Threshold: > 0 in 5 minutes
- Action: Page security team

**Alert 2: Unscoped Record Saves**
- Monitor: `security_event:unscoped_record_save`
- Threshold: > 10 in 1 hour
- Action: Notify development team

**Alert 3: Tenant Not Found**
- Monitor: `security_event:tenant_not_found`
- Threshold: > 5 in 5 minutes
- Action: Check configuration

**Alert 4: Suspended Tenant Access**
- Monitor: `security_event:deleted_tenant_access`
- Threshold: > 0 in 5 minutes
- Action: Log for business review

### Step 9.2: Regular Audits
- [ ] Weekly: Review cross-tenant query logs
- [ ] Monthly: Audit unscoped record saves
- [ ] Quarterly: Review tenant isolation tests

---

## Rollback Procedure

### If Critical Issues Found:

#### Rollback Code Changes:
```bash
# Restore from backups
cp -r backups/tenant_managers_YYYYMMDD_HHMMSS/apps/* apps/
cp -r backups/cache_migration_YYYYMMDD_HHMMSS/apps/* apps/

# Revert middleware change
git checkout HEAD -- intelliwiz_config/settings/base.py

# Restart services
systemctl restart gunicorn
```

#### Rollback Migration:
```bash
# Reverse migration (if needed)
python manage.py migrate tenants 0002_previous_migration

# Note: is_active field will be removed, but data preserved
```

#### Rollback Git:
```bash
git revert HEAD
git push origin main
```

### Rollback Checklist:
- [ ] Code restored from backups
- [ ] Services restarted
- [ ] Migration reversed (if needed)
- [ ] Verification passes
- [ ] No errors in logs
- [ ] Team notified

---

## Success Criteria

### Deployment Successful When:

**Technical**:
- [ ] All 112+ models have TenantAwareManager
- [ ] All 200+ cache files use tenant_cache
- [ ] Migration applied (is_active field exists)
- [ ] Middleware configured (unified or dual)
- [ ] All tests passing
- [ ] Verification script passes (exit code 0)

**Functional**:
- [ ] Valid tenants can access system
- [ ] Unknown tenants rejected (strict mode)
- [ ] Suspended tenants get 410 Gone
- [ ] Cache keys are tenant-prefixed
- [ ] No cross-tenant data leakage
- [ ] Thread-local cleanup verified

**Operational**:
- [ ] No errors in production logs
- [ ] Performance metrics stable
- [ ] Monitoring alerts configured
- [ ] Team trained on new utilities
- [ ] Documentation updated

---

## Post-Deployment Tasks

### Immediate (Within 24 hours):
- [ ] Monitor logs continuously
- [ ] Check for security events
- [ ] Verify cache hit rates
- [ ] Performance testing
- [ ] User acceptance testing

### Short-term (Within 1 week):
- [ ] Review audit logs
- [ ] Address any test failures
- [ ] Update CLAUDE.md with new middleware info
- [ ] Train team on new utilities
- [ ] Schedule retrospective

### Long-term (Within 1 month):
- [ ] Analyze tenant isolation metrics
- [ ] Review performance impact
- [ ] Consider making tenant non-nullable (after verifying no NULL records)
- [ ] Consider PostgreSQL RLS for defense-in-depth
- [ ] Plan for automated tenant provisioning

---

## Quick Command Reference

### During Deployment:
```bash
# 1. Verify setup
python scripts/verify_tenant_setup.py --verbose

# 2. Generate migration
python manage.py makemigrations tenants

# 3. Add managers
python scripts/add_tenant_managers.py

# 4. Migrate cache
python scripts/migrate_to_tenant_cache.py

# 5. Apply migration
python manage.py migrate tenants

# 6. Run tests
pytest apps/tenants/tests/ -v

# 7. Restart services
systemctl restart gunicorn celery-worker celery-beat
```

### Verification Commands:
```bash
# Check configuration
python manage.py check

# Verify managers
python scripts/add_tenant_managers.py --verify

# Verify cache
python scripts/migrate_to_tenant_cache.py --verify

# Run verification script
python scripts/verify_tenant_setup.py
```

### Monitoring Commands:
```bash
# Check logs
tail -f /var/log/django/tenants.log
grep "security_event" /var/log/django/*.log

# Check Redis cache keys
redis-cli KEYS "tenant:*" | head -20

# Check database
psql -d intelliwiz_db -c "SELECT tenantname, is_active, suspended_at FROM tenants_tenant;"
```

---

## Team Communication Template

### Pre-Deployment Notification:
```
Subject: Multi-Tenancy Security Hardening Deployment - [DATE]

Team,

We will be deploying comprehensive multi-tenancy improvements:

WHAT: Security hardening + code quality improvements
WHEN: [DATE/TIME] (estimated 1 hour maintenance window)
WHY: Fix 22 identified issues, eliminate IDOR vulnerabilities

CHANGES:
- All tenant-aware models get automatic query filtering
- Cache keys now tenant-isolated
- Thread-local cleanup guaranteed
- Tenant suspend/activate functionality

IMPACT:
- No breaking changes to existing functionality
- Improved security and data isolation
- Better performance (cached tenant lookups)

TESTING:
- All automated tests passing
- Staging validation complete
- Rollback procedure prepared

If you have questions, see:
- MULTI_TENANCY_ULTRATHINK_FINAL_REPORT.md
- docs/TENANT_MIDDLEWARE_MIGRATION_GUIDE.md

Thanks,
[Your Name]
```

### Post-Deployment Notification:
```
Subject: Multi-Tenancy Hardening Deployed Successfully

Team,

Multi-tenancy improvements deployed successfully!

RESULTS:
✅ 112+ models now have automatic tenant filtering
✅ 200+ cache files now tenant-isolated
✅ Zero security events in first 4 hours
✅ All tests passing

MONITORING:
Please report any issues immediately to #engineering-ops

NEW FEATURES:
- Tenant suspend/activate via admin
- Better audit logging
- Comprehensive edge case tests

DOCUMENTATION:
- Quick reference: apps/tenants/QUICK_REFERENCE.md
- Full report: MULTI_TENANCY_ULTRATHINK_FINAL_REPORT.md

Thanks for your patience during the deployment!
```

---

## Final Sign-Off

### Deployment Completed By:
- [ ] Name: ___________________________
- [ ] Date: ___________________________
- [ ] Time: ___________________________

### Verification Completed By:
- [ ] Name: ___________________________
- [ ] Date: ___________________________
- [ ] All checks: PASS / FAIL

### Sign-Offs:
- [ ] Development Lead: ___________________________
- [ ] Security Team: ___________________________
- [ ] Operations Team: ___________________________

---

**Deployment Status**: ⬜ Not Started | ⏳ In Progress | ✅ Complete

**Checklist Version**: 1.0
**Last Updated**: 2025-11-03
