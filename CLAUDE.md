# CLAUDE.md - Quick Reference Guide

> **Context**: Enterprise facility management platform (Django 5.2.1) with multi-tenant architecture, REST APIs, PostgreSQL task queue, and advanced security middleware.

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [⛔ Critical Rules](#-critical-rules-read-first)
- [Architecture At-a-Glance](#architecture-at-a-glance)
- [Development Best Practices](#development-best-practices)
- [📚 Complete Documentation](#-complete-documentation)
- [Support](#support)
- [Recent Updates](#recent-updates)

---

## Quick Start

### Python Version Setup (IMPORTANT)

**Recommended: Python 3.11.9** for maximum stability with scikit-learn and data science packages.

```bash
# If using pyenv (recommended)
pyenv install 3.11.9
pyenv local 3.11.9

# Create fresh virtual environment
rm -rf venv
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate

# Verify Python version
python --version  # Should show: Python 3.11.9
```

### Installation

⚠️ **IMPORTANT**: Do NOT use `pip install -r requirements.txt` (this file has been removed to prevent platform conflicts).

**Recommended: Smart Installer (Detects your platform automatically)**
```bash
source venv/bin/activate
python scripts/install_dependencies.py              # Full installation
python scripts/install_dependencies.py --dry-run    # Preview what will be installed
python scripts/install_dependencies.py --minimal    # Core dependencies only
```

**Alternative: Manual Platform-Specific Installation**

**macOS:**
```bash
source venv/bin/activate
pip install -r requirements/base-macos.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
```

**Linux:**
```bash
pip install -r requirements/base-linux.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
pip install -r requirements/ai_requirements.txt
```

**What's the difference?**
- **macOS**: Uses Metal Performance Shaders (MPS) for GPU acceleration, NO CUDA packages
- **Linux**: Includes NVIDIA CUDA 12.8 libraries for GPU acceleration

📖 **See**: [Complete Installation Guide](.github/INSTALL_GUIDE.md) for troubleshooting and platform-specific details

### Infrastructure Requirements

⚠️ **CRITICAL**: The following infrastructure is **required** for production deployment:

#### Redis (MANDATORY)

**Required for**: Journal rate limiting, Celery task queue, caching layer

**Backend**: Must use `django-redis` cache backend (NOT memcached or filesystem)

```python
# intelliwiz_config/settings/base.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        }
    }
}
```

**Why**: Journal security middleware uses Redis sorted sets for cross-worker rate limiting (Nov 2025 fix). In-memory rate limiting was removed because it:
- Resets on worker restart
- Doesn't work across multiple workers
- Allows rate limit bypass in multi-process deployments

**Deployment validation**:
```bash
# Verify Redis connectivity
python manage.py shell -c "from django.core.cache import cache; cache.client.get_client().ping(); print('✅ Redis OK')"
```

**Startup check**: Journal middleware validates Redis backend on initialization. Check logs for:
```
✅ Journal rate limiting: Redis connection verified
```

If Redis unavailable, middleware logs warning and operates in **fail-open mode** (allows all requests - less secure but prevents blocking legitimate users).

📖 **See**: `intelliwiz_config/settings/base.py` for complete Redis configuration

### Top 10 Commands

```bash
## Development server
python manage.py runserver                              # HTTP only
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application  # With WebSockets

## Testing
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v

## Celery workers
./scripts/celery_workers.sh start                       # All optimized workers

## Database
python manage.py makemigrations && python manage.py migrate
python manage.py init_intelliwiz default                # Initialize

## Code quality
python scripts/validate_code_quality.py --verbose
python scripts/check_file_sizes.py --verbose              # Check file size limits
python scripts/detect_god_files.py --path apps/your_app   # Find refactoring candidates

## Refactoring verification
python scripts/verify_attendance_models_refactoring.py    # Verify model refactorings
python manage.py check                                    # Check for import errors

## Schedule validation
python manage.py validate_schedules --verbose
python manage.py validate_schedules --check-orphaned-tasks
```

📖 **More commands**: Check `scripts/` directory and app-level documentation

---

## ⛔ Critical Rules (READ FIRST)

### 🔥 Zero-Tolerance Security Violations

**Before ANY code changes, read `.claude/rules.md` - these patterns are FORBIDDEN:**

| Violation | Why Forbidden | Required Pattern |
|-----------|---------------|------------------|
| `except Exception:` | Hides real errors | Use specific exceptions from `apps/core/exceptions/patterns.py` |
| Custom encryption | Unaudited crypto = vulnerabilities | Require security team sign-off |
| `@csrf_exempt` | Disables CSRF protection | Document alternative protection mechanism |
| Debug info in responses | Exposes internal architecture | Sanitize all error responses |
| File upload without validation | Path traversal, injection attacks | Use `perform_secure_uploadattachment` |
| File download without permissions | IDOR, cross-tenant access | Use `SecureFileDownloadService` with validation |
| Missing network timeouts | Workers hang indefinitely | `requests.get(url, timeout=(5, 15))` |
| Secrets without validation | Runtime failures in production | Validate on settings load |

### 🔒 Secure File Access Standards

**ALL file downloads MUST use `SecureFileDownloadService` for permission validation:**

```python
# ✅ CORRECT: Secure file download with multi-layer validation
from apps.core.services.secure_file_download_service import SecureFileDownloadService

# Validate attachment access (ownership, tenant, permissions)
attachment = SecureFileDownloadService.validate_attachment_access(
    attachment_id=request.GET['id'],
    user=request.user
)

# Serve file securely (path validation + permission check)
response = SecureFileDownloadService.validate_and_serve_file(
    filepath=attachment.filepath,
    filename=attachment.filename,
    user=request.user,
    owner_id=attachment.owner
)

# ❌ FORBIDDEN: Direct file access without validation
attachment = Attachment.objects.get(id=request.GET['id'])  # No permission check
with open(attachment.path, 'rb') as f:  # IDOR vulnerability
    return FileResponse(f)
```

**Security Layers Enforced:**
1. **Tenant Isolation** - Cross-tenant access blocked
2. **Ownership Validation** - User must own file or have permissions
3. **Path Traversal Prevention** - MEDIA_ROOT boundary enforcement
4. **Audit Logging** - All access attempts logged with correlation IDs
5. **Default Deny** - Explicit permission required for access

### 📐 Architecture Limits (MANDATORY)

**File size limits prevent god files and maintainability issues:**

- Settings files: **< 200 lines** (split by environment)
- Model classes: **< 150 lines** (single responsibility)
- View methods: **< 30 lines** (delegate to services)
- Form classes: **< 100 lines** (focused validation)
- Utility functions: **< 50 lines** (atomic, testable)

**Violation = PR rejection by automated checks**

### 🛡️ Exception Handling Standards

```python
# ✅ CORRECT: Specific exception types
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise

# ❌ FORBIDDEN: Generic exceptions
try:
    user.save()
except Exception as e:  # TOO BROAD
    logger.error(f"Error: {e}")
```

### 🕐 DateTime Standards (Python 3.12+ Compatible)

```python
# ✅ CORRECT: Centralized imports and constants
from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from apps.core.constants.datetime_constants import SECONDS_IN_DAY, SECONDS_IN_HOUR
from apps.core.utils_new.datetime_utilities import get_current_utc, convert_to_utc

# Model fields
created_at = models.DateTimeField(auto_now_add=True)  # Creation timestamp
updated_at = models.DateTimeField(auto_now=True)      # Last modified
event_time = models.DateTimeField(default=timezone.now)  # User-defined

# ❌ FORBIDDEN: Deprecated patterns
datetime.utcnow()  # Use timezone.now() instead
time.sleep(3600)   # Use SECONDS_IN_HOUR constant
from datetime import timezone  # Conflicts with django.utils.timezone
```

### 📋 Pre-Code-Change Checklist

**Claude Code MUST complete before ANY modifications:**

1. ✅ Read `.claude/rules.md`
2. ✅ Identify applicable rules for planned changes
3. ✅ Validate proposed code follows required patterns
4. ✅ Reject implementations that violate any rule

**Automated enforcement**: Pre-commit hooks, CI/CD pipeline, static analysis

---

## Architecture At-a-Glance

### System Profile

**Enterprise facility management platform** for multi-tenant security guarding, facilities, and asset management.

- **Framework**: Django 5.2.1 + PostgreSQL 14.2 with PostGIS
- **APIs**: Primary REST API at `/api/v2/` (type-safe, Pydantic-validated); Legacy endpoints at `/api/v1/` for specialized use cases only
- **Task Queue**: Celery with PostgreSQL-native session storage
- **Authentication**: Custom user model (`peoples.People`) with multi-model architecture
- **Multi-tenancy**: Tenant-aware models with database routing

### Core Business Domains

| Domain | Primary Apps | Purpose |
|--------|-------------|---------|
| **Operations** | `activity`, `work_order_management`, `scheduler` | Task management, PPM, scheduling |
| **Assets** | `inventory`, `monitoring` | Asset tracking, maintenance |
| **People** | `peoples`, `attendance` | Authentication, attendance, expenses |
| **Help Desk** | `y_helpdesk` | Ticketing, escalations, SLAs |
| **Reports** | `reports` | Analytics, scheduled reports |
| **Security** | `noc`, `face_recognition` | AI monitoring, biometrics |
| **AI/ML** | `ml_training` | ML training data platform, dataset management, labeling, active learning |
| **Wellness** | `journal`, `wellness` | Wellbeing aggregation, evidence-based interventions |

### URL Structure

```text
/operations/     # Tasks, tours, work orders
/assets/         # Inventory, maintenance
/people/         # Directory, attendance
/help-desk/      # Tickets, escalations
/reports/        # Analytics
/admin/          # Administration
/ml-training/    # ML training data platform (dataset management, labeling, active learning)
/api/journal/    # Journal entries from mobile (Kotlin)
/api/wellness/   # Wellness content delivery
/journal/analytics/  # Wellbeing trends dashboard (admin)
```

**Note on Wellness Architecture**: The `journal` and `wellness` apps work together as an **aggregation system**. Journal entries originate from Kotlin mobile frontends with mood/stress/energy ratings. The backend analyzes these entries in real-time (`JournalAnalyticsService`) and delivers contextual, evidence-based wellness content. Site admins view aggregated wellbeing metrics through Django Admin and analytics dashboards.

**Note on API Versioning (V1→V2 Migration - Nov 2025)**:
- **Primary API**: `/api/v2/` - Type-safe REST with Pydantic validation, comprehensive endpoints for all business domains
- **Legacy V1 Endpoints**: The following V1 endpoints remain active for specialized hardware/legacy client support:
  - `/api/v1/biometrics/` - Biometric device integrations (face recognition, fingerprint)
  - `/api/v1/assets/nfc/` - NFC tag scanning for asset management
  - `/api/v1/journal/` - Mobile journal entry submission (Kotlin app)
  - `/api/v1/wellness/` - Wellness content delivery (legacy mobile clients)
  - `/api/v1/search/` - Global search endpoint
  - `/api/v1/helpbot/` - AI chatbot interactions
- **Migration Status**: All core REST API functionality migrated to V2 (Nov 7-8, 2025). Generic V1 sync serializers relocated to `apps/core/serializers/sync_base_serializers.py` for backward compatibility.
- **Deprecation Timeline**: Legacy V1 endpoints will remain active until all specialized clients migrate to V2 equivalents.

📖 **See**: [Architecture Decision Records](docs/architecture/adr/) and [Documentation Index](docs/DOCUMENTATION_INDEX.md)

---

## Development Best Practices

### Code Quality Principles

1. **Simplicity** - Prefer simple, clean, maintainable code
2. **Readability** - Self-documenting patterns, minimal comments
3. **Small units** - Functions <50 lines, methods <30 lines
4. **Single responsibility** - One purpose per class/function
5. **Avoid deep nesting** - Max 3 levels of conditionals/loops
6. **DRY principle** - Use helper functions, avoid duplication
7. **Explicit imports** - No wildcard imports (except settings)
8. **Security first** - Always validate and sanitize user input
9. **No global state** - Pass context explicitly
10. **Django best practices** - Use framework security features

### Network Call Standards

**ALL network calls MUST include timeout parameters:**

```python
# ✅ CORRECT: With timeout
response = requests.get(url, timeout=(5, 15))  # (connect, read) seconds
response = requests.post(webhook_url, json=data, timeout=(5, 30))

# ❌ INCORRECT: No timeout (can hang workers)
response = requests.get(url)
```

**Timeout guidelines:**
- API/metadata: `(5, 15)` - 5s connect, 15s read
- File downloads: `(5, 30)` - 5s connect, 30s read
- Long operations: `(5, 60)` - 5s connect, 60s read

### Blocking I/O Prevention

**Never use `time.sleep()` in request paths:**

```python
# ✅ CORRECT: Exponential backoff with jitter
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(
    exceptions=(IntegrityError, OperationalError),
    max_retries=3,
    retry_policy='DATABASE_OPERATION'
)
def save_user(user):
    user.save()

# ❌ INCORRECT: Fixed delay blocks worker
def save_user(user):
    for attempt in range(3):
        try:
            user.save()
            break
        except Exception:
            time.sleep(2)  # BLOCKS WORKER THREAD
```

### Performance Optimization

```python
# ✅ Database query optimization
users = People.objects.select_related('profile', 'organizational').all()
users = People.objects.with_full_details()  # Custom helper

# ✅ Prefetch for many-to-many
tasks = Task.objects.prefetch_related('assigned_people').all()

# ❌ N+1 query problem
for user in People.objects.all():
    print(user.profile.gender)  # Generates extra query per user
```

---

## 📚 Complete Documentation

> **Note**: Most documentation removed during V2 migration (Nov 2025) has been archived. See [TRANSITIONAL_ARTIFACTS_TRACKER.md](TRANSITIONAL_ARTIFACTS_TRACKER.md) for deprecated endpoints and transitional code scheduled for removal.

### Documentation Index

📖 **[Complete Documentation Catalog](docs/DOCUMENTATION_INDEX.md)** - Comprehensive index of all project documentation with status tracking and navigation.

### Architecture Decision Records (Active)

- **[ADRs](docs/architecture/adr/)** - Documented architectural decisions with context and consequences
- Latest: ADR-008 (Ultrathink Technical Debt Remediation - Nov 2025)

### Key Reference Documents (Root Directory)

**Core Architecture & Refactoring:**
- **God File Refactoring**: `GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md`
- **Security Mentor**: `SECURITY_FACILITY_MENTOR_PHASE2_COMPLETE.md`
- **Operator Guide**: `NON_NEGOTIABLES_OPERATOR_GUIDE.md`
- **Exception Handling**: `EXCEPTION_HANDLING_PART3_COMPLETE.md` - 100% remediation (554→0 violations)

**Quality & Monitoring:**
- **Removed Code Inventory**: `REMOVED_CODE_INVENTORY.md`
- **Celery Task Inventory**: `CELERY_TASK_INVENTORY_REPORT.md`
- **Code Quality Remediation**: `CODE_QUALITY_OBSERVATIONS_RESOLUTION_FINAL.md`
- **Transitional Artifacts**: `TRANSITIONAL_ARTIFACTS_TRACKER.md`

**API Migration:**
- **REST API Migration**: `REST_API_MIGRATION_COMPLETE.md` (legacy query layer retired Oct 2025)

### Key Files

- **Rules**: `.claude/rules.md` (mandatory reading)
- **Settings**: `intelliwiz_config/settings/`
- **URLs**: `intelliwiz_config/urls_optimized.py`
- **User model**: `apps/peoples/models.py`
- **Security**: `apps/core/models.py`, `apps/core/middleware/`
- **Multi-tenancy**: `apps/tenants/models.py`
- **Test config**: `pytest.ini`

---

## Support

- **Security issues**: Contact security team immediately
- **Architecture questions**: Review [Architecture Decision Records](docs/architecture/adr/) and completion reports
- **Quality violations**: Run validation tools before asking - see `.claude/rules.md`
- **Common problems**: Check `KNOWN_RACE_CONDITIONS.md` and GitHub issues
- **New features**: Follow architecture limits in CLAUDE.md and `.claude/rules.md`

---

**Last Updated**: November 11, 2025
**Maintainer**: Development Team
**Review Cycle**: Quarterly or on major architecture changes

## Recent Updates

- **Nov 11, 2025**: Ultrathink Phase 7 - Race condition fix + 3 technical debt items ([details](ULTRATHINK_REMEDIATION_PHASE7_COMPLETE.md))
- **Nov 11, 2025**: Ultrathink Phase 6 - ML conflict prediction infrastructure ([details](ULTRATHINK_REMEDIATION_PHASE6_COMPLETE.md))
- **Nov 11, 2025**: Ultrathink Phase 5 - 11 security vulnerabilities + critical bugs fixed ([details](ULTRATHINK_REMEDIATION_PHASE5_COMPLETE.md))
- **Nov 10, 2025**: Installation improvements - Smart dependency installer ([details](.github/INSTALL_GUIDE.md))

**Full History**: See [Detailed Changelog](docs/project-history/CHANGELOG_DETAILED.md) and [docs/project-history/](docs/project-history/)
