# Transitional Artifacts Tracker
**Purpose**: Track temporary code, compatibility shims, and migration artifacts that should be reviewed/removed over time
**Last Updated**: November 8, 2025
**Status**: ACTIVE TRACKING

---

## Overview

This document tracks all transitional code artifacts created during the V1→V2 API migration. These artifacts exist to maintain backward compatibility during the migration period and should be reviewed for removal once all clients have migrated.

---

## Active Transitional Artifacts

### 1. Generic Sync Base Serializers

**File**: `apps/core/serializers/sync_base_serializers.py`

**Created**: November 8, 2025

**Purpose**: Provide backward-compatible sync serializers for legacy sync endpoints after V1 deletion

**Used By**:
- `apps/attendance/views/attendance_sync_views.py`
- `apps/activity/views/task_sync_views.py`
- `apps/y_helpdesk/views_extra/ticket_sync_views.py`
- `apps/work_order_management/views_extra/wom_sync_views.py`

**Migration Path**:
1. Once all sync operations migrate to V2 batch sync (`BatchSyncRequestSerializer`)
2. Update the 4 view files to use V2 serializers
3. Delete `sync_base_serializers.py`
4. Remove legacy sync endpoints

**Target Removal Date**: Q1 2026 (after mobile client migration)

**Risk Level**: LOW - Well-isolated, only affects 4 sync views

---

### 2. Legacy V1 Endpoints

**File**: `intelliwiz_config/urls_optimized.py` (lines 97-102)

**Created**: Original implementation; retained during migration

**Purpose**: Support specialized hardware and legacy mobile clients

**Active Endpoints**:
```python
path('api/v1/biometrics/', include('apps.api.biometrics_urls')),
path('api/v1/assets/nfc/', include('apps.activity.api.nfc_urls')),
path('api/v1/journal/', include(('apps.journal.urls', 'journal')...)),
path('api/v1/wellness/', include(('apps.wellness.urls', 'wellness')...)),
path('api/v1/search/', include(('apps.search.urls', 'search'))),
path('api/v1/helpbot/', include('apps.helpbot.urls')),
```

**Migration Path**:
1. **Biometrics** (`/api/v1/biometrics/`):
   - Hardware: Facial recognition devices, fingerprint scanners
   - Action: Create V2 equivalent with same endpoints for firmware compatibility
   - Timeline: Q2 2026 (requires firmware updates)

2. **NFC** (`/api/v1/assets/nfc/`):
   - Hardware: NFC readers for asset tagging
   - Action: Create V2 equivalent; coordinate with hardware vendor
   - Timeline: Q2 2026

3. **Journal** (`/api/v1/journal/`):
   - Client: Legacy Kotlin mobile app versions
   - Action: Update app to use `/api/v2/wellness/journal/`
   - Timeline: Q1 2026 (force update required)

4. **Wellness** (`/api/v1/wellness/`):
   - Client: Legacy mobile apps
   - Action: Migrate to `/api/v2/wellness/`
   - Timeline: Q1 2026

