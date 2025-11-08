# V2 Migration Strategy - Full Migration with V1 Compatibility Shim

> **Decision**: Migrate fully to V2 as the canonical API, with a thin V1 compatibility shim

**Date**: November 7, 2025  
**Status**: Recommended Approach  
**Risk Level**: 🟢 Low (with proper instrumentation)

---

## Executive Summary

**Recommendation**: Make V2 the **single source of truth** for all business logic, while maintaining a **thin V1 compatibility shim** that translates field names and delegates to V2.

**Why This Approach**:
- Kotlin app is NEW (not built yet) → can use V2 from day 1
- No evidence of production V1 API clients for Operations/Attendance
- V1 already deprecated with sunset date
- Eliminates code duplication while maintaining compatibility
- Easy to remove V1 shim once usage reaches zero

---

## Architecture Decision

### ❌ What We're NOT Doing

**Option 1: Keep Both V1 and V2 Full Implementations**
```
Problems:
- Double maintenance burden (2 serializers, 2 viewsets, 2 test suites)
- Code duplication and drift
- Confusion about which version to use
- Double the testing surface
```

### ✅ What We're DOING

**Option 2: V2 Canonical + V1 Thin Shim**
```
Benefits:
- Single source of truth (V2)
- V1 clients still work (through shim)
- Minimal code duplication
- Easy to remove V1 later (just delete shim)
- Clear migration path
```

---

## Implementation Steps

### Phase 1: Audit Current Usage (Week 1)

#### Step 1.1: Add Usage Tracking
```python
# apps/core/middleware/api_usage_tracking.py
class APIUsageTrackingMiddleware:
    """Track v1 vs v2 API usage"""
    
    def __call__(self, request):
        if '/api/v1/' in request.path or self.is_legacy_path(request.path):
            # Log v1 usage
            logger.info(
                "V1_API_USAGE",
                extra={
                    'path': request.path,
                    'user': request.user.id if request.user.is_authenticated else None,
                    'user_agent': request.META.get('HTTP_USER_AGENT'),
                    'ip': request.META.get('REMOTE_ADDR'),
                }
            )
```

#### Step 1.2: Search For V1 Usage
```bash
# Check web frontend
grep -r "api/v1/" frontend/
grep -r "/api/operations/" frontend/
grep -r "/api/attendance/" frontend/

# Check templates
grep -r "api/v1/" templates/

# Check if any AJAX calls to v1
find . -name "*.js" -exec grep -l "api/v1\|/api/operations/\|/api/attendance/" {} \;
```

**Action**: Document all v1 clients found

#### Step 1.3: Instrument for 7 Days
- Deploy usage tracking to staging
- Monitor for 1 week
- Identify all v1 API consumers

---

### Phase 2: Create V1 Compatibility Shim (Week 1-2)

#### Step 2.1: Create Field Mapper

```python
# apps/api/v1/field_mapper.py
"""
V1 ↔ V2 Field Name Mapping

Translates between v1 (legacy) and v2 (clean) field names.
"""

V1_TO_V2_FIELD_MAPPING = {
    # Jobs/Jobneed
    'jobneedname': 'title',
    'jobneedneed': 'description',
    'people': 'assigned_to',
    'jobtype': 'job_type',
    
    # Add more mappings as needed
}

V2_TO_V1_FIELD_MAPPING = {v: k for k, v in V1_TO_V2_FIELD_MAPPING.items()}


def map_v1_to_v2(data: dict) -> dict:
    """Convert v1 field names to v2"""
    if not isinstance(data, dict):
        return data
    
    mapped = {}
    for k, v in data.items():
        new_key = V1_TO_V2_FIELD_MAPPING.get(k, k)
        
        # Recursively map nested objects
        if isinstance(v, dict):
            mapped[new_key] = map_v1_to_v2(v)
        elif isinstance(v, list):
            mapped[new_key] = [
                map_v1_to_v2(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            mapped[new_key] = v
    
    return mapped


def map_v2_to_v1(data: dict) -> dict:
    """Convert v2 field names back to v1"""
    if not isinstance(data, dict):
        return data
    
    mapped = {}
    for k, v in data.items():
        new_key = V2_TO_V1_FIELD_MAPPING.get(k, k)
        
        # Recursively map nested objects
        if isinstance(v, dict):
            mapped[new_key] = map_v2_to_v1(v)
        elif isinstance(v, list):
            mapped[new_key] = [
                map_v2_to_v1(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            mapped[new_key] = v
    
    return mapped
```

#### Step 2.2: Create V1 Shim ViewSets

