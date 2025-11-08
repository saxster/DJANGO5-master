# Circular Dependency - Quick Reference

**🚀 Fast Guide for Developers**

---

## 🔍 Check for Circular Dependencies

```bash
# Full analysis
python scripts/detect_circular_dependencies.py apps/ --verbose

# With diagram
python scripts/detect_circular_dependencies.py apps/ --diagram report.md
```

---

## 🛠️ Resolution Patterns (Copy-Paste Ready)

### Pattern 1: Dependency Inversion (Interface)

**Use when:** Both apps need each other's functionality

```python
# Step 1: Create interface
# File: apps/core/interfaces/my_service_interface.py
from typing import Protocol, List

class MyServiceProvider(Protocol):
    """Interface for cross-app service"""
    def do_something(self, param: str) -> List[dict]:
        """Do the thing"""
        ...

# Step 2: App A implements
# File: apps/app_a/services/my_service.py
class AppAService:
    def do_something(self, param: str) -> List[dict]:
        return [{'result': param}]

# Step 3: App B consumes
# File: apps/app_b/services/consumer.py
from apps.core.interfaces.my_service_interface import MyServiceProvider

def use_service(provider: MyServiceProvider, param: str):
    """Use service without importing App A"""
    return provider.do_something(param)

# Step 4: Dependency injection in views
# File: apps/app_b/views.py
from apps.app_a.services.my_service import AppAService
from apps.app_b.services.consumer import use_service

def my_view(request):
    provider = AppAService()
    result = use_service(provider, request.GET.get('q'))
    return JsonResponse({'data': result})
```

---

### Pattern 2: Late/Lazy Import

**Use when:** Infrastructure code occasionally needs app context

```python
# ❌ WRONG - Module-level import causes circular dependency
from apps.attendance.models import Geofence

def validate_location(lat, lon):
    return Geofence.objects.filter(location__contains=(lat, lon)).exists()

# ✅ CORRECT - Function-level import
def validate_location(lat, lon):
    """
    Validate location against geofences.
    
    Late import to avoid circular dependency:
    - apps/core/validators.py (this file)
    - apps/attendance/models.py (imports core.BaseModel)
    """
    from apps.attendance.models import Geofence  # Late import
    
    return Geofence.objects.filter(
        location__contains=(lat, lon)
    ).exists()
```

---

### Pattern 3: Django Signals (Event-Driven)

**Use when:** Apps need to react to events in other apps

```python
# Step 1: Define signal
# File: apps/core/signals/activity_signals.py
import django.dispatch

# Define signals
activity_failed = django.dispatch.Signal()  # Provides: job_id, reason, severity
activity_completed = django.dispatch.Signal()  # Provides: job_id, result

# Step 2: Emit signal (Activity app)
# File: apps/activity/services/job_service.py
from apps.core.signals.activity_signals import activity_failed, activity_completed

class JobService:
    def execute_job(self, job):
        try:
            result = self._do_work(job)
            
            # Emit success signal
            activity_completed.send(
                sender=self.__class__,
                job_id=job.id,
                result=result
            )
        except Exception as e:
            # Emit failure signal
            activity_failed.send(
                sender=self.__class__,
                job_id=job.id,
                reason=str(e),
                severity='high'
            )
            raise

# Step 3: Listen to signal (Helpdesk app)
# File: apps/y_helpdesk/signals.py
from django.dispatch import receiver
from apps.core.signals.activity_signals import activity_failed
from apps.y_helpdesk.models import Ticket

@receiver(activity_failed)
def create_ticket_from_activity_failure(sender, job_id, reason, severity, **kwargs):
    """
    Automatically create helpdesk ticket when activity fails.
    No direct import of activity app needed.
    """
    Ticket.objects.create(
        title=f"Activity {job_id} Failed",
        description=f"Reason: {reason}",
        priority=severity,
        category='system_generated',
        source='activity_monitor'
    )

# Step 4: Register signals
# File: apps/y_helpdesk/apps.py
from django.apps import AppConfig

class YHelpdeskConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.y_helpdesk'
    
    def ready(self):
        """Import signals to register receivers"""
        import apps.y_helpdesk.signals  # noqa
```

---

### Pattern 4: App Consolidation

**Use when:** Multiple apps have overlapping responsibilities

```bash
# Before: Circular dependencies between related apps
apps/
  core_onboarding/
  people_onboarding/
  client_onboarding/
  site_onboarding/

# After: Consolidated into single app with submodules
apps/
  onboarding/
    __init__.py
    apps.py
    models/
      __init__.py
      base.py          # Shared models
    core/              # Core onboarding logic
      __init__.py
      services.py
      views.py
    people/            # People onboarding
      __init__.py
      services.py
      views.py
    client/            # Client onboarding
      __init__.py
      services.py
      views.py
    site/              # Site onboarding
      __init__.py
      services.py
      views.py
```

