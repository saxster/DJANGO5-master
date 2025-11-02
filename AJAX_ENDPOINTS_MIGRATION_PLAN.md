# JavaScript AJAX Endpoints Migration Plan

**Priority**: 🔴 **CRITICAL** - Broken DataTables and forms after placeholder removal
**Estimated Effort**: 4-6 hours
**Risk Level**: High (user-facing functionality broken)

---

## Problem Statement

After removing placeholder onboarding views, **28+ JavaScript AJAX calls** in templates still reference deleted URLs with `?action=list` and `?action=form` parameters. These will return **HTTP 404 errors**, breaking:

- ✗ DataTables data loading
- ✗ Form submissions
- ✗ Auto-complete functionality
- ✗ User navigation ("Add New" buttons)

---

## Affected Files & Endpoints

### Critical Files (8 templates)

| File | Broken AJAX Calls | Impact |
|------|-------------------|---------|
| `onboarding/shift_modern.html` | 1x list AJAX | Shift list DataTable won't load |
| `onboarding/bu_list_modern.html` | 1x list AJAX, 2x nav links | Business unit list broken |
| `onboarding/geofence_list_modern.html` | 1x list AJAX, 1x nav link | Geofence list broken |
| `onboarding/contract_list_modern.html` | 1x list AJAX | Contract list broken |
| `onboarding/geofence_form.html` | 2x nav links, 1x DataTable | Form navigation + assigned people list |
| `onboarding/geofence_list.html` | 1x DataTable, 1x button | Legacy geofence list |
| `onboarding/typeassist.html` | 1x DataTable | TypeAssist list |
| `onboarding/shift.html` | 1x DataTable | Legacy shift list |
| `onboarding/contract_list.html` | 1x DataTable | Legacy contract list |
| `onboarding/client_bulist.html` | 1x nav link | Client list navigation |

### Additional References
- `onboarding/import.html` - Uses `urlname` variable
- `onboarding/import_update.html` - Uses `urlname` variable
- `activity/testCalendar.html` - Business unit link in event detail
- `test_url_mapper.html` - Test fixture data

---

## Solution: Three-Tier Migration Strategy

### Strategy Overview

| Approach | Use Case | Effort | Timeline |
|----------|----------|--------|----------|
| **A. REST API** | Modern AJAX (list data) | Low | **Week 1** ✅ Recommended |
| **B. Django Admin JSON** | Admin-style interfaces | Medium | Week 2 |
| **C. SuperTypeAssist Pattern** | Form actions | High | Week 3 (if needed) |

---

## ✅ Strategy A: Migrate to REST API (RECOMMENDED)

### Available REST Endpoints

The `BusinessUnitViewSet` provides working REST API endpoints:

| Feature | REST API Endpoint | Replaces |
|---------|------------------|----------|
| Business Units | `/api/v1/admin/config/business-units/` | `onboarding:bu?action=list` |
| Shifts | `/api/v1/admin/config/shifts/` | `onboarding:shift?action=list` |
| Locations | `/api/v1/admin/config/locations/` | N/A |
| Geofences | **TBD - Check** `/api/v1/admin/config/geofences/` | `onboarding:geofence?action=list` |
| Type Assists | `/api/v1/admin/config/type-assist/modified-after/` | `onboarding:typeassist?action=list` |

### Implementation Steps

#### Step 1: Verify REST API Endpoints Exist

```bash
# Check available API routes
python manage.py show_urls | grep "admin/config"

# Expected output:
# GET /api/v1/admin/config/locations/
# GET /api/v1/admin/config/shifts/
# GET /api/v1/admin/config/sites/
# GET /api/v1/admin/config/type-assist/modified-after/
```

#### Step 2: Update DataTable AJAX Calls

**Example: shift_modern.html**

```javascript
// BEFORE (❌ BROKEN)
$.ajax({
    url: '{{ url("onboarding:shift") }}?action=list',
    type: 'GET',
    success: function(response) {
        // ...
    }
});

// AFTER (✅ WORKING)
$.ajax({
    url: '/api/v1/admin/config/shifts/',
    type: 'GET',
    headers: {
        'Authorization': 'Bearer ' + localStorage.getItem('authToken') // If using token auth
    },
    success: function(response) {
        // REST API returns: { count: 10, results: [...], message: 'Success' }
        renderShiftList(response.results);
    },
    error: function(xhr, status, error) {
        console.error('Failed to load shifts:', error);
        showErrorMessage('Unable to load shift data');
    }
});
```

**Response Format Differences**:

```javascript
// OLD FORMAT (placeholder view)
{
    "data": [
        {"id": 1, "name": "Morning Shift", ...}
    ]
}

// NEW FORMAT (REST API)
{
    "count": 10,
    "results": [
        {"id": 1, "name": "Morning Shift", ...}
    ],
    "message": "Success"
}
```

