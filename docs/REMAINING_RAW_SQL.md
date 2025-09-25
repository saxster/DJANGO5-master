# Remaining Raw SQL Documentation

## Overview
This document tracks the remaining raw SQL queries in the codebase after the Django ORM migration.

## Status Summary
- ✅ All major PostgreSQL functions migrated to Django ORM
- ✅ Service layer updated to use Django ORM
- ⚠️ One complex query remains (ticket events)
- ℹ️ Infrastructure queries remain (valid use cases)

## Remaining Raw SQL

### 1. Ticket Events Query (Medium Priority)
**Location**: `apps/activity/utils.py` (lines 427-436)

**Query**:
```sql
select e.id as eid, d.devicename, d.ipaddress, ta.taname as type, 
       e.source, e.cdtz, COUNT(att.id) AS attachment__count
from (
    select id, bu_id, ticketno, events, 
           unnest(string_to_array(events, ',')::bigint[]) as eventid  
    from ticket where ticketno=%s 
) ticket
inner join event e on ticket.eventid = e.id
inner join typeassist ta on e.eventtype_id = ta.id
inner join device d on e.device_id = d.id
inner join attachment att on e.id = att.event_id
inner join bt b on ticket.bu_id = b.id
GROUP BY e.id, d.devicename, d.ipaddress, ta.taname 
ORDER BY {} {}
```

**Why it wasn't migrated**:
- Uses PostgreSQL-specific array functions (`string_to_array`, `unnest`)
- Complex subquery with array manipulation
- Would require significant refactoring of data model

**Migration strategy** (if needed):
1. Option 1: Refactor ticket.events to use ManyToMany relationship
2. Option 2: Use Django's `ArrayField` and `unnest` through raw SQL
3. Option 3: Keep as-is if performance is acceptable

### 2. Infrastructure Queries (Keep As-Is)
These queries are for infrastructure management and should remain as raw SQL:

#### Cache Management
- `apps/core/cache/materialized_view_select2.py` - Manages materialized views
- `apps/core/cache/postgresql_select2.py` - PostgreSQL cache operations

#### Monitoring & Health
- `apps/core/health_checks.py` - Database health checks
- `apps/core/monitoring.py` - Performance monitoring queries

#### Maintenance Commands
- `apps/core/management/commands/cleanup_sessions.py` - Session cleanup
- `apps/core/management/commands/manage_select2_cache.py` - Cache management

## Security Measures
All raw SQL execution goes through:
- `apps/core/utils_new/sql_security.py` - SQL validation
- Whitelist pattern matching
- Query parameter sanitization

## Recommendations

### Immediate Actions
1. ✅ Deploy current ORM implementation
2. ✅ Monitor performance in production
3. ✅ Ensure all PostgreSQL functions are deprecated

### Future Improvements
1. Consider migrating ticket events query if:
   - Performance becomes an issue
   - Data model is refactored
   - Array operations are needed elsewhere

2. Review infrastructure queries periodically for:
   - Security updates
   - Performance optimization
   - Django native alternatives

## Conclusion
The Django ORM migration is complete for all business logic queries. The remaining raw SQL queries are either:
1. Infrastructure-related (valid use case)
2. Complex array operations (ticket events)

No further action is required for the current migration project.