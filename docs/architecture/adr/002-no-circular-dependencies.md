# ADR 002: No Circular Dependencies

**Status:** Accepted

**Date:** 2025-11-04

**Deciders:** Development Team, Architecture Review Board

**Related:**
- `.claude/rules.md` - SOLID Principles Enforcement
- `docs/architecture/REFACTORING_PATTERNS.md` - Pitfall #2
- ADR 001 - File Size Limits

---

## Context

Circular dependencies occur when Module A imports Module B, and Module B imports Module A (directly or transitively). These were found throughout the codebase, particularly after splitting god files into multiple modules.

### Problems Encountered

1. **Import Errors:**
   ```python
   # models/model_a.py
   from .model_b import ModelB  # Fails at runtime!

   class ModelA(models.Model):
       related_b = models.ForeignKey(ModelB)

   # models/model_b.py
   from .model_a import ModelA  # Circular import!

   class ModelB(models.Model):
       related_a = models.ForeignKey(ModelA)
   ```

2. **Runtime Failures:**
   - `ImportError: cannot import name 'ModelA' from partially initialized module`
   - Unpredictable import order issues
   - Different behavior in tests vs. production

3. **Code Smells:**
   - High coupling between modules
   - Difficult to understand dependencies
   - Hard to refactor or reorder imports
   - Testing becomes complex

4. **Architectural Issues:**
   - Violation of Dependency Inversion Principle
   - Tight coupling prevents modular evolution
   - Difficult to create clear layers

---

## Decision

**We prohibit circular dependencies between modules and enforce the Dependency Inversion Principle.**

### Rules

1. **Use String References for Django Foreign Keys:**
   ```python
   # ✅ CORRECT: String reference
   class ModelA(models.Model):
       related_b = models.ForeignKey('app.ModelB', on_delete=models.CASCADE)
   ```

2. **Layer Dependencies Top-Down:**
   ```
   Views → Services → Models
     ↓        ↓         ↓
    No upward dependencies allowed
   ```

3. **Use Dependency Injection:**
   ```python
   # ✅ CORRECT: Service accepts model as parameter
   class NotificationService:
       def notify(self, user: 'peoples.People', message: str):
           # No direct import of user model
           pass
   ```

4. **Import at Usage Time (TYPE_CHECKING):**
   ```python
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from .model_b import ModelB  # Only for type hints

   class ModelA(models.Model):
       def process_b(self, b: 'ModelB') -> None:
           # No circular import at runtime
           pass
   ```

### Detection

Automated circular dependency detection:

```bash
# Pre-commit hook checks for circular imports
python -c "import apps.your_app.models"  # Must succeed

# Static analysis tool
pip install pydeps
pydeps apps/ --show-cycles --cluster

# Manual check
python scripts/detect_circular_dependencies.py
```

---

## Consequences

### Positive

1. **Predictable Imports:**
   - ✅ No runtime import errors
   - ✅ Consistent behavior across environments
   - ✅ Clear import order

2. **Better Architecture:**
   - ✅ Loose coupling between modules
   - ✅ Clear dependency hierarchy
   - ✅ Easier to understand code flow
   - ✅ Follows SOLID principles

3. **Improved Testability:**
   - ✅ Easy to mock dependencies
   - ✅ Test modules in isolation
   - ✅ Clear test setup

4. **Maintainability:**
   - ✅ Safe to refactor modules
   - ✅ Add features without breaking imports
   - ✅ Clear module boundaries

### Negative

1. **String References for Foreign Keys:**
   - ❌ Less IDE autocomplete support
   - ❌ Typos not caught until runtime
   - ❌ Slightly less readable

2. **More Explicit Imports:**
   - ❌ Cannot import at module level in some cases
   - ❌ Need TYPE_CHECKING blocks for type hints

3. **Learning Curve:**
   - ❌ Developers must understand dependency rules
   - ❌ May feel restrictive initially

### Mitigation Strategies

1. **For String References:**
   - Use Django's `AppConfig.ready()` to validate references
   - Write tests that load all models
   - Use `check --deploy` in CI/CD

2. **For Type Hints:**
   - Use `TYPE_CHECKING` pattern consistently
   - Document pattern in code templates
   - IDE plugins can help

