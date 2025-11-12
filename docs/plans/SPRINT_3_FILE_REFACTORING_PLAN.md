# Sprint 3: File Size Refactoring Plan

**Goal:** Refactor 10 files exceeding pragmatic size limits (<500 lines for views/serializers, <1000 lines for tasks)

**Priority:** P1 (Should complete before production scale-up)

**Estimated Effort:** 20-30 hours

---

## High Priority: View Files (3 files, 673+586+602 = 1,861 lines)

### Task 1: Split helpdesk_views.py (673 lines → 3 files)

**Current:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/v2/views/helpdesk_views.py`

**Target Structure:**
```
apps/api/v2/views/
├── helpdesk_list_views.py (~250 lines)
│   ├── TicketListView
│   ├── TicketSearchView
│   └── TicketFilterView
├── helpdesk_detail_views.py (~200 lines)
│   ├── TicketDetailView
│   ├── TicketCreateView
│   └── TicketUpdateView
└── helpdesk_workflow_views.py (~223 lines)
    ├── TicketTransitionView
    ├── TicketEscalateView
    └── TicketAssignView
```

**URL Updates:** `apps/api/v2/urls/helpdesk_urls.py` - Update imports

---

### Task 2: Split people_views.py (586 lines → 2 files)

**Current:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/v2/views/people_views.py`

**Target Structure:**
```
apps/api/v2/views/
├── people_user_views.py (~400 lines)
│   ├── PeopleUsersListView
│   ├── PeopleUserDetailView
│   └── PeopleUserUpdateView
└── people_role_views.py (~186 lines)
    ├── PeopleRolesView
    └── PeopleCapabilitiesView
```

**URL Updates:** `apps/api/v2/urls/people_urls.py` - Update imports

---

### Task 3: Split frontend_serializers.py (602 lines → 3 files)

**Current:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/serializers/frontend_serializers.py`

**Target Structure:**
```
apps/core/serializers/
├── response_mixins.py (~200 lines)
│   └── Response formatting mixins
├── pagination_helpers.py (~200 lines)
│   └── Pagination serializers
└── caching_serializers.py (~202 lines)
    └── Cache-aware serializers
```

**Import Updates:** Update all files importing from `frontend_serializers`

---

## Medium Priority: Task Files >1000 Lines (3 files)

### Task 4: Split journal_wellness_tasks.py (1521 lines → 3 files)

**Current:** `/Users/amar/Desktop/MyCode/DJANGO5-master/background_tasks/journal_wellness_tasks.py`

**Target Structure:**
```
background_tasks/
├── journal_analysis_tasks.py (~500 lines)
│   └── Entry analysis and processing
├── wellness_intervention_tasks.py (~500 lines)
│   └── Intervention triggering and management
└── wellness_content_delivery_tasks.py (~521 lines)
    └── Content delivery and personalization
```

---

### Task 5: Split onboarding_tasks_phase2.py (1447 lines → 3 files)

**Current:** `/Users/amar/Desktop/MyCode/DJANGO5-master/background_tasks/onboarding_tasks_phase2.py`

**Target Structure:**
```
background_tasks/
├── onboarding_validation_tasks.py (~450 lines)
│   └── Input validation and data quality
├── onboarding_integration_tasks.py (~500 lines)
│   └── External system integrations
└── onboarding_notification_tasks.py (~497 lines)
    └── Email and notification workflows
```

---

### Task 6: Split mental_health_intervention_tasks.py (1212 lines → 2 files)

**Current:** `/Users/amar/Desktop/MyCode/DJANGO5-master/background_tasks/mental_health_intervention_tasks.py`

**Target Structure:**
```
background_tasks/
├── crisis_detection_tasks.py (~600 lines)
│   └── Crisis pattern detection and scoring
└── intervention_delivery_tasks.py (~612 lines)
    └── Intervention delivery and tracking
```

---

## Low Priority: Service Files >600 Lines (4 files)

### Task 7: Split secure_file_upload_service.py (1011 lines → 3 files)

**Target:**
```
apps/core/services/
├── file_type_validator.py (~350 lines)
├── filename_security_service.py (~300 lines)
└── file_upload_orchestrator.py (~361 lines)
```

### Task 8: Split photo_authenticity_service.py (833 lines → 2 files)

**Target:**
```
apps/core/services/
├── exif_validator.py (~400 lines)
└── photo_authenticity_checker.py (~433 lines)
```

### Task 9: Split admin_mentor_service.py (830 lines → 3 files)

**Target:**
```
apps/core/services/
├── admin_guide_content.py (~300 lines)
├── admin_tutorial_engine.py (~300 lines)
└── admin_help_service.py (~230 lines)
```

### Task 10: Split advanced_file_validation_service.py (753 lines → 2 files)

**Target:**
```
apps/core/services/
├── file_magic_validator.py (~400 lines)
└── file_content_analyzer.py (~353 lines)
```

---

## Refactoring Guidelines

### Principles
1. **Single Responsibility**: Each new file has ONE clear purpose
2. **Backward Compatibility**: Create facade imports in original files
3. **Test Migration**: Move related tests to new test files
4. **Import Updates**: Use IDE refactoring or grep to update imports

### Pattern

```python
# Original file (becomes facade)
# apps/api/v2/views/helpdesk_views.py
"""
Helpdesk views - LEGACY FACADE

This module has been split for maintainability:
- helpdesk_list_views.py - List and search operations
- helpdesk_detail_views.py - CRUD operations
- helpdesk_workflow_views.py - State transitions

Import from specific modules or use this facade for backward compatibility.
"""
from .helpdesk_list_views import TicketListView, TicketSearchView
from .helpdesk_detail_views import TicketDetailView, TicketCreateView
from .helpdesk_workflow_views import TicketTransitionView, TicketEscalateView

__all__ = [
    'TicketListView', 'TicketSearchView',
    'TicketDetailView', 'TicketCreateView',
    'TicketTransitionView', 'TicketEscalateView',
]
```

### Testing Strategy

1. **Before refactoring**: Run full test suite, save results
2. **After refactoring**: Run same tests - should have identical results
3. **Import validation**: `python manage.py check --deploy`
4. **Coverage**: `pytest --cov` - should maintain or improve coverage

---

## Execution Plan

### Phase 1: High Priority (Views + Serializers)
**Effort:** 8-12 hours
- Tasks 1-3: Split view and serializer files
- High user impact (API layer)
- Clear module boundaries

### Phase 2: Medium Priority (Large Task Files)
**Effort:** 6-9 hours
- Tasks 4-6: Split background task files >1000 lines
- Lower immediate impact (background operations)
- More complex dependencies

### Phase 3: Low Priority (Service Files)
**Effort:** 6-9 hours
- Tasks 7-10: Split service files >600 lines
- Can be deferred to Sprint 4 if needed
- Primarily maintainability improvements

---

## Success Criteria

- [ ] All view files <500 lines
- [ ] All task files <1000 lines (pragmatic threshold)
- [ ] All service files <600 lines (top 10 addressed)
- [ ] 100% test pass rate maintained
- [ ] No breaking changes to APIs
- [ ] Import updates automated/verified
- [ ] Code quality script validates improvements

**Timeline:** Complete Phase 1 in Sprint 3, defer Phases 2-3 to Sprint 4 if needed
