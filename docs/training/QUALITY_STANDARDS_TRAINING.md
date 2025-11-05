# Quality Standards Training Guide

**Audience:** All developers contributing to the codebase

**Duration:** 2 hours (self-paced) + 1 hour hands-on practice

**Last Updated:** November 5, 2025

---

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture Limits](#architecture-limits)
3. [Quality Gates](#quality-gates)
4. [Code Quality Principles](#code-quality-principles)
5. [Automated Enforcement](#automated-enforcement)
6. [Hands-On Exercises](#hands-on-exercises)
7. [Assessment](#assessment)

---

## Introduction

### Why Quality Standards Matter

Quality standards ensure:
- **Maintainability:** Code is easy to understand and modify
- **Reliability:** Fewer bugs and production incidents
- **Collaboration:** Consistent patterns reduce onboarding time
- **Security:** Enforced patterns prevent vulnerabilities

### Our Quality Journey

**Phase 1-6 Results (October-November 2025):**
- 80+ god files eliminated across 16 apps
- Average file size reduced 75% (1,200 → 300 lines)
- 0 production incidents from refactoring
- 100% backward compatibility maintained

**Key Achievement:** Zero-tolerance enforcement of architecture limits via automated tooling.

---

## Architecture Limits

### File Size Limits (ADR 001)

**Purpose:** Prevent "god files" that become unmaintainable

| File Type | Limit | Rationale | Enforcement |
|-----------|-------|-----------|-------------|
| **Settings** | < 200 lines | Split by environment (base, dev, prod) | Pre-commit hook |
| **Models** | < 150 lines | Single model or closely related models | Pre-commit hook |
| **View Methods** | < 30 lines | Delegate to service layer (ADR 003) | Code review |
| **Forms** | < 100 lines | Focused validation logic | Pre-commit hook |
| **Utilities** | < 150 lines | Related helper functions only | Pre-commit hook |

#### Why These Limits?

**150 lines (models):**
- Fits on ~2 screens (no scrolling)
- Easy to understand at a glance
- Encourages single responsibility
- Based on research: [Clean Code](https://www.oreilly.com/library/view/clean-code-a/9780136083238/) recommendations

**30 lines (view methods):**
- Forces service layer extraction
- HTTP logic vs business logic separation
- Easier to test business logic in isolation

**Example: Model File Limit**

```python
# ❌ VIOLATION: 280-line model file with multiple models

# apps/attendance/models.py (280 lines)
class PeopleEventlog(models.Model):
    # ... 100 lines

class Geofence(models.Model):
    # ... 80 lines

class Post(models.Model):
    # ... 100 lines

# Too many concerns in one file!
```

```python
# ✅ COMPLIANT: Split into focused modules

# apps/attendance/models/people_eventlog.py (145 lines)
class PeopleEventlog(models.Model):
    # Focused on attendance tracking only

# apps/attendance/models/geofence.py (78 lines)
class Geofence(models.Model):
    # Focused on geographic boundaries

# apps/attendance/models/post.py (132 lines)
class Post(models.Model):
    # Focused on post/duty station management
```

---

### Exception Handling Standards (ADR 005)

**Rule:** Never use generic `except Exception:` - use specific exception types

**Why?** Generic exceptions:
- Hide real errors
- Make debugging impossible
- Can catch and suppress critical failures (KeyboardInterrupt, SystemExit)

#### Before/After

```python
# ❌ FORBIDDEN: Generic exception
try:
    user.save()
except Exception as e:  # Too broad!
    logger.error(f"Error: {e}")
    # What kind of error? Database? Validation? Network?
```

```python
# ✅ CORRECT: Specific exceptions
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from django.core.exceptions import ValidationError

try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error saving user: {e}", exc_info=True)
    raise  # Re-raise for proper error handling
except ValidationError as e:
    logger.warning(f"Validation failed: {e}")
    # Handle validation errors differently
```

**Exception Patterns Available:**

```python
# apps/core/exceptions/patterns.py

DATABASE_EXCEPTIONS = (
    OperationalError,
    IntegrityError,
    DatabaseError,
)

NETWORK_EXCEPTIONS = (
    requests.exceptions.RequestException,
    socket.timeout,
    ConnectionError,
)

VALIDATION_EXCEPTIONS = (
    ValidationError,
    forms.ValidationError,
)
```

---

### Network Call Standards

**Rule:** ALL network calls MUST include timeout parameters

**Why?** Network calls without timeouts can:
- Hang indefinitely
- Block Celery workers
- Cause cascading failures
- Prevent graceful degradation

#### Before/After

```python
# ❌ FORBIDDEN: No timeout
response = requests.get(api_url)
# Can hang forever!

# ❌ FORBIDDEN: Single timeout value
response = requests.get(api_url, timeout=30)
# What if connection hangs? What if read is slow?
```

```python
# ✅ CORRECT: Connection + read timeouts
response = requests.get(
    api_url,
    timeout=(5, 15)  # (connect_timeout, read_timeout)
)

# ✅ CORRECT: Different timeouts for different operations
response = requests.post(
    webhook_url,
    json=data,
    timeout=(5, 30)  # Longer read for webhooks
)

# ✅ CORRECT: File downloads need longer timeouts
response = requests.get(
    file_url,
    timeout=(5, 60),  # 60s for large files
    stream=True
)
```

**Timeout Guidelines:**

| Operation | Connect Timeout | Read Timeout | Total |
|-----------|----------------|--------------|-------|
| **API calls** | 5s | 15s | 20s |
| **Webhooks** | 5s | 30s | 35s |
| **File downloads** | 5s | 60s | 65s |
| **Database queries** | N/A | 30s | 30s |

---

## Quality Gates

### Pre-Commit Hooks

**Automatically enforced before every commit:**

1. **File Size Validation**
   ```bash
   scripts/check_file_sizes.py
   ```
   - Checks all Python files against limits
   - Blocks commit if violations found

2. **Code Formatting (Black)**
   ```bash
   black --check .
   ```
   - Enforces consistent formatting
   - Auto-fixes with `black .`

3. **Import Sorting (isort)**
   ```bash
   isort --check-only .
   ```
   - Enforces import organization
   - Auto-fixes with `isort .`

4. **Linting (Flake8)**
   ```bash
   flake8 .
   ```
   - Catches style violations
   - Enforces PEP 8 standards

5. **Type Checking (mypy)**
   ```bash
   mypy apps/
   ```
   - Catches type errors
   - Enforces type hints

**Bypassing Hooks (Emergency Only):**

```bash
git commit --no-verify -m "emergency: Fix production issue"
```

**Warning:** Bypassing hooks requires justification in commit message and will be flagged in code review.

---

### CI/CD Pipeline

**Automated checks on every pull request:**

1. **Full Test Suite**
   ```bash
   python -m pytest --cov=apps --cov-report=term-missing
   ```
   - Minimum 80% coverage required
   - All tests must pass

2. **Security Scanning**
   ```bash
   bandit -r apps/
   ```
   - Detects security vulnerabilities
   - Blocks merge if critical issues found

3. **Dependency Audit**
   ```bash
   pip-audit
   ```
   - Checks for vulnerable dependencies
   - Must resolve or document exceptions

4. **Static Analysis**
   ```bash
   python scripts/validate_code_quality.py --verbose
   ```
   - Detects code smells
   - Enforces architecture limits

**PR Merge Requirements:**

- [ ] All CI checks passing
- [ ] 2 approvals from team members
- [ ] No unresolved review comments
- [ ] Branch up to date with main
- [ ] Documentation updated (if needed)

---

### Code Review Checklist

**Reviewers must verify:**

#### Architecture Compliance

- [ ] File sizes within limits
- [ ] No god files or god classes
- [ ] Single Responsibility Principle followed
- [ ] Clear module boundaries

#### Exception Handling

- [ ] No generic `except Exception:`
- [ ] Specific exceptions from patterns.py
- [ ] Exceptions logged with context
- [ ] Re-raise when appropriate

#### Network Calls

- [ ] All requests have timeouts
- [ ] Timeout values appropriate for operation
- [ ] Error handling for network failures
- [ ] Retry logic where appropriate

#### Security

- [ ] No `@csrf_exempt` without justification
- [ ] User input validated and sanitized
- [ ] File uploads validated (type, size, content)
- [ ] SQL queries parameterized (no string concatenation)
- [ ] Secrets not hardcoded

#### Testing

- [ ] New code has tests
- [ ] Tests cover edge cases
- [ ] Tests are maintainable
- [ ] No test-only methods in production code

---

## Code Quality Principles

### 1. Simplicity

**Principle:** Prefer simple, straightforward solutions over clever code

**Example:**

```python
# ❌ COMPLEX: Clever one-liner
result = [x for x in data if x.status == 'active' and x.score > 50 and x.is_verified and not x.is_deleted]

# ✅ SIMPLE: Multi-step with clear intent
active_items = [x for x in data if x.status == 'active']
verified_items = [x for x in active_items if x.is_verified and not x.is_deleted]
result = [x for x in verified_items if x.score > 50]
```

---

### 2. Readability

**Principle:** Code should be self-documenting; minimize comments

**Example:**

```python
# ❌ UNCLEAR: Needs comments
def proc(u, t):
    # Check if user active
    if u.s == 1:
        # Process timestamp
        d = t - u.ct
        # Check if expired
        if d > 86400:
            return False
    return True

# ✅ CLEAR: Self-documenting
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

def is_user_session_valid(user, timestamp):
    """Check if user session is still valid (within 24 hours)."""
    if user.status != UserStatus.ACTIVE:
        return False

    time_since_creation = timestamp - user.created_at
    return time_since_creation <= SECONDS_IN_DAY
```

---

### 3. Small Units

**Principle:** Functions <50 lines, methods <30 lines

**Why?**
- Easier to understand
- Easier to test
- Easier to reuse
- Easier to refactor

**Example:**

```python
# ❌ TOO LARGE: 80-line method
def process_attendance(self, request):
    # Validate form (20 lines)
    # Check geofence (25 lines)
    # Save to database (15 lines)
    # Send notifications (20 lines)
    pass

# ✅ CORRECT: Delegate to helpers
def process_attendance(self, request):
    """Process attendance check-in."""
    form_data = self._validate_attendance_form(request)
    location = self._validate_geofence(form_data['coordinates'])
    event = self._save_attendance_event(form_data, location)
    self._send_notifications(event)
    return event

def _validate_attendance_form(self, request):
    """Validate attendance form data."""
    # 15 lines

def _validate_geofence(self, coordinates):
    """Validate user is within geofence."""
    # 20 lines

def _save_attendance_event(self, form_data, location):
    """Save attendance event to database."""
    # 12 lines

def _send_notifications(self, event):
    """Send notifications for attendance event."""
    # 18 lines
```

---

### 4. Single Responsibility

**Principle:** Each class/function should do one thing and do it well

**Example:**

```python
# ❌ MULTIPLE RESPONSIBILITIES
class UserManager:
    def process_user(self, user_data):
        # Validates data
        # Saves to database
        # Sends email
        # Logs event
        # Updates cache
        pass

# ✅ SINGLE RESPONSIBILITY
class UserValidator:
    def validate(self, user_data):
        """Validate user data."""
        pass

class UserRepository:
    def save(self, user):
        """Save user to database."""
        pass

class UserNotificationService:
    def send_welcome_email(self, user):
        """Send welcome email to user."""
        pass

class UserAuditLogger:
    def log_creation(self, user):
        """Log user creation event."""
        pass
```

---

## Automated Enforcement

### Running Quality Checks Locally

**Before committing:**

```bash
# 1. Format code
black .
isort .

# 2. Run linters
flake8 .
mypy apps/

# 3. Check file sizes
python scripts/check_file_sizes.py --verbose

# 4. Run tests
python -m pytest --cov=apps --cov-report=term-missing

# 5. Security scan
bandit -r apps/

# 6. Overall quality check
python scripts/validate_code_quality.py --verbose
```

**Or use the all-in-one script:**

```bash
./scripts/run_quality_checks.sh
```

---

### Interpreting Quality Reports

**File Size Report:**

```
🔍 Checking file sizes...

❌ VIOLATIONS FOUND:

apps/attendance/models.py: 615 lines (limit: 150)
  → Split into focused modules (see REFACTORING_PLAYBOOK.md)

apps/peoples/forms.py: 280 lines (limit: 100)
  → Extract into form classes per model

✅ COMPLIANT FILES: 1,234
❌ VIOLATIONS: 2
```

**Code Quality Report:**

```
📊 Code Quality Metrics:

God Files: 2 (Target: 0)
Average File Size: 145 lines (Target: <150)
Generic Exceptions: 12 (Target: 0)
Missing Timeouts: 3 (Target: 0)
Test Coverage: 82% (Target: >80%)

🎯 PRIORITY ISSUES:
1. apps/core/utils.py:45 - Generic except Exception
2. apps/api/views.py:123 - requests.get without timeout
3. apps/helpbot/services.py:234 - Generic except Exception
```

---

## Hands-On Exercises

### Exercise 1: Fix File Size Violation

**Scenario:** You have a 250-line model file that violates the 150-line limit.

**Task:** Split the file into compliant modules

**File:** `apps/example/models.py` (250 lines)

```python
# Contains:
# - UserStatus enum (15 lines)
# - UserType enum (12 lines)
# - User model (90 lines)
# - UserProfile model (80 lines)
# - UserSettings model (53 lines)
```

**Steps:**

1. Analyze responsibilities
2. Create module structure
3. Extract enums
4. Split models
5. Create `__init__.py`
6. Preserve original file
7. Test imports
8. Verify tests pass

**Solution:** See `docs/architecture/REFACTORING_PLAYBOOK.md`, Pattern 1

---

### Exercise 2: Fix Generic Exception

**Scenario:** You have code with generic exception handling

**Task:** Replace with specific exceptions

**Code:**

```python
def process_payment(payment_data):
    try:
        # Validate payment data
        validate_payment(payment_data)

        # Call external payment API
        response = requests.post(
            PAYMENT_API_URL,
            json=payment_data
        )

        # Save to database
        payment = Payment.objects.create(**payment_data)

        return payment
    except Exception as e:
        logger.error(f"Payment error: {e}")
        return None
```

**Problems:**
1. Generic `except Exception`
2. Missing request timeout
3. Multiple failure modes hidden
4. Returns None on error (unclear what failed)

**Solution:**

```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS
from django.core.exceptions import ValidationError

def process_payment(payment_data):
    """Process payment with proper error handling."""

    # Step 1: Validate
    try:
        validate_payment(payment_data)
    except ValidationError as e:
        logger.warning(f"Payment validation failed: {e}")
        raise PaymentValidationError("Invalid payment data") from e

    # Step 2: Call external API
    try:
        response = requests.post(
            PAYMENT_API_URL,
            json=payment_data,
            timeout=(5, 30)  # 5s connect, 30s read
        )
        response.raise_for_status()
    except NETWORK_EXCEPTIONS as e:
        logger.error(f"Payment API call failed: {e}", exc_info=True)
        raise PaymentAPIError("Failed to process payment") from e

    # Step 3: Save to database
    try:
        payment = Payment.objects.create(**payment_data)
    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Failed to save payment: {e}", exc_info=True)
        raise PaymentDatabaseError("Database error saving payment") from e

    return payment
```

---

### Exercise 3: Add Request Timeouts

**Scenario:** You have code making network calls without timeouts

**Task:** Add appropriate timeouts

**Code:**

```python
def fetch_user_data(user_id):
    # Fetch from API
    response = requests.get(f"{API_URL}/users/{user_id}")
    return response.json()

def download_report(report_id):
    # Download large file
    response = requests.get(f"{API_URL}/reports/{report_id}/download")
    return response.content

def send_webhook(webhook_url, data):
    # Send webhook notification
    response = requests.post(webhook_url, json=data)
    return response.status_code
```

**Solution:**

```python
# Guideline: (connect_timeout, read_timeout)
# - API calls: (5, 15)
# - File downloads: (5, 60)
# - Webhooks: (5, 30)

def fetch_user_data(user_id):
    """Fetch user data from API."""
    response = requests.get(
        f"{API_URL}/users/{user_id}",
        timeout=(5, 15)  # Standard API call
    )
    response.raise_for_status()
    return response.json()

def download_report(report_id):
    """Download large report file."""
    response = requests.get(
        f"{API_URL}/reports/{report_id}/download",
        timeout=(5, 60),  # Longer for large files
        stream=True  # Don't load entire file into memory
    )
    response.raise_for_status()
    return response.content

def send_webhook(webhook_url, data):
    """Send webhook notification."""
    try:
        response = requests.post(
            webhook_url,
            json=data,
            timeout=(5, 30)  # Webhooks can be slow
        )
        response.raise_for_status()
        return response.status_code
    except requests.exceptions.Timeout:
        logger.warning(f"Webhook timeout: {webhook_url}")
        # Don't fail if webhook times out
        return 408  # Request Timeout
```

---

## Assessment

### Knowledge Check

**Answer these questions to verify understanding:**

1. **What is the maximum line limit for a Django model file?**
   - Answer: < 150 lines

2. **Why are generic `except Exception:` blocks forbidden?**
   - Answer: They hide real errors, make debugging impossible, and can catch critical failures

3. **What are the two timeout values for requests.get()?**
   - Answer: (connect_timeout, read_timeout)

4. **What should you do with the original file when refactoring?**
   - Answer: Preserve as `*_deprecated.py` with deprecation notice

5. **What is the minimum test coverage percentage?**
   - Answer: 80%

---

### Practical Assessment

**Complete these tasks:**

1. **Find and fix a file size violation:**
   ```bash
   python scripts/check_file_sizes.py --path apps/
   # Pick one violation and refactor following REFACTORING_PLAYBOOK.md
   ```

2. **Find and fix a generic exception:**
   ```bash
   grep -r "except Exception" apps/ --include="*.py"
   # Pick one and replace with specific exceptions
   ```

3. **Find and fix a missing timeout:**
   ```bash
   grep -r "requests\.\(get\|post\)" apps/ --include="*.py"
   # Verify all have timeout parameter
   ```

4. **Run full quality check:**
   ```bash
   python scripts/validate_code_quality.py --verbose
   # Achieve 0 violations
   ```

---

## Resources

### Documentation

- [REFACTORING_PLAYBOOK.md](../architecture/REFACTORING_PLAYBOOK.md) - Complete refactoring guide
- [REFACTORING_PATTERNS.md](../architecture/REFACTORING_PATTERNS.md) - Quick pattern reference
- [ADR 001: File Size Limits](../architecture/adr/001-file-size-limits.md)
- [ADR 005: Exception Handling](../architecture/adr/005-exception-handling-standards.md)

### Tools

- `scripts/check_file_sizes.py` - File size validation
- `scripts/detect_god_files.py` - Find refactoring candidates
- `scripts/validate_code_quality.py` - Overall quality check

### External Resources

- [Clean Code by Robert C. Martin](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
- [Python PEP 8 Style Guide](https://pep8.org/)
- [Django Best Practices](https://django-best-practices.readthedocs.io/)

---

## Next Steps

**After completing this training:**

1. Complete [Refactoring Training](REFACTORING_TRAINING.md)
2. Complete [Service Layer Training](SERVICE_LAYER_TRAINING.md)
3. Complete [Testing Training](TESTING_TRAINING.md)
4. Apply knowledge to your next PR
5. Help onboard new team members

---

**Training Complete! 🎓**

You now understand our quality standards and how to maintain them. Remember: quality is not optional—it's enforced automatically.

**Questions?** Ask in #engineering Slack channel or review the documentation links above.

---

**Last Updated:** November 5, 2025

**Maintainer:** Development Team

**Next Review:** February 2026
