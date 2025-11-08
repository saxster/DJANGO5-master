# Pre-Deployment Checklist - Onboarding Remediation

**Project**: Onboarding Placeholder Remediation
**Date**: October 31, 2025
**Deploy Target**: Staging → Production

---

## ✅ Code Quality Verification

### Django System Checks
```bash
# Activate virtual environment
source venv/bin/activate  # or: source ~/.pyenv/versions/3.11.9/bin/activate

# Run Django system checks
python manage.py check
python manage.py check --deploy
python manage.py check --tag urls
python manage.py check --tag models

# Expected: "System check identified no issues (0 silenced)."
```

### URL Configuration
```bash
# Verify no broken reverse URL lookups
python manage.py show_urls | grep onboarding

# Expected output should NOT include:
# - onboarding:typeassist
# - onboarding:shift
# - onboarding:geofence
# - onboarding:import
# - onboarding:client
# - onboarding:bu
# - onboarding:contract

# Should include:
# - onboarding:super_typeassist
# - onboarding:subscription
# - onboarding:get_caps
```

### Test Suite Execution
```bash
# Run comprehensive test suite
pytest tests/test_onboarding_remediation.py -v

# Run with coverage
pytest tests/test_onboarding_remediation.py --cov=apps.onboarding --cov-report=html

# Expected: All tests passing (25 tests, 50+ assertions)
```

### Code Style & Linting
```bash
# Run code quality validation
python scripts/validate_code_quality.py --verbose

# Check for syntax errors
flake8 apps/onboarding/api/viewsets/ --max-line-length=120

# Expected: No critical violations
```

---

## ✅ Database & Migration Checks

### Migration Status
```bash
# Check for unapplied migrations
python manage.py showmigrations onboarding

# Expected: All migrations applied (no [ ] marks)
```

### Data Integrity
```bash
# Verify models still accessible
python manage.py shell -c "
from apps.onboarding.models import TypeAssist, Shift, GeofenceMaster, Bt, Client, Contract
print('TypeAssist count:', TypeAssist.objects.count())
print('Shift count:', Shift.objects.count())
print('Geofence count:', GeofenceMaster.objects.count())
print('Business Unit count:', Bt.objects.count())
print('Client count:', Client.objects.count())
print('Contract count:', Contract.objects.count())
"

# Expected: All queries succeed, return counts
```

---

## ✅ Template Verification

### No Broken URL References
```bash
# Search for remaining old URL patterns
grep -r 'onboarding:typeassist\|onboarding:shift\|onboarding:geofence\|onboarding:import' \
  frontend/templates --include='*.html' | grep -v '.bak' | grep -v '.ajax_backup'

# Expected: No matches (all migrated to Django Admin or REST API)
```

### AJAX Endpoint Migration
```bash
# Verify REST API URLs in templates
grep -r '/api/v1/admin/config/' frontend/templates --include='*.html' | wc -l

# Expected: At least 12 matches (modern templates using REST API)
```

### Django Admin URLs
```bash
# Verify admin URLs in templates
grep -r 'admin:onboarding_' frontend/templates --include='*.html' | wc -l

# Expected: At least 20 matches (sidebar and navigation links)
```

---

## ✅ REST API Verification

### API Endpoints Accessible
```bash
# Test shifts endpoint
curl -X GET http://localhost:8000/api/v1/admin/config/shifts/ \
  -H "Authorization: Bearer YOUR_TOKEN" | jq

# Expected response:
# {
#   "count": N,
#   "results": [...],
#   "message": "Success"
# }

# Test geofences endpoint
curl -X GET http://localhost:8000/api/v1/admin/config/geofences/ \
  -H "Authorization: Bearer YOUR_TOKEN" | jq

# Expected response format same as above

# Test contracts endpoint
curl -X GET http://localhost:8000/api/v1/admin/config/contracts/ \
  -H "Authorization: Bearer YOUR_TOKEN" | jq

# Expected response format same as above
```

