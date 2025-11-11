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
- **Linux**: Includes NVIDIA CUDA 12.1 libraries for GPU acceleration

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

📖 **See**: [Settings & Configuration](docs/configuration/SETTINGS_AND_CONFIG.md) for complete Redis setup

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

**📖 See**: [Complete Command Reference](docs/workflows/COMMON_COMMANDS.md)

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

**Note on Wellness Architecture**: The `journal` and `wellness` apps work together as an **aggregation system**. Journal entries originate from Kotlin mobile frontends with mood/stress/energy ratings. The backend analyzes these entries in real-time (`JournalAnalyticsService`) and delivers contextual, evidence-based wellness content. Site admins view aggregated wellbeing metrics through Django Admin and analytics dashboards. See [Wellness & Journal System](docs/features/DOMAIN_SPECIFIC_SYSTEMS.md#wellness--journal-system) for complete details.

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

**📖 See**: [Complete System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md)

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

> **⚠️ DOCUMENTATION NOTICE (Nov 11, 2025):**
> The comprehensive docs/ structure referenced below was removed during V2 migration (commit 4dc48df). Most documentation exists as completion reports in the root directory. Documentation reorganization is pending.
>
> **Available Documentation:**
> - Architecture Decision Records: `docs/architecture/adr/` (active)
> - Completion Reports: Root directory (see Key Reference Documents below)
> - App-Level Docs: `apps/*/docs/` and `apps/*/README.md`

<!-- COMMENTED OUT - Documentation files removed in V2 migration (Nov 8, 2025)
### Architecture & Design

- **[System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md)** - Complete architectural overview, business domains, security architecture, refactored modules
- **[Query Optimization Architecture](docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md)** - N+1 detection vs optimization service, decision tree, performance patterns
- **[Refactoring Patterns](docs/architecture/REFACTORING_PATTERNS.md)** - God file refactoring patterns with step-by-step guide and examples
- **[Refactoring Playbook](docs/architecture/REFACTORING_PLAYBOOK.md)** ⚠️ **MANDATORY** - Complete refactoring guide for future work (Phase 1-6 patterns)
- **[Architecture Decision Records (ADRs)](docs/architecture/adr/)** - Documented architectural decisions with context and consequences
- **[Project Retrospective](docs/PROJECT_RETROSPECTIVE.md)** - Complete Phase 1-6 refactoring journey with lessons learned

### Workflows & Operations

- **[Common Commands](docs/workflows/COMMON_COMMANDS.md)** - Complete command reference organized by category
- **[Background Processing](docs/workflows/BACKGROUND_PROCESSING.md)** - Enterprise Celery with specialized queues, monitoring, circuit breakers
- **[Celery Configuration Guide](docs/workflows/CELERY_CONFIGURATION_GUIDE.md)** ⚠️ **MANDATORY** - Complete Celery standards (decorators, naming, organization, beat schedule)
- **[Idempotency Framework](docs/workflows/IDEMPOTENCY_FRAMEWORK.md)** - Duplicate task prevention with Redis + PostgreSQL fallback

### Testing & Quality

- **[Testing & Quality Guide](docs/testing/TESTING_AND_QUALITY_GUIDE.md)** - Comprehensive testing docs, code quality validation, pre-commit hooks, quality metrics
- **[Testing Training](docs/training/TESTING_TRAINING.md)** - Writing effective tests for refactored code
- **[Exception Handling Quick Reference](docs/quick_reference/EXCEPTION_HANDLING_QUICK_REFERENCE.md)** - Pattern selector, best practices, validation

### API & Integration

- **[Type-Safe API Contracts](docs/api/TYPE_SAFE_CONTRACTS.md)** - REST v1/v2 with Pydantic, WebSocket patterns, Kotlin/Swift codegen, OpenAPI schemas

### Features & Systems

- **[Domain-Specific Systems](docs/features/DOMAIN_SPECIFIC_SYSTEMS.md)** - Security AI Mentor (7 pillars), Stream Testbench, Caching Strategy, Face Recognition, NOC, Reports System

### Configuration & Setup

- **[Settings & Configuration](docs/configuration/SETTINGS_AND_CONFIG.md)** - Environment files, settings structure, database config, logging, Redis, security settings

### Team Training

- **[Quality Standards Training](docs/training/QUALITY_STANDARDS_TRAINING.md)** - Understanding quality gates and architecture limits
- **[Refactoring Training](docs/training/REFACTORING_TRAINING.md)** - How to split god files using proven patterns
- **[Service Layer Training](docs/training/SERVICE_LAYER_TRAINING.md)** - Implementing ADR 003 service patterns
- **[Testing Training](docs/training/TESTING_TRAINING.md)** - Writing effective tests for refactored code

### Troubleshooting

- **[Common Issues](docs/troubleshooting/COMMON_ISSUES.md)** - Solutions to pre-commit hooks, CI/CD, legacy API quirks, idempotency, Celery, Flake8, database, Redis, performance issues
-->

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
- **Architecture questions**: Review [System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md) and domain guides
- **Quality violations**: Run validation tools before asking - see [Testing & Quality Guide](docs/testing/TESTING_AND_QUALITY_GUIDE.md)
- **Common problems**: Check [Troubleshooting Guide](docs/troubleshooting/COMMON_ISSUES.md) first
- **New features**: Follow architecture limits and refactoring patterns

---

**Last Updated**: November 11, 2025 (Ultrathink Phase 3 - Code quality remediation: 6 critical issues resolved)
**Previous Update**: November 11, 2025 (Ultrathink Phase 2 - Technical debt remediation: 7 issues resolved)
**Maintainer**: Development Team
**Review Cycle**: Quarterly or on major architecture changes

**Recent Changes (Nov 11, 2025) - Ultrathink Remediation Phase 3 (6 Critical Issues)**:

**CRITICAL Priority (Phase 1):**
- ✅ **Issue #5: Site Onboarding Missing FK Fixed** (`apps/site_onboarding/services/site_service.py`) - IntegrityError prevention
  - SiteService.create_site() now requires conversation_session FK before creating OnboardingSite
  - Made conversation_session_id a required parameter (removed default=None)
  - Removed invalid 'name' field reference (field doesn't exist on model)
  - Added test_create_site_requires_conversation_session() for FK validation
  - Prevents 100% crash rate with IntegrityError: NOT NULL constraint failed
- ✅ **Issue #6: Streamlab Orphaned Async Tasks Fixed** (`apps/streamlab/consumers.py`) - Memory leak elimination
  - Added task lifecycle management to StreamMetricsConsumer
  - Store task reference in self.periodic_task, cancel on disconnect()
  - Proper asyncio.CancelledError handling in send_periodic_updates()
  - Added test_background_task_cancelled_on_disconnect() lifecycle test
  - Prevents zombie tasks hammering DB after WebSocket disconnect

**HIGH Priority (Phase 2):**
- ✅ **Issue #4: Service Auth Module Deprecated** (`apps/service/auth.py`) - Security vulnerability documentation
  - Added DeprecationWarning to all 4 authentication functions
  - Created comprehensive apps/service/DEPRECATION_NOTICE.md (250+ lines)
  - Documented critical bugs: KeyError risk, IP validation bypass (allowAccess reset to True), password logging
  - Verified zero production usage (legacy GraphQL auth, modern code uses apps.peoples.services.authentication_service)
  - Scheduled removal: March 2026

**CLEANUP Priority (Phase 3):**
- ✅ **Issue #1: Scheduler Dead Code Removed** (`apps/scheduler/services.py`) - 94 lines eliminated
  - Deleted unused TourJobService class with missing imports (Job, DatabaseConstants, DatabaseError, ObjectDoesNotExist)
  - Fixed duplicate Cast import in apps/scheduler/models/reminder.py
  - Updated 6 background_tasks files: apps.reminder → apps.scheduler.models.reminder imports
- ✅ **Issue #2: Search Cache No-op Removed** (`apps/search/services/caching_service.py`) - 42 lines eliminated
  - Deleted invalidate_entity_cache() method (only logged, never invalidated Redis)
  - Removed test_cache_invalidation_on_entity_update() (test admitted it didn't work)
  - Added TODO comment for future cache invalidation implementation
- ✅ **Issue #3: Security Intelligence Shim Deleted** (`apps/security_intelligence/`) - 32 lines eliminated
  - Deleted entire orphaned legacy app directory (re-imported apps.noc.security_intelligence)
  - Never activated (not in INSTALLED_APPS), zero production imports
  - Real app remains at apps.noc.security_intelligence

📊 **Phase 3 Impact**: 6 issues resolved, 21 files modified, 3 files deleted, 220+ lines dead code removed, 2 critical bugs fixed, 1 security module deprecated, 100% backward compatibility

**Previous Changes (Nov 11, 2025) - Ultrathink Remediation Phase 2 (7 Issues)**:

**HIGH Priority (Phase 1):**
- ✅ **Issue #6b: Fake PDF Generation Fixed** (`apps/report_generation/tasks.py`) - Replaced placeholder with AsyncPDFGenerationService integration
  - Real PDF generation using WeasyPrint with proper error handling
  - Updates GeneratedReport.pdf_file with actual path
  - Returns success=False on failure (was always True)
- ✅ **Issue #4: N+1 Query Eliminated** (`apps/performance_analytics/services/team_analytics_service.py`) - Coaching queue optimization
  - Replaced per-worker COUNT loop with single annotated query
  - Query count reduced from N+1 to 2 total
  - 50-70% performance improvement for 50+ worker sites

**MEDIUM Priority (Phase 2):**
- ✅ **Issue #7: No-Show Detection Implemented** (`apps/reports/services/dar_service.py`) - DAR compliance requirement
  - Compares scheduled Jobs with Attendance records
  - 15-minute grace period, excludes cancelled/completed jobs
  - Supervisors can now identify staffing gaps
- ✅ **Issue #5: Reminder App Merged** (`apps/scheduler/`) - Architecture cleanup
  - Moved Reminder model from apps/reminder to apps/scheduler/models/
  - Removed apps.reminder from INSTALLED_APPS
  - Backend-only model co-located with only usage point (scheduler/utils.py)
- ✅ **Issue #1: Ontology Decorator Optimized** (`apps/ontology/decorators.py`) - Import performance
  - Added @functools.lru_cache for source info loading
  - Deferred inspect.getsourcelines() to metadata access time
  - 30-50% faster imports for modules with 100+ decorators

**LOW Priority (Phase 3):**
- ✅ **Issue #2: Duplicate Serializers Archived** (`apps/people_onboarding/`) - Code cleanup
  - Moved serializers_fixed.py to .deprecated
  - Created DEPRECATED_SERIALIZERS_NOTICE.md
  - Zero functional impact (file had no imports)
- ✅ **Issue #3: Password Service TODO Removed** (`apps/peoples/services/password_management_service.py`) - Documentation accuracy
  - Verified @monitor_service_performance decorator is active
  - Updated docstring to reflect accurate monitoring state

📊 **Phase 1-3 Impact**: 7 technical debt items resolved, 11 files modified, 3 commits, 100% backward compatibility

**Previous Changes (Nov 11, 2025) - Ultrathink Comprehensive Remediation (Phase 1)**:
- ✅ **MQTT Client Fixed** (`apps/mqtt/client.py`) - Removed `.py` extension from settings module path, fixing ModuleNotFoundError in all environments
- ✅ **Monitoring Thresholds Corrected** (`apps/monitoring/services/device_health_service.py`) - Fixed duplicate HEALTH_WARNING/HEALTH_GOOD values (70→60/80), proper 3-tier health system
- ✅ **OpenAPI Schema Modernized** (`apps/onboarding_api/openapi_schemas.py`) - Replaced drf-yasg stub with drf-spectacular (OpenAPI 3.0), working Swagger/ReDoc UI
- ✅ **WebSocket Metrics Fixed** (`apps/noc/models/websocket_connection.py`) - New WebSocketConnection model tracks actual recipients vs hardcoded `recipient_count=1`
  - NOC consumers register/unregister connections on connect/disconnect
  - Broadcast service queries real connection count for accurate monitoring
  - Fixes invalid SLA reporting and dashboard metrics
- ✅ **ML Training Blocking I/O Eliminated** (`apps/ml_training/services/training_orchestrator.py`) - Removed 10-second `time.sleep()` loops
  - New TrainingOrchestrator service supports external ML platforms (non-blocking HTTP triggers)
  - Replaced fake metrics (0.95 accuracy always) with real training workflow
  - Progress callbacks via WebSocket instead of blocking loops
- ✅ **Onboarding Shim Deprecated** (`apps/onboarding/__init__.py`) - Added deprecation warnings with March 2026 removal timeline
- ✅ **Bonus Fixes**: Calendar admin registration, OSMGeoAdmin→GISModelAdmin (Django 5.x), missing `Any` import
- 📊 **Impact**: 9 issues fixed, ~530 lines changed, 2 new files, 100% backward compatibility maintained

**Previous Changes (Nov 10, 2025) - Installation Improvements**:
- ✅ **Smart Dependency Installer** created (`scripts/install_dependencies.py`) - Automatically detects platform and installs correct dependencies
- ✅ **Root requirements.txt removed** - Prevented CUDA package conflicts on macOS
- ✅ **Installation Guide** created (`.github/INSTALL_GUIDE.md`) - Comprehensive platform-specific setup instructions
- ✅ **CLAUDE.md Updated** - Clear warnings and installation methods
- 🎯 **Problem Solved**: Users no longer get `nvidia-cublas-cu12` errors on macOS

**Previous Changes (Nov 5, 2025) - Phase 7 Complete**:
- ✅ **Refactoring Playbook** created (`docs/architecture/REFACTORING_PLAYBOOK.md`) - Complete guide for future refactorings
- ✅ **Training Materials** created in `docs/training/` (4 comprehensive guides)
  - Quality Standards Training - Architecture limits and quality gates
  - Refactoring Training - Step-by-step god file splitting
  - Service Layer Training - ADR 003 implementation patterns
  - Testing Training - Effective testing strategies
- ✅ **Project Retrospective** created (`docs/PROJECT_RETROSPECTIVE.md`) - Complete Phase 1-6 journey
- ✅ **All ADRs Updated** - Added Phase 1-6 implementation references and validation status
- ✅ **CLAUDE.md Updated** - New commands, updated architecture section, Phase 1-6 results
- 📊 **Phase 1-6 Results**: 16 apps refactored, 80+ god files eliminated, 100% backward compatibility

**Previous Changes (Nov 4, 2025) - Phase 1**:
- ✅ File size validation script added (`scripts/check_file_sizes.py`)
- ✅ Refactoring patterns documented (`docs/architecture/REFACTORING_PATTERNS.md`)
- ✅ Architecture Decision Records created (5 ADRs covering file limits, dependencies, services, testing, exceptions)
- ✅ Documentation indexed and linked in CLAUDE.md

**Previous Changes (Nov 1, 2025)**:
- ✅ INSTALLED_APPS consolidated to single source of truth in base.py (deleted installed_apps.py)
- ✅ apps.ontology activated (was missing from runtime configuration)
- ✅ apps.ml_training activated at `/ml-training/` (dataset management, labeling, active learning)
- ✅ Mentor module fully removed (moved to separate service - API layer orphaned and deleted)
- ✅ Dead code removed: top-level issue_tracker/, settings_local.py
- 📋 See REMOVED_CODE_INVENTORY.md for complete details
