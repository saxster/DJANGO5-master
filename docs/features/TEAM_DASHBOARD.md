# Team Dashboard - Unified Operations Queue

**User-Friendly Name:** "Team Dashboard"  
**Technical Name:** Unified Operations Queue  
**URL:** `/admin/dashboard/team/`

---

## Overview

The Team Dashboard provides a single, unified view of all tasks, tickets, incidents, and alerts that need attention. It replaces the need to check multiple systems by aggregating work items from across the platform into one prioritized queue.

### Key Features

✅ **Single Source of Truth** - All work in one place  
✅ **Smart Prioritization** - Urgency badges based on deadlines  
✅ **Quick Actions** - One-click assignment and completion  
✅ **Real-Time Updates** - Auto-refresh every 2 minutes  
✅ **User-Friendly Interface** - No technical jargon  
✅ **Mobile Responsive** - Works on all devices  

---

## Architecture

### Database View

The dashboard uses a PostgreSQL view (`v_team_dashboard`) that aggregates:

- **Tickets** from `ticket` table (status: NEW, OPEN, ONHOLD)
- **Incidents** from `noc_incident` table (state: not RESOLVED/CLOSED)
- **Jobs** from `job` table (enabled, not expired)

**Performance Optimizations:**
- Indexed columns for tenant, status, priority, assignee
- Cached query results (60 second TTL)
- LIMIT 50 items per view
- Optimized WHERE clauses on view source tables

### Service Layer

**`TeamDashboardService`** (`apps/core/services/team_dashboard_service.py`)
- Handles data retrieval with filters
- Calculates statistics
- Manages caching
- Multi-tenant isolation

**`QuickActionsService`** (`apps/core/services/quick_actions.py`)
- `assign_to_me()` - Take ownership of a task
- `mark_complete()` - Mark task as done
- `request_help()` - Create help ticket

### Views

**`TeamDashboardView`** - Main dashboard page (GET)  
**`TeamDashboardAPIView`** - AJAX actions (POST/GET)

Both enforce:
- Login required
- Tenant isolation
- CSRF protection
- Permission checks

---

## User Guide

### Accessing the Dashboard

1. Log into IntelliWiz Admin
2. Click "📋 Team Dashboard" in the top navigation
3. Or navigate to `/admin/dashboard/team/`

### Quick Filters

**📋 My Tasks** - Show only items assigned to you  
**👥 All Tasks** - Show all items for your tenant  
**🆘 Needs Assignment** - Show unassigned items  

### Priority Badges

- 🔥 **Critical** - Highest priority
- 🔴 **High** - Needs attention soon
- 🟠 **Medium** - Normal priority
- 🟢 **Normal/Low** - Can wait

### Urgency Badges

- ⏰ **Overdue** - Past deadline!
- ⚡ **Due Soon** - Due within 2 hours
- 📅 **Coming Up** - Due within 24 hours
- ✅ **On Track** - No immediate deadline

### Quick Actions

**👤 Take It** - Assign the task to yourself  
**✅ Mark Done** - Complete your task  
**🆘 Get Help** - Request assistance (creates a high-priority ticket)

### Search

Use the search box to find tasks by:
- Task number (e.g., "T00123", "INC-00456")
- Title/description keywords

---

## Technical Details

### Database Schema

```sql
CREATE VIEW v_team_dashboard AS
SELECT 
    'TICKET' as item_type,
    id as item_id,
    ticketno as item_number,
    ticketdesc as title,
    priority,
    status,
    assignee_id,
    tenant_id,
    created_at,
    priority_score,
    sla_due_at,
    urgency_badge,
    url_namespace
FROM ...
```

### API Endpoints

**GET `/admin/dashboard/team/`**
- Returns HTML dashboard page

**GET `/admin/dashboard/team/api/`**
- Returns JSON with items and stats
- Query params: `status`, `priority`, `assigned_to`, `item_type`, `search`

**POST `/admin/dashboard/team/api/`**
- Performs actions (assign, complete, help)
- CSRF protected
- Multi-tenant validated

### Action Payload Examples

**Assign to Me:**
```json
{
  "action": "assign_to_me",
  "item_type": "TICKET",
  "item_id": 123,
  "note": "Taking this on"
}
```

**Mark Complete:**
```json
{
  "action": "mark_complete",
  "item_type": "INCIDENT",
  "item_id": 456,
  "note": "Fixed the issue"
}
```