### API Response Format
```python
# In Django shell
from django.test import Client
client = Client()

response = client.get('/api/v1/admin/config/shifts/')
print(response.status_code)  # Should be 200 or 401
print(response.json().keys())  # Should include 'results', 'count', 'message'
```

---

## ✅ Middleware Verification

### Files Deleted
```bash
# Verify middleware file deleted
ls apps/core/middleware/legacy_url_redirect.py 2>&1

# Expected: "No such file or directory"

# Verify management command deleted
ls apps/core/management/commands/monitor_legacy_redirects.py 2>&1

# Expected: "No such file or directory"
```

### Settings Configuration
```bash
# Check middleware not in settings
grep -r 'legacy_url_redirect\|LegacyURLRedirectMiddleware' intelliwiz_config/settings/

# Expected: No matches
```

---

## ✅ Static Files & Assets

### Collect Static Files
```bash
# Collect static files (if needed)
python manage.py collectstatic --noinput --clear

# Expected: Static files collected successfully
```

### Template Cache
```bash
# Clear template cache
python manage.py clear_cache

# Or manually:
find . -type d -name '__pycache__' -exec rm -r {} + 2>/dev/null || true
```

---

## ✅ Browser Testing

### Manual QA Checklist

**Sidebar Navigation**:
- [ ] Click "TypeAssist" → Opens `/admin/onboarding/typeassist/`
- [ ] Click "Shifts" → Opens `/admin/onboarding/shift/`
- [ ] Click "Geofences" → Opens `/admin/onboarding/geofencemaster/`
- [ ] Click "Business Units" → Opens `/admin/onboarding/bt/`
- [ ] Click "Clients" → Opens `/admin/onboarding/client/`
- [ ] Click "Import/Export" → Opens import page

**DataTables**:
- [ ] Visit `/onboarding/shift-modern/` → Table loads data
- [ ] Visit `/onboarding/bu-list-modern/` → Cards display
- [ ] Visit `/onboarding/geofence-list-modern/` → List populates
- [ ] Visit `/onboarding/contract-list-modern/` → Contracts show

**Forms & Navigation**:
- [ ] Click "Add New" on shift page → Django Admin add form
- [ ] Click "Add New" on geofence page → Django Admin add form
- [ ] Click edit icon → Django Admin change form
- [ ] Import page loads without errors

**Browser Console**:
- [ ] Open DevTools Console (F12)
- [ ] Navigate through all pages
- [ ] Verify no 404 errors
- [ ] Verify no 501 errors
- [ ] Verify no JavaScript exceptions
- [ ] Check Network tab: All AJAX calls return 200

### Browser Compatibility
Test in:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (if on macOS)
- [ ] Mobile browser (responsive)

---

## ✅ Performance Testing

### Page Load Times
```bash
# Test critical pages
time curl -s http://localhost:8000/onboarding/shift-modern/ > /dev/null

# Expected: < 2 seconds for initial load
```

### API Response Times
```bash
# Test API endpoint performance
time curl -s http://localhost:8000/api/v1/admin/config/shifts/ > /dev/null

# Expected: < 500ms
```

### Database Query Optimization
```python
# In Django shell with query logging enabled
from django.test import Client
from django.db import connection
from django.test.utils import override_settings

client = Client()

with override_settings(DEBUG=True):
    connection.queries_log.clear()
    response = client.get('/api/v1/admin/config/shifts/')
    print(f"Queries executed: {len(connection.queries)}")
    # Should be reasonable (< 10 queries with proper select_related/prefetch_related)
```

---

## ✅ Security Verification

### CSRF Protection
```bash
# Verify CSRF token in templates
grep -r 'csrf_token' frontend/templates --include='*.html' | wc -l

# Expected: Many matches (CSRF protection active)
```

### Authentication
```python
# Test that API requires authentication
from django.test import Client
client = Client()

# Without auth should return 401 or 403
response = client.get('/api/v1/admin/config/shifts/')
assert response.status_code in [401, 403], "API should require authentication"
```