```python
# apps/activity/api/v1_compat/viewsets.py
"""
V1 Compatibility Shim

Thin adapter that translates v1 requests to v2, calls v2 logic,
and translates responses back to v1 format.
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from apps.activity.api.v2.viewsets import JobViewSetV2
from apps.api.v1.field_mapper import map_v1_to_v2, map_v2_to_v1


class JobViewSetV1Compat(JobViewSetV2):
    """
    V1 compatibility shim for Jobs.
    
    Delegates all logic to JobViewSetV2 with field name translation.
    """
    
    def create(self, request, *args, **kwargs):
        # Translate v1 request to v2
        v2_data = map_v1_to_v2(request.data)
        request._full_data = v2_data
        
        # Call v2 logic
        response = super().create(request, *args, **kwargs)
        
        # Translate v2 response back to v1
        if response.status_code in [200, 201]:
            response.data['data'] = map_v2_to_v1(response.data.get('data', {}))
        
        return response
    
    def list(self, request, *args, **kwargs):
        # Call v2 logic
        response = super().list(request, *args, **kwargs)
        
        # Translate v2 response back to v1
        if response.status_code == 200:
            results = response.data.get('data', {}).get('results', [])
            response.data['data']['results'] = [
                map_v2_to_v1(item) for item in results
            ]
        
        return response
    
    # Similar for retrieve, update, partial_update, destroy
    # All custom actions (@action decorated methods) also need translation
```

#### Step 2.3: Update V1 URLs to Use Shim

```python
# apps/api/v1/operations_urls.py (NEW - replace existing v1 routes)
from apps.activity.api.v1_compat.viewsets import JobViewSetV1Compat

router = DefaultRouter()
router.register(r'jobs', JobViewSetV1Compat, basename='job-v1-compat')

urlpatterns = [
    path('', include(router.urls)),
]
```

---

### Phase 3: Freeze V1 (Week 2)

#### Feature Freeze
```python
# Add to v1 viewsets
class JobViewSetV1Compat(JobViewSetV2):
    """
    ⚠️ FROZEN: V1 API is deprecated and feature-frozen.
    
    No new features will be added to v1.
    Security fixes only.
    Migrate to v2 before Jan 31, 2026.
    """
```

#### Add Deprecation Headers
Already done via `APIDeprecationMiddleware`

#### Document Migration Path

---

### Phase 4: Kotlin App Uses V2 Only (Weeks 3-20)

**Directive**: Kotlin/Android app must use `/api/v2/` endpoints ONLY.

**Benefits**:
- Clean field names from day 1
- No technical debt
- Best practices baked in
- Modern response envelopes

---

### Phase 5: Migrate Existing Clients (If Any) (Weeks 3-8)

#### If Web Frontend Uses V1:

**Option A: Update Frontend to V2** (Recommended)
```javascript
// Before (v1)
const response = await fetch('/api/v1/operations/jobs/', {
    method: 'POST',
    body: JSON.stringify({
        jobneedname: 'Fix HVAC',
        jobneedneed: 'Unit not cooling',
        people: [123, 456]
    })
});

// After (v2)
const response = await fetch('/api/v2/operations/jobs/', {
    method: 'POST',
    body: JSON.stringify({
        title: 'Fix HVAC',
        description: 'Unit not cooling',
        assigned_to: [123, 456]
    })
});
```

**Option B: Keep Frontend on V1 Shim** (If migration is complex)
- No changes needed
- Frontend continues working through shim
- Migrate when convenient

---

### Phase 6: Monitor and Remove V1 (Ongoing)

#### Monitoring Dashboard
```sql
-- Track v1 usage over time
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as v1_requests,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT ip_address) as unique_ips
FROM api_usage_logs
WHERE api_version = 'v1'
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

#### Removal Triggers
Remove V1 shim when:
1. **Zero traffic for 90 consecutive days**, OR
2. **Sunset date reached** (Jan 31, 2026)

#### Removal Process
```python
# Step 1: Add 410 Gone responses
class V1GoneMiddleware:
    """Return 410 Gone for all v1 requests"""
    
    def __call__(self, request):
        if self.is_v1_request(request):
            return JsonResponse({
                'error': 'API v1 has been removed',
                'message': 'Please migrate to v2',
                'sunset_date': '2026-01-31',
                'documentation': '/docs/kotlin-frontend/V2_MIGRATION_STRATEGY.md'
            }, status=410)
        
        return self.get_response(request)

