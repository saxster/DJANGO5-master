# Architecture Overview

**System design, patterns, and architectural decisions**

→ **Quick start:** See [CLAUDE.md](../CLAUDE.md) for setup and daily commands

---

## Table of Contents

- [System Profile](#system-profile)
- [Business Domains](#business-domains)
- [Multi-Tenant Architecture](#multi-tenant-architecture)
- [API Architecture](#api-architecture)
- [Data Architecture](#data-architecture)
- [Security Architecture](#security-architecture)
- [URL Design](#url-design)
- [Refactored Architecture](#refactored-architecture)
- [Design Decisions](#design-decisions)

---

## System Profile

**Enterprise facility management platform** for multi-tenant security guarding, facilities, and asset management.

### Technology Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | Django | 5.2.1 | Web framework |
| **Language** | Python | 3.11.9 | Runtime (recommended) |
| **Database** | PostgreSQL + PostGIS | 14.2+ | Relational + spatial data |
| **Task Queue** | Celery | Latest | Background processing |
| **Cache** | Redis | Latest | Caching + sessions |
| **APIs** | REST (DRF) | Latest | REST endpoints (legacy query layer retired Oct 2025) |

### Deployment Model

- **Development:** Single server, SQLite/PostgreSQL, local Redis
- **Staging:** Multi-server, PostgreSQL RDS, ElastiCache Redis
- **Production:** Kubernetes cluster, managed PostgreSQL, Redis Enterprise

### Scalability Approach

- **Horizontal:** Multiple Celery workers, load-balanced web servers
- **Vertical:** Database read replicas, Redis clustering
- **Async:** Celery queues for background processing
- **Caching:** Multi-layer (Redis, PostgreSQL materialized views)

---

## Business Domains

### Operations

**Apps:** `activity`, `work_order_management`, `scheduler`

**Purpose:**
- Task management (jobs, tours, checkpoints)
- Preventive/Planned Maintenance (PPM)
- Schedule management (shifts, rosters)
- Work order lifecycle

**Key Models:**
- `Jobneed` (tasks/jobs)
- `Tour` (patrol routes)
- `Schedule` (shift schedules)
- `WorkOrder` (maintenance requests)

### Assets

**Apps:** `inventory`, `monitoring`

**Purpose:**
- Asset tracking (equipment, vehicles)
- Maintenance history
- Real-time monitoring
- Lifecycle management

**Key Models:**
- `Asset` (equipment registry)
- `Maintenance` (service records)
- `Location` (physical locations)

### People

**Apps:** `peoples`, `attendance`

**Purpose:**
- Authentication and authorization
- Attendance tracking (GPS-verified)
- Expense management
- User profiles

**Key Models:**
- `People` (core authentication)
- `PeopleProfile` (personal info)
- `PeopleOrganizational` (company data)
- `Attendance` (check-in/out)

### Help Desk

**Apps:** `y_helpdesk`

**Purpose:**
- Ticketing system
- Escalation workflows
- SLA management
- Issue tracking

**Key Models:**
- `Ticket` (support tickets)
- `TicketCategory` (classification)
- `Escalation` (SLA tracking)

### Reports

**Apps:** `reports`

**Purpose:**
- Analytics and dashboards
- Scheduled report generation
- Data export (CSV, Excel, PDF)
- Business intelligence

**Key Models:**
- `ReportTemplate` (report definitions)
- `ScheduledReport` (automated reports)
- `ReportExecution` (history)

### Security

**Apps:** `noc`, `face_recognition`

**Purpose:**
- AI-powered monitoring (Network Operations Center)
- Facial recognition biometrics
- Security scorecard (7 non-negotiables)
- Anomaly detection

**Key Models:**
- `NOCAlert` (security alerts)
- `FaceRecognition` (biometric data)
- `NonNegotiablesScorecard` (compliance)

---

## Multi-Tenant Architecture

### Tenant Isolation Strategy

**Shared Database, Filtered Queries:**
- Single PostgreSQL database for all tenants
- Every model has `tenant` or `client` foreign key
- Middleware injects tenant filter on all queries
- Row-level security at ORM level

### Database Routing

**`TenantDbRouter`** in `intelliwiz_config/routers.py`:

```python
class TenantDbRouter:
    """Routes database operations based on tenant context"""

    def db_for_read(self, model, **hints):
        """Direct reads to appropriate database"""
        if hasattr(model, 'tenant'):
            return 'default'  # Tenant-aware model
        return None  # Let Django decide

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Control migrations per database"""
        return db == 'default'
```

### Security Boundaries

**Tenant separation enforced at:**
1. **Middleware layer:** `TenantMiddleware` sets `request.tenant`
2. **ORM layer:** `TenantManager` filters all queries
3. **API layer:** Serializers validate tenant ownership
4. **Celery layer:** Tasks receive `tenant_id` parameter

**Critical:** Never use `.objects.all()` without tenant filter!

```python
# ❌ WRONG: Leaks data across tenants
users = People.objects.all()

# ✅ CORRECT: Tenant-filtered
users = People.objects.filter(tenant=request.tenant)

# ✅ CORRECT: Use manager
users = People.objects.tenant_filtered(request.tenant)
```

---

## API Architecture

### REST Design (Oct 2025)

**Legacy query layer retired October 29, 2025.** All APIs now REST-based.

**Endpoints:**
- **v1:** `/api/v1/` - Legacy DRF APIs
- **v2:** `/api/v2/` - Type-safe Pydantic APIs

### API v2: Type-Safe Contracts

**Pattern:** Pydantic validation → DRF serializer → Standard envelope

```python
# Pydantic model for validation
from apps.core.validation.pydantic_base import BusinessLogicModel
from pydantic import Field

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
            return Response(create_error_response(serializer.errors), 400)

        result = process_voice_sync(serializer.validated_data)
        return Response(create_success_response(result))
```

### Standard Response Envelope

**All v2 endpoints use:**

```python
{
  "success": true,
  "data": { ... },
  "errors": null,
  "meta": {
    "timestamp": "2025-10-29T10:30:00Z",
    "execution_time_ms": 45.2
  }
}
```

### OpenAPI Schema

**Interactive documentation:**
- **Swagger UI:** `http://localhost:8000/api/schema/swagger/`
- **ReDoc:** `http://localhost:8000/api/schema/redoc/`
- **JSON Schema:** `http://localhost:8000/api/schema/swagger.json`

**Codegen for mobile:**
```bash
# Generate Kotlin models
openapi-generator generate \
  -i http://localhost:8000/api/schema/swagger.json \
  -g kotlin \
  -o mobile/android/generated
```

### WebSocket Messages

**Type-safe Pydantic models** for real-time communication:

```python
from apps.api.websocket_messages import parse_websocket_message, SyncStartMessage

async def receive(self, text_data):
    raw = json.loads(text_data)
    validated = parse_websocket_message(raw)  # ✅ Type-safe

    if isinstance(validated, SyncStartMessage):
        await self._handle_sync_start(validated)
```

---

## Data Architecture

### Custom User Model (Split Design)

**Sep 2025 refactoring** to reduce model complexity:

#### People (Core Authentication) - 178 lines

```python
# apps/peoples/models/user_model.py
class People(AbstractBaseUser, PermissionsMixin):
    """Core authentication model"""

    # Authentication
    loginid = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Identity
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    peoplecode = models.CharField(max_length=50, unique=True)
    peoplename = models.CharField(max_length=255)

    # Security
    email = models.EmailField(unique=True)
    mobno = EncryptedCharField(max_length=20)  # Encrypted
    isadmin = models.BooleanField(default=False)
    isverified = models.BooleanField(default=False)

    # Capabilities
    capabilities = models.JSONField(default=dict)  # AI/system capabilities

    USERNAME_FIELD = 'loginid'
    objects = PeopleManager()
```

#### PeopleProfile (Personal Info) - 117 lines

```python
# apps/peoples/models/profile_model.py
class PeopleProfile(models.Model):
    """Personal information"""

    people = models.OneToOneField(People, on_delete=models.CASCADE, related_name='profile')
    profile_image = models.ImageField(upload_to='profiles/')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    date_of_reporting = models.DateField(null=True, blank=True)
    people_extras = models.JSONField(default=dict)  # Legacy capabilities
```

#### PeopleOrganizational (Company Data) - 177 lines

```python
# apps/peoples/models/organizational_model.py
class PeopleOrganizational(models.Model):
    """Organizational relationships"""

    people = models.OneToOneField(People, on_delete=models.CASCADE, related_name='organizational')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True)
    peopletype = models.ForeignKey(PeopleType, on_delete=models.SET_NULL, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True)
    reporting_manager = models.ForeignKey(People, on_delete=models.SET_NULL, null=True, related_name='subordinates')
```

### Backward Compatibility

**`PeopleCompatibilityMixin`** provides property accessors:

```python
# Works via property accessor
user = People.objects.get(loginid='john')
user.profile_image  # → user.profile.profile_image
user.department     # → user.organizational.department

# Optimized query helper
users = People.objects.with_full_details()  # Includes profile + org (single query)
```

### Query Optimization Patterns

```python
# ✅ GOOD: select_related for foreign keys
users = People.objects.select_related('profile', 'organizational').all()

# ✅ GOOD: prefetch_related for many-to-many
tasks = Jobneed.objects.prefetch_related('assigned_people').all()

# ✅ GOOD: Custom manager method
users = People.objects.with_full_details()  # Optimized joins

# ❌ BAD: N+1 query problem
for user in People.objects.all():
    print(user.profile.gender)  # Extra query per user!
```

---

## Security Architecture

### Multi-Layer Middleware Stack

**Ordered by execution priority:**

1. **`SQLInjectionProtectionMiddleware`**
   - SQL injection prevention
   - Input sanitization
   - Query parameter validation

2. **`XSSProtectionMiddleware`**
   - XSS protection headers
   - Content-Type enforcement
   - Output encoding

3. **`CorrelationIDMiddleware`**
   - Request tracking across services
   - Log correlation
   - Distributed tracing

4. **Content Security Policy (CSP)**
   - CSP headers with strict policies
   - Violation reporting to `/core/csp-report/`
   - Nonce-based script execution

5. **API Authentication**
   - JWT token validation
   - HMAC signing support
   - Rate limiting per user

### Authentication Flow

```
1. User login → POST /api/v1/auth/login
2. Validate credentials (password hashing: Argon2)
3. Generate JWT token (RS256 signing)
4. Return token + refresh token
5. Client includes token in headers: Authorization: Bearer <token>
6. Middleware validates token on each request
7. request.user populated for authorized requests
```

### Authorization Patterns

**Row-level security:**

```python
# Tenant-based
user.tenant → Filters all queries

# Role-based
user.is_staff → Access to /admin/
user.capabilities → Fine-grained permissions (JSON field)

# Object-level
def has_permission(user, obj):
    return obj.created_by == user or user.is_admin
```

### Input Validation

**Pydantic + DRF double validation:**

```python
# Layer 1: Pydantic (business logic)
class TaskDataModel(BusinessLogicModel):
    title: str = Field(..., min_length=3, max_length=255)
    priority: int = Field(..., ge=1, le=10)

# Layer 2: DRF (API contract)
class TaskSerializer(PydanticSerializerMixin, serializers.Serializer):
    pydantic_model = TaskDataModel
    title = serializers.CharField(max_length=255)

# Both layers validate - belt and suspenders approach
```

---

## URL Design

### Domain-Driven Structure

**Optimized in** `intelliwiz_config/urls_optimized.py`:

```python
urlpatterns = [
    path('operations/', include('apps.activity.urls')),      # Tasks, tours, work orders
    path('assets/', include('apps.inventory.urls')),         # Inventory, maintenance
    path('people/', include('apps.peoples.urls')),           # Directory, attendance
    path('help-desk/', include('apps.y_helpdesk.urls')),     # Tickets, escalations
    path('reports/', include('apps.reports.urls')),          # Analytics
    path('admin/', admin.site.urls),                         # Administration
]
```

**Benefits:**
- Clear domain separation
- Predictable URL patterns
- Easy to understand and navigate
- RESTful resource naming

### Legacy URL Redirects

**Backward compatibility** for mobile apps:

```python
# Old pattern: /activity/jobs/
# New pattern: /operations/jobs/
# Redirect configured for 6-month deprecation period
```

---

## Refactored Architecture

### God File Elimination (Sep 2025)

**Problem:** Monolithic files violated architecture limits (150 lines models, 200 lines settings)

**Solution:** Split into focused modules with single responsibility

#### Reports Views: 2,070 lines → 5 modules

```python
# apps/reports/views/
base.py                   # Shared base classes, forms (50 lines)
template_views.py         # Template management (200 lines)
configuration_views.py    # Report configuration (180 lines)
export_views.py           # PDF/CSV exports (260 lines)
schedule_views.py         # Scheduling + design preview (220 lines)
pdf_views.py              # WeasyPrint + Pandoc helpers (280 lines)
frappe_integration_views.py  # ERP integrations (210 lines)
__init__.py              # Backward compatibility (20 lines)
```

**Import patterns:**
```python
# Legacy (still works)
from apps.reports.views import DownloadReports

# Recommended
from apps.reports.views.export_views import DownloadReports
```

#### Onboarding Admin: 1,796 lines → 9 modules

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

#### Service Layer: 31 functions → 6 modules

```python
# apps/service/services/
database_service.py       # 10 DB operations
file_service.py          # 4 file operations (SECURE - Rule #14 compliant)
geospatial_service.py    # 3 geospatial operations
job_service.py           # 6 job/tour operations (RACE-PROTECTED)
crisis_service.py        # 3 crisis management
```

**Security-critical functions:**
```python
# Path traversal protected
from apps.service.services.file_service import perform_secure_uploadattachment

# Race condition protected
from apps.service.services.job_service import update_adhoc_record
```

### Architectural Limits Enforced

| Component | Max Size | Reason | Enforcement |
|-----------|----------|--------|-------------|
| **Settings files** | 200 lines | Split by concern | Lint check |
| **Model classes** | 150 lines | Single responsibility | Lint check |
| **View methods** | 30 lines | Delegate to services | Complexity check |
| **Form classes** | 100 lines | Focused validation | Lint check |
| **Utility functions** | 50 lines | Atomic operations | Complexity check |

→ **Complete history:** `docs/archive/refactorings/REFACTORING_ARCHIVES.md`

---

## Design Decisions

### Why REST over the Legacy Query Layer (Oct 29, 2025)

**Decision:** Migrate from the legacy query layer to REST APIs

**Rationale:**
- **Simpler security model:** Standard DRF throttling, permissions
- **Better tooling:** OpenAPI/Swagger generation, mobile codegen
- **Easier debugging:** Request/response in browser dev tools
- **Lower token cost:** Smaller schema files for AI context
- **Standard patterns:** More familiar to team

**Trade-offs:**
- Lost: Flexible queries, single endpoint
- Gained: Simplicity, better caching, smaller surface area

### Why PostgreSQL Sessions (Oct 2025)

**Decision:** Use PostgreSQL for sessions (not Redis)

**Rationale:**
- **Architectural simplicity:** One less Redis database
- **20ms latency acceptable:** Trade-off for simpler stack
- **Reduced dependencies:** Fewer moving parts
- **Easier debugging:** SQL queries visible

**Trade-offs:**
- Lost: <5ms Redis speed
- Gained: Simpler architecture, easier maintenance

### Why Split User Model (Sep 2025)

**Decision:** Split `People` (450 lines) → 3 models

**Rationale:**
- **Architecture limits:** Models must be <150 lines
- **Single responsibility:** Auth separate from profile/org
- **Query optimization:** Only load what's needed
- **Easier testing:** Mock individual concerns

**Trade-offs:**
- Lost: Single model simplicity
- Gained: Maintainability, performance, testability

---

## Additional Resources

### Related Documentation

- **Quick Start:** [CLAUDE.md](../CLAUDE.md) - Daily commands
- **Celery Guide:** [CELERY.md](CELERY.md) - Background processing
- **Reference:** `REFERENCE.md` - Commands and configs (to be created)
- **Rules:** `RULES.md` - Mandatory patterns (to be created)

### Key Files

- **Settings:** `intelliwiz_config/settings/` (base, development, production)
- **URLs:** `intelliwiz_config/urls_optimized.py`
- **User models:** `apps/peoples/models/`
- **Celery config:** `intelliwiz_config/celery.py`
- **Middleware:** `apps/core/middleware/`

### Design Documents

- **Optimization design:** `docs/plans/2025-10-29-claude-md-optimization-design.md`
- **Implementation roadmap:** `IMPLEMENTATION_ROADMAP.md`
- **Archive:** `docs/archive/` (historical refactorings)

---

**Last Updated:** 2025-10-29
**Maintainer:** Solutions Architect
**Review Cycle:** Quarterly
