# System Architecture

> **Complete architectural overview of the enterprise facility management platform**

---

## System Profile

**Enterprise facility management platform** for multi-tenant security guarding, facilities, and asset management.

### Technology Stack

- **Framework**: Django 5.2.1
- **Database**: PostgreSQL 14.2 with PostGIS
- **APIs**: REST at `/api/v1/` (legacy query layer retired Oct 2025)
- **Task Queue**: PostgreSQL-native (replaced Celery dependency for sessions)
- **Authentication**: Custom user model (`peoples.People`) with multi-model architecture
- **Multi-tenancy**: Tenant-aware models with database routing
- **Caching**: Redis with environment-specific optimization
- **Real-time**: WebSockets via Django Channels

---

## Core Business Domains

| Domain | Primary Apps | Purpose |
|--------|-------------|---------|
| **Operations** | `activity`, `work_order_management`, `scheduler` | Task management, PPM, scheduling |
| **Assets** | `inventory`, `monitoring` | Asset tracking, maintenance |
| **People** | `peoples`, `attendance` | Authentication, attendance, expenses |
| **Help Desk** | `y_helpdesk` | Ticketing, escalations, SLAs |
| **Reports** | `reports` | Analytics, scheduled reports |
| **Security** | `noc`, `face_recognition` | AI monitoring, biometrics |

---

## URL Architecture (Domain-Driven)

### Optimized Structure

Located in `intelliwiz_config/urls_optimized.py`:

```text
/operations/     # Tasks, tours, work orders
/assets/         # Inventory, maintenance
/people/         # Directory, attendance
/help-desk/      # Tickets, escalations
/reports/        # Analytics
/admin/          # Administration
```

### Backward Compatibility

Legacy URLs automatically redirect to new structure for mobile app compatibility.

---

## Refactored Architecture (Sep 2025)

### God File Elimination Strategy

Monolithic files split into focused modules with backward compatibility.

### Reports Views (5 modules, 2,070 lines)

```python
# apps/reports/views/
base.py                   # Shared base classes, forms
template_views.py         # Template management
configuration_views.py    # Report configuration
export_views.py           # Download + export endpoints
schedule_views.py         # Scheduling + design preview
pdf_views.py              # PDF helpers (WeasyPrint/Pandoc)
frappe_integration_views.py  # ERP integrations
__init__.py              # Backward compatibility

# Import patterns
from apps.reports.views import DownloadReports  # Still works (legacy)
from apps.reports.views.export_views import DownloadReports  # Recommended
```

**Reference**: `GOD_FILE_REFACTORING_PHASES_5-7_COMPLETE.md`

### Onboarding Admin (9 modules, 1,796 lines)

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

### Service Layer (6 modules, 31 functions)

```python
# apps/service/services/
database_service.py       # 10 DB operations
file_service.py          # 4 file operations (SECURE - Rule #14 compliant)
geospatial_service.py    # 3 geospatial operations
job_service.py           # 6 job/tour operations (RACE-PROTECTED)
crisis_service.py        # 3 crisis management

# Security-critical functions
from apps.service.services.file_service import perform_secure_uploadattachment  # Path traversal protected
from apps.service.services.job_service import update_adhoc_record  # Distributed lock protected
```

### Reports Services (5 modules - Oct 2025)

```python
# apps/reports/services/
report_data_service.py           # Data retrieval and processing
report_generation_service.py     # Report generation workflows
report_export_service.py         # Export functionality (CSV/Excel/JSON)
report_template_service.py       # Template management
frappe_service.py                # Frappe/ERPNext ERP integration ✨ NEW (Oct 2025)

# Frappe ERP Integration (Type-Safe)
from apps.reports.services import get_frappe_service, FrappeCompany, PayrollDocumentType

service = get_frappe_service()
customers = service.get_customers(FrappeCompany.SPS)
payroll = service.get_payroll_data(company=FrappeCompany.SPS, ...)
```

**New Features** (Oct 2025):
- ✅ Type-safe ERP integration with Enums
- ✅ Environment-based configuration (no hardcoded credentials)
- ✅ Connection pooling + caching (5min TTL)
- ✅ Comprehensive error handling (3 custom exceptions)
- ✅ Backward compatibility wrappers (deprecated legacy functions)

**Reference**: `apps/reports/services/frappe_service.py` (593 lines)

---

## Custom User Model Architecture

### Split Model Design (Sep 2025)

**Reducing complexity through model separation**

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

### Why Split Models?