# Step 2: After 30 days of 410, delete v1 code
```

---

## Migration Guide for Clients

### Field Name Mapping Table

| V1 Field Name | V2 Field Name | Type | Notes |
|---------------|---------------|------|-------|
| `jobneedname` | `title` | string | Job title |
| `jobneedneed` | `description` | string | Job description |
| `people` | `assigned_to` | array[int] | Assigned user IDs |
| `jobtype` | `job_type` | string | Job type enum |
| `bu_id` | `bu_id` | int | No change |
| `client_id` | `client_id` | int | No change |

### Response Envelope Changes

**V1 Response** (varies by endpoint):
```json
{
    "id": 123,
    "jobneedname": "Fix HVAC",
    "status": "pending"
}
```

**V2 Response** (standardized):
```json
{
    "success": true,
    "data": {
        "id": 123,
        "title": "Fix HVAC",
        "status": "pending"
    },
    "errors": null,
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-11-07T12:34:56Z"
}
```

### Error Response Changes

**V1 Errors** (Django default):
```json
{
    "jobneedname": ["This field is required."]
}
```

**V2 Errors** (standardized):
```json
{
    "success": false,
    "data": null,
    "errors": [
        {
            "error_code": "VALIDATION_ERROR",
            "field": "title",
            "message": "This field is required.",
            "details": null
        }
    ],
    "correlation_id": "...",
    "timestamp": "..."
}
```

---

## Testing Strategy

### V1 Shim Tests

```python
# apps/activity/api/v1_compat/tests/test_field_mapping.py
def test_v1_create_maps_to_v2():
    """Test v1 request fields are translated to v2"""
    client = APIClient()
    client.force_authenticate(user=user)
    
    v1_payload = {
        'jobneedname': 'Fix HVAC',
        'jobneedneed': 'Unit not cooling',
        'people': [user.id]
    }
    
    response = client.post('/api/v1/operations/jobs/', v1_payload)
    
    assert response.status_code == 201
    # Response should have v1 field names
    assert 'jobneedname' in response.data
    assert response.data['jobneedname'] == 'Fix HVAC'
    
    # But database should use actual model fields
    job = Jobneed.objects.get(id=response.data['id'])
    assert job.jobneedname == 'Fix HVAC'  # Model hasn't changed


def test_v2_uses_clean_names():
    """Test v2 uses clean field names"""
    client = APIClient()
    client.force_authenticate(user=user)
    
    v2_payload = {
        'title': 'Fix HVAC',
        'description': 'Unit not cooling',
        'assigned_to': [user.id]
    }
    
    response = client.post('/api/v2/operations/jobs/', v2_payload)
    
    assert response.status_code == 201
    # Response should have v2 field names
    assert 'title' in response.data['data']
    assert response.data['data']['title'] == 'Fix HVAC'
```

### Round-Trip Tests

```python
def test_v1_to_v2_to_v1_round_trip():
    """Ensure v1 data survives round trip through v2"""
    v1_data = {
        'jobneedname': 'Test Job',
        'people': [1, 2, 3]
    }
    
    # Convert to v2
    v2_data = map_v1_to_v2(v1_data)
    assert v2_data == {'title': 'Test Job', 'assigned_to': [1, 2, 3]}
    
    # Convert back to v1
    v1_again = map_v2_to_v1(v2_data)
    assert v1_again == v1_data
```

---

## Timeline

### Week 1: Audit & Prepare
- ✅ Add usage tracking
- ✅ Search for v1 clients
- ✅ Monitor for 7 days
- ✅ Document findings

### Week 2: Implement Shim
- ✅ Create field mapper
- ✅ Create v1 compat viewsets
- ✅ Update v1 URLs to use shim
- ✅ Write shim tests
- ✅ Deploy to staging

### Week 3: Validate
- ✅ Run full test suite
- ✅ Test v1 shim manually
- ✅ Test v2 directly
- ✅ Generate OpenAPI schema
- ✅ Update documentation

### Week 4-20: Kotlin Development
- ✅ Kotlin app uses v2 only
- ⬜ Web frontend migrates (if needed)
- ⬜ Monitor v1 usage
- ⬜ Communicate with clients

### Jan 31, 2026: V1 Sunset
- ⬜ Remove v1 shim code
- ⬜ Update documentation
- ⬜ Celebrate clean codebase 🎉

---

## Success Criteria

### Technical
- ✅ Single service layer (v2)
- ✅ V1 clients still work (through shim)
- ✅ V2 clients work natively
- ✅ No code duplication in business logic
- ✅ All tests passing
- ✅ OpenAPI schema validates

### Business
- ✅ Zero breaking changes for existing clients
- ✅ Kotlin app development not blocked
- ✅ Clear migration path documented
- ✅ Monitoring in place
- ✅ Sunset date communicated

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Unknown v1 clients break | Low | High | Usage tracking + 90-day grace period |
| Field mapping bugs | Medium | Medium | Comprehensive round-trip tests |
| Performance overhead from shim | Low | Low | Shim is thin (just field renaming) |
| Team adds features to v1 | Medium | Low | Feature freeze + code owners |
| Subtle behavior differences | Low | Medium | Adapter tests + snapshot tests |

---

## Conclusion

**Recommended Path**: 
1. Make V2 the canonical API (already done ✅)
2. Create thin V1 compatibility shim (Week 2)
3. Kotlin app uses V2 only (Week 3+)
4. Monitor v1 usage and migrate clients
5. Remove v1 shim at sunset or zero traffic

**Benefits**:
- ✅ Single source of truth
- ✅ No code duplication
- ✅ Backward compatibility maintained
- ✅ Clear migration path
- ✅ Easy to remove later

**Status**: Ready to implement Week 2 tasks

---

**Document Version**: 1.0  
**Last Updated**: Nov 7, 2025  
**Next Review**: After Week 1 audit complete
