# Mandatory Patterns & Rules

**Zero-tolerance violations and architectural limits**

→ **Quick reference:** See [CLAUDE.md](../CLAUDE.md#critical-rules) for top 8 rules

---

## Table of Contents

- [Overview](#overview)
- [Zero-Tolerance Violations](#zero-tolerance-violations)
- [Architecture Limits](#architecture-limits)
- [Code Quality Standards](#code-quality-standards)
- [Pre-Commit Checklist](#pre-commit-checklist)
- [Enforcement Mechanisms](#enforcement-mechanisms)

---

## Overview

**Purpose:** Prevent anti-patterns, code smells, and security vulnerabilities

**Enforcement:** Pre-commit hooks + flake8 + CI/CD pipeline + Code review

**Violation = PR rejection** (automated)

---

## Zero-Tolerance Violations

### Rule #1: SQL Injection (Legacy API Bypass) ⚠️ DEPRECATED

**Status:** Legacy query layer retired October 29, 2025 (REST migration complete)

**Historical Issue:** SQL injection middleware bypassed non-REST endpoints

**Lesson Learned:** Never bypass security checks for any endpoint type

---

### Rule #2: Bare Except Blocks

**Violation:** Using `except:` or `except Exception:` without specific exception types

❌ **FORBIDDEN:**
```python
try:
    user.save()
except Exception as e:
    logger.error(f"Error: {e}")
```

✅ **REQUIRED:**
```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise
```

**Why:** Generic exceptions hide real errors, impossible to debug

**Detection:** Flake8 E722, pre-commit hook

**Exception Groups:**
- `DATABASE_EXCEPTIONS` - Django ORM errors
- `NETWORK_EXCEPTIONS` - HTTP, socket, timeout errors
- `FILE_EXCEPTIONS` - I/O, permission errors

**Related:** `apps/core/exceptions/patterns.py`

---

### Rule #3: Production Print Statements

**Violation:** Using `print()` statements in production code

❌ **FORBIDDEN:**
```python
def process_payment(amount):
    print(f"Processing ${amount}")  # ❌ Goes to stdout, not logs
    # ...
```

✅ **REQUIRED:**
```python
import logging
logger = logging.getLogger(__name__)

def process_payment(amount):
    logger.info(f"Processing payment: ${amount}")  # ✅ Proper logging
    # ...
```

**Why:** Print statements don't integrate with logging infrastructure, hard to track

**Detection:** Flake8 T001 (requires `flake8-print` plugin)

**Exceptions:** CLI scripts (`scripts/*.py`), management commands

---

### Rule #4: Missing Network Timeouts

**Violation:** Network calls without timeout parameters

❌ **FORBIDDEN:**
```python
response = requests.get(url)  # ❌ Can hang forever
response = requests.post(webhook_url, json=data)  # ❌ No timeout
```

✅ **REQUIRED:**
```python
# Format: (connect_timeout, read_timeout) in seconds
response = requests.get(url, timeout=(5, 15))  # ✅ 5s connect, 15s read
response = requests.post(webhook_url, json=data, timeout=(5, 30))
```

**Why:** Workers hang indefinitely, resource exhaustion

**Timeout Guidelines:**
- API/metadata: `(5, 15)` - 5s connect, 15s read
- File downloads: `(5, 30)` - 5s connect, 30s read
- Long operations: `(5, 60)` - 5s connect, 60s read

---

### Rule #5: CSRF Bypass Without Documentation

**Violation:** Using `@csrf_exempt` without documenting alternative protection

❌ **FORBIDDEN:**
```python
@csrf_exempt
def api_view(request):
    # No CSRF protection, no documentation
    pass
```

✅ **REQUIRED:**
```python
@csrf_exempt  # Exempt: Uses JWT token authentication
def api_view(request):
    """
    CSRF Protection: JWT token validation in middleware
    See: apps.core.middleware.api_authentication
    """
    pass
```

**Why:** CSRF protection critical for state-changing operations

**Alternatives:**
- JWT token authentication
- HMAC signing
- API key validation

---

### Rule #6: Unsafe File Upload

**Violation:** Direct file save without validation

❌ **FORBIDDEN:**
```python
def upload_file(request):
    file = request.FILES['document']
    file.save(f'/uploads/{file.name}')  # ❌ Path traversal vulnerability
```

✅ **REQUIRED:**
```python
from apps.service.services.file_service import perform_secure_uploadattachment

def upload_file(request):
    file = request.FILES['document']
    result = perform_secure_uploadattachment(
        file=file,
        allowed_extensions=['.pdf', '.docx'],
        max_size_mb=10
    )  # ✅ Path traversal protected, type validated
```

**Why:** File upload vulnerabilities = RCE, path traversal attacks

**Protection:**
- File type validation (magic bytes, not extension)
- Size limits
- Path sanitization
- Virus scanning (production)

**Related:** Rule #14 in original `.claude/rules.md`

---

### Rule #7: Hardcoded Secrets

**Violation:** Credentials in code without validation

❌ **FORBIDDEN:**
```python
SECRET_KEY = env("SECRET_KEY")  # ❌ No validation
REDIS_PASSWORD = "hardcoded_password"  # ❌ In code!
```

✅ **REQUIRED:**
```python
def validate_secret(secret_name, secret_value):
    if not secret_value or len(secret_value) < 32:
        raise ValueError(f"Invalid {secret_name}: must be 32+ characters")
    return secret_value

SECRET_KEY = validate_secret("SECRET_KEY", env("SECRET_KEY"))
REDIS_PASSWORD = validate_secret("REDIS_PASSWORD", env("REDIS_PASSWORD"))
```

**Why:** Runtime failures in production, security vulnerabilities

**Requirements:**
- Validate on settings load (fail-fast)
- Minimum 32 characters
- Never commit to git
- Document rotation procedures

---

### Rule #8: Blocking I/O in Request Paths

**Violation:** Using `time.sleep()` in views/request handlers

❌ **FORBIDDEN:**
```python
def save_user(request):
    for attempt in range(3):
        try:
            user.save()
            break
        except Exception:
            time.sleep(2)  # ❌ BLOCKS WORKER THREAD
```

✅ **REQUIRED:**
```python
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(
    exceptions=(IntegrityError, OperationalError),
    max_retries=3,
    retry_policy='DATABASE_OPERATION'  # Exponential backoff with jitter
)
def save_user(request):
    user.save()
```

**Why:** Blocks worker threads, degraded performance

**Alternatives:**
- Exponential backoff with jitter
- Celery tasks for async operations
- Database-level retries

---

## Architecture Limits

**Enforced by:** Lint checks, code review, pre-commit hooks

| Component | Max Size | Reason | Enforcement |
|-----------|----------|--------|-------------|
| **Settings files** | 200 lines | Split by concern (base, dev, prod) | Lint check |
| **Model classes** | 150 lines | Single responsibility principle | Lint check |
| **View methods** | 30 lines | Delegate to services | Complexity check (C901) |
| **Form classes** | 100 lines | Focused validation | Lint check |
| **Utility functions** | 50 lines | Atomic, testable operations | Complexity check |

**Violation Examples:**

❌ **FORBIDDEN:**
```python
# settings.py - 1,600+ lines
DATABASES = {...}
LOGGING = {...}  # 200+ lines
CORS_SETTINGS = {...}
# ... endless configuration
```

✅ **REQUIRED:**
```python
# settings/
#   base.py          (< 200 lines)
#   development.py   (< 100 lines)
#   production.py    (< 100 lines)
#   security/        (separate module)

from .base import *
from .security.middleware import MIDDLEWARE
```

**Related:** God file refactoring (Sep 2025)

---

## Code Quality Standards

### Exception Handling

**Use specific exception types** from `apps/core/exceptions/patterns.py`:

```python
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    FILE_EXCEPTIONS,
)

# Database operations
try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise

# Network calls
try:
    response = requests.get(url, timeout=(5, 15))
except NETWORK_EXCEPTIONS as e:
    logger.error(f"Network error: {e}", exc_info=True)
    raise

# File operations
try:
    with open(file_path) as f:
        data = f.read()
except FILE_EXCEPTIONS as e:
    logger.error(f"File error: {e}", exc_info=True)
    raise
```

### DateTime Usage

**Python 3.12+ compatible patterns:**

```python
# ✅ CORRECT: Centralized imports
from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY, SECONDS_IN_HOUR

# Model fields
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
event_time = models.DateTimeField(default=timezone.now)

# Current time
now = timezone.now()  # ✅ Timezone-aware

# ❌ FORBIDDEN: Deprecated patterns
datetime.utcnow()  # Use timezone.now() instead
from datetime import timezone  # Conflicts with django.utils.timezone
time.sleep(3600)  # Use SECONDS_IN_HOUR constant
```

### Network Calls

**Always include timeout parameters:**

```python
# ✅ CORRECT
import requests

response = requests.get(url, timeout=(5, 15))
response = requests.post(webhook_url, json=data, timeout=(5, 30))

# With error handling
try:
    response = requests.get(url, timeout=(5, 15))
    response.raise_for_status()
except requests.Timeout:
    logger.error(f"Timeout connecting to {url}")
except requests.RequestException as e:
    logger.error(f"Request failed: {e}")
```

### File Operations

**Use secure upload helper:**

```python
from apps.service.services.file_service import perform_secure_uploadattachment

# ✅ CORRECT: Validated upload
result = perform_secure_uploadattachment(
    file=uploaded_file,
    allowed_extensions=['.pdf', '.docx', '.xlsx'],
    max_size_mb=10,
    upload_to='documents/'
)

# ❌ FORBIDDEN: Direct save
uploaded_file.save(f'/uploads/{uploaded_file.name}')
```

---

## Pre-Commit Checklist

**Required before committing code:**

- [ ] Read `.claude/rules.md` (now `docs/RULES.md`)
- [ ] Identify applicable rules for your changes
- [ ] Validate code follows required patterns
- [ ] Run `flake8 apps/` (no E722, T001, C901 violations)
- [ ] Run `pytest -m unit` (unit tests pass)
- [ ] Verify no `print()` statements in production code
- [ ] Check network calls have timeouts
- [ ] Ensure specific exception types used
- [ ] Validate file size limits (if creating new files)

---

## Enforcement Mechanisms

### Pre-Commit Hooks

**Location:** `.githooks/pre-commit`

**Checks:**
- Flake8 style validation
- Bare except blocks (E722)
- Print statements (T001)
- Cyclomatic complexity (C901)
- Celery beat schedule validation
- Markdown link checking

**Installation:**
```bash
./scripts/setup-git-hooks.sh
```

### CI/CD Pipeline

**Location:** `.github/workflows/`

**Checks:**
- All pre-commit hooks
- Security scanning (bandit)
- Test coverage (>80%)
- Code quality score
- License compliance

**Failure = PR blocked**

### Flake8 Configuration

**File:** `.flake8`

```ini
[flake8]
max-line-length = 120
max-complexity = 10
exclude = migrations,__pycache__,.git,venv

# Enforced rules
select = E,W,F,C,T
# E722: Bare except blocks (ZERO TOLERANCE)
# T001: Print statements (production code)
# C901: Cyclomatic complexity > 10

# Per-file ignores
per-file-ignores =
    scripts/*.py:T001                # CLI output OK
    test_*.py:T001,E501,C901         # Test complexity OK
    */management/commands/*.py:T001  # CLI output OK
```

### Static Analysis

**Tools:**
- **bandit:** Security vulnerability scanner
- **pylint:** Code quality analyzer
- **mypy:** Type checking (optional)

**Integration:** CI/CD pipeline

### Code Review

**Automated checks:**
- All rules validated before human review
- PR comments added for violations
- Approval blocked until fixed

**Human review:**
- Architecture alignment
- Business logic correctness
- Test coverage adequacy

---

## Additional Resources

### Related Documentation

- **Quick Start:** [CLAUDE.md](../CLAUDE.md#critical-rules) - Top 8 rules
- **Reference:** [REFERENCE.md](REFERENCE.md#code-quality-tools) - Validation tools
- **Celery:** [CELERY.md](CELERY.md) - Task patterns
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) - Design decisions

### Key Files

- **Exception patterns:** `apps/core/exceptions/patterns.py`
- **DateTime constants:** `apps/core/constants/datetime_constants.py`
- **Retry mechanism:** `apps/core/utils_new/retry_mechanism.py`
- **File service:** `apps/service/services/file_service.py`

### Historical Context

- **Original rules:** `.claude/rules.md` (archived content)
- **Refactoring archive:** `docs/archive/refactorings/REFACTORING_ARCHIVES.md`
- **Code quality reports:** `CODE_QUALITY_OBSERVATIONS_RESOLUTION_FINAL.md` (archived)

---

**Last Updated:** 2025-10-29
**Maintainer:** Security + Quality Team
**Review Cycle:** On rule changes or security updates