5. **Search** (`/api/v1/search/`):
   - Action: Migrate to V2 search endpoint (create if doesn't exist)
   - Timeline: Q1 2026

6. **Helpbot** (`/api/v1/helpbot/`):
   - Action: Already has V2 equivalent at `/api/v2/helpbot/`
   - Timeline: Q1 2026 (low priority)

**Target Removal Date**: Q2 2026 (hardware), Q1 2026 (software)

**Risk Level**: MEDIUM - External dependencies (hardware firmware, mobile app updates)

---

### 3. Kotlin Status Documentation (Outdated)

**Files**:
- `docs/kotlin-frontend/DOCUMENTATION_STATUS.md`
- `docs/kotlin-frontend/COMPREHENSIVE_INSPECTION_REPORT.md`
- `docs/kotlin-frontend/API_VERSION_RESOLUTION_STRATEGY.md`

**Created**: October 30, 2025 (before V2 implementation)

**Issue**: Documents state "V2 endpoints missing" when they're now fully implemented

**Migration Path**:
1. Update all 3 files with banner stating V2 is now complete (Nov 7-8, 2025)
2. Add reference to `REST_API_MIGRATION_COMPLETE.md` for current status
3. Consider archiving to `docs/kotlin-frontend/archive/` if no longer needed

**Target Update Date**: November 8, 2025 (PENDING)

**Risk Level**: LOW - Documentation only, no functional impact

---

## Removed Artifacts (Successfully Migrated)

### V1 API Code

**Deleted**: November 7-8, 2025

**What Was Removed**:
- 27 V1 Python files (~3,000 lines)
- V1 view modules, URL routers, middleware
- V1 test files (replaced with V2 tests)
- Empty `apps/api/v1/` directory (removed Nov 8, 2025)

**Replaced With**:
- V2 API implementation in `apps/api/v2/`
- Type-safe Pydantic serializers
- Comprehensive test suite (115+ tests)

**Status**: ✅ COMPLETE

---

## Migration Monitoring Metrics

### Endpoint Usage Tracking

**Recommendation**: Add telemetry to track V1 vs V2 usage

**Suggested Metrics**:
```python
# Add to middleware or view decorators
{
    'endpoint_version': 'v1' | 'v2',
    'endpoint_path': str,
    'client_type': 'mobile' | 'web' | 'hardware',
    'timestamp': datetime,
    'user_agent': str
}
```

**Analysis Queries**:
- V1 usage by endpoint (identify most-used legacy endpoints)
- Client types still using V1 (mobile app versions, hardware devices)
- V1 usage trends over time (should decrease)

**Action Threshold**:
- When V1 usage drops below 5% for an endpoint → deprecate
- When V1 usage is 0% for 30 days → remove

---

## Deprecation Warnings

### Implementation Plan

**Phase 1: Soft Warnings** (Dec 2025)
```python
# Add to V1 views
warnings.warn(
    "API v1 is deprecated. Please migrate to /api/v2/. "
    "See docs/api/v1-to-v2-migration.md for details.",
    DeprecationWarning
)

# Add to response headers
response['X-API-Deprecation'] = 'true'
response['X-API-Sunset-Date'] = '2026-03-31'
```

**Phase 2: Hard Warnings** (Feb 2026)
```python
# Return deprecation notice in response
{
    "warning": "This endpoint will be removed on 2026-03-31. Migrate to /api/v2/",
    "migration_guide": "https://docs.example.com/api/migration",
    "data": {...}  # Actual response data
}
```

**Phase 3: Sunset** (Mar 31, 2026)
```python
# Return 410 Gone
return Response(
    {"error": "This endpoint has been removed. Use /api/v2/ instead."},
    status=status.HTTP_410_GONE
)
```

---

## Compatibility Shims

### None Currently Active

All compatibility has been maintained through:
1. **Generic sync serializers** - Backward-compatible base classes
2. **Legacy V1 endpoints** - Intentionally maintained for hardware
3. **Gradual migration** - No breaking changes enforced yet

**Future Shims** (if needed):
- Adapter pattern for V1→V2 request translation
- Proxy views that redirect V1 to V2
- Middleware to auto-upgrade V1 requests to V2

---

## Review Schedule

### Monthly Review (1st of each month)

**Check**:
- [ ] V1 endpoint usage metrics
- [ ] Mobile app version distribution (how many on legacy)
- [ ] Hardware firmware versions (biometric/NFC devices)
- [ ] Client migration progress

**Report To**: Tech lead, product manager

### Quarterly Review (Q1, Q2, Q3, Q4)

**Assess**:
- [ ] Feasibility of removing specific V1 endpoints
- [ ] Need for extended deprecation timeline
- [ ] Impact of removal on users/clients
- [ ] Cost of maintaining legacy endpoints

**Deliverable**: Migration progress report with removal recommendations

---

## Rollback Plan

### If V2 Issues Discovered

**Scenario**: Critical bug in V2 API requires rollback

**Action**:
1. V1 endpoints remain active (no immediate risk)
2. Direct clients back to V1 temporarily
3. Fix V2 issue
4. Redeploy V2
5. Resume migration

**Risk Mitigation**:
- V1 endpoints preserved specifically for this scenario
- No breaking changes in V2 that can't be rolled back
- Comprehensive test suite catches most issues pre-deployment

---

## Governance

### Artifact Addition Process

**When creating new transitional code**:
1. Add entry to this document with:
   - Purpose and justification
   - Files affected
   - Migration path
   - Target removal date
   - Risk level
2. Tag code with comment:
   ```python
   # TRANSITIONAL: Added Nov 2025 for V1→V2 migration
   # Remove after Q1 2026 when all clients migrate to V2
   # See: TRANSITIONAL_ARTIFACTS_TRACKER.md
   ```
3. Create calendar reminder for review/removal

### Artifact Removal Process

**Before removing transitional code**:
1. Check usage metrics (must be <5% or 0% for 30 days)
2. Notify stakeholders (mobile team, hardware vendors)
3. Add deprecation warning (30 days before removal)
4. Create rollback plan
5. Remove code
6. Update this document (move to "Removed Artifacts")

---

## Contact & Escalation

**Questions about this tracker**:
- Tech Lead: Migration planning and timeline
- DevOps: Metrics and monitoring
- Product: Client migration coordination

**Escalation**:
- If removal blocked by external dependency → Product Manager
- If removal causes production issues → Tech Lead
- If timeline needs extension → Engineering Manager

---

**Document Version**: 1.0
**Created**: November 8, 2025
**Next Review**: December 1, 2025
**Owner**: Backend Development Team
