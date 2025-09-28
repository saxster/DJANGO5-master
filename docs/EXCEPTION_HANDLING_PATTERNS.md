# Exception Handling Patterns - Developer Guide

## 🎯 Purpose

This guide provides standardized exception handling patterns for the Django 5 enterprise platform, ensuring code quality, security, and maintainability while complying with **Rule 11** from `.claude/rules.md`.

## 🚨 The Problem: Generic Exception Handling

### ❌ FORBIDDEN Pattern

```python
try:
    result = some_operation()
except Exception as e:  # TOO GENERIC!
    logger.error("Something failed")
    return None
```

**Why this is dangerous:**
- Hides specific errors (TypeError, ValueError, database errors, etc.)
- Makes debugging impossible
- Can mask security vulnerabilities
- Violates Rule 11 (Zero tolerance policy)

## ✅ The Solution: Specific Exception Handling

### Pattern 1: Database Operations

```python
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

try:
    user = People.objects.create(**user_data)
except IntegrityError as e:
    logger.error(f"Duplicate user detected: {e}", extra={'user_email': user_data.get('email')})
    raise ValidationError("User with this email already exists")
except DatabaseError as e:
    logger.error(f"Database error during user creation: {e}", exc_info=True)
    raise BusinessLogicException("Unable to create user - database unavailable")
except ValidationError as e:
    logger.warning(f"User data validation failed: {e}")
    raise
```

**Key Points:**
- Catches `IntegrityError` for unique constraint violations
- Catches `DatabaseError` for connection/query failures
- Catches `ValidationError` for data validation issues
- Each exception has specific handling and logging

---

### Pattern 2: GraphQL Mutations

```python
from graphql import GraphQLError
from django.db import DatabaseError
from django.core.exceptions import ValidationError
from apps.core.exceptions import AuthenticationError

@login_required
def mutate(cls, root, info, input):
    try:
        result = perform_business_logic(input)
        return SuccessResponse(result=result)

    except AuthenticationError as e:
        logger.warning(f"Auth failure in mutation: {e}", extra={'user_id': info.context.user.id})
        raise GraphQLError("Authentication failed") from e

    except ValidationError as e:
        logger.info(f"Validation error in mutation: {e}")
        raise GraphQLError(f"Invalid input: {e}") from e

    except DatabaseError as e:
        logger.error(f"Database error in mutation: {e}", exc_info=True)
        raise GraphQLError("Service temporarily unavailable") from e
```

**Key Points:**
- Authentication errors handled separately
- Validation errors provide user feedback
- Database errors logged but don't expose internals
- All errors converted to GraphQLError for API consistency

---

### Pattern 3: File Upload Operations

```python
from apps.core.exceptions import FileValidationException
from django.core.exceptions import ValidationError

try:
    validated_file = validate_uploaded_file(file)
    save_result = save_to_storage(validated_file)
    create_database_record(save_result)

except (IOError, OSError) as e:
    logger.error(f"File system error: {e}", exc_info=True)
    return Response({"error": "File upload failed"}, status=500)

except FileValidationException as e:
    logger.warning(f"Invalid file upload attempt: {e}")
    return Response({"error": str(e)}, status=400)

except DatabaseError as e:
    logger.error(f"Database error after file upload: {e}", exc_info=True)
    return Response({"error": "Upload processing failed"}, status=500)
```

**Key Points:**
- File system errors (`IOError`, `OSError`) handled separately
- Custom validation exception for file security checks
- Database errors handled after file operations
- Different HTTP status codes for different error types

---

### Pattern 4: Background Tasks (Celery/Async)

```python
from django.db import DatabaseError
from apps.core.exceptions import IntegrationException

@shared_task(bind=True, max_retries=3)
def process_data_sync(self, data):
    try:
        records = extract_records(data)
        save_to_database(records)
        notify_completion()

    except (ValueError, TypeError) as e:
        logger.error(f"Data format error in sync task: {e}", exc_info=True)
        raise

    except DatabaseError as e:
        logger.error(f"Database error in sync task: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)

    except IntegrationException as e:
        logger.error(f"External service error in sync: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)
```

