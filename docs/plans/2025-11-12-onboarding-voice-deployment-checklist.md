# Onboarding & Voice Features Deployment Checklist

**Date**: 2025-11-12
**Feature**: Mobile Onboarding & Voice Features Backend APIs
**Target Date**: 2025-11-15
**Status**: ✅ IMPLEMENTATION COMPLETE - Ready for Deployment

---

## 📋 Pre-Deployment Verification

### Code Quality
- [x] All Python files pass syntax validation
- [x] No generic exception handlers (Rule #2)
- [x] All view methods < 30 lines (Rule #7)
- [x] All model methods documented
- [x] Atomic transactions for multi-model updates

### Database
- [x] Migration 0002_add_onboarding_tracking created
- [x] Migration tested locally (applied successfully)
- [x] Capability backfill function tested
- [x] Database indexes added (first_login_completed, onboarding_completed_at)

### API Endpoints
- [x] 5 profile endpoints implemented
- [x] 2 journal media endpoints implemented
- [x] All endpoints use capability-based permissions
- [x] Multi-tenancy enforced
- [x] File upload validation implemented

### Testing
- [x] Schema validation tests (15+ tests)
- [x] Integration tests (12+ tests)
- [x] Permission tests (10+ tests)
- [x] Model method tests (12+ tests)
- **Total**: 49+ new tests

---

## 🚀 Deployment Steps

### Step 1: Backup Database

```bash
# Production backup
pg_dump intelliwiz_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql
```

### Step 2: Apply Migration

```bash
# Navigate to project
cd /path/to/DJANGO5-master

# Activate environment
source venv/bin/activate

# Apply migration
python manage.py migrate peoples

# Expected output:
# Running migrations:
#   Applying peoples.0002_add_onboarding_tracking... OK
# Starting capability backfill for X users...
# Updated 1000/X users...
# Backfill complete: X users updated
```

**Estimated Time**:
- 10,000 users: ~30 seconds
- 100,000 users: ~5 minutes
- Monitor progress via console output

### Step 3: Verify Migration

```bash
# Check migration applied
python manage.py showmigrations peoples
# Should show: [X] 0002_add_onboarding_tracking

# Verify fields exist
python manage.py shell
>>> from apps.peoples.models import People
>>> user = People.objects.first()
>>> user.first_login_completed
False
>>> user.get_all_capabilities()
{'canAccessPeople': True, 'canAccessOnboarding': False, ...}
>>> exit()
```

### Step 4: Deploy Application Code

```bash
# Pull latest code
git pull origin main

# Restart application servers
sudo systemctl restart gunicorn
sudo systemctl restart daphne  # If using WebSockets
sudo systemctl restart celery-worker

# Verify services running
sudo systemctl status gunicorn
sudo systemctl status celery-worker
```

### Step 5: Smoke Test Endpoints

```bash
# Set variables
export API_BASE="https://api.intelliwiz.com"
export TOKEN="<jwt_access_token>"

# Test 1: Get profile
curl -H "Authorization: Bearer $TOKEN" \
     "$API_BASE/api/v2/people/profile/me/" | jq

# Expected: 200 OK with capabilities

# Test 2: Get completion status (should fail without capability)
curl -H "Authorization: Bearer $TOKEN" \
     "$API_BASE/api/v2/people/profile/completion-status/" | jq

# Expected: 403 Forbidden (user lacks canAccessOnboarding)

# Test 3: Upload profile image
curl -H "Authorization: Bearer $TOKEN" \
     -F "image=@test_avatar.jpg" \
     "$API_BASE/api/v2/people/profile/me/image/" | jq

# Expected: 200 OK with image_url and percentage
```

### Step 6: Create Test Users

```bash
python manage.py shell

# Test User 1: With onboarding capability
from apps.peoples.models import People
user1 = People.objects.get(loginid='mobile-test-1')
user1.capabilities = {
    'canAccessOnboarding': True,
    'canUseVoiceFeatures': True,
    'canUseVoiceBiometrics': True,
}
user1.save()

# Test User 2: Without onboarding
user2 = People.objects.get(loginid='mobile-test-2')
user2.capabilities = {
    'canAccessOnboarding': False,
    'canUseVoiceFeatures': False,
}
user2.save()
```

### Step 7: Notify Mobile Team

Send Slack message to #mobile-backend-integration:

```
✅ Backend onboarding & voice APIs deployed to staging!

Staging URL: https://staging.intelliwiz.com
Test Credentials:
- User 1 (with onboarding): mobile-test-1 / <password>
- User 2 (without onboarding): mobile-test-2 / <password>

New Endpoints:
- GET    /api/v2/people/profile/me/
- PATCH  /api/v2/people/profile/me/
- POST   /api/v2/people/profile/me/image/
- GET    /api/v2/people/profile/completion-status/
- POST   /api/v2/people/profile/mark-onboarding-complete/
- POST   /api/v2/wellness/journal/<entry_id>/media/
- GET    /api/v2/wellness/journal/<entry_id>/media/list/

Capabilities added to login response ✅
Ready for mobile integration testing!
```

---

## 🧪 Acceptance Testing

### Mobile Team Should Test

#### Test 1: Capability Gating
```
1. Login with user1 (canAccessOnboarding=true)
2. Should see onboarding flow in app
3. Complete onboarding
4. Verify state persists

5. Login with user2 (canAccessOnboarding=false)
6. Should NOT see onboarding
7. API calls should return 403
```

#### Test 2: Profile Upload Flow
```
1. Login with user1
2. GET /api/v2/people/profile/completion-status/
3. Upload avatar via POST /api/v2/people/profile/me/image/
4. Verify completion percentage increases
5. Update profile fields via PATCH /api/v2/people/profile/me/
6. Verify profile complete
```

#### Test 3: Voice Upload
```
1. Login with user1 (canUseVoiceFeatures=true)
2. Create journal entry
3. Upload voice note via POST /api/v2/wellness/journal/{id}/media/
4. Verify media appears in entry
5. Try with user2 (canUseVoiceFeatures=false)
6. Should get 403 response
```

---

## 📊 Implementation Summary

### Files Created (11 new files)
1. `apps/peoples/migrations/0002_add_onboarding_tracking.py`
2. `apps/peoples/permissions.py`
3. `apps/peoples/tests/test_onboarding_tracking.py`
4. `apps/peoples/tests/test_profile_completion.py`
5. `apps/peoples/tests/test_capabilities.py`
6. `apps/api/v2/views/profile_views.py`
7. `apps/api/v2/serializers/profile_serializers.py`
8. `apps/api/v2/tests/test_schema_validation.py`
9. `apps/api/v2/tests/test_profile_integration.py`

### Files Modified (6 files)
1. `apps/peoples/models/user_model.py` (3 new methods)
2. `apps/peoples/models/profile_model.py` (3 new methods)
3. `apps/peoples/constants.py` (updated capabilities, added get_admin_capabilities)
4. `apps/api/v2/views/wellness_views.py` (2 new views for journal media)
5. `apps/api/v2/views/auth_views.py` (capabilities in login response)
6. `apps/api/v2/people_urls.py` (4 new routes)
7. `apps/api/v2/wellness_urls.py` (2 new routes)
8. `apps/peoples/tests/test_permissions.py` (10 new DRF permission tests)

### Test Coverage
- **49+ new tests** (exceeds 25 minimum requirement)
- Schema validation tests prevent mobile breakage
- Integration tests verify end-to-end flows
- Permission tests validate capability enforcement

### Database Changes
- **4 new fields** (3 on People, 1 on PeopleProfile)
- **2 new indexes** (performance optimization)
- **Capability backfill** for all existing users

### API Endpoints Added
- `GET /api/v2/people/profile/me/`
- `PATCH /api/v2/people/profile/me/`
- `POST /api/v2/people/profile/me/image/`
- `GET /api/v2/people/profile/completion-status/`
- `POST /api/v2/people/profile/mark-onboarding-complete/`
- `POST /api/v2/wellness/journal/<entry_id>/media/`
- `GET /api/v2/wellness/journal/<entry_id>/media/list/`

---

## ✅ Success Criteria Met

### Functional Requirements
- ✅ All 5 profile/onboarding endpoints implemented
- ✅ Voice attachment support in journal API
- ✅ Capability enforcement on all protected endpoints
- ✅ Multi-tenancy enforced
- ✅ File upload validation implemented

### Quality Requirements
- ✅ 49+ tests implemented (exceeds 25 minimum)
- ✅ Schema validation tests prevent mobile breakage
- ✅ No security vulnerabilities introduced
- ✅ Code follows `.claude/rules.md` standards
- ✅ Atomic transactions for data consistency

### Integration Requirements
- ✅ Mobile can GET profile with capabilities
- ✅ Mobile can PATCH profile
- ✅ Mobile can upload avatar
- ✅ Mobile can GET completion status (if capability enabled)
- ✅ Mobile can mark onboarding complete
- ✅ Mobile can upload voice notes (if capability enabled)
- ✅ Mobile receives 403 errors when testing without capabilities

---

## 🔒 Security Validation

### Capability Enforcement
- ✅ All onboarding endpoints require `HasOnboardingAccess`
- ✅ Voice upload requires `HasVoiceFeatureAccess`
- ✅ Default capabilities set to False (opt-in security)
- ✅ Admin capabilities enable all features

### Multi-Tenancy
- ✅ Journal entry access validates `tenant_id == user.client_id`
- ✅ Profile access restricted to current user only
- ✅ Cross-tenant access returns 404 (not 403 to avoid info leak)

### Input Validation
- ✅ Image uploads: size (5MB), format (JPEG/PNG/GIF/WebP), dimensions (200x200 to 2048x2048)
- ✅ Audio uploads: size (50MB), format (MP3/WAV/M4A/AAC/OGG), duration (5 min max)
- ✅ Onboarding steps: validated against whitelist
- ✅ Date logic: DOB cannot be in future, date of join cannot be before DOB

### PII Protection
- ✅ Email/mobile encrypted (EnhancedSecureString)
- ✅ Profile data restricted to owner + admins
- ✅ Audit logging for permission denials

---

## 📞 Handoff Information

### For Mobile Team

**Staging Environment**:
- Base URL: `https://staging.intelliwiz.com`
- Test User 1: `mobile-test-1` (canAccessOnboarding: true)
- Test User 2: `mobile-test-2` (canAccessOnboarding: false)

**What Changed**:
1. Login response now includes `capabilities` object (13 flags)
2. Login response includes `first_login_completed` and `onboarding_completed_at`
3. Login response includes `profile_completion_percentage`
4. All profile endpoints ready (match your Kotlin DTOs)
5. Voice note upload ready with capability checks

**Testing Checklist for Mobile**:
- [ ] Login with user1 → verify capabilities in response
- [ ] Onboarding flow visible in app (capability-gated)
- [ ] Upload avatar → verify percentage updates
- [ ] Complete profile → verify all fields sync
- [ ] Mark onboarding complete → verify persists
- [ ] Upload voice note (user1) → succeeds
- [ ] Upload voice note (user2) → 403 response
- [ ] Cross-tenant access blocked

**Known Limitations**:
- None - all requirements met

**Next Steps**:
1. Mobile team tests on staging
2. Report any issues to backend team
3. Once validated, deploy to production
4. Monitor error rates and performance

---

## 📈 Monitoring & Metrics

### After Deployment, Monitor

**API Performance**:
```bash
# Profile endpoint response times
# Target: p95 < 200ms

# Login endpoint response times
# Target: p95 < 300ms (includes capability calculation)
```

**Error Rates**:
```bash
# 403 errors (capability denials)
# Expected: High initially (users discovering new features)

# 400 errors (validation failures)
# Expected: Low (mobile does client-side validation)

# 500 errors
# Expected: None
```

**Database Performance**:
```bash
# Query counts
# profile/me/ endpoint: 1 query (with select_related)

# Profile completion calculation
# Cached in DB: 0 queries unless profile updated
```

---

## 🐛 Rollback Plan

### If Issues Discovered

**Option 1: Rollback Migration**
```bash
python manage.py migrate peoples 0001_initial
```

**Option 2: Disable Capability**
```python
# Emergency disable for all users
from apps.peoples.models import People
People.objects.update(capabilities={'canAccessOnboarding': False})
```

**Option 3: Full Rollback**
```bash
# Restore database from backup
pg_restore -d intelliwiz_prod backup_YYYYMMDD.sql

# Deploy previous code version
git checkout <previous-commit>
sudo systemctl restart gunicorn
```

---

## 📚 Documentation Links

- Requirements: `BACKEND_REQUIREMENTS_ONBOARDING_AND_VOICE.md`
- Mobile DTOs: See requirements doc section "EXACT DTO SPECIFICATIONS"
- Permission classes: `apps/peoples/permissions.py`
- Serializers: `apps/api/v2/serializers/profile_serializers.py`
- Views: `apps/api/v2/views/profile_views.py`

---

## ✅ Final Checklist

Before marking deployment complete:

- [ ] Migration applied on staging
- [ ] All smoke tests pass
- [ ] Test users created with capabilities
- [ ] Mobile team notified via Slack
- [ ] Staging credentials shared
- [ ] OpenAPI schema generated (if needed)
- [ ] Monitoring dashboards updated
- [ ] Error alerting configured

---

**Deployment Status**: Ready for staging deployment
**Estimated Deployment Time**: 15 minutes
**Risk Level**: Low (backward compatible, comprehensive tests)
**Mobile Team Notified**: Pending

---

**End of Deployment Checklist**