3. **For Learning Curve:**
   - Document patterns in `REFACTORING_PATTERNS.md`
   - Code review checklist includes dependency check
   - Automated validation catches violations

---

## Implementation Patterns

### Pattern 1: String References (Django Models)

**Problem:** Models reference each other

**Solution:**
```python
# models/attendance_event.py
from django.db import models

class AttendanceEvent(models.Model):
    user = models.ForeignKey(
        'peoples.People',  # ✅ String reference to avoid import
        on_delete=models.CASCADE
    )
    post = models.ForeignKey(
        'attendance.Post',  # ✅ Same app, string reference
        on_delete=models.SET_NULL,
        null=True
    )
```

### Pattern 2: TYPE_CHECKING Block

**Problem:** Need type hints but avoid circular imports

**Solution:**
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.peoples.models import People  # Only for type checker
    from .post import Post

class AttendanceService:
    def check_in(self, user: 'People', post: 'Post') -> bool:
        # Type hints work, no circular import at runtime
        return user.can_access(post)
```

### Pattern 3: Late Import

**Problem:** Need concrete import for utility function

**Solution:**
```python
class AttendanceHelper:
    def get_user_posts(self, user_id: int) -> list:
        # Import at function level to break circular dependency
        from apps.peoples.models import People
        from .post import Post

        user = People.objects.get(id=user_id)
        return Post.objects.filter(assigned_users=user)
```

### Pattern 4: Dependency Injection

**Problem:** Service needs access to models from multiple apps

**Solution:**
```python
# services/notification_service.py
class NotificationService:
    def send_notification(self, recipient, message: str):
        """
        Args:
            recipient: peoples.People instance (not imported)
            message: Notification message
        """
        # Work with recipient as abstract object
        email = recipient.email
        # ... send notification
```

### Pattern 5: App-Level Organization

**Problem:** Multiple models with complex relationships

**Solution:**
```
apps/attendance/
├── models/
│   ├── __init__.py          # Central import point
│   ├── base.py              # Abstract base classes (no dependencies)
│   ├── core.py              # Core models (depend on base)
│   ├── audit.py             # Audit models (depend on core)
│   └── reporting.py         # Reports (depend on audit)
```

**Dependency flow:** `base → core → audit → reporting`

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Mutual Model Imports

❌ **WRONG:**
```python
# models/user.py
from .profile import Profile

class User(models.Model):
    pass

# models/profile.py
from .user import User  # Circular!

class Profile(models.Model):
    user = models.OneToOneField(User)
```

✅ **CORRECT:**
```python
# models/user.py
class User(models.Model):
    pass

# models/profile.py
class Profile(models.Model):
    user = models.OneToOneField('app.User', on_delete=models.CASCADE)
```

### Anti-Pattern 2: Service Layer Circular Dependencies

❌ **WRONG:**
```python
# services/user_service.py
from .notification_service import NotificationService

class UserService:
    def create_user(self, data):
        NotificationService().send_welcome_email(user)

# services/notification_service.py
from .user_service import UserService  # Circular!

class NotificationService:
    def send_welcome_email(self, user):
        UserService().update_last_notified(user)
```

✅ **CORRECT:**
```python
# services/user_service.py
class UserService:
    def create_user(self, data):
        from .notification_service import NotificationService  # Late import
        NotificationService().send_welcome_email(user)

# services/notification_service.py
class NotificationService:
    def send_welcome_email(self, user):
        # Update user directly, no circular dependency
        user.last_notified = timezone.now()
        user.save()
```

### Anti-Pattern 3: Bidirectional Package Imports

❌ **WRONG:**
```python
# apps/attendance/services.py
from apps.peoples.services import PeopleService

# apps/peoples/services.py
from apps.attendance.services import AttendanceService  # Circular!
```

✅ **CORRECT:**
```python
# apps/attendance/services.py
from apps.peoples.services import PeopleService  # One direction only

# apps/peoples/services.py
# No import of attendance
# If needed, use dependency injection or events
```

---

## Validation

### Pre-Commit Validation

```bash
#!/bin/bash
# .githooks/check-circular-dependencies.sh

echo "Checking for circular dependencies..."

# Test import of all apps
python3 -c "
import sys
try:
    import apps.peoples.models
    import apps.attendance.models
    import apps.activity.models
    import apps.core.models
    print('✅ All imports successful')
