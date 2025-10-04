# Dashboard Catalog

**Comprehensive registry of all monitoring and analytics dashboards across the YOUTILITY5 platform.**

**Last Updated:** 2025-10-04
**Owner:** Dashboard Infrastructure Team
**Status:** Production Ready

---

## Table of Contents

- [Overview](#overview)
- [Quick Access](#quick-access)
- [Dashboard Categories](#dashboard-categories)
- [Complete Dashboard Listing](#complete-dashboard-listing)
- [Usage Patterns](#usage-patterns)
- [Troubleshooting](#troubleshooting)

---

## Overview

The YOUTILITY5 platform provides **unified dashboard infrastructure** with role-based access control, real-time monitoring capabilities, and standardized API contracts.

### Key Features

✅ **Central Registry** - Single source of truth for all dashboards
✅ **Role-Based Access** - Automatic permission filtering
✅ **Unified API** - Consistent response structure across all dashboards
✅ **Performance Optimized** - Intelligent caching with <200ms TTFB
✅ **Export Capabilities** - CSV/JSON export for all dashboards
✅ **Real-Time Updates** - WebSocket support for selected dashboards

### Architecture

```
Dashboard Hub (/dashboards/)
├── Core Dashboards
├── Security Dashboards
├── Admin/Infrastructure Dashboards
├── NOC Dashboards
├── Domain-Specific Dashboards
└── Operational Dashboards
```

---

## Quick Access

### Dashboard Hub

**URL:** `/dashboards/`
**Permission:** Authenticated users
**Description:** Unified access point to all dashboards with role-aware filtering

**Features:**
- Category-based organization
- Search functionality
- Recent dashboards tracking
- Favorites support (coming soon)

---

## Dashboard Categories

### Core Dashboards (`core`)

Primary operational dashboards for day-to-day monitoring.

| Dashboard | Purpose | Priority |
|-----------|---------|----------|
| Main Dashboard | System overview and key metrics | 1 |

---

### Security Dashboards (`security`)

Security monitoring, threat detection, and compliance tracking.

| Dashboard | Purpose | Priority |
|-----------|---------|----------|
| CSRF Violations | CSRF attack monitoring and blocking | 30 |
| GraphQL Permission Audit | Authorization analytics and denials | 31 |
| Rate Limiting | Rate limit analytics and blocked requests | 32 |

---

### Admin/Infrastructure Dashboards (`admin_infra`)

System administration and infrastructure monitoring.

| Dashboard | Purpose | Priority |
|-----------|---------|----------|
| Database Performance | PostgreSQL performance metrics | 20 |
| Redis Performance | Cache performance and health | 21 |
| Task Monitoring | Background task tracking | 22 |
| State Transitions | State machine monitoring | 23 |

---

### NOC Dashboards (`noc`)

Network Operations Center dashboards for security intelligence.

| Dashboard | Purpose | Priority |
|-----------|---------|----------|
| NOC Overview | Security intelligence overview | 40 |
| Security Scorecard | 7 Non-Negotiables monitoring | 41 |

---

### Domain-Specific Dashboards

**Activity Module:**
- Meter Reading Dashboard (`/activity/meter_readings/`)
- Vehicle Entry Dashboard (`/activity/vehicle_entries/`)

**Attendance Module:**
- AI Analytics Dashboard (`/attendance/ai-analytics/`) - Staff only

**Journal Module:**
- Wellness Dashboard (`/journal/dashboard/`)

**StreamLab Module:**
- Stream Testing Dashboard (`/streamlab/`)

**People Onboarding:**
- Onboarding Dashboard (`/people-onboarding/`)

---

## Complete Dashboard Listing

### Core - Main Dashboard

**ID:** `core_main`
**Title:** Main Dashboard
**URL:** `/dashboard/`
**Permission:** Authenticated
**Category:** core
**Priority:** 1
**Refresh Interval:** 30 seconds
**Real-Time:** No

**Description:**
System overview and key operational metrics including:
- Total people count
- Active assets
- Today's attendance
- Pending tasks

**Owner:** Core Team
**SLO:** <200ms TTFB on cached views
**Runbook:** See operational docs

---

### Admin/Infra - Database Performance

**ID:** `core_database`
**Title:** Database Performance
**URL:** `/admin/database/`
**Permission:** Staff
**Category:** admin_infra
**Priority:** 20
**Refresh Interval:** None (on-demand)
**Real-Time:** No

**Description:**
PostgreSQL performance monitoring with:
- Query execution plans
- Slow query analysis
- Connection pool metrics
- Index usage statistics

**Owner:** Infrastructure Team
**SLO:** <500ms TTFB
**Runbook:** `docs/database/performance-monitoring.md`

---

### Admin/Infra - Redis Performance

**ID:** `core_redis`
**Title:** Redis Performance
**URL:** `/admin/redis/dashboard/`
**Permission:** Staff
**Category:** admin_infra
**Priority:** 21
**Refresh Interval:** None (on-demand)
**Real-Time:** No

**Description:**
Redis performance metrics including:
- Memory usage and fragmentation
- Hit/miss ratios
- Operations per second
- Connection metrics

**Owner:** Infrastructure Team
**SLO:** <500ms TTFB
**Runbook:** `docs/REDIS_OPERATIONS_GUIDE.md`

---

### Admin/Infra - Task Monitoring

**ID:** `core_tasks`
**Title:** Task Monitoring
**URL:** `/admin/tasks/dashboard`
**Permission:** Staff
**Category:** admin_infra
**Priority:** 22
**Refresh Interval:** None (on-demand)
**Real-Time:** No

**Description:**
Background task monitoring with:
- Task execution metrics
- Idempotency analysis
- Schedule conflict detection
- Queue health status

**Owner:** Core Team
**SLO:** <200ms TTFB
**Runbook:** `IDEMPOTENCY_IMPLEMENTATION_GUIDE.md`

---

### Admin/Infra - State Transitions

**ID:** `core_state_transitions`
**Title:** State Transitions
**URL:** `/admin/state-transitions/dashboard/`
**Permission:** Staff
**Category:** admin_infra
**Priority:** 23
**Refresh Interval:** None (on-demand)
**Real-Time:** No

**Description:**
State machine transition monitoring:
- Transition success/failure rates
- Failure analysis
- Performance trends
- Entity-specific history

**Owner:** Core Team
**SLO:** <500ms TTFB
**Runbook:** `docs/STATE_MACHINE_DEVELOPER_GUIDE.md`

---

### Security - CSRF Violations

**ID:** `security_csrf`
**Title:** CSRF Violations
**URL:** `/admin/security/csrf-violations/`
**Permission:** Staff
**Category:** security
**Priority:** 30
**Refresh Interval:** 15 seconds
**Real-Time:** Yes (recommended)

**Description:**
CSRF attack monitoring and threat detection:
- Real-time violation tracking
- Geographic analysis
- Automated IP blocking
- Attack pattern recognition

**Owner:** Security Team
**SLO:** <500ms TTFB
**Runbook:** `docs/security/csrf-monitoring.md`

**Alerts:**
- >50 violations/hour → High severity
- >100 violations/hour → Critical severity

---

### Security - GraphQL Permission Audit

**ID:** `security_graphql_audit`
**Title:** GraphQL Permission Audit
**URL:** `/admin/security/graphql-audit/`
**Permission:** Staff
**Category:** security
**Priority:** 31
**Refresh Interval:** 30 seconds
**Real-Time:** Yes (recommended)

**Description:**
GraphQL authorization analytics:
- Permission denial tracking
- Field access patterns
- Object access violations
- Introspection attempts
- Mutation chaining violations

**Owner:** Security Team
**SLO:** <500ms TTFB
**Runbook:** `docs/security/graphql-security-guide.md`

---

### Security - Rate Limiting

**ID:** `security_rate_limiting`
**Title:** Rate Limiting
**URL:** `/security/rate-limiting/dashboard/`
**Permission:** Staff
**Category:** security
**Priority:** 32
**Refresh Interval:** None (on-demand)
**Real-Time:** No

**Description:**
Rate limiting analytics:
- Blocked request tracking
- User/IP blocking patterns
- Rate limit violations
- Threshold recommendations

**Owner:** Security Team
**SLO:** <200ms TTFB
**Runbook:** `docs/security/rate-limiting-architecture.md`

---

## Usage Patterns

### For End Users

1. **Access Dashboard Hub:** Navigate to `/dashboards/`
2. **Browse Categories:** Filter dashboards by category
3. **Search:** Use search bar to find specific dashboards
4. **Recent Access:** Quick access to recently viewed dashboards

### For Developers

```python
from apps.core.registry import dashboard_registry

# Register a new dashboard
dashboard_registry.register(
    id='my_dashboard',
    title='My Custom Dashboard',
    url='/my/dashboard/',
    permission='myapp.view_dashboard',
    category='custom',
    description='Custom analytics dashboard',
    icon='fa-chart',
    priority=50,
    refresh_interval=60  # Auto-refresh every 60 seconds
)

# Get dashboards for user
user_dashboards = dashboard_registry.get_dashboards_for_user(request.user)

# Search dashboards
results = dashboard_registry.search('performance')
```

### For Administrators

**Dashboard Health Checks:**
```bash
# Test all dashboard URLs resolve
python -m pytest apps/core/tests/test_dashboard_infrastructure.py::test_all_dashboards_accessible -v

# Validate permissions
python -m pytest apps/core/tests/test_dashboard_infrastructure.py::test_dashboard_permissions -v
```

---

## Troubleshooting

### Dashboard Not Appearing

**Possible Causes:**
1. User lacks required permission
2. Dashboard not registered in registry
3. URL routing issue

**Solution:**
```bash
# Check if dashboard is registered
python manage.py shell
>>> from apps.core.registry import dashboard_registry
>>> dashboard_registry.get('dashboard_id')

# Check user permissions
>>> user.has_perm('app.permission')
```

---

### Dashboard Loading Slowly

**Possible Causes:**
1. Cache not working
2. Heavy database queries
3. Missing indexes

**Solution:**
- Check cache hit rate in response (`cache_info.hit`)
- Review query performance with `/admin/database/`
- Enable query logging and analyze slow queries

---

### Permission Denied

**Possible Causes:**
1. User not authenticated
2. Missing required permission
3. Incorrect permission string in registry

**Solution:**
```python
# Verify dashboard permission requirements
dashboard = dashboard_registry.get('dashboard_id')
print(f"Required permission: {dashboard.permission}")

# Check user permissions
print(f"User permissions: {list(user.get_all_permissions())}")
```

---

## API Reference

### Dashboard Hub Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboards/` | GET | Main dashboard hub |
| `/dashboards/search/` | GET | Search dashboards |
| `/dashboards/categories/` | GET | Get categories |
| `/dashboards/metrics/` | GET | Usage metrics |
| `/dashboards/track/<id>/` | POST | Track access |

### Standard Dashboard API Response

```json
{
  "version": "v1",
  "timestamp": "2025-10-04T12:00:00Z",
  "tenant": {
    "bu_id": 123,
    "client_id": 456
  },
  "dashboard_id": "core_main",
  "data": {
    "metrics": {...},
    "charts": [...],
    "alerts": [...]
  },
  "cache_info": {
    "hit": true,
    "ttl": 300,
    "generated_at": "2025-10-04T12:00:00Z"
  }
}
```

---

## SLO Summary

| Dashboard Category | TTFB Target | Uptime Target | Error Rate Target |
|-------------------|-------------|---------------|-------------------|
| Core | <200ms | 99.9% | <0.1% |
| Security | <500ms | 99.5% | <0.5% |
| Admin/Infra | <500ms | 99% | <1% |
| Domain-Specific | <1s | 99% | <1% |

---

## Migration & Deprecation

### Deprecated Dashboards

None currently.

### Planned Additions

- **Q4 2025:** Real-time WebSocket support for all security dashboards
- **Q1 2026:** Machine learning-powered anomaly detection dashboards
- **Q1 2026:** Multi-dashboard comparison views

---

## Related Documentation

- **Dashboard Development Guide:** `docs/development/dashboard-development-guide.md`
- **API Contracts:** `docs/API_BULK_OPERATIONS.md`
- **Security Guide:** `docs/security/graphql-security-guide.md`
- **Performance Guide:** `docs/REDIS_OPERATIONS_GUIDE.md`

---

**Questions or Issues?** Contact the Dashboard Infrastructure Team or file an issue in the project repository.
