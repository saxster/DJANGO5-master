# ADR 003: Service Layer Pattern

**Status:** Accepted

**Date:** 2025-11-04

**Deciders:** Development Team, Architecture Review Board

**Related:**
- `.claude/rules.md` Rule #8 - View Method Size Limits
- ADR 001 - File Size Limits
- ADR 002 - No Circular Dependencies

---

## Context

The codebase had extensive business logic embedded directly in Django views, violating separation of concerns and making code difficult to test, reuse, and maintain.

### Problems Identified

1. **Fat Views (200+ line methods):**
   ```python
   # ❌ WRONG: Business logic in view
   class AttendanceView(View):
       def post(self, request):
           # 200+ lines of:
           # - Form validation
           # - Business rule checks
           # - Database operations
           # - External API calls
           # - Email sending
           # - Logging
           # All mixed together in one method!
   ```

2. **Code Duplication:**
   - Same business logic repeated in multiple views
   - API endpoints and web views duplicating validation
   - Difficult to maintain consistency

3. **Testing Challenges:**
   - Cannot test business logic without HTTP layer
   - Must mock request/response objects
   - Integration tests become slow
   - Unit tests become impossible

4. **Poor Reusability:**
   - Business logic tied to HTTP requests
   - Cannot reuse from Celery tasks
   - Cannot reuse from management commands
   - Cannot reuse from other apps

---

## Decision

**We adopt the Service Layer Pattern: Views handle HTTP, Services handle business logic.**

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Client                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Views/Controllers                     │
│  • HTTP request/response handling                        │
│  • Authentication/authorization                          │
│  • Input validation (forms)                              │
│  • Response formatting (JSON, HTML)                      │
│  • < 30 lines per method                                 │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Service Layer                         │
│  • Business logic                                        │
│  • Transaction management                                │
│  • Domain validation                                     │
│  • Cross-cutting concerns (logging, caching)             │
│  • Reusable from views, tasks, commands                  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      Models/ORM                          │
│  • Data definition                                       │
│  • Simple validation (constraints)                       │
│  • Database operations                                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                       Database                           │
└─────────────────────────────────────────────────────────┘
```

### Principles

1. **Views are Thin (< 30 lines):**
   - Parse request
   - Call service method
   - Format response
   - That's it!

2. **Services are Focused:**
   - One service per domain
   - Clear public interface
   - Private helper methods
   - No HTTP concerns

3. **Models are Data:**
   - Define schema
   - Simple constraints
   - No complex business logic
   - Database operations only

---

## Consequences

### Positive

1. **Maintainability:**
   - ✅ Easy to locate business logic (in services)
   - ✅ Easy to locate HTTP handling (in views)
   - ✅ Clear separation of concerns
   - ✅ Smaller, focused files

2. **Testability:**
   - ✅ Test business logic without HTTP
   - ✅ Fast unit tests (no Django test client)
   - ✅ Easy to mock dependencies
   - ✅ Clear test boundaries

3. **Reusability:**
   - ✅ Use from views, tasks, commands
   - ✅ Share logic between REST and GraphQL
   - ✅ Consistent behavior across interfaces
   - ✅ Easy to create new interfaces

4. **Code Quality:**
   - ✅ Forces explicit dependencies
   - ✅ Encourages pure functions
   - ✅ Reduces coupling
   - ✅ Follows SOLID principles

### Negative

1. **More Files:**
   - ❌ Need to create service modules
   - ❌ More imports to manage
   - ❌ Navigation between files

2. **Learning Curve:**
   - ❌ Developers must learn pattern
   - ❌ Decide what goes where
   - ❌ Different from Django tutorial

3. **Initial Overhead:**
   - ❌ Simple CRUD requires more boilerplate
   - ❌ Temptation to skip for "quick" features

### Mitigation Strategies

1. **For File Navigation:**
   - Standard directory structure (`services/`)
   - Clear naming conventions (`*_service.py`)
   - IDE shortcuts and bookmarks

2. **For Learning Curve:**
   - Document patterns (this ADR)
   - Code templates for common cases
   - Code review guidance

3. **For Simple CRUD:**
   - Allow thin services for basic operations
   - Use Django generic views when appropriate
   - Don't over-engineer simple features

---

## Implementation Patterns

### Pattern 1: Basic Service

```python
# apps/attendance/services/attendance_service.py
from django.db import transaction
from apps.core.utils_new.db_utils import get_current_db_name
from apps.attendance.models import PeopleEventlog

class AttendanceService:
    """Business logic for attendance operations"""

    @staticmethod
    def check_in(user_id: int, post_id: int, geolocation: dict) -> PeopleEventlog:
        """
        Record user check-in at post

        Args:
            user_id: ID of user checking in
            post_id: ID of post
            geolocation: Dict with lat/lng

        Returns:
            Created PeopleEventlog instance

        Raises:
            ValidationError: If check-in not allowed
        """
        with transaction.atomic(using=get_current_db_name()):
            # Business logic here
            # - Validate user can access post
            # - Check if already checked in
            # - Validate geolocation within geofence
            # - Create event log
            # - Send notifications
            pass