except ImportError as e:
    print(f'❌ Circular import detected: {e}')
    sys.exit(1)
"

# Use pydeps if available
if command -v pydeps &> /dev/null; then
    pydeps apps/ --max-bacon=3 --show-cycles > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ Circular dependencies detected by pydeps"
        exit 1
    fi
fi

echo "✅ No circular dependencies found"
```

### CI/CD Validation

```yaml
# .github/workflows/ci.yml
- name: Check Circular Dependencies
  run: |
    python -m pip install pydeps
    pydeps apps/ --max-bacon=3 --show-cycles --no-output
    if [ $? -ne 0 ]; then
      echo "Circular dependencies detected!"
      exit 1
    fi
```

### Manual Testing

```bash
# Check specific app
python -c "import apps.attendance.models; print('✅ OK')"

# Visualize dependencies
pydeps apps/attendance --show-deps --cluster

# Check for cycles
pydeps apps/ --show-cycles --max-bacon=3
```

---

## Resolution Process

**If circular dependency is found:**

1. **Identify the Cycle:**
   ```bash
   pydeps apps/your_app --show-cycles
   # Output: ModelA → ModelB → ModelA
   ```

2. **Choose Resolution Strategy:**

   | Strategy | Use When | Example |
   |----------|----------|---------|
   | String references | Django models | `ForeignKey('app.Model')` |
   | TYPE_CHECKING | Type hints only | `if TYPE_CHECKING: import X` |
   | Late import | Utility functions | `def func(): from X import Y` |
   | Dependency injection | Services | `def process(model_instance)` |
   | Refactor | Poor design | Extract shared code to third module |

3. **Implement Fix:**
   ```python
   # Before: Circular import
   from .model_b import ModelB

   # After: String reference
   # No import needed
   ```

4. **Test:**
   ```bash
   python -c "import apps.your_app.models"  # Should succeed
   python manage.py check  # Should pass
   ```

5. **Document:**
   Add comment explaining string reference:
   ```python
   class ModelA(models.Model):
       # String reference to avoid circular import with ModelB
       related_b = models.ForeignKey('app.ModelB', ...)
   ```

---

## Examples

### Example 1: People and Attendance

**Challenge:** People app and Attendance app reference each other

```python
# ✅ CORRECT APPROACH

# apps/peoples/models/user_model.py
class People(AbstractBaseUser):
    # No imports from attendance app
    pass

# apps/attendance/models/people_eventlog.py
class PeopleEventlog(models.Model):
    # String reference to avoid circular import
    people = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE
    )
```

### Example 2: Core Services and Domain Services

**Challenge:** Core services need domain models, domain services need core utilities

```python
# ✅ CORRECT APPROACH

# apps/core/services/base_service.py
class BaseService:
    """Abstract service - no domain imports"""
    def validate(self, model_instance):
        # Works with any model via duck typing
        return model_instance.is_valid()

# apps/attendance/services/attendance_service.py
from apps.core.services.base_service import BaseService

class AttendanceService(BaseService):
    # Domain service imports core, not vice versa
    def process_event(self, event):
        if self.validate(event):
            # ... process
            pass
```

### Example 3: Refactoring to Break Cycle

**Before (Circular):**
```python
# models/user.py
from .notification import NotificationPreference

class User(models.Model):
    def get_notifications(self):
        return NotificationPreference.objects.filter(user=self)

# models/notification.py
from .user import User  # Circular!

class NotificationPreference(models.Model):
    user = models.ForeignKey(User)
```

**After (Resolved):**
```python
# models/user.py
class User(models.Model):
    def get_notifications(self):
        # Late import to break cycle
        from .notification import NotificationPreference
        return NotificationPreference.objects.filter(user=self)

# models/notification.py
class NotificationPreference(models.Model):
    # String reference instead of import
    user = models.ForeignKey('app.User', on_delete=models.CASCADE)
```

---

## References

- [Python Import System](https://docs.python.org/3/reference/import.html)
- [Django Model String References](https://docs.djangoproject.com/en/5.0/ref/models/fields/#django.db.models.ForeignKey)
- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/#forward-references)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)

---

**Last Updated:** 2025-11-04

**Next Review:** 2026-02-04 (3 months) - Review effectiveness and collect feedback