**Key Points:**
- Data errors don't retry (bad data won't get better)
- Database errors retry with backoff
- Integration errors retry with longer backoff
- Task binding allows access to retry mechanism

---

### Pattern 5: API/Service Layer

```python
from apps.core.exceptions import (
    AuthenticationError,
    BusinessLogicException,
    IntegrationException
)

def call_external_api(endpoint, data):
    try:
        response = requests.post(endpoint, json=data, timeout=30)
        response.raise_for_status()
        return response.json()

    except requests.Timeout as e:
        logger.error(f"API timeout: {endpoint}", exc_info=True)
        raise IntegrationException("External service timeout")

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            raise AuthenticationError("API authentication failed")
        elif e.response.status_code >= 500:
            raise IntegrationException(f"External service error: {e.response.status_code}")
        else:
            raise BusinessLogicException(f"API request failed: {e.response.text}")

    except requests.RequestException as e:
        logger.error(f"Network error calling API: {e}", exc_info=True)
        raise IntegrationException("Network error communicating with external service")
```

**Key Points:**
- HTTP errors mapped to domain exceptions
- Timeout handled separately from network errors
- 401 errors raise authentication exceptions
- 5xx errors indicate integration problems

---

## 📚 Available Exception Types

### Django Core Exceptions

```python
from django.core.exceptions import (
    ValidationError,      # Data validation failures
    PermissionDenied,    # Authorization failures
    ObjectDoesNotExist,  # Model not found
    MultipleObjectsReturned  # Query returned multiple objects
)

from django.db import (
    DatabaseError,       # General database errors
    IntegrityError,      # Constraint violations
    OperationalError,    # DB connection/operation errors
)
```

### Application Custom Exceptions

```python
from apps.core.exceptions import (
    # Security
    AuthenticationError,
    SecurityException,
    RateLimitException,

    # Business Logic
    BusinessLogicException,
    BusinessRuleValidationException,

    # Integration
    IntegrationException,
    APIException,
    MQTTException,

    # File Operations
    FileValidationException,
    FileUploadSecurityException,

    # Data
    EnhancedValidationException,
    DatabaseIntegrityException,
)
```

### Python Built-in Exceptions

```python
# Use when appropriate:
ValueError       # Invalid value
TypeError        # Wrong type
AttributeError   # Missing attribute
KeyError         # Missing dict key
IOError          # File I/O errors
OSError          # Operating system errors
```

---

## 🛠️ Tools and Automation

### 1. Exception Scanner

Scan your code for generic exception patterns:

```bash
# Scan entire codebase
python scripts/exception_scanner.py --path apps

# Scan specific module
python scripts/exception_scanner.py --path apps/peoples --format json

# Generate priority fix list
python scripts/exception_scanner.py --path apps --priority-list

# CI/CD mode (fails on violations)
python scripts/exception_scanner.py --path apps --strict
```

### 2. Exception Fixer (Auto-fix Tool)

Automatically fix generic exceptions with context-aware suggestions:

```bash
# Dry run (preview fixes)
python scripts/exception_fixer.py --file apps/peoples/models.py --dry-run

# Auto-fix with high confidence
python scripts/exception_fixer.py --file apps/peoples/models.py --auto-fix --min-confidence 0.8

# Fix entire directory
python scripts/exception_fixer.py --path apps/peoples --auto-fix

# Interactive mode
python scripts/exception_fixer.py --scan-report scan.json --interactive
```

### 3. Pre-commit Hook

Prevent new violations from being committed:

```bash
# Install hooks
bash scripts/setup-git-hooks.sh

# Hook will automatically check staged files
git commit -m "Your message"

# Bypass hook if necessary (requires justification)
git commit --no-verify -m "Your message"
```

---

## 🎯 Decision Tree: Which Exception to Catch?

