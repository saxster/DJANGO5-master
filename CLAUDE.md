# CLAUDE.md

> **Context**: Enterprise facility management platform (Django 5.2.1) with multi-tenant architecture, GraphQL/REST APIs, PostgreSQL task queue, and advanced security middleware.

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [⛔ Critical Rules](#-critical-rules-read-first)
- [Architecture Overview](#architecture-overview)
- [Development Workflows](#development-workflows)
- [Domain-Specific Systems](#domain-specific-systems)
- [Configuration Reference](#configuration-reference)
- [Testing & Quality](#testing--quality)

---

## Quick Start

### Most Common Commands

```bash
## Development server
python manage.py runserver                              # HTTP only
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application  # With WebSockets

## Testing
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v
python -m pytest -m unit                                # Unit tests only
./run_working_tests.sh                                  # Pre-configured subset

## Celery workers
./scripts/celery_workers.sh start                       # All optimized workers
./scripts/celery_workers.sh monitor                     # Real-time dashboard

## Database
python manage.py makemigrations && python manage.py migrate
python manage.py init_intelliwiz default                # Initialize with defaults

## Code quality validation
python scripts/validate_code_quality.py --verbose       # Full validation
python manage.py validate_graphql_config                # GraphQL settings check
```

### Emergency Commands

```bash
## Schedule health
python manage.py validate_schedules --verbose
python manage.py validate_schedules --fix --dry-run

## Task idempotency
python scripts/migrate_to_idempotent_tasks.py --analyze

## Security scorecard (daily at 6 AM automatic)
python manage.py shell
>>> from background_tasks.non_negotiables_tasks import evaluate_non_negotiables
>>> evaluate_non_negotiables.delay()
```

---

## ⛔ Critical Rules (READ FIRST)

### 🔥 Zero-Tolerance Security Violations

**Before ANY code changes, read `.claude/rules.md` - these patterns are FORBIDDEN:**

| Violation | Why Forbidden | Required Pattern |
|-----------|---------------|------------------|
| GraphQL SQL injection bypass | Middleware skips GraphQL endpoints | Use `GRAPHQL_PATHS` from centralized config |
| `except Exception:` | Hides real errors, impossible to debug | Use specific exceptions from `apps/core/exceptions/patterns.py` |
| Custom encryption | Unaudited crypto = vulnerabilities | Require security team sign-off |
| `@csrf_exempt` | Disables CSRF protection | Document alternative protection mechanism |
| Debug info in responses | Exposes internal architecture | Sanitize all error responses |
| File upload without validation | Path traversal, injection attacks | Use `perform_secure_uploadattachment` |
| Missing network timeouts | Workers hang indefinitely | `requests.get(url, timeout=(5, 15))` |
| Secrets without validation | Runtime failures in production | Validate on settings load |

### 📐 Architecture Limits (MANDATORY)

**File size limits prevent god files and maintainability issues:**

- Settings files: **< 200 lines** (split by environment)
- Model classes: **< 150 lines** (single responsibility)
- View methods: **< 30 lines** (delegate to services)
- Form classes: **< 100 lines** (focused validation)
- Utility functions: **< 50 lines** (atomic, testable)

#### Violation = PR rejection by automated checks

### 🛡️ Exception Handling Standards

```python
# ✅ CORRECT: Specific exception types
from apps/core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

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

**Migration tool available**: `python scripts/migrate_exception_handling.py --analyze`

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

**Reference**: `docs/DATETIME_FIELD_STANDARDS.md`, `DATETIME_REFACTORING_COMPLETE.md`

### 📊 GraphQL Security (Centralized Configuration)

**⚠️ Single Source of Truth**: `intelliwiz_config/settings/security/graphql.py`

```bash
# Validate configuration
python manage.py validate_graphql_config --report

# DO NOT define GraphQL settings in:
# ❌ base.py (import only)
# ❌ development.py (overrides only)
# ❌ Any other file
```

**Key protections**:

- Query depth limit: 10 (dev) / 8 (prod)
- Complexity limit: 2000 (dev) / 800 (prod)
- Rate limit: 1000/5min (dev) / 50/5min (prod)
- Introspection: Enabled (dev) / **DISABLED** (prod)

**Reference**: `docs/configuration/graphql-settings-guide.md`

### 📋 Pre-Code-Change Checklist

**Claude Code MUST complete before ANY modifications:**

1. ✅ Read `.claude/rules.md`
2. ✅ Identify applicable rules for planned changes
3. ✅ Validate proposed code follows required patterns
4. ✅ Reject implementations that violate any rule

**Automated enforcement**: Pre-commit hooks, CI/CD pipeline, static analysis

---

## Architecture Overview

### System Profile

**Enterprise facility management platform** for multi-tenant security guarding, facilities, and asset management.

- **Framework**: Django 5.2.1 + PostgreSQL 14.2 with PostGIS
- **APIs**: GraphQL (primary) at `/api/graphql/`, REST at `/api/v1/`
- **Task Queue**: PostgreSQL-native (replaced Celery dependency for sessions)
- **Authentication**: Custom user model (`peoples.People`) with multi-model architecture
- **Multi-tenancy**: Tenant-aware models with database routing

### Core Business Domains

| Domain | Primary Apps | Purpose |
|--------|-------------|---------|
| **Operations** | `activity`, `work_order_management`, `schedhuler` | Task management, PPM, scheduling |
| **Assets** | `inventory`, `monitoring` | Asset tracking, maintenance |
| **People** | `peoples`, `attendance` | Authentication, attendance, expenses |
| **Help Desk** | `y_helpdesk` | Ticketing, escalations, SLAs |
| **Reports** | `reports` | Analytics, scheduled reports |
| **Security** | `noc`, `face_recognition` | AI monitoring, biometrics |

### URL Architecture (Domain-Driven)

**Optimized structure** in `intelliwiz_config/urls_optimized.py`:

```text
/operations/     # Tasks, tours, work orders
/assets/         # Inventory, maintenance
/people/         # Directory, attendance
/help-desk/      # Tickets, escalations
/reports/        # Analytics
/admin/          # Administration
```

Legacy URLs redirect to new structure for backward compatibility.

### Refactored Architecture (Sep 2025)

**God file elimination** - monolithic files split into focused modules:

#### Reports Views (5 modules, 2,070 lines)

```python
# apps/reports/views/
base.py                   # Shared base classes, forms
template_views.py         # Template management
configuration_views.py    # Report configuration
generation_views.py       # PDF/Excel generation
__init__.py              # Backward compatibility

# Import patterns
from apps.reports.views import DownloadReports  # Still works (legacy)
from apps.reports.views.generation_views import DownloadReports  # Recommended
```

#### Onboarding Admin (9 modules, 1,796 lines)

```python
# apps/onboarding/admin/
base.py                   # Shared resources
typeassist_admin.py       # Data import/export
business_unit_admin.py    # Business unit management
shift_admin.py            # Shift configuration
conversation_admin.py     # AI conversational onboarding
changeset_admin.py        # AI changeset rollback
knowledge_admin.py        # Knowledge base with vectors
__init__.py              # Backward compatibility
```

#### Service Layer (6 modules, 31 functions)

```python
# apps/service/services/
database_service.py       # 10 DB operations
file_service.py          # 4 file operations (SECURE - Rule #14 compliant)
geospatial_service.py    # 3 geospatial operations
job_service.py           # 6 job/tour operations (RACE-PROTECTED)
crisis_service.py        # 3 crisis management
graphql_service.py       # 4 GraphQL mutations

# Security-critical functions
from apps.service.services.file_service import perform_secure_uploadattachment  # Path traversal protected
from apps.service.services.job_service import update_adhoc_record  # Distributed lock protected
```

**Reference**: `GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md`

### Custom User Model Architecture

**Split model design** (Sep 2025 - reducing complexity):

```python
# peoples.People (178 lines) - Core authentication
- Authentication: loginid, password, is_staff, is_superuser
- Identity: uuid, peoplecode, peoplename
- Security: email, mobno (encrypted), isadmin, isverified
- Capabilities: JSON field for AI/system capabilities

# peoples.PeopleProfile (117 lines) - Personal info
- Profile image, gender, dates (birth, join, report)
- Legacy capabilities JSON (people_extras)

# peoples.PeopleOrganizational (177 lines) - Organization
- Location, department, designation, peopletype
- Client, business unit, reporting manager

# Backward compatibility via PeopleCompatibilityMixin
user.profile_image  # Works via property accessor
People.objects.with_full_details()  # Optimized query helper
```

### Security Architecture

**Multi-layer middleware stack**:

1. `SQLInjectionProtectionMiddleware` - SQL injection prevention
2. `XSSProtectionMiddleware` - XSS protection
3. `CorrelationIDMiddleware` - Request tracking
4. `GraphQLComplexityValidationMiddleware` - DoS prevention (depth/complexity limits)
5. `GraphQLRateLimitingMiddleware` - GraphQL rate limiting
6. `GraphQLCSRFProtectionMiddleware` - CSRF for mutations
7. Content Security Policy (CSP) with violation reporting
8. API authentication with HMAC signing support

**GraphQL DoS Protection**:

- Max query depth: 10 (dev) / 8 (prod)
- Max complexity: 2000 (dev) / 800 (prod)
- Validation caching: 5min (<10ms overhead)
- Blocks: Deep nesting, complexity bombs, alias overload

---

## Development Workflows

### Background Processing Architecture

**Enterprise-grade Celery** with specialized queues:

| Queue | Priority | SLA | Use Cases |
|-------|----------|-----|-----------|
| `critical` | 10 | <2s | Crisis intervention, security alerts |
| `high_priority` | 8 | <3s | User-facing ops, biometrics |
| `email` | 7 | <5s | Email processing |
| `reports` | 6 | <60s | Analytics, ML processing |
| `external_api` | 5 | <10s | MQTT, third-party integrations |
| `maintenance` | 3 | <300s | Cleanup, cache warming |

**Configuration**:

- Worker concurrency: 8 workers, 4x prefetch
- Retry policy: Exponential backoff with jitter (3 max)
- Monitoring: `TaskMetrics` with real-time tracking
- Circuit breakers: Automatic failure protection

### Universal Idempotency Framework (Oct 2025)

**Prevents duplicate task execution** across all background operations:

```python
# Core components
from apps.core.tasks.idempotency_service import UniversalIdempotencyService
from apps.core.tasks.base import IdempotentTask
from apps.core.tasks.decorators import with_idempotency

# Example: Idempotent task class
class AutoCloseJobsTask(IdempotentTask):
    name = 'auto_close_jobs'
    idempotency_scope = 'global'
    idempotency_ttl = SECONDS_IN_HOUR * 4  # 4 hours

    def run(self):
        # Automatic duplicate prevention
        pass

# Example: Decorator for existing tasks
@with_idempotency(scope='user', ttl=SECONDS_IN_HOUR * 2)
@app.task
def send_reminder_email(user_id):
    pass
```

**Performance**:

- Redis check: <2ms (25x faster than PostgreSQL)
- PostgreSQL fallback: <7ms
- Duplicate detection: <1% in steady state
- Total overhead: <7% per task

**Task Categories** (TTL by priority):

- Critical: 4h (`auto_close_jobs`, `ticket_escalation`)
- High Priority: 2h (`create_job`, `send_reminder_email`)
- Reports: 24h (`create_scheduled_reports`)
- Mutations: 6h (`process_graphql_mutation_async`)
- Maintenance: 12h (`cleanup_reports_which_are_12hrs_old`)

**Schedule coordination**:

```bash
# Validate schedules
python manage.py validate_schedules --verbose
python manage.py validate_schedules --check-duplicates
python manage.py validate_schedules --fix --dry-run

# Analyze for migration
python scripts/migrate_to_idempotent_tasks.py --analyze
python scripts/migrate_to_idempotent_tasks.py --task auto_close_jobs
```

**Monitoring**:

- Dashboard: `/admin/tasks/dashboard`
- Idempotency analysis: `/admin/tasks/idempotency-analysis`
- Schedule conflicts: `/admin/tasks/schedule-conflicts`

**Reference**:

- Framework: `apps/core/tasks/idempotency_service.py` (430 lines)
- Base class: `apps/core/tasks/base.py` (185 lines)
- Key generation: `background_tasks/task_keys.py` (320 lines)

### Race Condition Testing

**Critical for data integrity**:

```bash
# Run all race condition tests
python -m pytest -k "race" -v

# Specific test suites
python -m pytest apps/core/tests/test_background_task_race_conditions.py -v
python -m pytest apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py -v
python -m pytest apps/core/tests/test_atomic_json_field_updates.py -v

# Penetration testing
python comprehensive_race_condition_penetration_test.py --scenario all
```

### Database Management

```bash
# Migrations
python manage.py makemigrations
python manage.py migrate

# Initialize with defaults
python manage.py init_intelliwiz default

# Database shell with SQL logging
python manage.py shell_plus --print-sql

# Model visualization (requires django-extensions)
python manage.py graph_models --all-applications --group-models -o models.png
```

### Static Files & Assets

```bash
# Production collection
python manage.py collectstatic --no-input

# Development: Served automatically by runserver
# Production: WhiteNoise (dev) / Nginx (prod)
```

### Type-Safe API Contracts (Oct 2025)

**Comprehensive data contracts for Kotlin/Swift mobile codegen** with Pydantic validation.

#### Quick Access

```bash
# OpenAPI schema (REST v1/v2)
curl http://localhost:8000/api/schema/swagger.json > openapi.json

# WebSocket message schema (JSON Schema)
cat docs/api-contracts/websocket-messages.json

# Interactive API docs
open http://localhost:8000/api/schema/swagger/
open http://localhost:8000/api/schema/redoc/

# Schema metadata
curl http://localhost:8000/api/schema/metadata/
```

#### Architecture

**Three API surfaces with complete type safety**:

| API Type | Validation | Codegen | Example |
|----------|-----------|---------|---------|
| **REST v1** | DRF Serializers | OpenAPI Generator | `TaskSyncSerializer` |
| **REST v2** | Pydantic + DRF | OpenAPI Generator | `VoiceSyncRequestSerializer` |
| **GraphQL** | Pydantic Queries | Apollo Kotlin | `JobQueries` uses Pydantic |
| **WebSocket** | Pydantic Messages | JSON Schema | `SyncStartMessage` |

#### REST v2 Pattern (Type-Safe)

```python
# Pydantic model for validation
from apps.core.validation.pydantic_base import BusinessLogicModel

class VoiceSyncDataModel(BusinessLogicModel):
    device_id: str = Field(..., min_length=5)
    voice_data: List[VoiceDataItem] = Field(..., max_items=100)

# DRF serializer with Pydantic integration
from apps.core.serializers.pydantic_integration import PydanticSerializerMixin

class VoiceSyncRequestSerializer(PydanticSerializerMixin, serializers.Serializer):
    pydantic_model = VoiceSyncDataModel  # ✅ Auto-validation
    full_validation = True

    device_id = serializers.CharField(...)  # For OpenAPI schema

# View with standardized responses
from apps.core.api_responses import create_success_response, create_error_response

class SyncVoiceView(APIView):
    def post(self, request):
        serializer = VoiceSyncRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(create_error_response([...]), 400)

        return Response(create_success_response(result))
```

#### WebSocket Pattern (Type-Safe)

```python
# Pydantic message models
from apps.api.websocket_messages import parse_websocket_message

async def receive(self, text_data):
    raw = json.loads(text_data)
    validated = parse_websocket_message(raw)  # ✅ Type-safe

    if isinstance(validated, SyncStartMessage):
        await self._handle_sync_start(validated)  # ✅ Type hints
```

#### Pydantic Domain Models

**Enhanced schemas for Kotlin codegen** (14 total):

```python
# apps/service/pydantic_schemas/
task_enhanced_schema.py          # TaskDetailSchema (30 fields)
asset_enhanced_schema.py         # AssetDetailSchema (25 fields)
ticket_enhanced_schema.py        # TicketDetailSchema (20 fields)
attendance_enhanced_schema.py    # AttendanceDetailSchema (10 fields)
location_enhanced_schema.py      # LocationDetailSchema (15 fields)
question_enhanced_schema.py      # QuestionDetailSchema (15 fields)
# ... original minimal schemas
```

**Usage**:

```python
from apps.service.pydantic_schemas import TaskDetailSchema

# Runtime validation
task_data = TaskDetailSchema(**request_data)  # ✅ Validates immediately

# Convert to Django model
task = Jobneed(**task_data.to_django_dict())

# Use in GraphQL
from apps.core.graphql.pydantic_validators import create_pydantic_input_type
TaskInputType = create_pydantic_input_type(TaskDetailSchema)
```

#### Standard Response Envelope

**ALL v2 endpoints use**:

```python
from apps.core.api_responses import APIResponse, APIError, create_success_response

# Success
return Response(create_success_response(
    data={'id': 123, 'name': 'Test'},
    execution_time_ms=25.5
))

# Error
return Response(create_error_response([
    APIError(field='device_id', message='Required', code='REQUIRED')
]), status=400)
```

**Kotlin mapping**:

```kotlin
data class APIResponse<T>(
    val success: Boolean,
    val data: T?,
    val errors: List<APIError>?,
    val meta: APIMeta
)
```

#### For Kotlin/Swift Teams

**Complete guide**: `docs/mobile/kotlin-codegen-guide.md`
**Migration guide**: `docs/mobile/MIGRATION_GUIDE_TYPE_SAFE_CONTRACTS.md`
**WebSocket contracts**: `docs/api-contracts/websocket-messages.json`
**Kotlin example**: `docs/api-contracts/WebSocketMessage.kt.example`

**Reference**: `DATA_CONTRACTS_COMPREHENSIVE_COMPLETE.md`

---

## Domain-Specific Systems

### Security & Facility AI Mentor (Oct 2025)

**Intelligent monitoring of 7 operational non-negotiables** with daily scorecards and auto-alerts.

#### The 7 Pillars

1. **Right Guard at Right Post** - Schedule coverage & attendance
2. **Supervise Relentlessly** - Tour completion & checkpoints
3. **24/7 Control Desk** - Alert acknowledgment SLAs
4. **Legal & Professional** - PF/ESIC/payroll compliance
5. **Support the Field** - Uniform/equipment tickets
6. **Record Everything** - Report delivery (daily/weekly/monthly)
7. **Respond to Emergencies** - Crisis escalation <2min

#### Quick Access

```bash
# Web UI
http://localhost:8000/helpbot/security_scorecard/

# API
curl http://localhost:8000/helpbot/api/v1/scorecard/ -H "Authorization: Token <token>"

# Programmatic
from apps.noc.security_intelligence.services import NonNegotiablesService
service = NonNegotiablesService()
scorecard = service.generate_scorecard(tenant, client)

# Manual evaluation (runs daily at 6 AM automatic)
from background_tasks.non_negotiables_tasks import evaluate_non_negotiables
evaluate_non_negotiables.delay()
```

#### Scoring Logic

- **GREEN**: All pillars ≥90% OR only AMBER pillars
- **AMBER**: Any pillar 70-89% OR minor violations
- **RED**: Any pillar <70% OR CRITICAL violations

#### Infrastructure (95% Reuse)

- `ScheduleCoordinator` - Schedule health scoring
- `TaskComplianceMonitor` - Tour compliance tracking
- `NOCAlertEvent` - Alert SLA monitoring
- `AlertCorrelationService` - Auto-alert creation
- `EscalationService` - On-call routing
- `Ticket` model - Field support and crisis tracking

**Reference**:

- Implementation: `SECURITY_FACILITY_MENTOR_PHASE2_COMPLETE.md`
- Operator guide: `NON_NEGOTIABLES_OPERATOR_GUIDE.md`
- Model: `apps/noc/security_intelligence/models/non_negotiables_scorecard.py`
- Service: `apps/noc/security_intelligence/services/non_negotiables_service.py` (775 lines)

### Stream Testbench (Real-Time Testing)

**Enterprise stream testing platform** with PII protection and AI-powered anomaly detection.

```bash
# Run Stream Testbench tests
python -m pytest apps/streamlab/tests/ apps/issue_tracker/tests/ -v
python run_stream_tests.py                              # Complete suite
python testing/stream_load_testing/spike_test.py        # Performance validation

# Start ASGI server (required for WebSockets)
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

**Core apps**:

- `streamlab` - Stream testing core with PII protection
- `issue_tracker` - AI-powered issue knowledge base

### Caching Strategy

```python
# Redis for general caching
CACHES['default'] = "redis://127.0.0.1:6379/1"

# Custom materialized view cache for Select2 dropdowns
CACHES['select2'] = MaterializedViewSelect2Cache
```

**Session optimization**:

- PostgreSQL sessions (not Redis)
- 20ms latency trade-off approved for architecture simplicity

---

## Configuration Reference

### Environment Files

```bash
# Development
.env.dev.secure            # Local development settings

# Production
.env.production            # Production secrets (not in repo)
```

### Settings Structure

**Centralized by concern**:

```text
intelliwiz_config/settings/
├── base.py               # Core Django settings (imports only)
├── development.py        # Dev overrides
├── production.py         # Production overrides
└── security/
    ├── graphql.py        # ⚠️ GraphQL settings (SINGLE SOURCE OF TRUTH)
    ├── csp.py            # Content Security Policy
    └── middleware.py     # Security middleware config
```

**Critical**:

- GraphQL settings ONLY in `security/graphql.py`
- Other files import or override (never define)
- Validation: `python manage.py validate_graphql_config`

### Database Configuration

- **Primary**: PostgreSQL 14.2+ with PostGIS extension
- **Routing**: `TenantDbRouter` for multi-tenant isolation
- **Sessions**: PostgreSQL (not Redis) - 20ms trade-off approved
- **Optimization**: Use `select_related()` and `prefetch_related()` for relationships

### Logging

```python
# Comprehensive file-based logging with rotation
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/intelliwiz.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    }
}
```

**⚠️ Never log**:

- Passwords or authentication tokens
- PII (Personal Identifiable Information)
- Credit card or payment data
- API keys or secrets

---

## Testing & Quality

### Test Execution

```bash
# Full test suite with coverage
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v

# Test categories
python -m pytest -m unit          # Unit tests
python -m pytest -m integration   # Integration tests
python -m pytest -m security      # Security tests

# Specific test suites
python -m pytest apps/peoples/tests/test_models/test_people_model_comprehensive.py -v
python -m pytest apps/core/tests/test_datetime_refactoring_comprehensive.py -v
python -m pytest apps/schedhuler/tests/test_schedule_uniqueness_comprehensive.py -v
```

### Code Quality Validation

```bash
# Comprehensive validation suite
python scripts/validate_code_quality.py --verbose
python scripts/validate_code_quality.py --report quality_report.md

# Validates:
# ✅ Wildcard imports (except Django settings pattern)
# ✅ Generic exception handling
# ✅ Network timeout parameters
# ✅ Code injection (eval/exec)
# ✅ Blocking I/O (time.sleep in request paths)
# ✅ sys.path manipulation
# ✅ Production print statements
```

### Exception Handling Migration

```bash
# Analyze generic exception patterns
python scripts/migrate_exception_handling.py --analyze

# Generate migration report
python scripts/migrate_exception_handling.py --report exception_migration_report.md

# Auto-fix high confidence issues (when ready)
python scripts/migrate_exception_handling.py --fix --confidence HIGH
```

**Current status (2025-09-30)**:

- ✅ Network timeouts: 100% compliant
- ✅ sys.path manipulation: 100% compliant
- ✅ Critical security: 8 eval/exec instances (down from 10)
- 🟡 Exception handling: 970 instances require migration (tool available)
- 🟡 Wildcard imports: 15 instances (documented exceptions)

### Pre-Commit Validation

**Multi-layer enforcement**:

1. Pre-commit hooks (`.githooks/pre-commit`)
2. CI/CD pipeline (`.github/workflows/`)
3. Static analysis (bandit, flake8, pylint)
4. Code review automation

**Setup**:

```bash
./scripts/setup-git-hooks.sh  # Install validation hooks
```

### Quality Metrics (Tracked & Enforced)

- Security scan pass rate: **100%** (zero tolerance)
- Rule compliance rate: **100%** (zero exceptions)
- Code review efficiency: **>60% improvement** (pre-validated)
- Critical issue prevention: **100%** (automated detection)

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

**ALL network calls MUST include timeout parameters**:

```python
# ✅ CORRECT: With timeout
response = requests.get(url, timeout=(5, 15))  # (connect, read) seconds
response = requests.post(webhook_url, json=data, timeout=(5, 30))

# ❌ INCORRECT: No timeout (can hang workers)
response = requests.get(url)
```

**Timeout guidelines**:

- API/metadata: `(5, 15)` - 5s connect, 15s read
- File downloads: `(5, 30)` - 5s connect, 30s read
- Long operations: `(5, 60)` - 5s connect, 60s read

### Blocking I/O Prevention

**Never use `time.sleep()` in request paths**:

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

## Troubleshooting

### Pre-Commit Hooks Failing

1. Review specific rule violation in error message
2. Check `.claude/rules.md` for correct pattern
3. Fix violation before attempting commit
4. Contact team lead if rule clarification needed

### CI/CD Pipeline Failing

1. Check quality report in PR comments
2. Fix all identified violations locally
3. Re-run tests to ensure compliance
4. Request code review only after all checks pass

### GraphQL Configuration Issues

```bash
# Settings not loading?
python manage.py shell
>>> from django.conf import settings
>>> print(settings.GRAPHQL_PATHS)

# Validation failing?
python manage.py validate_graphql_config --report

# Pre-commit blocking?
python manage.py validate_graphql_config --check-duplicates
```

### Idempotency Issues

```bash
# Duplicate tasks still running?
python scripts/migrate_to_idempotent_tasks.py --analyze
python manage.py validate_schedules --check-duplicates

# Check idempotency logs
# Dashboard: /admin/tasks/idempotency-analysis
```

---

## Additional Resources

### Documentation

- **GraphQL Configuration**: `docs/configuration/graphql-settings-guide.md`
- **GraphQL Security**: `docs/security/graphql-complexity-validation-guide.md`
- **DateTime Standards**: `docs/DATETIME_FIELD_STANDARDS.md`
- **DateTime Refactoring**: `DATETIME_REFACTORING_COMPLETE.md`
- **God File Refactoring**: `GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md`
- **Security Mentor**: `SECURITY_FACILITY_MENTOR_PHASE2_COMPLETE.md`
- **Operator Guide**: `NON_NEGOTIABLES_OPERATOR_GUIDE.md`
- **Team Setup**: `TEAM_SETUP.md`

### Key Files

- **Rules**: `.claude/rules.md` (mandatory reading)
- **Settings**: `intelliwiz_config/settings/`
- **URLs**: `intelliwiz_config/urls_optimized.py`
- **User model**: `apps/peoples/models.py`
- **Security**: `apps/core/models.py`, `apps/core/middleware/`
- **Multi-tenancy**: `apps/tenants/models.py`
- **Test config**: `pytest.ini`

### Support

- Security issues: Contact security team immediately
- Architecture questions: Review this document and domain guides
- Quality violations: Run validation tools before asking
- New features: Follow architecture limits and refactoring patterns

---

**Last Updated**: October 2025
**Maintainer**: Development Team
**Review Cycle**: Quarterly or on major architecture changes
