# ADR 005: Exception Handling Standards

**Status:** Accepted

**Date:** 2025-11-04

**Deciders:** Development Team, Architecture Review Board

**Related:**
- `.claude/rules.md` Rule #11 - Exception Handling Specificity
- `apps/core/exceptions/patterns.py` - Exception patterns
- `scripts/analyze_exception_violations.py` - Violation detection

---

## Context

The codebase had widespread use of generic exception handling (`except Exception:`) that masked real errors and made debugging difficult.

### Problems Identified

1. **Hidden Errors:**
   ```python
   # ❌ WRONG: Swallows all exceptions
   try:
       user.save()
       send_notification(user)
       update_cache(user)
   except Exception as e:
       logger.error("Something failed")  # Which operation?
       return None  # Silent failure!
   ```

2. **Debugging Nightmares:**
   - Exceptions caught without proper logging
   - Stack traces lost
   - Root causes hidden
   - Production issues hard to diagnose

3. **Incorrect Error Handling:**
   - Database errors treated like validation errors
   - Network timeouts treated like permission errors
   - Different errors require different responses

4. **Security Issues:**
   - Sensitive errors exposed to users
   - Generic error messages not helpful
   - Difficult to distinguish attack patterns

### Violation Analysis

Automated scan found **500+ instances** of generic exception handling:

```bash
$ python scripts/analyze_exception_violations.py
Found 523 violations of exception handling standards:
  - Generic 'except Exception': 387 instances
  - Bare 'except': 89 instances
  - Exception without logging: 47 instances
```

---

## Decision

**We prohibit generic exception handling and require specific exception types.**

### Rules

1. **Use Specific Exception Types:**
   ```python
   # ✅ CORRECT: Specific exceptions
   from django.db import IntegrityError, OperationalError
   from django.core.exceptions import ValidationError, PermissionDenied

   try:
       user.save()
   except IntegrityError as e:
       logger.error(f"Duplicate user: {e}")
       raise ValidationError("User already exists")
   except OperationalError as e:
       logger.error(f"Database error: {e}")
       raise ServiceUnavailable("Database temporarily unavailable")
   ```

2. **Use Exception Groups from patterns.py:**
   ```python
   # ✅ CORRECT: Use predefined groups
   from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

   try:
       response = requests.get(url, timeout=(5, 15))
   except NETWORK_EXCEPTIONS as e:
       logger.error(f"Network error calling {url}: {e}")
       raise ExternalServiceError(f"Failed to contact {service_name}")
   ```

3. **Always Log Before Re-raising:**
   ```python
   # ✅ CORRECT: Log then re-raise
   try:
       dangerous_operation()
   except SpecificError as e:
       logger.error(f"Operation failed: {e}", exc_info=True, extra={
           'correlation_id': request.correlation_id,
           'user_id': request.user.id,
       })
       raise  # Re-raise original exception
   ```

4. **Never Catch and Ignore:**
   ```python
   # ❌ FORBIDDEN: Silent failure
   try:
       critical_operation()
   except Exception:
       pass  # NEVER DO THIS!

   # ✅ CORRECT: Explicit handling
   try:
       critical_operation()
   except ExpectedError:
       # Handle expected error
       logger.warning("Expected error occurred, continuing")
   ```

### Standard Exception Groups

Defined in `apps/core/exceptions/patterns.py`:

```python
# Database exceptions
DATABASE_EXCEPTIONS = (
    IntegrityError,
    OperationalError,
    DatabaseError,
)

# Network exceptions
NETWORK_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError,
)

# Validation exceptions
VALIDATION_EXCEPTIONS = (
    ValidationError,
    ValueError,
    TypeError,
)

# Permission exceptions
PERMISSION_EXCEPTIONS = (
    PermissionDenied,
    PermissionError,
)
```

---

## Consequences

### Positive

1. **Better Debugging:**
   - ✅ Know exactly what failed
   - ✅ Full stack traces preserved
   - ✅ Clear error messages
   - ✅ Easier to reproduce issues

2. **Correct Error Handling:**
   - ✅ Database errors → retry with backoff
   - ✅ Network errors → exponential backoff
   - ✅ Validation errors → user-friendly message
   - ✅ Permission errors → 403 response

3. **Security:**
   - ✅ Don't expose internal errors to users
   - ✅ Log security-relevant exceptions
   - ✅ Detect attack patterns (repeated permission errors)

4. **Code Quality:**
   - ✅ Forces developers to think about error cases
   - ✅ Explicit error handling paths
   - ✅ Clear intent in code