---

### Pattern 5: Layer Enforcement (API → Domain)

**Use when:** API layer imports back into domain

```python
# ❌ WRONG - Domain imports API layer
# File: apps/wellness/services.py
from apps.api.v2.wellness.serializers import JournalSerializer  # NO!

class WellnessService:
    def process_entry(self, data):
        serializer = JournalSerializer(data=data)  # Domain shouldn't know about API
        ...

# ✅ CORRECT - API imports domain only
# File: apps/api/v2/wellness/views.py
from rest_framework.views import APIView
from apps.wellness.models import JournalEntry
from apps.wellness.services import WellnessService
from apps.api.v2.wellness.serializers import JournalSerializer

class JournalEntryView(APIView):
    def post(self, request):
        # API layer orchestrates
        serializer = JournalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Call domain service
        service = WellnessService()
        result = service.process_entry(serializer.validated_data)
        
        return Response({'result': result})

# File: apps/wellness/services.py
class WellnessService:
    def process_entry(self, data: dict):
        """Pure domain logic - no knowledge of API layer"""
        entry = JournalEntry.objects.create(**data)
        return self.analyze_mood(entry)
```

---

## 📋 Checklist: Fixing a Circular Dependency

- [ ] **Identify Pattern** - Which pattern applies?
- [ ] **Create Feature Branch** - `git checkout -b fix/circular-dep-X-Y`
- [ ] **Run Baseline Tests** - `pytest apps/X/ apps/Y/ -v`
- [ ] **Implement Fix** - Follow pattern exactly
- [ ] **Document Changes** - Add comments explaining pattern
- [ ] **Run Circular Dep Check** - `python scripts/detect_circular_dependencies.py apps/ --verbose`
- [ ] **Verify Tests Pass** - `pytest apps/X/ apps/Y/ -v`
- [ ] **Check Django Integrity** - `python manage.py check`
- [ ] **Update Progress Tracker** - Mark task complete
- [ ] **Submit PR** - Reference issue, include metrics

---

## 🚨 Common Mistakes to Avoid

### Mistake 1: Importing Serializers in Domain Layer
```python
# ❌ WRONG
from apps.api.serializers import MySerializer  # Domain importing API

# ✅ CORRECT
# API imports domain, not the other way around
```

### Mistake 2: Module-Level Imports When Late Import Needed
```python
# ❌ WRONG - Circular import at module level
from apps.other_app import something

# ✅ CORRECT - Late import in function
def my_function():
    from apps.other_app import something  # Late import
    return something()
```

### Mistake 3: Direct Cross-App Service Calls
```python
# ❌ WRONG - Direct bidirectional imports
from apps.app_b.services import ServiceB

# ✅ CORRECT - Use signals or interfaces
from apps.core.signals.my_signals import event_happened
event_happened.send(sender=self, data={'key': 'value'})
```

### Mistake 4: Forgetting to Register Signal Handlers
```python
# ❌ WRONG - Signal handler defined but not registered
# apps/my_app/signals.py
def my_handler(sender, **kwargs):
    pass

# ✅ CORRECT - Use @receiver decorator
from django.dispatch import receiver
from apps.core.signals.my_signals import my_signal

@receiver(my_signal)
def my_handler(sender, **kwargs):
    pass

# AND register in AppConfig
class MyAppConfig(AppConfig):
    def ready(self):
        import apps.my_app.signals  # noqa
```

---

## 🔧 Useful Commands

```bash
# Detect circular dependencies
python scripts/detect_circular_dependencies.py apps/ --verbose

# Generate dependency diagram
python scripts/detect_circular_dependencies.py apps/ --diagram deps.md

# Check Django integrity
python manage.py check --deploy

# Run specific app tests
python -m pytest apps/my_app/tests/ -v

# Run all tests
python -m pytest --cov=apps --cov-report=html -v

# Check for import errors
python -c "from apps import *; print('OK')"
```

---

## 📚 Documentation Links

- **[Resolution Plan](CIRCULAR_DEPENDENCY_RESOLUTION_PLAN.md)** - Detailed strategy
- **[Progress Tracker](CIRCULAR_DEPENDENCY_RESOLUTION_PROGRESS.md)** - Implementation status
- **[ADR-007](docs/architecture/adr/ADR-007-Circular-Dependency-Resolution.md)** - Architecture decisions
- **[Dependency Analysis](CIRCULAR_DEPS_ANALYSIS.md)** - Current state diagram

---

## 🆘 Getting Help

- **Slack:** #circular-dependency-cleanup
- **Questions:** Tag @tech-lead in PR
- **Blockers:** Raise in daily standup

---

**Last Updated:** 2025-11-06  
**Quick Tip:** Start with Phase 1 tasks (easiest wins) to build confidence!