1. **Maintainability**: Each model < 150 lines (architectural limit)
2. **Performance**: Selective loading (don't load profile for auth checks)
3. **Security**: Separation of concerns (auth vs. personal data)
4. **Backward Compatibility**: Legacy code works unchanged

---

## Security Architecture

### Multi-Layer Middleware Stack

1. `SQLInjectionProtectionMiddleware` - SQL injection prevention
2. `XSSProtectionMiddleware` - XSS protection
3. `CorrelationIDMiddleware` - Request tracking
4. `APIDeprecationMiddleware` - Lifecycle enforcement for REST endpoints
5. `PathBasedRateLimitMiddleware` - Endpoint-specific throttling
6. `RateLimitMonitoringMiddleware` - Rate limit analytics
7. Content Security Policy (CSP) with violation reporting
8. API authentication with HMAC signing support

### Rate Limiting & DoS Protection

- **Path-based throttles** tuned for REST v1/v2 endpoints
- **Burst controls** enforced via PostgreSQL-backed counters
- **Monitoring** exported via Prometheus metrics for Celery/web
- **Automation**: notifications triggered when thresholds breach targets

### Authentication Flow

```text
1. User login → JWT token generation
2. Token stored in HttpOnly cookie (XSS protection)
3. CSRF token in header (CSRF protection)
4. Middleware validates both tokens
5. Request proceeds with authenticated user context
```

---

## Database Architecture

### Primary Database

- **Engine**: PostgreSQL 14.2+
- **Extensions**: PostGIS for geospatial queries
- **Routing**: `TenantDbRouter` for multi-tenant isolation
- **Sessions**: PostgreSQL (not Redis) - 20ms trade-off approved
- **Connection pooling**: Optimized for read-heavy workloads

### Query Optimization

```python
# ✅ Use select_related for ForeignKey
users = People.objects.select_related('profile', 'organizational').all()

# ✅ Use prefetch_related for ManyToMany
tasks = Task.objects.prefetch_related('assigned_people').all()

# ✅ Custom query helpers
users = People.objects.with_full_details()  # Combines both
```

---

## Caching Strategy

### Redis Configuration

**Environment-specific optimization**

- **Production**: 100 connections, JSON serializer, compression enabled
- **Development**: 20 connections, JSON serializer, no compression
- **Testing**: Local memory or Redis, fast timeouts

### Cache Backends

| Cache Name | Backend | Database | Purpose |
|------------|---------|----------|---------|
| `default` | Redis | DB 1 | General Django caching |
| `select2` | PostgreSQL | N/A | Materialized views for dropdowns |
| `sessions` | Redis | DB 4 | User sessions (optional) |
| `celery_results` | Redis | DB 1 | Task results (shared with default) |

### Select2 Migration (Oct 2025)

✅ **COMPLETE** - Migrated from Redis to PostgreSQL materialized views

```python
# Select2 now uses PostgreSQL-based materialized views (NOT Redis!)
CACHES['select2'] = {
    'BACKEND': 'apps.core.cache.materialized_view_select2.MaterializedViewSelect2Cache',
    'LOCATION': '',  # No Redis needed
    'OPTIONS': {
        'MAX_ENTRIES': 10000,  # Production
        'CULL_FREQUENCY': 3,
    },
}

# Materialized views available:
# - mv_people_dropdown (users)
# - mv_location_dropdown (locations)
# - mv_asset_dropdown (assets)
```

---

## Multi-Tenancy

### Database Routing

```python
# apps/tenants/router.py
class TenantDbRouter:
    def db_for_read(self, model, **hints):
        # Route based on tenant_id in request context
        return get_tenant_database()

    def db_for_write(self, model, **hints):
        return get_tenant_database()
```

### Tenant Isolation

- **Row-Level**: `tenant_id` on all models
- **Schema-Level**: Separate PostgreSQL schemas per tenant
- **Database-Level**: Dedicated databases for enterprise clients

---

## Major Refactorings

### "schedhuler" → "scheduler" Rename (Oct 2025)

**Status**: ✅ COMPLETE

- **Scope**: 719 occurrences across 157 files
- **App directory**: `apps/schedhuler/` → `apps/scheduler/`
- **URL patterns**: `/schedhuler/` → `/scheduler/` (backwards compatible)
- **Migration**: Django migration history preserved

**Reference**: `SCHEDHULER_TO_SCHEDULER_RENAME_COMPLETE.md`

---

## Performance Characteristics

### Response Time Targets

- **API endpoints**: <200ms (p95)
- **Dashboard load**: <1s (p95)
- **Report generation**: <5s (p95)
- **WebSocket latency**: <100ms

### Scalability

- **Concurrent users**: 1,000+ supported
- **Database connections**: 100 pool size
- **Redis connections**: 100 pool size
- **Celery workers**: 8 per instance, horizontal scaling

---

**Last Updated**: October 29, 2025
**Maintainer**: Architecture Team
**Related**: [Critical Rules](../../CLAUDE.md#critical-rules), [Security Architecture](../../CLAUDE.md#security-architecture)