### Negative

1. **More Verbose:**
   - ❌ Multiple except blocks
   - ❌ More imports
   - ❌ More lines of code

2. **Learning Curve:**
   - ❌ Must know exception hierarchy
   - ❌ Must understand which exceptions to catch
   - ❌ Must know exception groups

3. **Refactoring Cost:**
   - ❌ 500+ violations to fix
   - ❌ Risk of breaking existing behavior
   - ❌ Time investment

### Mitigation Strategies

1. **For Verbosity:**
   - Use exception groups (catch multiple related exceptions)
   - Use helper functions for common patterns
   - Templates and snippets in IDEs

2. **For Learning Curve:**
   - Document common patterns (this ADR)
   - Code review feedback
   - Pre-commit hooks catch violations

3. **For Refactoring Cost:**
   - Automated detection script
   - Incremental migration (prioritize critical paths)
   - Focus on security-critical and business-critical apps first

---

## Implementation Patterns

### Pattern 1: Database Operations

```python
# ✅ CORRECT: Specific database exception handling
from django.db import IntegrityError, OperationalError, transaction
from apps.core.utils_new.db_utils import get_current_db_name

def create_user(data):
    try:
        with transaction.atomic(using=get_current_db_name()):
            user = User.objects.create(**data)
            profile = UserProfile.objects.create(user=user)
            return user
    except IntegrityError as e:
        logger.error(f"Duplicate user creation attempt: {e}", extra={
            'username': data.get('username'),
            'email': data.get('email'),
        })
        raise ValidationError("User with this email already exists")
    except OperationalError as e:
        logger.error(f"Database operation failed: {e}", exc_info=True)
        raise ServiceUnavailable("Database temporarily unavailable")
```

### Pattern 2: External API Calls

```python
# ✅ CORRECT: Network exception handling with retry
import requests
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(
    exceptions=NETWORK_EXCEPTIONS,
    max_retries=3,
    retry_policy='EXTERNAL_API'
)
def call_external_api(url, payload):
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=(5, 30)  # 5s connect, 30s read
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout as e:
        logger.error(f"API timeout for {url}: {e}")
        raise ExternalServiceError(f"Service timeout: {url}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"API HTTP error for {url}: {e.response.status_code}")
        if e.response.status_code >= 500:
            raise ExternalServiceError("Service unavailable")
        else:
            raise ValidationError("Invalid request to external service")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"API connection error for {url}: {e}")
        raise ExternalServiceError(f"Cannot connect to {url}")
```

### Pattern 3: File Operations

```python
# ✅ CORRECT: File operation exception handling
from pathlib import Path

def read_config_file(filepath):
    try:
        path = Path(filepath)
        with path.open('r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {filepath}")
        raise ConfigurationError(f"Missing configuration file: {filepath}")
    except PermissionError:
        logger.error(f"Permission denied reading: {filepath}")
        raise ConfigurationError(f"Cannot read configuration file: {filepath}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        raise ConfigurationError(f"Invalid configuration file format")
    except OSError as e:
        logger.error(f"OS error reading {filepath}: {e}")
        raise ConfigurationError(f"Error reading configuration file")
```

### Pattern 4: Validation and Business Logic

```python
# ✅ CORRECT: Validation exception handling
from django.core.exceptions import ValidationError

def validate_attendance_check_in(user, post, geolocation):
    try:
        # Validate user permissions
        if not user.can_access_post(post):
            raise PermissionDenied("User not assigned to this post")

        # Validate geofence
        if not is_within_geofence(geolocation, post):
            raise ValidationError("Location outside geofence")

        # Validate not already checked in
        if is_already_checked_in(user, post):
            raise ValidationError("Already checked in at this post")

    except PermissionDenied:
        logger.warning(f"Permission denied: user {user.id} post {post.id}")
        raise  # Re-raise as-is
    except ValidationError as e:
        logger.info(f"Validation failed: {e}")
        raise  # Re-raise with original message
```

### Pattern 5: Multi-Step Operations with Cleanup

```python
# ✅ CORRECT: Exception handling with cleanup
def process_file_upload(uploaded_file):
    temp_path = None
    try:
        # Step 1: Save to temp location
        temp_path = save_to_temp(uploaded_file)

        # Step 2: Validate file
        validate_file(temp_path)

        # Step 3: Process file
        result = process_file(temp_path)

        # Step 4: Move to permanent location
        permanent_path = move_to_permanent(temp_path)

        return permanent_path

    except ValidationError as e:
        logger.warning(f"File validation failed: {e}")
        raise  # User-facing error
    except IOError as e:
        logger.error(f"File operation failed: {e}", exc_info=True)
        raise ServiceUnavailable("File processing error")
    finally:
        # Always cleanup temp file
        if temp_path and Path(temp_path).exists():
            try:
                Path(temp_path).unlink()
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
                # Don't raise in finally block
```