**Request Help:**
```json
{
  "action": "request_help",
  "item_type": "TICKET",
  "item_id": 789,
  "help_message": "Not sure how to proceed with this customer request"
}
```

### Cache Keys

- `team_dashboard:{tenant_id}:{user_id}:{filters_hash}` - Item list (60s)
- `team_dashboard_stats:{tenant_id}:{user_id}` - Statistics (30s)

Cache is automatically invalidated when:
- User takes action (assign, complete)
- Items are created/updated

---

## Installation & Setup

### 1. Run Migration

```bash
python manage.py migrate core 0020_add_team_dashboard_view
```

This creates:
- `v_team_dashboard` database view
- Performance indexes on source tables

### 2. Verify URLs

The dashboard is automatically available at `/admin/dashboard/team/` via `apps/core/urls_admin.py`.

### 3. Test Access

```bash
# Open in browser
open http://localhost:8000/admin/dashboard/team/

# Or test API
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/admin/dashboard/team/api/
```

### 4. Verify Database View

```sql
-- Check view exists
SELECT * FROM v_team_dashboard LIMIT 5;

-- Verify indexes
\d ticket
\d noc_incident
\d job
```

---

## Validation Checklist

✅ **Database View Created**
```bash
python manage.py dbshell
SELECT COUNT(*) FROM v_team_dashboard;
```

✅ **URLs Configured**
```bash
python manage.py show_urls | grep team_dashboard
```

✅ **Filters Work**
- Test "My Tasks" filter
- Test "All Tasks" filter
- Test "Needs Assignment" filter
- Test search functionality

✅ **Actions Work**
- Take ownership of a task
- Mark task as complete
- Request help

✅ **Real-Time Updates**
- Dashboard auto-refreshes every 2 minutes
- Cache invalidates after actions

✅ **Mobile Responsive**
- Test on phone/tablet
- Verify layout adapts

✅ **Security**
- Tenant isolation enforced
- CSRF protection active
- Permission checks work

---

## Troubleshooting

### Dashboard shows no items

**Check database view:**
```sql
SELECT COUNT(*) FROM v_team_dashboard WHERE tenant_id = YOUR_TENANT_ID;
```

If count is 0, verify source tables have data:
```sql
SELECT COUNT(*) FROM ticket WHERE status IN ('NEW', 'OPEN', 'ONHOLD');
SELECT COUNT(*) FROM noc_incident WHERE state NOT IN ('RESOLVED', 'CLOSED');
```

### Actions not working

**Check CSRF token:**
- Open browser console
- Look for 403 Forbidden errors
- Verify `csrftoken` cookie exists

**Check permissions:**
- User must be logged in
- User must belong to a tenant
- User must have permission for the item

### Cache not updating

**Clear cache manually:**
```python
from django.core.cache import cache
cache.clear()
```

**Disable cache for testing:**
```python
# In settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
```

### Performance issues

**Check query performance:**
```sql
EXPLAIN ANALYZE SELECT * FROM v_team_dashboard WHERE tenant_id = 1 LIMIT 50;
```

**Verify indexes:**
```sql
\d ticket
-- Should show: idx_ticket_dashboard

\d noc_incident
-- Should show: idx_incident_dashboard
```

**Monitor cache hit rate:**
```bash
# Check Redis (if using Redis cache)
redis-cli INFO stats
```

---

## Future Enhancements

### Phase 2
- [ ] WebSocket real-time updates (no page reload)
- [ ] Bulk actions (assign multiple items)
- [ ] Custom filters (by client, site, date range)
- [ ] Export to CSV/Excel
- [ ] Email digest of daily tasks

### Phase 3
- [ ] Mobile app integration
- [ ] Push notifications for urgent items
- [ ] Task analytics dashboard
- [ ] Smart assignment recommendations
- [ ] SLA violation alerts

### Phase 4
- [ ] Kanban board view
- [ ] Calendar view
- [ ] Team workload balancing
- [ ] Gamification (points, badges)
- [ ] Integration with external tools (Slack, Teams)

---

## Related Documentation

- [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md)
- [Service Layer Pattern (ADR 003)](../architecture/adr/003-service-layer-pattern.md)
- [Multi-Tenancy Security](../architecture/MULTI_TENANCY_SECURITY.md)
- [Performance Optimization](../architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md)

---

**Created:** November 7, 2025  
**Maintainer:** Development Team  
**Review Cycle:** Quarterly  
**Status:** ✅ Complete and Production Ready
