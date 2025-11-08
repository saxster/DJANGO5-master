# ADR 007: Circular Dependency Resolution Strategy

**Status:** Proposed  
**Date:** 2025-11-06  
**Deciders:** Development Team  
**Affected Components:** All apps with circular dependencies (18 critical cycles)  

---

## Context

The codebase has grown organically, resulting in **129 circular import dependencies** between Django apps:
- **18 Critical** (2-3 node cycles requiring immediate fix)
- **20 Warnings** (4-5 node cycles needing attention)
- **91 Info** (longer cycles for review)

Circular dependencies cause:
1. **Import errors** at runtime when circular paths are triggered
2. **Testing difficulties** - Hard to isolate and mock dependencies
3. **Tight coupling** - Changes ripple across multiple apps
4. **Initialization issues** - AppConfig and signal registration failures

### Key Problem Areas

1. **Infrastructure coupling:** `core ↔ journal`, `core ↔ attendance`
2. **Business logic entanglement:** `peoples ↔ activity`, `reports ↔ work_order_management`
3. **API layer violations:** `wellness ↔ api`, `api` imports back into domain apps
4. **Onboarding fragmentation:** 3 separate onboarding apps with circular dependencies
5. **Event-driven needs:** `activity ↔ y_helpdesk`, `scheduler ↔ noc`

---

## Decision

We will resolve circular dependencies using a **multi-pattern approach** based on dependency type:

### Pattern 1: Dependency Inversion
**Use when:** Both apps need shared functionality

**Implementation:**
- Create interface/protocol in `apps/core/interfaces/`
- Both apps depend on interface, not each other
- Use dependency injection where needed

**Example:**
```python
# apps/core/interfaces/knowledge_base_interface.py
from typing import Protocol, List

class KnowledgeBaseProvider(Protocol):
    def search_articles(self, query: str) -> List[dict]:
        ...

# apps/help_center/services.py (implements)
class HelpCenterService:
    def search_articles(self, query: str) -> List[dict]:
        # Implementation

# apps/y_helpdesk/services.py (consumes)
from apps.core.interfaces.knowledge_base_interface import KnowledgeBaseProvider

def suggest_kb_articles(kb_provider: KnowledgeBaseProvider, ticket_description: str):
    return kb_provider.search_articles(ticket_description)
```

**Applies to:** 
- `core ↔ journal`
- `y_helpdesk ↔ help_center`
- `client_onboarding ↔ scheduler`
- `noc ↔ ml`

### Pattern 2: Late/Lazy Imports
**Use when:** Infrastructure code occasionally needs app-specific context

**Implementation:**
- Import inside function/method, not at module level
- Document why late import is necessary
- Keep usage minimal (code smell if overused)

**Example:**
```python
# apps/core/validators.py
def validate_attendance_geofence(lat, lon):
    # Late import to avoid circular dependency with attendance app
    from apps.attendance.models import Geofence
    
    return Geofence.objects.filter(
        location__contains=(lat, lon)
    ).exists()
```

**Applies to:**
- `core ↔ attendance` (validators)
- `tenants ↔ helpbot` (context injection)

### Pattern 3: Django Signals (Event-Driven)
**Use when:** Apps need to react to events in other apps

**Implementation:**
- Define signals in `apps/core/signals/`
- Emitting app sends signal (no import of receiving app)
- Receiving app connects handlers in `signals.py`
- Register in AppConfig.ready()

**Example:**
```python
# apps/core/signals/activity_signals.py
import django.dispatch

activity_failed = django.dispatch.Signal()  # job_id, reason, severity

# apps/activity/services/job_service.py
from apps.core.signals.activity_signals import activity_failed

def mark_job_failed(job, reason):
    activity_failed.send(
        sender=self.__class__,
        job_id=job.id,
        reason=reason,
        severity='high'
    )

# apps/y_helpdesk/signals.py
from django.dispatch import receiver
from apps.core.signals.activity_signals import activity_failed
from apps.y_helpdesk.models import Ticket

@receiver(activity_failed)
def create_ticket_from_activity_failure(sender, job_id, reason, severity, **kwargs):
    Ticket.objects.create(
        title=f"Activity {job_id} failed",
        description=reason,
        priority=severity
    )

# apps/y_helpdesk/apps.py
class YHelpdeskConfig(AppConfig):
    def ready(self):
        import apps.y_helpdesk.signals  # Register signal handlers
```

**Applies to:**
- `activity ↔ y_helpdesk`
- `scheduler ↔ noc`
- `client_onboarding ↔ work_order_management`

### Pattern 4: App Consolidation
**Use when:** Multiple apps have overlapping responsibilities

**Implementation:**
- Merge apps into single Django app with submodules
- Restructure as `apps/{domain}/{subdomain}/`
- Update all imports project-wide
- Migrate models in single migration

**Example:**
```
BEFORE:
  apps/core_onboarding/
  apps/people_onboarding/
  apps/client_onboarding/
  apps/site_onboarding/

AFTER:
  apps/onboarding/
    ├── core/          # Core onboarding logic
    ├── people/        # People onboarding
    ├── client/        # Client onboarding
    ├── site/          # Site onboarding
    ├── models/
    ├── services/
    └── api/
```

**Applies to:**
- `core_onboarding ↔ people_onboarding` → Merge into `apps/onboarding/`
- `noc ↔ monitoring` → Consider `apps/noc/monitoring/`