---

## Exception Hierarchy

### Django Exceptions

```
Exception
├── django.core.exceptions.ObjectDoesNotExist
│   └── Model.DoesNotExist
├── django.core.exceptions.ValidationError
├── django.core.exceptions.PermissionDenied
├── django.core.exceptions.SuspiciousOperation
├── django.db.IntegrityError
├── django.db.OperationalError
└── django.db.DatabaseError
```

### Custom Exceptions

```python
# apps/core/exceptions/patterns.py

class IntelliwizError(Exception):
    """Base exception for all Intelliwiz errors"""
    pass

class ValidationError(IntelliwizError):
    """Business validation errors"""
    pass

class ServiceUnavailable(IntelliwizError):
    """External service unavailable"""
    pass

class ConfigurationError(IntelliwizError):
    """Configuration errors"""
    pass

class ExternalServiceError(IntelliwizError):
    """External API/service errors"""
    pass
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Generic Exception Catch

❌ **FORBIDDEN:**
```python
try:
    complex_operation()
except Exception as e:  # TOO GENERIC!
    logger.error("Failed")
    return None
```

✅ **CORRECT:**
```python
try:
    complex_operation()
except SpecificError1 as e:
    # Handle specific error
    pass
except SpecificError2 as e:
    # Handle different error differently
    pass
```

### Anti-Pattern 2: Bare Except

❌ **FORBIDDEN:**
```python
try:
    operation()
except:  # Catches EVERYTHING including KeyboardInterrupt!
    pass
```

✅ **CORRECT:**
```python
try:
    operation()
except (SpecificError1, SpecificError2) as e:
    # Only catch what you can handle
    pass
```

### Anti-Pattern 3: Silent Failures

❌ **FORBIDDEN:**
```python
try:
    critical_operation()
except Exception:
    pass  # Silent failure - no logging!
```

✅ **CORRECT:**
```python
try:
    critical_operation()
except SpecificError as e:
    logger.error(f"Critical operation failed: {e}", exc_info=True)
    raise  # Re-raise or handle appropriately
```

### Anti-Pattern 4: Catching and Returning None

❌ **FORBIDDEN:**
```python
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except Exception:
        return None  # Hides ObjectDoesNotExist, DatabaseError, etc.
```

✅ **CORRECT:**
```python
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.info(f"User {user_id} not found")
        raise Http404("User not found")
    except DatabaseError as e:
        logger.error(f"Database error fetching user {user_id}: {e}")
        raise ServiceUnavailable("Database error")
```

### Anti-Pattern 5: Exception for Control Flow

❌ **FORBIDDEN:**
```python
# Using exceptions for normal control flow
try:
    user = User.objects.get(email=email)
except User.DoesNotExist:
    user = User.objects.create(email=email)  # Bad pattern!
```

✅ **CORRECT:**
```python
# Use explicit checks
user, created = User.objects.get_or_create(email=email)
# or
if not User.objects.filter(email=email).exists():
    user = User.objects.create(email=email)
```

---

## Migration Strategy

### Phase 1: Detection (Week 1)

```bash
# Run violation detection
python scripts/analyze_exception_violations.py --verbose > violations.txt

# Analyze by app
python scripts/analyze_exception_violations.py --app core
python scripts/analyze_exception_violations.py --app peoples
```

### Phase 2: Prioritization (Week 1)

Prioritize by criticality:

1. **Security-Critical (Immediate):**
   - Authentication/authorization code
   - Encryption/decryption operations
   - Permission checks

2. **Business-Critical (High Priority):**
   - Financial transactions
   - Data integrity operations
   - Core workflows

3. **User-Facing (Medium Priority):**
   - API endpoints
   - Form handling
   - View logic

4. **Supporting (Lower Priority):**
   - Utilities
   - Helpers
   - Background tasks

### Phase 3: Migration (Weeks 2-8)

**For each violation:**

1. **Understand Context:**
   - What operation is being performed?
   - What errors can occur?
   - How should each error be handled?

2. **Replace Generic Handler:**
   ```python
   # Before
   try:
       operation()
   except Exception as e:
       logger.error(f"Failed: {e}")

   # After
   try:
       operation()
   except SpecificError1 as e:
       logger.error(f"Specific error 1: {e}")
       raise
   except SpecificError2 as e:
       logger.error(f"Specific error 2: {e}")
       raise
   ```

3. **Test:**
   - Verify error handling still works
   - Add unit tests for error cases
   - Verify logging is correct

4. **Document:**
   - Add comments explaining exception handling
   - Update docstrings with exceptions raised

### Phase 4: Enforcement (Ongoing)

```bash
# Pre-commit hook
python scripts/analyze_exception_violations.py --fail-on-violations