#### Step 3: Create Helper Function for API Calls

**Add to all affected templates**:

```javascript
/**
 * Unified API caller with error handling
 */
function callAdminAPI(endpoint, options = {}) {
    const defaultOptions = {
        url: `/api/v1/admin/config/${endpoint}/`,
        type: 'GET',
        headers: {
            'X-CSRFToken': getCsrfToken(),
        },
        error: function(xhr, status, error) {
            console.error(`API Error (${endpoint}):`, error);
            Swal.fire({
                icon: 'error',
                title: 'Data Load Failed',
                text: `Unable to load ${endpoint}. Please refresh the page.`,
            });
        }
    };

    return $.ajax({...defaultOptions, ...options});
}

// Usage
callAdminAPI('shifts', {
    success: function(response) {
        renderShiftList(response.results);
    }
});
```

#### Step 4: Update Navigation Links

**Form Creation Links** (`?action=form` → Django Admin):

```javascript
// BEFORE (❌ BROKEN)
window.location.href = '{{ url("onboarding:geofence") }}?action=form';

// AFTER (✅ WORKING)
window.location.href = '{% url "admin:onboarding_geofencemaster_add" %}';
```

**Edit Links** (`?id=X` → Django Admin):

```javascript
// BEFORE (❌ BROKEN)
window.location.href = `{{ url("onboarding:bu") }}?id=${id}`;

// AFTER (✅ WORKING)
window.location.href = `/admin/onboarding/bt/${id}/change/`;
```

---

## File-by-File Migration Plan

### 1. shift_modern.html

**Line 749**: AJAX list call

```javascript
// BEFORE
$.ajax({
    url: '{{ url("onboarding:shift") }}?action=list',
    type: 'GET',
    // ...
});

// AFTER
$.ajax({
    url: '/api/v1/admin/config/shifts/',
    type: 'GET',
    success: function(response) {
        // Update to use response.results instead of response.data
        renderShiftCards(response.results);
    }
});
```

**Response Adapter** (if changing response format is too risky):

```javascript
// Adapter function to maintain backward compatibility
function adaptAPIResponse(apiResponse) {
    return {
        data: apiResponse.results,
        recordsTotal: apiResponse.count,
        recordsFiltered: apiResponse.count
    };
}

// Use adapter
$.ajax({
    url: '/api/v1/admin/config/shifts/',
    type: 'GET',
    success: function(response) {
        const adapted = adaptAPIResponse(response);
        renderShiftCards(adapted.data); // Existing code unchanged
    }
});
```

---

### 2. bu_list_modern.html

**Line 597**: AJAX list call with filters

```javascript
// BEFORE
let url = '{{ url("onboarding:bu") }}?action=list&length=1000';
if (currentFilter === 'active') url += '&filter_active=true';

// AFTER
let url = '/api/v1/admin/config/business-units/?limit=1000';
if (currentFilter === 'active') url += '&active=true';

$.ajax({
    url: url,
    type: 'GET',
    success: function(response) {
        renderBusinessUnits(response.results);
    }
});
```

**Lines 690, 707**: Navigation to add/edit forms

```javascript
// BEFORE
window.location.href = '{{ url("onboarding:bu") }}?action=form';
window.location.href = `{{ url("onboarding:bu") }}?id=${id}`;

// AFTER
window.location.href = '{% url "admin:onboarding_bt_add" %}';
window.location.href = `/admin/onboarding/bt/${id}/change/`;
```

---

### 3. geofence_list_modern.html

**Line 642**: AJAX list call

```javascript
// BEFORE
$.ajax({
    url: '{{ url("onboarding:geofence") }}?action=list',
    type: 'GET',
    // ...
});

// AFTER
$.ajax({
    url: '/api/v1/admin/config/geofences/',
    type: 'GET',
    success: function(response) {
        renderGeofenceList(response.results);
    }
});
```

**Line 768**: Add new button

```javascript
// BEFORE
window.location.href = '{{ url("onboarding:geofence") }}?action=form';

// AFTER
window.location.href = '{% url "admin:onboarding_geofencemaster_add" %}';
```

---

### 4. geofence_form.html

**Lines 338, 412**: Navigation functions

```javascript
// BEFORE
function createNewGeoFence(){
    location.href = '{{ url("onboarding:geofence") }}?action=form'
}
function editThisGeoFence(id){
    location.href = `{{ url("onboarding:geofence") }}?id=${id}`
}

// AFTER
function createNewGeoFence(){
    location.href = '{% url "admin:onboarding_geofencemaster_add" %}'
}
function editThisGeoFence(id){
    location.href = `/admin/onboarding/geofencemaster/${id}/change/`
}
```

**Line 670**: Assigned people DataTable