```

### Pattern 2: Thin View Using Service

```python
# apps/attendance/views/attendance_views.py
from django.views import View
from django.http import JsonResponse
from apps.attendance.services.attendance_service import AttendanceService

class CheckInView(View):
    """Handle attendance check-in requests"""

    def post(self, request):
        # Parse and validate input (< 30 lines total)
        user_id = request.user.id
        post_id = request.POST.get('post_id')
        geolocation = {
            'lat': request.POST.get('latitude'),
            'lng': request.POST.get('longitude'),
        }

        # Call service
        try:
            event = AttendanceService.check_in(user_id, post_id, geolocation)
            return JsonResponse({
                'success': True,
                'event_id': event.id,
            })
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
            }, status=400)
```

### Pattern 3: Service with Dependencies

```python
# apps/attendance/services/geofence_service.py
from typing import Tuple
from apps.attendance.models import Geofence

class GeofenceService:
    """Geofence validation and management"""

    def __init__(self, notification_service=None):
        """
        Args:
            notification_service: Optional NotificationService for alerts
        """
        self.notification_service = notification_service

    def is_within_geofence(
        self,
        latitude: float,
        longitude: float,
        post_id: int
    ) -> Tuple[bool, float]:
        """
        Check if location is within post geofence

        Args:
            latitude: Location latitude
            longitude: Location longitude
            post_id: Post to check against

        Returns:
            Tuple of (is_within: bool, distance_meters: float)
        """
        # Business logic for geofence validation
        pass

    def validate_or_alert(self, latitude: float, longitude: float, post_id: int):
        """Validate location and send alert if outside geofence"""
        is_within, distance = self.is_within_geofence(latitude, longitude, post_id)

        if not is_within and self.notification_service:
            self.notification_service.send_geofence_violation_alert(
                post_id, distance
            )

        return is_within
```

### Pattern 4: Service Composition

```python
# apps/attendance/services/attendance_workflow_service.py
from .attendance_service import AttendanceService
from .geofence_service import GeofenceService
from .notification_service import NotificationService

class AttendanceWorkflowService:
    """Orchestrates complex attendance workflows"""

    def __init__(self):
        self.attendance_service = AttendanceService()
        self.geofence_service = GeofenceService()
        self.notification_service = NotificationService()

    def complete_check_in_workflow(self, user_id, post_id, geolocation):
        """
        Full check-in workflow with validation and notifications
        """
        # 1. Validate geofence
        is_valid = self.geofence_service.validate_or_alert(
            geolocation['lat'],
            geolocation['lng'],
            post_id
        )

        if not is_valid:
            raise ValidationError("Outside geofence")

        # 2. Record check-in
        event = self.attendance_service.check_in(user_id, post_id, geolocation)

        # 3. Send notifications
        self.notification_service.notify_check_in(event)

        return event
```

---

## Service Organization

### Directory Structure

```
apps/your_app/
├── models/              # Data definitions
├── services/            # Business logic
│   ├── __init__.py
│   ├── base_service.py       # Abstract base (if needed)
│   ├── core_service.py       # Main business logic
│   ├── validation_service.py # Validation logic
│   ├── notification_service.py # Notifications
│   └── reporting_service.py  # Reports/analytics
├── views/               # HTTP handling
└── tests/
    ├── test_models.py
    ├── test_services.py      # Unit tests (fast)
    └── test_views.py         # Integration tests (slower)
```

### Naming Conventions

| Pattern | Example | Purpose |
|---------|---------|---------|
| `*Service` | `AttendanceService` | Main business logic |
| `*Manager` | `CacheManager` | Resource management |
| `*Handler` | `EventHandler` | Event processing |
| `*Validator` | `GeofenceValidator` | Validation logic |
| `*Builder` | `ReportBuilder` | Object construction |

---

## When to Use Services

### Always Use Services For

- ✅ Multi-step business workflows
- ✅ Operations spanning multiple models
- ✅ Complex validation logic
- ✅ External API calls
- ✅ Sending emails/notifications
- ✅ Calculations and computations
- ✅ Report generation
- ✅ Data transformations

### Can Skip Services For

- ⚠️ Simple CRUD operations (list, retrieve, update, delete)
- ⚠️ Read-only queries with no business logic
- ⚠️ Trivial operations delegated to model methods

**Rule of Thumb:** If view method exceeds 20 lines, extract to service.

---

## Testing Strategy

### Service Tests (Unit Tests - Fast)

```python
# tests/test_services.py
from apps.attendance.services.attendance_service import AttendanceService

def test_check_in_creates_event():
    # No HTTP, no database (use mocks), pure business logic test
    service = AttendanceService()
    event = service.check_in(user_id=1, post_id=2, geolocation={'lat': 0, 'lng': 0})
    assert event.event_type == 'check_in'