### Pattern 5: Architectural Layer Enforcement
**Use when:** Violating clean architecture (API/Service/Domain layers)

**Implementation:**
- Enforce: API → Service → Domain (one-way)
- API layer imports domain models/services
- Domain/Service NEVER imports API layer
- Serializers belong in API layer

**Example:**
```python
# ✅ CORRECT
# apps/api/v2/wellness/views.py
from apps.wellness.models import JournalEntry
from apps.wellness.services import WellnessAnalyzer

# ❌ WRONG
# apps/wellness/services.py
from apps.api.v2.wellness.serializers import JournalSerializer  # NO!
```

**Applies to:**
- `wellness ↔ api`
- `client_onboarding ↔ onboarding_api`
- `reports ↔ work_order_management` (reports should only read)

### Pattern 6: Extract to Core
**Use when:** Service layer couples to specific domains

**Implementation:**
- Generic utilities → `apps/core/utils_new/`
- Cross-app services → `apps/core/services/{domain}_bridge.py`
- Keep service layer generic

**Example:**
```python
# apps/core/services/people_activity_bridge.py
"""
Bridge service for cross-app operations between peoples and activity.
Provides clean interface for common operations.
"""
from apps.peoples.models import People
from apps.activity.models import Jobneed

class PeopleActivityBridge:
    @staticmethod
    def get_active_jobs_for_person(person_id):
        return Jobneed.objects.filter(
            assigned_people__id=person_id,
            status='active'
        ).select_related('job')
```

**Applies to:**
- `peoples ↔ activity`
- `client_onboarding ↔ service`

---

## Consequences

### Positive
- ✅ **Reduced coupling** - Apps can be developed independently
- ✅ **Easier testing** - Mock interfaces instead of concrete implementations
- ✅ **Better architecture** - Clean layers (API → Service → Domain)
- ✅ **Fewer import errors** - No circular import paths
- ✅ **Framework alignment** - Leverage Django signals (built-in event bus)

### Negative
- ⚠️ **Indirection** - More files to navigate (interfaces, signals)
- ⚠️ **Signal debugging** - Harder to trace event-driven flows
- ⚠️ **Migration effort** - Need to update imports across codebase
- ⚠️ **Learning curve** - Team needs to understand new patterns

### Neutral
- ℹ️ **Model ForeignKeys** - Acceptable coupling (Django-native pattern)
- ℹ️ **Read-only queries** - Reports can import domain models
- ℹ️ **Backwards compatibility** - Deprecation path for old imports

---

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Create `apps/core/interfaces/` directory
2. Create `apps/core/signals/` directory
3. Add architectural tests (detect circular imports in CI)
4. Document patterns in team wiki

### Phase 2: Critical Fixes (Weeks 2-3)
1. Fix API layer violations (wellness ↔ api)
2. Remove test code from production (core ↔ ai_testing)
3. Implement signal-based decoupling (activity ↔ y_helpdesk)

### Phase 3: Consolidation (Week 4)
1. Merge onboarding apps
2. Evaluate noc/monitoring merge

### Phase 4: Infrastructure (Week 5)
1. Dependency inversion for core dependencies
2. Late imports for validators

### Phase 5: Validation (Week 6)
1. Run full test suite
2. Update documentation
3. Team training on new patterns

---

## Alternatives Considered

### Alternative 1: Monolithic Refactor
**Description:** Merge all apps into single monolith  
**Rejected because:** Loses Django app modularity, harder to maintain

### Alternative 2: Microservices
**Description:** Split into separate services with API boundaries  
**Rejected because:** Overkill for current scale, deployment complexity

### Alternative 3: Ignore Circular Dependencies
**Description:** Accept current state, use late imports everywhere  
**Rejected because:** Technical debt compounds, import errors persist

---

## Validation

### Success Metrics
1. **Zero critical circular dependencies** (18 → 0)
2. **Warnings reduced by 80%** (20 → ≤4)
3. **All apps pass** `python manage.py check`
4. **Test suite passes** with no import errors
5. **CI/CD gate** prevents new circular dependencies

### Testing
```bash
# Before each fix
python scripts/detect_circular_dependencies.py apps/ --verbose > before.txt

# After fix
python scripts/detect_circular_dependencies.py apps/ --verbose > after.txt
diff before.txt after.txt

# Functional testing
python -m pytest apps/{changed_app}/tests/ -v
python manage.py check --deploy
```

### Rollback Plan
- Each phase is independently revertible via Git
- Feature flags for consolidated apps
- Gradual migration with deprecation warnings

---

## References

- [Django Best Practices: App Design](https://docs.djangoproject.com/en/5.0/intro/reusable-apps/)
- [Python Circular Imports Guide](https://stackabuse.com/python-circular-imports/)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
- Project Documentation:
  - `CIRCULAR_DEPS_ANALYSIS.md` - Full dependency graph
  - `CIRCULAR_DEPENDENCY_RESOLUTION_PLAN.md` - Detailed resolution plan
  - `scripts/detect_circular_dependencies.py` - Analysis tool

---

## Notes

- Model-level ForeignKeys are **acceptable** circular dependencies (Django pattern)
- Services should use interfaces or signals for cross-app communication
- API layer must never be imported by domain layer
- Document all late imports with reason

---

**Reviewers:** Development Team, Architecture Review Board  
**Approved:** [Pending]  
**Implementation Tracking:** `CIRCULAR_DEPENDENCY_RESOLUTION_PROGRESS.md`