# CI/CD check
python scripts/analyze_exception_violations.py --strict
```

---

## Validation

### Pre-Commit Hook

```bash
#!/bin/bash
# .githooks/check-exceptions.sh

echo "Checking exception handling standards..."

# Check for generic exception handling
python scripts/analyze_exception_violations.py --fail-on-new

if [ $? -ne 0 ]; then
    echo "❌ Found exception handling violations"
    echo "Run: python scripts/analyze_exception_violations.py --verbose"
    exit 1
fi

echo "✅ Exception handling standards met"
```

### Code Review Checklist

- [ ] No `except Exception:` without justification
- [ ] No bare `except:` clauses
- [ ] All exceptions logged with context
- [ ] Specific exception types used
- [ ] Appropriate error responses (HTTP status, user messages)
- [ ] Stack traces preserved (`exc_info=True`)
- [ ] Cleanup code in `finally` blocks

---

## Examples

### Example 1: View with Proper Exception Handling

```python
# apps/attendance/views/check_in_view.py
from django.views import View
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse
from apps.attendance.services.attendance_service import AttendanceService

class CheckInView(View):
    def post(self, request):
        try:
            service = AttendanceService()
            event = service.check_in(
                user=request.user,
                post_id=request.POST.get('post_id'),
                geolocation=request.POST.get('geolocation'),
            )
            return JsonResponse({
                'success': True,
                'event_id': event.id,
            })

        except ValidationError as e:
            # User-facing error (400)
            logger.info(f"Check-in validation failed: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
            }, status=400)

        except PermissionDenied as e:
            # Permission error (403)
            logger.warning(f"Check-in permission denied: {e}", extra={
                'user_id': request.user.id,
                'post_id': request.POST.get('post_id'),
            })
            return JsonResponse({
                'success': False,
                'error': 'Permission denied',
            }, status=403)

        except DatabaseError as e:
            # Internal error (500)
            logger.error(f"Database error during check-in: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Service temporarily unavailable',
            }, status=500)
```

### Example 2: Celery Task with Retry Logic

```python
# apps/attendance/tasks.py
from celery import shared_task
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

@shared_task(
    bind=True,
    autoretry_for=DATABASE_EXCEPTIONS + NETWORK_EXCEPTIONS,
    retry_backoff=True,
    max_retries=3
)
def send_attendance_notification(self, event_id):
    try:
        event = PeopleEventlog.objects.get(id=event_id)
        NotificationService().send_check_in_notification(event)

    except PeopleEventlog.DoesNotExist:
        # Don't retry - record doesn't exist
        logger.error(f"Event {event_id} not found")
        return

    except NETWORK_EXCEPTIONS as e:
        # Retry automatically via Celery
        logger.warning(f"Network error sending notification: {e}")
        raise  # Celery will retry

    except DATABASE_EXCEPTIONS as e:
        # Retry automatically via Celery
        logger.error(f"Database error fetching event: {e}")
        raise  # Celery will retry
```

---

## References

- [Python Exception Hierarchy](https://docs.python.org/3/library/exceptions.html)
- [Django Exceptions](https://docs.djangoproject.com/en/5.0/ref/exceptions/)
- [PEP 3134 - Exception Chaining](https://www.python.org/dev/peps/pep-3134/)
- [Effective Python - Brett Slatkin](https://effectivepython.com/) - Item 65: Use Exception Chains

---

**Last Updated:** 2025-11-04

**Next Review:** 2026-02-04 (3 months) - Review migration progress and effectiveness
---

## Implementation Status

**Status:** ✅ **Implemented and Validated** (Phase 1-6)

**Phase 1-6 Results:**
- Applied across 16 refactored apps
- 100% compliance in all new code
- 0 production incidents related to this ADR

**See:** [PROJECT_RETROSPECTIVE.md](../../PROJECT_RETROSPECTIVE.md) for complete implementation details

**Last Updated:** 2025-11-05