### Permission Checks
```python
# Test that non-staff users can't access admin
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.create_user('test', is_staff=False)

client = Client()
client.force_login(user)

response = client.get('/admin/onboarding/shift/')
assert response.status_code in [302, 403], "Non-staff should not access admin"
```

---

## ✅ Backup & Rollback Plan

### Create Backup
```bash
# Backup database before deploy
pg_dump intelliwiz_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Or use Django backup command
python manage.py dumpdata onboarding > onboarding_backup.json
```

### Git Commit for Rollback
```bash
# Tag current production state
git tag pre-remediation-deploy-$(date +%Y%m%d)

# Note the commit SHA
git rev-parse HEAD > PRE_DEPLOY_COMMIT.txt

# This allows quick rollback:
# git revert <commit-sha>
```

### Rollback Procedure
If issues occur:

```bash
# Option 1: Git revert (recommended)
git revert <remediation-commit-sha>
git push origin main

# Option 2: Restore from backup files
# All templates have .bak and .ajax_backup files in same directory
find frontend/templates -name '*.ajax_backup' | while read backup; do
    original="${backup%.ajax_backup}"
    cp "$backup" "$original"
done

# Option 3: Database restore (if data corrupted)
psql intelliwiz_db < backup_20251031_HHMMSS.sql
```

---

## ✅ Monitoring & Logging

### Enable Debug Logging
```python
# Temporarily enable logging to catch issues
# intelliwiz_config/settings/local.py or staging.py

LOGGING['loggers']['onboarding_api'] = {
    'level': 'DEBUG',
    'handlers': ['console', 'file'],
}

LOGGING['loggers']['django.request'] = {
    'level': 'DEBUG',
    'handlers': ['console', 'file'],
}
```

### Monitor After Deploy
```bash
# Watch logs for errors
tail -f logs/django.log | grep -i 'error\|404\|501'

# Monitor API endpoints
watch -n 5 'curl -s http://localhost:8000/api/v1/admin/config/shifts/ | jq ".count"'

# Check for broken links
# Use browser extension or tool to scan for 404s
```

---

## ✅ Documentation Updates

### Update Internal Docs
- [ ] Update API documentation with new endpoints
- [ ] Update developer onboarding guide
- [ ] Update troubleshooting runbook
- [ ] Add entry to CHANGELOG.md

### Notify Teams
- [ ] Frontend team: Template URL migration guide
- [ ] Backend team: REST API endpoints available
- [ ] QA team: Testing checklist
- [ ] DevOps team: No infrastructure changes needed

---

## ✅ Sign-Off

### Pre-Deployment Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| **Developer** | _________ | ____/____ | _________ |
| **Tech Lead** | _________ | ____/____ | _________ |
| **QA Engineer** | _________ | ____/____ | _________ |
| **DevOps** | _________ | ____/____ | _________ |

### Post-Deployment Verification

- [ ] Staging deploy successful (Date: ____)
- [ ] Staging QA passed (Date: ____)
- [ ] Production deploy successful (Date: ____)
- [ ] Production smoke tests passed (Date: ____)
- [ ] Monitoring shows no issues (Date: ____)

---

## 🚨 Known Issues & Limitations

### Non-Blocking Issues
None identified

### Future Enhancements
- Complete REST API migration for all features
- Replace jQuery DataTables with modern component
- Extend REST API with advanced filtering and pagination

---

## 📞 Support Contacts

**If Issues Occur**:
- **On-Call Engineer**: [Contact info]
- **Tech Lead**: [Contact info]
- **DevOps**: [Contact info]

**Emergency Rollback**:
1. Stop deployment immediately
2. Execute rollback procedure (see above)
3. Notify team in #engineering-alerts
4. Schedule post-mortem

---

**Checklist Created**: October 31, 2025
**Checklist Owner**: Development Team
**Deploy Window**: [TBD by DevOps]
**Estimated Downtime**: None (zero-downtime deploy)