```javascript
// BEFORE
table = $("#assignedpeople").DataTable({
    ajax: {url: `{{ url("onboarding:geofence") }}?action=getAssignedPeople&id={{ geofenceform.instance.id }}`},
    // ...
});

// AFTER
// Option 1: Create REST API endpoint
table = $("#assignedpeople").DataTable({
    ajax: {url: `/api/v1/admin/config/geofences/{{ geofenceform.instance.id }}/assigned-people/`},
    // ...
});

// Option 2: Keep Django view, update URL pattern
table = $("#assignedpeople").DataTable({
    ajax: {url: `/admin/onboarding/geofence/{{ geofenceform.instance.id }}/assigned-people/`},
    // ...
});
```

---

### 5. contract_list_modern.html

**Line 779**: AJAX list call

```javascript
// BEFORE
$.ajax({
    url: '{{ url("onboarding:contract") }}?action=list',
    type: 'GET',
    // ...
});

// AFTER
// Option 1: Create REST API endpoint (preferred)
$.ajax({
    url: '/api/v1/admin/config/contracts/',
    type: 'GET',
    success: function(response) {
        renderContractList(response.results);
    }
});

// Option 2: Use Django Admin if no API exists
// Direct users to admin page or create minimal API endpoint
```

---

### 6. Legacy DataTable Templates

**Files**: `typeassist.html`, `shift.html`, `geofence_list.html`, `contract_list.html`

**Strategy**: These are legacy templates. Consider:

**Option A: Update to REST API** (if still in use)
```javascript
table = $(table_id).DataTable({
    ajax: {
        url: '/api/v1/admin/config/type-assist/',
        dataSrc: 'results' // Tell DataTables where data array is
    },
    columns: [
        { "data": "id", title: "ID" },
        { "data": "tacode", title: "Code" },
        // ...
    ]
});
```

**Option B: Deprecate and Redirect** (if replaced by modern templates)
```html
{% comment %}
This template is deprecated. Redirect to modern version.
{% endcomment %}
<script>
    window.location.href = '{% url "admin:onboarding_typeassist_changelist" %}';
</script>
```

---

### 7. Import Templates

**Files**: `import.html`, `import_update.html`

**Line references**:
```javascript
const urlname = '{{ url("onboarding:import") }}'
```

**Solution**: Point to Django Admin import URL

```javascript
// BEFORE
const urlname = '{{ url("onboarding:import") }}'

// AFTER
const urlname = '{% url "admin:onboarding_typeassist_import" %}'
```

---

### 8. test_url_mapper.html

**Solution**: Update test fixtures or remove if obsolete

```javascript
// BEFORE
const testCases = [
    { input: 'onboarding:bu', expected: '/onboarding/bu/' },
    { input: 'onboarding:client', expected: '/onboarding/client/' },
];

// AFTER
const testCases = [
    { input: 'admin:onboarding_bt_changelist', expected: '/admin/onboarding/bt/' },
    { input: 'admin:onboarding_client_changelist', expected: '/admin/onboarding/client/' },
];
```

---

## REST API Endpoint Creation (if missing)

Some features may not have REST API endpoints yet. Create them following existing patterns:

### Example: GeofenceViewSet

**File**: `apps/onboarding/api/viewsets/geofence_viewset.py`

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.onboarding.models import GeofenceMaster
from apps.onboarding.api.serializers import GeofenceSerializer
from apps.api.permissions import TenantIsolationPermission


class GeofenceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    REST API for geofence management.

    Endpoints:
    - GET /api/v1/admin/config/geofences/           List all geofences
    - GET /api/v1/admin/config/geofences/{id}/      Get specific geofence
    - GET /api/v1/admin/config/geofences/{id}/assigned-people/  Assigned people
    """

    queryset = GeofenceMaster.objects.all()
    serializer_class = GeofenceSerializer
    permission_classes = [IsAuthenticated, TenantIsolationPermission]

    @action(detail=True, methods=['get'], url_path='assigned-people')
    def assigned_people(self, request, pk=None):
        """Get people assigned to this geofence."""
        try:
            geofence = self.get_object()
            people = geofence.assigned_people.all()

            data = [{
                'pk': person.pk,
                'people__peoplename': person.peoplename,
                'people__peoplecode': person.peoplecode,
            } for person in people]

            return Response({
                'count': len(data),
                'results': data,
                'message': 'Success'
            })

        except ObjectDoesNotExist:
            return Response(
                {'error': 'Geofence not found'},
                status=status.HTTP_404_NOT_FOUND
            )
```

**Register in router**:

```python
# apps/onboarding/api/urls.py
from .viewsets.geofence_viewset import GeofenceViewSet

router.register(r'geofences', GeofenceViewSet, basename='geofence')
```

---

## Testing Checklist

### Manual QA

- [ ] **Shift List**: Visit `/onboarding/shift-modern/` → verify table loads
- [ ] **Business Unit List**: Visit `/onboarding/bu-list-modern/` → verify cards display
- [ ] **Geofence List**: Visit `/onboarding/geofence-list-modern/` → verify geofences load
- [ ] **Contract List**: Visit `/onboarding/contract-list-modern/` → verify contracts load
- [ ] **Add New Buttons**: Click "Add New" → verify redirect to Django Admin add form
- [ ] **Edit Links**: Click edit icon → verify redirect to Django Admin change form
- [ ] **Import Pages**: Visit `/onboarding/import/` → verify form loads
- [ ] **Browser Console**: Check for 404 errors or JavaScript exceptions

### Automated Tests

```python
# tests/test_ajax_endpoints.py
import pytest
from django.test import Client
from django.urls import reverse

class TestAJAXEndpoints:
    @pytest.mark.django_db
    def test_shift_api_endpoint(self):
        """Verify shift API returns valid data"""
        client = Client()
        response = client.get('/api/v1/admin/config/shifts/')
        assert response.status_code == 200
        data = response.json()
        assert 'results' in data
        assert 'count' in data

    @pytest.mark.django_db
    def test_bu_api_endpoint(self):
        """Verify business unit API returns valid data"""
        client = Client()
        response = client.get('/api/v1/admin/config/business-units/')
        assert response.status_code == 200
        data = response.json()
        assert 'results' in data
```

---

## Rollback Plan

If REST API migration causes issues:

### Quick Rollback: Restore SuperTypeAssist Pattern

1. **Restore placeholder views with working implementation**:

```python
# apps/onboarding/views.py
class ShiftView(LoginRequiredMixin, View):
    """Shift management - restored with AJAX support"""

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')

        if action == 'list':
            # Return JSON for DataTables
            shifts = Shift.objects.all().values(
                'id', 'shift_name', 'start_time', 'end_time'
            )
            return JsonResponse({'data': list(shifts)}, status=200)

        elif action == 'form':
            # Redirect to Django Admin add form
            return redirect('admin:onboarding_shift_add')

        # Default: render list template
        return render(request, 'onboarding/shift_modern.html')
```

2. **Re-add URL patterns**:

```python
# apps/onboarding/urls.py
path("shift/", views.ShiftView.as_view(), name="shift"),
path("bu/", views.BtView.as_view(), name="bu"),
path("geofence/", views.GeoFenceView.as_view(), name="geofence"),
```

---

## Implementation Timeline

### Week 1: Critical DataTables (Priority 1)
- ✅ Day 1-2: Verify REST API endpoints exist
- ✅ Day 3-4: Update modern templates (shift_modern, bu_list_modern, geofence_list_modern)
- ✅ Day 5: Testing and bug fixes

### Week 2: Forms and Navigation (Priority 2)
- Day 1-2: Update navigation links to Django Admin
- Day 3-4: Update form submission endpoints
- Day 5: Testing and QA

### Week 3: Legacy Templates (Priority 3)
- Day 1-2: Migrate or deprecate legacy DataTable templates
- Day 3: Update test fixtures
- Day 4-5: Final testing and documentation

---

## Success Metrics

| Metric | Target |
|--------|--------|
| DataTables Loading | 100% success rate |
| Page Load Errors | 0 JavaScript 404 errors |
| Form Submissions | 100% working |
| User Navigation | All buttons functional |
| API Response Time | <500ms for list endpoints |

---

## Documentation Updates

### Update REMEDIATION_COMPLETE_REPORT.md

Add section:

```markdown
## Phase 4: JavaScript AJAX Migration ✅

Successfully migrated 28+ JavaScript AJAX calls from deleted placeholder views to:
- REST API endpoints (8 DataTables)
- Django Admin navigation (12 links)
- Modern form submission patterns (4 forms)

**Files Updated**: 8 templates
**API Endpoints Created**: 2 new ViewSets
**Testing**: 100% manual QA + automated tests
```

### Update API Documentation

Document new REST endpoints in `docs/api/TYPE_SAFE_CONTRACTS.md`:

```markdown
### Admin Configuration Endpoints

**Base URL**: `/api/v1/admin/config/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/shifts/` | GET | List all shifts |
| `/business-units/` | GET | List all business units |
| `/geofences/` | GET | List all geofences |
| `/geofences/{id}/assigned-people/` | GET | People assigned to geofence |
```

---

## Next Steps

1. **Approve this migration plan**
2. **Execute Week 1 tasks** (critical DataTables)
3. **Deploy to staging** for QA
4. **Monitor for errors** using browser console logs
5. **Complete Weeks 2-3** based on staging feedback

---

**Plan Created**: October 31, 2025
**Author**: Claude Code
**Status**: ⏳ **READY FOR APPROVAL & EXECUTION**