```

### View Tests (Integration Tests - Slower)

```python
# tests/test_views.py
from django.test import Client

def test_check_in_endpoint():
    # Test HTTP interface
    client = Client()
    response = client.post('/attendance/check-in/', {
        'post_id': 2,
        'latitude': 0,
        'longitude': 0,
    })
    assert response.status_code == 200
    assert response.json()['success'] is True
```

### Coverage Targets

- Services: 90%+ code coverage (core business logic)
- Views: 70%+ code coverage (HTTP handling)
- Models: 80%+ code coverage (data validation)

---

## Migration Strategy

### For New Features

- ✅ Always use service layer
- ✅ No exceptions for "small" features
- ✅ Code review enforces pattern

### For Existing Code

**Prioritization:**

1. High-traffic endpoints
2. Endpoints with business logic duplication
3. Endpoints causing bugs
4. Endpoints difficult to test

**Process:**

1. Create service with existing view logic
2. Update view to call service
3. Write service unit tests
4. Verify integration tests still pass
5. Remove duplicated logic from other locations

**Do NOT refactor everything at once - incremental migration only.**

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Anemic Services

❌ **WRONG:**
```python
class AttendanceService:
    @staticmethod
    def create_event(data):
        return PeopleEventlog.objects.create(**data)  # Just a wrapper!
```

✅ **CORRECT:**
```python
class AttendanceService:
    @staticmethod
    def check_in(user_id, post_id, geolocation):
        # Validation
        # Business rules
        # Transaction management
        # Side effects (notifications, logging)
        return event
```

### Anti-Pattern 2: God Services

❌ **WRONG:**
```python
class AttendanceService:
    def check_in(self): pass
    def check_out(self): pass
    def generate_report(self): pass
    def send_notification(self): pass
    def validate_geofence(self): pass
    # ... 50 more methods
```

✅ **CORRECT:**
```python
# Split by responsibility
class AttendanceService: pass     # Check-in/out operations
class GeofenceService: pass       # Geofence validation
class NotificationService: pass   # Notifications
class ReportingService: pass      # Reports
```

### Anti-Pattern 3: Mixing HTTP in Services

❌ **WRONG:**
```python
class AttendanceService:
    def check_in(self, request):  # ❌ request object in service!
        user_id = request.user.id
        return JsonResponse({'success': True})  # ❌ HTTP response in service!
```

✅ **CORRECT:**
```python
class AttendanceService:
    def check_in(self, user_id: int, post_id: int) -> PeopleEventlog:
        # No HTTP concerns, pure business logic
        return event
```

---

## Examples

### Example 1: Complex Workflow

**Before (Fat View):**
```python
# 200+ lines in view
def post(self, request):
    # Parse form
    # Validate user permissions
    # Check geofence
    # Check if already checked in
    # Create event
    # Update post assignments
    # Send notifications
    # Log audit trail
    # Return response
```

**After (Thin View + Service):**
```python
# View (25 lines)
def post(self, request):
    form = CheckInForm(request.POST)
    if form.is_valid():
        event = AttendanceWorkflowService().complete_check_in(
            user=request.user,
            post_id=form.cleaned_data['post_id'],
            geolocation=form.cleaned_data['geolocation'],
        )
        return JsonResponse({'success': True, 'event_id': event.id})
    return JsonResponse({'errors': form.errors}, status=400)

# Service (150 lines)
class AttendanceWorkflowService:
    def complete_check_in(self, user, post_id, geolocation):
        # All business logic here
        pass
```

### Example 2: Reusing Across Interfaces

```python
# Service (once)
class ReportService:
    def generate_attendance_report(self, start_date, end_date):
        # Business logic
        return report_data

# Web View
def attendance_report_view(request):
    service = ReportService()
    data = service.generate_attendance_report(start_date, end_date)
    return render(request, 'report.html', {'data': data})

# REST API
class AttendanceReportAPI(APIView):
    def get(self, request):
        service = ReportService()
        data = service.generate_attendance_report(start_date, end_date)
        return Response(data)

# Celery Task
@shared_task
def scheduled_report_task():
    service = ReportService()
    data = service.generate_attendance_report(yesterday, today)
    email_report(data)

# Management Command
class Command(BaseCommand):
    def handle(self, *args, **options):
        service = ReportService()
        data = service.generate_attendance_report(start_date, end_date)
        print_report(data)
```

---

## References

- [Patterns of Enterprise Application Architecture - Martin Fowler](https://martinfowler.com/eaaCatalog/serviceLayer.html)
- [Django Service Layer](https://mitchel.me/2017/django-service-layer/)
- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design - Eric Evans](https://domainlanguage.com/ddd/)

---

**Last Updated:** 2025-11-04

**Next Review:** 2026-02-04 (3 months) - Evaluate adoption rate and effectiveness