```
Is it a database operation?
├─ Yes → catch (DatabaseError, IntegrityError)
└─ No → Continue...

Is it a file operation?
├─ Yes → catch (IOError, OSError, FileValidationException)
└─ No → Continue...

Is it user input validation?
├─ Yes → catch (ValidationError, ValueError, TypeError)
└─ No → Continue...

Is it an external API/service call?
├─ Yes → catch (requests.RequestException, IntegrationException, ConnectionError)
└─ No → Continue...

Is it authentication/authorization?
├─ Yes → catch (AuthenticationError, PermissionDenied)
└─ No → Continue...

Is it GraphQL?
├─ Yes → catch specific errors, raise GraphQLError
└─ No → Continue...

Is it a background task?
├─ Yes → catch (DatabaseError, IntegrationException), retry appropriately
└─ No → Review code context and use appropriate specific exceptions
```

---

## 📋 Code Review Checklist

Before submitting PR, verify:

- [ ] No `except Exception:` patterns
- [ ] No bare `except:` clauses
- [ ] Each exception handler catches specific exception types
- [ ] Appropriate logging with correlation IDs
- [ ] No sensitive data in exception messages
- [ ] Exception messages help debugging without exposing internals
- [ ] Tests verify correct exceptions are raised
- [ ] Pre-commit hook passes
- [ ] CI/CD pipeline passes exception quality check

---

## 🚀 Migration Guide

### Step 1: Identify Violations

```bash
python scripts/exception_scanner.py --path apps/your_module --priority-list
```

### Step 2: Auto-fix Low-risk Cases

```bash
python scripts/exception_fixer.py --path apps/your_module --auto-fix --min-confidence 0.8
```

### Step 3: Manual Review Critical Cases

Review and manually fix:
- Authentication logic
- Payment processing
- Security-sensitive operations
- Complex business logic

### Step 4: Add Tests

```python
def test_specific_exception_raised():
    with pytest.raises(DatabaseError):
        function_that_fails_with_db_error()

def test_validation_error_on_invalid_input():
    with pytest.raises(ValidationError) as exc_info:
        validate_user_input(invalid_data)
    assert 'email' in str(exc_info.value)
```

### Step 5: Verify and Commit

```bash
# Run tests
python -m pytest apps/your_module -v

# Verify no violations
python scripts/exception_scanner.py --path apps/your_module

# Commit (pre-commit hook will validate)
git add apps/your_module
git commit -m "fix: replace generic exception handling with specific types"
```

---

## 🔗 Additional Resources

- **Rule 11 Reference:** `.claude/rules.md#rule-11-exception-handling-specificity`
- **Custom Exceptions:** `apps/core/exceptions.py`
- **Exception Scanner:** `scripts/exception_scanner.py`
- **Exception Fixer:** `scripts/exception_fixer.py`
- **CI/CD Workflow:** `.github/workflows/exception-quality-check.yml`

---

## ❓ FAQ

### Q: Can I ever use `except Exception:`?

**A:** No. This is explicitly forbidden by Rule 11. Always use specific exception types.

### Q: What if I don't know which exceptions can be raised?

**A:** Use the exception fixer tool which analyzes context, or check Django/library documentation. When in doubt, start with conservative catches and add more as you discover them through testing.

### Q: What about `except` without any exception type?

**A:** Absolutely forbidden! Bare `except:` catches even `SystemExit` and `KeyboardInterrupt`, making your code very hard to debug and test.

### Q: Can I catch multiple exceptions?

**A:** Yes! Use tuples: `except (ValueError, TypeError) as e:`

### Q: Should I always re-raise exceptions?

**A:** Not always. If you're at an API boundary (GraphQL mutation, REST endpoint), convert to appropriate response. Otherwise, handle or re-raise with context.

---

**Remember:** Specific exception handling is not just a code quality issue—it's a **security and reliability issue**. Generic exceptions hide bugs and vulnerabilities.

✅ **Zero tolerance policy on generic exceptions**